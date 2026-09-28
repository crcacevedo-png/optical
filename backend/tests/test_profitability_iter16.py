"""Iter 16 — Rentabilidad por producto (Utilidad -> Flujo de caja + /profitability).

Cubre:
  - GET /api/finance/profitability como admin (200 con la forma esperada).
  - GET /api/finance/profitability como superadmin (403).
  - E2E: crear venta con producto con cost_price, verificar revenue/cogs/margin y limpiar.
  - Regresion: income-statement sigue exponiendo net_profit.
"""
import os
from datetime import datetime, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")
from _credentials import ADMIN_EMAIL, ADMIN_PASSWORD, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD  # noqa: E402
TEST_PRODUCT_ID = "69cac743cf7c7911e128250a"  # Ray-Ban (cost 450, sale 850)


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    csrf = s.cookies.get("csrf_token")
    if csrf:
        s.headers.update({"X-CSRF-Token": csrf})
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def superadmin():
    return _login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)


# ── /profitability shape & auth ─────────────────────────────────────────────
class TestProfitabilityEndpoint:
    def test_admin_ok_shape(self, admin):
        r = admin.get(f"{BASE_URL}/api/finance/profitability", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("period", "basis", "revenue_with_cost", "cogs", "gross_margin",
                  "gross_margin_pct", "revenue_without_cost", "items_without_cost", "by_product"):
            assert k in data, f"missing key {k}"
        assert data["basis"] == "devengado"
        assert isinstance(data["by_product"], list)
        assert "from" in data["period"] and "to" in data["period"]

    def test_superadmin_forbidden(self, superadmin):
        r = superadmin.get(f"{BASE_URL}/api/finance/profitability", timeout=30)
        assert r.status_code == 403, f"esperaba 403 y llego {r.status_code}"


# ── E2E: crear venta y validar margen ───────────────────────────────────────
class TestProfitabilityE2E:
    def test_new_sale_reflected_in_profitability(self, admin):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        payload = {
            "patient_name_override": "TEST_QA_Prof16",
            "items": [{
                "product_id": TEST_PRODUCT_ID,
                "name": "Ray-Ban QA",
                "price": 850,
                "quantity": 2,
                "total": 1700,
            }],
            "subtotal": 1700, "discount": 0, "tax": 0, "total": 1700,
            "payments": [{"method": "cash", "amount": 1700}],
            "notes": "TEST_QA iter16 - borrar despues",
        }
        r = admin.post(f"{BASE_URL}/api/sales", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        sale = r.json()
        sale_id = sale.get("id") or sale.get("_id") or sale.get("sale_id")
        assert sale_id, f"sin id en respuesta: {sale}"

        try:
            # unit_cost snapshoteado — validado via GET si el POST no lo devuelve
            items = sale.get("items") or []
            if not items:
                g = admin.get(f"{BASE_URL}/api/sales/{sale_id}", timeout=30)
                if g.status_code == 200:
                    items = g.json().get("items") or []
            if items:
                assert items[0].get("unit_cost") == 450, f"unit_cost esperado 450, got {items[0].get('unit_cost')}"
                assert items[0].get("cost_source") == "product"

            r2 = admin.get(f"{BASE_URL}/api/finance/profitability",
                           params={"date_from": today, "date_to": today}, timeout=30)
            assert r2.status_code == 200, r2.text
            data = r2.json()
            row = next((b for b in data["by_product"] if b.get("product_id") == TEST_PRODUCT_ID), None)
            assert row is not None, f"producto no aparece: {data['by_product']}"
            assert row["has_cost"] is True
            assert row["revenue"] >= 1700
            assert row["cogs"] >= 900
            assert row["margin"] >= 800
            # margen aproximado: 800/1700 ≈ 47.06 -> 47.1
            assert row["margin_pct"] is not None and 45 <= row["margin_pct"] <= 50
        finally:
            # CLEANUP obligatorio
            d = admin.delete(f"{BASE_URL}/api/sales/{sale_id}", timeout=30)
            assert d.status_code in (200, 204), f"cleanup failed: {d.status_code} {d.text}"


# ── Regresion: income-statement sigue devolviendo net_profit ────────────────
class TestIncomeStatementRegression:
    def test_income_statement_has_net_profit(self, admin):
        r = admin.get(f"{BASE_URL}/api/finance/income-statement", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "net_profit" in data, f"net_profit ausente: keys={list(data.keys())}"
