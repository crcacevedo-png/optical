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
_load_test_bypass = os.environ.get("LOAD_TEST_BYPASS_RATELIMIT", "").strip() == "1"

# Limite muy alto en modo bypass (equivale a "sin limite" para tests de carga
# desde una sola IP, simulando 1000 IPs distintas en produccion).
_default_limits = ["1000000/minute"] if _load_test_bypass else ["120/minute"]

if _redis_url and not _load_test_bypass:
    # slowapi soporta backend Redis via storage_uri
    limiter = Limiter(
        key_func=_rate_limit_key,
        default_limits=_default_limits,
        storage_uri=_redis_url,
    )
else:
    limiter = Limiter(key_func=_rate_limit_key, default_limits=_default_limits)
