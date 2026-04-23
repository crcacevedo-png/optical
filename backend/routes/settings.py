from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse
from bson import ObjectId

from db import db, serialize_doc, UPLOADS_DIR
from auth_utils import get_current_user
from models import CompanyUpdate

router = APIRouter(prefix="/settings", tags=["Configuracion"])

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
    filename = f"{company_id}.{ext}"
    filepath = UPLOADS_DIR / filename
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)
    await db.companies.update_one({"_id": ObjectId(company_id)}, {"$set": {"logo_filename": filename}})
    return {"message": "Logo actualizado", "logo_url": f"/api/companies/{company_id}/logo"}

@router.get("/logo")
async def get_my_company_logo(user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])}, {"logo_filename": 1})
    if not company or not company.get("logo_filename"):
        raise HTTPException(status_code=404, detail="Sin logo")
    filepath = UPLOADS_DIR / company["logo_filename"]
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    ext = company["logo_filename"].rsplit(".", 1)[-1].lower()
    media_types = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}
    return FileResponse(str(filepath), media_type=media_types.get(ext, "image/png"))
