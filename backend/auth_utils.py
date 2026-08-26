from fastapi import Request, HTTPException
from bson import ObjectId
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import os
import re

from db import db

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
REFRESH_TOKEN_EXPIRE_DAYS = 7

def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]

def get_real_ip(request: Request) -> str:
    """Obtiene la IP real del cliente respetando la topologia trusted-proxy (SEC-001 fix Feb 2026).

    Orden de prioridad:
    1. `CF-Connecting-IP` (Cloudflare — cuando la app esta detras de CF; imposible de spoofear).
    2. **Rightmost** de `X-Forwarded-For` (el hop del proxy trusted mas cercano; los valores a la
       izquierda son controlables por el cliente y NO se deben usar para blocking/rate-limit).
    3. `X-Real-IP` (algunos ingress lo setean).
    4. `request.client.host` (conexion directa).

    IMPORTANTE: nunca uses leftmost XFF. Un anonimo podria falsificarlo y provocar bans
    dirigidos a IPs de victimas via /api/security/csp-report o saltarse rate limits.
    """
    cf_ip = request.headers.get("CF-Connecting-IP", "").strip()
    if cf_ip:
        return cf_ip
    xff = request.headers.get("X-Forwarded-For", "").strip()
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            # rightmost = el ultimo hop trusted; en preview/prod Emergent es la IP real del cliente
            return parts[-1]
    real_ip = request.headers.get("X-Real-IP", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"

def validate_password_strength(password: str) -> tuple[bool, str]:
    """Valida la fortaleza de una contrasena. Retorna (es_valida, mensaje_error)."""
    if not password or len(password) < 8:
        return False, "La contrasena debe tener al menos 8 caracteres"
    if not re.search(r"[A-Z]", password):
        return False, "La contrasena debe contener al menos una letra mayuscula"
    if not re.search(r"[a-z]", password):
        return False, "La contrasena debe contener al menos una letra minuscula"
    if not re.search(r"\d", password):
        return False, "La contrasena debe contener al menos un digito"
    return True, ""

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(user_id: str, email: str, role: str, company_id: str = None, session_id: str = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id, "email": email, "role": role, "company_id": company_id,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access"
    }
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str, session_id: str = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh"
    }
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

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
        # Verificacion de cuenta activa
        if not user.get("is_active", True):
            raise HTTPException(status_code=401, detail="Cuenta desactivada")
        # Verificacion de company activa (P3 hardening Feb 2026):
        # si la optica esta desactivada, bloquea a TODOS los usuarios (incluyendo staff no-admin)
        # excepto superadmin. Sin esto, staff podia seguir operando en una optica deshabilitada.
        if user.get("company_id") and user.get("role") != "superadmin":
            try:
                company = await db.companies.find_one(
                    {"_id": ObjectId(user["company_id"])}, {"is_active": 1}
                )
                if company and company.get("is_active") is False:
                    raise HTTPException(status_code=401, detail="Optica desactivada. Contacta al equipo de Cortexia.")
            except HTTPException:
                raise
            except Exception:
                pass
        # Revocacion de tokens emitidos antes del ultimo cambio de password
        token_iat = payload.get("iat", 0)
        pw_changed_at = user.get("password_changed_at", 0)
        if pw_changed_at and token_iat < pw_changed_at:
            raise HTTPException(status_code=401, detail="Sesion invalidada. Inicie sesion nuevamente.")
        # Validacion de sesion: si el JWT tiene sid, verificar que la sesion no este revocada
        session_id = payload.get("sid")
        if session_id:
            try:
                session = await db.sessions.find_one({"session_id": session_id})
            except Exception:
                session = None
            if session and session.get("revoked"):
                raise HTTPException(status_code=401, detail="Sesion revocada. Inicie sesion nuevamente.")
            # Refresca last_activity_at con throttling: solo si han pasado >30s desde el ultimo update.
            # Reduce carga de escrituras en apps chatty sin perder precision para el panel.
            if session:
                now_utc = datetime.now(timezone.utc)
                last_act = session.get("last_activity_at")
                should_update = True
                if isinstance(last_act, datetime):
                    if last_act.tzinfo is None:
                        last_act = last_act.replace(tzinfo=timezone.utc)
                    if (now_utc - last_act).total_seconds() < 30:
                        should_update = False
                if should_update:
                    try:
                        await db.sessions.update_one(
                            {"session_id": session_id},
                            {"$set": {"last_activity_at": now_utc}}
                        )
                    except Exception:
                        pass
            # Guardar sid en el user context para uso downstream (endpoints de sesiones)
            user["current_session_id"] = session_id
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
