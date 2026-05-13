"""Tests for Communication module (Announcements) - SuperAdmin CRUD + /active endpoint filtering."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://eyecare-erp.preview.emergentagent.com').rstrip('/')

SUPERADMIN = {"email": "superadmin@cortexia.com", "password": "Admin123!"}
ADMIN_ENTERPRISE = {"email": "analuhs@gmail.com", "password": "Alta2026$"}
ADMIN_FREE = {"email": "admin@cortexia.gt", "password": "Demo123!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def super_session():
    return _login(SUPERADMIN)


@pytest.fixture(scope="module")
def enterprise_session():
    return _login(ADMIN_ENTERPRISE)


@pytest.fixture(scope="module")
def free_session():
    return _login(ADMIN_FREE)


# -------- LIST (GET /api/announcements) --------
class TestList:
    def test_list_as_superadmin(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/announcements", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 3, f"expected at least 3 seed announcements, got {len(data)}"
        # Required fields
        for a in data:
            assert "_id" in a and isinstance(a["_id"], str)
            assert "title" in a
            assert "message" in a
            assert "type" in a
            assert a["type"] in ("info", "warning", "promo")
            assert "is_active" in a

    def test_list_forbidden_for_admin(self, enterprise_session):
        r = enterprise_session.get(f"{BASE_URL}/api/announcements", timeout=20)
        assert r.status_code == 403

    def test_list_unauthenticated(self):
        r = requests.get(f"{BASE_URL}/api/announcements", timeout=20)
        assert r.status_code in (401, 403)


# -------- CRUD (POST/PUT/DELETE) --------
class TestCRUD:
    def test_create_update_delete_flow(self, super_session):
        # CREATE
        payload = {
            "title": "TEST_Anuncio Pytest",
            "message": "Mensaje de prueba pytest",
            "type": "info",
            "target_plans": ["Free"],
            "target_cities": [],
            "start_date": "2026-01-01",
            "end_date": "2030-12-31"
        }
        r = super_session.post(f"{BASE_URL}/api/announcements", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "_id" in body
        new_id = body["_id"]

        # Verify via GET list
        listed = super_session.get(f"{BASE_URL}/api/announcements").json()
        found = next((a for a in listed if a["_id"] == new_id), None)
        assert found is not None, "created announcement not in list"
        assert found["title"] == payload["title"]
        assert found["type"] == "info"
        assert found["target_plans"] == ["Free"]
        assert found["is_active"] is True

        # UPDATE - change title, type, is_active
        upd = {"title": "TEST_Anuncio Pytest UPDATED", "type": "warning", "is_active": False}
        r = super_session.put(f"{BASE_URL}/api/announcements/{new_id}", json=upd, timeout=20)
        assert r.status_code == 200, r.text

        listed2 = super_session.get(f"{BASE_URL}/api/announcements").json()
        found2 = next((a for a in listed2 if a["_id"] == new_id), None)
        assert found2 is not None
        assert found2["title"] == "TEST_Anuncio Pytest UPDATED"
        assert found2["type"] == "warning"
        assert found2["is_active"] is False

        # DELETE
        r = super_session.delete(f"{BASE_URL}/api/announcements/{new_id}", timeout=20)
        assert r.status_code == 200

        listed3 = super_session.get(f"{BASE_URL}/api/announcements").json()
        assert not any(a["_id"] == new_id for a in listed3), "announcement still present after delete"

    def test_create_forbidden_for_admin(self, enterprise_session):
        r = enterprise_session.post(f"{BASE_URL}/api/announcements",
                                    json={"title": "x", "message": "y", "type": "info"}, timeout=20)
        assert r.status_code == 403

    def test_update_invalid_id_returns_400(self, super_session):
        r = super_session.put(f"{BASE_URL}/api/announcements/not-a-valid-id",
                              json={"title": "x"}, timeout=20)
        assert r.status_code == 400

    def test_update_nonexistent_returns_404(self, super_session):
        # Valid ObjectId format but not present
        r = super_session.put(f"{BASE_URL}/api/announcements/507f1f77bcf86cd799439011",
                              json={"title": "x"}, timeout=20)
        assert r.status_code == 404


# -------- ACTIVE endpoint (filtered for admin) --------
class TestActive:
    def test_active_superadmin_returns_empty(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/announcements/active", timeout=20)
        assert r.status_code == 200
        assert r.json() == []

    def test_active_enterprise_admin(self, enterprise_session):
        r = enterprise_session.get(f"{BASE_URL}/api/announcements/active", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # Enterprise admin should see warning (all plans) + promo (Basic+Enterprise) = 2
        types = sorted([a["type"] for a in data])
        assert "warning" in types, f"Enterprise admin should see 'warning' (all plans), got: {types}"
        assert "promo" in types, f"Enterprise admin should see 'promo' (Basic+Enterprise), got: {types}"
        assert "info" not in types, f"Enterprise admin should NOT see 'info' (Free-only), got: {types}"
        assert len(data) == 2, f"expected 2 active announcements for Enterprise, got {len(data)}: {types}"
        # Ensure no Mongo ObjectId leaked
        for a in data:
            assert isinstance(a["_id"], str)

    def test_active_free_admin(self, free_session):
        r = free_session.get(f"{BASE_URL}/api/announcements/active", timeout=20)
        assert r.status_code == 200
        data = r.json()
        types = sorted([a["type"] for a in data])
        # Free admin should see warning (all plans) + info (Free only) = 2
        assert "warning" in types, f"Free admin should see 'warning', got: {types}"
        assert "info" in types, f"Free admin should see 'info' (Free-only), got: {types}"
        assert "promo" not in types, f"Free admin should NOT see 'promo' (Basic+Enterprise), got: {types}"
        assert len(data) == 2, f"expected 2 for Free, got {len(data)}: {types}"

    def test_active_unauthenticated(self):
        r = requests.get(f"{BASE_URL}/api/announcements/active", timeout=20)
        assert r.status_code in (401, 403)

    def test_inactive_announcement_excluded(self, super_session, enterprise_session):
        # Create an inactive (after toggling) warning targeting all plans
        payload = {"title": "TEST_inactive", "message": "no should show",
                   "type": "warning", "target_plans": [], "target_cities": [],
                   "start_date": "2026-01-01", "end_date": "2030-12-31"}
        created = super_session.post(f"{BASE_URL}/api/announcements", json=payload).json()
        aid = created["_id"]
        try:
            # Deactivate
            super_session.put(f"{BASE_URL}/api/announcements/{aid}", json={"is_active": False})
            r = enterprise_session.get(f"{BASE_URL}/api/announcements/active", timeout=20)
            ids = [a["_id"] for a in r.json()]
            assert aid not in ids, "inactive announcement leaked into /active"
        finally:
            super_session.delete(f"{BASE_URL}/api/announcements/{aid}")
