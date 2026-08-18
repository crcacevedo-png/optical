"""
Endpoint para recibir reportes de violaciones de Content Security Policy (CSP).
Los navegadores modernos envian reports cuando bloquean recursos por CSP,
lo cual da telemetria proactiva sobre intentos de XSS/inyeccion.

Formatos soportados:
- CSP Level 2: application/csp-report (JSON con clave "csp-report")
- Reporting API (report-to): application/reports+json (array de reports)

Guarda en `db.csp_violations` con TTL 30 dias.

Alertas de spike (Feb 2026):
- Umbral configurable via env CSP_SPIKE_THRESHOLD (default 5)
- Ventana configurable via env CSP_SPIKE_WINDOW_MIN (default 15)
- Cooldown configurable via env CSP_ALERT_COOLDOWN_MIN (default 60)
- Trigger: si en ventana los reports >= threshold y no hubo alerta activa en cooldown,
  envia email a CORTEXIA_ALERTS_TO (o ADMIN_EMAIL) + notificacion push al SuperAdmin.
"""
import os
import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import Optional

from db import db
from auth_utils import get_current_user
from rate_limiter import limiter
from email_service import queue_email, render_security_alert
from routes.notifications import create_notification

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/security", tags=["Seguridad"])

# Config de spike detection
SPIKE_THRESHOLD = int(os.environ.get("CSP_SPIKE_THRESHOLD", "5"))
SPIKE_WINDOW_MIN = int(os.environ.get("CSP_SPIKE_WINDOW_MIN", "15"))
ALERT_COOLDOWN_MIN = int(os.environ.get("CSP_ALERT_COOLDOWN_MIN", "60"))


def _normalize_report(raw: dict) -> dict:
    """Normaliza formato CSP Level 2 (csp-report) y Reporting API (body)."""
    # Level 2: {csp-report: {...}}
    report = raw.get("csp-report") if isinstance(raw, dict) else None
    if not report and isinstance(raw, dict):
        # Reporting API: {type, url, body: {...}}
        report = raw.get("body") or raw
    return report or {}


async def _check_and_alert_spike():
    """Detecta picos de violaciones CSP y notifica al equipo Cortexia.
    - No bloquea la respuesta HTTP (llamada best-effort desde el endpoint).
    - Deduplicacion via db.csp_alerts (guarda last_alert_at por scope 'global').
    """
    try:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=SPIKE_WINDOW_MIN)

        # 1) Contar violaciones en la ventana
        recent_count = await db.csp_violations.count_documents({"created_at": {"$gte": window_start}})
        if recent_count < SPIKE_THRESHOLD:
            return

        # 2) Check cooldown (evita spam)
        cooldown_start = now - timedelta(minutes=ALERT_COOLDOWN_MIN)
        last_alert = await db.csp_alerts.find_one({"scope": "global"}, sort=[("last_alert_at", -1)])
        if last_alert and last_alert.get("last_alert_at") and last_alert["last_alert_at"] > cooldown_start:
            logger.debug(f"[csp-alert] En cooldown, skip (recent={recent_count})")
            return

        # 3) Agregar top directives y top blocked_uris para el email
        top_directives = {}
        async for row in db.csp_violations.aggregate([
            {"$match": {"created_at": {"$gte": window_start}}},
            {"$group": {"_id": "$violated_directive", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5},
        ]):
            top_directives[row["_id"] or "unknown"] = row["count"]

        top_uris = {}
        async for row in db.csp_violations.aggregate([
            {"$match": {"created_at": {"$gte": window_start}}},
            {"$group": {"_id": "$blocked_uri", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5},
        ]):
            uri = row["_id"] or "(inline)"
            top_uris[uri[:80]] = row["count"]

        # 4) Enviar email al equipo Cortexia
        app_url = os.environ.get("APP_URL", "https://cortexiaoptical.com")
        alerts_to = os.environ.get("CORTEXIA_ALERTS_TO") or os.environ.get("ADMIN_EMAIL") or "info@cortexiagt.com"
        try:
            event_meta = {
                "Cantidad en ventana": f"{recent_count} violaciones en {SPIKE_WINDOW_MIN} min",
                "Umbral": f">= {SPIKE_THRESHOLD}",
            }
            for d, c in top_directives.items():
                event_meta[f"Directive: {d}"] = f"{c} bloqueos"
            for u, c in list(top_uris.items())[:3]:
                event_meta[f"URI: {u}"] = f"{c} intentos"
            html = render_security_alert(
                name="Equipo Cortexia",
                event_title=f"Pico de violaciones CSP detectado ({recent_count})",
                event_description=(
                    f"En los ultimos {SPIKE_WINDOW_MIN} minutos se registraron {recent_count} "
                    "violaciones de Content Security Policy — puede indicar un intento activo "
                    "de XSS o inyeccion cross-site. Revisa el panel /admin/dashboard."
                ),
                event_meta=event_meta,
                app_url=app_url,
            )
            queue_email(
                alerts_to,
                f"[Cortexia][SECURITY] Pico CSP: {recent_count} violaciones en {SPIKE_WINDOW_MIN} min",
                html,
                tag="csp_spike_alert",
            )
        except Exception as e:
            logger.warning(f"[csp-alert] Email fallo: {e}")

        # 5) Notificacion push al SuperAdmin
        try:
            await create_notification(
                event_type="csp_spike",
                title=f"Pico CSP: {recent_count} violaciones",
                message=f"Ultimos {SPIKE_WINDOW_MIN} min: {recent_count} violaciones (umbral {SPIKE_THRESHOLD}). Revisa Dashboard SaaS.",
                metadata={
                    "count": recent_count,
                    "window_minutes": SPIKE_WINDOW_MIN,
                    "top_directives": top_directives,
                }
            )
        except Exception as e:
            logger.warning(f"[csp-alert] Notification fallo: {e}")

        # 6) Marcar alerta enviada para cooldown
        await db.csp_alerts.update_one(
            {"scope": "global"},
            {"$set": {
                "scope": "global",
                "last_alert_at": now,
                "last_count": recent_count,
                "last_top_directives": top_directives,
            }},
            upsert=True,
        )
        logger.info(f"[csp-alert] Alerta enviada: {recent_count} violaciones en {SPIKE_WINDOW_MIN} min")
    except Exception as e:
        logger.error(f"[csp-alert] Error inesperado: {e}")


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

    # Best-effort: verificar si hay spike y notificar (no bloquea la respuesta)
    if stored > 0:
        try:
            await _check_and_alert_spike()
        except Exception as e:
            logger.warning(f"[csp-report] Spike check fallo: {e}")

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
