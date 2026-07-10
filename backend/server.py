from fastapi import FastAPI, APIRouter, Depends, Query, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from bson import ObjectId
from pathlib import Path
from datetime import datetime, timezone
import os
import logging

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from db import db, client
from auth_utils import get_current_user, hash_password, get_real_ip
from rate_limiter import limiter

from routes import (
    auth, companies, settings, branches, patients, appointments,
    prescriptions, inventory, sales, quotations, consultations,
    finance, reports, users, suppliers, plans, superadmin, announcements,
    notifications, security, data_export, audit_log, onboarding, health_metrics
)

app = FastAPI(title="Cortexia Optical API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Gzip compression para responses > 500 bytes (grande impacto en listados y JSON)
app.add_middleware(GZipMiddleware, minimum_size=500)

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
api_router.include_router(announcements.router)
api_router.include_router(notifications.router)
api_router.include_router(security.router)
api_router.include_router(data_export.router)
api_router.include_router(audit_log.router)
api_router.include_router(onboarding.router)
api_router.include_router(health_metrics.router)

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

# Security headers middleware (HSTS, CSP, X-Frame-Options, etc.)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # Solo en HTTPS / produccion - HSTS forza HTTPS por 1 año
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Previene clickjacking (no permitir embeber en iframes externos)
    response.headers["X-Frame-Options"] = "DENY"
    # Previene MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Solo enviar referrer al mismo origen
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Restringe que features del browser pueden usarse
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    return response

# No-cache middleware
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

# CORS - Strict whitelist + reflect allowed origins for credentials support
# Lee de CORS_ORIGINS env (comma-separated) o usa defaults conocidos
_DEFAULT_ORIGINS = {
    "https://cortexiaoptical.com",
    "https://www.cortexiaoptical.com",
    "https://eyecare-erp.preview.emergentagent.com",
}
ALLOWED_ORIGINS = set(_DEFAULT_ORIGINS)
_cors_env = os.environ.get("CORS_ORIGINS", "").strip()
if _cors_env and _cors_env != "*":
    for o in _cors_env.split(","):
        o = o.strip()
        if o:
            ALLOWED_ORIGINS.add(o)
# Backward-compat: EXTRA_CORS_ORIGINS tambien funciona
_extra = os.environ.get("EXTRA_CORS_ORIGINS", "").strip()
if _extra:
    for o in _extra.split(","):
        o = o.strip()
        if o:
            ALLOWED_ORIGINS.add(o)

def _is_allowed_origin(origin: str) -> bool:
    if not origin:
        return False
    return origin in ALLOWED_ORIGINS

@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin", "")
    allowed = _is_allowed_origin(origin)
    
    if request.method == "OPTIONS":
        response = Response(status_code=200 if allowed else 403)
        if allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Max-Age"] = "600"
            response.headers["Vary"] = "Origin"
        return response
    
    response = await call_next(request)
    if allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Vary"] = "Origin"
    return response

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup():
    # ═══════════════════════════════════════════════════════════════════
    # ÍNDICES MongoDB — critico para escalar a miles de opticas
    # Todos los indexes son idempotentes (create_index no falla si existen)
    # ═══════════════════════════════════════════════════════════════════

    # --- Users ---
    await db.users.create_index("email", unique=True)
    await db.users.create_index([("company_id", 1), ("is_active", 1)])
    await db.users.create_index([("company_id", 1), ("role", 1)])

    # --- Login attempts (brute-force protection) ---
    await db.login_attempts.create_index("identifier")
    await db.login_attempts.create_index("created_at", expireAfterSeconds=86400)  # 24h TTL

    # --- Audit log (TTL: 180 dias) ---
    await db.audit_log.create_index([("created_at", -1)])
    await db.audit_log.create_index([("action", 1), ("created_at", -1)])
    await db.audit_log.create_index([("company_id", 1), ("created_at", -1)])
    await db.audit_log.create_index([("user_email", 1), ("created_at", -1)])
    # TTL: elimina automaticamente registros > 180 dias
    try:
        await db.audit_log.create_index("created_at", expireAfterSeconds=15552000, name="audit_ttl")
    except Exception as e:
        logger.debug(f"audit_log TTL index already present: {e}")

    # --- Companies ---
    await db.companies.create_index([("is_active", 1)])
    await db.companies.create_index([("plan_id", 1)])
    await db.companies.create_index("email")

    # --- Patients ---
    await db.patients.create_index([("company_id", 1), ("last_name", 1)])
    await db.patients.create_index([("company_id", 1), ("phone", 1)])
    await db.patients.create_index([("company_id", 1), ("dpi", 1)])
    await db.patients.create_index([("company_id", 1), ("is_deleted", 1), ("created_at", -1)])
    await db.patients.create_index([("company_id", 1), ("branch_id", 1)])

    # --- Appointments ---
    await db.appointments.create_index([("company_id", 1), ("date", 1)])
    await db.appointments.create_index([("company_id", 1), ("patient_id", 1)])
    await db.appointments.create_index([("company_id", 1), ("status", 1), ("date", 1)])

    # --- Products / Stock / Inventory ---
    await db.products.create_index([("company_id", 1), ("is_active", 1)])
    await db.products.create_index([("company_id", 1), ("sku", 1)])
    await db.products.create_index([("company_id", 1), ("category", 1)])
    await db.stock.create_index([("company_id", 1), ("branch_id", 1), ("product_id", 1)], unique=True)
    await db.stock.create_index([("company_id", 1), ("product_id", 1)])
    await db.inventory_movements.create_index([("company_id", 1), ("created_at", -1)])
    await db.inventory_movements.create_index([("company_id", 1), ("product_id", 1), ("created_at", -1)])

    # --- Sales ---
    await db.sales.create_index([("company_id", 1), ("created_at", -1)])
    await db.sales.create_index([("company_id", 1), ("branch_id", 1), ("created_at", -1)])
    await db.sales.create_index([("company_id", 1), ("patient_id", 1)])
    await db.sales.create_index([("company_id", 1), ("status", 1)])

    # --- Finance ---
    await db.finance_entries.create_index([("company_id", 1), ("date", -1)])
    await db.finance_entries.create_index([("company_id", 1), ("type", 1), ("date", -1)])

    # --- Quotations ---
    await db.quotations.create_index([("company_id", 1), ("created_at", -1)])
    await db.quotations.create_index([("company_id", 1), ("status", 1)])
    await db.quotations.create_index([("company_id", 1), ("patient_id", 1)])

    # --- Consultations & Prescriptions ---
    await db.optical_consultations.create_index([("company_id", 1), ("patient_id", 1), ("created_at", -1)])
    await db.optical_consultations.create_index([("company_id", 1), ("created_at", -1)])
    await db.eyeglass_prescriptions.create_index([("company_id", 1), ("patient_id", 1), ("created_at", -1)])
    await db.contact_lens_prescriptions.create_index([("company_id", 1), ("patient_id", 1), ("created_at", -1)])
    await db.medical_prescriptions.create_index([("company_id", 1), ("patient_id", 1), ("created_at", -1)])

    # --- Branches ---
    await db.branches.create_index([("company_id", 1), ("is_active", 1)])

    # --- Suppliers ---
    await db.suppliers.create_index([("company_id", 1), ("is_active", 1)])

    # --- Notifications (SuperAdmin) ---
    await db.notifications.create_index([("read", 1), ("created_at", -1)])
    await db.notifications.create_index([("created_at", -1)])

    # --- Announcements ---
    await db.announcements.create_index([("is_active", 1), ("starts_at", 1), ("ends_at", 1)])

    logger.info("MongoDB indexes verified/created OK")
    
    # Seed superadmin - lee credenciales SOLO de env vars. Si no estan presentes,
    # NO crea ni resetea el SuperAdmin (evita hardcodear secretos en el repo).
    # IMPORTANTE: En el panel de Emergent Deployments, configura las variables:
    #   ADMIN_EMAIL (email del superadmin)
    #   ADMIN_PASSWORD (minimo 8 chars, entre comillas simples si contiene $)
    admin_email = (os.environ.get("ADMIN_EMAIL", "") or "").strip()
    admin_password = (os.environ.get("ADMIN_PASSWORD", "") or "").strip()
    if admin_email and admin_password and len(admin_password) >= 8:
        logger.info(f"SuperAdmin seed: email={admin_email}, pw_len={len(admin_password)}")
        try:
            existing = await db.users.find_one({"email": admin_email})
            new_hash = hash_password(admin_password)
            if existing:
                await db.users.update_one(
                    {"email": admin_email},
                    {"$set": {"password_hash": new_hash, "role": "superadmin", "is_active": True}}
                )
                logger.info(f"SuperAdmin password reset OK: {admin_email}")
            else:
                await db.users.insert_one({
                    "email": admin_email, "password_hash": new_hash,
                    "name": "Super Administrador", "role": "superadmin",
                    "company_id": None, "branch_id": None, "is_active": True,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                logger.info(f"SuperAdmin created: {admin_email}")
        except Exception as e:
            logger.error(f"SuperAdmin seed error: {e}")
    else:
        logger.warning("SuperAdmin seed SKIPPED: ADMIN_EMAIL/ADMIN_PASSWORD env vars no configurados o password < 8 chars")
    
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
