"""Tests for SuperAdmin dashboard endpoint - /api/superadmin/dashboard"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")
SUPERADMIN = {"email": "superadmin@cortexia.com", "password": "Admin123!"}
ADMIN = {"email": "analuhs@gmail.com", "password": "Alta2026$"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def super_session():
    return _login(SUPERADMIN)


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN)


class TestSuperAdminDashboard:
    def test_dashboard_returns_200_for_superadmin(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/superadmin/dashboard", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # required keys
        for k in ["totals", "companies_by_plan", "estimated_revenue",
                  "revenue_by_plan", "patient_growth", "companies_at_limit",
                  "recent_plan_changes", "new_companies_month"]:
            assert k in data, f"missing key {k}"

    def test_totals_structure(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/superadmin/dashboard", timeout=20)
        d = r.json()["totals"]
        for k in ["companies", "patients", "users", "branches"]:
            assert k in d
            assert isinstance(d[k], int)
            assert d[k] >= 0
        # at least 1 company should exist (Altavista + Demo)
        assert d["companies"] >= 1

    def test_companies_by_plan_format(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/superadmin/dashboard", timeout=20)
        arr = r.json()["companies_by_plan"]
        assert isinstance(arr, list)
        for item in arr:
            assert "name" in item and "value" in item
            assert isinstance(item["value"], int)
            assert item["value"] > 0  # filters value>0

    def test_estimated_revenue_is_number(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/superadmin/dashboard", timeout=20)
        rev = r.json()["estimated_revenue"]
        assert isinstance(rev, (int, float))
        assert rev >= 0

    def test_revenue_by_plan_format(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/superadmin/dashboard", timeout=20)
        arr = r.json()["revenue_by_plan"]
        assert isinstance(arr, list)
        total = 0
        for item in arr:
            assert "name" in item and "value" in item
            total += item["value"]
        # sum of revenue_by_plan should equal estimated_revenue
        assert total == r.json()["estimated_revenue"]

    def test_patient_growth_is_6_months(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/superadmin/dashboard", timeout=20)
        arr = r.json()["patient_growth"]
        assert isinstance(arr, list)
        assert len(arr) == 6
        for item in arr:
            assert "month" in item and "count" in item
            assert isinstance(item["count"], int)
            assert item["count"] >= 0

    def test_companies_at_limit_format(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/superadmin/dashboard", timeout=20)
        arr = r.json()["companies_at_limit"]
        assert isinstance(arr, list)
        for c in arr:
            for k in ["name", "plan_name", "patients", "max_patients", "branches",
                      "max_branches", "patients_warning", "branches_warning",
                      "patients_percent", "branches_percent"]:
                assert k in c, f"missing {k} in companies_at_limit entry"

    def test_recent_plan_changes_format(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/superadmin/dashboard", timeout=20)
        arr = r.json()["recent_plan_changes"]
        assert isinstance(arr, list)
        assert len(arr) <= 10
        # Each entry should have NO mongo _id leakage as ObjectId (must be str)
        for h in arr:
            if "_id" in h:
                assert isinstance(h["_id"], str)
            assert "company_name" in h or "new_plan_name" in h

    def test_dashboard_blocked_for_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/superadmin/dashboard", timeout=20)
        assert r.status_code == 403, f"expected 403 for non-superadmin, got {r.status_code}"

    def test_dashboard_blocked_unauthenticated(self):
        r = requests.get(f"{BASE_URL}/api/superadmin/dashboard", timeout=15)
        assert r.status_code in (401, 403)
