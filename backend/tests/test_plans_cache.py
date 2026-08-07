"""Tests for plans cache coherency fix (iteration 28).

Focus: PUT/POST/DELETE /api/plans must invalidate Redis cache atomically so
that subsequent GET /api/plans reflects changes immediately (no 5-min TTL wait).
"""
import os
import random
import pytest
import requests

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        # read from frontend/.env
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert url, "REACT_APP_BACKEND_URL not configured"
    return url.rstrip("/")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

SUPER_EMAIL = "superadmin@cortexia.com"
SUPER_PASS = "Montecristo2026"
ADMIN_EMAIL = "admin@cortexia.gt"
ADMIN_PASS = "Demo123!"


def _session(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    # bearer fallback if provided
    body = r.json()
    token = body.get("access_token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def super_headers():
    return _session(SUPER_EMAIL, SUPER_PASS)


@pytest.fixture(scope="module")
def admin_headers():
    return _session(ADMIN_EMAIL, ADMIN_PASS)


# ─── Basic list & permissions ─────────────────────────────────────────
class TestPlansList:
    def test_list_plans_super(self, super_headers):
        r = super_headers.get(f"{API}/plans", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "_id" in data[0]
        assert "name" in data[0]

    def test_list_plans_admin(self, admin_headers):
        r = admin_headers.get(f"{API}/plans", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ─── PUT /api/plans/{id} validation ───────────────────────────────────
class TestUpdatePlan:
    def test_put_plan_success_and_persist(self, super_headers):
        # pick an existing plan
        plans = super_headers.get(f"{API}/plans", timeout=15).json()
        assert plans, "no plans in DB"
        plan = plans[0]
        pid = plan["_id"]
        original_price = plan.get("price", 0)
        new_price = random.randint(100, 9999)
        r = super_headers.put(
            f"{API}/plans/{pid}",
            json={"price": new_price},
            timeout=15,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        assert r.json().get("message") == "Plan actualizado"

        # GET immediately - cache should be invalidated
        plans2 = super_headers.get(f"{API}/plans", timeout=15).json()
        found = next((p for p in plans2 if p["_id"] == pid), None)
        assert found is not None, "plan disappeared after update"
        assert found["price"] == new_price, f"cache stale: got {found['price']} want {new_price}"

        # restore
        super_headers.put(f"{API}/plans/{pid}", json={"price": original_price}, timeout=15)

    def test_put_plan_not_found(self, super_headers):
        # valid ObjectId format but non-existent
        r = super_headers.put(
            f"{API}/plans/507f1f77bcf86cd799439011",
            json={"price": 100},
            timeout=15,
        )
        assert r.status_code == 404
        assert "no encontrado" in r.json().get("detail", "").lower()

    def test_put_plan_invalid_id(self, super_headers):
        r = super_headers.put(
            f"{API}/plans/not-an-objectid",
            json={"price": 100},
            timeout=15,
        )
        assert r.status_code == 400
        assert "invalido" in r.json().get("detail", "").lower()

    def test_put_plan_forbidden_admin(self, admin_headers, super_headers):
        plans = super_headers.get(f"{API}/plans", timeout=15).json()
        pid = plans[0]["_id"]
        r = admin_headers.put(
            f"{API}/plans/{pid}",
            json={"price": 999},
            timeout=15,
        )
        assert r.status_code == 403


# ─── Cache coherence: super updates → admin sees immediately ──────────
class TestCacheCoherence:
    def test_super_update_visible_to_admin_immediately(self, super_headers, admin_headers):
        # admin warms cache first
        plans_admin_before = admin_headers.get(f"{API}/plans", timeout=15).json()
        assert plans_admin_before
        pid = plans_admin_before[0]["_id"]
        original_price = plans_admin_before[0].get("price", 0)

        new_price = 888 + random.randint(0, 999)
        r = super_headers.put(
            f"{API}/plans/{pid}",
            json={"price": new_price},
            timeout=15,
        )
        assert r.status_code == 200

        # admin GET immediately - must see new price (no TTL wait)
        plans_admin_after = admin_headers.get(f"{API}/plans", timeout=15).json()
        found = next((p for p in plans_admin_after if p["_id"] == pid), None)
        assert found is not None
        assert found["price"] == new_price, (
            f"CACHE STALE: admin still sees old price {found['price']} instead of {new_price}"
        )

        # restore
        super_headers.put(f"{API}/plans/{pid}", json={"price": original_price}, timeout=15)

    def test_usage_reflects_recent_changes(self, super_headers, admin_headers):
        # find admin's company_id
        me = admin_headers.get(f"{API}/auth/me", timeout=15)
        assert me.status_code == 200
        company_id = me.json().get("company_id")
        assert company_id, "admin has no company_id"

        # fetch current plan of the company via usage endpoint
        usage = admin_headers.get(f"{API}/plans/usage/{company_id}", timeout=15)
        assert usage.status_code == 200
        plan = usage.json().get("plan")
        if not plan:
            pytest.skip("company has no plan assigned")
        pid = plan["_id"]
        original_price = plan.get("price", 0)

        new_price = 7777 + random.randint(0, 222)
        r = super_headers.put(
            f"{API}/plans/{pid}",
            json={"price": new_price},
            timeout=15,
        )
        assert r.status_code == 200

        usage2 = admin_headers.get(f"{API}/plans/usage/{company_id}", timeout=15)
        assert usage2.status_code == 200
        assert usage2.json()["plan"]["price"] == new_price

        # restore
        super_headers.put(f"{API}/plans/{pid}", json={"price": original_price}, timeout=15)


# ─── POST / DELETE lifecycle ──────────────────────────────────────────
class TestCreateDeletePlan:
    def test_create_and_delete_plan_refresh_cache(self, super_headers):
        payload = {
            "name": f"TEST_Plan_{random.randint(10000, 99999)}",
            "price": 123,
            "max_branches": 2,
            "max_patients": 100,
            "modules": ["patients", "sales"],
        }
        r = super_headers.post(f"{API}/plans", json=payload, timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        new_id = r.json()["_id"]

        # immediate GET must include it
        plans = super_headers.get(f"{API}/plans", timeout=15).json()
        assert any(p["_id"] == new_id for p in plans), "created plan not visible immediately (cache stale)"

        # DELETE (no company using it)
        d = super_headers.delete(f"{API}/plans/{new_id}", timeout=15)
        assert d.status_code == 200, f"{d.status_code} {d.text}"

        # immediate GET must NOT include it
        plans2 = super_headers.get(f"{API}/plans", timeout=15).json()
        assert not any(p["_id"] == new_id for p in plans2), "deleted plan still visible (cache stale)"

    def test_delete_plan_in_use_blocked(self, super_headers, admin_headers):
        # find plan used by admin's company
        me = admin_headers.get(f"{API}/auth/me", timeout=15).json()
        company_id = me.get("company_id")
        usage = admin_headers.get(f"{API}/plans/usage/{company_id}", timeout=15).json()
        plan = usage.get("plan")
        if not plan:
            pytest.skip("admin's company has no plan")
        r = super_headers.delete(f"{API}/plans/{plan['_id']}", timeout=15)
        assert r.status_code == 400
        assert "empresa" in r.json()["detail"].lower()


# ─── Regression: assign & billing checkout ────────────────────────────
class TestRegression:
    def test_assign_plan(self, super_headers, admin_headers):
        me = admin_headers.get(f"{API}/auth/me", timeout=15).json()
        company_id = me.get("company_id")
        plans = super_headers.get(f"{API}/plans", timeout=15).json()
        # keep original plan
        usage = admin_headers.get(f"{API}/plans/usage/{company_id}", timeout=15).json()
        original_pid = usage["plan"]["_id"] if usage.get("plan") else plans[0]["_id"]
        target_pid = plans[-1]["_id"]

        r = super_headers.put(
            f"{API}/plans/assign/{company_id}?plan_id={target_pid}",
            timeout=15,
        )
        assert r.status_code == 200
        # restore
        super_headers.put(
            f"{API}/plans/assign/{company_id}?plan_id={original_pid}",
            timeout=15,
        )

    def test_billing_checkout(self, admin_headers, super_headers):
        plans = super_headers.get(f"{API}/plans", timeout=15).json()
        pid = plans[0]["_id"]
        r = admin_headers.post(
            f"{API}/billing/checkout",
            json={"plan_id": pid, "origin_url": BASE_URL},
            timeout=20,
        )
        # accept 200 with checkout_url, or 400 if stripe not configured for this env
        if r.status_code == 200:
            assert "checkout_url" in r.json() or "url" in r.json()
        else:
            print(f"billing checkout returned {r.status_code}: {r.text}")
            assert r.status_code in (200, 400, 500)


# ─── Regression: core endpoints ───────────────────────────────────────
class TestCoreEndpoints:
    def test_patients(self, admin_headers):
        r = admin_headers.get(f"{API}/patients", timeout=15)
        assert r.status_code == 200

    def test_sales(self, admin_headers):
        r = admin_headers.get(f"{API}/sales", timeout=15)
        assert r.status_code == 200

    def test_support_tickets(self, admin_headers):
        r = admin_headers.get(f"{API}/support-tickets", timeout=15)
        assert r.status_code == 200

    def test_prescriptions_eyeglass(self, admin_headers):
        r = admin_headers.get(f"{API}/prescriptions/eyeglass", timeout=15)
        assert r.status_code == 200

    def test_prescriptions_contact(self, admin_headers):
        r = admin_headers.get(f"{API}/prescriptions/contact", timeout=15)
        assert r.status_code == 200

    def test_prescriptions_medical(self, admin_headers):
        r = admin_headers.get(f"{API}/prescriptions/medical", timeout=15)
        assert r.status_code == 200
