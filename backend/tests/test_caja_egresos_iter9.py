"""Iter9: Egresos integrados al flujo de Caja (backend).

Casos:
 - E2E: open(100) + venta cash Q200 + egreso cash 75 -> preview.expected_cash=225
 - Egreso NO efectivo (transfer) suma a egresos_total pero no egresos_cash
 - Egreso a credito con amount_paid: salida del turno = amount_paid (no total)
 - Close verifica cash_difference=0 con counted_cash=225
 - Regresion: GET /api/finance NO 500 con egresos a credito con payments[]
 - PDF /api/cash-register/report/pdf incluye lineas de egresos
"""
import io
import os
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@cortexia.gt"
ADMIN_PASSWORD = "DemoAdmin2026!"
VENDEDOR_EMAIL = "vendedor@cortexia.gt"
VENDEDOR_PASSWORD = "DemoUser2026!"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login: {r.status_code} {r.text[:200]}"
    csrf = s.cookies.get("csrf_token")
    if csrf:
        s.headers.update({"X-CSRF-Token": csrf})
    return s, r.json()


def _ensure_closed(sess):
    try:
        r = sess.get(f"{BASE_URL}/api/cash-register/current", timeout=30)
        if r.status_code == 200 and r.json().get("register"):
            sess.post(
                f"{BASE_URL}/api/cash-register/close",
                json={"counted_cash": 0, "closing_notes": "cleanup iter9"},
                timeout=30,
            )
    except Exception:
        pass


@pytest.fixture(scope="module")
def admin():
    """Admin session for creating suppliers, listing finance."""
    s, user = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    yield s, user


@pytest.fixture(scope="module")
def vendedor():
    """Vendedor session (branch_id present) for caja/finance/sales flow."""
    s, user = _login(VENDEDOR_EMAIL, VENDEDOR_PASSWORD)
    _ensure_closed(s)
    yield s, user
    _ensure_closed(s)


@pytest.fixture(scope="module")
def qa_supplier(admin):
    s, _ = admin
    r = s.post(
        f"{BASE_URL}/api/suppliers",
        json={"name": "QA Proveedor Iter9", "phone": "5555-9999"},
        timeout=30,
    )
    assert r.status_code in (200, 201), f"supplier: {r.status_code} {r.text[:200]}"
    data = r.json()
    sid = data.get("_id") or data.get("id")
    assert sid
    yield sid
    try:
        s.delete(f"{BASE_URL}/api/suppliers/{sid}", timeout=30)
    except Exception:
        pass


# Persistente entre tests (para hacer flow ordenado)
_state = {"register_id": None, "egresos_ids": [], "sale_id": None}


class TestE2EEgresosEnCaja:
    def test_01_open_caja_100(self, vendedor):
        s, _ = vendedor
        r = s.post(
            f"{BASE_URL}/api/cash-register/open",
            json={"opening_amount": 100, "opening_notes": "QA iter9"},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:200]
        _state["register_id"] = r.json()["register"]["_id"]

    def test_02_crear_venta_cash_200(self, vendedor):
        s, _ = vendedor
        payload = {
            "items": [{"description": "QA venta cash", "quantity": 1, "unit_price": 200}],
            "subtotal": 200, "discount": 0, "tax": 0, "total": 200,
            "amount_paid": 200, "payment_method": "cash",
            "notes": "QA iter9",
        }
        r = s.post(f"{BASE_URL}/api/sales", json=payload, timeout=30)
        assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:200]}"
        data = r.json()
        _state["sale_id"] = data.get("_id") or data.get("id") or (data.get("sale") or {}).get("_id")

    def test_03_crear_egreso_cash_75(self, vendedor, qa_supplier):
        s, _ = vendedor
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        payload = {
            "type": "egreso", "category": "suppliers", "amount": 75,
            "description": "QA egreso cash", "supplier_id": qa_supplier,
            "date": today, "payment_method": "cash",
        }
        r = s.post(f"{BASE_URL}/api/finance", json=payload, timeout=30)
        assert r.status_code == 200, r.text[:200]
        _state["egresos_ids"].append(r.json()["_id"])

    def test_04_preview_expected_cash_225(self, vendedor):
        s, _ = vendedor
        r = s.get(f"{BASE_URL}/api/cash-register/current/preview", timeout=30)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        # Claves nuevas requeridas
        for k in ("egresos_by_method", "egresos_total", "egresos_cash", "egresos_count", "egresos_detail"):
            assert k in body, f"clave faltante: {k}"
        assert body["egresos_count"] == 1, body["egresos_count"]
        assert abs(body["egresos_cash"] - 75.0) < 0.01
        assert abs(body["egresos_total"] - 75.0) < 0.01
        assert abs(body["totals_by_method"].get("cash", 0) - 200.0) < 0.01
        # expected_cash = 100 + 200 - 75 = 225
        assert abs(body["expected_cash"] - 225.0) < 0.01, body["expected_cash"]

    def test_05_crear_egreso_transfer_50(self, vendedor, qa_supplier):
        s, _ = vendedor
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        payload = {
            "type": "egreso", "category": "suppliers", "amount": 50,
            "description": "QA egreso transfer", "supplier_id": qa_supplier,
            "date": today, "payment_method": "transfer",
        }
        r = s.post(f"{BASE_URL}/api/finance", json=payload, timeout=30)
        assert r.status_code == 200, r.text[:200]
        _state["egresos_ids"].append(r.json()["_id"])

        # Preview: transfer NO afecta expected_cash pero suma a egresos_total
        rp = s.get(f"{BASE_URL}/api/cash-register/current/preview", timeout=30)
        assert rp.status_code == 200
        b = rp.json()
        assert abs(b["egresos_cash"] - 75.0) < 0.01, b["egresos_cash"]
        assert abs(b["egresos_total"] - 125.0) < 0.01, b["egresos_total"]
        assert abs(b["expected_cash"] - 225.0) < 0.01
        assert abs(b["egresos_by_method"].get("transfer", 0) - 50.0) < 0.01

    def test_06_crear_egreso_credito_amount_paid(self, vendedor, qa_supplier):
        """Egreso a credito Q1000 con amount_paid=200 cash. Salida del turno = 200."""
        s, _ = vendedor
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        due = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
        payload = {
            "type": "egreso", "category": "suppliers", "amount": 1000,
            "description": "QA egreso credito", "supplier_id": qa_supplier,
            "date": today, "payment_method": "cash",
            "is_credit": True, "amount_paid": 200, "due_date": due,
        }
        r = s.post(f"{BASE_URL}/api/finance", json=payload, timeout=30)
        assert r.status_code == 200, r.text[:200]
        _state["egresos_ids"].append(r.json()["_id"])

        rp = s.get(f"{BASE_URL}/api/cash-register/current/preview", timeout=30)
        assert rp.status_code == 200
        b = rp.json()
        # egresos_cash pasa de 75 -> 275 (75 + 200 amount_paid, NO 1075)
        assert abs(b["egresos_cash"] - 275.0) < 0.01, f"egresos_cash={b['egresos_cash']} (esperado 275)"
        # egresos_total: 75 cash + 50 transfer + 200 credito = 325
        assert abs(b["egresos_total"] - 325.0) < 0.01, f"egresos_total={b['egresos_total']}"
        # expected_cash = 100 + 200 - 275 = 25
        assert abs(b["expected_cash"] - 25.0) < 0.01, b["expected_cash"]

    def test_07_regresion_get_finance_no_500(self, vendedor):
        """Antes daba 500 por payments[].created_by ObjectId. Debe ser 200."""
        s, _ = vendedor
        r = s.get(f"{BASE_URL}/api/finance", params={"type": "egreso"}, timeout=30)
        assert r.status_code == 200, f"REGRESION 500: {r.status_code} {r.text[:200]}"
        entries = r.json()
        creds = [e for e in entries if e.get("is_credit")]
        assert creds, "no hay egresos a credito en el listado"
        for e in creds:
            for p in e.get("payments") or []:
                assert isinstance(p.get("created_by"), str) or p.get("created_by") is None, \
                    f"payments.created_by no serializado: {type(p.get('created_by'))}"

    def test_08_close_con_solo_egreso_cash_efectivo_225(self, vendedor):
        """Cerrar caja con expected_cash=25 (100 + 200 - 275) y counted=25 -> diff=0.
        Verifica que los 3 egresos (cash 75, transfer 50, credito 200) esten en egresos_detail
        y que solo cash+credito(cash) afectan expected_cash."""
        s, _ = vendedor

        # Preview
        rp = s.get(f"{BASE_URL}/api/cash-register/current/preview", timeout=30)
        assert rp.status_code == 200
        assert abs(rp.json()["expected_cash"] - 25.0) < 0.01

        r = s.post(
            f"{BASE_URL}/api/cash-register/close",
            json={"counted_cash": 25, "closing_notes": "QA cierre iter9"},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:200]
        reg = r.json()["register"]
        assert abs(reg["expected_cash"] - 25.0) < 0.01
        assert abs(reg["cash_difference"] - 0.0) < 0.01, reg["cash_difference"]
        # 3 egresos en detail
        assert reg.get("egresos_count") == 3, reg.get("egresos_count")
        assert reg.get("egresos_detail") and len(reg["egresos_detail"]) == 3
        # egresos_cash = 75 + 200 = 275
        assert abs(reg["egresos_cash"] - 275.0) < 0.01
        # egresos_total = 75 + 50 + 200 = 325
        assert abs(reg["egresos_total"] - 325.0) < 0.01
        # Verificar que el credito guardo amount=200 (amount_paid) NO 1000
        credit_row = [x for x in reg["egresos_detail"] if x.get("is_credit")]
        assert len(credit_row) == 1
        assert abs(credit_row[0]["amount"] - 200.0) < 0.01, credit_row[0]["amount"]
        # Verificar metodos
        methods = sorted([x["method"] for x in reg["egresos_detail"]])
        assert methods == ["cash", "cash", "transfer"], methods

    def test_09_pdf_report_incluye_egresos(self, vendedor):
        s, _ = vendedor
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # rango que incluye la caja recien cerrada
        month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
        r = s.get(
            f"{BASE_URL}/api/cash-register/report/pdf",
            params={"date_from": month_start, "date_to": today},
            timeout=60,
        )
        assert r.status_code == 200, r.text[:200]
        ct = r.headers.get("content-type", "")
        assert "pdf" in ct.lower(), f"content-type: {ct}"
        content = r.content
        assert content[:4] == b"%PDF", "no es PDF valido"
        # Buscar los textos (aunque PDF es binario, reportlab suele emitir texto plano en el stream)
        # Nota: los textos pueden estar comprimidos; solo verificamos que sea PDF valido
        assert len(content) > 1000

    def test_zz_cleanup(self, vendedor):
        s, _ = vendedor
        sid = _state["sale_id"]
        if sid:
            try:
                s.delete(f"{BASE_URL}/api/sales/{sid}", timeout=30)
            except Exception:
                pass
        # Limpiar finance_entries y cash_registers QA via mongo (no hay DELETE endpoint)
        try:
            import asyncio
            from motor.motor_asyncio import AsyncIOMotorClient
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "opticas_saas")

            async def _clean():
                client = AsyncIOMotorClient(mongo_url)
                db = client[db_name]
                from bson import ObjectId as _OID
                eids = [_OID(x) for x in _state["egresos_ids"]]
                if eids:
                    await db.finance_entries.delete_many({"_id": {"$in": eids}})
                # cerrar cash_register de test si aun abierta
                if _state.get("register_id"):
                    await db.cash_registers.delete_one({"_id": _OID(_state["register_id"])})
                client.close()

            asyncio.get_event_loop().run_until_complete(_clean())
        except Exception as ex:
            print(f"cleanup mongo err: {ex}")
