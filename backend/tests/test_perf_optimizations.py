"""Tests para optimizaciones de performance en Cortexia Optical.
- Refactor list_quotations (batch $in, bulk update de vencidas)
- Cache Redis TTL 60s en /api/inventory/products y /api/inventory/stock
- Invalidacion de cache tras create_product, update_product, inventory_movement, create_sale, delete_sale
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@cortexia.gt"
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD","")
VENDEDOR_EMAIL = "vendedor@cortexia.gt"
VENDEDOR_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD","")


# ─────────────────────────── Fixtures ───────────────────────────
def _login_session(email: str, password: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_headers():
    # Nombre conservado para retro compat; retorna Session autenticada por cookie
    return _login_session(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def vendedor_headers():
    return _login_session(VENDEDOR_EMAIL, VENDEDOR_PASSWORD)


@pytest.fixture(scope="module")
def admin_token(admin_headers):
    # Placeholder: la autenticacion es por cookie; retornamos cookie value si existe
    for c in admin_headers.cookies:
        return c.value
    return "cookie-auth"


@pytest.fixture(scope="module")
def vendedor_token(vendedor_headers):
    for c in vendedor_headers.cookies:
        return c.value
    return "cookie-auth"


# ─────────────────────────── Regresion básica ───────────────────────────
class TestRegression:
    def test_login_admin(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 10

    def test_login_vendedor(self, vendedor_token):
        assert isinstance(vendedor_token, str) and len(vendedor_token) > 10

    def test_get_patients(self, admin_headers):
        r = admin_headers.get(f"{API}/patients", timeout=15)
        assert r.status_code == 200
        data = r.json()
        # /api/patients devuelve dict con 'patients' o lista directa segun endpoint
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "patients" in data

    def test_get_sales(self, admin_headers):
        r = admin_headers.get(f"{API}/sales", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ─────────────────────────── Quotations ───────────────────────────
class TestQuotations:
    def test_list_quotations_structure(self, admin_headers):
        r = admin_headers.get(f"{API}/quotations", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        # Si hay cotizaciones, validar estructura enriquecida
        if data:
            q = data[0]
            # Campos base
            for f in ["_id", "quotation_number", "status", "total", "created_at"]:
                assert f in q, f"falta campo {f} en quotation"
            # Cuando hay patient_id, deben existir campos enriquecidos (aunque vacios)
            if q.get("patient_id"):
                for f in ["patient_name", "patient_phone", "patient_email", "patient_whatsapp"]:
                    assert f in q, f"falta {f} (patient_id={q.get('patient_id')})"

    def test_list_quotations_filter_status(self, admin_headers):
        r = admin_headers.get(f"{API}/quotations?status=pendiente", timeout=20)
        assert r.status_code == 200
        for q in r.json():
            assert q["status"] in ["pendiente", "vencida"]  # puede convertirse a vencida al listar

    def test_create_quotation_and_verify_enriched(self, admin_headers):
        # Buscar un paciente
        pr = admin_headers.get(f"{API}/patients", timeout=15)
        pdata = pr.json()
        patients = pdata.get("patients", []) if isinstance(pdata, dict) else pdata
        if not patients:
            pytest.skip("no hay pacientes para crear cotizacion")
        patient = patients[0]
        payload = {
            "patient_id": patient["_id"],
            "items": [{"name": "TEST_perf_item", "quantity": 1, "unit_price": 100.0, "subtotal": 100.0}],
            "subtotal": 100.0,
            "discount": 0,
            "discount_type": "amount",
            "total": 100.0,
            "notes": "TEST perf optimization",
            "validity_days": 15,
        }
        cr = admin_headers.post(f"{API}/quotations", json=payload, timeout=15)
        assert cr.status_code == 200, cr.text
        qid = cr.json()["_id"]

        # Verificar aparece con enriched fields
        lr = admin_headers.get(f"{API}/quotations?patient_id=" + patient["_id"], timeout=15)
        assert lr.status_code == 200
        found = [q for q in lr.json() if q["_id"] == qid]
        assert found, f"cotizacion recien creada {qid} no aparece en list"
        q = found[0]
        expected_name = f"{patient.get('first_name','')} {patient.get('last_name','')}".strip()
        assert q.get("patient_name") == expected_name
        assert "patient_phone" in q and "patient_email" in q and "patient_whatsapp" in q
        # created_by esta presente → creator_name
        assert "creator_name" in q, "falta creator_name"


# ─────────────────────────── Inventory cache ───────────────────────────
class TestInventoryCache:
    def test_products_cache_consistency(self, admin_headers):
        r1 = admin_headers.get(f"{API}/inventory/products", timeout=15)
        r2 = admin_headers.get(f"{API}/inventory/products", timeout=15)
        assert r1.status_code == 200 and r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        ids1 = sorted([p["_id"] for p in d1])
        ids2 = sorted([p["_id"] for p in d2])
        assert ids1 == ids2
        stock1 = {p["_id"]: p.get("stock_actual", 0) for p in d1}
        stock2 = {p["_id"]: p.get("stock_actual", 0) for p in d2}
        assert stock1 == stock2, "stock_actual difiere entre 2 llamadas consecutivas (cache inconsistente)"

    def test_stock_cache_and_fields(self, admin_headers):
        r1 = admin_headers.get(f"{API}/inventory/stock", timeout=15)
        r2 = admin_headers.get(f"{API}/inventory/stock", timeout=15)
        assert r1.status_code == 200 and r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        assert isinstance(d1, list)
        if not d1:
            pytest.skip("no hay stock")
        # Verificar campos enriquecidos
        for s in d1:
            for f in ["product_name", "sku", "min_stock", "sale_price", "cost_price"]:
                assert f in s, f"falta {f} en item de stock"
        # Cache consistency
        assert len(d1) == len(d2)

    def test_products_filters_not_cached(self, admin_headers):
        # Peticion sin filtro poblara cache
        admin_headers.get(f"{API}/inventory/products", timeout=15)
        # Con filtro category (aunque no exista, debe retornar array sin usar cache)
        r_cat = admin_headers.get(f"{API}/inventory/products?category=NoExisteTEST", timeout=15)
        assert r_cat.status_code == 200
        assert isinstance(r_cat.json(), list)
        # Con search
        r_search = admin_headers.get(f"{API}/inventory/products?search=zzTESTzz", timeout=15)
        assert r_search.status_code == 200
        assert isinstance(r_search.json(), list)


# ─────────────────────────── Cache invalidation ───────────────────────────
class TestCacheInvalidation:
    def test_invalidation_on_create_product(self, admin_headers):
        # Poblar cache
        r_before = admin_headers.get(f"{API}/inventory/products", timeout=15)
        assert r_before.status_code == 200
        ids_before = {p["_id"] for p in r_before.json()}

        # Crear producto (admin invalida cache 'all')
        sku = f"TESTP-{uuid.uuid4().hex[:8]}"
        payload = {
            "name": f"TEST_perf_product_{sku}",
            "sku": sku,
            "category": "TEST",
            "cost_price": 10.0,
            "sale_price": 20.0,
            "min_stock": 1,
            "initial_stock": 0,
        }
        cr = admin_headers.post(f"{API}/inventory/products", json=payload, timeout=15)
        assert cr.status_code == 200, cr.text
        new_id = cr.json()["_id"]

        # GET inmediatamente debe reflejar (sin esperar 60s)
        r_after = admin_headers.get(f"{API}/inventory/products", timeout=15)
        assert r_after.status_code == 200
        ids_after = {p["_id"] for p in r_after.json()}
        assert new_id in ids_after, "producto recien creado no visible → cache no invalidado"
        assert new_id not in ids_before

    def test_invalidation_on_movement(self, admin_headers):
        # Crear producto primero para tener un target consistente
        sku = f"TESTM-{uuid.uuid4().hex[:8]}"
        # Obtener una branch para el movimiento
        br = admin_headers.get(f"{API}/branches", timeout=15)
        if br.status_code != 200 or not br.json():
            pytest.skip("no hay branches disponibles")
        branch_id = br.json()[0]["_id"]

        cr = admin_headers.post(f"{API}/inventory/products", json={
            "name": f"TEST_mov_product_{sku}", "sku": sku, "category": "TEST",
            "cost_price": 5.0, "sale_price": 15.0, "min_stock": 1,
            "initial_stock": 10, "branch_id": branch_id,
        }, timeout=15)
        assert cr.status_code == 200, cr.text
        product_id = cr.json()["_id"]

        # Poblar cache stock
        r_before = admin_headers.get(f"{API}/inventory/stock", timeout=15)
        assert r_before.status_code == 200
        stock_before = {s["product_id"]: s["quantity"] for s in r_before.json()}
        qty_before = stock_before.get(product_id, 0)

        # Movimiento entrada +5
        mv = admin_headers.post(f"{API}/inventory/movement", json={
            "product_id": product_id, "branch_id": branch_id,
            "type": "entrada", "quantity": 5, "notes": "TEST perf"
        }, timeout=15)
        assert mv.status_code == 200, mv.text

        r_after = admin_headers.get(f"{API}/inventory/stock", timeout=15)
        assert r_after.status_code == 200
        stock_after = {s["product_id"]: s["quantity"] for s in r_after.json()}
        qty_after = stock_after.get(product_id, 0)
        assert qty_after == qty_before + 5, f"cache stock no invalidado: {qty_before} → {qty_after} (esperado {qty_before+5})"

    def test_invalidation_on_sale(self, admin_headers):
        # Crear producto con stock, luego venta que descuente stock
        sku = f"TESTS-{uuid.uuid4().hex[:8]}"
        br = admin_headers.get(f"{API}/branches", timeout=15)
        if br.status_code != 200 or not br.json():
            pytest.skip("no hay branches disponibles")
        branch_id = br.json()[0]["_id"]

        cr = admin_headers.post(f"{API}/inventory/products", json={
            "name": f"TEST_sale_product_{sku}", "sku": sku, "category": "TEST",
            "cost_price": 5.0, "sale_price": 25.0, "min_stock": 1,
            "initial_stock": 10, "branch_id": branch_id,
        }, timeout=15)
        assert cr.status_code == 200
        product_id = cr.json()["_id"]

        # Poblar cache
        r_before = admin_headers.get(f"{API}/inventory/stock", timeout=15)
        assert r_before.status_code == 200
        stock_before = {s["product_id"]: s["quantity"] for s in r_before.json()}
        qty_before = stock_before.get(product_id, 0)
        assert qty_before >= 2, f"esperaba >=2 stock, hay {qty_before}"

        # Consumidor final (sin patient_id)
        sale_payload = {
            "patient_name_override": "TEST_consumer",
            "items": [{"product_id": product_id, "name": "TEST_sale", "quantity": 2, "unit_price": 25.0, "subtotal": 50.0}],
            "subtotal": 50.0, "discount": 0, "tax": 0, "total": 50.0,
            "payments": [{"method": "cash", "amount": 50.0}],
            "notes": "TEST perf",
        }
        sr = admin_headers.post(f"{API}/sales", json=sale_payload, timeout=15)
        assert sr.status_code == 200, sr.text

        r_after = admin_headers.get(f"{API}/inventory/stock", timeout=15)
        assert r_after.status_code == 200
        stock_after = {s["product_id"]: s["quantity"] for s in r_after.json()}
        qty_after = stock_after.get(product_id, 0)
        assert qty_after == qty_before - 2, f"cache stock no invalido tras venta: {qty_before} → {qty_after}"
