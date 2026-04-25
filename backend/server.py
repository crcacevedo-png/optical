from fastapi import FastAPI, APIRouter, Depends, Query, Request
from starlette.middleware.cors import CORSMiddleware
from bson import ObjectId
from pathlib import Path
from datetime import datetime, timezone
import os
import logging

from db import db, client
from auth_utils import get_current_user, hash_password

from routes import (
    auth, companies, settings, branches, patients, appointments,
    prescriptions, inventory, sales, quotations, consultations,
    finance, reports, users, suppliers, plans, superadmin
)

app = FastAPI(title="Cortexia Optical API")

api_router = APIRouter(prefix="/api")

# Include all routers
api_router.include_router(auth.router)
api_router.include_router(companies.router)
api_router.include_router(branches.router)
api_router.include_router(patients.router)
api_router.include_router(appointments.router)
api_router.include_router(prescriptions.router)
api_router.include_router(inventory.router)
api_router.include_router(sales.router)
api_router.include_router(quotations.router)
api_router.include_router(consultations.router)
api_router.include_router(finance.router)
api_router.include_router(reports.router)
api_router.include_router(users.router)
api_router.include_router(suppliers.router)
api_router.include_router(settings.router)
api_router.include_router(plans.router)
api_router.include_router(superadmin.router)

# Global search
@api_router.get("/search")
async def global_search(q: str = Query(..., min_length=2), user: dict = Depends(get_current_user)):
    company_id = ObjectId(user["company_id"])
    regex = {"$regex": q, "$options": "i"}
    results = []
    patients = await db.patients.find(
        {"company_id": company_id, "$or": [{"first_name": regex}, {"last_name": regex}, {"phone": regex}, {"dpi": regex}]},
        {"_id": 1, "first_name": 1, "last_name": 1, "phone": 1}
    ).limit(5).to_list(5)
    for p in patients:
        results.append({"type": "patient", "id": str(p["_id"]), "title": f"{p.get('first_name','')} {p.get('last_name','')}", "subtitle": p.get("phone", "")})
    products = await db.products.find(
        {"company_id": company_id, "$or": [{"name": regex}, {"sku": regex}]},
        {"_id": 1, "name": 1, "sku": 1, "price": 1}
    ).limit(5).to_list(5)
    for p in products:
        results.append({"type": "product", "id": str(p["_id"]), "title": p["name"], "subtitle": f"SKU: {p.get('sku','')} | Q{p.get('price',0):.2f}"})
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

# No-cache middleware
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

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

@app.on_event("startup")
async def startup():
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
        await db.users.insert_one({
            "email": "admin@cortexia.gt", "password_hash": hash_password("Demo123!"),
            "name": "Dr. Carlos Mendoza", "role": "admin", "company_id": company_id,
            "branch_id": None, "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
        })
        branch_result = await db.branches.insert_one({
            "company_id": company_id, "name": "Sede Central - Zona 1",
            "address": "6ta Avenida 12-34, Zona 1", "phone": "+502 2234-5678",
            "email": "central@cortexia.gt", "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        branch_id = branch_result.inserted_id
        await db.users.insert_one({
            "email": "vendedor@cortexia.gt", "password_hash": hash_password("Demo123!"),
            "name": "Maria Lopez", "role": "user", "company_id": company_id,
            "branch_id": branch_id, "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
        })
        patients_data = [
            {"first_name": "Juan", "last_name": "Perez Garcia", "phone": "+502 5555-1234", "whatsapp": "+502 5555-1234", "dpi": "1234567890101", "gender": "M", "birth_date": "1985-03-15", "city": "Guatemala", "country": "Guatemala"},
            {"first_name": "Ana", "last_name": "Martinez Ruiz", "phone": "+502 5555-2345", "whatsapp": "+502 5555-2345", "dpi": "2345678901212", "gender": "F", "birth_date": "1990-07-22", "city": "Mixco", "country": "Guatemala"},
            {"first_name": "Roberto", "last_name": "Gonzalez Lopez", "phone": "+502 5555-3456", "whatsapp": "+502 5555-3456", "dpi": "3456789012323", "gender": "M", "birth_date": "1978-11-08", "city": "Villa Nueva", "country": "Guatemala"},
            {"first_name": "Sofia", "last_name": "Hernandez Cruz", "phone": "+502 5555-4567", "whatsapp": "+502 5555-4567", "dpi": "4567890123434", "gender": "F", "birth_date": "1995-01-30", "city": "Guatemala", "country": "Guatemala"},
            {"first_name": "Luis", "last_name": "Ramirez Morales", "phone": "+502 5555-5678", "whatsapp": "+502 5555-5678", "dpi": "5678901234545", "gender": "M", "birth_date": "1982-09-12", "city": "Petapa", "country": "Guatemala"}
        ]
        patient_ids = []
        for p in patients_data:
            result = await db.patients.insert_one({
                **p, "company_id": company_id, "branch_id": branch_id,
                "address": "Ciudad de Guatemala", "email": f"{p['first_name'].lower()}@email.com",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            patient_ids.append(result.inserted_id)
        products_data = [
            {"name": "Armazon Ray-Ban RB5154", "sku": "ARZ-RB5154", "category": "armazones", "brand": "Ray-Ban", "cost_price": 450, "sale_price": 850, "min_stock": 3},
            {"name": "Armazon Oakley OX8046", "sku": "ARZ-OX8046", "category": "armazones", "brand": "Oakley", "cost_price": 380, "sale_price": 720, "min_stock": 3},
            {"name": "Lente Progresivo Essilor", "sku": "LNT-PROG-ESS", "category": "lentes", "brand": "Essilor", "cost_price": 600, "sale_price": 1200, "min_stock": 5},
            {"name": "Lente Bifocal Zeiss", "sku": "LNT-BIF-ZEI", "category": "lentes", "brand": "Zeiss", "cost_price": 450, "sale_price": 900, "min_stock": 5},
            {"name": "Lente de Contacto Acuvue Oasys", "sku": "LC-ACUVUE", "category": "contactos", "brand": "Acuvue", "cost_price": 180, "sale_price": 350, "min_stock": 10},
            {"name": "Solucion ReNu 360ml", "sku": "SOL-360", "category": "accesorios", "brand": "ReNu", "cost_price": 45, "sale_price": 95, "min_stock": 8},
            {"name": "Estuche Premium para Anteojos", "sku": "EST-PREM", "category": "accesorios", "brand": "Generic", "cost_price": 25, "sale_price": 65, "min_stock": 10}
        ]
        for pr in products_data:
            result = await db.products.insert_one({
                **pr, "company_id": company_id, "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            await db.stock.insert_one({
                "company_id": company_id, "branch_id": branch_id,
                "product_id": result.inserted_id, "quantity": 15,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for i, pid in enumerate(patient_ids[:3]):
            await db.appointments.insert_one({
                "company_id": company_id, "branch_id": branch_id, "patient_id": pid,
                "date": today, "time": f"{9 + i}:00", "duration": 30,
                "type": "consulta", "status": "pendiente", "professional_name": "Dr. Carlos Mendoza",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        await db.eyeglass_prescriptions.insert_one({
            "company_id": company_id, "patient_id": patient_ids[0],
            "professional_name": "Dr. Carlos Mendoza",
            "od_sphere": -2.50, "od_cylinder": -0.75, "od_axis": 90, "od_dp": 32,
            "oi_sphere": -2.25, "oi_cylinder": -0.50, "oi_axis": 85, "oi_dp": 32,
            "observations": "Miopia con astigmatismo leve", "lens_type": "Monofocal",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info("Demo data seeded successfully")

    # Seed default plans
    existing_plans = await db.plans.count_documents({})
    if existing_plans == 0:
        default_plans = [
            {
                "name": "Free",
                "price": 0,
                "max_branches": 1,
                "max_patients": 50,
                "modules": [],
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "name": "Basic",
                "price": 299,
                "max_branches": 3,
                "max_patients": 500,
                "modules": ["inventario", "ventas"],
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "name": "Enterprise",
                "price": 799,
                "max_branches": 0,
                "max_patients": 0,
                "modules": ["inventario", "ventas", "proveedores", "finanzas"],
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        ]
        await db.plans.insert_many(default_plans)
        # Assign Free plan to all existing companies without a plan
        free_plan = await db.plans.find_one({"name": "Free"})
        if free_plan:
            await db.companies.update_many(
                {"plan_id": {"$exists": False}},
                {"$set": {"plan_id": free_plan["_id"]}}
            )
        logger.info("Default plans seeded")

@app.on_event("shutdown")
async def shutdown():
    client.close()
