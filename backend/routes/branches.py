from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user
from models import BranchCreate

router = APIRouter(prefix="/branches", tags=["Sucursales"])

@router.get("")
async def list_branches(user: dict = Depends(get_current_user), company_id: Optional[str] = None):
    if user["role"] == "superadmin":
        if not company_id:
            branches = await db.branches.find({}).to_list(500)
        else:
            branches = await db.branches.find({"company_id": ObjectId(company_id)}).to_list(100)
        for b in branches:
            serialize_doc(b)
            company = await db.companies.find_one({"_id": ObjectId(str(b.get("company_id", "")))}, {"name": 1})
            if company:
                b["company_name"] = company["name"]
        return branches
    query = {"company_id": ObjectId(user["company_id"])}
    branches = await db.branches.find(query, {"_id": 1, "name": 1, "address": 1, "phone": 1, "email": 1, "is_active": 1}).to_list(100)
    for b in branches:
        b["_id"] = str(b["_id"])
        b["company_id"] = str(b.get("company_id", ""))
    return branches

@router.post("")
async def create_branch(data: BranchCreate, user: dict = Depends(get_current_user), company_id: Optional[str] = None):
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    target_company_id = None
    if user["role"] == "superadmin":
        if not company_id:
            raise HTTPException(status_code=400, detail="Debe especificar la empresa (company_id)")
        target_company_id = ObjectId(company_id)
    else:
        if not user.get("company_id"):
            raise HTTPException(status_code=400, detail="No tiene empresa asignada")
        target_company_id = ObjectId(user["company_id"])
    
    # Check plan branch limit
    company = await db.companies.find_one({"_id": target_company_id})
    if company and company.get("plan_id"):
        plan = await db.plans.find_one({"_id": company["plan_id"]})
        if plan and plan.get("max_branches", 0) > 0:
            current_count = await db.branches.count_documents({"company_id": target_company_id})
            if current_count >= plan["max_branches"]:
                raise HTTPException(status_code=403, detail=f"Limite de sucursales alcanzado ({plan['max_branches']}). Actualice su plan para agregar mas.")
    
    branch_doc = {
        "company_id": target_company_id, "name": data.name, "address": data.address,
        "phone": data.phone, "email": data.email.lower() if data.email else None,
        "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.branches.insert_one(branch_doc)
    return {"_id": str(result.inserted_id), "name": data.name}

@router.get("/{branch_id}")
async def get_branch(branch_id: str, user: dict = Depends(get_current_user)):
    branch = await db.branches.find_one({"_id": ObjectId(branch_id)})
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    if user["role"] != "superadmin" and str(branch["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    branch["_id"] = str(branch["_id"])
    branch["company_id"] = str(branch["company_id"])
    return branch

@router.put("/{branch_id}")
async def update_branch(branch_id: str, data: BranchCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    branch = await db.branches.find_one({"_id": ObjectId(branch_id)})
    if not branch or str(branch["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    update_data = data.model_dump(exclude_unset=True)
    await db.branches.update_one({"_id": ObjectId(branch_id)}, {"$set": update_data})
    return {"message": "Sucursal actualizada"}

@router.delete("/{branch_id}")
async def delete_branch(branch_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Solo SuperAdmin puede eliminar sucursales")
    branch = await db.branches.find_one({"_id": ObjectId(branch_id)})
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    await db.branches.delete_one({"_id": ObjectId(branch_id)})
    return {"message": "Sucursal eliminada"}
