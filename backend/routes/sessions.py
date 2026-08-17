"""
Panel de Sesiones Activas - gestion de sesiones concurrentes.

Modelo de datos (collection `sessions`):
  session_id: uuid str
  user_id: ObjectId
  company_id: ObjectId | None
  user_email, user_name, user_role: cache para list rapido
  ip: str
  user_agent: str (raw, hasta 500 chars)
  created_at, last_activity_at: datetime
  revoked: bool
  revoked_at, revoked_reason: opcionales

Reglas:
- Admin ve todas las sesiones de usuarios de su company.
- Vendedor / doctor solo ven las suyas.
- Usuario puede revocar cualquiera de sus propias sesiones.
- Admin puede revocar sesiones de cualquier usuario de su company.
- Superadmin puede ver/revocar cualquiera.
- No se puede revocar la sesion ACTUAL (para no auto-cerrar) - se usa /auth/logout.

TTL: se auto-purgan tras 7 dias de inactividad (indice TTL en `last_activity_at`).
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from bson import ObjectId
from datetime import datetime, timezone

from db import db
from auth_utils import get_current_user
from audit import log_audit

router = APIRouter(prefix="/sessions", tags=["Sesiones"])


def _serialize(s: dict) -> dict:
    out = {
        "session_id": s.get("session_id"),
        "user_id": str(s.get("user_id")) if s.get("user_id") else None,
        "user_email": s.get("user_email"),
        "user_name": s.get("user_name"),
        "user_role": s.get("user_role"),
        "ip": s.get("ip"),
        "user_agent": s.get("user_agent"),
        "created_at": s.get("created_at").isoformat() if isinstance(s.get("created_at"), datetime) else s.get("created_at"),
        "last_activity_at": s.get("last_activity_at").isoformat() if isinstance(s.get("last_activity_at"), datetime) else s.get("last_activity_at"),
        "revoked": bool(s.get("revoked")),
    }
    return out


@router.get("")
async def list_sessions(user: dict = Depends(get_current_user)):
    """Lista sesiones activas (no revocadas) segun rol:
    - user/doctor: solo las propias.
    - admin: todas las de su company.
    - superadmin: todas.
    """
    query: dict = {"revoked": {"$ne": True}}
    if user["role"] == "superadmin":
        pass  # sin filtro
    elif user["role"] == "admin":
        if not user.get("company_id"):
            raise HTTPException(status_code=400, detail="Usuario sin company")
        query["company_id"] = ObjectId(user["company_id"])
    else:
        query["user_id"] = ObjectId(user["_id"])

    docs = await db.sessions.find(query).sort("last_activity_at", -1).limit(500).to_list(500)
    current_sid = user.get("current_session_id")
    items = []
    for d in docs:
        s = _serialize(d)
        s["is_current"] = (current_sid is not None and s["session_id"] == current_sid)
        items.append(s)
    return {"items": items, "total": len(items), "current_session_id": current_sid}


@router.post("/{session_id}/revoke")
async def revoke_session(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Revoca una sesion. El caller debe tener permisos sobre esa sesion."""
    session = await db.sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    if session.get("revoked"):
        return {"ok": True, "message": "La sesion ya estaba revocada"}

    # Autorizacion
    sess_user_id = str(session.get("user_id")) if session.get("user_id") else None
    sess_company_id = str(session.get("company_id")) if session.get("company_id") else None
    caller_id = user["_id"]
    caller_role = user["role"]
    caller_company_id = user.get("company_id")

    allowed = False
    if caller_role == "superadmin":
        allowed = True
    elif sess_user_id == caller_id:
        allowed = True  # propio
    elif caller_role == "admin" and sess_company_id and sess_company_id == caller_company_id:
        allowed = True

    if not allowed:
        raise HTTPException(status_code=403, detail="No autorizado para revocar esta sesion")

    # Bloquear autoauto-revocacion de la sesion actual (para eso existe /auth/logout)
    if session_id == user.get("current_session_id"):
        raise HTTPException(status_code=400, detail="No puedes revocar tu sesion actual. Usa 'Cerrar sesion'.")

    await db.sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "revoked": True,
            "revoked_at": datetime.now(timezone.utc),
            "revoked_by": ObjectId(caller_id),
            "revoked_reason": "manual" if sess_user_id == caller_id else "revoked_by_admin",
        }}
    )

    await log_audit(
        "SESSION_REVOKED",
        actor_id=caller_id, actor_email=user.get("email"), actor_role=caller_role,
        company_id=caller_company_id,
        target_id=sess_user_id, target_type="user",
        metadata={
            "session_id": session_id,
            "target_email": session.get("user_email"),
            "target_name": session.get("user_name"),
            "self": sess_user_id == caller_id,
        },
        request=request,
    )
    return {"ok": True, "message": "Sesion revocada"}


@router.post("/revoke-all-mine")
async def revoke_all_mine(request: Request, user: dict = Depends(get_current_user)):
    """Cierra todas las OTRAS sesiones del usuario actual, dejando activa solo esta."""
    current_sid = user.get("current_session_id")
    query = {
        "user_id": ObjectId(user["_id"]),
        "revoked": {"$ne": True},
    }
    if current_sid:
        query["session_id"] = {"$ne": current_sid}
    result = await db.sessions.update_many(
        query,
        {"$set": {
            "revoked": True,
            "revoked_at": datetime.now(timezone.utc),
            "revoked_by": ObjectId(user["_id"]),
            "revoked_reason": "revoke_all_mine",
        }}
    )
    await log_audit(
        "SESSION_REVOKE_ALL_MINE",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"),
        metadata={"revoked_count": result.modified_count},
        request=request,
    )
    return {"ok": True, "revoked_count": result.modified_count}
