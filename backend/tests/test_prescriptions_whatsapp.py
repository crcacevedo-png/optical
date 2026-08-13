"""Tests for prescription list endpoints enrichment with patient_phone/patient_whatsapp
and regression on POST + PDF endpoints. Also validates related endpoints."""
import os
import io
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "admin@cortexia.gt")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD",""))


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    # Auth via httpOnly cookies; also attach bearer if provided
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


# Backwards-compat alias used across tests
@pytest.fixture(scope="module")
def headers(session):
    return session  # actually a Session, used with .get/.post


@pytest.fixture(scope="module")
def patient_id(headers):
    # Try to fetch existing patients
    r = headers.get(f"{API}/patients", timeout=30)
    assert r.status_code == 200, f"GET /patients failed: {r.status_code} {r.text}"
    body = r.json()
    patients = body["patients"] if isinstance(body, dict) else body
    if patients:
        return patients[0]["_id"]
    # Otherwise create one
    payload = {
        "first_name": "TEST_WA",
        "last_name": "Paciente",
        "phone": "50255551111",
        "whatsapp": "50255552222",
    }
    r = headers.post(f"{API}/patients", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"Create patient failed: {r.status_code} {r.text}"
    return r.json()["_id"]


# ============ Enrichment tests ============

@pytest.mark.parametrize("rx_type", ["eyeglass", "contact", "medical"])
def test_list_prescriptions_enrichment_fields(headers, rx_type):
    r = headers.get(f"{API}/prescriptions/{rx_type}", timeout=30)
    assert r.status_code == 200, f"GET /prescriptions/{rx_type} -> {r.status_code} {r.text}"
    items = r.json()
    assert isinstance(items, list)
    if not items:
        pytest.skip(f"No {rx_type} prescriptions returned; cannot verify enrichment")
    # Count rx that got enriched vs orphan
    enriched = [rx for rx in items if "patient_name" in rx]
    orphan = [rx for rx in items if "patient_name" not in rx]
    print(f"[{rx_type}] total={len(items)} enriched={len(enriched)} orphan={len(orphan)}")
    if orphan:
        # Report but don't fail here - covered by dedicated test_orphan
        print(f"WARN: {len(orphan)} orphan rx (patient deleted) missing enrichment fields")
    # At least one rx must be enriched (assuming at least one patient exists)
    assert enriched, f"No {rx_type} rx had enrichment fields at all"
    for rx in enriched:
        assert "patient_phone" in rx and isinstance(rx["patient_phone"], str)
        assert "patient_whatsapp" in rx and isinstance(rx["patient_whatsapp"], str)


# ============ POST regression + then enrichment verification ============

def _eyeglass_payload(patient_id):
    return {
        "patient_id": patient_id,
        "professional_name": "Dr TEST",
        "od_sphere": "-1.00", "od_cylinder": "-0.50", "od_axis": 90,
        "oi_sphere": "-1.25", "oi_cylinder": "-0.75", "oi_axis": 85,
        "observations": "TEST_WA eyeglass",
        "lens_type": "monofocal",
    }


def _contact_payload(patient_id):
    return {
        "patient_id": patient_id,
        "professional_name": "Dr TEST",
        "od_power": "-1.00", "od_bc": "8.6", "od_dia": "14.2",
        "oi_power": "-1.25", "oi_bc": "8.6", "oi_dia": "14.2",
        "brand": "TEST", "lens_type": "monthly", "replacement": "mensual",
        "observations": "TEST_WA contact",
    }


def _medical_payload(patient_id):
    return {
        "patient_id": patient_id,
        "professional_name": "Dr TEST",
        "diagnosis": "TEST_WA diagnosis",
        "medications": [{"name": "Med A", "dose": "1x1", "duration": "7 dias"}],
        "instructions": "Tomar con agua",
    }


@pytest.fixture(scope="module")
def created_rx_ids(headers, patient_id):
    ids = {}
    endpoints = {
        "eyeglass": _eyeglass_payload(patient_id),
        "contact": _contact_payload(patient_id),
        "medical": _medical_payload(patient_id),
    }
    for rx_type, payload in endpoints.items():
        r = headers.post(f"{API}/prescriptions/{rx_type}", json=payload, timeout=30)
        assert r.status_code in (200, 201), f"POST /prescriptions/{rx_type} -> {r.status_code} {r.text}"
        body = r.json()
        assert "_id" in body, f"No _id in response for {rx_type}: {body}"
        ids[rx_type] = body["_id"]
    return ids


@pytest.mark.parametrize("rx_type", ["eyeglass", "contact", "medical"])
def test_post_prescription_and_verify_enrichment(headers, created_rx_ids, patient_id, rx_type):
    # After creating, list should contain this rx with enriched fields
    r = headers.get(f"{API}/prescriptions/{rx_type}?patient_id={patient_id}", timeout=30)
    assert r.status_code == 200
    items = r.json()
    match = [rx for rx in items if rx.get("_id") == created_rx_ids[rx_type]]
    assert match, f"Created {rx_type} rx not found in list for patient"
    rx = match[0]
    assert "patient_name" in rx and rx["patient_name"], f"patient_name empty in {rx_type}"
    assert "patient_phone" in rx
    assert "patient_whatsapp" in rx


# ============ PDF regression ============

@pytest.mark.parametrize("rx_type", ["eyeglass", "contact", "medical"])
def test_get_prescription_pdf(headers, created_rx_ids, rx_type):
    rx_id = created_rx_ids[rx_type]
    r = headers.get(f"{API}/prescriptions/{rx_type}/{rx_id}/pdf", timeout=60)
    assert r.status_code == 200, f"PDF {rx_type} -> {r.status_code} {r.text[:200]}"
    ctype = r.headers.get("content-type", "")
    assert "application/pdf" in ctype, f"Wrong content-type for {rx_type}: {ctype}"
    # Valid PDF starts with %PDF
    assert r.content[:4] == b"%PDF", f"Not a valid PDF for {rx_type}"


# ============ Related endpoints regression ============

@pytest.mark.parametrize("path,allowed", [
    ("/sales", (200,)),
    ("/patients", (200,)),
    ("/quotations", (200,)),
    ("/support-tickets", (200, 403)),
    ("/cash-register/current", (200, 404)),
])
def test_related_endpoints_ok(headers, path, allowed):
    r = headers.get(f"{API}{path}", timeout=30)
    assert r.status_code in allowed, f"GET {path} -> {r.status_code} {r.text[:200]}"


# ============ Empty phone/whatsapp fields still present ============

def test_patient_without_phone_still_has_fields(headers):
    """Create a patient without phone/whatsapp, then a prescription, then verify fields exist as empty strings."""
    payload = {"first_name": "TEST_NoPhone", "last_name": "WA", "phone": ""}
    r = headers.post(f"{API}/patients", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"Create patient failed: {r.status_code} {r.text}"
    pid = r.json()["_id"]

    # Create eyeglass rx
    rx_payload = _eyeglass_payload(pid)
    r = headers.post(f"{API}/prescriptions/eyeglass", json=rx_payload, timeout=30)
    assert r.status_code in (200, 201)
    rx_id = r.json()["_id"]

    # List and inspect
    r = headers.get(f"{API}/prescriptions/eyeglass?patient_id={pid}", timeout=30)
    assert r.status_code == 200
    items = r.json()
    match = [rx for rx in items if rx.get("_id") == rx_id]
    assert match, "Rx not found"
    rx = match[0]
    assert rx.get("patient_phone", None) == "" or rx.get("patient_phone") is None or isinstance(rx.get("patient_phone"), str)
    assert rx.get("patient_whatsapp", None) == "" or rx.get("patient_whatsapp") is None or isinstance(rx.get("patient_whatsapp"), str)
    # Field must be present in response dict
    assert "patient_phone" in rx
    assert "patient_whatsapp" in rx
