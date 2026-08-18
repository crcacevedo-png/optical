"""
Registro y consulta de IPs bloqueadas por comportamiento anomalo.
- Alimentado automaticamente por security_reports._check_and_alert_spike cuando
  una IP genera un pico sostenido de violaciones CSP.
- Cache in-memory (set) con refresco cada 30s para checkeo O(1) desde el middleware.
- TTL de bloqueo: por defecto 24h (BLOCKED_IP_TTL_HOURS).
"""
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Set, Optional

from db import db

logger = logging.getLogger(__name__)

BLOCKED_IP_TTL_HOURS = int(os.environ.get("BLOCKED_IP_TTL_HOURS", "24"))
CACHE_REFRESH_SECONDS = int(os.environ.get("BLOCKED_IP_CACHE_REFRESH", "30"))

# Cache local
_cache_lock = asyncio.Lock()
_cache: Set[str] = set()
_cache_loaded_at: Optional[datetime] = None


async def _reload_cache_locked():
    """Carga la lista de IPs bloqueadas activas desde Mongo (no expirados)."""
    global _cache, _cache_loaded_at
    now = datetime.now(timezone.utc)
    active_ips = set()
    async for doc in db.blocked_ips.find({"blocked_until": {"$gt": now}}, {"ip": 1}):
        ip = doc.get("ip")
        if ip:
            active_ips.add(ip)
    _cache = active_ips
    _cache_loaded_at = now
    logger.info(f"[blocked-ips] Cache reloaded: {len(active_ips)} IPs activas")


async def _ensure_cache_fresh():
    """Refresca el cache si esta stale."""
    global _cache_loaded_at
    now = datetime.now(timezone.utc)
    if _cache_loaded_at is None or (now - _cache_loaded_at).total_seconds() > CACHE_REFRESH_SECONDS:
        async with _cache_lock:
            # Double-check dentro del lock
            if _cache_loaded_at is None or (now - _cache_loaded_at).total_seconds() > CACHE_REFRESH_SECONDS:
                await _reload_cache_locked()


async def is_ip_blocked(ip: str) -> bool:
    """Check O(1) desde el middleware. Refresca cache si stale."""
    if not ip:
        return False
    await _ensure_cache_fresh()
    return ip in _cache


async def block_ip(ip: str, *, reason: str, metadata: dict = None, hours: Optional[int] = None) -> bool:
    """Bloquea una IP por `hours` horas. Retorna True si fue nuevo bloqueo, False si ya estaba activo.
    Idempotente: si ya esta bloqueada, extiende el TTL.
    """
    if not ip:
        return False
    ttl = hours or BLOCKED_IP_TTL_HOURS
    now = datetime.now(timezone.utc)
    until = now + timedelta(hours=ttl)
    existing = await db.blocked_ips.find_one({"ip": ip})
    is_new = not existing or (existing.get("blocked_until") and existing["blocked_until"] <= now)
    doc = {
        "ip": ip,
        "reason": reason,
        "metadata": metadata or {},
        "blocked_at": now,
        "blocked_until": until,
        "block_count": (existing.get("block_count", 0) if existing else 0) + 1,
    }
    await db.blocked_ips.update_one({"ip": ip}, {"$set": doc}, upsert=True)
    # Invalidar cache
    async with _cache_lock:
        _cache.add(ip)
    logger.warning(f"[blocked-ips] IP {ip} bloqueada por {ttl}h. Razon: {reason}")
    return is_new


async def unblock_ip(ip: str) -> bool:
    """Remueve el bloqueo de una IP. Retorna True si existia."""
    if not ip:
        return False
    result = await db.blocked_ips.delete_one({"ip": ip})
    async with _cache_lock:
        _cache.discard(ip)
    return result.deleted_count > 0


async def list_blocked_ips(limit: int = 100) -> list:
    """Retorna lista de IPs bloqueadas (activas y expiradas recientes) para el panel."""
    now = datetime.now(timezone.utc)
    items = []
    async for doc in db.blocked_ips.find({}).sort("blocked_at", -1).limit(limit):
        items.append({
            "_id": str(doc.get("_id")),
            "ip": doc.get("ip"),
            "reason": doc.get("reason"),
            "block_count": doc.get("block_count", 1),
            "blocked_at": doc.get("blocked_at").isoformat() if isinstance(doc.get("blocked_at"), datetime) else doc.get("blocked_at"),
            "blocked_until": doc.get("blocked_until").isoformat() if isinstance(doc.get("blocked_until"), datetime) else doc.get("blocked_until"),
            "active": bool(doc.get("blocked_until") and doc.get("blocked_until") > now),
            "metadata": doc.get("metadata", {}),
        })
    return items
