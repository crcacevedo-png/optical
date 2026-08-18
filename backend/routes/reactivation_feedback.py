"""
Feedback rapido del admin cuando se reactiva una optica.
- Se muestra automaticamente en el primer login post-reactivacion.
- El campo companies.needs_reactivation_feedback se setea cuando el
  superadmin reactiva la optica (routes/superadmin_retention.py).
- Al enviar o descartar el feedback, el flag se limpia y el dialog
  no vuelve a aparecer.
"""
from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Optional

from db import db
from auth_utils import get_current_user
from routes.notifications import create_notification
from audit import log_audit

router = APIRouter(prefix="/reactivation-feedback", tags=["Retencion"])


VALID_REASONS = {
    "sin_tiempo": "Falta de tiempo",
    "no_supe_empezar": "No supe por donde empezar",
    "olvide_password": "Olvide mi contrasena",
    "precio": "Precio",
    "no_lo_necesitaba": "No lo necesitaba en ese momento",
    "otro": "Otro",
}


class FeedbackSubmit(BaseModel):
    reason: str = Field(..., description="Codigo de motivo (sin_tiempo|no_supe_empezar|olvide_password|precio|no_lo_necesitaba|otro)")
    comment: Optional[str] = Field(None, max_length=1000)
    allow_contact: bool = False


def _requires_admin_of_reactivated_company(user: dict):
    """Verifica que el usuario sea admin y su company este marcada con needs_reactivation_feedback."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo los admins pueden enviar este feedback")
    if not user.get("company_id"):
        raise HTTPException(status_code=400, detail="Usuario sin optica asignada")


@router.post("")
async def submit_feedback(data: FeedbackSubmit, user: dict = Depends(get_current_user)):
    """Guarda feedback del admin post-reactivacion y notifica al SuperAdmin."""
    _requires_admin_of_reactivated_company(user)
    if data.reason not in VALID_REASONS:
        raise HTTPException(status_code=400, detail=f"Motivo invalido. Opciones: {list(VALID_REASONS.keys())}")

    cid = ObjectId(user["company_id"])
    company = await db.companies.find_one({"_id": cid}, {"name": 1, "needs_reactivation_feedback": 1})
    if not company:
        raise HTTPException(status_code=404, detail="Optica no encontrada")

    # H3 hardening (Feb 2026): precondition idempotente para prevenir feedback
    # repetido y spam al SuperAdmin cuando el usuario recarga o el flag ya se limpio.
    if not company.get("needs_reactivation_feedback"):
        raise HTTPException(status_code=400, detail="No hay feedback pendiente para esta optica")

    now = datetime.now(timezone.utc)
    doc = {
        "company_id": cid,
        "company_name": company.get("name"),
        "admin_id": ObjectId(user["_id"]),
        "admin_name": user.get("name"),
        "admin_email": user.get("email"),
        "reason": data.reason,
        "reason_label": VALID_REASONS[data.reason],
        "comment": (data.comment or "").strip() or None,
        "allow_contact": bool(data.allow_contact),
        "submitted_at": now.isoformat(),
    }
    await db.reactivation_feedbacks.insert_one(doc)

    # Limpia el flag para que el dialog no vuelva a aparecer
    await db.companies.update_one(
        {"_id": cid},
        {"$unset": {"needs_reactivation_feedback": ""}}
    )

    # Notifica al SuperAdmin
    try:
        await create_notification(
            event_type="reactivation_feedback",
            title=f"Feedback de reactivacion: {company.get('name')}",
            message=f"{user.get('name')} indico '{VALID_REASONS[data.reason]}'."
                    + (f" Contacto autorizado." if data.allow_contact else ""),
            metadata={
                "company_id": str(cid),
                "company_name": company.get("name"),
                "reason": data.reason,
                "allow_contact": data.allow_contact,
                "has_comment": bool(doc["comment"]),
            }
        )
    except Exception:
        pass

    try:
        await log_audit(
            "REACTIVATION_FEEDBACK_SUBMITTED",
            actor_id=user["_id"], actor_email=user.get("email"), actor_role="admin",
            company_id=str(cid),
            metadata={"reason": data.reason, "allow_contact": data.allow_contact},
        )
    except Exception:
        pass

    return {"ok": True, "message": "Gracias por tu feedback"}


@router.post("/skip")
async def skip_feedback(user: dict = Depends(get_current_user)):
    """El admin descarta el dialog sin enviar feedback. Limpia el flag."""
    _requires_admin_of_reactivated_company(user)
    cid = ObjectId(user["company_id"])
    await db.companies.update_one(
        {"_id": cid},
        {"$unset": {"needs_reactivation_feedback": ""}}
    )
    try:
        await log_audit(
            "REACTIVATION_FEEDBACK_SKIPPED",
            actor_id=user["_id"], actor_email=user.get("email"), actor_role="admin",
            company_id=str(cid),
        )
    except Exception:
        pass
    return {"ok": True, "message": "OK"}


@router.get("/list")
async def list_feedbacks(user: dict = Depends(get_current_user), limit: int = 100):
    """SuperAdmin lista todos los feedbacks recibidos (mas recientes primero)."""
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    limit = max(1, min(500, limit))
    docs = await db.reactivation_feedbacks.find({}).sort("submitted_at", -1).limit(limit).to_list(limit)
    for d in docs:
        d["_id"] = str(d["_id"])
        d["company_id"] = str(d["company_id"]) if d.get("company_id") else None
        d["admin_id"] = str(d["admin_id"]) if d.get("admin_id") else None

    # Aggregate breakdown por reason
    breakdown = {}
    async for row in db.reactivation_feedbacks.aggregate([
        {"$group": {"_id": "$reason", "count": {"$sum": 1}}}
    ]):
        breakdown[row["_id"] or "sin_motivo"] = row["count"]

    return {
        "items": docs,
        "total": len(docs),
        "breakdown": breakdown,
        "reason_labels": VALID_REASONS,
    }
