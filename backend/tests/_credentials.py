"""Credenciales de test centralizadas. Lee de env vars para evitar hardcoding.
Defaults coinciden con las credenciales del seed de la empresa Demo en desarrollo.
En CI/produccion se pueden sobreescribir con env vars.
"""
import os

# Credenciales de admin de la empresa Demo (seeded en /app/backend/server.py)
ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "admin@cortexia.gt")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "Demo123!")

# Credenciales de SuperAdmin (definidas en .env como ADMIN_EMAIL/ADMIN_PASSWORD)
SUPERADMIN_EMAIL = os.getenv("TEST_SUPERADMIN_EMAIL", os.getenv("ADMIN_EMAIL", "superadmin@cortexia.com"))
SUPERADMIN_PASSWORD = os.getenv("TEST_SUPERADMIN_PASSWORD", os.getenv("ADMIN_PASSWORD", "Montecristo2026"))

# Vendedor seed
VENDEDOR_EMAIL = os.getenv("TEST_VENDEDOR_EMAIL", "vendedor@cortexia.gt")
VENDEDOR_PASSWORD = os.getenv("TEST_VENDEDOR_PASSWORD", "Demo123!")
