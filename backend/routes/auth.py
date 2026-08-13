from fastapi import APIRouter, HTTPException, Depends, Request, Response
from bson import ObjectId
from datetime import datetime, timezone, timedelta
import os

from db import db
from auth_utils import (
    get_current_user, hash_password, verify_password,
    create_access_token, create_refresh_token, get_jwt_secret, JWT_ALGORITHM,
    get_real_ip, validate_password_strength
)
from models import UserRegister, UserLogin, ChangePassword, ForgotPassword, ResetPassword
from rate_limiter import limiter
from audit import log_audit
from email_service import queue_email, render_password_reset, render_security_alert
from routes.settings import get_role_permissions
import jwt
import secrets

router = APIRouter(prefix="/auth", tags=["Autenticacion"])

def _get_cookie_samesite():
    """Get SameSite cookie value. 'none' works for both same-origin and cross-origin with Secure=true."""
    return os.environ.get("COOKIE_SAMESITE", "none")

def _set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Set auth cookies with production-compatible settings."""
    ss = _get_cookie_samesite()
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite=ss, max_age=86400, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite=ss, max_age=604800, path="/")

def _clear_auth_cookies(response: Response):
    """Clear auth cookies with production-compatible settings."""
    ss = _get_cookie_samesite()
    response.delete_cookie("access_token", path="/", secure=True, samesite=ss)
    response.delete_cookie("refresh_token", path="/", secure=True, samesite=ss)

@router.post("/register")
async def register(data: UserRegister, response: Response):
    # Endpoint deshabilitado por seguridad. La creacion de usuarios solo se hace
    # via /api/users (requiere admin/superadmin) o via /api/companies/register
    # cuando un superadmin crea una nueva empresa con su admin.
    raise HTTPException(status_code=403, detail="Registro publico deshabilitado. Contacte al administrador.")

@router.post("/login")
@limiter.limit("10/minute")
async def login(data: UserLogin, response: Response, request: Request):
    email = data.email.lower()
    
    # Brute force check usando IP real (X-Forwarded-For)
    ip = get_real_ip(request)
    identifier = f"{ip}:{email}"
    try:
        attempt = await db.login_attempts.find_one({"identifier": identifier})
        if attempt and attempt.get("count", 0) >= 5:
            lockout_until = attempt.get("lockout_until")
            if lockout_until:
                try:
                    if datetime.fromisoformat(lockout_until) > datetime.now(timezone.utc):
                        raise HTTPException(status_code=429, detail="Demasiados intentos. Intente en 15 minutos.")
                except (ValueError, TypeError):
                    pass
            await db.login_attempts.delete_one({"identifier": identifier})
    except HTTPException:
        raise
    except Exception:
        pass
    
    user = await db.users.find_one({"email": email})
    if not user:
        await increment_login_attempts(identifier)
        await log_audit("LOGIN_FAILED", actor_email=email, metadata={"reason": "user_not_found"}, request=request)
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    
    # Verify password safely
    try:
        pw_hash = user.get("password_hash", "")
        if not pw_hash or not verify_password(data.password, pw_hash):
            attempts = await increment_login_attempts(identifier)
            await log_audit("LOGIN_FAILED", actor_id=str(user["_id"]), actor_email=email,
                            metadata={"reason": "wrong_password", "attempts": attempts}, request=request)
            # Alerta de seguridad cuando se alcanzan 3 intentos fallidos
            if attempts == 3:
                app_url = os.environ.get("APP_URL", "https://cortexiaoptical.com")
                ip = (request.headers.get("X-Forwarded-For", "") or "").split(",")[0].strip() or (request.client.host if request.client else "n/a")
                html = render_security_alert(
                    name=user.get("name", "Usuario"),
                    event_title="Multiples intentos fallidos de login",
                    event_description="Se han detectado varios intentos fallidos de inicio de sesion en tu cuenta. Si fuiste tu olvidando tu contrasena, usa la opcion de restablecer contrasena. Si no, alguien podria estar intentando acceder.",
                    event_meta={
                        "Email": email,
                        "Intentos fallidos": str(attempts),
                        "IP de origen": ip,
                        "Fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                    },
                    app_url=app_url,
                )
                queue_email(email, "[Cortexia] Intentos fallidos de inicio de sesion", html, tag="security_alert")
            raise HTTPException(status_code=401, detail="Credenciales invalidas")
    except HTTPException:
        raise
    except Exception:
        await increment_login_attempts(identifier)
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    
    if not user.get("is_active", True):
        await log_audit("LOGIN_FAILED", actor_id=str(user["_id"]), actor_email=email,
                        metadata={"reason": "account_disabled"}, request=request)
        raise HTTPException(status_code=403, detail="Cuenta desactivada")
    
    try:
        await db.login_attempts.delete_one({"identifier": identifier})
    except Exception:
        pass
    
    user_id = str(user["_id"])
    company_id = str(user["company_id"]) if user.get("company_id") else None
    
    # Tracking de activacion / actividad
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    is_first_login = not user.get("first_login_at")
    login_updates = {"last_login_at": now_iso}
    if is_first_login:
        login_updates["first_login_at"] = now_iso
    try:
        await db.users.update_one({"_id": user["_id"]}, {"$set": login_updates})
    except Exception:
        pass
    # Notificar al SuperAdmin cuando el admin de una nueva optica hace su PRIMER login
    if is_first_login and user.get("role") == "admin" and user.get("company_id"):
        try:
            company = await db.companies.find_one({"_id": user["company_id"]}, {"name": 1})
            company_name = company.get("name", "Optica") if company else "Optica"
            await db.companies.update_one(
                {"_id": user["company_id"]},
                {"$set": {"admin_activated_at": now_iso}}
            )
            from routes.notifications import create_notification
            await create_notification(
                event_type="admin_first_login",
                title="Optica activada",
                message=f"El administrador de {company_name} ({email}) inicio sesion por primera vez",
                metadata={"company_id": str(user["company_id"]), "company_name": company_name, "admin_email": email}
            )
            await log_audit("ADMIN_FIRST_LOGIN", actor_id=user_id, actor_email=email,
                            actor_role="admin", company_id=str(user["company_id"]),
                            metadata={"company_name": company_name}, request=request)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"admin_first_login side-effects failed: {e}")
    
    access_token = create_access_token(user_id, email, user["role"], company_id)
    refresh_token = create_refresh_token(user_id)
    
    _set_auth_cookies(response, access_token, refresh_token)
    await log_audit("LOGIN_SUCCESS", actor_id=user_id, actor_email=email,
                    actor_role=user["role"], company_id=company_id, request=request)
    
    result = {
        "_id": user_id, "email": user["email"], "name": user["name"], "role": user["role"],
        "company_id": company_id, "branch_id": str(user["branch_id"]) if user.get("branch_id") else None
    }
    # Attach plan info (non-blocking — login must never fail due to plan queries)
    if company_id and user["role"] != "superadmin":
        try:
            company = await db.companies.find_one(
                {"_id": ObjectId(company_id)},
                {"plan_id": 1, "needs_reactivation_feedback": 1}
            )
            if company:
                # Flag para dialogo de feedback post-reactivacion (solo admins)
                if user["role"] == "admin" and company.get("needs_reactivation_feedback"):
                    result["needs_reactivation_feedback"] = True
                if company.get("plan_id"):
                    plan = await db.plans.find_one({"_id": company["plan_id"]})
                    if plan:
                        result["plan_name"] = plan["name"]
                        result["plan_modules"] = plan.get("modules", [])
                        result["max_patients"] = plan.get("max_patients", 0)
                        result["max_branches"] = plan.get("max_branches", 0)
                        patients_count = await db.patients.count_documents({"company_id": ObjectId(company_id), "is_deleted": {"$ne": True}})
                        branches_count = await db.branches.count_documents({"company_id": ObjectId(company_id)})
                        result["patients_count"] = patients_count
                        result["branches_count"] = branches_count
                        max_p = plan.get("max_patients", 0)
                        max_b = plan.get("max_branches", 0)
                        result["patients_warning"] = max_p > 0 and patients_count >= max_p * 0.8
                        result["branches_warning"] = max_b > 0 and branches_count >= max_b * 0.8
                        result["patients_limit_reached"] = max_p > 0 and patients_count >= max_p
                        result["branches_limit_reached"] = max_b > 0 and branches_count >= max_b
            # Permisos por rol (allowed_menu_items = null si admin)
            try:
                result["allowed_menu_items"] = await get_role_permissions(ObjectId(company_id), user["role"])
            except Exception:
                result["allowed_menu_items"] = None
        except Exception:
            pass
    return result

async def increment_login_attempts(identifier: str) -> int:
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt:
        new_count = attempt.get("count", 0) + 1
        update = {"count": new_count}
        if new_count >= 5:
            update["lockout_until"] = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        await db.login_attempts.update_one({"identifier": identifier}, {"$set": update})
        return new_count
    else:
        await db.login_attempts.insert_one({"identifier": identifier, "count": 1})
        return 1

@router.post("/logout")
async def logout(request: Request, response: Response):
    # Intentar identificar al usuario (sin requerir auth para que /logout siempre funcione)
    user_id = None
    email = None
    role = None
    try:
        token = request.cookies.get("access_token")
        if token:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
            user_id = payload.get("sub")
            email = payload.get("email")
            role = payload.get("role")
    except Exception:
        pass
    # Invalida TODOS los tokens del usuario incrementando password_changed_at
    # (efectivamente revoca access + refresh tokens emitidos antes de este momento)
    # Usamos +1s para garantizar que cualquier token con iat <= now sea invalidado
    if user_id:
        try:
            now_ts = int(datetime.now(timezone.utc).timestamp()) + 1
            await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"password_changed_at": now_ts}}
            )
        except Exception:
            pass
        await log_audit("LOGOUT", actor_id=user_id, actor_email=email, actor_role=role, request=request)
    _clear_auth_cookies(response)
    return {"message": "Sesion cerrada"}

@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    # Attach plan info for non-superadmin users (non-blocking)
    if user.get("company_id") and user["role"] != "superadmin":
        try:
            company = await db.companies.find_one(
                {"_id": ObjectId(user["company_id"])},
                {"plan_id": 1, "needs_reactivation_feedback": 1}
            )
            if company:
                # Flag para dialogo de feedback post-reactivacion (solo admins)
                if user["role"] == "admin" and company.get("needs_reactivation_feedback"):
                    user["needs_reactivation_feedback"] = True
                if company.get("plan_id"):
                    plan = await db.plans.find_one({"_id": company["plan_id"]})
                    if plan:
                        user["plan_name"] = plan["name"]
                        user["plan_modules"] = plan.get("modules", [])
                        user["max_patients"] = plan.get("max_patients", 0)
                        user["max_branches"] = plan.get("max_branches", 0)
                        patients_count = await db.patients.count_documents({"company_id": ObjectId(user["company_id"]), "is_deleted": {"$ne": True}})
                        branches_count = await db.branches.count_documents({"company_id": ObjectId(user["company_id"])})
                        user["patients_count"] = patients_count
                        user["branches_count"] = branches_count
                        max_p = plan.get("max_patients", 0)
                        max_b = plan.get("max_branches", 0)
                        user["patients_warning"] = max_p > 0 and patients_count >= max_p * 0.8
                        user["branches_warning"] = max_b > 0 and branches_count >= max_b * 0.8
                        user["patients_limit_reached"] = max_p > 0 and patients_count >= max_p
                        user["branches_limit_reached"] = max_b > 0 and branches_count >= max_b
            # Permisos por rol
            try:
                user["allowed_menu_items"] = await get_role_permissions(ObjectId(user["company_id"]), user["role"])
            except Exception:
                user["allowed_menu_items"] = None
        except Exception:
            pass
    return user

@router.post("/change-password")
@limiter.limit("5/minute")
async def change_password(data: ChangePassword, request: Request, user: dict = Depends(get_current_user)):
    """Permite que cualquier usuario autenticado cambie su propia contraseña."""
    is_valid, msg = validate_password_strength(data.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)
    db_user = await db.users.find_one({"_id": ObjectId(user["_id"])})
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not verify_password(data.current_password, db_user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    # Revoca todos los tokens emitidos antes de este momento (+1s para tokens del mismo segundo)
    now_ts = int(datetime.now(timezone.utc).timestamp()) + 1
    await db.users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {
            "password_hash": hash_password(data.new_password),
            "password_changed_at": now_ts,
        }}
    )
    await log_audit("PASSWORD_CHANGED", actor_id=user["_id"], actor_email=user.get("email"),
                    actor_role=user.get("role"), company_id=user.get("company_id"), request=request)
    # Alerta de seguridad por email
    if user.get("email"):
        app_url = os.environ.get("APP_URL", "https://cortexiaoptical.com")
        html = render_security_alert(
            name=user.get("name", "Usuario"),
            event_title="Tu contrasena fue cambiada",
            event_description="La contrasena de tu cuenta acaba de ser modificada. Si fuiste tu, puedes ignorar este mensaje.",
            event_meta={
                "Email": user.get("email"),
                "IP": (request.headers.get("X-Forwarded-For", "") or "").split(",")[0].strip() or (request.client.host if request.client else "n/a"),
                "Fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            },
            app_url=app_url,
        )
        queue_email(user["email"], "[Cortexia] Tu contrasena fue cambiada", html, tag="security_alert")
    return {"message": "Contraseña actualizada correctamente"}


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(data: ForgotPassword, request: Request):
    """Solicita un email para restablecer la contrasena. Respuesta neutra: siempre 200
    para no revelar si el email existe (anti-enumeration)."""
    email = data.email.lower().strip()
    neutral_response = {"message": "Si el email existe, recibiras instrucciones para restablecer tu contrasena."}
    user = await db.users.find_one({"email": email})
    if not user or not user.get("is_active", True):
        return neutral_response
    # Generar token seguro
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.password_resets.insert_one({
        "user_id": user["_id"],
        "email": email,
        "token": token,
        "expires_at": expires_at,
        "used": False,
        "created_at": datetime.now(timezone.utc),
        "ip": (request.headers.get("X-Forwarded-For", "") or "").split(",")[0].strip() or (request.client.host if request.client else None),
    })
    app_url = os.environ.get("APP_URL", "https://cortexiaoptical.com")
    reset_link = f"{app_url.rstrip('/')}/reset-password?token={token}"
    html = render_password_reset(name=user.get("name", "Usuario"), reset_link=reset_link)
    queue_email(email, "[Cortexia] Restablece tu contrasena", html, tag="password_reset")
    await log_audit("PASSWORD_RESET_REQUESTED", actor_id=str(user["_id"]), actor_email=email,
                    actor_role=user.get("role"), request=request)
    return neutral_response


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(data: ResetPassword, request: Request):
    """Aplica el reset usando el token recibido por email."""
    from auth_utils import validate_password_strength
    is_valid, msg = validate_password_strength(data.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)
    reset = await db.password_resets.find_one({"token": data.token})
    if not reset:
        raise HTTPException(status_code=400, detail="Token invalido o ya utilizado")
    if reset.get("used"):
        raise HTTPException(status_code=400, detail="Token ya fue utilizado")
    expires = reset.get("expires_at")
    if expires:
        # Normalizar a UTC si viene sin tzinfo
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Token expirado. Solicita un nuevo enlace.")
    user = await db.users.find_one({"_id": reset["user_id"]})
    if not user:
        raise HTTPException(status_code=400, detail="Usuario no encontrado")
    # Aplicar nuevo password + invalidar tokens existentes
    now_ts = int(datetime.now(timezone.utc).timestamp()) + 1
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(data.new_password), "password_changed_at": now_ts}}
    )
    await db.password_resets.update_one({"_id": reset["_id"]}, {"$set": {"used": True, "used_at": datetime.now(timezone.utc)}})
    await log_audit("PASSWORD_RESET_COMPLETED", actor_id=str(user["_id"]), actor_email=user.get("email"),
                    actor_role=user.get("role"), company_id=str(user.get("company_id")) if user.get("company_id") else None,
                    request=request)
    # Alerta por email
    app_url = os.environ.get("APP_URL", "https://cortexiaoptical.com")
    html = render_security_alert(
        name=user.get("name", "Usuario"),
        event_title="Contrasena restablecida exitosamente",
        event_description="Acabas de restablecer la contrasena de tu cuenta usando el enlace que recibiste por email. Ya puedes ingresar con la nueva contrasena.",
        event_meta={
            "Email": user.get("email"),
            "IP": (request.headers.get("X-Forwarded-For", "") or "").split(",")[0].strip() or (request.client.host if request.client else "n/a"),
            "Fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        },
        app_url=app_url,
    )
    queue_email(user["email"], "[Cortexia] Contrasena restablecida", html, tag="security_alert")
    return {"message": "Contrasena restablecida correctamente. Ya puedes iniciar sesion."}

@router.post("/refresh")
@limiter.limit("30/minute")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No hay token de refresco")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Tipo de token invalido")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        # Verificar que la cuenta este activa
        if not user.get("is_active", True):
            raise HTTPException(status_code=401, detail="Cuenta desactivada")
        # Verificar que el refresh token no haya sido invalidado por cambio de password
        token_iat = payload.get("iat", 0)
        pw_changed_at = user.get("password_changed_at", 0)
        if pw_changed_at and token_iat < pw_changed_at:
            raise HTTPException(status_code=401, detail="Sesion invalidada. Inicie sesion nuevamente.")
        
        user_id = str(user["_id"])
        company_id = str(user["company_id"]) if user.get("company_id") else None
        access_token = create_access_token(user_id, user["email"], user["role"], company_id)
        ss = _get_cookie_samesite()
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite=ss, max_age=86400, path="/")
        return {"message": "Token renovado"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalido")
