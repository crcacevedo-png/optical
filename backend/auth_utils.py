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
    """Obtiene la IP real del cliente respetando X-Forwarded-For (detras de proxy/ingress).
    Toma el PRIMER IP de la cadena que es el cliente original.
    """
    xff = request.headers.get("X-Forwarded-For", "").strip()
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
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

def create_access_token(user_id: str, email: str, role: str, company_id: str = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id, "email": email, "role": role, "company_id": company_id,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh"
    }
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
        # Revocacion de tokens emitidos antes del ultimo cambio de password
        token_iat = payload.get("iat", 0)
        pw_changed_at = user.get("password_changed_at", 0)
        if pw_changed_at and token_iat < pw_changed_at:
            raise HTTPException(status_code=401, detail="Sesion invalidada. Inicie sesion nuevamente.")
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
