from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, Query, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta, date
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

# Uploads directory
UPLOADS_DIR = ROOT_DIR / "uploads" / "logos"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Config
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
REFRESH_TOKEN_EXPIRE_DAYS = 7

def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(user_id: str, email: str, role: str, company_id: str = None) -> str:
    payload = {
        "sub": user_id, "email": email, "role": role, "company_id": company_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def serialize_doc(doc):
    """Convert all ObjectId fields in a MongoDB document to strings."""
    if doc is None:
        return None
    for key, value in list(doc.items()):
        if isinstance(value, ObjectId):
            doc[key] = str(value)
    return doc

def calculate_age(birth_date_str: str) -> int:
    if not birth_date_str:
        return None
    try:
        birth = datetime.strptime(birth_date_str[:10], "%Y-%m-%d").date()
        today = date.today()
        return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    except (ValueError, TypeError):
        return None

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Tipo de token inválido")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        if user.get("company_id"):
            user["company_id"] = str(user["company_id"])
        if user.get("branch_id"):
            user["branch_id"] = str(user["branch_id"])
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

# ==================== PYDANTIC MODELS ====================
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class CompanyCreate(BaseModel):
    name: str
    legal_name: str = ""
    tax_id: str = ""
    address: str = ""
    phone: str
    email: EmailStr
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    admin_name: str
    admin_email: EmailStr
    admin_password: str

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    legal_name: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    is_active: Optional[bool] = None

class BranchCreate(BaseModel):
    name: str
    address: str
    phone: str
    email: Optional[EmailStr] = None

class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    dpi: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    phone: str
    whatsapp: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = "Guatemala"
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    notes: Optional[str] = None
    branch_id: Optional[str] = None

class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    dpi: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    notes: Optional[str] = None
    branch_id: Optional[str] = None

class AppointmentCreate(BaseModel):
    patient_id: str
    branch_id: Optional[str] = None
    professional_id: Optional[str] = None
    professional_name: Optional[str] = None
    date: str
    time: str
    duration: int = 30
    type: str
    status: Optional[str] = "pendiente"
    notes: Optional[str] = None

class AppointmentUpdate(BaseModel):
    status: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    duration: Optional[int] = None
    type: Optional[str] = None
    professional_name: Optional[str] = None
    notes: Optional[str] = None

class EyeglassPrescriptionCreate(BaseModel):
    patient_id: str
    consultation_id: Optional[str] = None
    professional_name: Optional[str] = None
    od_sphere: Optional[float] = None
    od_cylinder: Optional[float] = None
    od_axis: Optional[int] = None
    od_addition: Optional[float] = None
    od_dp: Optional[float] = None
    oi_sphere: Optional[float] = None
    oi_cylinder: Optional[float] = None
    oi_axis: Optional[int] = None
    oi_addition: Optional[float] = None
    oi_dp: Optional[float] = None
    observations: Optional[str] = None
    lens_type: Optional[str] = None
    frame_type: Optional[str] = None

class MedicalPrescriptionCreate(BaseModel):
    patient_id: str
    consultation_id: Optional[str] = None
    professional_name: Optional[str] = None
    diagnosis: Optional[str] = None
    medications: List[dict]
    instructions: Optional[str] = None

class ContactLensPrescriptionCreate(BaseModel):
    patient_id: str
    consultation_id: Optional[str] = None
    professional_name: Optional[str] = None
    od_power: Optional[float] = None
    od_bc: Optional[float] = None
    od_dia: Optional[float] = None
    od_cylinder: Optional[float] = None
    od_axis: Optional[int] = None
    od_addition: Optional[float] = None
    oi_power: Optional[float] = None
    oi_bc: Optional[float] = None
    oi_dia: Optional[float] = None
    oi_cylinder: Optional[float] = None
    oi_axis: Optional[int] = None
    oi_addition: Optional[float] = None
    brand: Optional[str] = None
    lens_type: Optional[str] = None
    replacement: Optional[str] = None
    observations: Optional[str] = None

class ProductCreate(BaseModel):
    name: str
    sku: str
    category: str
    brand: Optional[str] = None
    description: Optional[str] = None
    cost_price: float
    sale_price: float
    min_stock: int = 5
    branch_id: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    description: Optional[str] = None
    cost_price: Optional[float] = None
    sale_price: Optional[float] = None
    min_stock: Optional[int] = None

class InventoryMovement(BaseModel):
    product_id: str
    branch_id: str
    type: str  # 'entrada', 'salida'
    quantity: int
    notes: Optional[str] = None
    reference: Optional[str] = None

class SaleCreate(BaseModel):
    patient_id: Optional[str] = None
    items: List[dict]
    subtotal: float
    discount: float = 0
    tax: float = 0
    total: float
    payment_method: str
    amount_paid: float
    notes: Optional[str] = None

class FinanceEntryCreate(BaseModel):
    type: str  # 'ingreso', 'egreso'
    category: str
    amount: float
    description: str
    date: Optional[str] = None
    reference: Optional[str] = None

class QuotationCreate(BaseModel):
    patient_id: str
    items: List[dict]  # [{product_id, name, quantity, unit_price, subtotal}]
    subtotal: float
    discount: float = 0
    discount_type: str = "amount"  # 'amount' or 'percent'
    total: float
    notes: Optional[str] = None
    payment_conditions: Optional[str] = None
    validity_days: int = 15

class QuotationStatusUpdate(BaseModel):
    status: str  # 'aceptada', 'rechazada', 'vencida'

class ConsultationCreate(BaseModel):
    patient_id: str
    appointment_id: Optional[str] = None
    consultation_date: str
    consultation_time: Optional[str] = None
    consultation_type: str = "general"
    chief_complaint: str
    anamnesis: Optional[str] = None
    findings: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    recommendations: Optional[str] = None
    notes: Optional[str] = None
    # Historia Clinica - Antecedentes Oculares
    wears_glasses: Optional[bool] = None
    glasses_since: Optional[str] = None
    glasses_type: Optional[str] = None
    ocular_surgeries: Optional[str] = None
    ocular_trauma: Optional[str] = None
    ocular_diseases: Optional[str] = None
    # Historia Clinica - Antecedentes Sistemicos
    diabetes: Optional[bool] = None
    hypertension: Optional[bool] = None
    autoimmune_disease: Optional[bool] = None
    autoimmune_details: Optional[str] = None
    current_medications: Optional[str] = None
    allergies: Optional[str] = None
    # Historia Clinica - Antecedentes Familiares
    family_glaucoma: Optional[bool] = None
    family_glaucoma_relationship: Optional[str] = None
    family_macular_degeneration: Optional[bool] = None
    family_macular_relationship: Optional[str] = None
    family_high_myopia: Optional[bool] = None
    family_high_myopia_relationship: Optional[str] = None
    family_other_history: Optional[str] = None
    # Agudeza Visual
    va_distance_without_rx_od: Optional[str] = None
    va_distance_without_rx_oi: Optional[str] = None
    va_distance_with_rx_od: Optional[str] = None
    va_distance_with_rx_oi: Optional[str] = None
    va_near_without_rx_od: Optional[str] = None
    va_near_without_rx_oi: Optional[str] = None
    va_near_with_rx_od: Optional[str] = None
    va_near_with_rx_oi: Optional[str] = None
    va_pinhole_od: Optional[str] = None
    va_pinhole_oi: Optional[str] = None
    visual_acuity_method: Optional[str] = None

class ConsultationUpdate(BaseModel):
    consultation_type: Optional[str] = None
    chief_complaint: Optional[str] = None
    anamnesis: Optional[str] = None
    findings: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment_plan: Optional[str] = None
    recommendations: Optional[str] = None
    notes: Optional[str] = None
    wears_glasses: Optional[bool] = None
    glasses_since: Optional[str] = None
    glasses_type: Optional[str] = None
    ocular_surgeries: Optional[str] = None
    ocular_trauma: Optional[str] = None
    ocular_diseases: Optional[str] = None
    diabetes: Optional[bool] = None
    hypertension: Optional[bool] = None
    autoimmune_disease: Optional[bool] = None
    autoimmune_details: Optional[str] = None
    current_medications: Optional[str] = None
    allergies: Optional[str] = None
    family_glaucoma: Optional[bool] = None
    family_glaucoma_relationship: Optional[str] = None
    family_macular_degeneration: Optional[bool] = None
    family_macular_relationship: Optional[str] = None
    family_high_myopia: Optional[bool] = None
    family_high_myopia_relationship: Optional[str] = None
    family_other_history: Optional[str] = None
    va_distance_without_rx_od: Optional[str] = None
    va_distance_without_rx_oi: Optional[str] = None
    va_distance_with_rx_od: Optional[str] = None
    va_distance_with_rx_oi: Optional[str] = None
    va_near_without_rx_od: Optional[str] = None
    va_near_without_rx_oi: Optional[str] = None
    va_near_with_rx_od: Optional[str] = None
    va_near_with_rx_oi: Optional[str] = None
    va_pinhole_od: Optional[str] = None
    va_pinhole_oi: Optional[str] = None
    visual_acuity_method: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str
    branch_id: Optional[str] = None

# ==================== APP SETUP ====================
app = FastAPI(title="Cortexia Optical API")

api_router = APIRouter(prefix="/api")
auth_router = APIRouter(prefix="/auth", tags=["Autenticación"])
companies_router = APIRouter(prefix="/companies", tags=["Empresas"])
branches_router = APIRouter(prefix="/branches", tags=["Sucursales"])
patients_router = APIRouter(prefix="/patients", tags=["Pacientes"])
appointments_router = APIRouter(prefix="/appointments", tags=["Agenda"])
prescriptions_router = APIRouter(prefix="/prescriptions", tags=["Recetas"])
inventory_router = APIRouter(prefix="/inventory", tags=["Inventario"])
sales_router = APIRouter(prefix="/sales", tags=["Ventas"])
quotations_router = APIRouter(prefix="/quotations", tags=["Cotizaciones"])
consultations_router = APIRouter(prefix="/consultations", tags=["Consultas"])
finance_router = APIRouter(prefix="/finance", tags=["Finanzas"])
reports_router = APIRouter(prefix="/reports", tags=["Reportes"])
users_router = APIRouter(prefix="/users", tags=["Usuarios"])

# ==================== AUTH ROUTES ====================
@auth_router.post("/register")
async def register(data: UserRegister, response: Response):
    email = data.email.lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    user_doc = {
        "email": email, "password_hash": hash_password(data.password), "name": data.name,
        "role": "user", "company_id": None, "branch_id": None, "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    access_token = create_access_token(user_id, email, "user")
    refresh_token = create_refresh_token(user_id)
    
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite="none", max_age=86400, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")
    
    return {"_id": user_id, "email": email, "name": data.name, "role": "user"}

@auth_router.post("/login")
async def login(data: UserLogin, response: Response, request: Request):
    email = data.email.lower()
    
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= 5:
        lockout_until = attempt.get("lockout_until")
        if lockout_until and datetime.fromisoformat(lockout_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Demasiados intentos. Intente en 15 minutos.")
        else:
            await db.login_attempts.delete_one({"identifier": identifier})
    
    user = await db.users.find_one({"email": email})
    if not user:
        await increment_login_attempts(identifier)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    if not verify_password(data.password, user["password_hash"]):
        await increment_login_attempts(identifier)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Cuenta desactivada")
    
    await db.login_attempts.delete_one({"identifier": identifier})
    
    user_id = str(user["_id"])
    company_id = str(user["company_id"]) if user.get("company_id") else None
    access_token = create_access_token(user_id, email, user["role"], company_id)
    refresh_token = create_refresh_token(user_id)
    
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite="none", max_age=86400, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")
    
    return {
        "_id": user_id, "email": user["email"], "name": user["name"], "role": user["role"],
        "company_id": company_id, "branch_id": str(user["branch_id"]) if user.get("branch_id") else None
    }

async def increment_login_attempts(identifier: str):
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt:
        new_count = attempt.get("count", 0) + 1
        update = {"count": new_count}
        if new_count >= 5:
            update["lockout_until"] = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        await db.login_attempts.update_one({"identifier": identifier}, {"$set": update})
    else:
        await db.login_attempts.insert_one({"identifier": identifier, "count": 1})

@auth_router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/", secure=True, samesite="none")
    response.delete_cookie("refresh_token", path="/", secure=True, samesite="none")
    return {"message": "Sesión cerrada"}

@auth_router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user

@auth_router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No hay token de refresco")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Tipo de token inválido")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        
        user_id = str(user["_id"])
        company_id = str(user["company_id"]) if user.get("company_id") else None
        access_token = create_access_token(user_id, user["email"], user["role"], company_id)
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite="none", max_age=86400, path="/")
        return {"message": "Token renovado"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

# ==================== COMPANIES ROUTES ====================
@companies_router.get("")
async def list_companies(user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    companies = await db.companies.find({}).to_list(1000)
    for c in companies:
        serialize_doc(c)
        cid = ObjectId(c["_id"])
        c["branches_count"] = await db.branches.count_documents({"company_id": cid})
        c["users_count"] = await db.users.count_documents({"company_id": cid})
        c["patients_count"] = await db.patients.count_documents({"company_id": cid})
    return companies

@companies_router.post("")
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
    
    return {"_id": str(company_id), "name": data.name, "message": "Empresa creada exitosamente"}

@companies_router.get("/{company_id}")
async def get_company(company_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    company = await db.companies.find_one({"_id": ObjectId(company_id)})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    company["_id"] = str(company["_id"])
    return company

@companies_router.put("/{company_id}")
async def update_company(company_id: str, data: CompanyUpdate, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Sin datos para actualizar")
    await db.companies.update_one({"_id": ObjectId(company_id)}, {"$set": update_data})
    return {"message": "Empresa actualizada"}

@companies_router.delete("/{company_id}")
async def delete_company(company_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    await db.companies.update_one({"_id": ObjectId(company_id)}, {"$set": {"is_active": False}})
    return {"message": "Empresa desactivada"}

@companies_router.post("/{company_id}/logo")
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

@companies_router.get("/{company_id}/logo")
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

# ==================== BRANCHES ROUTES ====================
@branches_router.get("")
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

@branches_router.post("")
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
    
    branch_doc = {
        "company_id": target_company_id, "name": data.name, "address": data.address,
        "phone": data.phone, "email": data.email.lower() if data.email else None,
        "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.branches.insert_one(branch_doc)
    return {"_id": str(result.inserted_id), "name": data.name}

@branches_router.get("/{branch_id}")
async def get_branch(branch_id: str, user: dict = Depends(get_current_user)):
    branch = await db.branches.find_one({"_id": ObjectId(branch_id)})
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    if user["role"] != "superadmin" and str(branch["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    branch["_id"] = str(branch["_id"])
    branch["company_id"] = str(branch["company_id"])
    return branch

@branches_router.put("/{branch_id}")
async def update_branch(branch_id: str, data: BranchCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    branch = await db.branches.find_one({"_id": ObjectId(branch_id)})
    if not branch or str(branch["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    update_data = data.model_dump(exclude_unset=True)
    await db.branches.update_one({"_id": ObjectId(branch_id)}, {"$set": update_data})
    return {"message": "Sucursal actualizada"}

@branches_router.delete("/{branch_id}")
async def delete_branch(branch_id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Solo SuperAdmin puede eliminar sucursales")
    branch = await db.branches.find_one({"_id": ObjectId(branch_id)})
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    await db.branches.delete_one({"_id": ObjectId(branch_id)})
    return {"message": "Sucursal eliminada"}

# ==================== PATIENTS ROUTES ====================
@patients_router.get("")
async def list_patients(
    user: dict = Depends(get_current_user),
    search: Optional[str] = None,
    limit: int = Query(50, le=200),
    skip: int = 0
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin no puede ver pacientes")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if search:
        query["$or"] = [
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
            {"whatsapp": {"$regex": search, "$options": "i"}},
            {"dpi": {"$regex": search, "$options": "i"}}
        ]
    
    total = await db.patients.count_documents(query)
    patients = await db.patients.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    for p in patients:
        serialize_doc(p)
        p["age"] = calculate_age(p.get("birth_date"))
    
    return {"patients": patients, "total": total, "limit": limit, "skip": skip}

@patients_router.post("")
async def create_patient(data: PatientCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin no puede crear pacientes")
    
    patient_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(data.branch_id) if data.branch_id else (ObjectId(user["branch_id"]) if user.get("branch_id") else None),
        "first_name": data.first_name, "last_name": data.last_name, "dpi": data.dpi,
        "birth_date": data.birth_date, "gender": data.gender, "phone": data.phone,
        "whatsapp": data.whatsapp or data.phone, "email": data.email.lower() if data.email else None,
        "address": data.address, "city": data.city, "country": data.country,
        "emergency_contact": data.emergency_contact, "emergency_phone": data.emergency_phone,
        "notes": data.notes, "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    result = await db.patients.insert_one(patient_doc)
    return {"_id": str(result.inserted_id), "message": "Paciente creado"}

@patients_router.get("/{patient_id}")
async def get_patient(patient_id: str, user: dict = Depends(get_current_user)):
    patient = await db.patients.find_one({"_id": ObjectId(patient_id)})
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    if user["role"] != "superadmin" and str(patient["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    serialize_doc(patient)
    patient["age"] = calculate_age(patient.get("birth_date"))
    
    # Historial completo
    eyeglass_rx = await db.eyeglass_prescriptions.find({"patient_id": ObjectId(patient_id)}).sort("created_at", -1).to_list(20)
    for rx in eyeglass_rx:
        serialize_doc(rx)
    patient["eyeglass_prescriptions"] = eyeglass_rx
    
    contact_rx = await db.contact_lens_prescriptions.find({"patient_id": ObjectId(patient_id)}).sort("created_at", -1).to_list(20)
    for rx in contact_rx:
        serialize_doc(rx)
    patient["contact_prescriptions"] = contact_rx
    
    medical_rx = await db.medical_prescriptions.find({"patient_id": ObjectId(patient_id)}).sort("created_at", -1).to_list(20)
    for rx in medical_rx:
        serialize_doc(rx)
    patient["medical_prescriptions"] = medical_rx
    
    appointments = await db.appointments.find({"patient_id": ObjectId(patient_id)}).sort("date", -1).to_list(30)
    for apt in appointments:
        serialize_doc(apt)
    patient["appointments"] = appointments
    
    sales = await db.sales.find({"patient_id": ObjectId(patient_id)}).sort("created_at", -1).to_list(30)
    for s in sales:
        serialize_doc(s)
    patient["sales"] = sales
    
    consultations = await db.optical_consultations.find({"patient_id": ObjectId(patient_id)}).sort("created_at", -1).to_list(50)
    for con in consultations:
        serialize_doc(con)
        if con.get("professional_user_id"):
            prof = await db.users.find_one({"_id": ObjectId(con["professional_user_id"])}, {"name": 1})
            if prof:
                con["professional_name"] = prof["name"]
    patient["consultations"] = consultations
    
    return patient

@patients_router.put("/{patient_id}")
async def update_patient(patient_id: str, data: PatientUpdate, user: dict = Depends(get_current_user)):
    patient = await db.patients.find_one({"_id": ObjectId(patient_id)})
    if not patient or str(patient["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if "email" in update_data and update_data["email"]:
        update_data["email"] = update_data["email"].lower()
    if "branch_id" in update_data and update_data["branch_id"]:
        update_data["branch_id"] = ObjectId(update_data["branch_id"])
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.patients.update_one({"_id": ObjectId(patient_id)}, {"$set": update_data})
    return {"message": "Paciente actualizado"}

@patients_router.delete("/{patient_id}")
async def delete_patient(patient_id: str, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar pacientes")
    patient = await db.patients.find_one({"_id": ObjectId(patient_id)})
    if not patient or str(patient["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    await db.patients.update_one({"_id": ObjectId(patient_id)}, {"$set": {"is_deleted": True}})
    return {"message": "Paciente eliminado"}

# ==================== APPOINTMENTS ROUTES ====================
@appointments_router.get("")
async def list_appointments(
    user: dict = Depends(get_current_user),
    date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    branch_id: Optional[str] = None,
    view: Optional[str] = "day"
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin no puede ver citas")
    
    query = {"company_id": ObjectId(user["company_id"])}
    
    if date:
        query["date"] = date
    elif date_from and date_to:
        query["date"] = {"$gte": date_from, "$lte": date_to}
    
    if status:
        query["status"] = status
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    appointments = await db.appointments.find(query).sort([("date", 1), ("time", 1)]).to_list(500)
    for apt in appointments:
        serialize_doc(apt)
        patient = await db.patients.find_one({"_id": ObjectId(apt["patient_id"])}, {"first_name": 1, "last_name": 1, "phone": 1})
        if patient:
            apt["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
            apt["patient_phone"] = patient.get("phone", "")
    
    return appointments

@appointments_router.post("")
async def create_appointment(data: AppointmentCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin no puede crear citas")
    
    apt_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(data.branch_id) if data.branch_id else (ObjectId(user["branch_id"]) if user.get("branch_id") else None),
        "patient_id": ObjectId(data.patient_id),
        "professional_id": ObjectId(data.professional_id) if data.professional_id else None,
        "professional_name": data.professional_name,
        "date": data.date, "time": data.time, "duration": data.duration, "type": data.type,
        "status": data.status or "pendiente", "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    result = await db.appointments.insert_one(apt_doc)
    return {"_id": str(result.inserted_id), "message": "Cita creada"}

@appointments_router.get("/{appointment_id}")
async def get_appointment(appointment_id: str, user: dict = Depends(get_current_user)):
    apt = await db.appointments.find_one({"_id": ObjectId(appointment_id)})
    if not apt or str(apt["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    serialize_doc(apt)
    patient = await db.patients.find_one({"_id": ObjectId(apt["patient_id"])}, {"first_name": 1, "last_name": 1})
    if patient:
        apt["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
    return apt

@appointments_router.put("/{appointment_id}")
async def update_appointment(appointment_id: str, data: AppointmentUpdate, user: dict = Depends(get_current_user)):
    apt = await db.appointments.find_one({"_id": ObjectId(appointment_id)})
    if not apt or str(apt["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.appointments.update_one({"_id": ObjectId(appointment_id)}, {"$set": update_data})
    return {"message": "Cita actualizada"}

@appointments_router.delete("/{appointment_id}")
async def cancel_appointment(appointment_id: str, user: dict = Depends(get_current_user)):
    apt = await db.appointments.find_one({"_id": ObjectId(appointment_id)})
    if not apt or str(apt["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    await db.appointments.update_one({"_id": ObjectId(appointment_id)}, {"$set": {"status": "cancelada"}})
    return {"message": "Cita cancelada"}

# ==================== PRESCRIPTIONS - EYEGLASS ====================
@prescriptions_router.get("/eyeglass")
async def list_eyeglass_prescriptions(user: dict = Depends(get_current_user), patient_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    query = {"company_id": ObjectId(user["company_id"])}
    if patient_id:
        query["patient_id"] = ObjectId(patient_id)
    prescriptions = await db.eyeglass_prescriptions.find(query).sort("created_at", -1).to_list(100)
    for rx in prescriptions:
        serialize_doc(rx)
        patient = await db.patients.find_one({"_id": ObjectId(rx["patient_id"])}, {"first_name": 1, "last_name": 1})
        if patient:
            rx["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
    return prescriptions

@prescriptions_router.post("/eyeglass")
async def create_eyeglass_prescription(data: EyeglassPrescriptionCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    rx_doc = {
        "company_id": ObjectId(user["company_id"]), "patient_id": ObjectId(data.patient_id),
        "consultation_id": ObjectId(data.consultation_id) if data.consultation_id else None,
        "professional_name": data.professional_name or user["name"],
        "od_sphere": data.od_sphere, "od_cylinder": data.od_cylinder, "od_axis": data.od_axis,
        "od_addition": data.od_addition, "od_dp": data.od_dp,
        "oi_sphere": data.oi_sphere, "oi_cylinder": data.oi_cylinder, "oi_axis": data.oi_axis,
        "oi_addition": data.oi_addition, "oi_dp": data.oi_dp,
        "observations": data.observations, "lens_type": data.lens_type, "frame_type": data.frame_type,
        "created_at": datetime.now(timezone.utc).isoformat(), "created_by": ObjectId(user["_id"])
    }
    result = await db.eyeglass_prescriptions.insert_one(rx_doc)
    return {"_id": str(result.inserted_id), "message": "Receta creada"}

def draw_pdf_header(c, width, height, company, title):
    """Draw PDF header with company logo if available."""
    c.setFillColor(colors.HexColor("#0F4C3A"))
    c.rect(0, height - 1.2*inch, width, 1.2*inch, fill=True, stroke=False)
    logo_path = None
    if company and company.get("logo_filename"):
        candidate = UPLOADS_DIR / company["logo_filename"]
        if candidate.exists():
            logo_path = str(candidate)
    if logo_path:
        try:
            img = ImageReader(logo_path)
            iw, ih = img.getSize()
            aspect = iw / ih
            logo_h = 0.8 * inch
            logo_w = logo_h * aspect
            if logo_w > 1.5 * inch:
                logo_w = 1.5 * inch
                logo_h = logo_w / aspect
            c.drawImage(logo_path, 0.5*inch, height - 1.05*inch, width=logo_w, height=logo_h, preserveAspectRatio=True, mask='auto')
            text_x = 0.5*inch + logo_w + 0.2*inch
        except Exception:
            text_x = 1*inch
    else:
        text_x = 1*inch
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(text_x, height - 0.75*inch, company["name"] if company else "Cortexia Optical")
    c.setFont("Helvetica", 9)
    c.drawString(text_x, height - 0.95*inch, company.get("address", "") if company else "")
    phone = company.get("phone", "") if company else ""
    email = company.get("email", "") if company else ""
    if phone or email:
        c.drawString(text_x, height - 1.1*inch, f"Tel: {phone}  |  {email}")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, height - 1.55*inch, title)

@prescriptions_router.get("/eyeglass/{rx_id}/pdf")
async def get_eyeglass_prescription_pdf(rx_id: str, user: dict = Depends(get_current_user)):
    rx = await db.eyeglass_prescriptions.find_one({"_id": ObjectId(rx_id)})
    if not rx or str(rx["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    
    patient = await db.patients.find_one({"_id": rx["patient_id"]})
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    draw_pdf_header(c, width, height, company, "RECETA DE ANTEOJOS")
    
    # Info paciente
    c.setFont("Helvetica", 11)
    y = height - 2.2*inch
    c.drawString(1*inch, y, f"Paciente: {patient['first_name']} {patient['last_name']}" if patient else "")
    c.drawString(4.5*inch, y, f"Fecha: {rx['created_at'][:10]}")
    y -= 0.25*inch
    if patient and patient.get("birth_date"):
        age = calculate_age(patient["birth_date"])
        c.drawString(1*inch, y, f"Edad: {age} años" if age else "")
    c.drawString(4.5*inch, y, f"Profesional: {rx.get('professional_name', '')}")
    
    # Tabla de receta
    y -= 0.5*inch
    c.setFillColor(colors.HexColor("#F1F5F9"))
    c.rect(0.8*inch, y - 0.8*inch, 6.4*inch, 1*inch, fill=True, stroke=False)
    c.setFillColor(colors.black)
    
    c.setFont("Helvetica-Bold", 10)
    headers = ["", "ESFERA", "CILINDRO", "EJE", "ADICIÓN", "D.P."]
    x_positions = [1*inch, 1.8*inch, 2.8*inch, 3.8*inch, 4.7*inch, 5.6*inch]
    for i, header in enumerate(headers):
        c.drawString(x_positions[i], y, header)
    
    y -= 0.35*inch
    c.setFont("Helvetica", 11)
    c.drawString(x_positions[0], y, "OD")
    c.drawString(x_positions[1], y, str(rx.get("od_sphere") or "-"))
    c.drawString(x_positions[2], y, str(rx.get("od_cylinder") or "-"))
    c.drawString(x_positions[3], y, str(rx.get("od_axis") or "-") + "°" if rx.get("od_axis") else "-")
    c.drawString(x_positions[4], y, str(rx.get("od_addition") or "-"))
    c.drawString(x_positions[5], y, str(rx.get("od_dp") or "-"))
    
    y -= 0.35*inch
    c.drawString(x_positions[0], y, "OI")
    c.drawString(x_positions[1], y, str(rx.get("oi_sphere") or "-"))
    c.drawString(x_positions[2], y, str(rx.get("oi_cylinder") or "-"))
    c.drawString(x_positions[3], y, str(rx.get("oi_axis") or "-") + "°" if rx.get("oi_axis") else "-")
    c.drawString(x_positions[4], y, str(rx.get("oi_addition") or "-"))
    c.drawString(x_positions[5], y, str(rx.get("oi_dp") or "-"))
    
    # Detalles adicionales
    y -= 0.6*inch
    if rx.get("lens_type"):
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1*inch, y, "Tipo de Lente:")
        c.setFont("Helvetica", 10)
        c.drawString(2.2*inch, y, rx["lens_type"])
        y -= 0.25*inch
    
    if rx.get("observations"):
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1*inch, y, "Observaciones:")
        c.setFont("Helvetica", 10)
        c.drawString(2.4*inch, y, rx["observations"][:80])
    
    # Firma
    y = 2*inch
    c.line(1*inch, y, 3*inch, y)
    c.setFont("Helvetica", 9)
    c.drawString(1*inch, y - 0.2*inch, rx.get("professional_name", ""))
    c.drawString(1*inch, y - 0.4*inch, "Profesional de la Salud Visual")
    
    c.save()
    buffer.seek(0)
    
    return StreamingResponse(buffer, media_type="application/pdf", 
                           headers={"Content-Disposition": f"attachment; filename=receta_anteojos_{rx_id}.pdf"})

# ==================== PRESCRIPTIONS - CONTACT LENS ====================
@prescriptions_router.get("/contact")
async def list_contact_lens_prescriptions(user: dict = Depends(get_current_user), patient_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    query = {"company_id": ObjectId(user["company_id"])}
    if patient_id:
        query["patient_id"] = ObjectId(patient_id)
    prescriptions = await db.contact_lens_prescriptions.find(query).sort("created_at", -1).to_list(100)
    for rx in prescriptions:
        serialize_doc(rx)
        patient = await db.patients.find_one({"_id": ObjectId(rx["patient_id"])}, {"first_name": 1, "last_name": 1})
        if patient:
            rx["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
    return prescriptions

@prescriptions_router.post("/contact")
async def create_contact_lens_prescription(data: ContactLensPrescriptionCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    rx_doc = {
        "company_id": ObjectId(user["company_id"]), "patient_id": ObjectId(data.patient_id),
        "consultation_id": ObjectId(data.consultation_id) if data.consultation_id else None,
        "professional_name": data.professional_name or user["name"],
        "od_power": data.od_power, "od_bc": data.od_bc, "od_dia": data.od_dia,
        "od_cylinder": data.od_cylinder, "od_axis": data.od_axis, "od_addition": data.od_addition,
        "oi_power": data.oi_power, "oi_bc": data.oi_bc, "oi_dia": data.oi_dia,
        "oi_cylinder": data.oi_cylinder, "oi_axis": data.oi_axis, "oi_addition": data.oi_addition,
        "brand": data.brand, "lens_type": data.lens_type, "replacement": data.replacement,
        "observations": data.observations,
        "created_at": datetime.now(timezone.utc).isoformat(), "created_by": ObjectId(user["_id"])
    }
    result = await db.contact_lens_prescriptions.insert_one(rx_doc)
    return {"_id": str(result.inserted_id), "message": "Receta de lentes de contacto creada"}

@prescriptions_router.get("/contact/{rx_id}/pdf")
async def get_contact_lens_prescription_pdf(rx_id: str, user: dict = Depends(get_current_user)):
    rx = await db.contact_lens_prescriptions.find_one({"_id": ObjectId(rx_id)})
    if not rx or str(rx["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    
    patient = await db.patients.find_one({"_id": rx["patient_id"]})
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Header
    c.setFillColor(colors.HexColor("#0F4C3A"))
    c.rect(0, height - 1.2*inch, width, 1.2*inch, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(1*inch, height - 0.8*inch, company["name"] if company else "Cortexia Optical")
    c.setFont("Helvetica", 10)
    c.drawString(1*inch, height - 1*inch, company.get("address", "") if company else "")
    
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, height - 1.7*inch, "RECETA DE LENTES DE CONTACTO")
    
    c.setFont("Helvetica", 11)
    y = height - 2.2*inch
    c.drawString(1*inch, y, f"Paciente: {patient['first_name']} {patient['last_name']}" if patient else "")
    c.drawString(4.5*inch, y, f"Fecha: {rx['created_at'][:10]}")
    y -= 0.25*inch
    c.drawString(4.5*inch, y, f"Profesional: {rx.get('professional_name', '')}")
    
    # Tabla
    y -= 0.5*inch
    c.setFillColor(colors.HexColor("#F1F5F9"))
    c.rect(0.8*inch, y - 0.8*inch, 6.4*inch, 1*inch, fill=True, stroke=False)
    c.setFillColor(colors.black)
    
    c.setFont("Helvetica-Bold", 9)
    headers = ["", "ESFERA", "CIL", "EJE", "ADD", "DIA", "B.C."]
    x_pos = [1*inch, 1.7*inch, 2.5*inch, 3.3*inch, 4.1*inch, 4.9*inch, 5.7*inch]
    for i, h in enumerate(headers):
        c.drawString(x_pos[i], y, h)
    
    y -= 0.35*inch
    c.setFont("Helvetica", 10)
    c.drawString(x_pos[0], y, "OD")
    c.drawString(x_pos[1], y, str(rx.get("od_power") or "-"))
    c.drawString(x_pos[2], y, str(rx.get("od_cylinder") or "-"))
    c.drawString(x_pos[3], y, str(rx.get("od_axis") or "-"))
    c.drawString(x_pos[4], y, str(rx.get("od_addition") or "-"))
    c.drawString(x_pos[5], y, str(rx.get("od_dia") or "-"))
    c.drawString(x_pos[6], y, str(rx.get("od_bc") or "-"))
    
    y -= 0.35*inch
    c.drawString(x_pos[0], y, "OI")
    c.drawString(x_pos[1], y, str(rx.get("oi_power") or "-"))
    c.drawString(x_pos[2], y, str(rx.get("oi_cylinder") or "-"))
    c.drawString(x_pos[3], y, str(rx.get("oi_axis") or "-"))
    c.drawString(x_pos[4], y, str(rx.get("oi_addition") or "-"))
    c.drawString(x_pos[5], y, str(rx.get("oi_dia") or "-"))
    c.drawString(x_pos[6], y, str(rx.get("oi_bc") or "-"))
    
    y -= 0.6*inch
    if rx.get("brand"):
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1*inch, y, "Marca:")
        c.setFont("Helvetica", 10)
        c.drawString(1.8*inch, y, rx["brand"])
    if rx.get("lens_type"):
        c.drawString(3.5*inch, y, f"Tipo: {rx['lens_type']}")
    y -= 0.25*inch
    if rx.get("replacement"):
        c.drawString(1*inch, y, f"Reemplazo: {rx['replacement']}")
    
    if rx.get("observations"):
        y -= 0.4*inch
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1*inch, y, "Observaciones:")
        c.setFont("Helvetica", 10)
        c.drawString(2.4*inch, y, rx["observations"][:80])
    
    y = 2*inch
    c.line(1*inch, y, 3*inch, y)
    c.setFont("Helvetica", 9)
    c.drawString(1*inch, y - 0.2*inch, rx.get("professional_name", ""))
    
    c.save()
    buffer.seek(0)
    
    return StreamingResponse(buffer, media_type="application/pdf",
                           headers={"Content-Disposition": f"attachment; filename=receta_contacto_{rx_id}.pdf"})

# ==================== PRESCRIPTIONS - MEDICAL ====================
@prescriptions_router.get("/medical")
async def list_medical_prescriptions(user: dict = Depends(get_current_user), patient_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    query = {"company_id": ObjectId(user["company_id"])}
    if patient_id:
        query["patient_id"] = ObjectId(patient_id)
    prescriptions = await db.medical_prescriptions.find(query).sort("created_at", -1).to_list(100)
    for rx in prescriptions:
        serialize_doc(rx)
        patient = await db.patients.find_one({"_id": ObjectId(rx["patient_id"])}, {"first_name": 1, "last_name": 1})
        if patient:
            rx["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
    return prescriptions

@prescriptions_router.post("/medical")
async def create_medical_prescription(data: MedicalPrescriptionCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    rx_doc = {
        "company_id": ObjectId(user["company_id"]), "patient_id": ObjectId(data.patient_id),
        "consultation_id": ObjectId(data.consultation_id) if data.consultation_id else None,
        "professional_name": data.professional_name or user["name"],
        "diagnosis": data.diagnosis, "medications": data.medications, "instructions": data.instructions,
        "created_at": datetime.now(timezone.utc).isoformat(), "created_by": ObjectId(user["_id"])
    }
    result = await db.medical_prescriptions.insert_one(rx_doc)
    return {"_id": str(result.inserted_id), "message": "Receta médica creada"}

@prescriptions_router.get("/medical/{rx_id}/pdf")
async def get_medical_prescription_pdf(rx_id: str, user: dict = Depends(get_current_user)):
    rx = await db.medical_prescriptions.find_one({"_id": ObjectId(rx_id)})
    if not rx or str(rx["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    
    patient = await db.patients.find_one({"_id": rx["patient_id"]})
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    draw_pdf_header(c, width, height, company, "RECETA MEDICA")
    
    c.setFont("Helvetica", 11)
    y = height - 2.2*inch
    c.drawString(1*inch, y, f"Paciente: {patient['first_name']} {patient['last_name']}" if patient else "")
    c.drawString(4.5*inch, y, f"Fecha: {rx['created_at'][:10]}")
    y -= 0.25*inch
    c.drawString(4.5*inch, y, f"Profesional: {rx.get('professional_name', '')}")
    
    if rx.get("diagnosis"):
        y -= 0.5*inch
        c.setFont("Helvetica-Bold", 11)
        c.drawString(1*inch, y, "Diagnóstico:")
        c.setFont("Helvetica", 11)
        c.drawString(2.2*inch, y, rx["diagnosis"][:70])
    
    y -= 0.5*inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(1*inch, y, "Medicamentos:")
    y -= 0.3*inch
    c.setFont("Helvetica", 10)
    for med in rx.get("medications", []):
        c.drawString(1.2*inch, y, f"• {med.get('name', '')}")
        c.drawString(3.5*inch, y, f"Dosis: {med.get('dosage', '')}")
        c.drawString(5*inch, y, f"Duración: {med.get('duration', '')}")
        y -= 0.25*inch
        if med.get("frequency"):
            c.drawString(1.4*inch, y, f"Frecuencia: {med['frequency']}")
            y -= 0.25*inch
    
    if rx.get("instructions"):
        y -= 0.3*inch
        c.setFont("Helvetica-Bold", 11)
        c.drawString(1*inch, y, "Indicaciones:")
        c.setFont("Helvetica", 10)
        y -= 0.25*inch
        c.drawString(1.2*inch, y, rx["instructions"][:100])
    
    y = 2*inch
    c.line(1*inch, y, 3*inch, y)
    c.setFont("Helvetica", 9)
    c.drawString(1*inch, y - 0.2*inch, rx.get("professional_name", ""))
    
    c.save()
    buffer.seek(0)
    
    return StreamingResponse(buffer, media_type="application/pdf",
                           headers={"Content-Disposition": f"attachment; filename=receta_medica_{rx_id}.pdf"})

# ==================== INVENTORY ROUTES ====================
@inventory_router.get("/products")
async def list_products(user: dict = Depends(get_current_user), category: Optional[str] = None, search: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"]), "is_active": {"$ne": False}}
    if category:
        query["category"] = category
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
            {"brand": {"$regex": search, "$options": "i"}}
        ]
    
    products = await db.products.find(query).to_list(500)
    for p in products:
        serialize_doc(p)
        # Get current stock
        branch_id = ObjectId(user["branch_id"]) if user.get("branch_id") else None
        stock_query = {"company_id": ObjectId(user["company_id"]), "product_id": ObjectId(p["_id"])}
        if branch_id:
            stock_query["branch_id"] = branch_id
        stock_item = await db.stock.find_one(stock_query)
        p["stock_actual"] = stock_item["quantity"] if stock_item else 0
    return products

@inventory_router.post("/products")
async def create_product(data: ProductCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Solo administradores pueden crear productos")
    
    product_doc = {
        "company_id": ObjectId(user["company_id"]),
        "name": data.name, "sku": data.sku, "category": data.category, "brand": data.brand,
        "description": data.description, "cost_price": data.cost_price, "sale_price": data.sale_price,
        "min_stock": data.min_stock, "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.products.insert_one(product_doc)
    return {"_id": str(result.inserted_id), "message": "Producto creado"}

@inventory_router.put("/products/{product_id}")
async def update_product(product_id: str, data: ProductUpdate, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Solo administradores pueden actualizar productos")
    product = await db.products.find_one({"_id": ObjectId(product_id)})
    if not product or str(product["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    await db.products.update_one({"_id": ObjectId(product_id)}, {"$set": update_data})
    return {"message": "Producto actualizado"}

@inventory_router.get("/stock")
async def get_stock(user: dict = Depends(get_current_user), branch_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    stock = await db.stock.find(query).to_list(1000)
    for s in stock:
        serialize_doc(s)
        product = await db.products.find_one({"_id": ObjectId(s["product_id"])}, {"name": 1, "sku": 1, "min_stock": 1, "sale_price": 1, "cost_price": 1})
        if product:
            s["product_name"] = product["name"]
            s["sku"] = product["sku"]
            s["min_stock"] = product.get("min_stock", 5)
            s["sale_price"] = product.get("sale_price", 0)
            s["cost_price"] = product.get("cost_price", 0)
    return stock

@inventory_router.post("/movement")
async def create_inventory_movement(data: InventoryMovement, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    # Verify product exists
    product = await db.products.find_one({"_id": ObjectId(data.product_id)})
    if not product or str(product["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    stock = await db.stock.find_one({
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(data.branch_id),
        "product_id": ObjectId(data.product_id)
    })
    
    quantity_change = data.quantity if data.type == "entrada" else -data.quantity
    
    if stock:
        new_quantity = stock["quantity"] + quantity_change
        if new_quantity < 0:
            raise HTTPException(status_code=400, detail="Stock insuficiente")
        await db.stock.update_one(
            {"_id": stock["_id"]},
            {"$set": {"quantity": new_quantity, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    else:
        if quantity_change < 0:
            raise HTTPException(status_code=400, detail="Stock insuficiente")
        await db.stock.insert_one({
            "company_id": ObjectId(user["company_id"]),
            "branch_id": ObjectId(data.branch_id),
            "product_id": ObjectId(data.product_id),
            "quantity": quantity_change,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Record movement history
    movement_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(data.branch_id),
        "product_id": ObjectId(data.product_id),
        "type": data.type,
        "quantity": data.quantity,
        "notes": data.notes,
        "reference": data.reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    await db.inventory_movements.insert_one(movement_doc)
    
    return {"message": "Movimiento registrado"}

@inventory_router.get("/movements")
async def list_inventory_movements(
    user: dict = Depends(get_current_user),
    product_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    limit: int = 100
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if product_id:
        query["product_id"] = ObjectId(product_id)
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    movements = await db.inventory_movements.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    for m in movements:
        serialize_doc(m)
        product = await db.products.find_one({"_id": ObjectId(m["product_id"])}, {"name": 1})
        if product:
            m["product_name"] = product["name"]
    return movements

@inventory_router.get("/alerts")
async def get_stock_alerts(user: dict = Depends(get_current_user), branch_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    stock_items = await db.stock.find(query).to_list(1000)
    alerts = []
    for s in stock_items:
        product = await db.products.find_one({"_id": s["product_id"]}, {"name": 1, "min_stock": 1, "sku": 1})
        if product and s["quantity"] <= product.get("min_stock", 5):
            alerts.append({
                "product_id": str(s["product_id"]),
                "product_name": product["name"],
                "sku": product.get("sku", ""),
                "current_stock": s["quantity"],
                "min_stock": product.get("min_stock", 5),
                "branch_id": str(s["branch_id"])
            })
    return alerts

# ==================== SALES ROUTES ====================
@sales_router.get("")
async def list_sales(
    user: dict = Depends(get_current_user),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[str] = None,
    limit: int = 100
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    if date_from and date_to:
        query["created_at"] = {"$gte": date_from, "$lte": date_to + "T23:59:59"}
    
    sales = await db.sales.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    for s in sales:
        serialize_doc(s)
        if s.get("patient_id"):
            patient = await db.patients.find_one({"_id": ObjectId(s["patient_id"])}, {"first_name": 1, "last_name": 1})
            if patient:
                s["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
        if s.get("created_by"):
            seller = await db.users.find_one({"_id": ObjectId(s["created_by"])}, {"name": 1})
            if seller:
                s["seller_name"] = seller["name"]
    return sales

@sales_router.post("")
async def create_sale(data: SaleCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    branch_id = ObjectId(user["branch_id"]) if user.get("branch_id") else None
    
    sale_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": branch_id,
        "patient_id": ObjectId(data.patient_id) if data.patient_id else None,
        "items": data.items,
        "subtotal": data.subtotal, "discount": data.discount, "tax": data.tax, "total": data.total,
        "payment_method": data.payment_method, "amount_paid": data.amount_paid,
        "balance": data.total - data.amount_paid,
        "status": "completada" if data.amount_paid >= data.total else "pendiente",
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    result = await db.sales.insert_one(sale_doc)
    
    # Update stock for each item
    for item in data.items:
        if item.get("product_id") and branch_id:
            await db.stock.update_one(
                {"product_id": ObjectId(item["product_id"]), "branch_id": branch_id},
                {"$inc": {"quantity": -item.get("quantity", 1)}}
            )
            # Record movement
            await db.inventory_movements.insert_one({
                "company_id": ObjectId(user["company_id"]),
                "branch_id": branch_id,
                "product_id": ObjectId(item["product_id"]),
                "type": "salida",
                "quantity": item.get("quantity", 1),
                "notes": f"Venta #{str(result.inserted_id)[-6:]}",
                "reference": str(result.inserted_id),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": ObjectId(user["_id"])
            })
    
    # Create finance entry for income
    finance_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": branch_id,
        "type": "ingreso",
        "category": "ventas",
        "amount": data.amount_paid,
        "description": f"Venta #{str(result.inserted_id)[-6:]}",
        "reference_id": result.inserted_id,
        "reference_type": "sale",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    await db.finance_entries.insert_one(finance_doc)
    
    return {"_id": str(result.inserted_id), "message": "Venta registrada"}

@sales_router.get("/{sale_id}")
async def get_sale(sale_id: str, user: dict = Depends(get_current_user)):
    sale = await db.sales.find_one({"_id": ObjectId(sale_id)})
    if not sale or str(sale["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    serialize_doc(sale)
    if sale.get("patient_id"):
        patient = await db.patients.find_one({"_id": ObjectId(sale["patient_id"])}, {"first_name": 1, "last_name": 1})
        if patient:
            sale["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
    return sale

@sales_router.post("/{sale_id}/payment")
async def add_payment(sale_id: str, amount: float = Query(...), user: dict = Depends(get_current_user)):
    sale = await db.sales.find_one({"_id": ObjectId(sale_id)})
    if not sale or str(sale["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    
    new_paid = sale.get("amount_paid", 0) + amount
    new_balance = sale["total"] - new_paid
    status = "completada" if new_balance <= 0 else "pendiente"
    
    await db.sales.update_one(
        {"_id": ObjectId(sale_id)},
        {"$set": {"amount_paid": new_paid, "balance": max(0, new_balance), "status": status}}
    )
    
    # Create finance entry
    finance_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": sale.get("branch_id"),
        "type": "ingreso",
        "category": "ventas",
        "amount": amount,
        "description": f"Abono venta #{sale_id[-6:]}",
        "reference_id": ObjectId(sale_id),
        "reference_type": "sale_payment",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    await db.finance_entries.insert_one(finance_doc)
    
    return {"message": "Pago registrado", "new_balance": max(0, new_balance)}

# ==================== QUOTATIONS ROUTES ====================
@quotations_router.get("")
async def list_quotations(
    user: dict = Depends(get_current_user),
    status: Optional[str] = None,
    patient_id: Optional[str] = None,
    limit: int = 100
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if status and status != "todas":
        query["status"] = status
    if patient_id:
        query["patient_id"] = ObjectId(patient_id)
    
    quotations = await db.quotations.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    for q in quotations:
        serialize_doc(q)
        if q.get("patient_id"):
            patient = await db.patients.find_one({"_id": ObjectId(q["patient_id"])}, {"first_name": 1, "last_name": 1, "phone": 1})
            if patient:
                q["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
                q["patient_phone"] = patient.get("phone", "")
        if q.get("created_by"):
            creator = await db.users.find_one({"_id": ObjectId(q["created_by"])}, {"name": 1})
            if creator:
                q["creator_name"] = creator["name"]
        # Check expiration
        if q["status"] == "pendiente":
            created = datetime.fromisoformat(q["created_at"].replace("Z", "+00:00")) if isinstance(q["created_at"], str) else q["created_at"]
            expiry = created + timedelta(days=q.get("validity_days", 15))
            if datetime.now(timezone.utc) > expiry:
                q["status"] = "vencida"
                await db.quotations.update_one({"_id": ObjectId(q["_id"])}, {"$set": {"status": "vencida"}})
    return quotations

@quotations_router.post("")
async def create_quotation(data: QuotationCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    branch_id = ObjectId(user["branch_id"]) if user.get("branch_id") else None
    
    # Generate quotation number
    count = await db.quotations.count_documents({"company_id": ObjectId(user["company_id"])})
    quotation_number = f"COT-{count + 1:04d}"
    
    now = datetime.now(timezone.utc)
    expiry_date = (now + timedelta(days=data.validity_days)).strftime("%Y-%m-%d")
    
    quotation_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": branch_id,
        "patient_id": ObjectId(data.patient_id),
        "quotation_number": quotation_number,
        "items": data.items,
        "subtotal": data.subtotal,
        "discount": data.discount,
        "discount_type": data.discount_type,
        "total": data.total,
        "notes": data.notes,
        "payment_conditions": data.payment_conditions,
        "validity_days": data.validity_days,
        "expiry_date": expiry_date,
        "status": "pendiente",
        "created_at": now.isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    result = await db.quotations.insert_one(quotation_doc)
    return {"_id": str(result.inserted_id), "quotation_number": quotation_number, "message": "Cotizacion creada"}

@quotations_router.get("/{quotation_id}")
async def get_quotation(quotation_id: str, user: dict = Depends(get_current_user)):
    q = await db.quotations.find_one({"_id": ObjectId(quotation_id)})
    if not q or str(q["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cotizacion no encontrada")
    serialize_doc(q)
    if q.get("patient_id"):
        patient = await db.patients.find_one({"_id": ObjectId(q["patient_id"])}, {"first_name": 1, "last_name": 1, "phone": 1, "email": 1, "whatsapp": 1})
        if patient:
            q["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
            q["patient_phone"] = patient.get("phone", "")
            q["patient_email"] = patient.get("email", "")
            q["patient_whatsapp"] = patient.get("whatsapp", "")
    return q

@quotations_router.put("/{quotation_id}/status")
async def update_quotation_status(quotation_id: str, data: QuotationStatusUpdate, user: dict = Depends(get_current_user)):
    q = await db.quotations.find_one({"_id": ObjectId(quotation_id)})
    if not q or str(q["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cotizacion no encontrada")
    
    if data.status not in ["aceptada", "rechazada", "vencida"]:
        raise HTTPException(status_code=400, detail="Estado invalido")
    
    await db.quotations.update_one(
        {"_id": ObjectId(quotation_id)},
        {"$set": {"status": data.status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": f"Cotizacion {data.status}"}

@quotations_router.post("/{quotation_id}/convert")
async def convert_quotation_to_sale(quotation_id: str, payment_method: str = "efectivo", amount_paid: float = 0, user: dict = Depends(get_current_user)):
    q = await db.quotations.find_one({"_id": ObjectId(quotation_id)})
    if not q or str(q["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cotizacion no encontrada")
    
    if q["status"] != "pendiente" and q["status"] != "aceptada":
        raise HTTPException(status_code=400, detail="Solo cotizaciones pendientes o aceptadas pueden convertirse en venta")
    
    branch_id = q.get("branch_id")
    
    sale_doc = {
        "company_id": q["company_id"],
        "branch_id": branch_id,
        "patient_id": q.get("patient_id"),
        "items": q["items"],
        "subtotal": q["subtotal"],
        "discount": q["discount"],
        "tax": 0,
        "total": q["total"],
        "payment_method": payment_method,
        "amount_paid": amount_paid if amount_paid > 0 else q["total"],
        "balance": q["total"] - (amount_paid if amount_paid > 0 else q["total"]),
        "status": "completada" if (amount_paid if amount_paid > 0 else q["total"]) >= q["total"] else "pendiente",
        "notes": f"Generada desde cotizacion {q.get('quotation_number', quotation_id[-6:])}",
        "quotation_id": ObjectId(quotation_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    sale_result = await db.sales.insert_one(sale_doc)
    
    # Update stock
    for item in q["items"]:
        if item.get("product_id") and branch_id:
            await db.stock.update_one(
                {"product_id": ObjectId(item["product_id"]), "branch_id": branch_id},
                {"$inc": {"quantity": -item.get("quantity", 1)}}
            )
            await db.inventory_movements.insert_one({
                "company_id": q["company_id"],
                "branch_id": branch_id,
                "product_id": ObjectId(item["product_id"]),
                "type": "salida",
                "quantity": item.get("quantity", 1),
                "notes": f"Venta desde cotizacion {q.get('quotation_number', '')}",
                "reference": str(sale_result.inserted_id),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": ObjectId(user["_id"])
            })
    
    # Create finance entry
    paid = amount_paid if amount_paid > 0 else q["total"]
    finance_doc = {
        "company_id": q["company_id"],
        "branch_id": branch_id,
        "type": "ingreso",
        "category": "ventas",
        "amount": paid,
        "description": f"Venta #{str(sale_result.inserted_id)[-6:]} (cotizacion {q.get('quotation_number', '')})",
        "reference_id": sale_result.inserted_id,
        "reference_type": "sale",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    await db.finance_entries.insert_one(finance_doc)
    
    # Mark quotation as converted
    await db.quotations.update_one(
        {"_id": ObjectId(quotation_id)},
        {"$set": {"status": "convertida", "sale_id": sale_result.inserted_id, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"_id": str(sale_result.inserted_id), "message": "Cotizacion convertida a venta exitosamente"}

@quotations_router.get("/{quotation_id}/pdf")
async def get_quotation_pdf(quotation_id: str, user: dict = Depends(get_current_user)):
    q = await db.quotations.find_one({"_id": ObjectId(quotation_id)})
    if not q or str(q["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cotizacion no encontrada")
    
    patient = await db.patients.find_one({"_id": q["patient_id"]})
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    draw_pdf_header(c, width, height, company, "COTIZACION")
    
    # Quotation info
    c.setFont("Helvetica-Bold", 11)
    y = height - 2.1*inch
    c.drawString(1*inch, y, f"No: {q.get('quotation_number', '')}")
    c.drawString(5*inch, y, f"Fecha: {q['created_at'][:10]}")
    y -= 0.25*inch
    c.setFont("Helvetica", 11)
    c.drawString(1*inch, y, f"Paciente: {patient['first_name']} {patient['last_name']}" if patient else "")
    c.drawString(5*inch, y, f"Vigencia: {q.get('expiry_date', '')}")
    y -= 0.2*inch
    if patient and patient.get("phone"):
        c.drawString(1*inch, y, f"Tel: {patient['phone']}")
    
    # Table header
    y -= 0.5*inch
    c.setFillColor(colors.HexColor("#0F4C3A"))
    c.rect(0.8*inch, y - 0.05*inch, 6.4*inch, 0.35*inch, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    col_x = [0.9*inch, 1.5*inch, 5*inch, 5.7*inch, 6.4*inch]
    c.drawString(col_x[0], y + 0.05*inch, "#")
    c.drawString(col_x[1], y + 0.05*inch, "DESCRIPCION")
    c.drawString(col_x[2], y + 0.05*inch, "CANT")
    c.drawString(col_x[3], y + 0.05*inch, "PRECIO")
    c.drawString(col_x[4], y + 0.05*inch, "TOTAL")
    
    # Table rows
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    y -= 0.4*inch
    for i, item in enumerate(q.get("items", []), 1):
        if y < 2.5*inch:
            break
        c.drawString(col_x[0], y, str(i))
        name = item.get("name", "Producto")
        c.drawString(col_x[1], y, name[:35])
        c.drawString(col_x[2], y, str(item.get("quantity", 1)))
        c.drawRightString(6.2*inch, y, f"Q{item.get('unit_price', 0):,.2f}")
        c.drawRightString(7.1*inch, y, f"Q{item.get('subtotal', 0):,.2f}")
        y -= 0.3*inch
        # Separator line
        c.setStrokeColor(colors.HexColor("#E2E8F0"))
        c.line(0.8*inch, y + 0.15*inch, 7.2*inch, y + 0.15*inch)
    
    # Totals
    y -= 0.2*inch
    c.setFont("Helvetica", 11)
    c.drawRightString(6.2*inch, y, "Subtotal:")
    c.drawRightString(7.1*inch, y, f"Q{q.get('subtotal', 0):,.2f}")
    
    if q.get("discount", 0) > 0:
        y -= 0.3*inch
        c.drawRightString(6.2*inch, y, "Descuento:")
        c.setFillColor(colors.HexColor("#DC2626"))
        c.drawRightString(7.1*inch, y, f"-Q{q.get('discount', 0):,.2f}")
        c.setFillColor(colors.black)
    
    y -= 0.35*inch
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(6.2*inch, y, "TOTAL:")
    c.drawRightString(7.1*inch, y, f"Q{q.get('total', 0):,.2f}")
    
    # Notes and conditions
    y -= 0.6*inch
    if q.get("notes"):
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1*inch, y, "Notas:")
        c.setFont("Helvetica", 10)
        y -= 0.2*inch
        for line in q["notes"][:200].split("\n"):
            c.drawString(1*inch, y, line[:80])
            y -= 0.2*inch
    
    if q.get("payment_conditions"):
        y -= 0.15*inch
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1*inch, y, "Condiciones de Pago:")
        c.setFont("Helvetica", 10)
        y -= 0.2*inch
        c.drawString(1*inch, y, q["payment_conditions"][:100])
    
    # Validity notice
    y -= 0.5*inch
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.HexColor("#64748B"))
    c.drawString(1*inch, y, f"* Esta cotizacion es valida por {q.get('validity_days', 15)} dias hasta el {q.get('expiry_date', '')}.")
    
    # Footer
    c.setFillColor(colors.HexColor("#0F4C3A"))
    c.rect(0, 0, width, 0.5*inch, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 8)
    c.drawCentredString(width/2, 0.2*inch, f"{company['name'] if company else 'Cortexia Optical'} - {company.get('phone', '') if company else ''}")
    
    c.save()
    buffer.seek(0)
    
    return StreamingResponse(buffer, media_type="application/pdf",
                           headers={"Content-Disposition": f"attachment; filename=cotizacion_{q.get('quotation_number', quotation_id)}.pdf"})

# ==================== CONSULTATIONS ROUTES ====================
@consultations_router.get("")
async def list_consultations(
    user: dict = Depends(get_current_user),
    patient_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if patient_id:
        query["patient_id"] = ObjectId(patient_id)
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    if date_from and date_to:
        query["consultation_date"] = {"$gte": date_from, "$lte": date_to}
    elif date_from:
        query["consultation_date"] = {"$gte": date_from}
    
    consultations = await db.optical_consultations.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    for c in consultations:
        serialize_doc(c)
        if c.get("patient_id"):
            patient = await db.patients.find_one({"_id": ObjectId(c["patient_id"])}, {"first_name": 1, "last_name": 1})
            if patient:
                c["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
        if c.get("professional_user_id"):
            prof = await db.users.find_one({"_id": ObjectId(c["professional_user_id"])}, {"name": 1})
            if prof:
                c["professional_name"] = prof["name"]
    return consultations

@consultations_router.post("")
async def create_consultation(data: ConsultationCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    branch_id = ObjectId(user["branch_id"]) if user.get("branch_id") else None
    now = datetime.now(timezone.utc)
    
    doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": branch_id,
        "patient_id": ObjectId(data.patient_id),
        "appointment_id": ObjectId(data.appointment_id) if data.appointment_id else None,
        "professional_user_id": ObjectId(user["_id"]),
        "consultation_date": data.consultation_date,
        "consultation_time": data.consultation_time or now.strftime("%H:%M"),
        "consultation_type": data.consultation_type,
        "chief_complaint": data.chief_complaint,
        "anamnesis": data.anamnesis or "",
        "findings": data.findings or "",
        "diagnosis": data.diagnosis or "",
        "treatment_plan": data.treatment_plan or "",
        "recommendations": data.recommendations or "",
        "notes": data.notes or "",
        # Historia Clinica
        "wears_glasses": data.wears_glasses,
        "glasses_since": data.glasses_since or "",
        "glasses_type": data.glasses_type or "",
        "ocular_surgeries": data.ocular_surgeries or "",
        "ocular_trauma": data.ocular_trauma or "",
        "ocular_diseases": data.ocular_diseases or "",
        "diabetes": data.diabetes,
        "hypertension": data.hypertension,
        "autoimmune_disease": data.autoimmune_disease,
        "autoimmune_details": data.autoimmune_details or "",
        "current_medications": data.current_medications or "",
        "allergies": data.allergies or "",
        "family_glaucoma": data.family_glaucoma,
        "family_glaucoma_relationship": data.family_glaucoma_relationship or "",
        "family_macular_degeneration": data.family_macular_degeneration,
        "family_macular_relationship": data.family_macular_relationship or "",
        "family_high_myopia": data.family_high_myopia,
        "family_high_myopia_relationship": data.family_high_myopia_relationship or "",
        "family_other_history": data.family_other_history or "",
        # Agudeza Visual
        "va_distance_without_rx_od": data.va_distance_without_rx_od or "",
        "va_distance_without_rx_oi": data.va_distance_without_rx_oi or "",
        "va_distance_with_rx_od": data.va_distance_with_rx_od or "",
        "va_distance_with_rx_oi": data.va_distance_with_rx_oi or "",
        "va_near_without_rx_od": data.va_near_without_rx_od or "",
        "va_near_without_rx_oi": data.va_near_without_rx_oi or "",
        "va_near_with_rx_od": data.va_near_with_rx_od or "",
        "va_near_with_rx_oi": data.va_near_with_rx_oi or "",
        "va_pinhole_od": data.va_pinhole_od or "",
        "va_pinhole_oi": data.va_pinhole_oi or "",
        "visual_acuity_method": data.visual_acuity_method or "",
        "created_by": ObjectId(user["_id"]),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    }
    result = await db.optical_consultations.insert_one(doc)
    return {"_id": str(result.inserted_id), "message": "Consulta registrada"}

@consultations_router.get("/{consultation_id}")
async def get_consultation(consultation_id: str, user: dict = Depends(get_current_user)):
    c = await db.optical_consultations.find_one({"_id": ObjectId(consultation_id)})
    if not c or str(c["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")
    serialize_doc(c)
    
    # Patient info
    if c.get("patient_id"):
        patient = await db.patients.find_one({"_id": ObjectId(c["patient_id"])}, {"first_name": 1, "last_name": 1, "phone": 1, "birth_date": 1, "gender": 1})
        if patient:
            c["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
            c["patient_phone"] = patient.get("phone", "")
            c["patient_birth_date"] = patient.get("birth_date", "")
            c["patient_gender"] = patient.get("gender", "")
    
    # Professional info
    if c.get("professional_user_id"):
        prof = await db.users.find_one({"_id": ObjectId(c["professional_user_id"])}, {"name": 1, "email": 1})
        if prof:
            c["professional_name"] = prof["name"]
    
    # Linked prescriptions
    eyeglass_rx = await db.eyeglass_prescriptions.find({"consultation_id": ObjectId(consultation_id)}).sort("created_at", -1).to_list(10)
    for rx in eyeglass_rx:
        serialize_doc(rx)
    c["eyeglass_prescriptions"] = eyeglass_rx
    
    contact_rx = await db.contact_lens_prescriptions.find({"consultation_id": ObjectId(consultation_id)}).sort("created_at", -1).to_list(10)
    for rx in contact_rx:
        serialize_doc(rx)
    c["contact_prescriptions"] = contact_rx
    
    medical_rx = await db.medical_prescriptions.find({"consultation_id": ObjectId(consultation_id)}).sort("created_at", -1).to_list(10)
    for rx in medical_rx:
        serialize_doc(rx)
    c["medical_prescriptions"] = medical_rx
    
    return c

@consultations_router.put("/{consultation_id}")
async def update_consultation(consultation_id: str, data: ConsultationUpdate, user: dict = Depends(get_current_user)):
    c = await db.optical_consultations.find_one({"_id": ObjectId(consultation_id)})
    if not c or str(c["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")
    
    update_data = {}
    all_fields = [
        "consultation_type", "chief_complaint", "anamnesis", "findings", "diagnosis",
        "treatment_plan", "recommendations", "notes",
        "wears_glasses", "glasses_since", "glasses_type", "ocular_surgeries", "ocular_trauma", "ocular_diseases",
        "diabetes", "hypertension", "autoimmune_disease", "autoimmune_details", "current_medications", "allergies",
        "family_glaucoma", "family_glaucoma_relationship", "family_macular_degeneration", "family_macular_relationship",
        "family_high_myopia", "family_high_myopia_relationship", "family_other_history",
        "va_distance_without_rx_od", "va_distance_without_rx_oi", "va_distance_with_rx_od", "va_distance_with_rx_oi",
        "va_near_without_rx_od", "va_near_without_rx_oi", "va_near_with_rx_od", "va_near_with_rx_oi",
        "va_pinhole_od", "va_pinhole_oi", "visual_acuity_method"
    ]
    for field in all_fields:
        val = getattr(data, field, None)
        if val is not None:
            update_data[field] = val
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.optical_consultations.update_one({"_id": ObjectId(consultation_id)}, {"$set": update_data})
    return {"message": "Consulta actualizada"}

# ==================== FINANCE ROUTES ====================
@finance_router.get("")
async def list_finance_entries(
    user: dict = Depends(get_current_user),
    type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[str] = None,
    category: Optional[str] = None
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if type:
        query["type"] = type
    if category:
        query["category"] = category
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    if date_from and date_to:
        query["date"] = {"$gte": date_from, "$lte": date_to}
    
    entries = await db.finance_entries.find(query).sort("date", -1).to_list(500)
    for e in entries:
        serialize_doc(e)
    return entries

@finance_router.post("")
async def create_finance_entry(data: FinanceEntryCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    entry_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(user["branch_id"]) if user.get("branch_id") else None,
        "type": data.type,
        "category": data.category,
        "amount": data.amount,
        "description": data.description,
        "date": data.date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "reference": data.reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    result = await db.finance_entries.insert_one(entry_doc)
    return {"_id": str(result.inserted_id), "message": "Entrada registrada"}

@finance_router.get("/summary")
async def get_finance_summary(
    user: dict = Depends(get_current_user),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[str] = None
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    if date_from and date_to:
        query["date"] = {"$gte": date_from, "$lte": date_to}
    else:
        query["date"] = {"$gte": month_start, "$lte": today}
    
    entries = await db.finance_entries.find(query).to_list(1000)
    
    income = sum(e["amount"] for e in entries if e["type"] == "ingreso")
    expense = sum(e["amount"] for e in entries if e["type"] == "egreso")
    
    # Group by category
    income_by_category = {}
    expense_by_category = {}
    for e in entries:
        if e["type"] == "ingreso":
            income_by_category[e["category"]] = income_by_category.get(e["category"], 0) + e["amount"]
        else:
            expense_by_category[e["category"]] = expense_by_category.get(e["category"], 0) + e["amount"]
    
    return {
        "income": income,
        "expense": expense,
        "profit": income - expense,
        "income_by_category": income_by_category,
        "expense_by_category": expense_by_category,
        "period": {"from": date_from or month_start, "to": date_to or today}
    }

@finance_router.get("/dashboard")
async def get_finance_dashboard(user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    
    query = {"company_id": ObjectId(user["company_id"]), "date": {"$gte": month_start, "$lte": today}}
    if user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    entries = await db.finance_entries.find(query).to_list(1000)
    
    income = sum(e["amount"] for e in entries if e["type"] == "ingreso")
    expense = sum(e["amount"] for e in entries if e["type"] == "egreso")
    
    # Today's data
    today_query = {**query, "date": today}
    today_entries = await db.finance_entries.find(today_query).to_list(100)
    today_income = sum(e["amount"] for e in today_entries if e["type"] == "ingreso")
    today_expense = sum(e["amount"] for e in today_entries if e["type"] == "egreso")
    
    return {
        "month": {
            "income": income,
            "expense": expense,
            "profit": income - expense
        },
        "today": {
            "income": today_income,
            "expense": today_expense,
            "profit": today_income - today_expense
        }
    }

# ==================== REPORTS / DASHBOARD ====================
@reports_router.get("/dashboard")
async def get_dashboard(user: dict = Depends(get_current_user), branch_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    
    company_id = ObjectId(user["company_id"])
    branch_filter = {}
    if branch_id:
        branch_filter["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        branch_filter["branch_id"] = ObjectId(user["branch_id"])
    
    # Citas del día
    apt_query = {"company_id": company_id, "date": today, **branch_filter}
    appointments_today = await db.appointments.count_documents(apt_query)
    appointments_pending = await db.appointments.count_documents({**apt_query, "status": "pendiente"})
    
    # Pacientes nuevos del mes
    patients_query = {"company_id": company_id, "created_at": {"$gte": month_start}}
    new_patients = await db.patients.count_documents(patients_query)
    
    # Ventas del día
    sales_today_query = {"company_id": company_id, "created_at": {"$gte": today}, **branch_filter}
    sales_today = await db.sales.find(sales_today_query).to_list(100)
    total_sales_today = sum(s.get("total", 0) for s in sales_today)
    sales_count_today = len(sales_today)
    
    # Ventas del mes
    sales_month_query = {"company_id": company_id, "created_at": {"$gte": month_start}, **branch_filter}
    sales_month = await db.sales.find(sales_month_query).to_list(1000)
    total_sales_month = sum(s.get("total", 0) for s in sales_month)
    
    # Finanzas del mes
    finance_query = {"company_id": company_id, "date": {"$gte": month_start, "$lte": today}, **branch_filter}
    finance_entries = await db.finance_entries.find(finance_query).to_list(1000)
    income = sum(e["amount"] for e in finance_entries if e["type"] == "ingreso")
    expense = sum(e["amount"] for e in finance_entries if e["type"] == "egreso")
    
    # Alertas de inventario
    stock_alerts = await get_stock_alerts_count(company_id, branch_filter.get("branch_id"))
    
    # Próximas citas
    upcoming_apts = await db.appointments.find({
        "company_id": company_id, "date": {"$gte": today}, "status": {"$in": ["pendiente", "confirmada"]},
        **branch_filter
    }).sort([("date", 1), ("time", 1)]).limit(5).to_list(5)
    
    for apt in upcoming_apts:
        serialize_doc(apt)
        patient = await db.patients.find_one({"_id": ObjectId(apt["patient_id"])}, {"first_name": 1, "last_name": 1})
        if patient:
            apt["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
    
    return {
        "appointments_today": appointments_today,
        "appointments_pending": appointments_pending,
        "new_patients": new_patients,
        "sales_count_today": sales_count_today,
        "total_sales_today": total_sales_today,
        "total_sales_month": total_sales_month,
        "income": income,
        "expense": expense,
        "profit": income - expense,
        "stock_alerts": stock_alerts,
        "upcoming_appointments": upcoming_apts
    }

async def get_stock_alerts_count(company_id, branch_id=None):
    query = {"company_id": company_id}
    if branch_id:
        query["branch_id"] = branch_id
    
    stock_items = await db.stock.find(query).to_list(1000)
    count = 0
    for s in stock_items:
        product = await db.products.find_one({"_id": s["product_id"]}, {"min_stock": 1})
        if product and s["quantity"] <= product.get("min_stock", 5):
            count += 1
    return count

@reports_router.get("/sales")
async def get_sales_report(
    user: dict = Depends(get_current_user),
    date_from: str = None,
    date_to: str = None,
    branch_id: Optional[str] = None
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    if date_from and date_to:
        query["created_at"] = {"$gte": date_from, "$lte": date_to + "T23:59:59"}
    else:
        query["created_at"] = {"$gte": month_start, "$lte": today + "T23:59:59"}
    
    sales = await db.sales.find(query).to_list(1000)
    
    total = sum(s.get("total", 0) for s in sales)
    count = len(sales)
    by_payment = {}
    for s in sales:
        pm = s.get("payment_method", "otro")
        by_payment[pm] = by_payment.get(pm, 0) + s.get("total", 0)
    
    return {
        "total": total,
        "count": count,
        "average": total / count if count > 0 else 0,
        "by_payment_method": by_payment,
        "period": {"from": date_from or month_start, "to": date_to or today}
    }

# ==================== USERS ROUTES ====================
@users_router.get("")
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

@users_router.post("")
async def create_user(data: UserCreate, user: dict = Depends(get_current_user), company_id: Optional[str] = None):
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
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

@users_router.put("/{user_id}")
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

@users_router.delete("/{user_id}")
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

# ==================== INCLUDE ROUTERS ====================
api_router.include_router(auth_router)
api_router.include_router(companies_router)
api_router.include_router(branches_router)
api_router.include_router(patients_router)
api_router.include_router(appointments_router)
api_router.include_router(prescriptions_router)
api_router.include_router(inventory_router)
api_router.include_router(sales_router)
api_router.include_router(quotations_router)
api_router.include_router(consultations_router)
api_router.include_router(finance_router)
api_router.include_router(reports_router)
api_router.include_router(users_router)

@api_router.get("/search")
async def global_search(q: str = Query(..., min_length=2), user: dict = Depends(get_current_user)):
    company_id = ObjectId(user["company_id"])
    regex = {"$regex": q, "$options": "i"}
    results = []
    # Search patients
    patients = await db.patients.find(
        {"company_id": company_id, "$or": [{"first_name": regex}, {"last_name": regex}, {"phone": regex}, {"dpi": regex}]},
        {"_id": 1, "first_name": 1, "last_name": 1, "phone": 1}
    ).limit(5).to_list(5)
    for p in patients:
        results.append({"type": "patient", "id": str(p["_id"]), "title": f"{p.get('first_name','')} {p.get('last_name','')}", "subtitle": p.get("phone", "")})
    # Search products
    products = await db.products.find(
        {"company_id": company_id, "$or": [{"name": regex}, {"sku": regex}]},
        {"_id": 1, "name": 1, "sku": 1, "price": 1}
    ).limit(5).to_list(5)
    for p in products:
        results.append({"type": "product", "id": str(p["_id"]), "title": p["name"], "subtitle": f"SKU: {p.get('sku','')} | Q{p.get('price',0):.2f}"})
    # Search consultations
    cons = await db.optical_consultations.find(
        {"company_id": company_id, "$or": [{"chief_complaint": regex}, {"diagnosis": regex}]},
        {"_id": 1, "chief_complaint": 1, "consultation_date": 1, "patient_id": 1}
    ).limit(5).to_list(5)
    for c in cons:
        patient = await db.patients.find_one({"_id": c.get("patient_id")}, {"first_name": 1, "last_name": 1})
        pname = f"{patient['first_name']} {patient['last_name']}" if patient else ""
        results.append({"type": "consultation", "id": str(c["_id"]), "title": c.get("chief_complaint", "")[:60], "subtitle": f"{pname} | {c.get('consultation_date','')}"})
    return results

app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== STARTUP ====================
@app.on_event("startup")
async def startup():
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.patients.create_index([("company_id", 1), ("last_name", 1)])
    await db.patients.create_index([("company_id", 1), ("phone", 1)])
    await db.appointments.create_index([("company_id", 1), ("date", 1)])
    await db.stock.create_index([("company_id", 1), ("branch_id", 1), ("product_id", 1)], unique=True)
    await db.inventory_movements.create_index([("company_id", 1), ("created_at", -1)])
    await db.sales.create_index([("company_id", 1), ("created_at", -1)])
    await db.finance_entries.create_index([("company_id", 1), ("date", -1)])
    await db.quotations.create_index([("company_id", 1), ("created_at", -1)])
    await db.quotations.create_index([("company_id", 1), ("status", 1)])
    await db.optical_consultations.create_index([("company_id", 1), ("patient_id", 1)])
    await db.optical_consultations.create_index([("company_id", 1), ("created_at", -1)])
    
    # Seed superadmin
    admin_email = os.environ.get("ADMIN_EMAIL", "superadmin@cortexia.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin123!")
    existing = await db.users.find_one({"email": admin_email})
    if existing:
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password), "role": "superadmin"}}
        )
        logger.info(f"SuperAdmin password reset: {admin_email}")
    else:
        await db.users.insert_one({
            "email": admin_email, "password_hash": hash_password(admin_password),
            "name": "Super Administrador", "role": "superadmin",
            "company_id": None, "branch_id": None, "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"SuperAdmin created: {admin_email}")
    
    # Seed demo company
    demo_company = await db.companies.find_one({"name": "Cortexia Optical Demo"})
    if not demo_company:
        company_result = await db.companies.insert_one({
            "name": "Cortexia Optical Demo", "legal_name": "Cortexia Optical S.A.",
            "tax_id": "12345678-9", "address": "6ta Avenida 12-34, Zona 1, Ciudad de Guatemala",
            "phone": "+502 2234-5678", "email": "info@cortexia.gt",
            "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
        })
        company_id = company_result.inserted_id
        
        # Create admin
        await db.users.insert_one({
            "email": "admin@cortexia.gt", "password_hash": hash_password("Demo123!"),
            "name": "Dr. Carlos Mendoza", "role": "admin", "company_id": company_id,
            "branch_id": None, "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Create branch
        branch_result = await db.branches.insert_one({
            "company_id": company_id, "name": "Sede Central - Zona 1",
            "address": "6ta Avenida 12-34, Zona 1", "phone": "+502 2234-5678",
            "email": "central@cortexia.gt", "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        branch_id = branch_result.inserted_id
        
        # Create user
        await db.users.insert_one({
            "email": "vendedor@cortexia.gt", "password_hash": hash_password("Demo123!"),
            "name": "María López", "role": "user", "company_id": company_id,
            "branch_id": branch_id, "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Create patients
        patients_data = [
            {"first_name": "Juan", "last_name": "Pérez García", "phone": "+502 5555-1234", "whatsapp": "+502 5555-1234", "dpi": "1234567890101", "gender": "M", "birth_date": "1985-03-15", "city": "Guatemala", "country": "Guatemala"},
            {"first_name": "Ana", "last_name": "Martínez Ruiz", "phone": "+502 5555-2345", "whatsapp": "+502 5555-2345", "dpi": "2345678901212", "gender": "F", "birth_date": "1990-07-22", "city": "Mixco", "country": "Guatemala"},
            {"first_name": "Roberto", "last_name": "González López", "phone": "+502 5555-3456", "whatsapp": "+502 5555-3456", "dpi": "3456789012323", "gender": "M", "birth_date": "1978-11-08", "city": "Villa Nueva", "country": "Guatemala"},
            {"first_name": "Sofía", "last_name": "Hernández Cruz", "phone": "+502 5555-4567", "whatsapp": "+502 5555-4567", "dpi": "4567890123434", "gender": "F", "birth_date": "1995-01-30", "city": "Guatemala", "country": "Guatemala"},
            {"first_name": "Luis", "last_name": "Ramírez Morales", "phone": "+502 5555-5678", "whatsapp": "+502 5555-5678", "dpi": "5678901234545", "gender": "M", "birth_date": "1982-09-12", "city": "Petapa", "country": "Guatemala"}
        ]
        
        patient_ids = []
        for p in patients_data:
            result = await db.patients.insert_one({
                **p, "company_id": company_id, "branch_id": branch_id,
                "address": "Ciudad de Guatemala", "email": f"{p['first_name'].lower()}@email.com",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            patient_ids.append(result.inserted_id)
        
        # Create products
        products_data = [
            {"name": "Armazón Ray-Ban RB5154", "sku": "ARZ-RB5154", "category": "armazones", "brand": "Ray-Ban", "cost_price": 450, "sale_price": 850, "min_stock": 3},
            {"name": "Armazón Oakley OX8046", "sku": "ARZ-OX8046", "category": "armazones", "brand": "Oakley", "cost_price": 380, "sale_price": 720, "min_stock": 3},
            {"name": "Lente Progresivo Essilor", "sku": "LNT-PROG-ESS", "category": "lentes", "brand": "Essilor", "cost_price": 600, "sale_price": 1200, "min_stock": 5},
            {"name": "Lente Bifocal Zeiss", "sku": "LNT-BIF-ZEI", "category": "lentes", "brand": "Zeiss", "cost_price": 450, "sale_price": 900, "min_stock": 5},
            {"name": "Lente de Contacto Acuvue Oasys", "sku": "LC-ACUVUE", "category": "contactos", "brand": "Acuvue", "cost_price": 180, "sale_price": 350, "min_stock": 10},
            {"name": "Solución ReNu 360ml", "sku": "SOL-360", "category": "accesorios", "brand": "ReNu", "cost_price": 45, "sale_price": 95, "min_stock": 8},
            {"name": "Estuche Premium para Anteojos", "sku": "EST-PREM", "category": "accesorios", "brand": "Generic", "cost_price": 25, "sale_price": 65, "min_stock": 10}
        ]
        
        for pr in products_data:
            result = await db.products.insert_one({
                **pr, "company_id": company_id, "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            # Add stock
            await db.stock.insert_one({
                "company_id": company_id, "branch_id": branch_id,
                "product_id": result.inserted_id, "quantity": 15,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        
        # Create appointments
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for i, pid in enumerate(patient_ids[:3]):
            await db.appointments.insert_one({
                "company_id": company_id, "branch_id": branch_id, "patient_id": pid,
                "date": today, "time": f"{9 + i}:00", "duration": 30,
                "type": "consulta", "status": "pendiente", "professional_name": "Dr. Carlos Mendoza",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        
        # Create prescription
        await db.eyeglass_prescriptions.insert_one({
            "company_id": company_id, "patient_id": patient_ids[0],
            "professional_name": "Dr. Carlos Mendoza",
            "od_sphere": -2.50, "od_cylinder": -0.75, "od_axis": 90, "od_dp": 32,
            "oi_sphere": -2.25, "oi_cylinder": -0.50, "oi_axis": 85, "oi_dp": 32,
            "observations": "Miopía con astigmatismo leve", "lens_type": "Monofocal",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info("Demo data seeded successfully")
    
    # Write test credentials
    Path("/app/memory").mkdir(parents=True, exist_ok=True)
    with open("/app/memory/test_credentials.md", "w") as f:
        f.write("""# Test Credentials - Cortexia Optical

## SuperAdmin
- Email: superadmin@cortexia.com
- Password: Admin123!

## Demo Company Admin
- Email: admin@cortexia.gt
- Password: Demo123!

## Demo User
- Email: vendedor@cortexia.gt
- Password: Demo123!
""")

@app.on_event("shutdown")
async def shutdown():
    client.close()
