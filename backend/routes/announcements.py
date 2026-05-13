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
        ann_oid = ObjectId(a["_id"])
        a["views_count"] = await db.announcement_metrics.count_documents({"announcement_id": ann_oid, "action": "view"})
        a["dismissals_count"] = await db.announcement_metrics.count_documents({"announcement_id": ann_oid, "action": "dismiss"})
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
    await db.announcement_metrics.delete_many({"announcement_id": ObjectId(announcement_id)})
    return {"message": "Anuncio eliminado"}

@router.post("/{announcement_id}/track")
async def track_announcement(announcement_id: str, action: str, user: dict = Depends(get_current_user)):
    if action not in ("view", "dismiss"):
        raise HTTPException(status_code=400, detail="Accion invalida: use 'view' o 'dismiss'")
    try:
        ann_oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID invalido")
    
    company_id = user.get("company_id")
    if not company_id:
        return {"message": "ok"}
    
    existing = await db.announcement_metrics.find_one({
        "announcement_id": ann_oid,
        "company_id": ObjectId(company_id),
        "action": action
    })
    if not existing:
        company = await db.companies.find_one({"_id": ObjectId(company_id)}, {"name": 1})
        await db.announcement_metrics.insert_one({
            "announcement_id": ann_oid,
            "company_id": ObjectId(company_id),
            "company_name": company["name"] if company else "",
            "user_id": user["_id"],
            "user_name": user.get("name", ""),
            "action": action,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    return {"message": "ok"}

@router.get("/{announcement_id}/metrics")
async def get_announcement_metrics(announcement_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        ann_oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID invalido")
    
    views = await db.announcement_metrics.find({"announcement_id": ann_oid, "action": "view"}).to_list(500)
    dismissals = await db.announcement_metrics.find({"announcement_id": ann_oid, "action": "dismiss"}).to_list(500)
    
    view_companies = []
    for v in views:
        view_companies.append({
            "company_name": v.get("company_name", ""),
            "user_name": v.get("user_name", ""),
            "date": v.get("created_at", "")[:10]
        })
    dismiss_companies = []
    for d in dismissals:
        dismiss_companies.append({
            "company_name": d.get("company_name", ""),
            "user_name": d.get("user_name", ""),
            "date": d.get("created_at", "")[:10]
        })
    
    return {
        "views_count": len(views),
        "dismissals_count": len(dismissals),
        "view_details": view_companies,
        "dismiss_details": dismiss_companies,
    }

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
