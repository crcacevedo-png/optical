"""Backend tests para el módulo Billing (Stripe Checkout self-service).

Cobertura:
- POST /api/billing/checkout (admin, plan válido, mensual/anual, plan gratuito, plan_id inválido/inexistente, no admin)
- GET /api/billing/status/{session_id} (existente/inexistente)
- GET /api/billing/my-transactions (admin scope, superadmin all, vendedor 403)
- POST /api/webhook/stripe (existencia + body inválido -> 400)
- Regresiones básicas de plans, patients, sales, support-tickets, cash-register
Auth basado en cookies httpOnly (requests.Session).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ORIGIN = BASE_URL

SUPERADMIN = {"email": "superadmin@cortexia.com", "password": "Montecristo2026"}
ADMIN = {"email": "admin@cortexia.gt", "password": "Demo123!"}
VENDEDOR = {"email": "vendedor@cortexia.gt", "password": "Demo123!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login {creds['email']} failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def admin_s():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def vendedor_s():
    return _login(VENDEDOR)


@pytest.fixture(scope="module")
def super_s():
    # Fallback si Montecristo2026 falla
    try:
        return _login(SUPERADMIN)
    except AssertionError:
        return _login({"email": "superadmin@cortexia.com", "password": "Admin123!"})


@pytest.fixture(scope="module")
def plans(admin_s):
    r = admin_s.get(f"{API}/plans", timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def paid_plan(plans):
    for p in plans:
        price = p.get("price_monthly") or p.get("price") or 0
        if float(price or 0) > 0:
            return p
    pytest.skip("No hay planes de pago disponibles")


@pytest.fixture(scope="module")
def free_plan(plans):
    for p in plans:
        pm = float(p.get("price_monthly") or 0)
        py = float(p.get("price_yearly") or 0)
        pr = float(p.get("price") or 0)
        if pm == 0 and py == 0 and pr == 0:
            return p
    pytest.skip("No hay plan gratuito")


def _plan_id(p):
    return p.get("id") or p.get("_id")


# ─────── Checkout ───────

def test_checkout_admin_monthly(admin_s, paid_plan):
    r = admin_s.post(
        f"{API}/billing/checkout",
        json={"plan_id": _plan_id(paid_plan), "billing_cycle": "monthly", "origin_url": ORIGIN},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["checkout_url"].startswith("https://checkout.stripe.com/"), data
    assert data["session_id"].startswith("cs_"), data
    pytest.session_id_monthly = data["session_id"]


def test_checkout_admin_yearly(admin_s, paid_plan):
    r = admin_s.post(
        f"{API}/billing/checkout",
        json={"plan_id": _plan_id(paid_plan), "billing_cycle": "yearly", "origin_url": ORIGIN},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["checkout_url"].startswith("https://checkout.stripe.com/")
    sid = data["session_id"]
    rs = admin_s.get(f"{API}/billing/status/{sid}", timeout=30)
    assert rs.status_code == 200
    js = rs.json()
    assert js["billing_cycle"] == "yearly"
    assert js["status"] == "initiated"
    assert js["payment_status"] == "pending"


def test_checkout_free_plan_400(admin_s, free_plan):
    r = admin_s.post(
        f"{API}/billing/checkout",
        json={"plan_id": _plan_id(free_plan), "billing_cycle": "monthly", "origin_url": ORIGIN},
        timeout=30,
    )
    assert r.status_code == 400, r.text
    assert "gratuito" in r.json().get("detail", "").lower()


def test_checkout_non_admin_403(vendedor_s, paid_plan):
    r = vendedor_s.post(
        f"{API}/billing/checkout",
        json={"plan_id": _plan_id(paid_plan), "billing_cycle": "monthly", "origin_url": ORIGIN},
        timeout=30,
    )
    assert r.status_code == 403, r.text
    assert "administradores" in r.json().get("detail", "").lower()


def test_checkout_invalid_plan_id_400(admin_s):
    r = admin_s.post(
        f"{API}/billing/checkout",
        json={"plan_id": "not-an-objectid", "billing_cycle": "monthly", "origin_url": ORIGIN},
        timeout=30,
    )
    assert r.status_code == 400, r.text


def test_checkout_nonexistent_plan_404(admin_s):
    r = admin_s.post(
        f"{API}/billing/checkout",
        json={"plan_id": "507f1f77bcf86cd799439011", "billing_cycle": "monthly", "origin_url": ORIGIN},
        timeout=30,
    )
    assert r.status_code == 404, r.text


# ─────── Status ───────

def test_status_existing(admin_s):
    sid = getattr(pytest, "session_id_monthly", None)
    if not sid:
        pytest.skip("no session_id creado")
    r = admin_s.get(f"{API}/billing/status/{sid}", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["session_id"] == sid
    assert data["status"] == "initiated"
    assert data["payment_status"] == "pending"
    assert data["billing_cycle"] == "monthly"
    assert data.get("plan_name")


def test_status_nonexistent_404(admin_s):
    r = admin_s.get(f"{API}/billing/status/cs_test_does_not_exist_xyz", timeout=30)
    assert r.status_code == 404


# ─────── My Transactions ───────

def test_my_transactions_admin(admin_s):
    r = admin_s.get(f"{API}/billing/my-transactions", timeout=30)
    assert r.status_code == 200, r.text
    txs = r.json()
    assert isinstance(txs, list)
    assert len(txs) >= 1
    company_ids = {t.get("company_id") for t in txs}
    assert len(company_ids) == 1


def test_my_transactions_superadmin(super_s):
    r = super_s.get(f"{API}/billing/my-transactions?limit=100", timeout=30)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_my_transactions_vendedor_403(vendedor_s):
    r = vendedor_s.get(f"{API}/billing/my-transactions", timeout=30)
    assert r.status_code == 403


# ─────── Webhook ───────

def test_webhook_exists_invalid_body_400():
    r = requests.post(f"{API}/webhook/stripe", data=b"", headers={"Stripe-Signature": ""}, timeout=30)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"
    detail = (r.json().get("detail") or "").lower()
    assert "invalido" in detail or "invalid" in detail


# ─────── Regresión ───────

def test_regression_plans_list(admin_s):
    assert admin_s.get(f"{API}/plans", timeout=30).status_code == 200


def test_regression_plans_usage(admin_s):
    me = admin_s.get(f"{API}/auth/me", timeout=30).json()
    cid = me.get("company_id")
    if not cid:
        pytest.skip("no company_id")
    assert admin_s.get(f"{API}/plans/usage/{cid}", timeout=30).status_code == 200


def test_regression_plans_history(super_s, admin_s):
    # /plans/history/{company_id} es superadmin-only (403 para admin)
    me = admin_s.get(f"{API}/auth/me", timeout=30).json()
    cid = me.get("company_id")
    if not cid:
        pytest.skip("no company_id")
    assert super_s.get(f"{API}/plans/history/{cid}", timeout=30).status_code == 200


def test_regression_patients(admin_s):
    assert admin_s.get(f"{API}/patients", timeout=30).status_code == 200


def test_regression_sales(admin_s):
    assert admin_s.get(f"{API}/sales", timeout=30).status_code == 200


def test_regression_support_tickets(admin_s):
    assert admin_s.get(f"{API}/support-tickets", timeout=30).status_code == 200


def test_regression_cash_register_current(admin_s):
    r = admin_s.get(f"{API}/cash-register/current", timeout=30)
    assert r.status_code in (200, 404)


def test_regression_plans_assign_superadmin(super_s, admin_s, plans):
    me = admin_s.get(f"{API}/auth/me", timeout=30).json()
    cid = me["company_id"]
    plan_id = _plan_id(plans[0])
    r = super_s.put(f"{API}/plans/assign/{cid}?plan_id={plan_id}", timeout=30)
    assert r.status_code == 200, r.text
