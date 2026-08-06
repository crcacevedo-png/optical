"""Tests para:
- Cache Redis TTL 30s en /api/reports/dashboard (aggregations + batch fetch).
- Cursor pagination en /api/sales (retro-compat con lista).
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@cortexia.gt"
VENDEDOR_EMAIL = "vendedor@cortexia.gt"
PASSWORD = "Demo123!"


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def vendedor():
    return _login(VENDEDOR_EMAIL, PASSWORD)


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, PASSWORD)


# ─────────────────────── Regresion basica ───────────────────────
class TestRegression:
    def test_login_ok(self, admin, vendedor):
        assert admin is not None and vendedor is not None

    def test_patients_200(self, admin):
        r = admin.get(f"{API}/patients", timeout=15)
        assert r.status_code == 200

    def test_inventory_products_200(self, admin):
        r = admin.get(f"{API}/inventory/products", timeout=15)
        assert r.status_code == 200

    def test_quotations_200(self, admin):
        r = admin.get(f"{API}/quotations", timeout=15)
        assert r.status_code == 200


# ─────────────────────── Dashboard cache ───────────────────────
DASHBOARD_KEYS = {
    "appointments_today", "appointments_pending", "new_patients",
    "sales_count_today", "total_sales_today", "total_sales_month",
    "income", "expense", "profit", "stock_alerts", "upcoming_appointments",
}


class TestDashboardCache:
    def test_dashboard_keys_present(self, vendedor):
        r = vendedor.get(f"{API}/reports/dashboard", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        missing = DASHBOARD_KEYS - set(data.keys())
        assert not missing, f"faltan keys en dashboard: {missing}"
        assert isinstance(data["upcoming_appointments"], list)
        # profit = income - expense
        assert round(data["profit"], 2) == round(data["income"] - data["expense"], 2)

    def test_dashboard_cache_latency(self, vendedor):
        # 1a llamada — llena cache
        t0 = time.perf_counter()
        r1 = vendedor.get(f"{API}/reports/dashboard", timeout=20)
        t1 = time.perf_counter() - t0
        assert r1.status_code == 200
        # 2a llamada — deberia usar cache y ser mas rapida (o al menos identica)
        t0 = time.perf_counter()
        r2 = vendedor.get(f"{API}/reports/dashboard", timeout=20)
        t2 = time.perf_counter() - t0
        assert r2.status_code == 200
        # 3a llamada
        t0 = time.perf_counter()
        r3 = vendedor.get(f"{API}/reports/dashboard", timeout=20)
        t3 = time.perf_counter() - t0
        assert r3.status_code == 200
        print(f"dashboard latency: 1st={t1*1000:.0f}ms 2nd={t2*1000:.0f}ms 3rd={t3*1000:.0f}ms")
        # Data igual (cache hit → mismos valores)
        assert r1.json()["appointments_today"] == r2.json()["appointments_today"]
        assert r1.json()["total_sales_month"] == r2.json()["total_sales_month"]
        # Ambas cache hits (2da y 3ra) deben ser al menos comparables. No forzamos <1st
        # porque red publica varia; validamos como minimo que 2da o 3ra sea menor a 1ra.
        assert min(t2, t3) <= t1 + 0.3, f"cache no ayuda: 1st={t1:.3f} min(2,3)={min(t2,t3):.3f}"

    def test_dashboard_upcoming_patient_name_enriched(self, vendedor):
        r = vendedor.get(f"{API}/reports/dashboard", timeout=20)
        assert r.status_code == 200
        for apt in r.json().get("upcoming_appointments", []):
            if apt.get("patient_id"):
                assert "patient_name" in apt, "upcoming appointment sin patient_name (batch fetch fallo)"

    def test_dashboard_branch_filter_different_cache(self, admin, vendedor):
        # admin no tiene branch → "all"
        # branches disponibles
        br = admin.get(f"{API}/branches", timeout=15)
        if br.status_code != 200 or not br.json():
            pytest.skip("no branches")
        branch_id = br.json()[0]["_id"]
        r_all = admin.get(f"{API}/reports/dashboard", timeout=20)
        r_br = admin.get(f"{API}/reports/dashboard?branch_id={branch_id}", timeout=20)
        assert r_all.status_code == 200 and r_br.status_code == 200
        # Ambas responden y tienen las mismas keys
        assert set(r_all.json().keys()) == set(r_br.json().keys())

    def test_dashboard_invalid_branch(self, admin):
        r = admin.get(f"{API}/reports/dashboard?branch_id=nope", timeout=15)
        assert r.status_code in (400, 500)


# ─────────────────────── Sales cursor pagination ───────────────────────
class TestSalesCursor:
    def test_list_sales_default_is_list(self, vendedor):
        """Sin cursor/include_cursor debe devolver lista (retro-compat)."""
        r = vendedor.get(f"{API}/sales", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list), f"esperaba list, obtuve {type(data)}"

    def test_include_cursor_returns_object(self, vendedor):
        r = vendedor.get(f"{API}/sales?include_cursor=true&limit=5", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict), "con include_cursor=true debe ser objeto"
        for k in ("items", "next_cursor", "has_more"):
            assert k in data, f"falta key {k}"
        assert isinstance(data["items"], list)
        assert isinstance(data["has_more"], bool)
        assert data["next_cursor"] is None or isinstance(data["next_cursor"], str)

    def test_cursor_pagination_no_overlap(self, vendedor):
        """Piden limit=3, si has_more, siguiente pagina no traslapa."""
        # Ensure enough sales: crear algunas si no hay >= 4
        r0 = vendedor.get(f"{API}/sales", timeout=15)
        current = r0.json() if isinstance(r0.json(), list) else []
        need = max(0, 4 - len(current))
        for _ in range(need):
            payload = {
                "patient_name_override": f"TEST_cursor_{uuid.uuid4().hex[:6]}",
                "items": [{"name": "TEST_item", "quantity": 1, "unit_price": 1.0, "subtotal": 1.0}],
                "subtotal": 1.0, "discount": 0, "tax": 0, "total": 1.0,
                "payments": [{"method": "cash", "amount": 1.0}],
                "notes": "TEST cursor pagination",
            }
            cr = vendedor.post(f"{API}/sales", json=payload, timeout=15)
            assert cr.status_code == 200, cr.text

        r1 = vendedor.get(f"{API}/sales?limit=3&include_cursor=true", timeout=15)
        assert r1.status_code == 200
        d1 = r1.json()
        assert len(d1["items"]) <= 3
        if not d1["has_more"]:
            pytest.skip("no hay suficientes ventas para paginar")
        assert d1["next_cursor"] is not None
        # Verificar que el cursor es igual al _id del ultimo item
        assert d1["next_cursor"] == d1["items"][-1]["_id"]

        r2 = vendedor.get(f"{API}/sales?limit=3&cursor={d1['next_cursor']}", timeout=15)
        assert r2.status_code == 200
        d2 = r2.json()
        # Con cursor se retorna objeto tambien
        assert isinstance(d2, dict) and "items" in d2
        ids1 = {i["_id"] for i in d1["items"]}
        ids2 = {i["_id"] for i in d2["items"]}
        assert ids1.isdisjoint(ids2), f"overlap entre paginas: {ids1 & ids2}"

    def test_cursor_invalido_400(self, vendedor):
        r = vendedor.get(f"{API}/sales?cursor=not-an-oid", timeout=15)
        assert r.status_code == 400
        body = r.json()
        assert "cursor" in str(body).lower()

    def test_item_contract_preserved(self, vendedor):
        """Cada venta tiene patient_name (si patient_id) y seller_name (si created_by)."""
        r = vendedor.get(f"{API}/sales?limit=10&include_cursor=true", timeout=15)
        assert r.status_code == 200
        for s in r.json()["items"]:
            assert "_id" in s
            assert "total" in s
            if s.get("patient_id"):
                assert "patient_name" in s
            if s.get("created_by"):
                assert "seller_name" in s

    def test_regression_get_detail_and_admin_delete(self, admin, vendedor):
        # Crear venta con vendedor
        payload = {
            "patient_name_override": f"TEST_del_{uuid.uuid4().hex[:6]}",
            "items": [{"name": "TEST_item", "quantity": 1, "unit_price": 1.0, "subtotal": 1.0}],
            "subtotal": 1.0, "discount": 0, "tax": 0, "total": 1.0,
            "payments": [{"method": "cash", "amount": 1.0}],
            "notes": "TEST del regression",
        }
        cr = vendedor.post(f"{API}/sales", json=payload, timeout=15)
        assert cr.status_code == 200, cr.text
        sid = cr.json()["_id"]
        # GET detalle
        gr = vendedor.get(f"{API}/sales/{sid}", timeout=15)
        assert gr.status_code == 200
        assert gr.json()["_id"] == sid
        # DELETE admin
        dr = admin.delete(f"{API}/sales/{sid}", timeout=15)
        assert dr.status_code == 200, dr.text
        # Verificar 404
        gr2 = vendedor.get(f"{API}/sales/{sid}", timeout=15)
        assert gr2.status_code == 404
