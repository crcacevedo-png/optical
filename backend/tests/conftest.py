import os

# Test credentials — leidas EXCLUSIVAMENTE de env vars. Sin fallbacks hardcodeados.
# En desarrollo local, exporta TEST_*_PASSWORD o usa .env / .env.test.
SUPERADMIN_EMAIL = os.getenv("TEST_SUPERADMIN_EMAIL") or os.getenv("ADMIN_EMAIL", "")
SUPERADMIN_PASSWORD = os.getenv("TEST_SUPERADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD", "")
ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD", "")
DEMO_EMAIL = os.getenv("TEST_DEMO_EMAIL", "admin@cortexia.gt")
DEMO_PASSWORD = os.getenv("TEST_DEMO_PASSWORD") or os.getenv("DEMO_PASSWORD", "")
