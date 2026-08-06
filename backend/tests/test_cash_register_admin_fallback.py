"""Tests for cash_register fallback fix: admins without branch_id."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")

ADMIN = ("admin@cortexia.gt", "Demo123!")
SELLER = ("vendedor@cortexia.gt", "Demo123!")
SUPERADMIN = ("superadmin@cortexia.com", "Montecristo2026")


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    # Auth is httpOnly cookie-based; also try Bearer if provided
    tok = data.get("token") or data.get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s, data


def _ensure_closed(s):
    try:
        r = s.get(f"{BASE_URL}/api/cash-register/current", timeout=30)
        if r.status_code == 200 and r.json().get("register"):
            s.post(f"{BASE_URL}/api/cash-register/close",
                   json={"counted_cash": 0, "closing_notes": "cleanup"}, timeout=30)
    except Exception:
        pass


@pytest.fixture(scope="module")
def admin_sess():
    s, user = _login(*ADMIN)
    print(f"[admin] role={user.get('role')} branch_id={user.get('branch_id')}")
    assert user.get("branch_id") in (None, ""), f"Admin should have no branch_id but has {user.get('branch_id')}"
    _ensure_closed(s)
    yield s
    _ensure_closed(s)


@pytest.fixture(scope="module")
def seller_sess():
    s, user = _login(*SELLER)
    print(f"[seller] role={user.get('role')} branch_id={user.get('branch_id')}")
    _ensure_closed(s)
    yield s
    _ensure_closed(s)


# ---------- Admin fallback tests ----------

def test_admin_open_without_branch_uses_fallback(admin_sess):
    r = admin_sess.post(f"{BASE_URL}/api/cash-register/open",
                        json={"opening_amount": 100, "opening_notes": "TEST admin fallback"}, timeout=30)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    reg = body.get("register") or body
    assert reg.get("branch_id"), f"branch_id must not be null: {body}"
    assert reg.get("status") == "open"


def test_admin_current_returns_open_register(admin_sess):
    r = admin_sess.get(f"{BASE_URL}/api/cash-register/current", timeout=30)
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    assert r.json().get("register") is not None


def test_admin_current_preview(admin_sess):
    r = admin_sess.get(f"{BASE_URL}/api/cash-register/current/preview", timeout=30)
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"


def test_admin_close_register(admin_sess):
    r = admin_sess.post(f"{BASE_URL}/api/cash-register/close",
                       json={"counted_cash": 100, "closing_notes": "TEST close"}, timeout=30)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


def test_admin_open_with_branch_override(admin_sess):
    br = admin_sess.get(f"{BASE_URL}/api/branches", timeout=30)
    assert br.status_code == 200, br.text
    branches = br.json()
    branches = branches if isinstance(branches, list) else branches.get("branches", [])
    assert branches, "No branches available"
    target = branches[0]
    bid = target.get("id") or target.get("_id")
    assert bid

    _ensure_closed(admin_sess)
    r = admin_sess.post(f"{BASE_URL}/api/cash-register/open?branch_id={bid}",
                        json={"opening_amount": 50}, timeout=30)
    assert r.status_code == 200, f"override open failed: {r.status_code} {r.text}"
    reg = r.json().get("register") or r.json()
    assert reg.get("branch_id") == bid, f"override not respected: {reg.get('branch_id')} vs {bid}"

    rc = admin_sess.post(f"{BASE_URL}/api/cash-register/close?branch_id={bid}",
                         json={"counted_cash": 50}, timeout=30)
    assert rc.status_code == 200, rc.text


# ---------- Seller regression ----------

def test_seller_open_uses_own_branch(seller_sess):
    r = seller_sess.post(f"{BASE_URL}/api/cash-register/open",
                         json={"opening_amount": 25}, timeout=30)
    assert r.status_code == 200, f"seller open failed: {r.status_code} {r.text}"
    reg = r.json().get("register") or r.json()
    assert reg.get("branch_id"), reg
    seller_sess.post(f"{BASE_URL}/api/cash-register/close",
                     json={"counted_cash": 25}, timeout=30)


# ---------- Superadmin denied ----------

def test_superadmin_cannot_open():
    s, _ = _login(*SUPERADMIN)
    r = s.post(f"{BASE_URL}/api/cash-register/open",
               json={"opening_amount": 0}, timeout=30)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


# ---------- Regression on other endpoints ----------

@pytest.mark.parametrize("path", [
    "/api/sales",
    "/api/patients",
    "/api/inventory/products",
    "/api/quotations",
    "/api/support-tickets",
])
def test_regression_endpoints_ok(admin_sess, path):
    r = admin_sess.get(f"{BASE_URL}{path}", timeout=30)
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"
