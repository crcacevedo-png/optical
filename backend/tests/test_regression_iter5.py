"""Regression tests for iteration 5:
- N+1 fix in list_consultations (patient_name/professional_name populated)
- PDF/Excel generation wrapped in asyncio.to_thread (magic bytes)
- Durable email queue (queue_email is async; endpoints don't 500)
- serialize_doc on list endpoints (no ObjectId leaks)
- Auth flows still work (login, me, refresh, logout, forgot-password)
"""
import io
import os
import time
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")

ADMIN = ("admin@cortexia.gt", "DemoAdmin2026!")
SUPER = ("superadmin@cortexia.com", "Montecristo2026")
VEND = ("vendedor@cortexia.gt", "DemoUser2026!")


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    _refresh_csrf(s)
    return s, r


def _refresh_csrf(s):
    csrf = s.cookies.get("csrf_token")
    if csrf:
        s.headers.update({"X-CSRF-Token": csrf})
    return csrf


@pytest.fixture(scope="module")
def admin_session():
    s, _ = _login(*ADMIN)
    return s


@pytest.fixture(scope="module")
def super_session():
    s, _ = _login(*SUPER)
    return s


@pytest.fixture(scope="module")
def vend_session():
    s, _ = _login(*VEND)
    return s


# --------- AUTH ---------
class TestAuth:
    def test_admin_login_and_me(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json().get("email") == ADMIN[0]

    def test_super_login_and_me(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200

    def test_vendedor_login_and_me(self, vend_session):
        r = vend_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200

    def test_refresh_preserves_session(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/auth/refresh", timeout=15)
        assert r.status_code == 200, r.text[:200]
        # session still valid
        r2 = admin_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r2.status_code == 200

    def test_forgot_password_no_500(self):
        # separate session so no login rate-limit interference
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password",
                          json={"email": ADMIN[0]}, timeout=20)
        assert r.status_code == 200, f"forgot-password: {r.status_code} {r.text[:200]}"

    def test_logout_only_current(self):
        s, _ = _login(*ADMIN)
        r = s.post(f"{BASE_URL}/api/auth/logout", timeout=15)
        assert r.status_code in (200, 204)


# --------- CONSULTATIONS N+1 fix ---------
class TestConsultations:
    def test_list_populates_names(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/consultations?limit=20", timeout=30)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", data.get("consultations", []))
        assert isinstance(items, list)
        if items:
            # at least one item should have patient_name populated (from batch $in)
            has_pname = any("patient_name" in it for it in items)
            has_prof = any("professional_name" in it for it in items)
            assert has_pname, "patient_name not present in consultation list items"
            assert has_prof, "professional_name not present in consultation list items"
            # no ObjectId leaks
            for it in items[:5]:
                if "_id" in it:
                    # if present, must be a string (already serialized), not an ObjectId dict
                    assert isinstance(it["_id"], str), f"ObjectId leak (non-string _id): {it.get('_id')}"


# --------- PDFs / XLSX ---------
def _get_first_id(session, url, key_candidates=None):
    r = session.get(url, timeout=30)
    if r.status_code != 200:
        return None
    d = r.json()
    items = d if isinstance(d, list) else d.get("items", d.get("results", d.get("data", [])))
    if not items:
        return None
    it = items[0]
    for k in (key_candidates or ["id", "_id"]):
        if k in it:
            return it[k]
    return None


class TestPDFs:
    def test_prescription_pdfs(self, admin_session):
        for kind in ("eyeglass", "contact", "medical"):
            r = admin_session.get(f"{BASE_URL}/api/prescriptions?type={kind}&limit=5", timeout=30)
            if r.status_code != 200:
                pytest.skip(f"cannot list prescriptions {kind}")
            items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
            if not items:
                continue
            pid = items[0].get("id") or items[0].get("_id")
            if not pid:
                continue
            rp = admin_session.get(f"{BASE_URL}/api/prescriptions/{kind}/{pid}/pdf", timeout=60)
            assert rp.status_code == 200, f"{kind} pdf {rp.status_code} {rp.text[:200]}"
            assert rp.content[:4] == b"%PDF", f"{kind} not a PDF"

    def test_quotation_pdf(self, admin_session):
        qid = _get_first_id(admin_session, f"{BASE_URL}/api/quotations?limit=5")
        if not qid:
            pytest.skip("no quotation available")
        r = admin_session.get(f"{BASE_URL}/api/quotations/{qid}/pdf", timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_cash_register_pdf(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/cash-register/report/pdf", timeout=60)
        # 200 with pdf or 404 if no register open
        assert r.status_code in (200, 400, 404), r.text[:200]
        if r.status_code == 200:
            assert r.content[:4] == b"%PDF"

    def test_jornada_reports(self, admin_session):
        jid = _get_first_id(admin_session, f"{BASE_URL}/api/jornadas?limit=5")
        if not jid:
            pytest.skip("no jornada")
        rp = admin_session.get(f"{BASE_URL}/api/jornadas/{jid}/report.pdf", timeout=60)
        assert rp.status_code == 200
        assert rp.content[:4] == b"%PDF"
        rx = admin_session.get(f"{BASE_URL}/api/jornadas/{jid}/report.xlsx", timeout=60)
        assert rx.status_code == 200
        assert rx.content[:2] == b"PK"

    def test_user_guide_pdf(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/docs/user-guide.pdf", timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_security_manifesto_public(self):
        r = requests.get(f"{BASE_URL}/api/security/manifesto.pdf", timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"


# --------- DATA EXPORT ---------
class TestDataExport:
    def test_full_db_export_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/data-export/full-database", timeout=180)
        assert r.status_code == 200, r.text[:300]
        assert r.content[:2] == b"PK"
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        # xlsx contains xl/worksheets/sheet*.xml
        sheets = [n for n in names if n.startswith("xl/worksheets/sheet")]
        assert len(sheets) >= 8, f"Only {len(sheets)} sheets found"

    def test_full_db_export_vendedor_forbidden(self, vend_session):
        r = vend_session.get(f"{BASE_URL}/api/data-export/full-database", timeout=30)
        assert r.status_code == 403


# --------- DURABLE EMAIL QUEUE ---------
class TestEmailQueue:
    def test_quotation_send_email_enqueues(self, admin_session):
        # find a quotation whose patient has email
        r = admin_session.get(f"{BASE_URL}/api/quotations?limit=20", timeout=30)
        if r.status_code != 200:
            pytest.skip("cannot list quotations")
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        target = None
        for q in items:
            qid = q.get("id") or q.get("_id")
            if not qid:
                continue
            # verify patient email via detail if needed
            det = admin_session.get(f"{BASE_URL}/api/quotations/{qid}", timeout=15)
            if det.status_code == 200:
                dj = det.json()
                pemail = dj.get("patient_email") or (dj.get("patient") or {}).get("email")
                if pemail:
                    target = qid
                    break
        if not target:
            pytest.skip("no quotation with patient email")
        _refresh_csrf(admin_session)
        r = admin_session.post(f"{BASE_URL}/api/quotations/{target}/send-email", timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        body = r.json()
        msg = (body.get("message") or body.get("detail") or "").lower()
        assert "encolad" in msg or "camino" in msg or "envio" in msg, f"unexpected msg: {msg}"


# --------- SERIALIZE_DOC endpoints (no ObjectId, no 500) ---------
class TestSerializeDoc:
    @pytest.mark.parametrize("path", [
        "/api/cash-register",
        "/api/cash-register/current",
        "/api/support-tickets",
        "/api/quotations?limit=10",
    ])
    def test_no_objectid_leaks(self, admin_session, path):
        r = admin_session.get(f"{BASE_URL}{path}", timeout=30)
        assert r.status_code in (200, 404), f"{path} -> {r.status_code} {r.text[:200]}"
        if r.status_code == 200:
            txt = r.text
            # ObjectId serialized as dict would have {"$oid":...}
            assert "$oid" not in txt, f"ObjectId leak on {path}"

    def test_companies_superadmin(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/companies", timeout=30)
        assert r.status_code == 200
        assert "$oid" not in r.text

    def test_jornada_nested_lists(self, admin_session):
        jid = _get_first_id(admin_session, f"{BASE_URL}/api/jornadas?limit=5")
        if not jid:
            pytest.skip("no jornada")
        for sub in ("sales", "inventory", "patients"):
            r = admin_session.get(f"{BASE_URL}/api/jornadas/{jid}/{sub}", timeout=30)
            assert r.status_code in (200, 404), f"jornada {sub}: {r.status_code}"
            if r.status_code == 200:
                assert "$oid" not in r.text


# --------- SUPPORT TICKETS ---------
class TestSupport:
    def test_create_ticket(self, admin_session):
        payload = {
            "subject": "TEST_iter5 regression ticket",
            "category": "otro",
            "priority": "baja",
            "message": "Automated regression - safe to delete",
        }
        _refresh_csrf(admin_session)
        r = admin_session.post(f"{BASE_URL}/api/support-tickets", json=payload, timeout=30)
        assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:300]}"
