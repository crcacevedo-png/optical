"""Rate limiter compartido para evitar imports circulares entre server.py y routes/."""
from fastapi import Request
from slowapi import Limiter
from auth_utils import get_real_ip


def _rate_limit_key(request: Request) -> str:
    return get_real_ip(request)


limiter = Limiter(key_func=_rate_limit_key, default_limits=["120/minute"])
