"""Backend regression tests for:
 A) Sale receipt PDF (media carta horizontal) + WhatsApp share link + public endpoint
 B) Custom patient limit per company (SuperAdmin override)
"""
import io
import os
import struct
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

from _credentials import ADMIN_EMAIL, ADMIN_PASSWORD, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD  # noqa: E402


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
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


@pytest.fixture(scope="module")
def admin_info(admin):
    r = admin.get(f"{BASE_URL}/api/auth/me", timeout=30)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def some_sale_id(admin):
    r = admin.get(f"{BASE_URL}/api/sales", params={"limit": 5}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("data") or []
    assert items, f"No sales found for admin. resp={data}"
    sid = items[0].get("_id") or items[0].get("id")
    assert sid
    return sid


# ================= FEATURE A =================
class TestReceiptPDF:
    def test_a1_admin_can_download_pdf_media_carta(self, admin, some_sale_id):
        r = admin.get(f"{BASE_URL}/api/sales/{some_sale_id}/receipt.pdf", timeout=60)
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        # Verify page size 612 x 396 by parsing MediaBox
        text = r.content.decode("latin-1", errors="ignore")
        assert "/MediaBox" in text
        # find "/MediaBox [ 0 0 W H ]"
        import re
        m = re.search(r"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", text)
        assert m, "MediaBox not found in PDF"
        w, h = float(m.group(1)), float(m.group(2))
        assert abs(w - 612) < 1 and abs(h - 396) < 1, f"Expected 612x396 pt (media carta horizontal), got {w}x{h}"

    def test_a2_superadmin_forbidden(self, superadmin, some_sale_id):
        r = superadmin.get(f"{BASE_URL}/api/sales/{some_sale_id}/receipt.pdf", timeout=30)
        assert r.status_code == 403, r.text

    def test_a2_not_found(self, admin):
        r = admin.get(f"{BASE_URL}/api/sales/507f1f77bcf86cd799439011/receipt.pdf", timeout=30)
        assert r.status_code == 404

    def test_a3_share_link_shape(self, admin, some_sale_id):
        r = admin.get(f"{BASE_URL}/api/sales/{some_sale_id}/receipt-share-link", timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        for k in ["path", "token", "expires_at", "phone", "patient_name", "message"]:
            assert k in j, f"missing {k}"
        assert j["path"].startswith("/api/sales/public/receipt?token=")
        # phone should be digits only (if present)
        if j["phone"]:
            assert j["phone"].isdigit(), f"phone not normalized: {j['phone']}"
            # if starts with a length that isn't 502, then 502 should be prepended for GT
            # (we cannot assert 502 always - depends on the raw phone; just ensure digits)
        # save for a4
        pytest.shared_token = j["token"]

    def test_a4_public_endpoint_valid_token(self):
        token = getattr(pytest, "shared_token", None)
        assert token, "no token from a3"
        # New session, NO cookies/auth
        r = requests.get(f"{BASE_URL}/api/sales/public/receipt", params={"token": token}, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_a4_public_endpoint_invalid_token(self):
        r = requests.get(f"{BASE_URL}/api/sales/public/receipt", params={"token": "abcdefghijklmnop"}, timeout=30)
        assert r.status_code == 403, f"{r.status_code} {r.text[:200]}"


# ================= FEATURE B =================
@pytest.fixture(scope="module")
def companies_list(superadmin):
    r = superadmin.get(f"{BASE_URL}/api/companies", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("data") or []
    return items


@pytest.fixture(scope="module")
def target_company(companies_list):
    # Pick a company with plan_id
    for c in companies_list:
        if c.get("plan_id"):
            return c
    pytest.skip("no company with plan_id found")


@pytest.fixture(scope="module")
def admin_company_id(admin_info):
    return admin_info.get("company_id") or admin_info.get("user", {}).get("company_id")


class TestPatientLimitOverride:
    def test_b1_set_override_150(self, superadmin, target_company):
        cid = target_company.get("_id") or target_company.get("id")
        r = superadmin.put(
            f"{BASE_URL}/api/companies/{cid}/patient-limit",
            json={"patient_limit_override": 150}, timeout=30,
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("ok") is True
        assert j.get("patient_limit_override") == 150
        assert j.get("effective_max_patients") == 150
        assert "plan_max_patients" in j

    def test_b2_usage_and_listing_reflect_override(self, superadmin, target_company):
        cid = target_company.get("_id") or target_company.get("id")
        r = superadmin.get(f"{BASE_URL}/api/plans/usage/{cid}", timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("max_patients") == 150
        assert j.get("patient_limit_override") == 150
        assert "plan_max_patients" in j

        r2 = superadmin.get(f"{BASE_URL}/api/companies", timeout=30)
        assert r2.status_code == 200
        data = r2.json()
        items = data if isinstance(data, list) else data.get("items") or data.get("data") or []
        found = next((c for c in items if (c.get("_id") or c.get("id")) == cid), None)
        assert found, "target company not in listing"
        assert found.get("max_patients") == 150, f"listing max_patients={found.get('max_patients')}"
        assert found.get("patient_limit_override") == 150

    def test_b3_clear_override(self, superadmin, target_company):
        cid = target_company.get("_id") or target_company.get("id")
        r = superadmin.put(
            f"{BASE_URL}/api/companies/{cid}/patient-limit",
            json={"patient_limit_override": None}, timeout=30,
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("patient_limit_override") is None
        # effective back to plan
        assert j.get("effective_max_patients") == j.get("plan_max_patients")

    def test_b4_admin_forbidden(self, admin, target_company):
        cid = target_company.get("_id") or target_company.get("id")
        r = admin.put(
            f"{BASE_URL}/api/companies/{cid}/patient-limit",
            json={"patient_limit_override": 200}, timeout=30,
        )
        assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text[:200]}"

    def test_b5_enforcement_real_block(self, superadmin, admin, admin_company_id):
        assert admin_company_id, "no admin company_id"
        # Set override=1 on admin's company
        r = superadmin.put(
            f"{BASE_URL}/api/companies/{admin_company_id}/patient-limit",
            json={"patient_limit_override": 1}, timeout=30,
        )
        assert r.status_code == 200, r.text

        try:
            # attempt to create -> should 403
            payload = {
                "first_name": "TEST_QA",
                "last_name": "LimitBlock",
                "email": "test_qa_limit@example.com",
                "phone": "50255550000",
            }
            r2 = admin.post(f"{BASE_URL}/api/patients", json=payload, timeout=30)
            assert r2.status_code == 403, f"expected 403 got {r2.status_code} {r2.text[:200]}"
            body = r2.text.lower()
            assert "limite" in body or "límite" in body or "limit" in body

            # clear override
            r3 = superadmin.put(
                f"{BASE_URL}/api/companies/{admin_company_id}/patient-limit",
                json={"patient_limit_override": None}, timeout=30,
            )
            assert r3.status_code == 200

            # now should succeed
            r4 = admin.post(f"{BASE_URL}/api/patients", json=payload, timeout=30)
            assert r4.status_code in (200, 201), f"expected 200/201 got {r4.status_code} {r4.text[:300]}"
            created = r4.json()
            new_id = created.get("_id") or created.get("id")
            # cleanup created patient
            if new_id:
                admin.delete(f"{BASE_URL}/api/patients/{new_id}", timeout=30)
        finally:
            # final safety: ensure override is cleared
            superadmin.put(
                f"{BASE_URL}/api/companies/{admin_company_id}/patient-limit",
                json={"patient_limit_override": None}, timeout=30,
            )
