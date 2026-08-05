from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse, Response
from bson import ObjectId
from pydantic import BaseModel
from typing import List, Dict

from db import db, serialize_doc, UPLOADS_DIR
from auth_utils import get_current_user
from models import CompanyUpdate
import object_storage as objstore

router = APIRouter(prefix="/settings", tags=["Configuracion"])

# ─── Modulos disponibles para asignar a roles ─────────────────────────────
# Cada key es un modulo/menu del sistema. Los admins tienen acceso a todo.
# Solo los roles 'user' (Atencion al Cliente) son filtrables por admin.
AVAILABLE_MENU_ITEMS = [
    "dashboard", "patients", "consultations", "agenda", "prescriptions",
    "quotations", "inventory", "sales", "cash-register", "receivables",
    "suppliers", "finance", "reports",
]
DEFAULT_USER_PERMISSIONS = AVAILABLE_MENU_ITEMS.copy()


async def get_role_permissions(company_id: ObjectId, role: str) -> list:
    """Retorna la lista de items de menu permitidos para el rol dado.
    Admins retornan None (sin restriccion). Roles sin config retornan default.
    """
    if role == "admin":
        return None  # sin restricciones (respetando plan)
    company = await db.companies.find_one({"_id": company_id}, {"role_permissions": 1})
    if not company:
        return DEFAULT_USER_PERMISSIONS
    rp = (company.get("role_permissions") or {})
    if role in rp:
        return rp[role]
    return DEFAULT_USER_PERMISSIONS


@router.get("/company")
async def get_my_company(user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    if user["role"] == "superadmin":
        raise HTTPException(status_code=400, detail="SuperAdmin debe usar el panel de opticas")
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    serialize_doc(company)
    return company

@router.put("/company")
async def update_my_company(data: CompanyUpdate, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Sin datos para actualizar")
    await db.companies.update_one({"_id": ObjectId(user["company_id"])}, {"$set": update_data})
    return {"message": "Empresa actualizada"}

@router.post("/logo")
async def upload_my_company_logo(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    company_id = user["company_id"]
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "png"
    if ext not in ("png", "jpg", "jpeg", "webp", "gif"):
        raise HTTPException(status_code=400, detail="Formato no soportado. Use PNG, JPG o WEBP")
    content = await file.read()
    filename = f"{company_id}.{ext}"
    if objstore.is_enabled():
        # Object storage compartido (multi-pod safe)
        path = objstore.build_logo_path(company_id, ext)
        try:
            objstore.put_object(path, content, objstore.content_type_for(ext))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Fallo al subir logo: {e}") from e
        await db.companies.update_one(
            {"_id": ObjectId(company_id)},
            {"$set": {"logo_filename": filename, "logo_storage_path": path}},
        )
    else:
        # Fallback filesystem local (solo dev)
        filepath = UPLOADS_DIR / filename
        with open(filepath, "wb") as f:
            f.write(content)
        await db.companies.update_one(
            {"_id": ObjectId(company_id)},
            {"$set": {"logo_filename": filename, "logo_storage_path": None}},
        )
    return {"message": "Logo actualizado", "logo_url": f"/api/companies/{company_id}/logo"}

@router.get("/logo")
async def get_my_company_logo(user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    company = await db.companies.find_one(
        {"_id": ObjectId(user["company_id"])},
        {"logo_filename": 1, "logo_storage_path": 1},
    )
    if not company or not company.get("logo_filename"):
        raise HTTPException(status_code=404, detail="Sin logo")
    ext = company["logo_filename"].rsplit(".", 1)[-1].lower()
    media_type = objstore.content_type_for(ext) or "image/png"
    if company.get("logo_storage_path") and objstore.is_enabled():
        try:
            data, ct = objstore.get_object(company["logo_storage_path"])
            return Response(content=data, media_type=ct or media_type)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Logo no encontrado en storage: {e}") from e
    # Legacy local
    filepath = UPLOADS_DIR / company["logo_filename"]
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(str(filepath), media_type=media_type)


# ═══════════════════════════════════════════════════════════════════
# Permisos por Rol
# ═══════════════════════════════════════════════════════════════════

class RolePermissionsUpdate(BaseModel):
    permissions: Dict[str, List[str]]  # {"user": ["patients", "sales", ...]}


@router.get("/role-permissions")
async def get_role_permissions_endpoint(user: dict = Depends(get_current_user)):
    """Retorna permisos por rol de la empresa + catalogo de modulos disponibles."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    company = await db.companies.find_one(
        {"_id": ObjectId(user["company_id"])},
        {"role_permissions": 1}
    )
    permissions = (company or {}).get("role_permissions") or {"user": DEFAULT_USER_PERMISSIONS.copy(), "doctor": DEFAULT_USER_PERMISSIONS.copy()}
    # Asegurar que ambos roles esten presentes
    if "user" not in permissions:
        permissions["user"] = DEFAULT_USER_PERMISSIONS.copy()
    if "doctor" not in permissions:
        permissions["doctor"] = DEFAULT_USER_PERMISSIONS.copy()
    return {
        "permissions": permissions,
        "available_modules": AVAILABLE_MENU_ITEMS,
    }


@router.put("/role-permissions")
async def update_role_permissions(data: RolePermissionsUpdate, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    # Validar que las keys sean roles conocidos y los modulos sean validos
    ALLOWED_ROLES = {"user", "doctor"}  # admin no es configurable
    filtered = {}
    for role, mods in data.permissions.items():
        if role not in ALLOWED_ROLES:
            continue
        filtered[role] = [m for m in mods if m in AVAILABLE_MENU_ITEMS]
    await db.companies.update_one(
        {"_id": ObjectId(user["company_id"])},
        {"$set": {"role_permissions": filtered}}
    )
    return {"message": "Permisos actualizados", "permissions": filtered}
