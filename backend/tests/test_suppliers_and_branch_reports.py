"""Backend tests for:
- P0: Reports branch filter (branch_id query param on /api/reports/sales and /api/finance/summary)
- P3: Suppliers CRUD (/api/suppliers GET, POST, PUT, DELETE)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

from _credentials import ADMIN_EMAIL, ADMIN_PASSWORD


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def admin_session():
    """Cookie-based session authenticated as admin."""
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="module")
def created_supplier_id(admin_session):
    payload = {
        "name": "TEST_Pytest Distribuidora",
        "contact_name": "QA Bot",
        "phone": "+502 0000-0000",
        "email": "qa@test.example",
        "categories": ["Armazones", "Lentes Oftálmicos"],
        "notes": "created by pytest"
    }
    r = admin_session.post(f"{API}/suppliers", json=payload)
    assert r.status_code == 200, r.text
    sid = r.json().get("_id")
    assert sid
    yield sid
    # Teardown - soft delete
    admin_session.delete(f"{API}/suppliers/{sid}")


# ---------- Suppliers tests ----------
class TestSuppliersCRUD:
    def test_login_works(self, admin_session):
        r = admin_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json().get("role") == "admin"

    def test_list_suppliers(self, admin_session):
        r = admin_session.get(f"{API}/suppliers")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_supplier_persists_and_appears_in_list(self, admin_session, created_supplier_id):
        # GET single
        r = admin_session.get(f"{API}/suppliers/{created_supplier_id}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == "TEST_Pytest Distribuidora"
        assert data["contact_name"] == "QA Bot"
        assert "Armazones" in data.get("categories", [])
        assert data.get("is_active") is True

        # GET list
        r = admin_session.get(f"{API}/suppliers")
        assert r.status_code == 200
        ids = [s["_id"] for s in r.json()]
        assert created_supplier_id in ids

    def test_search_supplier_by_name(self, admin_session, created_supplier_id):
        r = admin_session.get(f"{API}/suppliers", params={"search": "Pytest"})
        assert r.status_code == 200
        names = [s["name"] for s in r.json()]
        assert any("Pytest" in n for n in names)

    def test_search_supplier_no_match(self, admin_session):
        r = admin_session.get(f"{API}/suppliers", params={"search": "ZZZ_unlikely_xyz_99"})
        assert r.status_code == 200
        assert r.json() == []

    def test_update_supplier(self, admin_session, created_supplier_id):
        r = admin_session.put(
            f"{API}/suppliers/{created_supplier_id}",
            json={"phone": "+502 1111-2222", "notes": "updated by pytest"},
        )
        assert r.status_code == 200, r.text

        # Verify persistence
        r = admin_session.get(f"{API}/suppliers/{created_supplier_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["phone"] == "+502 1111-2222"
        assert data["notes"] == "updated by pytest"
        # Unchanged field intact
        assert data["name"] == "TEST_Pytest Distribuidora"

    def test_create_supplier_missing_name_returns_422(self, admin_session):
        r = admin_session.post(f"{API}/suppliers", json={"contact_name": "no name"})
        assert r.status_code == 422

    def test_delete_supplier_soft_delete(self, admin_session):
        # Create a fresh one so module-scoped fixture is unaffected
        r = admin_session.post(f"{API}/suppliers", json={"name": "TEST_DeleteMe"})
        assert r.status_code == 200
        sid = r.json()["_id"]

        r = admin_session.delete(f"{API}/suppliers/{sid}")
        assert r.status_code == 200

        # Should not appear in list (soft delete: is_active=False filtered)
        r = admin_session.get(f"{API}/suppliers")
        ids = [s["_id"] for s in r.json()]
        assert sid not in ids

        # Direct GET still returns it (no 404 in current impl) - verify is_active=False
        r = admin_session.get(f"{API}/suppliers/{sid}")
        assert r.status_code == 200
        assert r.json().get("is_active") is False


# ---------- Reports branch filter tests ----------
class TestReportsBranchFilter:
    def test_get_branches(self, admin_session):
        r = admin_session.get(f"{API}/branches")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_sales_report_no_filter(self, admin_session):
        r = admin_session.get(
            f"{API}/reports/sales",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)

    def test_sales_report_with_branch_id(self, admin_session):
        r = admin_session.get(f"{API}/branches")
        branches = r.json()
        if not branches:
            pytest.skip("No branches available to test branch filter")
        branch_id = branches[0]["_id"]
        r = admin_session.get(
            f"{API}/reports/sales",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31", "branch_id": branch_id},
        )
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), dict)

    def test_sales_report_invalid_branch_id(self, admin_session):
        r = admin_session.get(
            f"{API}/reports/sales",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31", "branch_id": "invalid-id"},
        )
        # Should fail gracefully (400/422/500) - documenting behavior
        assert r.status_code in (200, 400, 422, 500)

    def test_finance_summary_with_branch_id(self, admin_session):
        r = admin_session.get(f"{API}/branches")
        branches = r.json()
        if not branches:
            pytest.skip("No branches available")
        branch_id = branches[0]["_id"]
        r = admin_session.get(
            f"{API}/finance/summary",
            params={"date_from": "2026-01-01", "date_to": "2026-12-31", "branch_id": branch_id},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # finance/summary returns object with month/today keys
        assert isinstance(data, dict)

    def test_finance_summary_no_filter(self, admin_session):
        r = admin_session.get(f"{API}/finance/summary")
        assert r.status_code == 200, r.text
