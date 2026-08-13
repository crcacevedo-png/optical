"""
Tests for GET /api/appointments/reminders endpoint (WhatsApp reminders).

Verifies:
- Returns {date, count, items[]} with patient_name, patient_phone, whatsapp_url, reminder_message
- 502 prefix for 8-digit Guatemala phones
- Excludes cancelada/completada/no_asistio
- Superadmin rejected with 403
- days_ahead out of [0,30] -> 400
- when_word 'hoy' vs 'manana'
- Multi-tenant isolation (implicit via company_id filter)
"""
import os
import pytest
import requests
from datetime import datetime, timedelta, date

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

ADMIN_EMAIL = "admin@cortexia.gt"
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD","")
SUPERADMIN_EMAIL = "superadmin@cortexia.com"
SUPERADMIN_PASSWORD = os.getenv("TEST_SUPERADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD","")


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    yield s
    s.post(f"{BASE_URL}/api/auth/logout")


@pytest.fixture(scope="module")
def superadmin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": SUPERADMIN_EMAIL, "password": SUPERADMIN_PASSWORD})
    assert r.status_code == 200, f"Superadmin login failed: {r.text}"
    yield s
    s.post(f"{BASE_URL}/api/auth/logout")


@pytest.fixture(scope="module")
def seed_patient_and_appts(admin_session):
    """Create a TEST patient with 8-digit phone + appointments for tomorrow (various statuses)."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    today = date.today().isoformat()

    # Create patient with 8-digit phone (Guatemala) via whatsapp field
    p_payload = {
        "first_name": "TESTReminder",
        "last_name": "Paciente",
        "phone": "55551234",       # 8 digits
        "whatsapp": "55551234",    # 8 digits -> should get 502 prefix
        "email": "test_reminder@example.com",
    }
    pr = admin_session.post(f"{BASE_URL}/api/patients", json=p_payload)
    assert pr.status_code in (200, 201), f"Create patient failed: {pr.status_code} {pr.text}"
    pid = pr.json().get("_id") or pr.json().get("id")
    assert pid, f"No patient id in response: {pr.json()}"

    created_ids = []

    def _create(date_str, time, status=None, ptype="consulta"):
        body = {
            "patient_id": pid,
            "date": date_str,
            "time": time,
            "duration": 30,
            "type": ptype,
            "notes": "TEST_reminder",
        }
        if status:
            body["status"] = status
        r = admin_session.post(f"{BASE_URL}/api/appointments", json=body)
        assert r.status_code == 200, f"Create appt failed: {r.text}"
        aid = r.json()["_id"]
        created_ids.append(aid)
        if status and status != "pendiente":
            # PUT to force status if not pendiente (POST default is pendiente)
            admin_session.put(f"{BASE_URL}/api/appointments/{aid}", json={"status": status})
        return aid

    pending_id = _create(tomorrow, "09:00")            # should appear
    confirmed_id = _create(tomorrow, "10:00", "confirmada")  # should appear
    cancelled_id = _create(tomorrow, "11:00", "cancelada")   # excluded
    completed_id = _create(tomorrow, "12:00", "completada")  # excluded
    noshow_id = _create(tomorrow, "13:00", "no_asistio")     # excluded
    today_id = _create(today, "14:00")                       # for hoy test

    yield {
        "patient_id": pid,
        "tomorrow": tomorrow,
        "today": today,
        "pending_id": pending_id,
        "confirmed_id": confirmed_id,
        "cancelled_id": cancelled_id,
        "completed_id": completed_id,
        "noshow_id": noshow_id,
        "today_id": today_id,
    }

    # cleanup
    for aid in created_ids:
        try:
            admin_session.delete(f"{BASE_URL}/api/appointments/{aid}")
        except Exception:
            pass


class TestRemindersEndpoint:
    def test_reminders_tomorrow_structure(self, admin_session, seed_patient_and_appts):
        r = admin_session.get(f"{BASE_URL}/api/appointments/reminders", params={"days_ahead": 1})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "date" in data and "count" in data and "items" in data
        assert data["date"] == seed_patient_and_appts["tomorrow"]
        assert isinstance(data["items"], list)
        assert data["count"] == len(data["items"])

    def test_reminders_excludes_cancelled_completed_noshow(self, admin_session, seed_patient_and_appts):
        r = admin_session.get(f"{BASE_URL}/api/appointments/reminders", params={"days_ahead": 1})
        assert r.status_code == 200
        items = r.json()["items"]
        seed = seed_patient_and_appts
        ids = {it.get("_id") or it.get("id") for it in items}
        assert seed["cancelled_id"] not in ids
        assert seed["completed_id"] not in ids
        assert seed["noshow_id"] not in ids
        # Our 2 valid ones should be present
        assert seed["pending_id"] in ids
        assert seed["confirmed_id"] in ids

    def test_reminders_item_fields_and_502_prefix(self, admin_session, seed_patient_and_appts):
        r = admin_session.get(f"{BASE_URL}/api/appointments/reminders", params={"days_ahead": 1})
        assert r.status_code == 200
        items = r.json()["items"]
        seed = seed_patient_and_appts
        our = [it for it in items if (it.get("_id") or it.get("id")) == seed["pending_id"]]
        assert our, "Seeded pending appt not found in reminders items"
        it = our[0]
        assert "patient_name" in it and it["patient_name"].startswith("TESTReminder")
        assert "patient_phone" in it
        assert "reminder_message" in it and "manana" in it["reminder_message"]
        assert "whatsapp_url" in it and it["whatsapp_url"]
        # 502 prefix expected because whatsapp field has 8 digits
        assert "wa.me/50255551234" in it["whatsapp_url"], f"Unexpected whatsapp_url: {it['whatsapp_url']}"

    def test_reminders_today_word(self, admin_session, seed_patient_and_appts):
        r = admin_session.get(f"{BASE_URL}/api/appointments/reminders", params={"days_ahead": 0})
        assert r.status_code == 200
        data = r.json()
        assert data["date"] == seed_patient_and_appts["today"]
        # At least our today appointment should carry when_word 'hoy'
        matching = [it for it in data["items"] if (it.get("_id") or it.get("id")) == seed_patient_and_appts["today_id"]]
        assert matching, "Today appointment not found"
        assert "hoy" in matching[0]["reminder_message"]

    def test_reminders_days_ahead_out_of_range_negative(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/appointments/reminders", params={"days_ahead": -1})
        assert r.status_code == 400

    def test_reminders_days_ahead_out_of_range_too_big(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/appointments/reminders", params={"days_ahead": 31})
        assert r.status_code == 400

    def test_reminders_superadmin_forbidden(self, superadmin_session):
        r = superadmin_session.get(f"{BASE_URL}/api/appointments/reminders", params={"days_ahead": 1})
        assert r.status_code == 403

    def test_reminders_unauth(self):
        r = requests.get(f"{BASE_URL}/api/appointments/reminders", params={"days_ahead": 1})
        assert r.status_code == 401
