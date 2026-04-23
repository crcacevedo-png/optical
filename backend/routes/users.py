from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user, hash_password
from models import UserCreate

router = APIRouter(prefix="/users", tags=["Usuarios"])

@router.get("")
async def list_users(user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    if user["role"] == "superadmin":
        users = await db.users.find({}, {"password_hash": 0}).to_list(500)
    else:
        users = await db.users.find({"company_id": ObjectId(user["company_id"])}, {"password_hash": 0}).to_list(100)
    
    for u in users:
        serialize_doc(u)
    return users

@router.post("")
async def create_user(data: UserCreate, user: dict = Depends(get_current_user), company_id: Optional[str] = None):
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="El email ya esta registrado")
    
    target_company_id = None
    if user["role"] == "superadmin":
        if not company_id:
            raise HTTPException(status_code=400, detail="Debe especificar la empresa (company_id)")
        target_company_id = ObjectId(company_id)
    else:
        target_company_id = ObjectId(user["company_id"])
    
    user_doc = {
        "email": data.email.lower(), "password_hash": hash_password(data.password),
        "name": data.name, "role": data.role, "company_id": target_company_id,
        "branch_id": ObjectId(data.branch_id) if data.branch_id else None,
        "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.users.insert_one(user_doc)
    return {"_id": str(result.inserted_id), "message": "Usuario creado"}

@router.put("/{user_id}")
async def update_user(user_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    target_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user["role"] == "admin" and str(target_user.get("company_id")) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    update_data = {}
    if "name" in data:
        update_data["name"] = data["name"]
    if "role" in data:
        update_data["role"] = data["role"]
    if "branch_id" in data:
        update_data["branch_id"] = ObjectId(data["branch_id"]) if data["branch_id"] else None
    if "is_active" in data:
        update_data["is_active"] = data["is_active"]
    if "password" in data and data["password"]:
        update_data["password_hash"] = hash_password(data["password"])
    
    if update_data:
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    return {"message": "Usuario actualizado"}

@router.delete("/{user_id}")
async def deactivate_user(user_id: str, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    target_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user["role"] == "admin" and str(target_user.get("company_id")) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": False}})
    return {"message": "Usuario desactivado"}
