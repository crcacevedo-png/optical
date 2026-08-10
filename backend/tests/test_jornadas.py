"""Backend tests for Jornadas module (Iter 1).

Cubre:
- Plan gating (Free -> 402, Basic -> 200)
- CRUD + validaciones
- Filtros de listado
- Detalle y summary
- Transiciones de estado (activate/start-closing/close/cancel/reopen)
- Validaciones de negocio (motivo obligatorio, inventario, superadmin)
- Multi-tenant
"""
import os
import pytest
import requests
import uuid
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPERADMIN_EMAIL = "superadmin@cortexia.com"
SUPERADMIN_PASSWORD = "Montecristo2026"
BASIC_ADMIN_EMAIL = "admin@cortexia.gt"
BASIC_ADMIN_PASSWORD = "Demo123!"
FREE_ADMIN_EMAIL = "analuhs@gmail.com"
FREE_ADMIN_PASSWORD = "Alta2026$"

BRANCH_ID_BASIC = "69d458bb6a6b539b3084f0a3"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        return None, None
    return s, r.json()


@pytest.fixture(scope="module")
def basic_token():
    s, data = _login(BASIC_ADMIN_EMAIL, BASIC_ADMIN_PASSWORD)
    if not s:
        pytest.skip("No se pudo autenticar admin basic")
    return s, data


@pytest.fixture(scope="module")
def super_token():
    s, _ = _login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    if not s:
        pytest.skip("No se pudo autenticar superadmin")
    return s


@pytest.fixture(scope="module")
def free_token():
    s, data = _login(FREE_ADMIN_EMAIL, FREE_ADMIN_PASSWORD)
    return s, data


def _h(token):
    # Compatibilidad: token es en realidad la sesion con cookies
    return {}


# ─── LOGIN / plan_modules ───────────────────────────────────────────
def test_login_basic_returns_plan_modules(basic_token):
    _, data = basic_token
    user = data.get("user") or data
    # plan_modules puede venir en user o en root
    modules = user.get("plan_modules") or data.get("plan_modules")
    assert modules is not None, "Se esperaba plan_modules en login response"
    assert "jornadas" in modules, f"admin@cortexia.gt debe tener modulo jornadas. Modulos: {modules}"


def test_auth_me_basic_has_jornadas_module(basic_token):
    token, _ = basic_token
    r = token.get(f"{API}/auth/me", timeout=10)
    assert r.status_code == 200
    modules = r.json().get("plan_modules") or []
    assert "jornadas" in modules


# ─── PLAN GATING ────────────────────────────────────────────────────
def test_free_admin_cannot_list_jornadas(free_token):
    token, data = free_token
    if not token:
        pytest.skip(f"No se pudo autenticar {FREE_ADMIN_EMAIL} (posiblemente cambio password)")
    # Verificar que su plan NO tenga jornadas
    r = token.get(f"{API}/auth/me", timeout=10)
    modules = r.json().get("plan_modules") or []
    if "jornadas" in modules:
        pytest.skip(f"{FREE_ADMIN_EMAIL} no esta en plan Free (tiene jornadas). Skip gating test.")
    r = token.get(f"{API}/jornadas", timeout=10)
    assert r.status_code == 402, f"Se esperaba 402 gating, obtuvo {r.status_code}: {r.text[:200]}"


def test_basic_admin_can_list_jornadas(basic_token):
    token, _ = basic_token
    r = token.get(f"{API}/jornadas", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data and "total" in data
    assert isinstance(data["items"], list)


# ─── CRUD ───────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def created_jornada(basic_token):
    token, _ = basic_token
    payload = {
        "name": f"TEST_Jornada_{uuid.uuid4().hex[:6]}",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=2)).isoformat(),
        "responsible_branch_id": BRANCH_ID_BASIC,
        "location": "Feria Test",
        "cash_config": {"mode": "own", "initial_fund": 500},
        "inventory_config": {"use_branch_stock": True, "use_consignment": False},
        "goal_amount": 5000,
        "goal_patients": 20,
    }
    r = token.post(f"{API}/jornadas", json=payload, timeout=15)
    assert r.status_code in (200, 201), f"Create fallo: {r.status_code} {r.text[:300]}"
    jid = r.json().get("_id")
    assert jid
    yield jid, token
    # cleanup (soft delete via API si sigue planificada)
    try:
        token.delete(f"{API}/jornadas/{jid}", timeout=10)
    except Exception:
        pass


def test_create_jornada_returns_id(created_jornada):
    jid, _ = created_jornada
    assert isinstance(jid, str) and len(jid) == 24


def test_create_jornada_end_before_start_rejected(basic_token):
    token, _ = basic_token
    payload = {
        "name": f"TEST_BadDates_{uuid.uuid4().hex[:6]}",
        "start_date": (date.today() + timedelta(days=5)).isoformat(),
        "end_date": date.today().isoformat(),
        "responsible_branch_id": BRANCH_ID_BASIC,
        "cash_config": {"mode": "own", "initial_fund": 0},
        "inventory_config": {"use_branch_stock": True},
    }
    r = token.post(f"{API}/jornadas", json=payload, timeout=10)
    assert r.status_code == 400, f"esperado 400, obtuvo {r.status_code}: {r.text[:200]}"


def test_get_jornada_detail(created_jornada):
    jid, token = created_jornada
    r = token.get(f"{API}/jornadas/{jid}", timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j.get("_id") == jid or j.get("id") == jid
    assert j.get("status") == "planificada"
    assert "responsible_branch_name" in j or j.get("responsible_branch_id")


def test_get_summary_has_kpis(created_jornada):
    jid, token = created_jornada
    r = token.get(f"{API}/jornadas/{jid}/summary", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "kpis" in body
    kpis = body["kpis"]
    for key in ("total_sold", "patients_count", "cash_balance"):
        assert key in kpis
    # goal_amount_pct debe existir (era 5000, sold=0 => 0.0)
    assert "goal_amount_pct" in kpis


def test_list_jornadas_filter_status(basic_token, created_jornada):
    token, _ = basic_token
    r = token.get(f"{API}/jornadas?status=planificada", timeout=10)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i.get("status") == "planificada" for i in items)


def test_list_jornadas_filter_invalid_status(basic_token):
    token, _ = basic_token
    r = token.get(f"{API}/jornadas?status=xxx", timeout=10)
    assert r.status_code == 400


def test_list_jornadas_search(basic_token, created_jornada):
    token, _ = basic_token
    jid, _ = created_jornada
    r = token.get(f"{API}/jornadas?search=TEST_", timeout=10)
    assert r.status_code == 200
    ids = [i.get("_id") or i.get("id") for i in r.json()["items"]]
    assert jid in ids


def test_update_jornada_planned(created_jornada):
    jid, token = created_jornada
    r = token.put(f"{API}/jornadas/{jid}",
                     json={"description": "actualizada por test"}, timeout=10)
    assert r.status_code == 200
    r2 = token.get(f"{API}/jornadas/{jid}", timeout=10)
    assert r2.json().get("description") == "actualizada por test"


# ─── TRANSICIONES ───────────────────────────────────────────────────
def test_activate_requires_inventory_source(basic_token):
    token, _ = basic_token
    # Crear con inventario sin fuentes
    payload = {
        "name": f"TEST_NoInv_{uuid.uuid4().hex[:6]}",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=1)).isoformat(),
        "responsible_branch_id": BRANCH_ID_BASIC,
        "cash_config": {"mode": "own", "initial_fund": 0},
        "inventory_config": {"use_branch_stock": False, "use_consignment": False},
    }
    r = token.post(f"{API}/jornadas", json=payload, timeout=10)
    assert r.status_code in (200, 201)
    jid = r.json()["_id"]
    r2 = token.post(f"{API}/jornadas/{jid}/activate", timeout=10)
    assert r2.status_code == 400
    # cleanup
    token.delete(f"{API}/jornadas/{jid}", timeout=10)


def test_full_lifecycle_transitions(basic_token):
    token, _ = basic_token
    payload = {
        "name": f"TEST_Lifecycle_{uuid.uuid4().hex[:6]}",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=1)).isoformat(),
        "responsible_branch_id": BRANCH_ID_BASIC,
        "cash_config": {"mode": "own", "initial_fund": 100},
        "inventory_config": {"use_branch_stock": True},
    }
    r = token.post(f"{API}/jornadas", json=payload, timeout=10)
    jid = r.json()["_id"]
    # activate
    r1 = token.post(f"{API}/jornadas/{jid}/activate", timeout=10)
    assert r1.status_code == 200, r1.text[:200]
    # invalid: activate again
    r2 = token.post(f"{API}/jornadas/{jid}/activate", timeout=10)
    assert r2.status_code == 400
    # start-closing
    r3 = token.post(f"{API}/jornadas/{jid}/start-closing", timeout=10)
    assert r3.status_code == 200
    # close
    r4 = token.post(f"{API}/jornadas/{jid}/close", timeout=10)
    assert r4.status_code == 200
    # editing cerrada -> 400
    r5 = token.put(f"{API}/jornadas/{jid}", json={"description": "no"}, timeout=10)
    assert r5.status_code == 400


def test_cancel_requires_reason(basic_token):
    token, _ = basic_token
    payload = {
        "name": f"TEST_Cancel_{uuid.uuid4().hex[:6]}",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=1)).isoformat(),
        "responsible_branch_id": BRANCH_ID_BASIC,
        "cash_config": {"mode": "own"},
        "inventory_config": {"use_branch_stock": True},
    }
    r = token.post(f"{API}/jornadas", json=payload, timeout=10)
    jid = r.json()["_id"]
    # sin motivo
    r1 = token.post(f"{API}/jornadas/{jid}/cancel", json={}, timeout=10)
    assert r1.status_code == 400
    # con motivo
    r2 = token.post(f"{API}/jornadas/{jid}/cancel",
                      json={"reason": "prueba"}, timeout=10)
    assert r2.status_code == 200


def test_reopen_forbidden_for_admin(basic_token, super_token):
    admin_token, _ = basic_token
    # Crear + ciclo completo con admin -> cerrada
    payload = {
        "name": f"TEST_Reopen_{uuid.uuid4().hex[:6]}",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=1)).isoformat(),
        "responsible_branch_id": BRANCH_ID_BASIC,
        "cash_config": {"mode": "own"},
        "inventory_config": {"use_branch_stock": True},
    }
    r = admin_token.post(f"{API}/jornadas", json=payload, timeout=10)
    jid = r.json()["_id"]
    admin_token.post(f"{API}/jornadas/{jid}/activate", timeout=10)
    admin_token.post(f"{API}/jornadas/{jid}/start-closing", timeout=10)
    admin_token.post(f"{API}/jornadas/{jid}/close", timeout=10)
    # admin no puede reabrir
    r1 = admin_token.post(f"{API}/jornadas/{jid}/reopen",
                      json={"reason": "test"}, timeout=10)
    assert r1.status_code == 403
    # superadmin sin motivo -> 400
    r2 = super_token.post(f"{API}/jornadas/{jid}/reopen",
                      json={}, timeout=10)
    assert r2.status_code == 400
    # superadmin con motivo -> 200
    r3 = super_token.post(f"{API}/jornadas/{jid}/reopen",
                      json={"reason": "prueba reopen"}, timeout=10)
    assert r3.status_code == 200, r3.text[:200]


def test_delete_planned_ok(basic_token):
    token, _ = basic_token
    payload = {
        "name": f"TEST_Delete_{uuid.uuid4().hex[:6]}",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=1)).isoformat(),
        "responsible_branch_id": BRANCH_ID_BASIC,
        "cash_config": {"mode": "own"},
        "inventory_config": {"use_branch_stock": True},
    }
    r = token.post(f"{API}/jornadas", json=payload, timeout=10)
    jid = r.json()["_id"]
    r1 = token.delete(f"{API}/jornadas/{jid}", timeout=10)
    assert r1.status_code == 200
    r2 = token.get(f"{API}/jornadas/{jid}", timeout=10)
    assert r2.status_code == 404


def test_delete_active_rejected(basic_token):
    token, _ = basic_token
    payload = {
        "name": f"TEST_DelActive_{uuid.uuid4().hex[:6]}",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=1)).isoformat(),
        "responsible_branch_id": BRANCH_ID_BASIC,
        "cash_config": {"mode": "own"},
        "inventory_config": {"use_branch_stock": True},
    }
    r = token.post(f"{API}/jornadas", json=payload, timeout=10)
    jid = r.json()["_id"]
    token.post(f"{API}/jornadas/{jid}/activate", timeout=10)
    r1 = token.delete(f"{API}/jornadas/{jid}", timeout=10)
    assert r1.status_code == 400
    # cleanup: cancel then delete
    token.post(f"{API}/jornadas/{jid}/cancel", json={"reason": "cleanup"}, timeout=10)
    token.delete(f"{API}/jornadas/{jid}", timeout=10)


# ─── MULTI-TENANT ───────────────────────────────────────────────────
def test_multi_tenant_isolation(super_token, basic_token):
    """SuperAdmin crea jornada en OTRA empresa; admin no debe verla."""
    admin_token, admin_data = basic_token
    admin_user = admin_data.get("user") or admin_data
    admin_company = admin_user.get("company_id")

    # Buscar otra empresa via superadmin
    r = super_token.get(f"{API}/companies", timeout=10)
    if r.status_code != 200:
        pytest.skip("No se pudo listar empresas")
    companies = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    others = [c for c in companies if str(c.get("_id") or c.get("id")) != str(admin_company)]
    if not others:
        pytest.skip("No hay otra empresa para probar aislamiento")
    other_company_id = str(others[0].get("_id") or others[0].get("id"))
    # Buscar sucursal de esa empresa
    rb = super_token.get(f"{API}/branches?company_id={other_company_id}", timeout=10)
    if rb.status_code != 200:
        pytest.skip("No se pudieron listar sucursales")
    br = rb.json() if isinstance(rb.json(), list) else rb.json().get("items", [])
    if not br:
        pytest.skip("Empresa alterna sin sucursales")
    other_branch_id = str(br[0].get("_id") or br[0].get("id"))

    # SuperAdmin no tiene company_id => create requiere company_id.
    # En su lugar, insertaremos directo via /companies switch no disponible.
    # Skip si no se puede crear con superadmin fuera de company.
    payload = {
        "name": f"TEST_MT_{uuid.uuid4().hex[:6]}",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=1)).isoformat(),
        "responsible_branch_id": other_branch_id,
        "cash_config": {"mode": "own"},
        "inventory_config": {"use_branch_stock": True},
    }
    r = super_token.post(f"{API}/jornadas", json=payload, timeout=10)
    if r.status_code != 201 and r.status_code != 200:
        pytest.skip(f"Superadmin no puede crear jornada sin company: {r.status_code}")
    jid = r.json().get("_id")
    if not jid:
        pytest.skip("No se creo jornada")
    # admin no debe verla
    r2 = admin_token.get(f"{API}/jornadas/{jid}", timeout=10)
    assert r2.status_code == 404
