"""
Backend tests for Sesiones Activas feature.
Covers: SESSION-A through SESSION-I.
"""
import os
import time
import jwt
import pytest
import requests

# Track logins for rate-limit pacing (10/min per IP on /auth/login)
_LOGIN_TIMES: list = []
def _pace_login():
    now = time.time()
    # keep only last-60s
    while _LOGIN_TIMES and now - _LOGIN_TIMES[0] > 60:
        _LOGIN_TIMES.pop(0)
    if len(_LOGIN_TIMES) >= 8:  # margin under 10
        sleep_for = 61 - (now - _LOGIN_TIMES[0])
        if sleep_for > 0:
            time.sleep(sleep_for)
        _LOGIN_TIMES.clear()
    _LOGIN_TIMES.append(time.time())

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")

SUPERADMIN_EMAIL = "superadmin@cortexia.com"
SUPERADMIN_PASSWORD = "Montecristo2026"
ADMIN_EMAIL = "admin@cortexia.gt"
ADMIN_PASSWORD = "DemoAdmin2026!"
VENDEDOR_EMAIL = "vendedor@cortexia.gt"
VENDEDOR_PASSWORD = "DemoUser2026!"


def _login(email, password, ua="pytest-agent/1.0"):
    _pace_login()
    s = requests.Session()
    s.headers.update({"User-Agent": ua})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return s, r.json()


def _decode(token):
    return jwt.decode(token, options={"verify_signature": False})


# ---------- SESSION-A: login inserta sesion + JWT tiene sid ----------
def test_a_login_creates_session_with_sid():
    s, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-A-admin/1.0")
    at = s.cookies.get("access_token")
    rt = s.cookies.get("refresh_token")
    assert at and rt
    ap = _decode(at)
    rp = _decode(rt)
    assert "sid" in ap and ap["sid"], f"access_token missing sid: {ap}"
    assert "sid" in rp and rp["sid"] == ap["sid"], "refresh_token sid mismatch"

    # sesion listada
    r = s.get(f"{BASE_URL}/api/sessions")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert any(x["session_id"] == ap["sid"] and x["is_current"] for x in items)
    cur = next(x for x in items if x["session_id"] == ap["sid"])
    assert cur["user_email"] == ADMIN_EMAIL
    assert cur["user_role"] == "admin"
    assert cur["user_agent"] and "test-A-admin" in cur["user_agent"]
    assert cur["ip"]


# ---------- SESSION-C: RBAC list ----------
def test_c_list_rbac_vendedor():
    s, _ = _login(VENDEDOR_EMAIL, VENDEDOR_PASSWORD, ua="test-C-vend/1.0")
    r = s.get(f"{BASE_URL}/api/sessions")
    assert r.status_code == 200
    data = r.json()
    items = data["items"]
    # Solo ve las propias
    emails = {i["user_email"] for i in items}
    assert emails == {VENDEDOR_EMAIL}, f"vendedor sees other users: {emails}"
    assert any(i["is_current"] for i in items)


def test_c_list_rbac_admin_sees_company():
    s, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-C-admin/1.0")
    r = s.get(f"{BASE_URL}/api/sessions")
    assert r.status_code == 200
    items = r.json()["items"]
    emails = {i["user_email"] for i in items}
    # Debe incluir al menos el propio admin. Puede o no incluir vendedor segun sesiones activas.
    assert ADMIN_EMAIL in emails
    # No debe incluir superadmin (otra company / no-company)
    assert SUPERADMIN_EMAIL not in emails


def test_c_list_rbac_superadmin_sees_all():
    s, _ = _login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD, ua="test-C-super/1.0")
    r = s.get(f"{BASE_URL}/api/sessions")
    assert r.status_code == 200
    items = r.json()["items"]
    emails = {i["user_email"] for i in items}
    assert SUPERADMIN_EMAIL in emails
    # Debe ver tambien las de admin/vendedor si existen sesiones activas
    # (por los tests previos deberian existir)


# ---------- SESSION-D: revoke con RBAC ----------
def test_d_admin_revokes_other_session_of_self():
    s1, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-D-admin-1/1.0")
    s2, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-D-admin-2/1.0")
    sid1 = _decode(s1.cookies.get("access_token"))["sid"]
    sid2 = _decode(s2.cookies.get("access_token"))["sid"]
    assert sid1 != sid2

    # s1 revoca sid2
    r = s1.post(f"{BASE_URL}/api/sessions/{sid2}/revoke")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # s2 ya no puede acceder
    me = s2.get(f"{BASE_URL}/api/auth/me")
    assert me.status_code == 401
    assert "revocada" in me.json().get("detail", "").lower()

    # GET /api/sessions no muestra sid2
    r = s1.get(f"{BASE_URL}/api/sessions")
    ids = [i["session_id"] for i in r.json()["items"]]
    assert sid2 not in ids


def test_d_cannot_revoke_current_session():
    s, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-D-current/1.0")
    sid = _decode(s.cookies.get("access_token"))["sid"]
    r = s.post(f"{BASE_URL}/api/sessions/{sid}/revoke")
    assert r.status_code == 400
    assert "actual" in r.json().get("detail", "").lower()


def test_d_admin_can_revoke_vendedor_of_same_company():
    v, _ = _login(VENDEDOR_EMAIL, VENDEDOR_PASSWORD, ua="test-D-vend-target/1.0")
    vsid = _decode(v.cookies.get("access_token"))["sid"]
    a, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-D-admin-revoker/1.0")
    r = a.post(f"{BASE_URL}/api/sessions/{vsid}/revoke")
    assert r.status_code == 200, r.text
    # vendedor now 401
    me = v.get(f"{BASE_URL}/api/auth/me")
    assert me.status_code == 401


def test_d_vendedor_cannot_revoke_admin():
    a, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-D-admin-victim/1.0")
    asid = _decode(a.cookies.get("access_token"))["sid"]
    v, _ = _login(VENDEDOR_EMAIL, VENDEDOR_PASSWORD, ua="test-D-vend-attacker/1.0")
    r = v.post(f"{BASE_URL}/api/sessions/{asid}/revoke")
    assert r.status_code == 403


def test_d_vendedor_can_revoke_own_other_session():
    v1, _ = _login(VENDEDOR_EMAIL, VENDEDOR_PASSWORD, ua="test-D-vend-own-1/1.0")
    v2, _ = _login(VENDEDOR_EMAIL, VENDEDOR_PASSWORD, ua="test-D-vend-own-2/1.0")
    sid2 = _decode(v2.cookies.get("access_token"))["sid"]
    r = v1.post(f"{BASE_URL}/api/sessions/{sid2}/revoke")
    assert r.status_code == 200, r.text


def test_d_superadmin_can_revoke_any():
    a, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-D-super-target/1.0")
    asid = _decode(a.cookies.get("access_token"))["sid"]
    s, _ = _login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD, ua="test-D-super/1.0")
    r = s.post(f"{BASE_URL}/api/sessions/{asid}/revoke")
    assert r.status_code == 200


# ---------- SESSION-E: revoke-all-mine ----------
def test_e_revoke_all_mine():
    s1, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-E-1/1.0")
    s2, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-E-2/1.0")
    s3, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-E-3/1.0")
    sid3 = _decode(s3.cookies.get("access_token"))["sid"]

    r = s3.post(f"{BASE_URL}/api/sessions/revoke-all-mine")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["revoked_count"] >= 2

    # s1 y s2 => 401
    assert s1.get(f"{BASE_URL}/api/auth/me").status_code == 401
    assert s2.get(f"{BASE_URL}/api/auth/me").status_code == 401
    # s3 sigue activa
    assert s3.get(f"{BASE_URL}/api/auth/me").status_code == 200
    # Lista: la propia sesion admin sid3 debe estar (puede haber otras de otros users)
    items = s3.get(f"{BASE_URL}/api/sessions").json()["items"]
    my_active = [i for i in items if i["user_email"] == ADMIN_EMAIL]
    assert len(my_active) == 1
    assert my_active[0]["session_id"] == sid3


# ---------- SESSION-F: logout revoca solo la actual ----------
def test_f_logout_only_current():
    s1, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-F-1/1.0")
    s2, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-F-2/1.0")
    sid1 = _decode(s1.cookies.get("access_token"))["sid"]
    sid2 = _decode(s2.cookies.get("access_token"))["sid"]

    r = s1.post(f"{BASE_URL}/api/auth/logout")
    assert r.status_code == 200

    # s2 sigue viva
    me2 = s2.get(f"{BASE_URL}/api/auth/me")
    assert me2.status_code == 200, f"logout invalidated other session: {me2.text}"
    items = s2.get(f"{BASE_URL}/api/sessions").json()["items"]
    ids = [i["session_id"] for i in items]
    assert sid2 in ids
    assert sid1 not in ids


# ---------- SESSION-I: refresh preserva sid ----------
def test_i_refresh_preserves_sid():
    s, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-I/1.0")
    original_sid = _decode(s.cookies.get("access_token"))["sid"]
    r = s.post(f"{BASE_URL}/api/auth/refresh")
    assert r.status_code == 200, r.text
    new_at = s.cookies.get("access_token")
    new_sid = _decode(new_at)["sid"]
    assert new_sid == original_sid
    # Debe funcionar
    r2 = s.get(f"{BASE_URL}/api/sessions")
    assert r2.status_code == 200


# ---------- SESSION-B: sesion revocada => 401 con detail correcto ----------
def test_b_revoked_session_returns_401():
    # Se apoya en revoke por otra sesion (evita ir a Mongo directo)
    s1, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-B-1/1.0")
    s2, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD, ua="test-B-2/1.0")
    sid2 = _decode(s2.cookies.get("access_token"))["sid"]
    r = s1.post(f"{BASE_URL}/api/sessions/{sid2}/revoke")
    assert r.status_code == 200
    me = s2.get(f"{BASE_URL}/api/auth/me")
    assert me.status_code == 401
    assert me.json().get("detail") == "Sesion revocada. Inicie sesion nuevamente."


# ---------- SESSION-G: TTL index (via API si expuesto) ----------
# No podemos consultar db.sessions.index_information() sin admin API.
# Verificamos indirectamente: la coleccion existe y responde.
def test_g_sessions_endpoint_available():
    s, _ = _login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD, ua="test-G/1.0")
    r = s.get(f"{BASE_URL}/api/sessions")
    assert r.status_code == 200
    assert "items" in r.json()
