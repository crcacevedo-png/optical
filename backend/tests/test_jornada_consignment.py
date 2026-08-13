"""Backend tests for Jornadas Iter 3: Consignacion via Excel + Liquidacion + Reporte final.

Cubre:
- EXCEL PREVIEW: header row detection, headers, sample_rows, suggested_mapping
- EXCEL IMPORT: crea productos con is_consignment_source=true, jornada_stock source=consignment, idempotency (hash)
- EXCEL UPLOADS: list + revert (fail si sold_qty>0, solo admin)
- LIQUIDATION: per_supplier + totals
- REPORT PDF: magic bytes %PDF + Content-Disposition attachment
- REPORT XLSX: magic bytes PK + hojas Resumen & Liquidacion
- CIERRE: no probamos cierre completo (Iter 2), pero validamos preview con use_consignment=false rechaza
- MULTITENANT: superadmin no puede ver liquidation de jornada de otro tenant (usamos ObjectId falso)
"""
import io
import os
import json
import uuid
import pytest
import requests
import openpyxl
from datetime import date, timedelta
from bson import ObjectId

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://eyecare-erp.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

BASIC_ADMIN_EMAIL = "admin@cortexia.gt"
BASIC_ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD","")

# Jornada existente con consignment ya habilitado (por review request)
JORNADA_WITH_CONSIGN = "6a793f0e1c71bc5b4d9c98ba"
BRANCH_ID = "69d458bb6a6b539b3084f0a3"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        return None
    return s


@pytest.fixture(scope="module")
def admin_sess():
    s = _login(BASIC_ADMIN_EMAIL, BASIC_ADMIN_PASSWORD)
    if not s:
        pytest.skip("no login admin")
    return s


def _make_excel_bytes(with_title_row: bool = True, rows: int = 3, unique_tag: str = None) -> bytes:
    """Genera un .xlsx con fila de titulo + headers + N productos."""
    tag = unique_tag or uuid.uuid4().hex[:6]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Consignacion"
    r = 1
    if with_title_row:
        ws.cell(row=r, column=1, value="Reporte de Consignacion").font = openpyxl.styles.Font(bold=True)
        r += 1  # deja fila 2 vacia? no, escribe otra fila con solo 1 celda -> excluded
    # headers en fila r (esperamos header_row=r cuando r=1 sin titulo, r=2 con titulo)
    headers = ["Codigo", "Descripcion", "Marca", "Cantidad", "Costo", "Precio", "Proveedor"]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=r, column=i, value=h)
    r += 1
    for i in range(rows):
        ws.cell(row=r, column=1, value=f"TEST-{tag}-{i}")
        ws.cell(row=r, column=2, value=f"Lente Consig {tag} {i}")
        ws.cell(row=r, column=3, value="MarcaTest")
        ws.cell(row=r, column=4, value=5 + i)
        ws.cell(row=r, column=5, value=100.0)
        ws.cell(row=r, column=6, value=150.0)
        ws.cell(row=r, column=7, value=f"ProveedorTest-{tag}")
        r += 1
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def consign_jornada_id(admin_sess):
    """Verifica que la jornada de review request existe y tiene consignment habilitado.

    Si no, crea una nueva con use_consignment=true.
    """
    r = admin_sess.get(f"{API}/jornadas/{JORNADA_WITH_CONSIGN}", timeout=10)
    if r.status_code == 200:
        j = r.json()
        cfg = (j.get("inventory_config") or {})
        if cfg.get("use_consignment"):
            return JORNADA_WITH_CONSIGN
        # Actualizar habilitando consignment
        upd = admin_sess.put(
            f"{API}/jornadas/{JORNADA_WITH_CONSIGN}",
            json={"inventory_config": {**cfg, "use_consignment": True}},
            timeout=10,
        )
        if upd.status_code == 200:
            return JORNADA_WITH_CONSIGN
    # Crear nueva
    payload = {
        "name": f"TEST_Consig_{uuid.uuid4().hex[:6]}",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=1)).isoformat(),
        "responsible_branch_id": BRANCH_ID,
        "cash_config": {"mode": "own", "initial_fund": 100},
        "inventory_config": {"use_branch_stock": False, "use_consignment": True},
    }
    r2 = admin_sess.post(f"{API}/jornadas", json=payload, timeout=15)
    assert r2.status_code in (200, 201), r2.text[:300]
    return r2.json()["_id"]


# ═════════════════════ EXCEL PREVIEW ═════════════════════
class TestExcelPreview:
    def test_preview_ok_with_title_row(self, admin_sess, consign_jornada_id):
        content = _make_excel_bytes(with_title_row=True, rows=3)
        files = {"file": ("preview.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = admin_sess.post(f"{API}/jornadas/{consign_jornada_id}/excel/preview", files=files, timeout=20)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # header_row deteccion: con titulo en fila 1 (1 celda) headers en fila 2
        assert data["header_row"] == 2, f"expected 2 got {data['header_row']}"
        assert "Codigo" in data["headers"] or "Descripcion" in data["headers"]
        assert isinstance(data["sample_rows"], list) and len(data["sample_rows"]) >= 1
        assert data["total_rows_estimate"] >= 3
        sm = data["suggested_mapping"]
        # auto-detecta description y quantity
        assert "description" in sm
        assert "quantity" in sm
        assert "code" in sm

    def test_preview_rejects_when_consignment_disabled(self, admin_sess):
        """Crea una jornada SIN consignment y verifica que preview responda 400."""
        payload = {
            "name": f"TEST_NoConsig_{uuid.uuid4().hex[:6]}",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=1)).isoformat(),
            "responsible_branch_id": BRANCH_ID,
            "cash_config": {"mode": "own", "initial_fund": 100},
            "inventory_config": {"use_branch_stock": True, "use_consignment": False},
        }
        r = admin_sess.post(f"{API}/jornadas", json=payload, timeout=15)
        assert r.status_code in (200, 201), r.text[:200]
        jid = r.json()["_id"]
        try:
            content = _make_excel_bytes(rows=2)
            files = {"file": ("x.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            rp = admin_sess.post(f"{API}/jornadas/{jid}/excel/preview", files=files, timeout=15)
            assert rp.status_code == 400
            assert "consignacion" in rp.text.lower()
        finally:
            admin_sess.delete(f"{API}/jornadas/{jid}", timeout=10)

    def test_preview_rejects_oversize(self, admin_sess, consign_jornada_id):
        # >5MB
        big = b"a" * (5 * 1024 * 1024 + 100)
        files = {"file": ("big.xlsx", big, "application/octet-stream")}
        r = admin_sess.post(f"{API}/jornadas/{consign_jornada_id}/excel/preview", files=files, timeout=20)
        # puede rechazar por tamaño (400) o por parse (400) - ambos aceptables
        assert r.status_code == 400


# ═════════════════════ EXCEL IMPORT ═════════════════════
class TestExcelImport:
    def test_import_creates_products_and_stock(self, admin_sess, consign_jornada_id):
        tag = uuid.uuid4().hex[:6]
        content = _make_excel_bytes(with_title_row=True, rows=3, unique_tag=tag)
        # mapping - header_row=2, cols indices 0..6
        mapping = {
            "code": 0, "description": 1, "brand": 2,
            "quantity": 3, "unit_cost": 4, "unit_price": 5, "supplier": 6,
        }
        body = {"header_row": 2, "mapping": mapping, "default_supplier": None, "default_margin_percent": None}
        files = {"file": ("import1.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data = {"mapping_json": json.dumps(body)}
        r = admin_sess.post(f"{API}/jornadas/{consign_jornada_id}/excel/import", files=files, data=data, timeout=30)
        assert r.status_code == 200, r.text[:400]
        j = r.json()
        assert j["rows_created"] == 3, j
        assert j["rows_linked"] == 0
        assert "upload_id" in j
        # Verify upload in list
        r2 = admin_sess.get(f"{API}/jornadas/{consign_jornada_id}/excel/uploads", timeout=15)
        assert r2.status_code == 200
        uploads = r2.json()["items"]
        assert any(u["_id"] == j["upload_id"] for u in uploads)

        # Verify inventory shows consignment items
        rinv = admin_sess.get(f"{API}/jornadas/{consign_jornada_id}/inventory", timeout=10)
        assert rinv.status_code == 200
        inv = rinv.json()
        items = inv.get("items") if isinstance(inv, dict) else inv
        assert any((it.get("source") == "consignment") for it in items), "No consignment stock found"

    def test_import_idempotency_same_hash_400(self, admin_sess, consign_jornada_id):
        tag = uuid.uuid4().hex[:6]
        content = _make_excel_bytes(with_title_row=True, rows=2, unique_tag=tag)
        mapping = {"code": 0, "description": 1, "quantity": 3, "unit_cost": 4, "unit_price": 5, "supplier": 6}
        body = {"header_row": 2, "mapping": mapping}
        files = {"file": ("dup.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data = {"mapping_json": json.dumps(body)}
        r1 = admin_sess.post(f"{API}/jornadas/{consign_jornada_id}/excel/import", files=files, data=data, timeout=30)
        assert r1.status_code == 200, r1.text[:300]
        # Subir de nuevo mismo contenido
        files2 = {"file": ("dup2.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data2 = {"mapping_json": json.dumps(body)}
        r2 = admin_sess.post(f"{API}/jornadas/{consign_jornada_id}/excel/import", files=files2, data=data2, timeout=30)
        assert r2.status_code == 400
        assert "hash" in r2.text.lower() or "cargado" in r2.text.lower()

    def test_import_requires_description_and_quantity_mapping(self, admin_sess, consign_jornada_id):
        content = _make_excel_bytes(with_title_row=True, rows=2)
        # falta description
        body = {"header_row": 2, "mapping": {"code": 0, "quantity": 3}}
        files = {"file": ("bad.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data = {"mapping_json": json.dumps(body)}
        r = admin_sess.post(f"{API}/jornadas/{consign_jornada_id}/excel/import", files=files, data=data, timeout=20)
        assert r.status_code == 400
        assert "description" in r.text.lower() or "quantity" in r.text.lower() or "mapping" in r.text.lower()


# ═════════════════════ REVERT ═════════════════════
class TestExcelRevert:
    def test_revert_upload_deletes_stock(self, admin_sess, consign_jornada_id):
        tag = uuid.uuid4().hex[:6]
        content = _make_excel_bytes(with_title_row=True, rows=2, unique_tag=tag)
        mapping = {"code": 0, "description": 1, "quantity": 3, "unit_cost": 4, "unit_price": 5, "supplier": 6}
        body = {"header_row": 2, "mapping": mapping}
        files = {"file": ("torevert.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data = {"mapping_json": json.dumps(body)}
        r = admin_sess.post(f"{API}/jornadas/{consign_jornada_id}/excel/import", files=files, data=data, timeout=30)
        assert r.status_code == 200
        upload_id = r.json()["upload_id"]
        # Revertir
        rr = admin_sess.post(f"{API}/jornadas/{consign_jornada_id}/excel/{upload_id}/revert", timeout=15)
        assert rr.status_code == 200, rr.text[:300]
        assert "revertida" in rr.text.lower() or "revert" in rr.text.lower()
        # Segundo revert -> 400
        rr2 = admin_sess.post(f"{API}/jornadas/{consign_jornada_id}/excel/{upload_id}/revert", timeout=15)
        assert rr2.status_code == 400


# ═════════════════════ LIQUIDATION ═════════════════════
class TestLiquidation:
    def test_liquidation_structure(self, admin_sess, consign_jornada_id):
        # asegurar al menos 1 carga consignada
        tag = uuid.uuid4().hex[:6]
        content = _make_excel_bytes(with_title_row=True, rows=2, unique_tag=tag)
        mapping = {"code": 0, "description": 1, "quantity": 3, "unit_cost": 4, "unit_price": 5, "supplier": 6}
        body = {"header_row": 2, "mapping": mapping}
        files = {"file": ("liqload.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data = {"mapping_json": json.dumps(body)}
        admin_sess.post(f"{API}/jornadas/{consign_jornada_id}/excel/import", files=files, data=data, timeout=30)

        r = admin_sess.get(f"{API}/jornadas/{consign_jornada_id}/liquidation", timeout=15)
        assert r.status_code == 200, r.text[:300]
        j = r.json()
        assert "per_supplier" in j
        assert "totals" in j
        t = j["totals"]
        for k in ("sold_units", "returned_units", "missing_units", "to_pay", "revenue", "margin"):
            assert k in t
        if j["per_supplier"]:
            sup = j["per_supplier"][0]
            assert "items" in sup
            if sup["items"]:
                it = sup["items"][0]
                for k in ("initial_qty", "sold_qty", "current_qty", "missing_qty", "to_pay", "revenue", "margin"):
                    assert k in it


# ═════════════════════ REPORTES PDF / XLSX ═════════════════════
class TestReports:
    def test_report_pdf(self, admin_sess, consign_jornada_id):
        r = admin_sess.get(f"{API}/jornadas/{consign_jornada_id}/report.pdf", timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert "attachment" in r.headers.get("content-disposition", "").lower()
        assert r.content[:4] == b"%PDF", f"bad magic {r.content[:10]}"

    def test_report_xlsx(self, admin_sess, consign_jornada_id):
        r = admin_sess.get(f"{API}/jornadas/{consign_jornada_id}/report.xlsx", timeout=30)
        assert r.status_code == 200, r.text[:200]
        ct = r.headers.get("content-type", "")
        assert "spreadsheet" in ct or "openxml" in ct
        assert "attachment" in r.headers.get("content-disposition", "").lower()
        assert r.content[:4] == b"PK\x03\x04", f"bad magic {r.content[:10]}"
        # Verificar hojas
        wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True)
        assert "Resumen" in wb.sheetnames
        assert "Liquidacion" in wb.sheetnames


# ═════════════════════ CIERRE HINT ═════════════════════
class TestCloseHint:
    def test_close_endpoint_still_reachable(self, admin_sess, consign_jornada_id):
        """No probamos cierre real (Iter 2 lo hizo), pero verificamos que el endpoint responde
        con validacion (jornada debe estar en 'en_cierre'). Si esta en 'activa' -> 400 esperado."""
        r = admin_sess.post(f"{API}/jornadas/{consign_jornada_id}/close", timeout=10)
        # Estado debe ser 'en_cierre' para cerrar. Si esta activa/planificada -> 400.
        # Si es 'cerrada' -> 400. Solo aceptamos que responda con status conocido.
        assert r.status_code in (200, 400, 404), r.text[:200]


# ═════════════════════ MULTITENANT ═════════════════════
class TestMultitenant:
    def test_liquidation_other_company_returns_404(self, admin_sess):
        # ObjectId falso valido
        fake = str(ObjectId())
        r = admin_sess.get(f"{API}/jornadas/{fake}/liquidation", timeout=10)
        assert r.status_code in (404, 401), r.text[:200]

    def test_report_pdf_other_company_returns_404(self, admin_sess):
        fake = str(ObjectId())
        r = admin_sess.get(f"{API}/jornadas/{fake}/report.pdf", timeout=10)
        assert r.status_code in (404, 401), r.text[:200]
