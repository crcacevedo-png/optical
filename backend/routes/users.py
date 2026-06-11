from fastapi import APIRouter, HTTPException, Depends, Request
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user, hash_password, validate_password_strength
from models import UserCreate, UserUpdate
from audit import log_audit

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
async def create_user(data: UserCreate, request: Request, user: dict = Depends(get_current_user), company_id: Optional[str] = None):
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    is_valid, msg = validate_password_strength(data.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)
    
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
    new_user_id = str(result.inserted_id)
    await log_audit("USER_CREATED", actor_id=user["_id"], actor_email=user.get("email"),
                    actor_role=user["role"], company_id=str(target_company_id),
                    target_id=new_user_id, target_type="user",
                    metadata={"new_user_email": data.email.lower(), "new_user_role": data.role},
                    request=request)
    return {"_id": new_user_id, "message": "Usuario creado"}

@router.put("/{user_id}")
async def update_user(user_id: str, data: UserUpdate, request: Request, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    target_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Aislamiento multi-tenant: admin solo puede modificar usuarios de su empresa
    if user["role"] == "admin" and str(target_user.get("company_id")) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Protecciones contra escalada de privilegios
    is_self = user_id == user["_id"]
    target_is_superadmin = target_user.get("role") == "superadmin"
    
    # Nadie (excepto otro superadmin) puede modificar a un superadmin
    if target_is_superadmin and user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="No puede modificar a un superadmin")
    
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.branch_id is not None:
        update_data["branch_id"] = ObjectId(data.branch_id) if data.branch_id else None
    if data.is_active is not None:
        # Evitar que un usuario se desactive a si mismo (lockout)
        if is_self:
            raise HTTPException(status_code=400, detail="No puede cambiar su propio estado")
        update_data["is_active"] = data.is_active
    if data.password is not None and data.password:
        is_valid, msg = validate_password_strength(data.password)
        if not is_valid:
            raise HTTPException(status_code=400, detail=msg)
        update_data["password_hash"] = hash_password(data.password)
        # Revocar tokens del usuario afectado (+1s para tokens del mismo segundo)
        update_data["password_changed_at"] = int(datetime.now(timezone.utc).timestamp()) + 1
    if data.role is not None:
        # Solo superadmin puede cambiar roles, y nunca a si mismo
        if user["role"] != "superadmin":
            raise HTTPException(status_code=403, detail="Solo superadmin puede cambiar roles")
        if is_self:
            raise HTTPException(status_code=400, detail="No puede cambiar su propio rol")
        if data.role not in ["user", "admin", "superadmin"]:
            raise HTTPException(status_code=400, detail="Rol invalido")
        update_data["role"] = data.role
    
    if update_data:
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
        # Audit: detectar cambios sensibles
        if "password_hash" in update_data:
            await log_audit("PASSWORD_RESET", actor_id=user["_id"], actor_email=user.get("email"),
                            actor_role=user["role"], company_id=user.get("company_id"),
                            target_id=user_id, target_type="user",
                            metadata={"target_email": target_user.get("email")}, request=request)
        if "role" in update_data:
            await log_audit("USER_ROLE_CHANGED", actor_id=user["_id"], actor_email=user.get("email"),
                            actor_role=user["role"], company_id=user.get("company_id"),
                            target_id=user_id, target_type="user",
                            metadata={"target_email": target_user.get("email"),
                                      "old_role": target_user.get("role"), "new_role": update_data["role"]},
                            request=request)
        if "is_active" in update_data:
            action = "USER_ACTIVATED" if update_data["is_active"] else "USER_DEACTIVATED"
            await log_audit(action, actor_id=user["_id"], actor_email=user.get("email"),
                            actor_role=user["role"], company_id=user.get("company_id"),
                            target_id=user_id, target_type="user",
                            metadata={"target_email": target_user.get("email")}, request=request)
    return {"message": "Usuario actualizado"}

@router.delete("/{user_id}")
async def deactivate_user(user_id: str, request: Request, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    target_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user["role"] == "admin" and str(target_user.get("company_id")) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": False}})
    await log_audit("USER_DELETED", actor_id=user["_id"], actor_email=user.get("email"),
                    actor_role=user["role"], company_id=user.get("company_id"),
                    target_id=user_id, target_type="user",
                    metadata={"target_email": target_user.get("email")}, request=request)
    return {"message": "Usuario desactivado"}
