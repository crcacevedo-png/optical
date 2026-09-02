"""
Panel de Retencion para SuperAdmin.
- GET /api/superadmin/retention: KPIs y listas segmentadas por estado de activacion.
- POST /api/companies/{id}/reactivate: reactiva + genera password reset link + envia email.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from bson import ObjectId
from datetime import datetime, timezone, timedelta
import os
import secrets

from db import db
from auth_utils import get_current_user, get_real_ip
from email_service import queue_email, render_reactivation_notice
from audit import log_audit

router = APIRouter(tags=["Retencion"])


def _days_since(iso_str, now):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int((now - dt).total_seconds() // 86400)
    except Exception:
        return None


AT_RISK_DAYS = int(os.environ.get("RETENTION_AT_RISK_DAYS", "15"))


@router.get("/superadmin/retention")
async def retention_dashboard(user: dict = Depends(get_current_user)):
    """Retorna KPIs y listas de opticas segmentadas por estado de actividad."""
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    now = datetime.now(timezone.utc)

    # Traer todas las companies (con is_active incluido)
    companies = await db.companies.find({}).to_list(10000)
    cids = [c["_id"] for c in companies]
    if not cids:
        return {
            "kpis": {"total": 0, "active": 0, "inactive": 0, "never_activated": 0,
                     "at_risk": 0, "expired": 0, "recently_activated": 0, "activation_rate": 0.0},
            "segments": {"never_activated": [], "at_risk": [], "expired": [], "recently_activated": []},
        }

    # Batch fetch admin por company
    admin_activity = {}
    admin_pipeline = [
        {"$match": {"company_id": {"$in": cids}, "role": "admin"}},
        {"$sort": {"created_at": 1}},
        {"$group": {
            "_id": "$company_id",
            "admin_email": {"$first": "$email"},
            "admin_name": {"$first": "$name"},
            "admin_id": {"$first": "$_id"},
            "first_login_at": {"$min": "$first_login_at"},
            "last_login_at": {"$max": "$last_login_at"},
        }}
    ]
    async for row in db.users.aggregate(admin_pipeline):
        admin_activity[str(row["_id"])] = row

    # Batch counts de patients
    patients_pipeline = [
        {"$match": {"company_id": {"$in": cids}, "is_deleted": {"$ne": True}}},
        {"$group": {"_id": "$company_id", "count": {"$sum": 1}}},
    ]
    patients_counts = {}
    async for row in db.patients.aggregate(patients_pipeline):
        patients_counts[str(row["_id"])] = row["count"]

    # Batch plans
    plan_ids = list({c.get("plan_id") for c in companies if c.get("plan_id")})
    plan_map = {}
    if plan_ids:
        for p in await db.plans.find({"_id": {"$in": plan_ids}}).to_list(len(plan_ids)):
            plan_map[str(p["_id"])] = p.get("name", "-")

    # Clasificar
    total = len(companies)
    active = sum(1 for c in companies if c.get("is_active", True))
    inactive = total - active

    never_activated = []
    at_risk = []
    expired = []
    recently_activated = []

    for c in companies:
        cid_str = str(c["_id"])
        act = admin_activity.get(cid_str, {})
        item = {
            "_id": cid_str,
            "name": c.get("name"),
            "email": c.get("email"),
            "created_at": c.get("created_at"),
            "is_active": c.get("is_active", True),
            "deactivated_reason": c.get("deactivated_reason"),
            "admin_id": str(act.get("admin_id")) if act.get("admin_id") else None,
            "admin_email": act.get("admin_email"),
            "admin_name": act.get("admin_name"),
            "admin_first_login_at": act.get("first_login_at"),
            "admin_last_login_at": act.get("last_login_at"),
            "days_since_created": _days_since(c.get("created_at"), now),
            "days_since_last_login": _days_since(act.get("last_login_at"), now),
            "plan_name": plan_map.get(str(c.get("plan_id")), "Sin plan"),
            "patients_count": patients_counts.get(cid_str, 0),
        }

        activated = bool(act.get("first_login_at"))

        # Expiradas: desactivadas por activation_expired
        if c.get("deactivated_reason") == "activation_expired":
            expired.append(item)
            continue

        if not activated:
            # Sin activar: aun activas y nunca ingresaron
            if c.get("is_active", True):
                never_activated.append(item)
            continue

        days_last = item["days_since_last_login"]
        days_first = _days_since(act.get("first_login_at"), now)

        # Recien activadas: primer login en los ultimos 7 dias
        if days_first is not None and days_first <= 7:
            recently_activated.append(item)

        # En riesgo: activas + activadas pero sin login > AT_RISK_DAYS
        if c.get("is_active", True) and days_last is not None and days_last > AT_RISK_DAYS:
            at_risk.append(item)

    # Ordenar
    never_activated.sort(key=lambda x: x["days_since_created"] or 0, reverse=True)
    at_risk.sort(key=lambda x: x["days_since_last_login"] or 0, reverse=True)
    expired.sort(key=lambda x: x["days_since_created"] or 0, reverse=True)
    recently_activated.sort(key=lambda x: _days_since(x["admin_first_login_at"], now) or 0)

    activation_rate = round((sum(1 for c in companies if admin_activity.get(str(c["_id"]), {}).get("first_login_at")) / total * 100), 1) if total > 0 else 0.0

    return {
        "kpis": {
            "total": total,
            "active": active,
            "inactive": inactive,
            "never_activated": len(never_activated),
            "at_risk": len(at_risk),
            "expired": len(expired),
            "recently_activated": len(recently_activated),
            "activation_rate": activation_rate,
        },
        "thresholds": {
            "at_risk_days": AT_RISK_DAYS,
            "deadline_days": int(os.environ.get("ACTIVATION_DEADLINE_DAYS", "30")),
        },
        "segments": {
            "never_activated": never_activated,
            "at_risk": at_risk,
            "expired": expired,
            "recently_activated": recently_activated,
        },
    }


@router.post("/companies/{company_id}/reactivate")
async def reactivate_company(company_id: str, request: Request, user: dict = Depends(get_current_user)):
    """SuperAdmin reactiva una optica desactivada + genera password reset + envia email al admin."""
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    try:
        cid = ObjectId(company_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de company invalido")

    company = await db.companies.find_one({"_id": cid})
    if not company:
        raise HTTPException(status_code=404, detail="Optica no encontrada")

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Reactivar company y admins
    await db.companies.update_one(
        {"_id": cid},
        {
            "$set": {
                "is_active": True,
                "reactivated_at": now_iso,
                "reactivated_by": user["_id"],
                "needs_reactivation_feedback": True,
            },
            "$unset": {"deactivated_reason": "", "deactivated_at": ""},
        }
    )
    await db.users.update_many(
        {"company_id": cid, "role": "admin"},
        {"$set": {"is_active": True}, "$unset": {"deactivated_by_activation_expiry_at": ""}}
    )

    # Encontrar admin principal para reset link
    admin = await db.users.find_one({"company_id": cid, "role": "admin"}, sort=[("created_at", 1)])
    if not admin:
        raise HTTPException(status_code=500, detail="La optica no tiene admin configurado")

    # Generar token de reset (misma logica de auth.py::forgot_password pero TTL 24h)
    token = secrets.token_urlsafe(48)
    expires_at = now + timedelta(hours=24)
    await db.password_resets.insert_one({
        "user_id": admin["_id"],
        "email": admin["email"],
        "token": token,
        "expires_at": expires_at,
        "used": False,
        "created_at": now,
        "ip": get_real_ip(request),
        "source": "reactivation",
    })

    app_url = os.environ.get("APP_URL", "https://cortexiaoptical.com")
    reset_link = f"{app_url.rstrip('/')}/reset-password?token={token}"

    # Enviar email
    html = render_reactivation_notice(
        admin_name=admin.get("name", "Administrador"),
        company_name=company.get("name", "tu optica"),
        reset_link=reset_link,
    )
    await queue_email(
        admin["email"],
        f"[Cortexia] Tu optica {company.get('name', 'ha sido reactivada')} fue reactivada",
        html,
        tag="reactivation",
    )

    # Reset markers de activation task para que no vuelvan a disparar reminders
    await db.users.update_one(
        {"_id": admin["_id"]},
        {"$unset": {
            "reminder_7d_sent_at": "",
            "reminder_2d_sent_at": "",
            "welcome_tips_sent_at": "",
        }}
    )

    # Audit + notification
    await log_audit(
        "COMPANY_REACTIVATED",
        actor_id=str(user["_id"]),
        actor_email=user.get("email"),
        actor_role="superadmin",
        company_id=company_id,
        metadata={"company_name": company.get("name"), "admin_email": admin["email"]},
        request=request,
    )

    return {
        "ok": True,
        "message": "Optica reactivada y email enviado al admin",
        "company_id": company_id,
        "admin_email": admin["email"],
    }
