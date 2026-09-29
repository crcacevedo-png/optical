"""Autoservicio de registro (Plan Basico) con verificacion de correo (doble opt-in).

Flujo:
1. POST /api/registration          -> PUBLICO: valida datos, hashea el password,
   guarda un registro PENDIENTE (pending_registrations) con token seguro (48h) y
   envia el correo de verificacion. NO crea la optica todavia.
2. POST /api/registration/verify   -> valida el token y PROVISIONA la optica + usuario
   admin, asigna el plan de autoservicio (Free/Basico) y aplica el limite de pacientes
   del codigo de promocion si aplica. Idempotente (doble clic seguro).
3. POST /api/registration/resend   -> reenvia el correo de verificacion.

Reglas anti-abuso: rate-limit, honeypot (`website`), consentimiento obligatorio.
La creacion real de la cuenta ocurre SOLO al hacer clic en el enlace de verificacion.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from pymongo import ReturnDocument
from datetime import datetime, timezone, timedelta
from typing import Optional
import os
import re
import logging
import secrets

from db import db
from auth_utils import get_real_ip, hash_password, validate_password_strength
from audit import log_audit
from rate_limiter import limiter
from routes.notifications import create_notification
from email_service import queue_email, render_verify_registration, render_welcome_self_service

router = APIRouter(prefix="/registration", tags=["Registro (autoservicio)"])

logger = logging.getLogger(__name__)

VERIFY_TOKEN_HOURS = int(os.environ.get("REGISTRATION_VERIFY_HOURS", "48"))
DEFAULT_FREE_PATIENT_LIMIT = 50

CONSENT_TEXT = (
    "Acepto que Cortexia Optical utilice mis datos para crear y administrar mi cuenta, "
    "y para contactarme por WhatsApp y correo electronico. Mis datos seran tratados de "
    "forma confidencial y puedo solicitar su eliminacion cuando lo desee."
)


def _app_url() -> str:
    return os.environ.get("APP_URL", "https://www.cortexiaoptical.com").strip().rstrip("/")


def _normalize_wa(raw: str) -> str:
    """Devuelve solo digitos; antepone 502 (Guatemala) si son 8 digitos locales."""
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if len(digits) == 8:
        digits = "502" + digits
    return digits


def _to_aware(dt):
    if isinstance(dt, datetime) and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _resolve_self_service_plan() -> Optional[dict]:
    """Plan que se asigna al registrarse por autoservicio.
    Prioridad: 1) plan marcado is_self_service_default; 2) plan gratuito ('Free' o price 0);
    3) el plan activo mas economico."""
    plan = await db.plans.find_one({"is_self_service_default": True, "is_active": {"$ne": False}})
    if plan:
        return plan
    plan = await db.plans.find_one({"name": "Free"})
    if plan:
        return plan
    plan = await db.plans.find_one({"$or": [{"price": 0}, {"price_monthly": 0}], "is_active": {"$ne": False}})
    if plan:
        return plan
    plans = await db.plans.find({"is_active": {"$ne": False}}).sort("price", 1).to_list(1)
    return plans[0] if plans else None


async def _resolve_promo(code_input: str):
    """Devuelve (codigo_matcheado|None, patient_limit|None) para un codigo activo."""
    code = (code_input or "").strip().upper()
    if not code:
        return None, None
    pc = await db.promo_codes.find_one({"code": code, "is_active": True})
    if not pc:
        return None, None
    pl = pc.get("patient_limit")
    limit = int(pl) if isinstance(pl, (int, float)) and pl and pl > 0 else None
    return pc["code"], limit


# ─────────────────────────── SUBMIT (PUBLICO) ───────────────────────────
class RegistrationSubmit(BaseModel):
    name: str
    optica_name: str
    email: EmailStr
    password: str
    whatsapp: str
    location: Optional[str] = ""
    promo_code: Optional[str] = ""
    consent: bool = False
    source: Optional[str] = None
    source_details: Optional[dict] = None
    website: Optional[str] = ""  # honeypot: los humanos lo dejan vacio


async def _send_verification_email(reg: dict):
    verify_link = f"{_app_url()}/verificar-cuenta?token={reg['token']}"
    html_body = render_verify_registration(
        name=reg.get("name") or "",
        optica_name=reg.get("optica_name") or "",
        verify_link=verify_link,
        hours=VERIFY_TOKEN_HOURS,
    )
    await queue_email(reg["email"], "Verifica tu correo para activar tu cuenta - Cortexia Optical",
                      html_body, tag="verify_registration")


@router.post("")
@limiter.limit("5/minute")
async def submit_registration(request: Request, data: RegistrationSubmit):
    # Honeypot: si viene lleno es un bot => fingimos exito sin guardar nada.
    if data.website:
        return {"ok": True, "message": "Revisa tu correo para verificar tu cuenta."}

    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio.")
    optica_name = (data.optica_name or "").strip()
    if not optica_name:
        raise HTTPException(status_code=400, detail="El nombre de la optica es obligatorio.")
    if not data.consent:
        raise HTTPException(status_code=400, detail="Debes aceptar el consentimiento para continuar.")

    wa_digits = _normalize_wa(data.whatsapp)
    if len(wa_digits) < 8:
        raise HTTPException(status_code=400, detail="El numero de WhatsApp no es valido.")
    whatsapp = "+" + wa_digits

    is_valid, msg = validate_password_strength(data.password or "")
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)

    email = str(data.email).strip().lower()
    if await db.users.find_one({"email": email}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con este correo. Inicia sesion o restablece tu contrasena.")

    matched_code, patient_limit = await _resolve_promo(data.promo_code or "")

    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(48)
    doc = {
        "name": name,
        "optica_name": optica_name,
        "email": email,
        "password_hash": hash_password(data.password),
        "whatsapp": whatsapp,
        "whatsapp_raw": (data.whatsapp or "").strip(),
        "location": (data.location or "").strip(),
        "promo_code": matched_code,
        "promo_code_input": (data.promo_code or "").strip().upper() or None,
        "patient_limit": patient_limit,
        "consent": True,
        "consent_text": CONSENT_TEXT,
        "source": (data.source or "").strip() or "no_especificado",
        "source_details": data.source_details or {},
        "token": token,
        "expires_at": now + timedelta(hours=VERIFY_TOKEN_HOURS),
        "verified": False,
        "company_id": None,
        "resend_count": 0,
        "ip": get_real_ip(request),
        "user_agent": (request.headers.get("user-agent") or "")[:300],
        "created_at": now.isoformat(),
    }
    # Reemplaza cualquier registro pendiente (no verificado) previo para este correo.
    await db.pending_registrations.replace_one({"email": email, "verified": {"$ne": True}}, doc, upsert=True)

    try:
        await _send_verification_email(doc)
    except Exception as e:
        logger.warning(f"No se pudo encolar el correo de verificacion para {email}: {e}")

    await log_audit("REGISTRATION_SUBMITTED", actor_email=email,
                    metadata={"optica": optica_name, "promo_code": matched_code}, request=request)
    return {
        "ok": True,
        "email": email,
        "message": "Te enviamos un correo para verificar tu cuenta. Revisa tu bandeja de entrada (y spam).",
    }


# ─────────────────────────── RESEND (PUBLICO) ───────────────────────────
class ResendRequest(BaseModel):
    email: EmailStr


@router.post("/resend")
@limiter.limit("3/minute")
async def resend_verification(request: Request, data: ResendRequest):
    neutral = {"ok": True, "message": "Si tu registro esta pendiente de verificacion, te reenviamos el enlace."}
    email = str(data.email).strip().lower()
    reg = await db.pending_registrations.find_one({"email": email, "verified": {"$ne": True}})
    if not reg:
        return neutral
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(48)
    await db.pending_registrations.update_one(
        {"_id": reg["_id"]},
        {"$set": {"token": token, "expires_at": now + timedelta(hours=VERIFY_TOKEN_HOURS)},
         "$inc": {"resend_count": 1}},
    )
    reg["token"] = token
    try:
        await _send_verification_email(reg)
    except Exception as e:
        logger.warning(f"No se pudo reenviar verificacion a {email}: {e}")
    return neutral


# ─────────────────────────── VERIFY (PUBLICO) ───────────────────────────
class VerifyRequest(BaseModel):
    token: str


async def _notify_new_self_service_company(company_id, company_name, admin_name, admin_email, promo_code):
    recipients = [u["email"] for u in await db.users.find(
        {"role": "superadmin", "is_active": True}, {"email": 1}).to_list(20) if u.get("email")]
    if not recipients:
        fb = os.environ.get("CORTEXIA_ALERTS_TO") or os.environ.get("ADMIN_EMAIL")
        if fb:
            recipients = [fb]
    subject = f"[Cortexia] Nueva optica por autoservicio: {company_name}"
    body = (
        "<h2>Nueva optica registrada por autoservicio</h2>"
        f"<p><b>Optica:</b> {company_name}</p>"
        f"<p><b>Admin:</b> {admin_name} ({admin_email})</p>"
        f"<p><b>Codigo de promocion:</b> {promo_code or 'Sin codigo'}</p>"
        "<p>La cuenta se creo y verifico automaticamente (Plan gratuito).</p>"
    )
    for em in recipients:
        await queue_email(em, subject, body, tag="new_self_service_company")
    await create_notification(
        "new_company", "Nueva optica por autoservicio",
        f"{company_name} - admin {admin_name} ({admin_email})",
        {"company_id": str(company_id), "company_name": company_name, "signup_source": "self_service"},
    )


@router.post("/verify")
@limiter.limit("20/minute")
async def verify_registration(request: Request, data: VerifyRequest):
    token = (data.token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Enlace de verificacion invalido.")
    reg = await db.pending_registrations.find_one({"token": token})
    if not reg:
        raise HTTPException(status_code=400, detail="Enlace de verificacion invalido o ya utilizado.")

    # Ya verificado (doble clic): respuesta idempotente.
    if reg.get("verified") and reg.get("company_id"):
        return {"ok": True, "already_verified": True, "email": reg.get("email"),
                "company_name": reg.get("optica_name")}

    exp = _to_aware(reg.get("expires_at"))
    if isinstance(exp, datetime) and exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="El enlace expiro. Solicita uno nuevo desde la pagina de registro.")

    email = (reg.get("email") or "").strip().lower()

    # Claim atomico: solo un verify concurrente provisiona.
    claimed = await db.pending_registrations.find_one_and_update(
        {"_id": reg["_id"], "verified": {"$ne": True}},
        {"$set": {"verified": True, "verified_at": datetime.now(timezone.utc).isoformat()}},
        return_document=ReturnDocument.AFTER,
    )
    if not claimed:
        fresh = await db.pending_registrations.find_one({"_id": reg["_id"]})
        return {"ok": True, "already_verified": True, "email": email,
                "company_name": (fresh or {}).get("optica_name")}

    # Si el correo ya se convirtio en usuario (por otra via), no dupliques.
    existing_user = await db.users.find_one({"email": email}, {"_id": 1, "company_id": 1})
    if existing_user:
        await db.pending_registrations.update_one(
            {"_id": reg["_id"]},
            {"$set": {"company_id": existing_user.get("company_id")}},
        )
        return {"ok": True, "already_verified": True, "email": email,
                "company_name": reg.get("optica_name")}

    try:
        plan = await _resolve_self_service_plan()
        now_iso = datetime.now(timezone.utc).isoformat()
        company_name = (reg.get("optica_name") or reg.get("name") or "Optica").strip()
        admin_name = (reg.get("name") or "Administrador").strip()
        whatsapp = reg.get("whatsapp") or ""

        company_doc = {
            "name": company_name, "legal_name": "", "tax_id": "",
            "address": reg.get("location") or "", "phone": whatsapp, "email": email,
            "contact_name": admin_name, "contact_phone": whatsapp, "contact_email": email,
            "is_active": True, "billing_state": "active",
            "signup_source": "self_service",
            "promo_code": reg.get("promo_code"),
            "created_at": now_iso,
        }
        if plan and plan.get("_id"):
            company_doc["plan_id"] = plan["_id"]
        # Codigo de promocion con beneficio: tope de pacientes gratuito ampliado.
        pl = reg.get("patient_limit")
        if isinstance(pl, int) and pl > 0:
            company_doc["patient_limit_override"] = pl

        result = await db.companies.insert_one(company_doc)
        company_id = result.inserted_id

        admin_doc = {
            "email": email, "password_hash": reg.get("password_hash"), "name": admin_name,
            "role": "admin", "company_id": company_id, "branch_id": None,
            "is_active": True, "email_verified": True, "created_at": now_iso,
        }
        try:
            await db.users.insert_one(admin_doc)
        except Exception:
            await db.companies.delete_one({"_id": company_id})
            raise HTTPException(status_code=409, detail="Ya existe un usuario con ese correo.")

        await db.pending_registrations.update_one(
            {"_id": reg["_id"]}, {"$set": {"company_id": company_id}})

        try:
            await _notify_new_self_service_company(company_id, company_name, admin_name, email, reg.get("promo_code"))
        except Exception as e:
            logger.warning(f"No se pudo notificar nueva optica autoservicio: {e}")

        try:
            welcome_html = render_welcome_self_service(
                admin_name=admin_name, company_name=company_name, login_link=_app_url())
            await queue_email(email, f"Bienvenido a Cortexia Optical - {company_name}",
                              welcome_html, tag="welcome_self_service")
        except Exception as e:
            logger.warning(f"No se pudo encolar correo de bienvenida a {email}: {e}")

        await log_audit("REGISTRATION_VERIFIED", actor_email=email,
                        metadata={"company_id": str(company_id), "company_name": company_name,
                                  "promo_code": reg.get("promo_code"),
                                  "plan": (plan or {}).get("name")},
                        request=request)
        return {"ok": True, "email": email, "company_name": company_name}
    except HTTPException:
        raise
    except Exception as e:
        # Rollback del claim para permitir reintento/reenvio.
        await db.pending_registrations.update_one(
            {"_id": reg["_id"]}, {"$set": {"verified": False}, "$unset": {"verified_at": ""}})
        logger.error(f"Fallo la provision de la cuenta para {email}: {e}")
        raise HTTPException(status_code=500, detail="No se pudo activar la cuenta. Intenta de nuevo en un momento.")
