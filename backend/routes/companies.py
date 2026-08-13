from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import FileResponse, Response
from bson import ObjectId
from datetime import datetime, timezone

from db import db, serialize_doc, UPLOADS_DIR
from auth_utils import get_current_user, hash_password
from models import CompanyCreate, CompanyUpdate
from routes.notifications import create_notification
from email_service import queue_email, render_welcome_company
import object_storage as objstore
import os
import re

router = APIRouter(prefix="/companies", tags=["Empresas"])

@router.get("")
async def list_companies(
    user: dict = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    search: str = Query("", max_length=100),
):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    query = {}
    if search:
        # SEC hardening: escape user input para prevenir ReDoS
        safe = re.escape(search)
        query = {"$or": [
            {"name": {"$regex": safe, "$options": "i"}},
            {"email": {"$regex": safe, "$options": "i"}},
            {"tax_id": {"$regex": safe, "$options": "i"}},
        ]}

    companies = await db.companies.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    if not companies:
        return []

    cids = [c["_id"] for c in companies]

    # Batch load planes referenciados
    plan_ids = list({c["plan_id"] for c in companies if c.get("plan_id")})
    plan_map = {}
    if plan_ids:
        plans = await db.plans.find({"_id": {"$in": plan_ids}}).to_list(len(plan_ids))
        plan_map = {str(p["_id"]): p for p in plans}

    # Batch counts via aggregation (elimina el N+1: 3 queries totales sin importar N companies)
    async def _counts_by_company(collection, match_extra=None):
        pipeline = [{"$match": {"company_id": {"$in": cids}, **(match_extra or {})}},
                    {"$group": {"_id": "$company_id", "count": {"$sum": 1}}}]
        rows = await collection.aggregate(pipeline).to_list(len(cids))
        return {str(r["_id"]): r["count"] for r in rows}

    branches_counts = await _counts_by_company(db.branches)
    users_counts = await _counts_by_company(db.users)
    patients_counts = await _counts_by_company(db.patients, {"is_deleted": {"$ne": True}})

    # Batch fetch admin activity (first/last login) para cada company
    admin_activity = {}
    admin_pipeline = [
        {"$match": {"company_id": {"$in": cids}, "role": "admin"}},
        {"$sort": {"created_at": 1}},
        {"$group": {
            "_id": "$company_id",
            "admin_email": {"$first": "$email"},
            "admin_name": {"$first": "$name"},
            "admin_id": {"$first": "$_id"},
            "first_login_at": {"$min": "$first_login_at"},
            "last_login_at": {"$max": "$last_login_at"},
        }}
    ]
    async for row in db.users.aggregate(admin_pipeline):
        admin_activity[str(row["_id"])] = row

    now = datetime.now(timezone.utc)

    def _days_since(iso_str):
        if not iso_str:
            return None
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int((now - dt).total_seconds() // 86400)
        except Exception:
            return None

    for c in companies:
        serialize_doc(c)
        cid_str = c["_id"]
        c["branches_count"] = branches_counts.get(cid_str, 0)
        c["users_count"] = users_counts.get(cid_str, 0)
        c["patients_count"] = patients_counts.get(cid_str, 0)
        plan = plan_map.get(c.get("plan_id"))
        if plan:
            c["plan_name"] = plan["name"]
            c["max_patients"] = plan.get("max_patients", 0)
            c["max_branches"] = plan.get("max_branches", 0)
            c["patients_warning"] = plan.get("max_patients", 0) > 0 and c["patients_count"] >= plan["max_patients"] * 0.8
            c["branches_warning"] = plan.get("max_branches", 0) > 0 and c["branches_count"] >= plan["max_branches"] * 0.8
        else:
            c["plan_name"] = "Sin plan"

        # Datos de activacion del admin
        act = admin_activity.get(cid_str)
        if act:
            c["admin_email"] = act.get("admin_email")
            c["admin_name"] = act.get("admin_name")
            c["admin_first_login_at"] = act.get("first_login_at")
            c["admin_last_login_at"] = act.get("last_login_at")
            c["admin_activated"] = bool(act.get("first_login_at"))
            c["days_since_last_login"] = _days_since(act.get("last_login_at"))
        else:
            c["admin_email"] = None
            c["admin_name"] = None
            c["admin_first_login_at"] = None
            c["admin_last_login_at"] = None
            c["admin_activated"] = False
            c["days_since_last_login"] = None
        c["days_since_created"] = _days_since(c.get("created_at"))

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
        admin_password=data.admin_password,
        login_link=app_url,
    )
    queue_email(
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
    content = await file.read()
    filename = f"{company_id}.{ext}"
    if objstore.is_enabled():
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
        filepath = UPLOADS_DIR / filename
        with open(filepath, "wb") as f:
            f.write(content)
        await db.companies.update_one(
            {"_id": ObjectId(company_id)},
            {"$set": {"logo_filename": filename, "logo_storage_path": None}},
        )
    return {"message": "Logo actualizado", "logo_url": f"/api/companies/{company_id}/logo"}

@router.get("/{company_id}/logo")
async def get_company_logo(company_id: str):
    company = await db.companies.find_one(
        {"_id": ObjectId(company_id)},
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
    filepath = UPLOADS_DIR / company["logo_filename"]
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(str(filepath), media_type=media_type)
