"""Sistema de auditoria. Registra acciones criticas en la coleccion audit_log
para forensics y cumplimiento.

Eventos registrados:
- LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT
- PASSWORD_CHANGED (propio), PASSWORD_RESET (por admin a otro user)
- USER_CREATED, USER_DEACTIVATED, USER_DELETED, USER_ROLE_CHANGED
- COMPANY_CREATED, COMPANY_DELETED, COMPANY_PLAN_CHANGED
- DATABASE_EXPORTED
"""
from fastapi import Request
from datetime import datetime, timezone
from bson import ObjectId
from typing import Optional

from db import db
from auth_utils import get_real_ip


async def log_audit(
    action: str,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    actor_role: Optional[str] = None,
    company_id: Optional[str] = None,
    target_id: Optional[str] = None,
    target_type: Optional[str] = None,
    metadata: Optional[dict] = None,
    request: Optional[Request] = None,
):
    """Registra un evento de auditoria. Non-blocking en errores."""
    try:
        entry = {
            "action": action,
            "actor_id": actor_id,
            "actor_email": actor_email,
            "actor_role": actor_role,
            "company_id": ObjectId(company_id) if company_id else None,
            "target_id": target_id,
            "target_type": target_type,
            "metadata": metadata or {},
            "ip": get_real_ip(request) if request else None,
            "user_agent": (request.headers.get("User-Agent", "")[:200] if request else None),
            "created_at": datetime.now(timezone.utc),
        }
        await db.audit_log.insert_one(entry)
    except Exception:
        pass  # Nunca bloquear el flujo principal por un fallo de audit
