from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse
from bson import ObjectId
from datetime import datetime, timezone

from db import db, serialize_doc, UPLOADS_DIR
from auth_utils import get_current_user, hash_password
from models import CompanyCreate, CompanyUpdate
from routes.notifications import create_notification
from email_service import send_email, render_welcome_company
import os

router = APIRouter(prefix="/companies", tags=["Empresas"])

@router.get("")
async def list_companies(user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    companies = await db.companies.find({}).to_list(1000)
    # Batch load plans
    plan_ids = list({c["plan_id"] for c in companies if c.get("plan_id")})
    plan_map = {}
    if plan_ids:
        plans = await db.plans.find({"_id": {"$in": plan_ids}}).to_list(len(plan_ids))
        plan_map = {str(p["_id"]): p for p in plans}
    for c in companies:
        serialize_doc(c)
        cid = ObjectId(c["_id"])
        c["branches_count"] = await db.branches.count_documents({"company_id": cid})
        c["users_count"] = await db.users.count_documents({"company_id": cid})
        c["patients_count"] = await db.patients.count_documents({"company_id": cid, "is_deleted": {"$ne": True}})
        plan = plan_map.get(c.get("plan_id"))
        if plan:
            c["plan_name"] = plan["name"]
            c["max_patients"] = plan.get("max_patients", 0)
            c["max_branches"] = plan.get("max_branches", 0)
            c["patients_warning"] = plan.get("max_patients", 0) > 0 and c["patients_count"] >= plan["max_patients"] * 0.8
            c["branches_warning"] = plan.get("max_branches", 0) > 0 and c["branches_count"] >= plan["max_branches"] * 0.8
        else:
            c["plan_name"] = "Sin plan"
    return companies

@router.post("")
async def create_company(data: CompanyCreate, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    company_doc = {
        "name": data.name, "legal_name": data.legal_name, "tax_id": data.tax_id,
        "address": data.address, "phone": data.phone, "email": data.email.lower(),
        "contact_name": data.contact_name, "contact_phone": data.contact_phone,
        "contact_email": data.contact_email,
        "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.companies.insert_one(company_doc)
    company_id = result.inserted_id
    
    admin_doc = {
        "email": data.admin_email.lower(), "password_hash": hash_password(data.admin_password),
        "name": data.admin_name, "role": "admin", "company_id": company_id, "branch_id": None,
        "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(admin_doc)
    
    await create_notification(
        "new_company", "Nueva optica registrada",
        f"{data.name} se ha registrado con admin {data.admin_name} ({data.admin_email})",
        {"company_id": str(company_id), "company_name": data.name}
    )
    
    # Email de bienvenida al admin de la nueva optica
    app_url = os.environ.get("APP_URL", "https://cortexiaoptical.com")
    welcome_html = render_welcome_company(
        admin_name=data.admin_name,
        company_name=data.name,
        admin_email=data.admin_email.lower(),
        login_link=app_url,
    )
    await send_email(
        data.admin_email.lower(),
        f"Bienvenido a Cortexia Optical - {data.name}",
        welcome_html,
        tag="welcome",
    )
    
    return {"_id": str(company_id), "name": data.name, "message": "Empresa creada exitosamente"}

@router.get("/{company_id}")
async def get_company(company_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    company = await db.companies.find_one({"_id": ObjectId(company_id)})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    company["_id"] = str(company["_id"])
    return company

@router.put("/{company_id}")
async def update_company(company_id: str, data: CompanyUpdate, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Sin datos para actualizar")
    await db.companies.update_one({"_id": ObjectId(company_id)}, {"$set": update_data})
    return {"message": "Empresa actualizada"}

@router.delete("/{company_id}")
async def delete_company(company_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    await db.companies.update_one({"_id": ObjectId(company_id)}, {"$set": {"is_active": False}})
    return {"message": "Empresa desactivada"}

@router.post("/{company_id}/logo")
async def upload_company_logo(company_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    company = await db.companies.find_one({"_id": ObjectId(company_id)})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
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

@router.get("/{company_id}/logo")
async def get_company_logo(company_id: str):
    company = await db.companies.find_one({"_id": ObjectId(company_id)}, {"logo_filename": 1})
    if not company or not company.get("logo_filename"):
        raise HTTPException(status_code=404, detail="Sin logo")
    filepath = UPLOADS_DIR / company["logo_filename"]
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    ext = company["logo_filename"].rsplit(".", 1)[-1].lower()
    media_types = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}
    return FileResponse(str(filepath), media_type=media_types.get(ext, "image/png"))
