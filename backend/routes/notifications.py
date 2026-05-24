from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notificaciones"])

@router.get("")
async def list_notifications(user: dict = Depends(get_current_user), limit: int = 30):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    notifications = await db.notifications.find({}).sort("created_at", -1).limit(limit).to_list(limit)
    for n in notifications:
        serialize_doc(n)
    return notifications

@router.get("/unread-count")
async def unread_count(user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        return {"count": 0}
    count = await db.notifications.count_documents({"is_read": False})
    return {"count": count}

@router.put("/{notification_id}/read")
async def mark_as_read(notification_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    await db.notifications.update_one({"_id": ObjectId(notification_id)}, {"$set": {"is_read": True}})
    return {"message": "ok"}

@router.put("/read-all")
async def mark_all_as_read(user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    await db.notifications.update_many({"is_read": False}, {"$set": {"is_read": True}})
    return {"message": "ok"}


# === Notification creation helpers (called from other routes) ===
async def create_notification(event_type: str, title: str, message: str, metadata: dict = None):
    """Create a push notification for the SuperAdmin."""
    await db.notifications.insert_one({
        "event_type": event_type,
        "title": title,
        "message": message,
        "metadata": metadata or {},
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
