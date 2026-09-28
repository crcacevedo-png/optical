"""Motor de cobros y suspension por impago (Dunning) — Cortexia Optical.

Transforma el estado de la suscripcion en Stripe en un estado INTERNO de facturacion
(`billing_state`: active | grace | suspended) con periodo de gracia, recordatorios
escalonados, suspension (muro de pago) y reactivacion automatica.

Se ejecuta a diario desde el cron `POST /api/cron/sync-subscriptions` (billing.py) y
tambien se puede invocar en vivo (account-status) para reactivar sin esperar al cron.

Reglas (Fase 1 MVP):
- Cortesia (is_courtesy) = SIEMPRE exenta (nunca gracia ni suspension).
- Pago fallido en Stripe (past_due/unpaid/incomplete) -> arranca gracia de BILLING_GRACE_DAYS
  dias desde la deteccion. Durante la gracia la optica opera normal + avisos.
- Al vencer la gracia sin pago -> SUSPENDIDA (muro de pago para el admin; resto ve aviso).
- Cancelacion (canceled/incomplete_expired) -> SUSPENDIDA (no baja a Free).
- Pago regularizado (active/trialing) -> REACTIVACION automatica + recupera acceso.
- Verificacion de monto: compara el cargo activo de Stripe vs el precio del plan; si difiere
  marca la cuenta y avisa al superadmin, pero NO suspende por esta causa.
"""
import os
import math
import logging
import asyncio
from datetime import datetime, timezone, timedelta

import stripe
from bson import ObjectId

from db import db, effective_monthly_cost
from email_service import (
    queue_email, render_payment_failed, render_grace_reminder,
    render_suspension_notice, render_payment_restored,
)
from routes.notifications import create_notification

logger = logging.getLogger(__name__)

GRACE_DAYS = int(os.environ.get("BILLING_GRACE_DAYS", "3"))

# Estados de Stripe agrupados
_STATUS_OK = ("active", "trialing")
_STATUS_PROBLEM = ("past_due", "unpaid", "incomplete")
_STATUS_DEAD = ("canceled", "incomplete_expired")


def _parse_iso(iso_str):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _app_url() -> str:
    return os.environ.get("APP_URL", "https://cortexiaoptical.com").strip().rstrip("/")


# ─────────────────────────── VISTA / SNAPSHOT ───────────────────────────

def build_billing_snapshot(company: dict) -> dict:
    """Snapshot de facturacion derivado del doc de la empresa (SIN llamar a Stripe).
    Lo consumen /auth/login y /auth/me para que el frontend pinte banners/muro."""
    if company.get("is_courtesy"):
        return {"state": "active", "is_exempt": True, "days_remaining": None}
    state = company.get("billing_state") or "active"
    grace_until = company.get("grace_until")
    days_remaining = None
    if state == "grace" and grace_until:
        gu = _parse_iso(grace_until)
        if gu:
            days_remaining = max(math.ceil((gu - datetime.now(timezone.utc)).total_seconds() / 86400), 0)
    return {
        "state": state,
        "grace_until": grace_until if state == "grace" else None,
        "days_remaining": days_remaining,
        "suspended_at": company.get("suspended_at") if state == "suspended" else None,
        "suspended_reason": company.get("suspended_reason") if state == "suspended" else None,
        "subscription_status": company.get("subscription_status"),
        "has_subscription": bool(company.get("stripe_customer_id")),
        "amount_mismatch": bool(company.get("amount_mismatch")),
        "is_exempt": False,
    }


# ─────────────────────────── NOTIFICACIONES ───────────────────────────

async def _get_company_admin(company: dict) -> dict | None:
    try:
        return await db.users.find_one(
            {"company_id": company["_id"], "role": "admin", "is_active": True},
            {"email": 1, "name": 1},
        )
    except Exception:
        return None


async def _notify_superadmins(*, subject: str, html: str, tag: str,
                              event_type: str, title: str, message: str, metadata: dict):
    """Alerta al superadmin: notificacion in-app + correo a todos los superadmins activos."""
    try:
        await create_notification(event_type, title, message, metadata)
    except Exception as e:
        logger.warning(f"[dunning] no se pudo crear notificacion in-app: {e}")
    try:
        emails = set()
        async for u in db.users.find({"role": "superadmin", "is_active": True}, {"email": 1}):
            if u.get("email"):
                emails.add(u["email"])
        for fb in (os.environ.get("CORTEXIA_ALERTS_TO"), os.environ.get("ADMIN_EMAIL")):
            if fb:
                emails.add(fb.strip())
        for e in emails:
            await queue_email(e, subject, html, tag=tag)
    except Exception as e:
        logger.warning(f"[dunning] no se pudo encolar correo a superadmins: {e}")


def _superadmin_alert_html(title: str, lines: list[str]) -> str:
    """HTML simple para el correo de alerta al superadmin (reusa el wrapper via template inline)."""
    from email_service import _wrapper, BRAND_DARK
    body = "".join(
        f'<p style="color:#334155;font-size:14px;line-height:1.6;margin:0 0 10px 0;">{l}</p>'
        for l in lines
    )
    body += f'<p style="margin-top:16px;"><a href="{_app_url()}/admin/cobros" style="color:{BRAND_DARK};font-weight:bold;">Abrir el panel de Cobros &rarr;</a></p>'
    return _wrapper(body, title)


async def _notify_payment_failed(company: dict, plan_name: str, amount_str: str, grace_until: datetime):
    admin = await _get_company_admin(company)
    pay_link = f"{_app_url()}/my-plan"
    grace_str = grace_until.strftime("%d/%m/%Y")
    if admin and admin.get("email"):
        html = render_payment_failed(
            admin_name=admin.get("name", "Administrador"),
            company_name=company.get("name", "tu optica"),
            plan_name=plan_name, amount_str=amount_str,
            grace_days=GRACE_DAYS, grace_until_str=grace_str, pay_link=pay_link,
        )
        await queue_email(admin["email"], "[Cortexia] Tu pago no se pudo procesar", html, tag="payment_failed")
    await _notify_superadmins(
        subject=f"[Cortexia] Pago fallido: {company.get('name', 'Optica')}",
        html=_superadmin_alert_html(
            "Pago fallido de una optica",
            [f"La optica <strong>{company.get('name', 'Optica')}</strong> tuvo un pago fallido en Stripe.",
             f"Plan: {plan_name} · Monto: {amount_str}.",
             f"Entra en periodo de gracia hasta el {grace_str} ({GRACE_DAYS} dias). Si no paga, se suspende."],
        ),
        tag="admin_payment_failed",
        event_type="payment_failed",
        title="Pago fallido de una optica",
        message=f"{company.get('name', 'Optica')} tuvo un pago fallido. Gracia hasta {grace_str}.",
        metadata={"company_id": str(company["_id"]), "company_name": company.get("name"), "grace_until": grace_until.isoformat()},
    )


async def _notify_grace_reminder(company: dict, days_remaining: int, grace_until: datetime):
    admin = await _get_company_admin(company)
    if admin and admin.get("email"):
        html = render_grace_reminder(
            admin_name=admin.get("name", "Administrador"),
            company_name=company.get("name", "tu optica"),
            days_remaining=days_remaining,
            grace_until_str=grace_until.strftime("%d/%m/%Y"),
            pay_link=f"{_app_url()}/my-plan",
        )
        await queue_email(admin["email"], f"[Cortexia] Recordatorio: regulariza tu pago ({days_remaining} dia(s))", html, tag="grace_reminder")


async def _notify_suspended(company: dict, reason: str):
    admin = await _get_company_admin(company)
    reason_txt = "cancelacion de la suscripcion" if reason == "subscription_canceled" else "falta de pago"
    if admin and admin.get("email"):
        html = render_suspension_notice(
            admin_name=admin.get("name", "Administrador"),
            company_name=company.get("name", "tu optica"),
            pay_link=f"{_app_url()}/my-plan", reason=reason_txt,
        )
        await queue_email(admin["email"], "[Cortexia] Tu cuenta fue suspendida", html, tag="suspension_notice")
    await _notify_superadmins(
        subject=f"[Cortexia] Optica SUSPENDIDA: {company.get('name', 'Optica')}",
        html=_superadmin_alert_html(
            "Optica suspendida por impago",
            [f"La optica <strong>{company.get('name', 'Optica')}</strong> fue <strong>suspendida</strong> ({reason_txt}).",
             "El admin solo puede ver el muro de pago hasta regularizar."],
        ),
        tag="admin_suspension",
        event_type="company_suspended",
        title="Optica suspendida por impago",
        message=f"{company.get('name', 'Optica')} fue suspendida ({reason_txt}).",
        metadata={"company_id": str(company["_id"]), "company_name": company.get("name"), "reason": reason},
    )


async def _notify_reactivated(company: dict):
    admin = await _get_company_admin(company)
    plan_name = ""
    if company.get("plan_id"):
        plan = await db.plans.find_one({"_id": company["plan_id"]}, {"name": 1})
        plan_name = (plan or {}).get("name", "")
    if admin and admin.get("email"):
        html = render_payment_restored(
            admin_name=admin.get("name", "Administrador"),
            company_name=company.get("name", "tu optica"),
            plan_name=plan_name,
        )
        await queue_email(admin["email"], "[Cortexia] Tu cuenta fue reactivada", html, tag="payment_restored")
    await _notify_superadmins(
        subject=f"[Cortexia] Optica reactivada: {company.get('name', 'Optica')}",
        html=_superadmin_alert_html(
            "Optica reactivada (pago regularizado)",
            [f"La optica <strong>{company.get('name', 'Optica')}</strong> regularizo su pago y recupero el acceso completo."],
        ),
        tag="admin_reactivation",
        event_type="company_reactivated",
        title="Optica reactivada",
        message=f"{company.get('name', 'Optica')} regularizo su pago y fue reactivada.",
        metadata={"company_id": str(company["_id"]), "company_name": company.get("name")},
    )


async def _notify_amount_mismatch(company: dict, detail: dict):
    exp = detail.get("expected_cents")
    act = detail.get("actual_cents")
    exp_s = f"{(exp or 0) / 100:.2f} {detail.get('expected_currency', '').upper()}"
    act_s = f"{(act or 0) / 100:.2f} {detail.get('actual_currency', '').upper()}"
    await _notify_superadmins(
        subject=f"[Cortexia] Discrepancia de monto: {company.get('name', 'Optica')}",
        html=_superadmin_alert_html(
            "Discrepancia de monto de suscripcion",
            [f"La optica <strong>{company.get('name', 'Optica')}</strong> tiene un cargo en Stripe que NO coincide con el precio de su plan.",
             f"Esperado (plan): {exp_s} · Cobrado en Stripe: {act_s} · Ciclo: {detail.get('cycle')}.",
             "No se suspende por esta causa; revisa el precio del plan o la suscripcion en Stripe."],
        ),
        tag="admin_amount_mismatch",
        event_type="amount_mismatch",
        title="Discrepancia de monto de suscripcion",
        message=f"{company.get('name', 'Optica')}: plan {exp_s} vs Stripe {act_s}.",
        metadata={"company_id": str(company["_id"]), "company_name": company.get("name"), "detail": detail},
    )


# ─────────────────────────── VERIFICACION DE MONTO ───────────────────────────

async def _check_amount(company: dict, sub, base_update: dict):
    if not company.get("plan_id"):
        return
    plan = await db.plans.find_one({"_id": company["plan_id"]})
    if not plan:
        return
    try:
        from routes.billing import _plan_amount_cents
        cycle = company.get("billing_cycle") or "monthly"
        expected_cents, _interval = _plan_amount_cents(plan, cycle)
    except Exception:
        return
    items = (sub.get("items") or {}).get("data") or []
    if not items:
        return
    price = items[0].get("price") or {}
    actual_cents = price.get("unit_amount")
    actual_currency = (price.get("currency") or "").lower()
    expected_currency = (plan.get("currency") or "usd").lower()
    mismatch = (actual_cents is not None and int(actual_cents) != int(expected_cents)) or \
               (actual_currency and actual_currency != expected_currency)
    if mismatch:
        detail = {
            "expected_cents": int(expected_cents), "actual_cents": int(actual_cents or 0),
            "expected_currency": expected_currency, "actual_currency": actual_currency,
            "cycle": company.get("billing_cycle") or "monthly",
        }
        base_update["amount_mismatch"] = True
        base_update["amount_mismatch_detail"] = detail
        if not company.get("amount_mismatch"):
            await _notify_amount_mismatch(company, detail)
    elif company.get("amount_mismatch"):
        base_update["amount_mismatch"] = False
        base_update["amount_mismatch_detail"] = None


# ─────────────────────────── MOTOR DE ESTADO ───────────────────────────

async def _reactivate(company: dict, base_update: dict):
    base_update.update({
        "billing_state": "active",
        "payment_failed_at": None, "grace_until": None,
        "suspended_at": None, "suspended_reason": None, "last_dunning_stage": None,
    })
    await db.companies.update_one({"_id": company["_id"]}, {"$set": base_update})
    await _notify_reactivated(company)


async def _handle_ok(company: dict, sub, base_update: dict):
    cps = sub.get("current_period_start")
    if cps:
        base_update["last_payment_at"] = datetime.fromtimestamp(cps, timezone.utc).isoformat()
    if company.get("billing_state") in ("grace", "suspended"):
        await _reactivate(company, base_update)
    else:
        base_update["billing_state"] = "active"
        await db.companies.update_one({"_id": company["_id"]}, {"$set": base_update})


async def _handle_problem(company: dict, base_update: dict, now: datetime, plan_name: str, amount_str: str):
    state = company.get("billing_state")
    if state not in ("grace", "suspended"):
        grace_until = now + timedelta(days=GRACE_DAYS)
        base_update.update({
            "billing_state": "grace",
            "payment_failed_at": now.isoformat(),
            "grace_until": grace_until.isoformat(),
            "last_dunning_stage": 0,
            "suspended_at": None,
        })
        await db.companies.update_one({"_id": company["_id"]}, {"$set": base_update})
        await _notify_payment_failed(company, plan_name, amount_str, grace_until)
    elif state == "grace":
        grace_until = _parse_iso(company.get("grace_until")) or (now + timedelta(days=GRACE_DAYS))
        if now >= grace_until:
            base_update.update({
                "billing_state": "suspended", "suspended_at": now.isoformat(),
                "suspended_reason": "payment_failed", "last_dunning_stage": 3,
            })
            await db.companies.update_one({"_id": company["_id"]}, {"$set": base_update})
            await _notify_suspended(company, reason="payment_failed")
        else:
            failed_at = _parse_iso(company.get("payment_failed_at")) or now
            day = (now - failed_at).days  # 1 .. GRACE_DAYS-1
            last_stage = int(company.get("last_dunning_stage") or 0)
            if 1 <= day <= (GRACE_DAYS - 1) and day > last_stage:
                base_update["last_dunning_stage"] = day
                await db.companies.update_one({"_id": company["_id"]}, {"$set": base_update})
                days_remaining = max(math.ceil((grace_until - now).total_seconds() / 86400), 0)
                await _notify_grace_reminder(company, days_remaining, grace_until)
            else:
                await db.companies.update_one({"_id": company["_id"]}, {"$set": base_update})
    else:  # suspended -> se mantiene
        await db.companies.update_one({"_id": company["_id"]}, {"$set": base_update})


async def _handle_dead(company: dict, base_update: dict, now: datetime):
    if company.get("billing_state") != "suspended":
        base_update.update({
            "billing_state": "suspended", "suspended_at": now.isoformat(),
            "suspended_reason": "subscription_canceled",
        })
        await db.companies.update_one({"_id": company["_id"]}, {"$set": base_update})
        await _notify_suspended(company, reason="subscription_canceled")
    else:
        await db.companies.update_one({"_id": company["_id"]}, {"$set": base_update})


async def process_company(company: dict, now: datetime | None = None) -> str:
    """Procesa UNA empresa contra Stripe y aplica el estado de facturacion.
    Devuelve el nuevo billing_state (string) para logging/tests."""
    now = now or datetime.now(timezone.utc)
    sub_id = company.get("stripe_subscription_id")
    if not sub_id:
        return company.get("billing_state") or "active"

    # Cortesia: exenta. Si venia de gracia/suspension, se reactiva silenciosamente.
    if company.get("is_courtesy"):
        if company.get("billing_state") in ("grace", "suspended"):
            await db.companies.update_one(
                {"_id": company["_id"]},
                {"$set": {"billing_state": "active", "payment_failed_at": None,
                          "grace_until": None, "suspended_at": None,
                          "suspended_reason": None, "last_dunning_stage": None,
                          "updated_at": now.isoformat()}},
            )
        return "active"

    try:
        sub = await asyncio.to_thread(
            lambda: stripe.Subscription.retrieve(sub_id, expand=["items.data.price"])
        )
    except stripe.error.StripeError as e:
        logger.warning(f"[dunning] no se pudo leer sub {sub_id} de {company.get('name')}: {e}")
        return company.get("billing_state") or "active"

    status = sub.get("status")
    base_update = {"subscription_status": status, "updated_at": now.isoformat()}
    pe = sub.get("current_period_end")
    if pe:
        base_update["current_period_end"] = datetime.fromtimestamp(pe, timezone.utc).isoformat()

    # Verificacion de monto (best-effort, no suspende)
    try:
        await _check_amount(company, sub, base_update)
    except Exception as e:
        logger.warning(f"[dunning] check_amount fallo para {company.get('name')}: {e}")

    # Nombre del plan + monto para los correos
    plan_name, amount_str = "tu plan", ""
    try:
        if company.get("plan_id"):
            plan = await db.plans.find_one({"_id": company["plan_id"]}, {"name": 1, "currency": 1, "price_monthly": 1, "price_yearly": 1, "price": 1})
            if plan:
                plan_name = plan.get("name", "tu plan")
                from routes.billing import _plan_amount_cents
                cents, _iv = _plan_amount_cents(plan, company.get("billing_cycle") or "monthly")
                sym = "$" if (plan.get("currency") or "USD").upper() == "USD" else (plan.get("currency") or "").upper()
                amount_str = f"{sym} {cents / 100:.2f}"
    except Exception:
        pass

    if status in _STATUS_OK:
        await _handle_ok(company, sub, base_update)
    elif status in _STATUS_PROBLEM:
        await _handle_problem(company, base_update, now, plan_name, amount_str)
    elif status in _STATUS_DEAD:
        await _handle_dead(company, base_update, now)
    else:
        await db.companies.update_one({"_id": company["_id"]}, {"$set": base_update})

    fresh = await db.companies.find_one({"_id": company["_id"]}, {"billing_state": 1})
    return (fresh or {}).get("billing_state") or "active"


async def run_dunning_cycle() -> dict:
    """Recorre todas las empresas con suscripcion en Stripe y aplica el motor de cobros.
    Se llama desde el cron diario. Devuelve un resumen de conteos."""
    counts = {"processed": 0, "active": 0, "grace": 0, "suspended": 0, "errors": 0}
    cursor = db.companies.find({"stripe_subscription_id": {"$exists": True, "$ne": None}})
    async for c in cursor:
        counts["processed"] += 1
        try:
            state = await process_company(c)
            counts[state] = counts.get(state, 0) + 1
        except Exception as e:
            counts["errors"] += 1
            logger.error(f"[dunning] error procesando {c.get('name')}: {e}")
    logger.info(f"[dunning] ciclo completado: {counts}")
    return counts


# ─────────────────────────── PANEL DE COBROS (SUPERADMIN) ───────────────────────────

async def build_collections_panel(days_ahead: int = 7) -> dict:
    """Datos para el panel de Cobros del superadmin."""
    now = datetime.now(timezone.utc)
    plans = {str(p["_id"]): p for p in await db.plans.find({}).to_list(500)}

    def _money(company):
        plan = plans.get(str(company.get("plan_id"))) if company.get("plan_id") else None
        cost = effective_monthly_cost(company, plan)
        cur = (plan.get("currency") if plan else "USD") or "USD"
        return cost, cur.upper()

    def _row(company, extra=None):
        plan = plans.get(str(company.get("plan_id"))) if company.get("plan_id") else None
        cost, cur = _money(company)
        row = {
            "company_id": str(company["_id"]),
            "company_name": company.get("name", "Optica"),
            "plan_name": (plan or {}).get("name", "Sin plan"),
            "billing_cycle": company.get("billing_cycle") or "monthly",
            "monthly_cost": round(cost, 2),
            "currency": cur,
            "subscription_status": company.get("subscription_status"),
            "billing_state": company.get("billing_state") or "active",
        }
        if extra:
            row.update(extra)
        return row

    grace, suspended, mismatches, upcoming = [], [], [], []
    mrr_at_risk = 0.0

    async for c in db.companies.find({"billing_state": "grace"}):
        gu = _parse_iso(c.get("grace_until"))
        days_left = max(math.ceil((gu - now).total_seconds() / 86400), 0) if gu else None
        grace.append(_row(c, {"grace_until": c.get("grace_until"), "days_remaining": days_left,
                              "payment_failed_at": c.get("payment_failed_at")}))
        cost, _ = _money(c)
        mrr_at_risk += cost

    async for c in db.companies.find({"billing_state": "suspended"}):
        suspended.append(_row(c, {"suspended_at": c.get("suspended_at"),
                                  "suspended_reason": c.get("suspended_reason")}))
        cost, _ = _money(c)
        mrr_at_risk += cost

    async for c in db.companies.find({"amount_mismatch": True}):
        mismatches.append(_row(c, {"amount_mismatch_detail": c.get("amount_mismatch_detail")}))

    horizon = (now + timedelta(days=days_ahead)).isoformat()
    async for c in db.companies.find({
        "billing_state": {"$in": ["active", None]},
        "is_courtesy": {"$ne": True},
        "current_period_end": {"$exists": True, "$ne": None, "$lte": horizon, "$gte": now.isoformat()},
    }):
        pe = _parse_iso(c.get("current_period_end"))
        days_to = max(math.ceil((pe - now).total_seconds() / 86400), 0) if pe else None
        upcoming.append(_row(c, {"current_period_end": c.get("current_period_end"), "days_to_renewal": days_to}))

    grace.sort(key=lambda r: (r.get("days_remaining") if r.get("days_remaining") is not None else 999))
    upcoming.sort(key=lambda r: (r.get("days_to_renewal") if r.get("days_to_renewal") is not None else 999))

    return {
        "generated_at": now.isoformat(),
        "grace_days": GRACE_DAYS,
        "kpis": {
            "upcoming_renewals": len(upcoming),
            "in_grace": len(grace),
            "suspended": len(suspended),
            "amount_mismatches": len(mismatches),
            "mrr_at_risk": round(mrr_at_risk, 2),
        },
        "upcoming": upcoming,
        "grace": grace,
        "suspended": suspended,
        "mismatches": mismatches,
    }
