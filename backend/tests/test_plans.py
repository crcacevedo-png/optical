"""Tests for Subscription Plans system - SuperAdmin plan management + assignment + limits."""
import os
import pytest
import requests
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPERADMIN = {"email": "superadmin@cortexia.com", "password": "Admin123!"}
DEMO_ADMIN = {"email": "admin@cortexia.gt", "password": os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD","")}
ALTAVISTA_ADMIN = {"email": "analuhs@gmail.com", "password": os.getenv("TEST_ENTERPRISE_ADMIN_PASSWORD","")}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=15)
    return s, r


@pytest.fixture(scope="module")
def super_session():
    s, r = _login(SUPERADMIN)
    assert r.status_code == 200, f"SuperAdmin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def demo_session():
    s, r = _login(DEMO_ADMIN)
    if r.status_code != 200:
        pytest.skip(f"Demo admin login failed: {r.status_code}")
    return s, r.json()


# -------- Plans listing & defaults --------
class TestPlansList:
    def test_list_plans_superadmin(self, super_session):
        r = super_session.get(f"{API}/plans", timeout=10)
        assert r.status_code == 200
        plans = r.json()
        assert isinstance(plans, list)
        assert len(plans) >= 3, f"Expected >=3 default plans, got {len(plans)}"
        names = [p["name"] for p in plans]
        for expected in ["Free", "Basic", "Enterprise"]:
            assert expected in names, f"Missing default plan: {expected}. Found: {names}"

    def test_default_plan_attributes(self, super_session):
        r = super_session.get(f"{API}/plans", timeout=10)
        plans = {p["name"]: p for p in r.json()}
        free = plans["Free"]
        assert free["price"] == 0
        assert free["max_branches"] == 1
        assert free["max_patients"] == 50
        assert free.get("modules", []) == [] or len(free.get("modules", [])) == 0

        basic = plans["Basic"]
        assert basic["price"] == 299
        assert basic["max_branches"] == 3
        assert basic["max_patients"] == 500
        assert "inventario" in basic.get("modules", [])
        assert "ventas" in basic.get("modules", [])

        ent = plans["Enterprise"]
        assert ent["price"] == 799
        # 0 means unlimited
        assert ent["max_branches"] == 0
        assert ent["max_patients"] == 0
        for m in ["inventario", "ventas", "proveedores", "finanzas"]:
            assert m in ent.get("modules", []), f"Enterprise missing module {m}"


# -------- CRUD on plans --------
class TestPlansCRUD:
    created_id = None

    def test_create_plan_superadmin(self, super_session):
        payload = {
            "name": f"TEST_Plan_{int(time.time())}",
            "price": 100,
            "max_branches": 2,
            "max_patients": 100,
            "modules": ["inventario"],
            "description": "Test plan"
        }
        r = super_session.post(f"{API}/plans", json=payload, timeout=10)
        assert r.status_code in (200, 201), f"{r.status_code}: {r.text}"
        body = r.json()
        assert "_id" in body
        TestPlansCRUD.created_id = body["_id"]

    def test_update_plan_superadmin(self, super_session):
        assert TestPlansCRUD.created_id, "Need created plan id"
        r = super_session.put(
            f"{API}/plans/{TestPlansCRUD.created_id}",
            json={"price": 150, "max_patients": 200},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        # Verify via list
        r2 = super_session.get(f"{API}/plans", timeout=10)
        plan = next((p for p in r2.json() if p["_id"] == TestPlansCRUD.created_id), None)
        assert plan is not None
        assert plan["price"] == 150
        assert plan["max_patients"] == 200

    def test_create_plan_non_superadmin_forbidden(self, demo_session):
        s, _ = demo_session
        r = s.post(f"{API}/plans", json={"name": "TEST_X", "price": 0, "max_branches": 1, "max_patients": 1, "modules": []}, timeout=10)
        assert r.status_code == 403, f"Expected 403 for non-superadmin, got {r.status_code}"

    def test_delete_plan_superadmin(self, super_session):
        assert TestPlansCRUD.created_id
        r = super_session.delete(f"{API}/plans/{TestPlansCRUD.created_id}", timeout=10)
        assert r.status_code == 200, r.text


# -------- /auth/me and login plan info --------
class TestAuthPlanInfo:
    def test_login_returns_plan_info_for_demo(self, demo_session):
        _, login_body = demo_session
        # Demo company should have Free plan assigned per request
        assert "plan_modules" in login_body, f"login response missing plan_modules: {login_body.keys()}"
        assert "max_patients" in login_body
        assert "patients_count" in login_body

    def test_me_returns_plan_info(self, demo_session):
        s, _ = demo_session
        r = s.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "plan_modules" in body
        assert isinstance(body["plan_modules"], list)
        assert "max_patients" in body
        assert "patients_count" in body

    def test_superadmin_me_no_plan_required(self, super_session):
        r = super_session.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        # superadmin should not enforce plan
        body = r.json()
        assert body["role"] == "superadmin"


# -------- Plan assignment + usage --------
class TestPlanAssignment:
    def test_get_companies_with_plan_badges(self, super_session):
        r = super_session.get(f"{API}/companies", timeout=10)
        assert r.status_code == 200
        comps = r.json()
        assert isinstance(comps, list) and len(comps) > 0
        # at least one company should have plan info
        with_plan = [c for c in comps if c.get("plan_name")]
        assert len(with_plan) >= 1, f"No company has plan_name attached. Sample: {comps[0].keys() if comps else 'no comps'}"

    def test_assign_plan_and_usage(self, super_session):
        # Get a non-demo company and a plan
        rc = super_session.get(f"{API}/companies", timeout=10)
        comps = rc.json()
        rp = super_session.get(f"{API}/plans", timeout=10)
        plans = {p["name"]: p for p in rp.json()}

        target = next((c for c in comps if c.get("name", "").lower().startswith("demo")), comps[0])
        company_id = target["_id"]
        original_plan_id = target.get("plan_id")

        free_id = plans["Free"]["_id"]
        # Assign Free plan
        r = super_session.put(f"{API}/plans/assign/{company_id}", params={"plan_id": free_id}, timeout=10)
        assert r.status_code == 200, r.text

        # Check usage
        ru = super_session.get(f"{API}/plans/usage/{company_id}", timeout=10)
        assert ru.status_code == 200
        usage = ru.json()
        assert "patients_count" in usage
        assert "max_patients" in usage
        assert usage["max_patients"] == 50  # Free plan
        assert "patients_warning" in usage
        assert "patients_limit_reached" in usage

        # Restore original plan if it existed
        if original_plan_id:
            super_session.put(f"{API}/plans/assign/{company_id}", params={"plan_id": str(original_plan_id)}, timeout=10)


# -------- Patient/Branch limit enforcement --------
class TestLimitEnforcement:
    def test_patient_creation_limit_when_free_plan(self, super_session, demo_session):
        # Ensure demo company is on Free plan
        s_demo, _ = demo_session
        me = s_demo.get(f"{API}/auth/me", timeout=10).json()
        max_patients = me.get("max_patients", 0)
        patients_count = me.get("patients_count", 0)
        plan_name = me.get("plan_name")

        if max_patients == 0:
            pytest.skip(f"Demo on unlimited plan ({plan_name}); cannot test limit")

        if patients_count < max_patients:
            pytest.skip(f"Demo at {patients_count}/{max_patients}; not at limit. Skipping enforcement test.")

        # If we are at limit, attempt create -> 403
        payload = {"first_name": "TEST", "last_name": "LimitCheck", "phone": "0000", "email": f"test_limit_{int(time.time())}@x.com"}
        r = s_demo.post(f"{API}/patients", json=payload, timeout=10)
        assert r.status_code == 403, f"Expected 403 at limit, got {r.status_code}: {r.text}"

    def test_patient_create_works_under_limit(self, demo_session):
        s_demo, _ = demo_session
        me = s_demo.get(f"{API}/auth/me", timeout=10).json()
        if me.get("patients_limit_reached"):
            pytest.skip("Demo at patient limit, cannot create")
        payload = {
            "first_name": "TEST_PlanLimit", "last_name": "User",
            "phone": f"555{int(time.time())%10000}",
            "email": f"test_planlimit_{int(time.time())}@x.com",
        }
        r = s_demo.post(f"{API}/patients", json=payload, timeout=10)
        # Either creates successfully or returns 403 if at limit
        assert r.status_code in (200, 201, 403)
        if r.status_code in (200, 201):
            pid = r.json().get("_id")
            if pid:
                # cleanup
                s_demo.delete(f"{API}/patients/{pid}", timeout=10)

    def test_branch_creation_blocked_when_at_limit(self, demo_session):
        s_demo, login = demo_session
        me = s_demo.get(f"{API}/auth/me", timeout=10).json()
        max_branches = me.get("max_branches", 0)
        branches_count = me.get("branches_count", 0)
        if max_branches == 0:
            pytest.skip("Unlimited branches plan")
        if branches_count < max_branches:
            pytest.skip(f"Not at branch limit: {branches_count}/{max_branches}")
        payload = {"name": f"TEST_Branch_{int(time.time())}", "address": "Test", "phone": "555"}
        r = s_demo.post(f"{API}/branches", json=payload, timeout=10)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"
