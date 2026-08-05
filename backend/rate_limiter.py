"""Rate limiter compartido para evitar imports circulares entre server.py y routes/.

En multi-pod: si REDIS_URL esta configurado, slowapi usa Redis como storage
compartido (limites coherentes entre pods). Si no, cae a memoria per-pod
(aceptable en single-pod dev).
"""
import os
from fastapi import Request
from slowapi import Limiter
from auth_utils import get_real_ip


def _rate_limit_key(request: Request) -> str:
    return get_real_ip(request)


_redis_url = (os.environ.get("REDIS_URL") or "").strip()

if _redis_url:
    # slowapi soporta backend Redis via storage_uri
    limiter = Limiter(
        key_func=_rate_limit_key,
        default_limits=["120/minute"],
        storage_uri=_redis_url,
    )
else:
    limiter = Limiter(key_func=_rate_limit_key, default_limits=["120/minute"])
