"""Cache compartido entre pods.

Prioridad:
1. Si `REDIS_URL` esta configurado → backend Redis (coherente en multi-pod).
2. Si no → TTL cache en memoria (per-pod, valido para dev y single-pod).

API sincrona (`get`, `set`, `invalidate`) mantiene compatibilidad con el codigo
existente. `get_or_load` acepta loader async igual que antes.

Uso:
    from cache import plans_cache
    plans = await plans_cache.get_or_load("all_plans", loader_fn, ttl=300)
"""
import json
import logging
import os
import time
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("cache")

REDIS_URL = (os.environ.get("REDIS_URL") or "").strip()

_redis_client = None  # redis.asyncio client
_redis_available = False


async def init_cache() -> None:
    """Inicializa backend Redis si REDIS_URL esta presente. Idempotente."""
    global _redis_client, _redis_available
    if not REDIS_URL:
        logger.info("Cache backend: memoria (in-process). Para multi-pod define REDIS_URL.")
        return
    try:
        from redis import asyncio as aioredis
        _redis_client = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        # Ping para verificar
        await _redis_client.ping()
        _redis_available = True
        logger.info("Cache backend: Redis conectado")
    except Exception as e:
        logger.error(f"Redis no disponible, fallback a memoria: {e}")
        _redis_client = None
        _redis_available = False


class TTLCache:
    """Cache con TTL. Usa Redis si esta disponible, si no memoria in-process."""

    def __init__(self, default_ttl: int = 300, namespace: str = "c"):
        self._default_ttl = default_ttl
        self._ns = namespace
        # Fallback in-memory
        self._store: dict[str, tuple[float, Any]] = {}
        self._hits = 0
        self._misses = 0

    def _k(self, key: str) -> str:
        # Include DB_NAME in the key so preview/prod (or any parallel deployments)
        # sharing the same Redis instance don't step on each other's cache.
        db_name = (os.environ.get("DB_NAME") or "default").strip()
        return f"cortexia:{db_name}:{self._ns}:{key}"

    def _mem_get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            self._misses += 1
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            self._store.pop(key, None)
            self._misses += 1
            return None
        self._hits += 1
        return value

    def _mem_set(self, key: str, value: Any, ttl: Optional[int]) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        self._store[key] = (time.monotonic() + ttl, value)

    async def aget(self, key: str) -> Optional[Any]:
        if _redis_available and _redis_client:
            try:
                raw = await _redis_client.get(self._k(key))
                if raw is None:
                    self._misses += 1
                    return None
                self._hits += 1
                return json.loads(raw)
            except Exception as e:
                logger.warning(f"Redis GET fallo, fallback memoria: {e}")
        return self._mem_get(key)

    async def aset(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        if _redis_available and _redis_client:
            try:
                await _redis_client.set(self._k(key), json.dumps(value, default=str), ex=ttl)
                return
            except Exception as e:
                logger.warning(f"Redis SET fallo, fallback memoria: {e}")
        self._mem_set(key, value, ttl)

    async def ainvalidate(self, key: str) -> None:
        if _redis_available and _redis_client:
            try:
                await _redis_client.delete(self._k(key))
            except Exception as e:
                logger.warning(f"Redis DEL fallo: {e}")
        self._store.pop(key, None)

    # ─── API sincrona retro-compatible (solo memoria; no-ops en Redis) ────
    def get(self, key: str) -> Optional[Any]:
        return self._mem_get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._mem_set(key, value, ttl)

    def invalidate(self, key: str) -> None:
        # Best effort en Redis via task background (fire-and-forget)
        if _redis_available and _redis_client:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.ainvalidate(key))
            except Exception:
                pass
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round((self._hits / total) * 100, 1) if total else 0.0,
            "default_ttl_seconds": self._default_ttl,
            "backend": "redis" if _redis_available else "memory",
        }

    async def get_or_load(
        self,
        key: str,
        loader: Callable[[], Awaitable[Any]],
        ttl: Optional[int] = None,
    ) -> Any:
        """Retorna cacheado o llama loader() y cachea."""
        cached = await self.aget(key)
        if cached is not None:
            return cached
        value = await loader()
        await self.aset(key, value, ttl)
        return value


def is_redis_backed() -> bool:
    return _redis_available


# Instancias globales
plans_cache = TTLCache(default_ttl=300, namespace="plans")
companies_cache = TTLCache(default_ttl=120, namespace="companies")
inventory_cache = TTLCache(default_ttl=60, namespace="inventory")


async def invalidate_inventory(company_id: str, branch_id: str = None) -> None:
    """Invalida cache de productos/stock para una empresa (opcional sucursal).
    Se llama tras crear/editar producto, movimiento de inventario o venta."""
    # products: la key es "products:{cid}:{branch_or_all}"
    await inventory_cache.ainvalidate(f"products:{company_id}:all")
    await inventory_cache.ainvalidate(f"stock:{company_id}:all")
    if branch_id:
        await inventory_cache.ainvalidate(f"products:{company_id}:{branch_id}")
        await inventory_cache.ainvalidate(f"stock:{company_id}:{branch_id}")
