"""Iter10: Nuevas features sobre Caja
- POST /api/finance desde Caja (mismo endpoint; se prueba flow: abrir->egreso cash/transfer/credito->preview->close)
- GET /api/cash-register/{register_id}/pdf (arqueo por cierre): admin/vendedor 200 %PDF con "Arqueo de Caja", "Egresos del turno" y descripciones
- superadmin 403, id invalido 400, id de otra empresa 404
- Ordenamiento de rutas: /{register_id}/pdf NO colisiona con /{register_id} (JSON)
- Range report PDF: incluye "Detalle de egresos del periodo" y descripciones
- Regresion: GET /api/finance sigue 200 con egresos a credito
"""
import io
import os
import pytest
import requests
from datetime import datetime, timezone, timedelta

from pypdf import PdfReader

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

from _credentials import ADMIN_EMAIL, ADMIN_PASSWORD, VENDEDOR_EMAIL, VENDEDOR_PASSWORD, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD  # noqa: E402


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
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
                json={"counted_cash": 0, "closing_notes": "cleanup iter10"},
                timeout=30,
            )
    except Exception:
        pass


def _pdf_text(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        return f""


@pytest.fixture(scope="module")
def admin():
    s, u = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    yield s, u


@pytest.fixture(scope="module")
def vendedor():
    s, u = _login(VENDEDOR_EMAIL, VENDEDOR_PASSWORD)
    _ensure_closed(s)
    yield s, u
    _ensure_closed(s)


@pytest.fixture(scope="module")
def superadmin():
    s, u = _login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    yield s, u


@pytest.fixture(scope="module")
def qa_supplier(admin):
    s, _ = admin
    r = s.post(f"{BASE_URL}/api/suppliers", json={"name": "QA10 Proveedor", "phone": "5000-0010"}, timeout=30)
    assert r.status_code in (200, 201), f"supplier: {r.status_code} {r.text[:200]}"
    data = r.json()
    sid = data.get("_id") or data.get("id")
    yield sid
    try:
        s.delete(f"{BASE_URL}/api/suppliers/{sid}", timeout=30)
    except Exception:
        pass


_state = {
    "register_id": None,
    "egresos_ids": [],
    "descs": ["QA10 egreso cash abc", "QA10 egreso transfer xyz"],
}


class TestFullFlow:
    def test_01_open_100(self, vendedor):
        s, _ = vendedor
        r = s.post(f"{BASE_URL}/api/cash-register/open", json={"opening_amount": 100, "opening_notes": "QA10"}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        _state["register_id"] = r.json()["register"]["_id"]

    def test_02_egreso_cash_40(self, vendedor, qa_supplier):
        s, _ = vendedor
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        r = s.post(f"{BASE_URL}/api/finance", json={
            "type": "egreso", "category": "other_expense", "amount": 40,
            "description": _state["descs"][0], "date": today, "payment_method": "cash",
        }, timeout=30)
        assert r.status_code == 200, r.text[:200]
        _state["egresos_ids"].append(r.json()["_id"])

    def test_03_egreso_transfer_20(self, vendedor):
        s, _ = vendedor
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        r = s.post(f"{BASE_URL}/api/finance", json={
            "type": "egreso", "category": "other_expense", "amount": 20,
            "description": _state["descs"][1], "date": today, "payment_method": "transfer",
        }, timeout=30)
        assert r.status_code == 200, r.text[:200]
        _state["egresos_ids"].append(r.json()["_id"])

    def test_04_preview(self, vendedor):
        s, _ = vendedor
        r = s.get(f"{BASE_URL}/api/cash-register/current/preview", timeout=30)
        assert r.status_code == 200
        b = r.json()
        # 100 + 0 - 40 = 60 expected cash
        assert abs(b["expected_cash"] - 60.0) < 0.01, b["expected_cash"]
        assert abs(b["egresos_cash"] - 40.0) < 0.01
        assert abs(b["egresos_total"] - 60.0) < 0.01
        assert b["egresos_count"] == 2

    def test_05_close_counted_60(self, vendedor):
        s, _ = vendedor
        r = s.post(f"{BASE_URL}/api/cash-register/close", json={"counted_cash": 60, "closing_notes": "QA10"}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        reg = r.json()["register"]
        assert abs(reg["expected_cash"] - 60.0) < 0.01
        assert abs(reg["cash_difference"]) < 0.01
        assert reg.get("egresos_count") == 2


class TestSingleCierrePDF:
    def test_06_pdf_admin_200(self, admin):
        s, _ = admin
        rid = _state["register_id"]
        r = s.get(f"{BASE_URL}/api/cash-register/{rid}/pdf", timeout=60)
        assert r.status_code == 200, r.text[:200]
        assert "pdf" in r.headers.get("content-type", "").lower()
        assert r.content[:4] == b"%PDF"
        text = _pdf_text(r.content)
        assert "Arqueo de Caja" in text, text[:500]
        assert "Egresos del turno" in text, text[:500]
        assert _state["descs"][0][:20] in text, text[:500]
        assert _state["descs"][1][:20] in text, text[:500]

    def test_07_pdf_vendedor_200(self, vendedor):
        s, _ = vendedor
        rid = _state["register_id"]
        r = s.get(f"{BASE_URL}/api/cash-register/{rid}/pdf", timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_08_pdf_superadmin_403(self, superadmin):
        s, _ = superadmin
        rid = _state["register_id"]
        r = s.get(f"{BASE_URL}/api/cash-register/{rid}/pdf", timeout=30)
        assert r.status_code == 403, f"expected 403 got {r.status_code}"

    def test_09_pdf_invalid_id_400(self, admin):
        s, _ = admin
        r = s.get(f"{BASE_URL}/api/cash-register/not-an-oid/pdf", timeout=30)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:200]}"

    def test_10_pdf_other_company_404(self, admin):
        # ObjectId con formato valido pero inexistente en la empresa
        s, _ = admin
        r = s.get(f"{BASE_URL}/api/cash-register/507f1f77bcf86cd799439011/pdf", timeout=30)
        assert r.status_code == 404, f"expected 404 got {r.status_code}: {r.text[:200]}"

    def test_11_route_no_collision_json_endpoint(self, admin):
        """GET /{id} sigue devolviendo JSON, no PDF."""
        s, _ = admin
        rid = _state["register_id"]
        r = s.get(f"{BASE_URL}/api/cash-register/{rid}", timeout=30)
        assert r.status_code == 200
        assert "json" in r.headers.get("content-type", "").lower()
        data = r.json()
        assert data.get("_id") == rid
        assert data.get("status") == "closed"


class TestRangeReportPDF:
    def test_12_range_pdf_contains_egresos_section(self, vendedor):
        s, _ = vendedor
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
        r = s.get(
            f"{BASE_URL}/api/cash-register/report/pdf",
            params={"date_from": month_start, "date_to": today},
            timeout=60,
        )
        assert r.status_code == 200, r.text[:200]
        assert r.content[:4] == b"%PDF"
        text = _pdf_text(r.content)
        assert "Detalle de egresos del periodo" in text, text[:600]
        # al menos una descripcion aparece
        assert _state["descs"][0][:20] in text or _state["descs"][1][:20] in text


class TestRegresion:
    def test_13_get_finance_no_500(self, vendedor):
        s, _ = vendedor
        r = s.get(f"{BASE_URL}/api/finance", timeout=30)
        assert r.status_code == 200, r.text[:200]


class TestZZCleanup:
    def test_zz_cleanup(self):
        try:
            import asyncio
            from motor.motor_asyncio import AsyncIOMotorClient
            from bson import ObjectId as _OID
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "opticas_saas")

            async def _clean():
                client = AsyncIOMotorClient(mongo_url)
                db = client[db_name]
                eids = [_OID(x) for x in _state["egresos_ids"]]
                if eids:
                    await db.finance_entries.delete_many({"_id": {"$in": eids}})
                if _state.get("register_id"):
                    await db.cash_registers.delete_one({"_id": _OID(_state["register_id"])})
                client.close()

            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("closed loop")
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(_clean())
        except Exception as ex:
            print(f"cleanup err: {ex}")
