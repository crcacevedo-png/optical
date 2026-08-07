"""Modulo de facturacion (Stripe).

Flujo self-service para que un admin cambie el plan de su optica:
1. Admin ve `/my-plan`, elige plan y ciclo (mensual/anual).
2. Frontend llama `POST /api/billing/checkout` -> backend crea sesion de Stripe.
3. Redirect a Stripe Checkout.
4. Al pagar Stripe manda webhook `/api/webhook/stripe` -> actualizamos company.plan_id.
5. Frontend hace polling a `/api/billing/status/{session_id}` para redirigir tras el pago.

Nota: usa `emergentintegrations` con `STRIPE_API_KEY=sk_test_emergent` (sandbox
compartido). En produccion cambiar por la key propia del cliente Stripe.
"""
import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from bson import ObjectId

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)

from db import db, serialize_doc
from auth_utils import get_current_user

router = APIRouter(prefix="/billing", tags=["Facturacion"])


class CheckoutRequest(BaseModel):
    plan_id: str = Field(..., description="_id del plan en Mongo")
    billing_cycle: str = Field("monthly", pattern="^(monthly|yearly)$")
    origin_url: str = Field(..., description="window.location.origin del frontend")


def _get_stripe_checkout(request: Request) -> StripeCheckout:
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    return StripeCheckout(
        api_key=os.environ["STRIPE_API_KEY"],
        webhook_url=webhook_url,
    )


def _plan_amount(plan: dict, cycle: str) -> tuple[float, str]:
    """Devuelve (amount_float, currency). Preferencia por price_monthly/price_yearly del plan."""
    key = "price_yearly" if cycle == "yearly" else "price_monthly"
    amount = plan.get(key)
    if amount is None:
        # Fallback: usa `price` como mensual; anual = mensual x 10 (2 meses gratis)
        base = float(plan.get("price", 0) or 0)
        amount = base * 10 if cycle == "yearly" else base
    amount = float(amount)
    currency = (plan.get("currency") or "gtq").lower()
    return amount, currency


@router.post("/checkout")
async def create_checkout(
    data: CheckoutRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden cambiar el plan")

    try:
        plan_oid = ObjectId(data.plan_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="plan_id invalido") from exc

    plan = await db.plans.find_one({"_id": plan_oid})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    amount, currency = _plan_amount(plan, data.billing_cycle)
    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Este plan es gratuito. Contacta al superadmin para asignarlo sin cobro.",
        )

    origin = data.origin_url.rstrip("/")
    success_url = f"{origin}/my-plan?session_id={{CHECKOUT_SESSION_ID}}&status=success"
    cancel_url = f"{origin}/my-plan?status=cancelled"

    stripe_checkout = _get_stripe_checkout(request)
    req = CheckoutSessionRequest(
        amount=amount,
        currency=currency,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "company_id": user["company_id"],
            "plan_id": data.plan_id,
            "plan_name": plan.get("name", ""),
            "billing_cycle": data.billing_cycle,
            "user_id": user["_id"],
            "user_email": user.get("email", ""),
        },
    )
    session = await stripe_checkout.create_checkout_session(req)

    # Registrar la transaccion ANTES del redirect (idempotencia + polling)
    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "company_id": ObjectId(user["company_id"]),
        "plan_id": plan_oid,
        "plan_name": plan.get("name", ""),
        "billing_cycle": data.billing_cycle,
        "user_id": ObjectId(user["_id"]),
        "user_email": user.get("email", ""),
        "amount": amount,
        "currency": currency,
        "status": "initiated",
        "payment_status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"checkout_url": session.url, "session_id": session.session_id}


@router.get("/status/{session_id}")
async def get_status(session_id: str, request: Request):
    """Polling endpoint publico (sin auth). Necesario porque Stripe puede redirigir
    desde un dominio externo y la cookie de sesion podria no viajar. La sesion
    Stripe misma es opaca a terceros — solo devolvemos estado, no datos sensibles."""
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaccion no encontrada")

    # Si aun no esta 'paid', consultar Stripe directamente (webhook puede tardar)
    if tx.get("payment_status") != "paid":
        try:
            stripe_checkout = _get_stripe_checkout(request)
            status = await stripe_checkout.get_checkout_status(session_id)
            if status.payment_status == "paid" or status.status == "complete":
                await _mark_paid_and_apply_plan(session_id)
                tx = await db.payment_transactions.find_one({"session_id": session_id})
        except Exception:
            pass  # transient — devolvemos el estado en DB

    return {
        "session_id": tx["session_id"],
        "status": tx.get("status"),
        "payment_status": tx.get("payment_status"),
        "plan_name": tx.get("plan_name"),
        "billing_cycle": tx.get("billing_cycle"),
    }


async def _mark_paid_and_apply_plan(session_id: str) -> None:
    """Idempotente: si no esta marcado como pagado, marca y aplica el plan a la empresa."""
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    if not tx or tx.get("payment_status") == "paid":
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    result = await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {
            "status": "completed",
            "payment_status": "paid",
            "paid_at": now_iso,
            "updated_at": now_iso,
        }},
    )
    if result.modified_count == 0:
        return  # Ya estaba pagado por otra via

    # Aplicar plan a la empresa + registrar historial
    cid = tx["company_id"]
    plan_oid = tx["plan_id"]
    company = await db.companies.find_one({"_id": cid}, {"plan_id": 1, "name": 1})
    old_plan_id = company.get("plan_id") if company else None
    old_plan_name = None
    if old_plan_id:
        old = await db.plans.find_one({"_id": old_plan_id}, {"name": 1})
        if old:
            old_plan_name = old.get("name")

    await db.companies.update_one(
        {"_id": cid},
        {"$set": {
            "plan_id": plan_oid,
            "billing_cycle": tx.get("billing_cycle"),
            "last_payment_at": now_iso,
            "updated_at": now_iso,
        }},
    )

    await db.plan_history.insert_one({
        "company_id": cid,
        "company_name": (company or {}).get("name", ""),
        "old_plan_name": old_plan_name,
        "new_plan_name": tx.get("plan_name"),
        "old_plan_id": old_plan_id,
        "new_plan_id": plan_oid,
        "changed_by": tx.get("user_id"),
        "changed_by_name": tx.get("user_email", ""),
        "billing_cycle": tx.get("billing_cycle"),
        "amount_paid": tx.get("amount"),
        "currency": tx.get("currency"),
        "session_id": session_id,
        "changed_at": now_iso,
    })


@router.get("/my-transactions")
async def my_transactions(user: dict = Depends(get_current_user), limit: int = 20):
    """Historial de pagos de la empresa del usuario actual."""
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Acceso denegado")
    query = {} if user["role"] == "superadmin" else {"company_id": ObjectId(user["company_id"])}
    txs = await db.payment_transactions.find(query).sort("_id", -1).limit(min(limit, 100)).to_list(limit)
    for t in txs:
        serialize_doc(t)
        if isinstance(t.get("company_id"), ObjectId):
            t["company_id"] = str(t["company_id"])
        if isinstance(t.get("plan_id"), ObjectId):
            t["plan_id"] = str(t["plan_id"])
        if isinstance(t.get("user_id"), ObjectId):
            t["user_id"] = str(t["user_id"])
    return txs


# ─── Webhook Stripe (path exacto que emergentintegrations espera) ─────────

webhook_router = APIRouter()


@webhook_router.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        stripe_checkout = _get_stripe_checkout(request)
        result = await stripe_checkout.handle_webhook(body, sig)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Webhook invalido: {exc}") from exc

    if result.session_id and result.payment_status == "paid":
        await _mark_paid_and_apply_plan(result.session_id)
    return {"received": True, "event_id": result.event_id}
