# Currency selection (LATAM) feature tests: settings PUT, /me, validation, RBAC, retrocompat, documents symbol
import io
import os
import re
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = ("admin@cortexia.gt", "DemoAdmin2026!")
VEND = ("vendedor@cortexia.gt", "DemoUser2026!")


def _login(email, pwd):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code} {r.text[:200]}")
    csrf = s.cookies.get("csrf_token")
    if csrf:
        s.headers.update({"X-CSRF-Token": csrf})
    return s


@pytest.fixture(scope="module")
def admin():
    s = _login(*ADMIN)
    yield s
    # Always reset to GTQ
    s.put(f"{BASE_URL}/api/settings/company", json={"currency": "GTQ"})


@pytest.fixture(scope="module")
def vendedor():
    return _login(*VEND)


def _items(js):
    if isinstance(js, list):
        return js
    for k in ("items", "sales", "quotations", "registers", "jornadas", "data", "results"):
        if isinstance(js.get(k), list):
            return js[k]
    return []


def _pdf_text(content):
    import fitz
    doc = fitz.open(stream=content, filetype="pdf")
    return "\n".join(p.get_text() for p in doc)


def _xlsx_text(content):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    out = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            out.extend(str(c) for c in row if c is not None)
        # include number formats
        for row in ws.iter_rows():
            for c in row:
                if c.number_format and c.number_format != "General":
                    out.append("FMT:" + c.number_format)
    return "\n".join(out)


Q_RE = re.compile(r"(?<![A-Za-z])Q\s?\d")


# --- Settings / auth
class TestCurrencySettings:
    def test_set_mxn_and_me(self, admin):
        r = admin.put(f"{BASE_URL}/api/settings/company", json={"currency": "MXN"})
        assert r.status_code == 200, r.text
        me = admin.get(f"{BASE_URL}/api/auth/me").json()
        assert me.get("currency") == "MXN"

    def test_invalid_currency(self, admin):
        r = admin.put(f"{BASE_URL}/api/settings/company", json={"currency": "XXX"})
        assert r.status_code == 400
        assert "Moneda" in r.json().get("detail", "")
        me = admin.get(f"{BASE_URL}/api/auth/me").json()
        assert me.get("currency") == "MXN"  # unchanged

    def test_lowercase_currency(self, admin):
        r = admin.put(f"{BASE_URL}/api/settings/company", json={"currency": "mxn"})
        print("lowercase mxn ->", r.status_code, r.text[:200])

    def test_vendedor_forbidden(self, vendedor):
        r = vendedor.put(f"{BASE_URL}/api/settings/company", json={"currency": "USD"})
        assert r.status_code == 403
        me = vendedor.get(f"{BASE_URL}/api/auth/me").json()
        print("vendedor me currency:", me.get("currency"))
        assert me.get("currency") == "MXN"  # same company shares currency

    def test_login_includes_currency(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
        assert r.status_code == 200
        js = r.json()
        u = js.get("user", js)
        assert u.get("currency") == "MXN"


# --- Documents with MXN (symbol '$')
class TestDocumentsSymbol:
    @pytest.fixture(autouse=True)
    def _set_mxn(self, admin):
        admin.put(f"{BASE_URL}/api/settings/company", json={"currency": "PEN"})

    def _check_pdf(self, r, name):
        assert r.status_code == 200, f"{name}: {r.status_code} {r.text[:200]}"
        txt = _pdf_text(r.content)
        q = Q_RE.findall(txt)
        print(f"{name}: S/ count={txt.count('S/')} Q-matches={q[:5]}")
        assert not q, f"{name} still contains Q amounts: {q[:5]}"
        return txt

    def test_sale_receipt_pdf(self, admin):
        sales = _items(admin.get(f"{BASE_URL}/api/sales").json())
        if not sales:
            pytest.skip("no sales")
        sid = sales[0].get("id") or sales[0].get("_id")
        txt = self._check_pdf(admin.get(f"{BASE_URL}/api/sales/{sid}/receipt.pdf"), "sale_receipt")
        assert "S/" in txt

    def test_quotation_pdf(self, admin):
        qs = _items(admin.get(f"{BASE_URL}/api/quotations").json())
        if not qs:
            pytest.skip("no quotations")
        qid = qs[0].get("id") or qs[0].get("_id")
        txt = self._check_pdf(admin.get(f"{BASE_URL}/api/quotations/{qid}/pdf"), "quotation")
        assert "S/" in txt

    def test_cash_report_pdf(self, admin):
        txt = self._check_pdf(admin.get(f"{BASE_URL}/api/cash-register/report/pdf"), "cash_report")
        assert "S/" in txt

    def test_single_cierre_pdf(self, admin):
        regs = _items(admin.get(f"{BASE_URL}/api/cash-register").json())
        if not regs:
            pytest.skip("no registers")
        rid = regs[0].get("id") or regs[0].get("_id")
        txt = self._check_pdf(admin.get(f"{BASE_URL}/api/cash-register/{rid}/pdf"), "single_cierre")
        assert "S/" in txt

    def test_income_statement_pdf(self, admin):
        txt = self._check_pdf(admin.get(f"{BASE_URL}/api/finance/income-statement.pdf"), "pl_pdf")
        assert "S/" in txt

    def test_reports_excel(self, admin):
        r = admin.get(f"{BASE_URL}/api/reports/export/excel")
        assert r.status_code == 200, r.text[:200]
        txt = _xlsx_text(r.content)
        q = Q_RE.findall(txt)
        qfmt = [l for l in txt.splitlines() if l.startswith("FMT:") and "Q" in l]
        print("reports xlsx S/ count:", txt.count("S/"), "Q:", q[:5], "Qfmt:", set(qfmt))
        assert not q and not qfmt

    def test_other_xlsx(self, admin):
        for path in ["/api/finance/income-statement.xlsx", "/api/finance/purchases-report.xlsx",
                     "/api/finance/expenses-report.xlsx"]:
            r = admin.get(f"{BASE_URL}{path}")
            if r.status_code != 200:
                print(path, r.status_code)
                continue
            txt = _xlsx_text(r.content)
            qfmt = set(l for l in txt.splitlines() if l.startswith("FMT:") and "Q" in l)
            print(path, "Q:", Q_RE.findall(txt)[:3], "Qfmt:", qfmt, "S/:", txt.count("S/"))

    def test_jornada_report_pdf(self, admin):
        js = _items(admin.get(f"{BASE_URL}/api/jornadas").json())
        if not js:
            pytest.skip("no jornadas")
        jid = js[0].get("id") or js[0].get("_id")
        txt = self._check_pdf(admin.get(f"{BASE_URL}/api/jornadas/{jid}/report.pdf"), "jornada_report")
        print("jornada S/:", "S/" in txt)


# --- Retrocompat: company without currency field -> GTQ
class TestRetrocompat:
    def test_missing_field_defaults_gtq(self, admin):
        from pymongo import MongoClient
        cli = MongoClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        me = admin.get(f"{BASE_URL}/api/auth/me").json()
        from bson import ObjectId
        cid = ObjectId(me["company_id"])
        db.companies.update_one({"_id": cid}, {"$unset": {"currency": ""}})
        try:
            me2 = admin.get(f"{BASE_URL}/api/auth/me").json()
            assert me2.get("currency") == "GTQ"
        finally:
            r = admin.put(f"{BASE_URL}/api/settings/company", json={"currency": "GTQ"})
            assert r.status_code == 200
