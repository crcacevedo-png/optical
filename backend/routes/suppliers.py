from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user
from models import SupplierCreate, SupplierUpdate

router = APIRouter(prefix="/suppliers", tags=["Proveedores"])

@router.get("")
async def list_suppliers(user: dict = Depends(get_current_user), search: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"]), "is_active": {"$ne": False}}
    if search:
        regex = {"$regex": search, "$options": "i"}
        query["$or"] = [{"name": regex}, {"contact_name": regex}, {"phone": regex}]
    
    suppliers = await db.suppliers.find(query).sort("name", 1).to_list(500)
    for s in suppliers:
        serialize_doc(s)
    return suppliers

@router.post("")
async def create_supplier(data: SupplierCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin", "optometrista", "vendedor"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    supplier_doc = {
        **data.model_dump(),
        "company_id": ObjectId(user["company_id"]),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user["_id"]
    }
    result = await db.suppliers.insert_one(supplier_doc)
    return {"_id": str(result.inserted_id), "message": "Proveedor creado"}

@router.get("/{supplier_id}")
async def get_supplier(supplier_id: str, user: dict = Depends(get_current_user)):
    supplier = await db.suppliers.find_one({"_id": ObjectId(supplier_id)})
    if not supplier:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    if user["role"] != "superadmin" and str(supplier["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    serialize_doc(supplier)
    return supplier

@router.put("/{supplier_id}")
async def update_supplier(supplier_id: str, data: SupplierUpdate, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin", "optometrista", "vendedor"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    supplier = await db.suppliers.find_one({"_id": ObjectId(supplier_id)})
    if not supplier or str(supplier["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    
    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.suppliers.update_one({"_id": ObjectId(supplier_id)}, {"$set": update_data})
    return {"message": "Proveedor actualizado"}

@router.delete("/{supplier_id}")
async def delete_supplier(supplier_id: str, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Solo Admin puede eliminar proveedores")
    
    supplier = await db.suppliers.find_one({"_id": ObjectId(supplier_id)})
    if not supplier or str(supplier["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    
    await db.suppliers.update_one({"_id": ObjectId(supplier_id)}, {"$set": {"is_active": False}})
    return {"message": "Proveedor eliminado"}
