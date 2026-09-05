"""Panel de la cola de correos para SuperAdmin.

Permite ver los correos encolados (enviados/pendientes/enviando/fallidos) y
reencolarlos con un clic. Solo lectura + reenvio; el envio real lo hace el
worker interno (email_service.email_worker_loop).
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional
import re

from db import db, serialize_doc
from auth_utils import get_current_user
from audit import log_audit

router = APIRouter(prefix="/email-queue", tags=["Cola de Correos"])

# Excluye campos pesados del listado (cuerpo HTML y contenido base64 de adjuntos).
_LIST_PROJECTION = {"html": 0, "attachments.content": 0}


def _require_superadmin(user: dict):
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")


@router.get("/stats")
async def email_queue_stats(user: dict = Depends(get_current_user)):
    """Conteos por estado para las tarjetas del panel."""
    _require_superadmin(user)
    statuses = ["pending", "sending", "sent", "failed"]
    counts = {s: await db.email_queue.count_documents({"status": s}) for s in statuses}
    counts["total"] = await db.email_queue.count_documents({})
    return counts


@router.get("")
async def list_email_queue(
    user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """Lista paginada de la cola de correos, ordenada por mas reciente."""
    _require_superadmin(user)
    q: dict = {}
    if status and status != "all":
        q["status"] = status
    if tag:
        q["tag"] = tag
    if search:
        q["to"] = {"$regex": re.escape(search), "$options": "i"}

    total = await db.email_queue.count_documents(q)
    docs = await db.email_queue.find(q, _LIST_PROJECTION).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    for d in docs:
        atts = d.get("attachments") or []
        d["attachment_names"] = [a.get("filename") for a in atts]
        d["attachment_count"] = len(atts)
        d.pop("attachments", None)
    return {
        "items": [serialize_doc(d) for d in docs],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("/{email_id}/resend")
async def resend_email(email_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Reencola un correo (lo devuelve a pending, reinicia intentos)."""
    _require_superadmin(user)
    try:
        oid = ObjectId(email_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID invalido")
    doc = await db.email_queue.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Correo no encontrado en la cola")

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.email_queue.update_one(
        {"_id": oid},
        {
            "$set": {
                "status": "pending",
                "attempts": 0,
                "next_attempt_at": now_iso,
                "updated_at": now_iso,
                "last_error": None,
            },
            "$unset": {"completed_at": ""},
        },
    )
    await log_audit(
        "EMAIL_QUEUE_RESEND", actor_id=user["_id"], actor_email=user.get("email"),
        actor_role="superadmin",
        metadata={"to": doc.get("to"), "subject": doc.get("subject"), "email_id": email_id},
        request=request,
    )
    return {"ok": True, "message": "Correo reencolado para envio"}


@router.post("/retry-failed")
async def retry_all_failed(request: Request, user: dict = Depends(get_current_user)):
    """Reencola TODOS los correos en estado failed."""
    _require_superadmin(user)
    now_iso = datetime.now(timezone.utc).isoformat()
    res = await db.email_queue.update_many(
        {"status": "failed"},
        {
            "$set": {
                "status": "pending",
                "attempts": 0,
                "next_attempt_at": now_iso,
                "updated_at": now_iso,
                "last_error": None,
            },
            "$unset": {"completed_at": ""},
        },
    )
    await log_audit(
        "EMAIL_QUEUE_RETRY_ALL_FAILED", actor_id=user["_id"], actor_email=user.get("email"),
        actor_role="superadmin", metadata={"count": res.modified_count}, request=request,
    )
    return {"ok": True, "reenqueued": res.modified_count}
