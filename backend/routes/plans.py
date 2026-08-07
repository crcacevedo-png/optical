from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone

from db import db, serialize_doc
from auth_utils import get_current_user
from models import PlanCreate, PlanUpdate
from routes.notifications import create_notification
from cache import plans_cache

router = APIRouter(prefix="/plans", tags=["Planes"])


async def _load_plans_from_db():
    plans = await db.plans.find({}).sort("price", 1).to_list(50)
    for p in plans:
        serialize_doc(p)
    return plans


@router.get("")
async def list_plans(user: dict = Depends(get_current_user)):
    # Cache 5 min: los planes son casi estaticos (SuperAdmin edita ocasionalmente)
    return await plans_cache.get_or_load("all_plans", _load_plans_from_db)

@router.post("")
async def create_plan(data: PlanCreate, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    plan_doc = {
        **data.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.plans.insert_one(plan_doc)
    await plans_cache.ainvalidate("all_plans")
    return {"_id": str(result.inserted_id), "message": "Plan creado"}

@router.put("/{plan_id}")
async def update_plan(plan_id: str, data: PlanUpdate, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        oid = ObjectId(plan_id)
    except Exception:
        raise HTTPException(status_code=400, detail="plan_id invalido")
    plan = await db.plans.find_one({"_id": oid})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.plans.update_one({"_id": oid}, {"$set": update_data})
    await plans_cache.ainvalidate("all_plans")
    return {"message": "Plan actualizado"}

@router.delete("/{plan_id}")
async def delete_plan(plan_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        oid = ObjectId(plan_id)
    except Exception:
        raise HTTPException(status_code=400, detail="plan_id invalido")
    companies_using = await db.companies.count_documents({"plan_id": oid})
    if companies_using > 0:
        raise HTTPException(status_code=400, detail=f"No se puede eliminar: {companies_using} empresa(s) usan este plan")
    await db.plans.delete_one({"_id": oid})
    await plans_cache.ainvalidate("all_plans")
    return {"message": "Plan eliminado"}

@router.put("/assign/{company_id}")
async def assign_plan(company_id: str, plan_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        new_plan = await db.plans.find_one({"_id": ObjectId(plan_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="plan_id invalido")
    if not new_plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    try:
        cid = ObjectId(company_id)
    except Exception:
        raise HTTPException(status_code=400, detail="company_id invalido")
    
    # Get current plan for history
    company = await db.companies.find_one({"_id": cid}, {"plan_id": 1, "name": 1})
    old_plan_name = None
    if company and company.get("plan_id"):
        old_plan = await db.plans.find_one({"_id": company["plan_id"]}, {"name": 1})
        if old_plan:
            old_plan_name = old_plan["name"]
    
    await db.companies.update_one({"_id": cid}, {"$set": {"plan_id": ObjectId(plan_id)}})
    
    # Record plan change history
    await db.plan_history.insert_one({
        "company_id": cid,
        "company_name": company["name"] if company else "",
        "old_plan_name": old_plan_name,
        "new_plan_name": new_plan["name"],
        "old_plan_id": company.get("plan_id") if company else None,
        "new_plan_id": ObjectId(plan_id),
        "changed_by": user["_id"],
        "changed_by_name": user.get("name", ""),
        "changed_at": datetime.now(timezone.utc).isoformat()
    })
    
    company_name = company["name"] if company else "Desconocida"
    await create_notification(
        "plan_change", "Cambio de plan",
        f"{company_name} cambio de {old_plan_name or 'Sin plan'} a {new_plan['name']}",
        {"company_id": str(cid), "company_name": company_name, "old_plan": old_plan_name, "new_plan": new_plan["name"]}
    )
    
    return {"message": "Plan asignado"}

@router.get("/usage/{company_id}")
async def get_plan_usage(company_id: str, user: dict = Depends(get_current_user)):
    try:
        cid = ObjectId(company_id)
    except Exception:
        raise HTTPException(status_code=400, detail="company_id invalido")
    company = await db.companies.find_one({"_id": cid})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    
    plan = None
    if company.get("plan_id"):
        plan = await db.plans.find_one({"_id": company["plan_id"]})
        if plan:
            serialize_doc(plan)
    
    patients_count = await db.patients.count_documents({"company_id": cid, "is_deleted": {"$ne": True}})
    branches_count = await db.branches.count_documents({"company_id": cid})
    
    max_patients = plan["max_patients"] if plan else 50
    max_branches = plan["max_branches"] if plan else 1
    
    return {
        "plan": plan,
        "patients_count": patients_count,
        "branches_count": branches_count,
        "max_patients": max_patients,
        "max_branches": max_branches,
        "patients_percent": round((patients_count / max_patients * 100), 1) if max_patients > 0 else 0,
        "branches_percent": round((branches_count / max_branches * 100), 1) if max_branches > 0 else 0,
        "patients_warning": max_patients > 0 and patients_count >= max_patients * 0.8,
        "branches_warning": max_branches > 0 and branches_count >= max_branches * 0.8,
        "patients_limit_reached": max_patients > 0 and patients_count >= max_patients,
        "branches_limit_reached": max_branches > 0 and branches_count >= max_branches,
    }


@router.get("/history/{company_id}")
async def get_plan_history(company_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        cid = ObjectId(company_id)
    except Exception:
        raise HTTPException(status_code=400, detail="company_id invalido")
    
    history = await db.plan_history.find({"company_id": cid}).sort("changed_at", -1).to_list(100)
    for h in history:
        serialize_doc(h)
    return history
