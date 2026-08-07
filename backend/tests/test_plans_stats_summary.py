"""Tests for GET /api/plans/stats/summary (SuperAdmin analytics panel)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPERADMIN = {"email": "superadmin@cortexia.com", "password": "Montecristo2026"}
ADMIN = {"email": "admin@cortexia.gt", "password": "Demo123!"}


def _session(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"Login failed for {creds['email']}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def su_headers():
    # kept name for backwards compat but returns a session
    return _session(SUPERADMIN)


@pytest.fixture(scope="module")
def admin_token():
    return _session(ADMIN)


# ---------- Auth ----------
def test_stats_summary_no_auth_returns_401():
    r = requests.get(f"{API}/plans/stats/summary", timeout=30)
    assert r.status_code in (401, 403), r.text
    # 401 preferred
    assert r.status_code == 401


def test_stats_summary_admin_returns_403(admin_token):
    r = admin_token.get(f"{API}/plans/stats/summary", timeout=30)
    assert r.status_code == 403, r.text


def test_stats_summary_superadmin_returns_200(su_headers):
    r = su_headers.get(f"{API}/plans/stats/summary", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in [
        "total_companies_active", "total_plans", "mrr_projected", "arr_projected",
        "plan_changes_last_30d", "revenue_paid_last_30d", "payments_count_last_30d", "per_plan"
    ]:
        assert k in d, f"missing key: {k}"
    assert isinstance(d["per_plan"], list)


# ---------- Shape of per_plan ----------
def test_per_plan_item_shape(su_headers):
    r = su_headers.get(f"{API}/plans/stats/summary", timeout=30)
    d = r.json()
    assert d["per_plan"], "expected at least one plan row (there is real data)"
    row = d["per_plan"][0]
    for k in [
        "plan_id", "plan_name", "price_monthly", "price_yearly", "currency",
        "companies_monthly", "companies_yearly", "total_companies", "mrr", "arr"
    ]:
        assert k in row, f"per_plan row missing {k}"
    assert isinstance(row["mrr"], (int, float))
    assert isinstance(row["arr"], (int, float))


# ---------- MRR / ARR math ----------
def test_mrr_arr_math_matches(su_headers):
    r = su_headers.get(f"{API}/plans/stats/summary", timeout=30)
    d = r.json()
    total_mrr_calc = 0.0
    for row in d["per_plan"]:
        expected_mrr = row["price_monthly"] * row["companies_monthly"] + (row["price_yearly"] / 12) * row["companies_yearly"]
        assert abs(row["mrr"] - round(expected_mrr, 2)) < 0.02, (
            f"MRR mismatch for {row['plan_name']}: expected {expected_mrr} got {row['mrr']}"
        )
        assert abs(row["arr"] - round(expected_mrr * 12, 2)) < 0.05
        total_mrr_calc += expected_mrr
    assert abs(d["mrr_projected"] - round(total_mrr_calc, 2)) < 0.05
    assert abs(d["arr_projected"] - round(total_mrr_calc * 12, 2)) < 0.10


# ---------- Ordering ----------
def test_per_plan_sorted_by_total_companies_desc(su_headers):
    r = su_headers.get(f"{API}/plans/stats/summary", timeout=30)
    counts = [row["total_companies"] for row in r.json()["per_plan"]]
    assert counts == sorted(counts, reverse=True), f"per_plan not sorted desc: {counts}"


# ---------- total_companies_active consistency ----------
def test_total_companies_active_equals_sum(su_headers):
    r = su_headers.get(f"{API}/plans/stats/summary", timeout=30)
    d = r.json()
    total = sum(row["total_companies"] for row in d["per_plan"])
    assert d["total_companies_active"] == total, (
        f"total_companies_active={d['total_companies_active']} sum(per_plan)={total}"
    )


# ---------- Regression: PUT /plans/{id} invalidates cache and reflects on stats ----------
def test_plan_edit_reflects_in_stats(su_headers):
    plans = su_headers.get(f"{API}/plans", timeout=30).json()
    assert plans and isinstance(plans, list)

    # Prefer a plan that has active companies AND a paid price
    d0 = su_headers.get(f"{API}/plans/stats/summary", timeout=30).json()
    target = None
    for row in d0["per_plan"]:
        if row["total_companies"] > 0 and (row["price_monthly"] > 0 or row["price_yearly"] > 0):
            # find full plan doc
            target = next((p for p in plans if p["_id"] == row["plan_id"]), None)
            if target:
                break
    if not target:
        pytest.skip("No paid plan with active companies")

    plan_id = target["_id"]
    original_price = float(target.get("price") or 0)
    bumped = original_price + 111.0

    row0 = next((r for r in d0["per_plan"] if r["plan_id"] == plan_id), None)
    monthly0 = row0["companies_monthly"]

    try:
        # bump via PlanUpdate.price (the model only exposes `price`, not price_monthly)
        u = su_headers.put(f"{API}/plans/{plan_id}",
                         json={"price": bumped}, timeout=30)
        assert u.status_code == 200, u.text
        d1 = su_headers.get(f"{API}/plans/stats/summary", timeout=30).json()
        row1 = next((r for r in d1["per_plan"] if r["plan_id"] == plan_id), None)
        assert row1 is not None
        # price_monthly should reflect immediately (cache invalidation regression)
        assert abs(row1["price_monthly"] - bumped) < 0.01, (
            f"price_monthly cache not invalidated: got {row1['price_monthly']} expected {bumped}"
        )
        expected_delta = 111.0 * monthly0
        assert abs((row1["mrr"] - row0["mrr"]) - expected_delta) < 0.05, (
            f"Expected MRR delta {expected_delta}, got {row1['mrr']-row0['mrr']}"
        )
    finally:
        # restore
        su_headers.put(f"{API}/plans/{plan_id}",
                     json={"price": original_price}, timeout=30)


# ---------- Regression: assign plan updates per_plan counts ----------
def test_assign_plan_updates_per_plan_counts(su_headers):
    plans = su_headers.get(f"{API}/plans", timeout=30).json()
    if len(plans) < 2:
        pytest.skip("Need at least 2 plans")

    # get an active company
    companies = su_headers.get(f"{API}/companies", timeout=30).json()
    if isinstance(companies, dict):
        companies = companies.get("companies") or companies.get("items") or []
    active = [c for c in companies if c.get("is_active", True) is not False and c.get("plan_id")]
    if not active:
        pytest.skip("No active company with plan_id to reassign")
    company = active[0]
    company_id = company.get("_id") or company.get("id")
    original_plan_id = str(company["plan_id"])

    # pick different plan
    other_plan_id = None
    for p in plans:
        if p["_id"] != original_plan_id:
            other_plan_id = p["_id"]
            break
    if not other_plan_id:
        pytest.skip("No alternate plan")

    d0 = su_headers.get(f"{API}/plans/stats/summary", timeout=30).json()
    def _count(d, pid):
        row = next((r for r in d["per_plan"] if r["plan_id"] == pid), None)
        return row["total_companies"] if row else 0
    orig_count_from = _count(d0, original_plan_id)
    orig_count_to = _count(d0, other_plan_id)

    try:
        r = su_headers.put(f"{API}/plans/assign/{company_id}?plan_id={other_plan_id}", timeout=30)
        assert r.status_code == 200, r.text
        d1 = su_headers.get(f"{API}/plans/stats/summary", timeout=30).json()
        assert _count(d1, original_plan_id) == orig_count_from - 1
        assert _count(d1, other_plan_id) == orig_count_to + 1
        # plan_changes_last_30d should have grown by at least 1
        assert d1["plan_changes_last_30d"] >= d0["plan_changes_last_30d"] + 1
    finally:
        # restore
        su_headers.put(f"{API}/plans/assign/{company_id}?plan_id={original_plan_id}", timeout=30)


# ---------- General regression ----------
def test_regression_login_admin_ok():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200


def test_regression_plans_list(su_headers):
    r = su_headers.get(f"{API}/plans", timeout=30)
    assert r.status_code == 200


def test_regression_support_tickets(su_headers):
    r = su_headers.get(f"{API}/support-tickets", timeout=30)
    assert r.status_code in (200, 404), r.text  # endpoint should exist
    assert r.status_code == 200


def test_regression_billing_checkout_route_exists(su_headers):
    # Just verify route responds (may 400 without body, but not 404)
    r = su_headers.post(f"{API}/billing/checkout", json={}, timeout=30)
    assert r.status_code != 404, "billing/checkout route missing"
