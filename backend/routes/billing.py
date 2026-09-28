"""Modulo de facturacion (Stripe) — SUSCRIPCIONES recurrentes.

Flujo self-service para que un admin cambie el plan de su optica:
1. Admin ve `/my-plan`, elige plan y ciclo (mensual/anual).
2. Frontend llama `POST /api/billing/checkout` -> backend crea sesion de Stripe (mode=subscription).
3. Redirect a Stripe Checkout (hosted).
4. Al volver, el frontend hace polling a `/api/billing/status/{session_id}` que consulta a Stripe
   y aplica el plan en cuanto la suscripcion queda activa (idempotente).
5. El estado de la suscripcion (renovaciones, impagos, cancelaciones) se mantiene al dia con una
   sincronizacion diaria: `POST /api/cron/sync-subscriptions` (cron de la plataforma).

Requiere que STRIPE_API_KEY sea la llave secreta REAL de la cuenta Stripe del cliente
(sk_test_... para pruebas, sk_live_... para produccion), agregada en Manage -> Secrets.
La suscripcion recurrente usa el SDK nativo de Stripe (emergentintegrations no soporta subscriptions).
"""
import os
import hmac
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import stripe
from dotenv import dotenv_values
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from bson import ObjectId

from db import db, serialize_doc
from auth_utils import get_current_user
from audit import log_audit

router = APIRouter(prefix="/billing", tags=["Facturacion"])
cron_router = APIRouter(prefix="/cron", tags=["Cron"])


_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# Nombres de variable candidatos, en orden de prioridad. STRIPE_SECRET_KEY va primero
# porque la plataforma NO lo rellena con el default del sandbox; STRIPE_API_KEY queda como
# respaldo (compatibilidad). El placeholder `sk_test_emergent` siempre se ignora.
_STRIPE_KEY_ENV_NAMES = ("STRIPE_SECRET_KEY", "STRIPE_API_KEY")
_STRIPE_PLACEHOLDER = "sk_test_emergent"


def _resolve_stripe_key() -> str:
    """Llave secreta efectiva de Stripe (BYOK, SDK nativo).

    Emergent inyecta el placeholder del sandbox (`sk_test_emergent`) en el entorno del
    proceso bajo `STRIPE_API_KEY`, tanto en preview como en producción, y ese valor puede
    opacar la llave real. Por eso: (1) buscamos una llave REAL en el entorno bajo cualquiera
    de los nombres candidatos (ignorando el placeholder); (2) como respaldo de PREVIEW,
    leemos `backend/.env` (que `load_dotenv(override=False)` no aplica por encima del valor
    inyectado). Si nada es real, devolvemos el placeholder para que `_stripe_configured()`
    lo detecte como "no configurado".
    """
    for name in _STRIPE_KEY_ENV_NAMES:
        v = (os.environ.get(name) or "").strip()
        if v and v != _STRIPE_PLACEHOLDER:
            return v
    file_env = dotenv_values(_ENV_PATH)
    for name in _STRIPE_KEY_ENV_NAMES:
        v = (file_env.get(name) or "").strip()
        if v and v != _STRIPE_PLACEHOLDER:
            return v
    return (os.environ.get("STRIPE_API_KEY") or "").strip()


def _init_stripe():
    stripe.api_key = _resolve_stripe_key()


def _stripe_configured() -> bool:
    """True solo si hay una llave secreta real de Stripe (no el placeholder compartido)."""
    k = _resolve_stripe_key()
    return k.startswith("sk_") and k != _STRIPE_PLACEHOLDER


def _not_configured_error():
    return HTTPException(
        status_code=503,
        detail="Stripe aun no esta configurado. Agrega tu llave secreta de Stripe como STRIPE_SECRET_KEY en Manage -> Secrets y vuelve a desplegar.",
    )


def _plan_amount_cents(plan: dict, cycle: str) -> tuple[int, str]:
    """Devuelve (unit_amount_en_centavos, intervalo). Anual = price_yearly o mensual x10."""
    if cycle == "yearly":
        amt = plan.get("price_yearly")
        if amt is None:
            base = float(plan.get("price_monthly") or plan.get("price", 0) or 0)
            amt = base * 10
        return int(round(float(amt) * 100)), "year"
    amt = plan.get("price_monthly")
    if amt is None:
        amt = float(plan.get("price", 0) or 0)
    return int(round(float(amt) * 100)), "month"


def _lookup_key(plan_id: str, cycle: str) -> str:
    return f"cortexia_{plan_id}_{cycle}"


# ─── Helpers sincronos de Stripe (se ejecutan en asyncio.to_thread) ──────────

def _ensure_product_and_price(plan_id: str, plan_name: str, currency: str,
                              amount_cents: int, interval: str) -> str:
    """Crea/actualiza el Product y el Price recurrente del plan. Devuelve price_id.
    El Price es inmutable en Stripe: si cambia el monto/moneda/intervalo, se desactiva
    el viejo y se crea uno nuevo transfiriendo el lookup_key."""
    cycle = "yearly" if interval == "year" else "monthly"
    lookup = _lookup_key(plan_id, cycle)

    product = None
    for p in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        if (p.get("metadata") or {}).get("emergent_plan_id") == plan_id:
            product = p
            break
    if product is None:
        product = stripe.Product.create(
            name=plan_name,
            metadata={"managed_by": "cortexia", "emergent_plan_id": plan_id},
        )
    elif product.get("name") != plan_name:
        try:
            stripe.Product.modify(product.id, name=plan_name)
        except stripe.error.StripeError:
            pass

    existing = stripe.Price.list(lookup_keys=[lookup], active=True, limit=1).data
    if existing:
        pr = existing[0]
        rec = pr.recurring or {}
        if (pr.unit_amount != amount_cents or pr.currency != currency
                or rec.get("interval") != interval):
            stripe.Price.modify(pr.id, active=False)
            existing = []
    if not existing:
        pr = stripe.Price.create(
            product=product.id,
            unit_amount=amount_cents,
            currency=currency,
            recurring={"interval": interval},
            lookup_key=lookup,
            transfer_lookup_key=True,
        )
    return pr.id


def _ensure_customer(existing_customer_id: Optional[str], company_name: str,
                     admin_email: Optional[str], company_id: str) -> str:
    if existing_customer_id:
        try:
            c = stripe.Customer.retrieve(existing_customer_id)
            if not c.get("deleted"):
                return existing_customer_id
        except stripe.error.StripeError:
            pass
    c = stripe.Customer.create(
        name=company_name,
        email=admin_email or None,
        metadata={"company_id": company_id},
    )
    return c.id


def _create_subscription_session(customer_id: str, price_id: str,
                                 success_url: str, cancel_url: str, metadata: dict):
    # Parametros fixed_by_ui de Stripe Checkout Studio (hosted). automatic_tax off,
    # sin phone, sin promo codes; payment_method_collection=always para suscripcion.
    return stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        billing_address_collection="auto",
        phone_number_collection={"enabled": False},
        automatic_tax={"enabled": False},
        allow_promotion_codes=False,
        payment_method_collection="always",
        metadata=metadata,
        subscription_data={"metadata": metadata},
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan_id: str = Field(..., description="_id del plan en Mongo")
    billing_cycle: str = Field("monthly", pattern="^(monthly|yearly)$")
    origin_url: str = Field(..., description="window.location.origin del frontend")


@router.post("/checkout")
async def create_checkout(data: CheckoutRequest, request: Request, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden cambiar el plan")
    _init_stripe()
    if not _stripe_configured():
        raise _not_configured_error()

    try:
        plan_oid = ObjectId(data.plan_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="plan_id invalido") from exc
    plan = await db.plans.find_one({"_id": plan_oid})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    amount_cents, interval = _plan_amount_cents(plan, data.billing_cycle)
    if amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Este plan es gratuito. El superadmin lo asigna sin cobro.")

    currency = (plan.get("currency") or "usd").lower()
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])}, {"name": 1, "stripe_customer_id": 1})
    company_name = (company or {}).get("name", "Optica")
    existing_customer = (company or {}).get("stripe_customer_id")

    origin = data.origin_url.rstrip("/")
    success_url = f"{origin}/my-plan?session_id={{CHECKOUT_SESSION_ID}}&status=success"
    cancel_url = f"{origin}/my-plan?status=cancelled"
    metadata = {
        "company_id": user["company_id"],
        "plan_id": data.plan_id,
        "plan_name": plan.get("name", ""),
        "billing_cycle": data.billing_cycle,
        "user_id": user["_id"],
        "user_email": user.get("email", ""),
    }

    def _work():
        price_id = _ensure_product_and_price(data.plan_id, plan.get("name", "Plan"), currency, amount_cents, interval)
        customer_id = _ensure_customer(existing_customer, company_name, user.get("email"), user["company_id"])
        session = _create_subscription_session(customer_id, price_id, success_url, cancel_url, metadata)
        return price_id, customer_id, session

    try:
        price_id, customer_id, session = await asyncio.to_thread(_work)
    except stripe.error.StripeError as e:
        detail = getattr(e, "user_message", None) or str(e)
        raise HTTPException(status_code=502, detail=f"Error de Stripe: {detail}")

    if customer_id != existing_customer:
        await db.companies.update_one(
            {"_id": ObjectId(user["company_id"])},
            {"$set": {"stripe_customer_id": customer_id}},
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.payment_transactions.insert_one({
        "session_id": session.id,
        "mode": "subscription",
        "company_id": ObjectId(user["company_id"]),
        "plan_id": plan_oid,
        "plan_name": plan.get("name", ""),
        "billing_cycle": data.billing_cycle,
        "user_id": ObjectId(user["_id"]),
        "user_email": user.get("email", ""),
        "amount": round(amount_cents / 100.0, 2),
        "currency": currency,
        "stripe_customer_id": customer_id,
        "stripe_price_id": price_id,
        "status": "initiated",
        "payment_status": "pending",
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    return {"checkout_url": session.url, "session_id": session.id}


@router.get("/status/{session_id}")
async def get_status(session_id: str, request: Request):
    """Polling publico (sin auth). Solo devuelve estado, no datos sensibles."""
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaccion no encontrada")

    _init_stripe()
    if tx.get("payment_status") != "paid" and _stripe_configured():
        try:
            session = await asyncio.to_thread(
                lambda: stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
            )
            if session.payment_status == "paid" or session.status == "complete":
                await _apply_paid(session_id, session)
                tx = await db.payment_transactions.find_one({"session_id": session_id})
        except stripe.error.StripeError:
            pass

    return {
        "session_id": tx["session_id"],
        "status": tx.get("status"),
        "payment_status": tx.get("payment_status"),
        "plan_name": tx.get("plan_name"),
        "billing_cycle": tx.get("billing_cycle"),
    }


async def _apply_paid(session_id: str, session=None) -> None:
    """Idempotente: marca la transaccion como pagada y aplica el plan a la empresa."""
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    if not tx or tx.get("payment_status") == "paid":
        return

    sub_id = None
    if session is not None:
        sub = session.get("subscription")
        sub_id = sub if isinstance(sub, str) else (sub or {}).get("id")

    now_iso = datetime.now(timezone.utc).isoformat()
    result = await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {
            "status": "completed",
            "payment_status": "paid",
            "stripe_subscription_id": sub_id,
            "paid_at": now_iso,
            "updated_at": now_iso,
        }},
    )
    if result.modified_count == 0:
        return

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
            "stripe_subscription_id": sub_id,
            "subscription_status": "active",
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


class PortalRequest(BaseModel):
    origin_url: str = Field(..., description="window.location.origin del frontend")


@router.post("/portal")
async def billing_portal(data: PortalRequest, user: dict = Depends(get_current_user)):
    """Abre el Billing Portal de Stripe para que el admin gestione/cancele su suscripcion."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden gestionar la suscripcion")
    _init_stripe()
    if not _stripe_configured():
        raise _not_configured_error()
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])}, {"stripe_customer_id": 1})
    customer_id = (company or {}).get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="Aun no tienes una suscripcion activa que gestionar.")
    origin = data.origin_url.rstrip("/")
    try:
        session = await asyncio.to_thread(
            lambda: stripe.billing_portal.Session.create(customer=customer_id, return_url=f"{origin}/my-plan")
        )
    except stripe.error.StripeError as e:
        detail = getattr(e, "user_message", None) or str(e)
        raise HTTPException(status_code=502, detail=f"Error de Stripe: {detail}")
    return {"url": session.url}


@router.get("/my-transactions")
async def my_transactions(user: dict = Depends(get_current_user), limit: int = 20):
    """Historial de pagos de la empresa del usuario actual."""
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Acceso denegado")
    query = {} if user["role"] == "superadmin" else {"company_id": ObjectId(user["company_id"])}
    txs = await db.payment_transactions.find(query).sort("_id", -1).limit(min(limit, 100)).to_list(limit)
    for t in txs:
        serialize_doc(t)
        for k in ("company_id", "plan_id", "user_id"):
            if isinstance(t.get(k), ObjectId):
                t[k] = str(t[k])
    return [serialize_doc(t) for t in txs]


# ─── Cron: sincronizacion diaria del estado de suscripciones ──────────────────

def _cron_authorized(request: Request) -> bool:
    secret = os.environ.get("WEBHOOK_CRON_SECRET") or ""
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth[:7].lower() == "bearer " else ""
    return bool(secret and token and hmac.compare_digest(token, secret))


async def _sync_subscriptions_job() -> None:
    """Recorre las empresas con suscripcion en Stripe y sincroniza su estado:
    activa/trial -> mantiene el plan; cancelada/impaga -> baja a Free."""
    _init_stripe()
    if not _stripe_configured():
        return
    free_plan = await db.plans.find_one({"name": "Free"}, {"_id": 1})
    free_id = free_plan["_id"] if free_plan else None

    cursor = db.companies.find(
        {"stripe_subscription_id": {"$exists": True, "$ne": None}},
        {"stripe_subscription_id": 1, "plan_id": 1, "name": 1},
    )
    async for c in cursor:
        sub_id = c.get("stripe_subscription_id")
        try:
            sub = await asyncio.to_thread(lambda sid=sub_id: stripe.Subscription.retrieve(sid))
        except stripe.error.StripeError:
            continue
        status = sub.get("status")
        now_iso = datetime.now(timezone.utc).isoformat()
        update = {"subscription_status": status, "updated_at": now_iso}

        if status in ("active", "trialing"):
            cps = sub.get("current_period_start")
            if cps:
                update["last_payment_at"] = datetime.fromtimestamp(cps, timezone.utc).isoformat()
        elif status in ("canceled", "unpaid", "incomplete_expired"):
            if free_id and c.get("plan_id") != free_id:
                update["plan_id"] = free_id
                await db.plan_history.insert_one({
                    "company_id": c["_id"],
                    "company_name": c.get("name", ""),
                    "old_plan_id": c.get("plan_id"),
                    "new_plan_id": free_id,
                    "new_plan_name": "Free",
                    "changed_by_name": "Sistema (impago/cancelacion)",
                    "reason": f"subscription_{status}",
                    "changed_at": now_iso,
                })
        # past_due / incomplete: se mantiene el plan (periodo de gracia), solo se marca el estado
        await db.companies.update_one({"_id": c["_id"]}, {"$set": update})


@cron_router.post("/sync-subscriptions")
async def cron_sync_subscriptions(request: Request):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _cron_authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    asyncio.create_task(_sync_subscriptions_job())
    return {"ok": True}
