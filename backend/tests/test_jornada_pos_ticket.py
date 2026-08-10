"""Iter 3.1 - Tests para Consulta + Receta encadenadas + Ticket PDF desde POS de jornada."""
import os
import uuid
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@cortexia.gt"
ADMIN_PASSWORD = "Demo123!"
SUPERADMIN_EMAIL = "superadmin@cortexia.com"
SUPERADMIN_PASSWORD = "Montecristo2026"

JORNADA_ACTIVE_ID = "6a793f0e1c71bc5b4d9c98ba"
PATIENT_ID = "6a7943f350b4d516a5cb0fec"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        return None
    return s


@pytest.fixture(scope="module")
def admin_sess():
    s = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not s:
        pytest.skip("no login admin demo")
    return s


# ─────────────── CONSULTA RAPIDA ───────────────
class TestConsultationQuick:
    def test_create_consultation_active_jornada(self, admin_sess):
        payload = {
            "patient_id": PATIENT_ID,
            "reason": f"TEST_reason_{uuid.uuid4().hex[:5]}",
            "observations": "obs test",
            "vision_od": "20/20",
            "vision_oi": "20/40",
        }
        r = admin_sess.post(f"{API}/jornadas/{JORNADA_ACTIVE_ID}/consultations", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "_id" in data
        assert len(data["_id"]) == 24
        pytest.consultation_id = data["_id"]

    def test_create_consultation_bad_patient(self, admin_sess):
        r = admin_sess.post(
            f"{API}/jornadas/{JORNADA_ACTIVE_ID}/consultations",
            json={"patient_id": "invalid"}, timeout=15,
        )
        assert r.status_code == 400


# ─────────────── RECETA RAPIDA ───────────────
class TestPrescriptionQuick:
    def test_create_rx_active_jornada(self, admin_sess):
        payload = {
            "patient_id": PATIENT_ID,
            "consultation_id": getattr(pytest, "consultation_id", None),
            "od_sphere": -1.25, "od_cylinder": -0.5, "od_axis": 90, "od_addition": 0, "od_dp": 32,
            "oi_sphere": -1.0, "oi_cylinder": -0.25, "oi_axis": 85, "oi_addition": 0, "oi_dp": 32,
            "lens_type": "monofocal", "observations": "TEST_rx",
        }
        r = admin_sess.post(f"{API}/jornadas/{JORNADA_ACTIVE_ID}/prescriptions/eyeglass", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "_id" in data
        pytest.prescription_id = data["_id"]


# ─────────────── SALE con consultation + prescription ───────────────
class TestSaleWithMedicalRefs:
    def test_create_sale_with_refs_and_receipt_pdf(self, admin_sess):
        # find product in jornada stock
        r_stock = admin_sess.get(f"{API}/jornadas/{JORNADA_ACTIVE_ID}/inventory", timeout=15)
        assert r_stock.status_code == 200
        items = r_stock.json().get("items", [])
        avail = [it for it in items if float(it.get("current_qty", 0)) >= 1]
        if not avail:
            pytest.skip("no stock disponible en jornada demo para ejecutar sale")
        pick = avail[0]
        product_id = str(pick.get("product_id"))
        price = float(pick.get("price") or pick.get("sale_price") or 100)

        sale_payload = {
            "patient_id": PATIENT_ID,
            "items": [{
                "product_id": product_id,
                "name": pick.get("name", "TEST_prod"),
                "quantity": 1, "price": price, "total": price,
            }],
            "payments": [{"method": "cash", "amount": price}],
            "discount": 0,
            "consultation_id": getattr(pytest, "consultation_id", None),
            "prescription_id": getattr(pytest, "prescription_id", None),
        }
        r = admin_sess.post(f"{API}/jornadas/{JORNADA_ACTIVE_ID}/sales", json=sale_payload, timeout=20)
        assert r.status_code == 200, r.text
        sale_id = r.json()["_id"]
        pytest.sale_id = sale_id

        # GET receipt PDF
        r_pdf = admin_sess.get(f"{API}/jornadas/{JORNADA_ACTIVE_ID}/sales/{sale_id}/receipt.pdf", timeout=20)
        assert r_pdf.status_code == 200, r_pdf.text
        assert r_pdf.headers.get("content-type", "").startswith("application/pdf")
        cd = r_pdf.headers.get("content-disposition", "")
        assert "inline" in cd.lower()
        assert r_pdf.content[:5] == b"%PDF-"
        assert len(r_pdf.content) > 500

    def test_receipt_pdf_404_wrong_sale(self, admin_sess):
        fake_sale = "6a7943f350b4d516a5cb0000"
        r = admin_sess.get(f"{API}/jornadas/{JORNADA_ACTIVE_ID}/sales/{fake_sale}/receipt.pdf", timeout=15)
        assert r.status_code == 404

    def test_receipt_pdf_multitenant_isolation(self, admin_sess):
        # sale existente pero con jornada distinta => 404
        fake_jornada = "000000000000000000000001"
        sale_id = getattr(pytest, "sale_id", None)
        if not sale_id:
            pytest.skip("no sale_id")
        r = admin_sess.get(f"{API}/jornadas/{fake_jornada}/sales/{sale_id}/receipt.pdf", timeout=15)
        assert r.status_code in (400, 404)


# ─────────────── VALIDATIONS ───────────────
class TestValidations:
    def test_consultation_invalid_jornada(self, admin_sess):
        r = admin_sess.post(
            f"{API}/jornadas/000000000000000000000001/consultations",
            json={"patient_id": PATIENT_ID}, timeout=15,
        )
        assert r.status_code in (400, 404)

    def test_rx_invalid_jornada(self, admin_sess):
        r = admin_sess.post(
            f"{API}/jornadas/000000000000000000000001/prescriptions/eyeglass",
            json={"patient_id": PATIENT_ID}, timeout=15,
        )
        assert r.status_code in (400, 404)
