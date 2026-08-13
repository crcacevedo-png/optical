"""Credenciales de test centralizadas — leidas SOLO de env vars.

En desarrollo local, define estas variables en un archivo `.env.test` (no
commiteado) o exportalas antes de correr pytest:

    export TEST_ADMIN_EMAIL=admin@cortexia.gt
    export TEST_ADMIN_PASSWORD=***
    export TEST_SUPERADMIN_EMAIL=superadmin@cortexia.com
    export TEST_SUPERADMIN_PASSWORD=***
    export TEST_VENDEDOR_EMAIL=vendedor@cortexia.gt
    export TEST_VENDEDOR_PASSWORD=***

Si no estan definidas, cae al ADMIN_EMAIL/ADMIN_PASSWORD del pod (que son
las credenciales de seed reales). NUNCA hardcodees passwords en este archivo.
"""
import os

# Auto-carga del .env del backend si existe (para conveniencia local)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.test"))
except Exception:  # dotenv opcional
    pass

# Admin de la empresa Demo (seed)
ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL") or os.getenv("DEMO_ADMIN_EMAIL") or "admin@cortexia.gt"
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD") or ""

# SuperAdmin: reusa ADMIN_EMAIL/ADMIN_PASSWORD del pod si no hay override
SUPERADMIN_EMAIL = os.getenv("TEST_SUPERADMIN_EMAIL") or os.getenv("ADMIN_EMAIL") or ""
SUPERADMIN_PASSWORD = os.getenv("TEST_SUPERADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD") or ""

# Vendedor seed
VENDEDOR_EMAIL = os.getenv("TEST_VENDEDOR_EMAIL") or "vendedor@cortexia.gt"
VENDEDOR_PASSWORD = os.getenv("TEST_VENDEDOR_PASSWORD") or os.getenv("DEMO_PASSWORD") or ""


def require(name: str, value: str) -> str:
    """Falla claro si una credencial de test no esta configurada."""
    if not value:
        raise RuntimeError(
            f"Credencial de test faltante: {name}. Configura la env var correspondiente "
            f"(TEST_ADMIN_PASSWORD / TEST_SUPERADMIN_PASSWORD / DEMO_PASSWORD)."
        )
    return value
