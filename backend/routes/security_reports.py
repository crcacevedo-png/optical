"""
Endpoint para recibir reportes de violaciones de Content Security Policy (CSP).
Los navegadores modernos envian reports cuando bloquean recursos por CSP,
lo cual da telemetria proactiva sobre intentos de XSS/inyeccion.

Formatos soportados:
- CSP Level 2: application/csp-report (JSON con clave "csp-report")
- Reporting API (report-to): application/reports+json (array de reports)

Guarda en `db.csp_violations` con TTL 30 dias.
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional

from db import db
from auth_utils import get_current_user
from rate_limiter import limiter

router = APIRouter(prefix="/security", tags=["Seguridad"])


def _normalize_report(raw: dict) -> dict:
    """Normaliza formato CSP Level 2 (csp-report) y Reporting API (body)."""
    # Level 2: {csp-report: {...}}
    report = raw.get("csp-report") if isinstance(raw, dict) else None
    if not report and isinstance(raw, dict):
        # Reporting API: {type, url, body: {...}}
        report = raw.get("body") or raw
    return report or {}


@router.post("/csp-report")
@limiter.limit("60/minute")
async def csp_report(request: Request):
    """Recibe CSP violation reports del navegador. No requiere auth
    (los navegadores envian estos reports sin credenciales)."""
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # El Reporting API puede enviar un ARRAY de reports
    reports = raw if isinstance(raw, list) else [raw]
    stored = 0
    now = datetime.now(timezone.utc)

    for r in reports:
        rep = _normalize_report(r)
        if not rep:
            continue
        # Extraer campos comunes (algunos vienen de Level 2, otros de Reporting API)
        doc = {
            "created_at": now,
            "document_uri": rep.get("document-uri") or rep.get("documentURL"),
            "referrer": rep.get("referrer"),
            "violated_directive": rep.get("violated-directive") or rep.get("effectiveDirective"),
            "effective_directive": rep.get("effective-directive") or rep.get("effectiveDirective"),
            "original_policy": (rep.get("original-policy") or rep.get("originalPolicy") or "")[:500],
            "blocked_uri": (rep.get("blocked-uri") or rep.get("blockedURL") or "")[:500],
            "source_file": rep.get("source-file") or rep.get("sourceFile"),
            "line_number": rep.get("line-number") or rep.get("lineNumber"),
            "column_number": rep.get("column-number") or rep.get("columnNumber"),
            "disposition": rep.get("disposition"),
            "sample": (rep.get("script-sample") or rep.get("sample") or "")[:200],
            "user_agent": (request.headers.get("User-Agent") or "")[:500],
            "ip": (request.headers.get("X-Forwarded-For") or (request.client.host if request.client else "") or "").split(",")[0].strip()[:80],
        }
        try:
            await db.csp_violations.insert_one(doc)
            stored += 1
        except Exception:
            pass

    return {"stored": stored}


@router.get("/csp-violations")
async def list_csp_violations(user: dict = Depends(get_current_user), limit: int = 100, hours: int = 24):
    """SuperAdmin lista violaciones recientes con agregacion por directive."""
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    limit = max(1, min(500, limit))
    hours = max(1, min(720, hours))

    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    items = []
    async for d in db.csp_violations.find({"created_at": {"$gte": since}}).sort("created_at", -1).limit(limit):
        d["_id"] = str(d["_id"])
        d["created_at"] = d["created_at"].isoformat() if isinstance(d.get("created_at"), datetime) else d.get("created_at")
        items.append(d)

    # Aggregate top violated directives + top blocked URIs
    by_directive = {}
    by_blocked = {}
    async for row in db.csp_violations.aggregate([
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {"_id": "$violated_directive", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]):
        by_directive[row["_id"] or "unknown"] = row["count"]

    async for row in db.csp_violations.aggregate([
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {"_id": "$blocked_uri", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]):
        by_blocked[row["_id"] or "unknown"] = row["count"]

    return {
        "items": items,
        "total": len(items),
        "since_hours": hours,
        "breakdown_by_directive": by_directive,
        "breakdown_by_blocked_uri": by_blocked,
    }
