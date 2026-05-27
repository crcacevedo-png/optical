from fastapi import APIRouter, HTTPException, Depends, Request, Response
from bson import ObjectId
from datetime import datetime, timezone, timedelta
import os

from db import db
from auth_utils import (
    get_current_user, hash_password, verify_password,
    create_access_token, create_refresh_token, get_jwt_secret, JWT_ALGORITHM
)
from models import UserRegister, UserLogin
import jwt

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
    email = data.email.lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="El email ya esta registrado")
    
    user_doc = {
        "email": email, "password_hash": hash_password(data.password), "name": data.name,
        "role": "user", "company_id": None, "branch_id": None, "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    access_token = create_access_token(user_id, email, "user")
    refresh_token = create_refresh_token(user_id)
    
    _set_auth_cookies(response, access_token, refresh_token)
    
    return {"_id": user_id, "email": email, "name": data.name, "role": "user"}

@router.post("/login")
async def login(data: UserLogin, response: Response, request: Request):
    email = data.email.lower()
    
    # Brute force check
    ip = request.client.host if request.client else "unknown"
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
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    
    # Verify password safely
    try:
        pw_hash = user.get("password_hash", "")
        if not pw_hash or not verify_password(data.password, pw_hash):
            await increment_login_attempts(identifier)
            raise HTTPException(status_code=401, detail="Credenciales invalidas")
    except HTTPException:
        raise
    except Exception:
        await increment_login_attempts(identifier)
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Cuenta desactivada")
    
    try:
        await db.login_attempts.delete_one({"identifier": identifier})
    except Exception:
        pass
    
    user_id = str(user["_id"])
    company_id = str(user["company_id"]) if user.get("company_id") else None
    access_token = create_access_token(user_id, email, user["role"], company_id)
    refresh_token = create_refresh_token(user_id)
    
    _set_auth_cookies(response, access_token, refresh_token)
    
    result = {
        "_id": user_id, "email": user["email"], "name": user["name"], "role": user["role"],
        "company_id": company_id, "branch_id": str(user["branch_id"]) if user.get("branch_id") else None
    }
    # Attach plan info (non-blocking — login must never fail due to plan queries)
    if company_id and user["role"] != "superadmin":
        try:
            company = await db.companies.find_one({"_id": ObjectId(company_id)}, {"plan_id": 1})
            if company and company.get("plan_id"):
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
        except Exception:
            pass
    return result

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

@router.post("/logout")
async def logout(response: Response):
    _clear_auth_cookies(response)
    return {"message": "Sesion cerrada"}

@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    # Attach plan info for non-superadmin users (non-blocking)
    if user.get("company_id") and user["role"] != "superadmin":
        try:
            company = await db.companies.find_one({"_id": ObjectId(user["company_id"])}, {"plan_id": 1})
            if company and company.get("plan_id"):
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
        except Exception:
            pass
    return user

@router.post("/refresh")
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
