import os

# Test credentials - loaded from environment with fallbacks for CI
SUPERADMIN_EMAIL = os.getenv("TEST_SUPERADMIN_EMAIL", "superadmin@cortexia.com")
SUPERADMIN_PASSWORD = os.getenv("TEST_SUPERADMIN_PASSWORD", "Admin123!")
ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "analuhs@gmail.com")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "Alta2026$")
DEMO_EMAIL = os.getenv("TEST_DEMO_EMAIL", "admin@cortexia.gt")
DEMO_PASSWORD = os.getenv("TEST_DEMO_PASSWORD", "Demo123!")
