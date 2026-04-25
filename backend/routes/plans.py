from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone

from db import db, serialize_doc
from auth_utils import get_current_user
from models import PlanCreate, PlanUpdate

router = APIRouter(prefix="/plans", tags=["Planes"])

@router.get("")
async def list_plans(user: dict = Depends(get_current_user)):
    plans = await db.plans.find({}).sort("price", 1).to_list(50)
    for p in plans:
        serialize_doc(p)
    return plans

@router.post("")
async def create_plan(data: PlanCreate, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    plan_doc = {
        **data.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.plans.insert_one(plan_doc)
    return {"_id": str(result.inserted_id), "message": "Plan creado"}

@router.put("/{plan_id}")
async def update_plan(plan_id: str, data: PlanUpdate, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    plan = await db.plans.find_one({"_id": ObjectId(plan_id)})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.plans.update_one({"_id": ObjectId(plan_id)}, {"$set": update_data})
    return {"message": "Plan actualizado"}

@router.delete("/{plan_id}")
async def delete_plan(plan_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    companies_using = await db.companies.count_documents({"plan_id": ObjectId(plan_id)})
    if companies_using > 0:
        raise HTTPException(status_code=400, detail=f"No se puede eliminar: {companies_using} empresa(s) usan este plan")
    await db.plans.delete_one({"_id": ObjectId(plan_id)})
    return {"message": "Plan eliminado"}

@router.put("/assign/{company_id}")
async def assign_plan(company_id: str, plan_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    plan = await db.plans.find_one({"_id": ObjectId(plan_id)})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    await db.companies.update_one({"_id": ObjectId(company_id)}, {"$set": {"plan_id": ObjectId(plan_id)}})
    return {"message": "Plan asignado"}

@router.get("/usage/{company_id}")
async def get_plan_usage(company_id: str, user: dict = Depends(get_current_user)):
    cid = ObjectId(company_id)
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
