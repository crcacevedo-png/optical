"""Tests for support tickets system + regression on core endpoints."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")

SUPERADMIN = {"email": "superadmin@cortexia.com", "password": os.getenv("TEST_SUPERADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD","")}
ADMIN = {"email": "admin@cortexia.gt", "password": os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD","")}
VENDEDOR = {"email": "vendedor@cortexia.gt", "password": os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD","")}


def _make_session(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"Login failed for {creds['email']}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def tokens():
    return {
        "superadmin": _make_session(SUPERADMIN),
        "admin": _make_session(ADMIN),
        "vendedor": _make_session(VENDEDOR),
    }


def _h(sess):
    # Backward-compat helper: returns the session; caller uses .get/.post directly
    return sess


# ---------- CREATE ----------
class TestCreateTicket:
    def test_admin_can_create(self, tokens):
        payload = {
            "subject": "TEST_ticket_admin",
            "message": "Mensaje inicial de prueba",
            "category": "consulta",
            "priority": "media",
        }
        r = tokens["admin"].post(f"{BASE_URL}/api/support-tickets", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "_id" in data
        pytest.admin_ticket_id = data["_id"]

    def test_vendedor_can_create(self, tokens):
        payload = {
            "subject": "TEST_ticket_vendedor",
            "message": "Mensaje del vendedor para prueba",
            "category": "bug",
            "priority": "alta",
        }
        r = tokens["vendedor"].post(f"{BASE_URL}/api/support-tickets", json=payload)
        assert r.status_code == 200, r.text
        pytest.vendedor_ticket_id = r.json()["_id"]

    def test_superadmin_cannot_create(self, tokens):
        payload = {"subject": "TEST_ticket_sa", "message": "no debe funcionar"}
        r = tokens["superadmin"].post(f"{BASE_URL}/api/support-tickets", json=payload)
        assert r.status_code == 403

    def test_validation_short_subject(self, tokens):
        r = tokens["admin"].post(
            f"{BASE_URL}/api/support-tickets",
            json={"subject": "ab", "message": "mensaje valido aqui"},
        )
        assert r.status_code == 422

    def test_validation_short_message(self, tokens):
        r = tokens["admin"].post(
            f"{BASE_URL}/api/support-tickets",
            json={"subject": "subject ok", "message": "hi"},
        )
        assert r.status_code == 422


# ---------- LIST ----------
class TestListTickets:
    def test_vendedor_sees_only_own(self, tokens):
        r = tokens["vendedor"].get(f"{BASE_URL}/api/support-tickets")
        assert r.status_code == 200
        tickets = r.json()
        assert isinstance(tickets, list)
        # vendedor_ticket must be in list
        ids = [t["_id"] for t in tickets]
        assert pytest.vendedor_ticket_id in ids
        # admin_ticket must NOT be visible
        assert pytest.admin_ticket_id not in ids

    def test_superadmin_sees_all_with_company_name(self, tokens):
        r = tokens["superadmin"].get(f"{BASE_URL}/api/support-tickets")
        assert r.status_code == 200
        tickets = r.json()
        ids = [t["_id"] for t in tickets]
        assert pytest.vendedor_ticket_id in ids
        assert pytest.admin_ticket_id in ids
        for t in tickets:
            assert "company_name" in t

    def test_filter_status(self, tokens):
        r = tokens["superadmin"].get(f"{BASE_URL}/api/support-tickets?status=abierto")
        assert r.status_code == 200
        for t in r.json():
            assert t["status"] == "abierto"

    def test_filter_priority(self, tokens):
        r = tokens["superadmin"].get(f"{BASE_URL}/api/support-tickets?priority=alta")
        assert r.status_code == 200
        for t in r.json():
            assert t["priority"] == "alta"

    def test_filter_category(self, tokens):
        r = tokens["superadmin"].get(f"{BASE_URL}/api/support-tickets?category=bug")
        assert r.status_code == 200
        for t in r.json():
            assert t["category"] == "bug"

    def test_filter_invalid_status(self, tokens):
        r = tokens["superadmin"].get(f"{BASE_URL}/api/support-tickets?status=invalid")
        assert r.status_code == 422


# ---------- DETAIL ----------
class TestGetTicket:
    def test_creator_can_view(self, tokens):
        r = tokens["admin"].get(f"{BASE_URL}/api/support-tickets/{pytest.admin_ticket_id}")
        assert r.status_code == 200
        data = r.json()
        assert "messages" in data
        assert len(data["messages"]) >= 1

    def test_superadmin_can_view(self, tokens):
        r = tokens["superadmin"].get(f"{BASE_URL}/api/support-tickets/{pytest.admin_ticket_id}")
        assert r.status_code == 200

    def test_other_user_forbidden(self, tokens):
        # vendedor tries to view admin's ticket
        r = tokens["vendedor"].get(f"{BASE_URL}/api/support-tickets/{pytest.admin_ticket_id}")
        assert r.status_code == 403

    def test_not_found(self, tokens):
        fake = "507f1f77bcf86cd799439011"
        r = tokens["superadmin"].get(f"{BASE_URL}/api/support-tickets/{fake}")
        assert r.status_code == 404

    def test_invalid_id(self, tokens):
        r = tokens["superadmin"].get(f"{BASE_URL}/api/support-tickets/not-an-oid")
        assert r.status_code == 400


# ---------- REPLY ----------
class TestReplyTicket:
    def test_third_user_forbidden(self, tokens):
        r = tokens["vendedor"].post(
            f"{BASE_URL}/api/support-tickets/{pytest.admin_ticket_id}/reply",
            json={"message": "intruso"},
        )
        assert r.status_code == 403

    def test_creator_can_reply(self, tokens):
        r = tokens["admin"].post(
            f"{BASE_URL}/api/support-tickets/{pytest.admin_ticket_id}/reply",
            json={"message": "respuesta del creador"},
        )
        assert r.status_code == 200

    def test_superadmin_reply_transitions_to_en_progreso(self, tokens):
        # admin_ticket is still 'abierto'. superadmin replies -> should become en_progreso
        r = tokens["superadmin"].post(
            f"{BASE_URL}/api/support-tickets/{pytest.admin_ticket_id}/reply",
            json={"message": "Hola, estamos revisando"},
        )
        assert r.status_code == 200
        # verify status changed
        g = tokens["superadmin"].get(f"{BASE_URL}/api/support-tickets/{pytest.admin_ticket_id}")
        assert g.status_code == 200
        assert g.json()["status"] == "en_progreso"

    def test_cannot_reply_when_closed(self, tokens):
        # Create fresh ticket, superadmin closes, then try to reply
        cr = tokens["admin"].post(
            f"{BASE_URL}/api/support-tickets",
            json={"subject": "TEST_will_close", "message": "prueba cierre de ticket"},
        )
        tid = cr.json()["_id"]
        s = tokens["superadmin"].patch(
            f"{BASE_URL}/api/support-tickets/{tid}/status",
            json={"status": "cerrado"},
        )
        assert s.status_code == 200
        r = tokens["admin"].post(
            f"{BASE_URL}/api/support-tickets/{tid}/reply",
            json={"message": "intento tras cierre"},
        )
        assert r.status_code == 400


# ---------- STATUS ----------
class TestStatusUpdate:
    def test_superadmin_can_change_any(self, tokens):
        r = tokens["superadmin"].patch(
            f"{BASE_URL}/api/support-tickets/{pytest.vendedor_ticket_id}/status",
            json={"status": "resuelto"},
        )
        assert r.status_code == 200

    def test_creator_can_only_close(self, tokens):
        # Create new ticket by vendedor, try to change to en_progreso (should fail), then close (should succeed)
        cr = tokens["vendedor"].post(
            f"{BASE_URL}/api/support-tickets",
            json={"subject": "TEST_creator_status", "message": "prueba estado de creador"},
        )
        tid = cr.json()["_id"]
        r_bad = tokens["vendedor"].patch(
            f"{BASE_URL}/api/support-tickets/{tid}/status",
            json={"status": "en_progreso"},
        )
        assert r_bad.status_code == 403
        r_ok = tokens["vendedor"].patch(
            f"{BASE_URL}/api/support-tickets/{tid}/status",
            json={"status": "cerrado"},
        )
        assert r_ok.status_code == 200

    def test_other_user_forbidden(self, tokens):
        r = tokens["vendedor"].patch(
            f"{BASE_URL}/api/support-tickets/{pytest.admin_ticket_id}/status",
            json={"status": "cerrado"},
        )
        assert r.status_code == 403


# ---------- STATS ----------
class TestStats:
    def test_superadmin_stats_global(self, tokens):
        r = tokens["superadmin"].get(f"{BASE_URL}/api/support-tickets/stats/summary")
        assert r.status_code == 200
        data = r.json()
        for k in ["open", "in_progress", "resolved", "closed", "total"]:
            assert k in data
            assert isinstance(data[k], int)
        assert data["total"] == data["open"] + data["in_progress"] + data["resolved"] + data["closed"]
        assert data["total"] >= 1

    def test_admin_stats_only_own(self, tokens):
        r_admin = tokens["admin"].get(f"{BASE_URL}/api/support-tickets/stats/summary")
        r_super = tokens["superadmin"].get(f"{BASE_URL}/api/support-tickets/stats/summary")
        assert r_admin.status_code == 200
        assert r_super.status_code == 200
        # admin total must be <= superadmin total
        assert r_admin.json()["total"] <= r_super.json()["total"]


# ---------- NOTIFICATION ----------
class TestNotificationCreated:
    def test_notification_exists_for_superadmin(self, tokens):
        r = tokens["superadmin"].get(f"{BASE_URL}/api/notifications")
        assert r.status_code == 200, r.text
        notifs = r.json()
        # Accept either list or dict wrapping
        items = notifs if isinstance(notifs, list) else notifs.get("items") or notifs.get("notifications") or []
        event_types = [n.get("event_type") for n in items]
        assert "SUPPORT_TICKET_CREATED" in event_types, f"No SUPPORT_TICKET_CREATED found. Events: {event_types[:10]}"


# ---------- REGRESSION ----------
class TestRegression:
    def test_login(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json=SUPERADMIN)
        assert r.status_code == 200

    def test_patients(self, tokens):
        r = tokens["admin"].get(f"{BASE_URL}/api/patients")
        assert r.status_code == 200

    def test_sales(self, tokens):
        r = tokens["admin"].get(f"{BASE_URL}/api/sales")
        assert r.status_code == 200

    def test_inventory_products(self, tokens):
        r = tokens["admin"].get(f"{BASE_URL}/api/inventory/products")
        assert r.status_code == 200
