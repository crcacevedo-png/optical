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
    notifications, security, data_export, audit_log, onboarding, health_metrics,
    cash_register, support_tickets, billing, jornadas, jornada_ops, jornada_consignment,
    superadmin_retention, reactivation_feedback, sessions, security_reports, user_guide,
    email_queue_admin, leads, registration,
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
api_router.include_router(cash_register.router)
api_router.include_router(support_tickets.router)
api_router.include_router(billing.router)
api_router.include_router(jornadas.router)
api_router.include_router(jornada_ops.router)
api_router.include_router(jornada_consignment.router)
api_router.include_router(superadmin_retention.router)
api_router.include_router(reactivation_feedback.router)
api_router.include_router(sessions.router)
api_router.include_router(security_reports.router)
api_router.include_router(user_guide.router)
api_router.include_router(email_queue_admin.router)
api_router.include_router(leads.router)
api_router.include_router(registration.router)
api_router.include_router(billing.cron_router)
api_router.include_router(registration.cron_router)
# Cron de la plataforma (Bearer WEBHOOK_CRON_SECRET) va bajo /api/cron/* via api_router.

# Global search
@api_router.get("/search")
async def global_search(q: str = Query(..., min_length=2, max_length=100), user: dict = Depends(get_current_user)):
    company_id = ObjectId(user["company_id"])
    # SEC hardening: escape user input para prevenir ReDoS y regex injection
    import re
    regex = {"$regex": re.escape(q), "$options": "i"}
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


def _origin_matches_host(origin: str, request: Request) -> bool:
    """Verifica si el Origin coincide con el Host/X-Forwarded-Host del request.
    Util cuando el proxy reescribe Origin al hostname interno del cluster
    (ej. Emergent CF: proxy publica en emergentagent.com pero backend recibe
    Origin=emergentcf.cloud interno). Un ataque cross-site NO puede forjar
    coincidencia entre Origin y Host, por eso este check es equivalente a
    validar contra whitelist para requests same-origin.
    """
    if not origin:
        return False
    from urllib.parse import urlparse
    try:
        origin_host = urlparse(origin).netloc.lower()
        req_host = (request.headers.get("host") or "").lower()
        xfh = (request.headers.get("x-forwarded-host") or "").lower()
        return origin_host and (origin_host == req_host or origin_host == xfh)
    except Exception:
        return False

@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin", "")
    allowed = _is_allowed_origin(origin)

    # IP block check (Feb 2026): bloquea requests desde IPs marcadas por comportamiento anomalo.
    # Aplica solo a paths /api (no bloqueamos el HTML de la SPA para no romper UX de usuarios legitimos
    # que quedaron atrapados por false-positive; ellos veran errores en las API calls y sabran).
    if request.url.path.startswith("/api"):
        from auth_utils import get_real_ip
        client_ip = get_real_ip(request)
        if client_ip and client_ip != "unknown":
            try:
                from blocked_ips import is_ip_blocked
                if await is_ip_blocked(client_ip):
                    return Response(
                        status_code=403,
                        content='{"detail":"IP bloqueada por comportamiento anomalo. Contacta soporte."}',
                        media_type="application/json",
                    )
            except Exception as e:
                logger.warning(f"blocked_ips check failed: {e}")

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

    # SEC-001 CSRF protection (Feb 2026): validar Origin en state-changing requests.
    # Necesario porque el proxy fuerza SameSite=None+Partitioned. Cloudflare a veces reescribe
    # el header Origin al hostname interno del cluster; validamos que Origin/Referer coincidan
    # con la whitelist O con el Host/X-Forwarded-Host (equivalente a same-origin desde el punto
    # de vista del cliente). Excepciones: webhooks server-to-server.
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        path = request.url.path
        # Whitelist de paths server-to-server sin auth cookie (Stripe webhook verifica via signature)
        # y endpoints que reciben reportes del navegador (no pueden usar X-CSRF-Token porque
        # el propio navegador los envia sin intervencion de JS).
        _CSRF_EXEMPT_PATHS = (
            "/api/cron/",
            "/api/security/csp-report",
        )
        is_exempt = any(path.startswith(p) for p in _CSRF_EXEMPT_PATHS)
        if not is_exempt:
            referer = request.headers.get("referer", "")
            has_auth_cookie = bool(request.cookies.get("access_token") or request.cookies.get("refresh_token"))
            # CSRF Double-Submit: si existe csrf_token cookie, exigimos header X-CSRF-Token
            # que coincida (attacker cross-site NO puede leer la cookie via JS por SOP).
            # Es la defensa mas robusta contra CSRF cuando el proxy reescribe el Origin header.
            csrf_cookie = request.cookies.get("csrf_token")
            csrf_header = request.headers.get("x-csrf-token")
            csrf_ok = bool(csrf_cookie and csrf_header and csrf_cookie == csrf_header)

            # Origin/Referer fallback (para clientes legacy sin csrf_token cookie aun)
            origin_ok = _is_allowed_origin(origin) or _origin_matches_host(origin, request)
            referer_ok = False
            if referer:
                from urllib.parse import urlparse
                try:
                    p = urlparse(referer)
                    ref_origin = f"{p.scheme}://{p.netloc}"
                    referer_ok = _is_allowed_origin(ref_origin) or _origin_matches_host(ref_origin, request)
                except Exception:
                    referer_ok = False

            # Politica:
            # - Si no hay cookie de auth, permitir (endpoint publico como /auth/login).
            # - Si hay auth cookie + csrf_token cookie => obligar CSRF header match (estricto).
            # - Si hay auth cookie sin csrf cookie (legacy) => permitir con origen valido.
            if has_auth_cookie:
                if csrf_cookie:
                    if not csrf_ok:
                        logger.warning(f"CSRF block (double-submit): {request.method} {path} csrf_cookie_present={bool(csrf_cookie)} header_present={bool(csrf_header)} match={csrf_ok}")
                        return Response(
                            status_code=403,
                            content='{"detail":"CSRF token invalido"}',
                            media_type="application/json",
                        )
                elif not (origin_ok or referer_ok):
                    logger.warning(f"CSRF block (origin fallback): {request.method} {path} origin='{origin}' referer='{referer[:100]}' host='{request.headers.get('host', '')}' xfh='{request.headers.get('x-forwarded-host', '')}'")
                    return Response(
                        status_code=403,
                        content='{"detail":"Origen no autorizado"}',
                        media_type="application/json",
                    )

    response = await call_next(request)
    if allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Vary"] = "Origin"

    # Security headers (Feb 2026): defense in depth para XSS/clickjacking/MIME sniffing.
    # No re-aplicar si la respuesta es de assets estaticos servidos por otro proxy.
    path = request.url.path
    if path.startswith("/api"):
        # Solo para responses de la API (que son JSON): headers minimos
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        # CSP para responses del API - restrictivo (no debe cargar recursos):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
    else:
        # HTML del frontend (React SPA) - CSP mas permisivo pero con reporting
        # Recursos externos permitidos:
        # - Google Fonts (fonts.googleapis.com CSS, fonts.gstatic.com WOFF2)
        # - Stripe (js.stripe.com + api.stripe.com para checkout)
        # - customer-assets.emergentagent.com (assets del cliente)
        # - Emergent object storage (imagenes de logos y attachments)
        # - wa.me (whatsapp links via <a href>)
        # 'unsafe-inline' requerido por Create React App (bootstrap scripts) y Tailwind.
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' data: https://fonts.gstatic.com",
            "img-src 'self' data: blob: https:",
            "connect-src 'self' https: wss:",
            "frame-src 'self' https://js.stripe.com https://hooks.stripe.com",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self' https://checkout.stripe.com",
            "object-src 'none'",
            "upgrade-insecure-requests",
            "report-uri /api/security/csp-report",
            "report-to csp-endpoint",
        ]
        response.headers.setdefault("Content-Security-Policy", "; ".join(csp_directives))
        # Reporting API endpoint
        response.headers.setdefault(
            "Report-To",
            '{"group":"csp-endpoint","max_age":10886400,"endpoints":[{"url":"/api/security/csp-report"}]}'
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

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

    # Sessions (Panel Sesiones Activas)
    await db.sessions.create_index("session_id", unique=True)
    await db.sessions.create_index([("user_id", 1), ("revoked", 1), ("last_activity_at", -1)])
    await db.sessions.create_index([("company_id", 1), ("revoked", 1), ("last_activity_at", -1)])
    # TTL: purga sesiones tras 7d de inactividad
    try:
        await db.sessions.create_index("last_activity_at", expireAfterSeconds=604800, name="sessions_ttl")
    except Exception:
        pass

    # --- CSP violations (TTL 30 dias) ---
    try:
        await db.csp_violations.create_index("created_at", expireAfterSeconds=2592000, name="csp_ttl")
        await db.csp_violations.create_index([("violated_directive", 1), ("created_at", -1)])
        await db.csp_violations.create_index([("ip", 1), ("created_at", -1)])
    except Exception:
        pass

    # --- Blocked IPs (TTL sobre blocked_until para auto-unblock) ---
    try:
        await db.blocked_ips.create_index("ip", unique=True)
        await db.blocked_ips.create_index("blocked_until", expireAfterSeconds=0, name="blocked_ips_ttl")
    except Exception:
        pass

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
    await db.companies.create_index([("billing_state", 1)])

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

    # --- Cash registers ---
    await db.cash_registers.create_index([("company_id", 1), ("branch_id", 1), ("status", 1)])
    await db.cash_registers.create_index([("company_id", 1), ("opened_at", -1)])

    # --- Support tickets ---
    await db.support_tickets.create_index([("created_by", 1), ("_id", -1)])
    await db.support_tickets.create_index([("status", 1), ("_id", -1)])
    await db.support_tickets.create_index([("company_id", 1), ("_id", -1)])

    # --- Payment transactions ---
    await db.payment_transactions.create_index([("session_id", 1)], unique=True)
    await db.payment_transactions.create_index([("company_id", 1), ("_id", -1)])
    await db.payment_transactions.create_index([("payment_status", 1)])

    # --- Jornadas ---
    await db.jornadas.create_index([("company_id", 1), ("status", 1), ("start_date", -1)])
    await db.jornadas.create_index([("company_id", 1), ("responsible_branch_id", 1), ("start_date", -1)])
    await db.jornadas.create_index([("company_id", 1), ("is_deleted", 1), ("start_date", -1)])
    await db.jornadas.create_index([("company_id", 1), ("name", 1)])
    # Iter 2: operativos (caja, inventario, ventas, pacientes)
    await db.jornada_stock.create_index([("company_id", 1), ("jornada_id", 1), ("product_id", 1)])
    await db.jornada_stock.create_index([("company_id", 1), ("jornada_id", 1), ("source", 1)])
    await db.jornada_transfers.create_index([("company_id", 1), ("jornada_id", 1), ("created_at", -1)])
    await db.cash_registers.create_index([("company_id", 1), ("jornada_id", 1), ("status", 1)])
    await db.sales.create_index([("company_id", 1), ("jornada_id", 1), ("_id", -1)])
    await db.patients.create_index([("company_id", 1), ("jornada_ids", 1)])

    # --- Email queue (cola durable de correos con reintentos) ---
    await db.email_queue.create_index([("status", 1), ("next_attempt_at", 1)])
    await db.email_queue.create_index("completed_at", expireAfterSeconds=604800, name="email_queue_ttl")  # purga enviados/fallidos a los 7d

    # --- Captacion de leads (global) ---
    await db.leads.create_index("email", unique=True)
    await db.leads.create_index([("created_at", -1)])
    await db.leads.create_index("promo_code")
    await db.leads.create_index("source")
    await db.leads.create_index("whatsapp")
    await db.promo_codes.create_index("code", unique=True)

    # --- Autoservicio de registro (verificacion de correo) ---
    await db.pending_registrations.create_index("token", unique=True)
    await db.pending_registrations.create_index("email")
    await db.pending_registrations.create_index("created_at")

    # --- Enlaces de comparticion de recetas (WhatsApp) con expiracion (TTL) ---
    await db.rx_share_links.create_index("token", unique=True)
    await db.rx_share_links.create_index("expires_at", expireAfterSeconds=0)

    logger.info("MongoDB indexes verified/created OK")

    # ═══════════════════════════════════════════════════════════════════
    # Migracion: backfill first_login_at para admins existentes.
    # Sin esto, el activation_task_loop desactivaria ópticas antiguas
    # asumiendo que nunca activaron su cuenta (first_login_at es un
    # campo nuevo introducido en Feb 2026).
    # ═══════════════════════════════════════════════════════════════════
    try:
        # Admins sin first_login_at: usan created_at como fallback
        res_bf = await db.users.update_many(
            {"role": "admin", "first_login_at": {"$exists": False}, "created_at": {"$exists": True}},
            [{"$set": {"first_login_at": "$created_at"}}]
        )
        res_bf_null = await db.users.update_many(
            {"role": "admin", "first_login_at": None, "created_at": {"$exists": True}},
            [{"$set": {"first_login_at": "$created_at"}}]
        )
        res_cbf = await db.companies.update_many(
            {"admin_activated_at": {"$exists": False}, "created_at": {"$exists": True}},
            [{"$set": {"admin_activated_at": "$created_at"}}]
        )
        total_bf = res_bf.modified_count + res_bf_null.modified_count
        if total_bf > 0 or res_cbf.modified_count > 0:
            logger.info(f"Activation backfill: admins.first_login_at={total_bf}, companies.admin_activated_at={res_cbf.modified_count}")
    except Exception as e:
        logger.warning(f"Activation backfill error (non-fatal): {e}")
    
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
        # Demo password se toma de env DEMO_PASSWORD; si no existe, generamos una
        # aleatoria segura y la logueamos (visible SOLO en logs del primer boot).
        demo_password = (os.environ.get("DEMO_PASSWORD") or "").strip()
        if not demo_password:
            import secrets
            demo_password = secrets.token_urlsafe(12)
            logger.warning(
                "DEMO_PASSWORD no configurada — generada aleatoriamente para primer seed: "
                f"{demo_password} (guardala si necesitas login demo)"
            )
        company_result = await db.companies.insert_one({
            "name": "Cortexia Optical Demo", "legal_name": "Cortexia Optical S.A.",
            "tax_id": "12345678-9", "address": "6ta Avenida 12-34, Zona 1, Ciudad de Guatemala",
            "phone": "+502 2234-5678", "email": "info@cortexia.gt",
            "is_active": True, "created_at": datetime.now(timezone.utc).isoformat()
        })
        company_id = company_result.inserted_id
        await db.users.insert_one({
            "email": "admin@cortexia.gt", "password_hash": hash_password(demo_password),
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
            "email": "vendedor@cortexia.gt", "password_hash": hash_password(demo_password),
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
                "currency": "USD",
                "max_branches": 1,
                "max_patients": 50,
                "modules": [],
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "name": "Basic",
                "price": 299,
                "currency": "USD",
                "max_branches": 3,
                "max_patients": 500,
                "modules": ["inventario", "ventas", "jornadas"],
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "name": "Enterprise",
                "price": 799,
                "currency": "USD",
                "max_branches": 0,
                "max_patients": 0,
                "modules": ["inventario", "ventas", "proveedores", "finanzas", "jornadas"],
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

    # Migracion idempotente: la membresia se cobra en USD.
    # Convierte planes sin moneda o en GTQ a USD (no toca planes ya en otra moneda).
    _cur_migration = await db.plans.update_many(
        {"$or": [{"currency": {"$exists": False}}, {"currency": {"$in": ["GTQ", "gtq"]}}]},
        {"$set": {"currency": "USD"}},
    )
    if _cur_migration.modified_count:
        logger.info(f"Plan currency migration: {_cur_migration.modified_count} plan(s) set to USD")

    # ═══════════════════════════════════════════════════════════════════
    # Object Storage init (multi-pod safe uploads)
    # ═══════════════════════════════════════════════════════════════════
    try:
        import object_storage as _objstore
        if _objstore.is_enabled():
            _objstore.init_storage()
            logger.info("Object storage initialized (Emergent)")
        else:
            logger.warning("Object storage disabled (EMERGENT_LLM_KEY missing) — using local filesystem")
    except Exception as e:
        logger.error(f"Object storage init error: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # Cache backend init (Redis compartido si REDIS_URL disponible)
    # ═══════════════════════════════════════════════════════════════════
    try:
        import cache as _cache
        await _cache.init_cache()
    except Exception as e:
        logger.error(f"Cache init error: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # Task de activacion de opticas (recordatorios + desactivacion 30 dias)
    # ═══════════════════════════════════════════════════════════════════
    try:
        import asyncio as _asyncio
        from activation_task import activation_task_loop
        _asyncio.create_task(activation_task_loop())
        logger.info("Activation task loop started (deadline=30d, checks every 12h)")
    except Exception as e:
        logger.error(f"Activation task init error: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # Worker de la cola durable de correos (reintentos + backoff)
    # ═══════════════════════════════════════════════════════════════════
    try:
        import asyncio as _asyncio
        from email_service import email_worker_loop
        _asyncio.create_task(email_worker_loop())
        logger.info("Email worker loop scheduled")
    except Exception as e:
        logger.error(f"Email worker init error: {e}")

@app.on_event("shutdown")
async def shutdown():
    client.close()
