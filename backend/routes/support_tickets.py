"""Sistema de tickets de soporte.

Cualquier usuario autenticado (admin, user, doctor) puede crear tickets que
llegan al SuperAdmin. Los tickets son visibles solo por su creador y por el
SuperAdmin. Superadmin puede responder, cambiar estado y cerrar.
"""
from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

from db import db, serialize_doc
from auth_utils import get_current_user
from routes.notifications import create_notification

router = APIRouter(prefix="/support-tickets", tags=["Soporte"])


CATEGORY = Literal["bug", "consulta", "mejora", "facturacion", "otro"]
PRIORITY = Literal["baja", "media", "alta"]
STATUS = Literal["abierto", "en_progreso", "resuelto", "cerrado"]


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
    return t


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
    doc = {
        "company_id": ObjectId(user["company_id"]),
        "company_name": (company or {}).get("name", ""),
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
        "created_at": now,
        "updated_at": now,
    }
    result = await db.support_tickets.insert_one(doc)
    ticket_id = str(result.inserted_id)

    # Notificar al superadmin (push notification)
    try:
        await create_notification(
            event_type="SUPPORT_TICKET_CREATED",
            title=f"Nuevo ticket de soporte: {data.subject[:60]}",
            message=f"{user.get('name','')} ({(company or {}).get('name', '')}) creo un ticket [{data.priority}] {data.category}",
            metadata={
                "ticket_id": ticket_id,
                "company_id": user["company_id"],
                "priority": data.priority,
                "category": data.category,
            },
        )
    except Exception:
        pass  # notificacion best-effort

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
        _serialize_ticket(t)
        # Contadores utiles en el listing
        msgs = t.get("messages", []) or []
        t["message_count"] = len(msgs)
        t["last_message_at"] = msgs[-1]["created_at"] if msgs else t.get("created_at")
        t["last_message_by_role"] = msgs[-1]["author_role"] if msgs else None
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
    return _serialize_ticket(ticket)


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

    await db.support_tickets.update_one(
        {"_id": oid},
        {
            "$push": {"messages": message},
            "$set": {"updated_at": now, "status": new_status},
        },
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
    return {
        "open": by_status.get("abierto", 0),
        "in_progress": by_status.get("en_progreso", 0),
        "resolved": by_status.get("resuelto", 0),
        "closed": by_status.get("cerrado", 0),
        "total": sum(by_status.values()),
    }
