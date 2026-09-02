"""Sistema de tickets de soporte.

Cualquier usuario autenticado (admin, user, doctor) puede crear tickets que
llegan al SuperAdmin. Los tickets son visibles solo por su creador y por el
SuperAdmin. Superadmin puede responder, cambiar estado y cerrar.

Features adicionales:
- Notificacion por email al equipo Cortexia (crcacevedo@gmail.com).
- Adjuntar screenshots (Object Storage compartido).
- Marcar tickets como leidos (por creador y por superadmin).
- SLA por prioridad (alta 24h, media 48h, baja 72h) — calculado en frontend.
"""
import os
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field

from db import db, serialize_doc
from auth_utils import get_current_user
from routes.notifications import create_notification
from email_service import queue_email, render_support_ticket
import object_storage as objstore

router = APIRouter(prefix="/support-tickets", tags=["Soporte"])


CATEGORY = Literal["bug", "consulta", "mejora", "facturacion", "otro"]
PRIORITY = Literal["baja", "media", "alta"]
STATUS = Literal["abierto", "en_progreso", "resuelto", "cerrado"]

SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "crcacevedo@gmail.com")
MAX_ATTACHMENTS_PER_TICKET = 5
MAX_ATTACHMENT_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_ATTACHMENT_EXTS = ("png", "jpg", "jpeg", "webp", "gif")


class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=5, max_length=5000)
    category: CATEGORY = "consulta"
    priority: PRIORITY = "media"


class TicketReply(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class TicketStatusUpdate(BaseModel):
    status: STATUS


def _serialize_ticket(t: dict) -> dict:
    serialize_doc(t)
    if isinstance(t.get("created_by"), ObjectId):
        t["created_by"] = str(t["created_by"])
    if isinstance(t.get("company_id"), ObjectId):
        t["company_id"] = str(t["company_id"])
    for m in t.get("messages", []) or []:
        if isinstance(m.get("author_id"), ObjectId):
            m["author_id"] = str(m["author_id"])
    for a in t.get("attachments", []) or []:
        if isinstance(a.get("uploaded_by_id"), ObjectId):
            a["uploaded_by_id"] = str(a["uploaded_by_id"])
    return t


def _compute_unread(ticket: dict, user: dict) -> bool:
    """Determina si el ticket tiene mensajes no leidos para el usuario actual."""
    updated = ticket.get("updated_at") or ticket.get("created_at")
    if user["role"] == "superadmin":
        last_read = ticket.get("last_read_by_super")
    else:
        last_read = ticket.get("last_read_by_creator")
    if not last_read:
        return True
    return (updated or "") > last_read


@router.post("")
async def create_ticket(data: TicketCreate, user: dict = Depends(get_current_user)):
    """Cualquier usuario autenticado (excepto superadmin) crea un ticket."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin no crea tickets propios")

    now = datetime.now(timezone.utc).isoformat()
    # Nombre corto de la empresa para el listing del superadmin
    company = await db.companies.find_one(
        {"_id": ObjectId(user["company_id"])}, {"name": 1}
    )
    company_name = (company or {}).get("name", "")
    doc = {
        "company_id": ObjectId(user["company_id"]),
        "company_name": company_name,
        "created_by": ObjectId(user["_id"]),
        "created_by_name": user.get("name", ""),
        "created_by_email": user.get("email", ""),
        "created_by_role": user["role"],
        "subject": data.subject.strip(),
        "category": data.category,
        "priority": data.priority,
        "status": "abierto",
        "messages": [
            {
                "author_id": ObjectId(user["_id"]),
                "author_name": user.get("name", ""),
                "author_role": user["role"],
                "message": data.message.strip(),
                "created_at": now,
            }
        ],
        "attachments": [],
        "last_read_by_creator": now,   # creador ya "leyo" al crearlo
        "last_read_by_super": None,     # super aun no lo ha leido
        "created_at": now,
        "updated_at": now,
    }
    result = await db.support_tickets.insert_one(doc)
    ticket_id = str(result.inserted_id)

    # Notificar al superadmin (push notification) — best-effort
    try:
        await create_notification(
            event_type="SUPPORT_TICKET_CREATED",
            title=f"Nuevo ticket de soporte: {data.subject[:60]}",
            message=f"{user.get('name','')} ({company_name}) creo un ticket [{data.priority}] {data.category}",
            metadata={
                "ticket_id": ticket_id,
                "company_id": user["company_id"],
                "priority": data.priority,
                "category": data.category,
            },
        )
    except Exception:
        pass

    # Email al equipo Cortexia — background task, no bloquea
    try:
        html = render_support_ticket(
            ticket_id=ticket_id,
            subject=data.subject.strip(),
            message=data.message.strip(),
            category=data.category,
            priority=data.priority,
            creator_name=user.get("name", ""),
            creator_email=user.get("email", ""),
            company_name=company_name,
        )
        subject_line = f"[Cortexia · {data.priority.upper()}] {data.subject[:80]}"
        queue_email(SUPPORT_EMAIL, subject_line, html, tag="support-ticket")
    except Exception:
        pass

    return {"_id": ticket_id, "message": "Ticket creado"}


@router.get("")
async def list_tickets(
    user: dict = Depends(get_current_user),
    status: Optional[STATUS] = None,
    priority: Optional[PRIORITY] = None,
    category: Optional[CATEGORY] = None,
    limit: int = 100,
):
    """SuperAdmin ve todos; resto ve solo los suyos."""
    query: dict = {}
    if user["role"] == "superadmin":
        pass  # sin filtro extra
    else:
        query["created_by"] = ObjectId(user["_id"])

    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    if category:
        query["category"] = category

    tickets = await db.support_tickets.find(query).sort("_id", -1).limit(min(limit, 500)).to_list(min(limit, 500))
    for t in tickets:
        serialize_doc(t)
        _serialize_ticket(t)
        # Contadores utiles en el listing
        msgs = t.get("messages", []) or []
        t["message_count"] = len(msgs)
        t["last_message_at"] = msgs[-1]["created_at"] if msgs else t.get("created_at")
        t["last_message_by_role"] = msgs[-1]["author_role"] if msgs else None
        t["attachment_count"] = len(t.get("attachments", []) or [])
        t["unread"] = _compute_unread(t, user)
    return tickets


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: str, user: dict = Depends(get_current_user)):
    try:
        oid = ObjectId(ticket_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="ID invalido") from exc
    ticket = await db.support_tickets.find_one({"_id": oid})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    # Ownership: creador o superadmin
    if user["role"] != "superadmin" and str(ticket.get("created_by")) != user["_id"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    serialize_doc(ticket)
    _serialize_ticket(ticket)
    ticket["unread"] = _compute_unread(ticket, user)
    return ticket


@router.post("/{ticket_id}/read")
async def mark_read(ticket_id: str, user: dict = Depends(get_current_user)):
    """Marca el ticket como leido por el usuario actual (creador o superadmin)."""
    try:
        oid = ObjectId(ticket_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="ID invalido") from exc
    ticket = await db.support_tickets.find_one({"_id": oid}, {"created_by": 1})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    is_creator = str(ticket.get("created_by")) == user["_id"]
    if not is_creator and user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    now = datetime.now(timezone.utc).isoformat()
    field = "last_read_by_super" if user["role"] == "superadmin" else "last_read_by_creator"
    await db.support_tickets.update_one({"_id": oid}, {"$set": {field: now}})
    return {"read_at": now}


# ─── Attachments (screenshots) ─────────────────────────────────────────────

@router.post("/{ticket_id}/attachments")
async def upload_attachment(ticket_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Sube una imagen al ticket. Guarda en Object Storage compartido."""
    try:
        oid = ObjectId(ticket_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="ID invalido") from exc
    ticket = await db.support_tickets.find_one({"_id": oid})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    is_creator = str(ticket.get("created_by")) == user["_id"]
    if not is_creator and user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    if len(ticket.get("attachments", []) or []) >= MAX_ATTACHMENTS_PER_TICKET:
        raise HTTPException(status_code=400, detail=f"Maximo {MAX_ATTACHMENTS_PER_TICKET} adjuntos por ticket")
    ext = (file.filename or "img.png").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "png"
    if ext not in ALLOWED_ATTACHMENT_EXTS:
        raise HTTPException(status_code=400, detail="Solo se permiten imagenes (PNG, JPG, WEBP, GIF)")
    content = await file.read()
    if len(content) > MAX_ATTACHMENT_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande (max 5MB)")
    if not objstore.is_enabled():
        raise HTTPException(status_code=503, detail="Almacenamiento no disponible")

    idx = len(ticket.get("attachments", []) or [])
    now = datetime.now(timezone.utc).isoformat()
    filename_safe = f"{idx:02d}_{now.replace(':','').replace('-','')[:15]}.{ext}"
    path = f"cortexia-optical/support/{ticket_id}/{filename_safe}"
    try:
        objstore.put_object(path, content, objstore.content_type_for(ext))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fallo al subir adjunto: {e}") from e

    attachment = {
        "filename": filename_safe,
        "storage_path": path,
        "content_type": objstore.content_type_for(ext),
        "size": len(content),
        "uploaded_by_id": ObjectId(user["_id"]),
        "uploaded_by_name": user.get("name", ""),
        "uploaded_at": now,
    }
    set_fields = {"updated_at": now}
    # Uploader marca como leido hasta este momento (mismo criterio que reply)
    if user["role"] == "superadmin":
        set_fields["last_read_by_super"] = now
    else:
        set_fields["last_read_by_creator"] = now
    await db.support_tickets.update_one(
        {"_id": oid},
        {"$push": {"attachments": attachment}, "$set": set_fields},
    )
    # Retorna URL de descarga
    return {
        "filename": filename_safe,
        "url": f"/api/support-tickets/{ticket_id}/attachments/{filename_safe}",
        "size": len(content),
        "content_type": attachment["content_type"],
    }


@router.get("/{ticket_id}/attachments/{filename}")
async def get_attachment(ticket_id: str, filename: str, user: dict = Depends(get_current_user)):
    try:
        oid = ObjectId(ticket_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="ID invalido") from exc
    ticket = await db.support_tickets.find_one({"_id": oid}, {"created_by": 1, "attachments": 1})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    is_creator = str(ticket.get("created_by")) == user["_id"]
    if not is_creator and user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    att = next((a for a in (ticket.get("attachments") or []) if a.get("filename") == filename), None)
    if not att:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")
    try:
        data, ct = objstore.get_object(att["storage_path"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fallo al descargar adjunto: {e}") from e
    return Response(content=data, media_type=ct or att.get("content_type", "image/png"))


@router.post("/{ticket_id}/reply")
async def reply_ticket(ticket_id: str, data: TicketReply, user: dict = Depends(get_current_user)):
    """El creador o el superadmin agregan un mensaje al hilo."""
    try:
        oid = ObjectId(ticket_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="ID invalido") from exc
    ticket = await db.support_tickets.find_one({"_id": oid})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if user["role"] != "superadmin" and str(ticket.get("created_by")) != user["_id"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    if ticket.get("status") == "cerrado":
        raise HTTPException(status_code=400, detail="El ticket esta cerrado")

    now = datetime.now(timezone.utc).isoformat()
    message = {
        "author_id": ObjectId(user["_id"]),
        "author_name": user.get("name", ""),
        "author_role": user["role"],
        "message": data.message.strip(),
        "created_at": now,
    }
    # Si el superadmin responde y el ticket estaba abierto, pasarlo a en_progreso
    new_status = ticket.get("status")
    if user["role"] == "superadmin" and new_status == "abierto":
        new_status = "en_progreso"

    set_fields = {"updated_at": now, "status": new_status}
    # Al enviar mensaje el autor ya "leyo" hasta este momento
    if user["role"] == "superadmin":
        set_fields["last_read_by_super"] = now
    else:
        set_fields["last_read_by_creator"] = now

    await db.support_tickets.update_one(
        {"_id": oid},
        {"$push": {"messages": message}, "$set": set_fields},
    )
    return {"message": "Respuesta agregada"}


@router.patch("/{ticket_id}/status")
async def update_status(ticket_id: str, data: TicketStatusUpdate, user: dict = Depends(get_current_user)):
    """Solo superadmin cambia el estado (creador puede cerrar el suyo)."""
    try:
        oid = ObjectId(ticket_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="ID invalido") from exc
    ticket = await db.support_tickets.find_one({"_id": oid})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")

    is_creator = str(ticket.get("created_by")) == user["_id"]
    is_super = user["role"] == "superadmin"
    if not is_super and not (is_creator and data.status == "cerrado"):
        raise HTTPException(status_code=403, detail="Solo SuperAdmin puede cambiar el estado")

    await db.support_tickets.update_one(
        {"_id": oid},
        {"$set": {"status": data.status, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"message": "Estado actualizado"}


@router.get("/stats/summary")
async def stats_summary(user: dict = Depends(get_current_user)):
    """Contadores para badges. SuperAdmin: global. Resto: sus tickets."""
    query: dict = {}
    if user["role"] != "superadmin":
        query["created_by"] = ObjectId(user["_id"])
    pipeline = [
        {"$match": query},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    rows = await db.support_tickets.aggregate(pipeline).to_list(10)
    by_status = {r["_id"]: r["count"] for r in rows}

    # Contador de no-leidos del usuario actual
    unread_pipeline = [
        {"$match": query},
        {"$project": {
            "updated_at": {"$ifNull": ["$updated_at", "$created_at"]},
            "last_read": (
                {"$ifNull": ["$last_read_by_super", ""]} if user["role"] == "superadmin"
                else {"$ifNull": ["$last_read_by_creator", ""]}
            ),
        }},
        {"$match": {"$expr": {"$gt": ["$updated_at", "$last_read"]}}},
        {"$count": "unread"},
    ]
    unread_rows = await db.support_tickets.aggregate(unread_pipeline).to_list(1)
    unread = unread_rows[0]["unread"] if unread_rows else 0

    return {
        "open": by_status.get("abierto", 0),
        "in_progress": by_status.get("en_progreso", 0),
        "resolved": by_status.get("resuelto", 0),
        "closed": by_status.get("cerrado", 0),
        "total": sum(by_status.values()),
        "unread": unread,
    }
