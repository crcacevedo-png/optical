from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone

from db import db, serialize_doc
from auth_utils import get_current_user
from models import AnnouncementCreate, AnnouncementUpdate

router = APIRouter(prefix="/announcements", tags=["Comunicacion"])

@router.get("")
async def list_announcements(user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    announcements = await db.announcements.find({}).sort("created_at", -1).to_list(200)
    for a in announcements:
        serialize_doc(a)
    return announcements

@router.post("")
async def create_announcement(data: AnnouncementCreate, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    now = datetime.now(timezone.utc)
    doc = {
        "title": data.title,
        "message": data.message,
        "type": data.type,
        "target_plans": data.target_plans or [],
        "target_cities": data.target_cities or [],
        "start_date": data.start_date or now.strftime("%Y-%m-%d"),
        "end_date": data.end_date,
        "is_active": True,
        "created_by": user["_id"],
        "created_at": now.isoformat()
    }
    result = await db.announcements.insert_one(doc)
    return {"_id": str(result.inserted_id), "message": "Anuncio creado"}

@router.put("/{announcement_id}")
async def update_announcement(announcement_id: str, data: AnnouncementUpdate, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        ann = await db.announcements.find_one({"_id": ObjectId(announcement_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID invalido")
    if not ann:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.announcements.update_one({"_id": ObjectId(announcement_id)}, {"$set": update_data})
    return {"message": "Anuncio actualizado"}

@router.delete("/{announcement_id}")
async def delete_announcement(announcement_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    await db.announcements.delete_one({"_id": ObjectId(announcement_id)})
    return {"message": "Anuncio eliminado"}

@router.get("/active")
async def get_active_announcements(user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        return []
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    query = {
        "is_active": True,
        "start_date": {"$lte": today},
        "$or": [
            {"end_date": None},
            {"end_date": ""},
            {"end_date": {"$gte": today}}
        ]
    }
    announcements = await db.announcements.find(query).sort("created_at", -1).to_list(50)
    
    # Filter by plan and city
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    plan_name = None
    company_city = None
    if company:
        company_city = (company.get("address") or "").lower()
        if company.get("plan_id"):
            plan = await db.plans.find_one({"_id": company["plan_id"]}, {"name": 1})
            if plan:
                plan_name = plan["name"]
    
    filtered = []
    for a in announcements:
        # Plan filter
        tp = a.get("target_plans", [])
        if tp and len(tp) > 0 and plan_name and plan_name not in tp:
            continue
        # City filter
        tc = a.get("target_cities", [])
        if tc and len(tc) > 0:
            if not company_city or not any(c.lower() in company_city for c in tc):
                continue
        serialize_doc(a)
        filtered.append(a)
    
    return filtered
