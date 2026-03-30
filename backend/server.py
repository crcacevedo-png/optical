from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, Query
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
import bcrypt
import jwt
import secrets
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Config
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 7

def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]

# Password hashing
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# JWT Token Management
def create_access_token(user_id: str, email: str, role: str, company_id: str = None) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "company_id": company_id,
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

# Auth helper
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

# Pydantic Models
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class CompanyCreate(BaseModel):
    name: str
    legal_name: str
    tax_id: str
    address: str
    phone: str
    email: EmailStr
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
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    notes: Optional[str] = None

class AppointmentCreate(BaseModel):
    patient_id: str
    branch_id: Optional[str] = None
    professional_id: Optional[str] = None
    date: str
    time: str
    duration: int = 30
    type: str
    notes: Optional[str] = None

class AppointmentUpdate(BaseModel):
    status: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    notes: Optional[str] = None

class EyeglassPrescriptionCreate(BaseModel):
    patient_id: str
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
    diagnosis: Optional[str] = None
    medications: List[dict]
    instructions: Optional[str] = None

class ProductCreate(BaseModel):
    name: str
    sku: str
    category: str
    brand: Optional[str] = None
    description: Optional[str] = None
    cost_price: float
    sale_price: float
    min_stock: int = 5

class InventoryMovement(BaseModel):
    product_id: str
    branch_id: str
    type: str
    quantity: int
    notes: Optional[str] = None

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
    type: str
    category: str
    amount: float
    description: str
    date: Optional[str] = None
    reference: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str
    branch_id: Optional[str] = None

# Create the main app
app = FastAPI(title="Ópticas SaaS API")

# Create routers
api_router = APIRouter(prefix="/api")
auth_router = APIRouter(prefix="/auth", tags=["Autenticación"])
companies_router = APIRouter(prefix="/companies", tags=["Empresas"])
branches_router = APIRouter(prefix="/branches", tags=["Sucursales"])
patients_router = APIRouter(prefix="/patients", tags=["Pacientes"])
appointments_router = APIRouter(prefix="/appointments", tags=["Agenda"])
prescriptions_router = APIRouter(prefix="/prescriptions", tags=["Recetas"])
inventory_router = APIRouter(prefix="/inventory", tags=["Inventario"])
sales_router = APIRouter(prefix="/sales", tags=["Ventas"])
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
        "email": email,
        "password_hash": hash_password(data.password),
        "name": data.name,
        "role": "user",
        "company_id": None,
        "branch_id": None,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    access_token = create_access_token(user_id, email, "user")
    refresh_token = create_refresh_token(user_id)
    
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=86400, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")
    
    return {"_id": user_id, "email": email, "name": data.name, "role": "user"}

@auth_router.post("/login")
async def login(data: UserLogin, response: Response, request: Request):
    email = data.email.lower()
    
    # Check brute force
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
    
    # Clear attempts on success
    await db.login_attempts.delete_one({"identifier": identifier})
    
    user_id = str(user["_id"])
    company_id = str(user["company_id"]) if user.get("company_id") else None
    access_token = create_access_token(user_id, email, user["role"], company_id)
    refresh_token = create_refresh_token(user_id)
    
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=86400, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")
    
    return {
        "_id": user_id,
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "company_id": company_id,
        "branch_id": str(user["branch_id"]) if user.get("branch_id") else None
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
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
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
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=86400, path="/")
        return {"message": "Token renovado"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

# ==================== COMPANIES ROUTES (SuperAdmin) ====================
@companies_router.get("")
async def list_companies(user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    companies = await db.companies.find({}, {"_id": 1, "name": 1, "legal_name": 1, "email": 1, "is_active": 1, "created_at": 1}).to_list(1000)
    for c in companies:
        c["_id"] = str(c["_id"])
    return companies

@companies_router.post("")
async def create_company(data: CompanyCreate, user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    company_doc = {
        "name": data.name,
        "legal_name": data.legal_name,
        "tax_id": data.tax_id,
        "address": data.address,
        "phone": data.phone,
        "email": data.email.lower(),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.companies.insert_one(company_doc)
    company_id = result.inserted_id
    
    # Create admin user for this company
    admin_doc = {
        "email": data.admin_email.lower(),
        "password_hash": hash_password(data.admin_password),
        "name": data.admin_name,
        "role": "admin",
        "company_id": company_id,
        "branch_id": None,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
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

# ==================== BRANCHES ROUTES ====================
@branches_router.get("")
async def list_branches(user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin no tiene sucursales")
    query = {"company_id": ObjectId(user["company_id"])}
    branches = await db.branches.find(query, {"_id": 1, "name": 1, "address": 1, "phone": 1, "is_active": 1}).to_list(100)
    for b in branches:
        b["_id"] = str(b["_id"])
        b["company_id"] = str(b.get("company_id", ""))
    return branches

@branches_router.post("")
async def create_branch(data: BranchCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    if not user.get("company_id"):
        raise HTTPException(status_code=400, detail="No tiene empresa asignada")
    
    branch_doc = {
        "company_id": ObjectId(user["company_id"]),
        "name": data.name,
        "address": data.address,
        "phone": data.phone,
        "email": data.email.lower() if data.email else None,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
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
            {"dpi": {"$regex": search, "$options": "i"}}
        ]
    
    patients = await db.patients.find(query, {"_id": 1, "first_name": 1, "last_name": 1, "phone": 1, "email": 1, "created_at": 1}).skip(skip).limit(limit).to_list(limit)
    for p in patients:
        p["_id"] = str(p["_id"])
    
    total = await db.patients.count_documents(query)
    return {"patients": patients, "total": total}

@patients_router.post("")
async def create_patient(data: PatientCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin no puede crear pacientes")
    
    patient_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(user["branch_id"]) if user.get("branch_id") else None,
        "first_name": data.first_name,
        "last_name": data.last_name,
        "dpi": data.dpi,
        "birth_date": data.birth_date,
        "gender": data.gender,
        "phone": data.phone,
        "email": data.email.lower() if data.email else None,
        "address": data.address,
        "emergency_contact": data.emergency_contact,
        "emergency_phone": data.emergency_phone,
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
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
    
    patient["_id"] = str(patient["_id"])
    patient["company_id"] = str(patient["company_id"])
    if patient.get("branch_id"):
        patient["branch_id"] = str(patient["branch_id"])
    if patient.get("created_by"):
        patient["created_by"] = str(patient["created_by"])
    
    # Get prescriptions
    eyeglass_rx = await db.eyeglass_prescriptions.find({"patient_id": ObjectId(patient_id)}).sort("created_at", -1).to_list(10)
    for rx in eyeglass_rx:
        rx["_id"] = str(rx["_id"])
        rx["patient_id"] = str(rx["patient_id"])
        rx["company_id"] = str(rx["company_id"])
    patient["eyeglass_prescriptions"] = eyeglass_rx
    
    medical_rx = await db.medical_prescriptions.find({"patient_id": ObjectId(patient_id)}).sort("created_at", -1).to_list(10)
    for rx in medical_rx:
        rx["_id"] = str(rx["_id"])
        rx["patient_id"] = str(rx["patient_id"])
        rx["company_id"] = str(rx["company_id"])
    patient["medical_prescriptions"] = medical_rx
    
    # Get appointments
    appointments = await db.appointments.find({"patient_id": ObjectId(patient_id)}).sort("date", -1).to_list(20)
    for apt in appointments:
        apt["_id"] = str(apt["_id"])
        apt["patient_id"] = str(apt["patient_id"])
        apt["company_id"] = str(apt["company_id"])
    patient["appointments"] = appointments
    
    # Get sales
    sales = await db.sales.find({"patient_id": ObjectId(patient_id)}).sort("created_at", -1).to_list(20)
    for s in sales:
        s["_id"] = str(s["_id"])
        if s.get("patient_id"):
            s["patient_id"] = str(s["patient_id"])
        s["company_id"] = str(s["company_id"])
    patient["sales"] = sales
    
    return patient

@patients_router.put("/{patient_id}")
async def update_patient(patient_id: str, data: PatientCreate, user: dict = Depends(get_current_user)):
    patient = await db.patients.find_one({"_id": ObjectId(patient_id)})
    if not patient or str(patient["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    update_data = data.model_dump(exclude_unset=True)
    await db.patients.update_one({"_id": ObjectId(patient_id)}, {"$set": update_data})
    return {"message": "Paciente actualizado"}

# ==================== APPOINTMENTS ROUTES ====================
@appointments_router.get("")
async def list_appointments(
    user: dict = Depends(get_current_user),
    date: Optional[str] = None,
    status: Optional[str] = None,
    branch_id: Optional[str] = None
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin no puede ver citas")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if date:
        query["date"] = date
    if status:
        query["status"] = status
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    appointments = await db.appointments.find(query).sort([("date", 1), ("time", 1)]).to_list(200)
    for apt in appointments:
        apt["_id"] = str(apt["_id"])
        apt["patient_id"] = str(apt["patient_id"])
        apt["company_id"] = str(apt["company_id"])
        if apt.get("branch_id"):
            apt["branch_id"] = str(apt["branch_id"])
        # Get patient name
        patient = await db.patients.find_one({"_id": ObjectId(apt["patient_id"])}, {"first_name": 1, "last_name": 1})
        if patient:
            apt["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
    
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
        "date": data.date,
        "time": data.time,
        "duration": data.duration,
        "type": data.type,
        "status": "scheduled",
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    result = await db.appointments.insert_one(apt_doc)
    return {"_id": str(result.inserted_id), "message": "Cita creada"}

@appointments_router.put("/{appointment_id}")
async def update_appointment(appointment_id: str, data: AppointmentUpdate, user: dict = Depends(get_current_user)):
    apt = await db.appointments.find_one({"_id": ObjectId(appointment_id)})
    if not apt or str(apt["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    await db.appointments.update_one({"_id": ObjectId(appointment_id)}, {"$set": update_data})
    return {"message": "Cita actualizada"}

@appointments_router.delete("/{appointment_id}")
async def cancel_appointment(appointment_id: str, user: dict = Depends(get_current_user)):
    apt = await db.appointments.find_one({"_id": ObjectId(appointment_id)})
    if not apt or str(apt["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    await db.appointments.update_one({"_id": ObjectId(appointment_id)}, {"$set": {"status": "cancelled"}})
    return {"message": "Cita cancelada"}

# ==================== PRESCRIPTIONS ROUTES ====================
@prescriptions_router.get("/eyeglass")
async def list_eyeglass_prescriptions(user: dict = Depends(get_current_user), patient_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    query = {"company_id": ObjectId(user["company_id"])}
    if patient_id:
        query["patient_id"] = ObjectId(patient_id)
    prescriptions = await db.eyeglass_prescriptions.find(query).sort("created_at", -1).to_list(100)
    for rx in prescriptions:
        rx["_id"] = str(rx["_id"])
        rx["patient_id"] = str(rx["patient_id"])
        rx["company_id"] = str(rx["company_id"])
        patient = await db.patients.find_one({"_id": ObjectId(rx["patient_id"])}, {"first_name": 1, "last_name": 1})
        if patient:
            rx["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
    return prescriptions

@prescriptions_router.post("/eyeglass")
async def create_eyeglass_prescription(data: EyeglassPrescriptionCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    rx_doc = {
        "company_id": ObjectId(user["company_id"]),
        "patient_id": ObjectId(data.patient_id),
        "od_sphere": data.od_sphere,
        "od_cylinder": data.od_cylinder,
        "od_axis": data.od_axis,
        "od_addition": data.od_addition,
        "od_dp": data.od_dp,
        "oi_sphere": data.oi_sphere,
        "oi_cylinder": data.oi_cylinder,
        "oi_axis": data.oi_axis,
        "oi_addition": data.oi_addition,
        "oi_dp": data.oi_dp,
        "observations": data.observations,
        "lens_type": data.lens_type,
        "frame_type": data.frame_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    result = await db.eyeglass_prescriptions.insert_one(rx_doc)
    return {"_id": str(result.inserted_id), "message": "Receta creada"}

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
    
    # Header
    c.setFont("Helvetica-Bold", 18)
    c.drawString(1*inch, height - 1*inch, company["name"] if company else "Óptica")
    c.setFont("Helvetica", 10)
    c.drawString(1*inch, height - 1.3*inch, company.get("address", "") if company else "")
    c.drawString(1*inch, height - 1.5*inch, f"Tel: {company.get('phone', '')}" if company else "")
    
    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, height - 2*inch, "RECETA DE ANTEOJOS")
    
    # Patient info
    c.setFont("Helvetica", 11)
    c.drawString(1*inch, height - 2.5*inch, f"Paciente: {patient['first_name']} {patient['last_name']}" if patient else "")
    c.drawString(1*inch, height - 2.7*inch, f"Fecha: {rx['created_at'][:10]}")
    
    # Prescription table
    y = height - 3.2*inch
    c.setFont("Helvetica-Bold", 10)
    c.drawString(1.5*inch, y, "OJO")
    c.drawString(2.5*inch, y, "ESFERA")
    c.drawString(3.5*inch, y, "CILINDRO")
    c.drawString(4.5*inch, y, "EJE")
    c.drawString(5.5*inch, y, "ADICIÓN")
    c.drawString(6.5*inch, y, "D.P.")
    
    y -= 0.3*inch
    c.setFont("Helvetica", 10)
    c.drawString(1.5*inch, y, "OD")
    c.drawString(2.5*inch, y, str(rx.get("od_sphere", "-") or "-"))
    c.drawString(3.5*inch, y, str(rx.get("od_cylinder", "-") or "-"))
    c.drawString(4.5*inch, y, str(rx.get("od_axis", "-") or "-"))
    c.drawString(5.5*inch, y, str(rx.get("od_addition", "-") or "-"))
    c.drawString(6.5*inch, y, str(rx.get("od_dp", "-") or "-"))
    
    y -= 0.3*inch
    c.drawString(1.5*inch, y, "OI")
    c.drawString(2.5*inch, y, str(rx.get("oi_sphere", "-") or "-"))
    c.drawString(3.5*inch, y, str(rx.get("oi_cylinder", "-") or "-"))
    c.drawString(4.5*inch, y, str(rx.get("oi_axis", "-") or "-"))
    c.drawString(5.5*inch, y, str(rx.get("oi_addition", "-") or "-"))
    c.drawString(6.5*inch, y, str(rx.get("oi_dp", "-") or "-"))
    
    # Observations
    if rx.get("observations"):
        y -= 0.6*inch
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1*inch, y, "Observaciones:")
        c.setFont("Helvetica", 10)
        c.drawString(1*inch, y - 0.2*inch, rx["observations"][:100])
    
    # Lens type
    if rx.get("lens_type"):
        y -= 0.6*inch
        c.drawString(1*inch, y, f"Tipo de lente: {rx['lens_type']}")
    
    c.save()
    buffer.seek(0)
    
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=receta_anteojos_{rx_id}.pdf"})

@prescriptions_router.get("/medical")
async def list_medical_prescriptions(user: dict = Depends(get_current_user), patient_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    query = {"company_id": ObjectId(user["company_id"])}
    if patient_id:
        query["patient_id"] = ObjectId(patient_id)
    prescriptions = await db.medical_prescriptions.find(query).sort("created_at", -1).to_list(100)
    for rx in prescriptions:
        rx["_id"] = str(rx["_id"])
        rx["patient_id"] = str(rx["patient_id"])
        rx["company_id"] = str(rx["company_id"])
        patient = await db.patients.find_one({"_id": ObjectId(rx["patient_id"])}, {"first_name": 1, "last_name": 1})
        if patient:
            rx["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
    return prescriptions

@prescriptions_router.post("/medical")
async def create_medical_prescription(data: MedicalPrescriptionCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    rx_doc = {
        "company_id": ObjectId(user["company_id"]),
        "patient_id": ObjectId(data.patient_id),
        "diagnosis": data.diagnosis,
        "medications": data.medications,
        "instructions": data.instructions,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
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
    
    # Header
    c.setFont("Helvetica-Bold", 18)
    c.drawString(1*inch, height - 1*inch, company["name"] if company else "Óptica")
    c.setFont("Helvetica", 10)
    c.drawString(1*inch, height - 1.3*inch, company.get("address", "") if company else "")
    
    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, height - 2*inch, "RECETA MÉDICA")
    
    # Patient info
    c.setFont("Helvetica", 11)
    c.drawString(1*inch, height - 2.5*inch, f"Paciente: {patient['first_name']} {patient['last_name']}" if patient else "")
    c.drawString(1*inch, height - 2.7*inch, f"Fecha: {rx['created_at'][:10]}")
    
    # Diagnosis
    y = height - 3.2*inch
    if rx.get("diagnosis"):
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1*inch, y, "Diagnóstico:")
        c.setFont("Helvetica", 10)
        c.drawString(1*inch, y - 0.2*inch, rx["diagnosis"][:100])
        y -= 0.5*inch
    
    # Medications
    c.setFont("Helvetica-Bold", 10)
    c.drawString(1*inch, y, "Medicamentos:")
    y -= 0.3*inch
    c.setFont("Helvetica", 10)
    for med in rx.get("medications", []):
        c.drawString(1.2*inch, y, f"• {med.get('name', '')}")
        c.drawString(3*inch, y, f"Dosis: {med.get('dosage', '')}")
        c.drawString(5*inch, y, f"Duración: {med.get('duration', '')}")
        y -= 0.25*inch
    
    # Instructions
    if rx.get("instructions"):
        y -= 0.3*inch
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1*inch, y, "Instrucciones:")
        c.setFont("Helvetica", 10)
        c.drawString(1*inch, y - 0.2*inch, rx["instructions"][:150])
    
    c.save()
    buffer.seek(0)
    
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=receta_medica_{rx_id}.pdf"})

# ==================== INVENTORY ROUTES ====================
@inventory_router.get("/products")
async def list_products(user: dict = Depends(get_current_user), category: Optional[str] = None, search: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
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
        p["_id"] = str(p["_id"])
        p["company_id"] = str(p["company_id"])
    return products

@inventory_router.post("/products")
async def create_product(data: ProductCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    product_doc = {
        "company_id": ObjectId(user["company_id"]),
        "name": data.name,
        "sku": data.sku,
        "category": data.category,
        "brand": data.brand,
        "description": data.description,
        "cost_price": data.cost_price,
        "sale_price": data.sale_price,
        "min_stock": data.min_stock,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.products.insert_one(product_doc)
    return {"_id": str(result.inserted_id), "message": "Producto creado"}

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
        s["_id"] = str(s["_id"])
        s["product_id"] = str(s["product_id"])
        s["company_id"] = str(s["company_id"])
        s["branch_id"] = str(s["branch_id"])
        product = await db.products.find_one({"_id": ObjectId(s["product_id"])}, {"name": 1, "sku": 1, "min_stock": 1, "sale_price": 1})
        if product:
            s["product_name"] = product["name"]
            s["sku"] = product["sku"]
            s["min_stock"] = product.get("min_stock", 5)
            s["sale_price"] = product.get("sale_price", 0)
    return stock

@inventory_router.post("/movement")
async def create_inventory_movement(data: InventoryMovement, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    # Update or create stock record
    stock = await db.stock.find_one({
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(data.branch_id),
        "product_id": ObjectId(data.product_id)
    })
    
    quantity_change = data.quantity if data.type == "in" else -data.quantity
    
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
    
    # Record movement
    movement_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(data.branch_id),
        "product_id": ObjectId(data.product_id),
        "type": data.type,
        "quantity": data.quantity,
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    await db.inventory_movements.insert_one(movement_doc)
    
    return {"message": "Movimiento registrado"}

@inventory_router.get("/alerts")
async def get_stock_alerts(user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    stock_items = await db.stock.find(query).to_list(1000)
    alerts = []
    for s in stock_items:
        product = await db.products.find_one({"_id": s["product_id"]}, {"name": 1, "min_stock": 1})
        if product and s["quantity"] <= product.get("min_stock", 5):
            alerts.append({
                "product_id": str(s["product_id"]),
                "product_name": product["name"],
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
    branch_id: Optional[str] = None
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    if date_from and date_to:
        query["created_at"] = {"$gte": date_from, "$lte": date_to}
    
    sales = await db.sales.find(query).sort("created_at", -1).to_list(200)
    for s in sales:
        s["_id"] = str(s["_id"])
        s["company_id"] = str(s["company_id"])
        if s.get("branch_id"):
            s["branch_id"] = str(s["branch_id"])
        if s.get("patient_id"):
            s["patient_id"] = str(s["patient_id"])
            patient = await db.patients.find_one({"_id": ObjectId(s["patient_id"])}, {"first_name": 1, "last_name": 1})
            if patient:
                s["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
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
        "subtotal": data.subtotal,
        "discount": data.discount,
        "tax": data.tax,
        "total": data.total,
        "payment_method": data.payment_method,
        "amount_paid": data.amount_paid,
        "balance": data.total - data.amount_paid,
        "status": "completed" if data.amount_paid >= data.total else "pending",
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    result = await db.sales.insert_one(sale_doc)
    
    # Update stock
    for item in data.items:
        if item.get("product_id") and branch_id:
            await db.stock.update_one(
                {"product_id": ObjectId(item["product_id"]), "branch_id": branch_id},
                {"$inc": {"quantity": -item.get("quantity", 1)}}
            )
    
    # Create finance entry
    finance_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": branch_id,
        "type": "income",
        "category": "sales",
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

@sales_router.post("/{sale_id}/payment")
async def add_payment(sale_id: str, amount: float, user: dict = Depends(get_current_user)):
    sale = await db.sales.find_one({"_id": ObjectId(sale_id)})
    if not sale or str(sale["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    
    new_paid = sale.get("amount_paid", 0) + amount
    new_balance = sale["total"] - new_paid
    status = "completed" if new_balance <= 0 else "pending"
    
    await db.sales.update_one(
        {"_id": ObjectId(sale_id)},
        {"$set": {"amount_paid": new_paid, "balance": new_balance, "status": status}}
    )
    
    # Create finance entry
    finance_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": sale.get("branch_id"),
        "type": "income",
        "category": "sales",
        "amount": amount,
        "description": f"Abono venta #{sale_id[-6:]}",
        "reference_id": ObjectId(sale_id),
        "reference_type": "sale_payment",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    await db.finance_entries.insert_one(finance_doc)
    
    return {"message": "Pago registrado", "new_balance": new_balance}

# ==================== FINANCE ROUTES ====================
@finance_router.get("")
async def list_finance_entries(
    user: dict = Depends(get_current_user),
    type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[str] = None
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if type:
        query["type"] = type
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    if date_from and date_to:
        query["date"] = {"$gte": date_from, "$lte": date_to}
    
    entries = await db.finance_entries.find(query).sort("date", -1).to_list(500)
    for e in entries:
        e["_id"] = str(e["_id"])
        e["company_id"] = str(e["company_id"])
        if e.get("branch_id"):
            e["branch_id"] = str(e["branch_id"])
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
    
    income = sum(e["amount"] for e in entries if e["type"] == "income")
    expense = sum(e["amount"] for e in entries if e["type"] == "expense")
    
    return {
        "income": income,
        "expense": expense,
        "profit": income - expense,
        "period": {"from": date_from or month_start, "to": date_to or today}
    }

# ==================== REPORTS ROUTES ====================
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
    
    # Appointments today
    apt_query = {"company_id": company_id, "date": today, **branch_filter}
    appointments_today = await db.appointments.count_documents(apt_query)
    
    # New patients this month
    patients_query = {"company_id": company_id, "created_at": {"$gte": month_start}}
    new_patients = await db.patients.count_documents(patients_query)
    
    # Sales this month
    sales_query = {"company_id": company_id, "created_at": {"$gte": month_start}, **branch_filter}
    sales = await db.sales.find(sales_query).to_list(1000)
    total_sales = sum(s.get("total", 0) for s in sales)
    sales_count = len(sales)
    
    # Finance summary
    finance_query = {"company_id": company_id, "date": {"$gte": month_start, "$lte": today}, **branch_filter}
    finance_entries = await db.finance_entries.find(finance_query).to_list(1000)
    income = sum(e["amount"] for e in finance_entries if e["type"] == "income")
    expense = sum(e["amount"] for e in finance_entries if e["type"] == "expense")
    
    # Stock alerts
    stock_alerts = await get_stock_alerts_count(company_id, branch_filter.get("branch_id"))
    
    # Upcoming appointments - simplified to avoid ObjectId issues
    upcoming_apts_raw = await db.appointments.find({
        "company_id": company_id,
        "date": {"$gte": today},
        "status": "scheduled",
        **branch_filter
    }).sort([("date", 1), ("time", 1)]).limit(5).to_list(5)
    
    upcoming_apts = []
    for apt in upcoming_apts_raw:
        # Convert all ObjectId fields to strings
        clean_apt = {
            "_id": str(apt["_id"]),
            "patient_id": str(apt["patient_id"]),
            "company_id": str(apt["company_id"]),
            "date": apt.get("date", ""),
            "time": apt.get("time", ""),
            "type": apt.get("type", ""),
            "status": apt.get("status", "")
        }
        if apt.get("branch_id"):
            clean_apt["branch_id"] = str(apt["branch_id"])
        if apt.get("professional_id"):
            clean_apt["professional_id"] = str(apt["professional_id"])
        
        # Get patient name
        patient = await db.patients.find_one({"_id": ObjectId(apt["patient_id"])}, {"first_name": 1, "last_name": 1})
        if patient:
            clean_apt["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
        
        upcoming_apts.append(clean_apt)
    
    # Recent prescriptions
    recent_rx = await db.eyeglass_prescriptions.find({"company_id": company_id}).sort("created_at", -1).limit(5).to_list(5)
    rx_count = len(recent_rx)
    
    return {
        "appointments_today": appointments_today,
        "new_patients": new_patients,
        "sales_count": sales_count,
        "total_sales": total_sales,
        "income": income,
        "expense": expense,
        "profit": income - expense,
        "stock_alerts": stock_alerts,
        "prescriptions_count": rx_count,
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
    
    query = {
        "company_id": ObjectId(user["company_id"]),
        "created_at": {"$gte": date_from or month_start, "$lte": date_to or today}
    }
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    sales = await db.sales.find(query).to_list(1000)
    
    total = sum(s.get("total", 0) for s in sales)
    count = len(sales)
    by_payment = {}
    for s in sales:
        pm = s.get("payment_method", "other")
        by_payment[pm] = by_payment.get(pm, 0) + s.get("total", 0)
    
    return {
        "total": total,
        "count": count,
        "average": total / count if count > 0 else 0,
        "by_payment_method": by_payment
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
        u["_id"] = str(u["_id"])
        if u.get("company_id"):
            u["company_id"] = str(u["company_id"])
        if u.get("branch_id"):
            u["branch_id"] = str(u["branch_id"])
    return users

@users_router.post("")
async def create_user(data: UserCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    user_doc = {
        "email": data.email.lower(),
        "password_hash": hash_password(data.password),
        "name": data.name,
        "role": data.role,
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(data.branch_id) if data.branch_id else None,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.users.insert_one(user_doc)
    return {"_id": str(result.inserted_id), "message": "Usuario creado"}

@users_router.put("/{user_id}")
async def update_user(user_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    target_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target_user or str(target_user.get("company_id")) != user["company_id"]:
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
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    target_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target_user or str(target_user.get("company_id")) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": False}})
    return {"message": "Usuario desactivado"}

# Include all routers
api_router.include_router(auth_router)
api_router.include_router(companies_router)
api_router.include_router(branches_router)
api_router.include_router(patients_router)
api_router.include_router(appointments_router)
api_router.include_router(prescriptions_router)
api_router.include_router(inventory_router)
api_router.include_router(sales_router)
api_router.include_router(finance_router)
api_router.include_router(reports_router)
api_router.include_router(users_router)

app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Startup event - seed admin and demo data
@app.on_event("startup")
async def startup():
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.patients.create_index([("company_id", 1), ("last_name", 1)])
    await db.appointments.create_index([("company_id", 1), ("date", 1)])
    await db.stock.create_index([("company_id", 1), ("branch_id", 1), ("product_id", 1)], unique=True)
    
    # Seed superadmin
    admin_email = os.environ.get("ADMIN_EMAIL", "superadmin@opticasaas.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin123!")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Super Administrador",
            "role": "superadmin",
            "company_id": None,
            "branch_id": None,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"SuperAdmin created: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})
        logger.info("SuperAdmin password updated")
    
    # Seed demo company
    demo_company = await db.companies.find_one({"name": "Óptica Visión Clara"})
    if not demo_company:
        company_result = await db.companies.insert_one({
            "name": "Óptica Visión Clara",
            "legal_name": "Óptica Visión Clara S.A.",
            "tax_id": "12345678-9",
            "address": "6ta Avenida 12-34, Zona 1, Ciudad de Guatemala",
            "phone": "+502 2234-5678",
            "email": "info@visionclara.gt",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        company_id = company_result.inserted_id
        
        # Create admin for demo company
        demo_admin = await db.users.find_one({"email": "admin@visionclara.gt"})
        if not demo_admin:
            await db.users.insert_one({
                "email": "admin@visionclara.gt",
                "password_hash": hash_password("Demo123!"),
                "name": "Carlos Mendoza",
                "role": "admin",
                "company_id": company_id,
                "branch_id": None,
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        
        # Create demo branch
        branch_result = await db.branches.insert_one({
            "company_id": company_id,
            "name": "Sede Central - Zona 1",
            "address": "6ta Avenida 12-34, Zona 1, Ciudad de Guatemala",
            "phone": "+502 2234-5678",
            "email": "central@visionclara.gt",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        branch_id = branch_result.inserted_id
        
        # Create demo user
        await db.users.insert_one({
            "email": "vendedor@visionclara.gt",
            "password_hash": hash_password("Demo123!"),
            "name": "María López",
            "role": "user",
            "company_id": company_id,
            "branch_id": branch_id,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Create demo patients
        patients_data = [
            {"first_name": "Juan", "last_name": "Pérez García", "phone": "+502 5555-1234", "dpi": "1234567890101", "gender": "M", "birth_date": "1985-03-15"},
            {"first_name": "Ana", "last_name": "Martínez Ruiz", "phone": "+502 5555-2345", "dpi": "2345678901212", "gender": "F", "birth_date": "1990-07-22"},
            {"first_name": "Roberto", "last_name": "González López", "phone": "+502 5555-3456", "dpi": "3456789012323", "gender": "M", "birth_date": "1978-11-08"},
            {"first_name": "Sofía", "last_name": "Hernández Cruz", "phone": "+502 5555-4567", "dpi": "4567890123434", "gender": "F", "birth_date": "1995-01-30"},
            {"first_name": "Luis", "last_name": "Ramírez Morales", "phone": "+502 5555-5678", "dpi": "5678901234545", "gender": "M", "birth_date": "1982-09-12"}
        ]
        
        patient_ids = []
        for p in patients_data:
            result = await db.patients.insert_one({
                **p,
                "company_id": company_id,
                "branch_id": branch_id,
                "address": "Ciudad de Guatemala",
                "email": f"{p['first_name'].lower()}@email.com",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            patient_ids.append(result.inserted_id)
        
        # Create demo products
        products_data = [
            {"name": "Armazón Ray-Ban RB5154", "sku": "ARZ-RB5154", "category": "armazones", "brand": "Ray-Ban", "cost_price": 450, "sale_price": 850},
            {"name": "Armazón Oakley OX8046", "sku": "ARZ-OX8046", "category": "armazones", "brand": "Oakley", "cost_price": 380, "sale_price": 720},
            {"name": "Lente Progresivo Essilor", "sku": "LNT-PROG-ESS", "category": "lentes", "brand": "Essilor", "cost_price": 600, "sale_price": 1200},
            {"name": "Lente Bifocal Zeiss", "sku": "LNT-BIF-ZEI", "category": "lentes", "brand": "Zeiss", "cost_price": 450, "sale_price": 900},
            {"name": "Lente de Contacto Acuvue", "sku": "LC-ACUVUE", "category": "contactos", "brand": "Acuvue", "cost_price": 180, "sale_price": 350},
            {"name": "Solución para Lentes 360ml", "sku": "SOL-360", "category": "accesorios", "brand": "Opti-Free", "cost_price": 45, "sale_price": 95},
            {"name": "Estuche Premium", "sku": "EST-PREM", "category": "accesorios", "brand": "Generic", "cost_price": 25, "sale_price": 65}
        ]
        
        product_ids = []
        for pr in products_data:
            result = await db.products.insert_one({
                **pr,
                "company_id": company_id,
                "min_stock": 5,
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            product_ids.append(result.inserted_id)
            
            # Add stock
            await db.stock.insert_one({
                "company_id": company_id,
                "branch_id": branch_id,
                "product_id": result.inserted_id,
                "quantity": 15,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        
        # Create demo appointments
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for i, pid in enumerate(patient_ids[:3]):
            await db.appointments.insert_one({
                "company_id": company_id,
                "branch_id": branch_id,
                "patient_id": pid,
                "date": today,
                "time": f"{9 + i}:00",
                "duration": 30,
                "type": "consulta",
                "status": "scheduled",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        
        # Create demo prescriptions
        await db.eyeglass_prescriptions.insert_one({
            "company_id": company_id,
            "patient_id": patient_ids[0],
            "od_sphere": -2.50,
            "od_cylinder": -0.75,
            "od_axis": 90,
            "od_addition": None,
            "od_dp": 32,
            "oi_sphere": -2.25,
            "oi_cylinder": -0.50,
            "oi_axis": 85,
            "oi_addition": None,
            "oi_dp": 32,
            "observations": "Miopía con astigmatismo leve",
            "lens_type": "Monofocal",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info("Demo data seeded successfully")
    
    # Write test credentials
    Path("/app/memory").mkdir(parents=True, exist_ok=True)
    with open("/app/memory/test_credentials.md", "w") as f:
        f.write("""# Test Credentials

## SuperAdmin
- Email: superadmin@opticasaas.com
- Password: Admin123!
- Role: superadmin

## Demo Company Admin (Óptica Visión Clara)
- Email: admin@visionclara.gt
- Password: Demo123!
- Role: admin

## Demo User
- Email: vendedor@visionclara.gt
- Password: Demo123!
- Role: user

## Auth Endpoints
- POST /api/auth/login
- POST /api/auth/register
- POST /api/auth/logout
- GET /api/auth/me
- POST /api/auth/refresh
""")

@app.on_event("shutdown")
async def shutdown():
    client.close()
