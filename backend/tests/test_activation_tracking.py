"""Tests for admin activation tracking (first_login_at, last_login_at, notifications).

Covers:
- Login updates last_login_at (and first_login_at when null)
- GET /api/companies (as superadmin) returns admin_activated, admin_first_login_at,
  admin_last_login_at, days_since_last_login, days_since_created, admin_email, admin_name
- When a new company admin logs in for the first time, a notification with
  event_type='admin_first_login' is created and audit log ADMIN_FIRST_LOGIN written
- activation_task.run_once does NOT wrongly deactivate old companies (backfill)
"""
import os
import time
import uuid
import asyncio
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
SUPERADMIN_EMAIL = "superadmin@cortexia.com"
SUPERADMIN_PASSWORD = "Montecristo2026"
DEMO_ADMIN_EMAIL = "admin@cortexia.gt"
DEMO_ADMIN_PASSWORD = "DemoAdmin2026!"


def _login(session, email, password):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    return r


@pytest.fixture(scope="module")
def superadmin_session():
    s = requests.Session()
    r = _login(s, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    assert r.status_code == 200, f"SuperAdmin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = _login(s, DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


# ============================================================
# Feature 2b: GET /api/companies returns activation fields
# ============================================================
class TestCompaniesActivationFields:
    def test_list_companies_has_activation_fields(self, superadmin_session):
        r = superadmin_session.get(f"{BASE_URL}/api/companies")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Debe existir al menos 1 optica (demo)"
        expected_keys = [
            "admin_activated", "admin_first_login_at", "admin_last_login_at",
            "days_since_last_login", "days_since_created", "admin_email", "admin_name",
        ]
        for company in data:
            for k in expected_keys:
                assert k in company, f"Falta '{k}' en company {company.get('name')}"

    def test_demo_company_admin_is_activated(self, superadmin_session, admin_session):
        # Admin ya hizo login (fixture) => first_login_at should be set
        r = superadmin_session.get(f"{BASE_URL}/api/companies")
        assert r.status_code == 200
        demo = next((c for c in r.json() if c.get("admin_email") == DEMO_ADMIN_EMAIL), None)
        assert demo is not None, "Demo company debe estar en /api/companies"
        assert demo["admin_activated"] is True
        assert demo["admin_first_login_at"] is not None
        assert demo["admin_last_login_at"] is not None
        assert demo["admin_name"] is not None


# ============================================================
# Feature 2a: Login updates last_login_at
# ============================================================
class TestLoginTracking:
    def test_login_updates_last_login(self, superadmin_session):
        # login as admin => last_login_at should update
        s1 = requests.Session()
        r1 = _login(s1, DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)
        assert r1.status_code == 200

        r2 = superadmin_session.get(f"{BASE_URL}/api/companies")
        demo = next(c for c in r2.json() if c.get("admin_email") == DEMO_ADMIN_EMAIL)
        first_ts = demo["admin_last_login_at"]
        assert first_ts is not None

        time.sleep(2)
        s2 = requests.Session()
        r3 = _login(s2, DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD)
        assert r3.status_code == 200

        r4 = superadmin_session.get(f"{BASE_URL}/api/companies")
        demo2 = next(c for c in r4.json() if c.get("admin_email") == DEMO_ADMIN_EMAIL)
        assert demo2["admin_last_login_at"] >= first_ts


# ============================================================
# Feature 2c: New admin first login => notification + audit
# ============================================================
class TestFirstLoginNotification:
    """Create a fresh company + admin, log in for the first time, verify side effects."""

    _created_company_id = None
    _created_admin_email = None
    _created_admin_password = None

    def test_create_company_and_first_login(self, superadmin_session):
        unique = uuid.uuid4().hex[:8]
        admin_email = f"test_activation_{unique}@example.com"
        admin_password = "TestActivation2026!"
        company_name = f"TEST_ActivationOptica_{unique}"

        payload = {
            "name": company_name,
            "legal_name": company_name,
            "tax_id": f"TAX{unique}",
            "address": "Test address",
            "phone": "+50255551234",
            "email": f"info_{unique}@example.com",
            "contact_name": "Contact",
            "contact_phone": "+50255551234",
            "contact_email": f"info_{unique}@example.com",
            "admin_email": admin_email,
            "admin_password": admin_password,
            "admin_name": "Test Admin Activation",
        }
        r = superadmin_session.post(f"{BASE_URL}/api/companies", json=payload)
        assert r.status_code == 200, f"Create company failed: {r.status_code} {r.text}"
        cid = r.json()["_id"]
        TestFirstLoginNotification._created_company_id = cid
        TestFirstLoginNotification._created_admin_email = admin_email
        TestFirstLoginNotification._created_admin_password = admin_password

        # Verify company appears with admin_activated=False before login
        r2 = superadmin_session.get(f"{BASE_URL}/api/companies")
        new = next((c for c in r2.json() if c["_id"] == cid), None)
        assert new is not None
        assert new["admin_activated"] is False, "Antes del primer login debe ser False"
        assert new["admin_first_login_at"] is None
        assert new["admin_email"] == admin_email

        # Snapshot notifications count BEFORE first login
        n_before = superadmin_session.get(f"{BASE_URL}/api/notifications").json()
        count_before = len([n for n in n_before if n.get("event_type") == "admin_first_login"])

        # Perform FIRST login as the new admin
        new_admin_session = requests.Session()
        r3 = _login(new_admin_session, admin_email, admin_password)
        assert r3.status_code == 200, f"First login failed: {r3.status_code} {r3.text}"

        # Give backend a moment for async notification creation
        time.sleep(1.5)

        # Verify company now shows admin_activated=True
        r4 = superadmin_session.get(f"{BASE_URL}/api/companies")
        activated = next(c for c in r4.json() if c["_id"] == cid)
        assert activated["admin_activated"] is True, "Despues del primer login debe ser True"
        assert activated["admin_first_login_at"] is not None
        assert activated["admin_last_login_at"] is not None

        # Verify notification created
        n_after = superadmin_session.get(f"{BASE_URL}/api/notifications").json()
        matches = [
            n for n in n_after
            if n.get("event_type") == "admin_first_login"
            and (n.get("metadata") or {}).get("admin_email") == admin_email
        ]
        assert len(matches) >= 1, "Debe crearse notificacion admin_first_login"
        notif = matches[0]
        assert "activada" in notif.get("title", "").lower() or "optica activada" in notif.get("title", "").lower()

        # count grew
        count_after = len([n for n in n_after if n.get("event_type") == "admin_first_login"])
        assert count_after > count_before

    def test_cleanup_created_company(self, superadmin_session):
        cid = TestFirstLoginNotification._created_company_id
        if cid:
            superadmin_session.delete(f"{BASE_URL}/api/companies/{cid}")


# ============================================================
# activation_task backfill safety: old companies should not be deactivated
# ============================================================
class TestActivationTaskBackfillSafety:
    def test_demo_and_seed_companies_still_active(self, superadmin_session):
        r = superadmin_session.get(f"{BASE_URL}/api/companies")
        assert r.status_code == 200
        companies = r.json()
        # Filter to companies created >= 30 dias sin login (potenciales victimas del bug)
        # Excluir opticas de test previas (prefijo TEST_) que pueden haber sido
        # borradas/desactivadas por otros tests; solo validar seed/production data.
        potentially_at_risk = [
            c for c in companies
            if (c.get("days_since_created") or 0) >= 30
            and c.get("admin_email")
            and not (c.get("name") or "").startswith("TEST_")
        ]
        # Todas deberian seguir activas (is_active True) porque el backfill puso first_login_at
        for c in potentially_at_risk:
            assert c.get("is_active", True) is True, (
                f"Optica antigua {c.get('name')} fue desactivada incorrectamente"
            )
            # y admin_first_login_at debe estar populado tras backfill
            assert c.get("admin_first_login_at") is not None, (
                f"Backfill de first_login_at fallo para {c.get('name')}"
            )
