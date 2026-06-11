"""Endpoint para que el SuperAdmin consulte el audit log."""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user

router = APIRouter(prefix="/audit", tags=["Auditoria"])


@router.get("/logs")
async def list_audit_logs(
    user: dict = Depends(get_current_user),
    action: Optional[str] = None,
    actor_email: Optional[str] = None,
    company_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
):
    """Lista los eventos de auditoria. Solo accesible para SuperAdmin."""
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Solo SuperAdmin puede consultar la auditoria")
    
    query = {}
    if action:
        query["action"] = action
    if actor_email:
        query["actor_email"] = {"$regex": actor_email, "$options": "i"}
    if company_id:
        from bson import ObjectId
        try:
            query["company_id"] = ObjectId(company_id)
        except Exception:
            pass
    
    total = await db.audit_log.count_documents(query)
    cursor = db.audit_log.find(query).sort("created_at", -1).skip(skip).limit(limit)
    logs = await cursor.to_list(limit)
    for log in logs:
        serialize_doc(log)
        if log.get("company_id"):
            log["company_id"] = str(log["company_id"])
        if log.get("created_at"):
            log["created_at"] = log["created_at"].isoformat() if hasattr(log["created_at"], "isoformat") else str(log["created_at"])
    
    return {"total": total, "logs": logs, "skip": skip, "limit": limit}


@router.get("/actions")
async def list_distinct_actions(user: dict = Depends(get_current_user)):
    """Lista los tipos de acciones registradas (para filtros del UI)."""
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Solo SuperAdmin puede consultar la auditoria")
    actions = await db.audit_log.distinct("action")
    return {"actions": sorted(actions)}
