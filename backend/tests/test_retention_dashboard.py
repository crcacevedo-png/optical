"""Tests para el Panel de Retencion (FEATURE B, C) y activation_task welcome_tips (FEATURE A).

Cobertura:
- GET /api/superadmin/retention (KPIs + segments + 403 para non-superadmin)
- POST /api/companies/{id}/reactivate (superadmin only, 404, mongo state, password_reset, audit)
- activation_task._process_welcome_tips: envia dia 3+, idempotente, no re-envia, resetea en reactivate

IMPORTANT: NUNCA modificar opticas reales (Altavista, Demo, Vision Clara). Solo TEST_*.
"""
import os
import sys
import uuid
import asyncio
import pytest
import requests
from datetime import datetime, timezone, timedelta
from bson import ObjectId

# Path para importar modulos del backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

# Un unico event loop compartido para todas las ops mongo (motor bindea loop)
_LOOP = asyncio.new_event_loop()

def run_async(coro):
    return _LOOP.run_until_complete(coro)
# Credenciales leidas SOLO de env vars (via _credentials.py). Sin secretos hardcodeados.
from _credentials import (  # noqa: E402
    SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD,
    ADMIN_EMAIL, ADMIN_PASSWORD,
    VENDEDOR_EMAIL, VENDEDOR_PASSWORD,
    require,
)
SUPERADMIN_PASSWORD = require("SUPERADMIN_PASSWORD", SUPERADMIN_PASSWORD)
ADMIN_PASSWORD = require("ADMIN_PASSWORD", ADMIN_PASSWORD)
VENDEDOR_PASSWORD = require("VENDEDOR_PASSWORD", VENDEDOR_PASSWORD)


def _login(session, email, password):
    return session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})


@pytest.fixture(scope="module")
def superadmin_session():
    s = requests.Session()
    r = _login(s, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    assert r.status_code == 200, f"SuperAdmin login failed: {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return s


@pytest.fixture(scope="module")
def vendedor_session():
    s = requests.Session()
    r = _login(s, VENDEDOR_EMAIL, VENDEDOR_PASSWORD)
    assert r.status_code == 200, f"Vendedor login failed: {r.text}"
    return s


# ============================================================
# FEATURE B: GET /api/superadmin/retention
# ============================================================
class TestRetentionEndpoint:
    def test_superadmin_can_access(self, superadmin_session):
        r = superadmin_session.get(f"{BASE_URL}/api/superadmin/retention")
        assert r.status_code == 200
        data = r.json()
        # KPIs structure
        assert "kpis" in data
        kpis = data["kpis"]
        for key in ["total", "active", "inactive", "never_activated",
                    "at_risk", "expired", "recently_activated", "activation_rate"]:
            assert key in kpis, f"KPI '{key}' faltante"
        # Thresholds
        assert "thresholds" in data
        assert data["thresholds"]["at_risk_days"] == 15
        assert data["thresholds"]["deadline_days"] == 30
        # Segments
        assert "segments" in data
        for seg in ["never_activated", "at_risk", "expired", "recently_activated"]:
            assert seg in data["segments"]
            assert isinstance(data["segments"][seg], list)
        # activation_rate is a float
        assert isinstance(kpis["activation_rate"], (int, float))
        assert 0 <= kpis["activation_rate"] <= 100

    def test_admin_forbidden(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/superadmin/retention")
        assert r.status_code == 403

    def test_vendedor_forbidden(self, vendedor_session):
        r = vendedor_session.get(f"{BASE_URL}/api/superadmin/retention")
        assert r.status_code == 403

    def test_unauthenticated_forbidden(self):
        r = requests.get(f"{BASE_URL}/api/superadmin/retention")
        assert r.status_code in (401, 403)

    def test_segment_items_have_required_fields(self, superadmin_session):
        r = superadmin_session.get(f"{BASE_URL}/api/superadmin/retention")
        data = r.json()
        # Al menos un segmento debe tener items para validar shape;
        # si todos vacios, no falla pero se skippea la validacion detallada.
        all_items = []
        for seg in ["never_activated", "at_risk", "expired", "recently_activated"]:
            all_items.extend(data["segments"][seg])
        if not all_items:
            pytest.skip("No hay opticas en ningun segmento — no se puede validar shape")
        for item in all_items[:5]:
            for key in ["name", "admin_email", "admin_name", "days_since_created",
                        "days_since_last_login", "plan_name", "patients_count"]:
                assert key in item, f"Field '{key}' missing in segment item"


# ============================================================
# FEATURE C: POST /api/companies/{id}/reactivate
# ============================================================
class TestReactivateEndpoint:
    _cid = None
    _admin_email = None

    def test_1_create_and_deactivate(self, superadmin_session):
        """Crea TEST company y la desactiva manualmente via API."""
        unique = uuid.uuid4().hex[:8]
        email = f"test_reactivate_{unique}@example.com"
        payload = {
            "name": f"TEST_Reactivate_Optica_{unique}",
            "legal_name": f"TEST_Reactivate_Optica_{unique}",
            "tax_id": f"REAC{unique}",
            "address": "Test",
            "phone": "+50255551234",
            "email": f"info_{unique}@example.com",
            "contact_name": "Contact",
            "contact_phone": "+50255551234",
            "contact_email": f"info_{unique}@example.com",
            "admin_email": email,
            "admin_password": "TestReactivate2026!",
            "admin_name": "Test Reactivate Admin",
        }
        r = superadmin_session.post(f"{BASE_URL}/api/companies", json=payload)
        assert r.status_code == 200, f"Create failed: {r.text}"
        TestReactivateEndpoint._cid = r.json()["_id"]
        TestReactivateEndpoint._admin_email = email

        # Marcar is_active=False + deactivated_reason via mongo (async)
        async def _deactivate():
            from db import db
            await db.companies.update_one(
                {"_id": ObjectId(TestReactivateEndpoint._cid)},
                {"$set": {
                    "is_active": False,
                    "deactivated_reason": "activation_expired",
                    "deactivated_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
            await db.users.update_many(
                {"company_id": ObjectId(TestReactivateEndpoint._cid), "role": "admin"},
                {"$set": {"is_active": False, "deactivated_by_activation_expiry_at": datetime.now(timezone.utc).isoformat()}}
            )
        run_async(_deactivate())

    def test_2_reactivate_success(self, superadmin_session):
        cid = TestReactivateEndpoint._cid
        assert cid, "test_1 debe correr antes"
        r = superadmin_session.post(f"{BASE_URL}/api/companies/{cid}/reactivate")
        assert r.status_code == 200, f"Reactivate failed: {r.text}"
        body = r.json()
        assert body["ok"]
        assert body["admin_email"] == TestReactivateEndpoint._admin_email

    def test_3_mongo_state_after_reactivate(self):
        cid = TestReactivateEndpoint._cid
        async def _check():
            from db import db
            company = await db.companies.find_one({"_id": ObjectId(cid)})
            assert company["is_active"]
            assert "reactivated_at" in company
            assert "reactivated_by" in company
            assert "deactivated_reason" not in company
            assert "deactivated_at" not in company
            admin = await db.users.find_one({"company_id": ObjectId(cid), "role": "admin"})
            assert admin["is_active"]
            assert "deactivated_by_activation_expiry_at" not in admin
            # welcome_tips_sent_at + reminder_7d + reminder_2d unset
            assert "welcome_tips_sent_at" not in admin
            assert "reminder_7d_sent_at" not in admin
            assert "reminder_2d_sent_at" not in admin
            # Password reset creado con source=reactivation y TTL 24h
            reset = await db.password_resets.find_one(
                {"user_id": admin["_id"], "source": "reactivation"},
                sort=[("created_at", -1)]
            )
            assert reset is not None, "Debe crearse password_reset con source='reactivation'"
            assert not reset["used"]
            # expires 24h from created_at (con margen)
            delta = reset["expires_at"] - reset["created_at"]
            assert timedelta(hours=23) <= delta <= timedelta(hours=25)
        run_async(_check())

    def test_4_audit_log_created(self):
        cid = TestReactivateEndpoint._cid
        async def _check():
            from db import db
            log = await db.audit_log.find_one(
                {"action": "COMPANY_REACTIVATED", "company_id": ObjectId(cid)},
                sort=[("created_at", -1)]
            )
            assert log is not None, "Audit COMPANY_REACTIVATED debe existir"
        run_async(_check())

    def test_5_reactivate_admin_forbidden(self, admin_session):
        cid = TestReactivateEndpoint._cid
        r = admin_session.post(f"{BASE_URL}/api/companies/{cid}/reactivate")
        assert r.status_code == 403

    def test_6_reactivate_nonexistent_returns_404(self, superadmin_session):
        fake = "507f1f77bcf86cd799439011"
        r = superadmin_session.post(f"{BASE_URL}/api/companies/{fake}/reactivate")
        assert r.status_code == 404

    def test_7_reactivate_invalid_id_returns_400(self, superadmin_session):
        r = superadmin_session.post(f"{BASE_URL}/api/companies/not-an-oid/reactivate")
        assert r.status_code == 400

    def test_99_cleanup(self):
        """Borra hard-delete la company y admin de test."""
        cid = TestReactivateEndpoint._cid
        if not cid:
            return
        async def _cleanup():
            from db import db
            oid = ObjectId(cid)
            await db.users.delete_many({"company_id": oid})
            await db.companies.delete_one({"_id": oid})
            await db.password_resets.delete_many({"email": TestReactivateEndpoint._admin_email})
        run_async(_cleanup())


# ============================================================
# FEATURE A: activation_task._process_welcome_tips (dia >= 3, < 23)
# ============================================================
class TestWelcomeTipsTask:
    _cid = None
    _admin_id = None

    def test_1_create_old_company(self, superadmin_session):
        """Crea company + admin y backdate created_at a hace 5 dias."""
        unique = uuid.uuid4().hex[:8]
        email = f"test_welcome_{unique}@example.com"
        payload = {
            "name": f"TEST_Welcome_Optica_{unique}",
            "legal_name": f"TEST_Welcome_Optica_{unique}",
            "tax_id": f"WEL{unique}",
            "address": "Test",
            "phone": "+50255551234",
            "email": f"info_{unique}@example.com",
            "contact_name": "Contact",
            "contact_phone": "+50255551234",
            "contact_email": f"info_{unique}@example.com",
            "admin_email": email,
            "admin_password": "TestWelcome2026!",
            "admin_name": "Test Welcome Admin",
        }
        r = superadmin_session.post(f"{BASE_URL}/api/companies", json=payload)
        assert r.status_code == 200, r.text
        TestWelcomeTipsTask._cid = r.json()["_id"]

        # Backdate: created_at a hace 5 dias, admin sin first_login_at
        async def _prep():
            from db import db
            five_days_ago = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
            await db.companies.update_one(
                {"_id": ObjectId(TestWelcomeTipsTask._cid)},
                {"$set": {"created_at": five_days_ago}}
            )
            admin = await db.users.find_one({"company_id": ObjectId(TestWelcomeTipsTask._cid), "role": "admin"})
            TestWelcomeTipsTask._admin_id = admin["_id"]
            await db.users.update_one(
                {"_id": admin["_id"]},
                {"$unset": {"first_login_at": "", "welcome_tips_sent_at": ""}}
            )
        run_async(_prep())

    def test_2_run_once_sends_welcome(self):
        """Ejecuta run_once y verifica welcome_tips_sent_at marcado."""
        async def _run():
            from activation_task import run_once
            from db import db
            await run_once()
            admin = await db.users.find_one({"_id": TestWelcomeTipsTask._admin_id})
            assert admin.get("welcome_tips_sent_at") is not None, \
                "welcome_tips_sent_at debe marcarse tras run_once"
        run_async(_run())

    def test_3_run_once_idempotent(self):
        """Segundo run_once no debe re-enviar — marker no debe cambiar."""
        async def _run():
            from activation_task import run_once
            from db import db
            admin_before = await db.users.find_one({"_id": TestWelcomeTipsTask._admin_id})
            marker_before = admin_before.get("welcome_tips_sent_at")
            await run_once()
            admin_after = await db.users.find_one({"_id": TestWelcomeTipsTask._admin_id})
            assert admin_after.get("welcome_tips_sent_at") == marker_before, \
                "welcome_tips_sent_at no debe re-marcarse (idempotencia)"
        run_async(_run())

    def test_4_not_sent_if_days_less_than_3(self, superadmin_session):
        """Crea company con created_at = hoy, run_once no debe enviar."""
        unique = uuid.uuid4().hex[:8]
        payload = {
            "name": f"TEST_Welcome_Fresh_{unique}",
            "legal_name": f"TEST_Welcome_Fresh_{unique}",
            "tax_id": f"FRE{unique}",
            "address": "T", "phone": "+50255551234",
            "email": f"info_{unique}@example.com",
            "contact_name": "C", "contact_phone": "+50255551234",
            "contact_email": f"info_{unique}@example.com",
            "admin_email": f"test_welcome_fresh_{unique}@example.com",
            "admin_password": "TestFresh2026!",
            "admin_name": "Fresh Admin",
        }
        r = superadmin_session.post(f"{BASE_URL}/api/companies", json=payload)
        assert r.status_code == 200
        fresh_cid = r.json()["_id"]
        async def _run():
            from activation_task import run_once
            from db import db
            await run_once()
            admin = await db.users.find_one({"company_id": ObjectId(fresh_cid), "role": "admin"})
            assert "welcome_tips_sent_at" not in admin, "No debe enviar si days_old < 3"
            # cleanup
            await db.users.delete_many({"company_id": ObjectId(fresh_cid)})
            await db.companies.delete_one({"_id": ObjectId(fresh_cid)})
        run_async(_run())

    def test_99_cleanup(self):
        cid = TestWelcomeTipsTask._cid
        if not cid:
            return
        async def _cleanup():
            from db import db
            oid = ObjectId(cid)
            await db.users.delete_many({"company_id": oid})
            await db.companies.delete_one({"_id": oid})
        run_async(_cleanup())


# ============================================================
# Regresion: backfill de activation_task no desactiva opticas antiguas reales
# ============================================================
class TestBackfillSafety:
    def test_real_companies_still_active(self, superadmin_session):
        r = superadmin_session.get(f"{BASE_URL}/api/superadmin/retention")
        data = r.json()
        expired = data["segments"]["expired"]
        # No debe haber opticas reales (Altavista, Demo, Vision Clara) en expired
        real_names = ["Altavista Opticas", "Cortexia Optical Demo", "Óptica Visión Clara"]
        for c in expired:
            assert c["name"] not in real_names, (
                f"Optica real '{c['name']}' aparece en expired — bug de backfill regresado"
            )
