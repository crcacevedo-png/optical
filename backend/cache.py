"""Cache TTL en memoria (per-pod). Ideal para catalogos que cambian poco:
planes, configuracion de empresa, feature flags.

NOTA de escalamiento: cuando se agreguen replicas del backend, migrar a Redis.
Cada pod tendra su propio cache -> puede haber ligero desfase (max TTL segundos)
tras un update, aceptable para catalogos.
"""
import time
from typing import Any, Callable, Awaitable, Optional


class TTLCache:
    """Cache thread-safe simple con expiracion por clave."""

    def __init__(self, default_ttl: int = 300):
        self._store: dict[str, tuple[float, Any]] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        self._store[key] = (time.monotonic() + ttl, value)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    async def get_or_load(
        self,
        key: str,
        loader: Callable[[], Awaitable[Any]],
        ttl: Optional[int] = None,
    ) -> Any:
        """Retorna el valor cacheado o lo carga con `loader()` y lo cachea."""
        cached = self.get(key)
        if cached is not None:
            return cached
        value = await loader()
        self.set(key, value, ttl)
        return value


# Instancia global (usar por modulo)
plans_cache = TTLCache(default_ttl=300)       # planes cambian poco -> 5 min
companies_cache = TTLCache(default_ttl=120)   # datos de empresa -> 2 min
