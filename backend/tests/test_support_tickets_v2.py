"""Tests for support-tickets v2 features: email queue, attachments, read-tracking, unread indicator."""
import os
import struct
import zlib
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


def _tiny_png(color=(255, 0, 0)):
    """Return a valid 1x1 PNG bytes (~69B)."""
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = b"\x00" + bytes(color)
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


@pytest.fixture(scope="module")
def sess():
    return {
        "superadmin": _make_session(SUPERADMIN),
        "admin": _make_session(ADMIN),
        "vendedor": _make_session(VENDEDOR),
    }


@pytest.fixture(scope="module")
def ticket_id(sess):
    """Ticket creado por admin con prefijo TEST_v2_."""
    r = sess["admin"].post(
        f"{BASE_URL}/api/support-tickets",
        json={
            "subject": "TEST_v2_attachments_and_read",
            "message": "ticket v2 para probar adjuntos y lectura",
            "category": "bug",
            "priority": "alta",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["_id"]


# ─── Email queue ────────────────────────────────────────────────────────────
class TestEmailQueue:
    def test_create_ticket_does_not_break_on_email(self, sess):
        """El endpoint de creación no debe fallar aunque falle el email (best-effort)."""
        r = sess["admin"].post(
            f"{BASE_URL}/api/support-tickets",
            json={"subject": "TEST_v2_email_smoke", "message": "smoke test email best-effort"},
        )
        assert r.status_code == 200
        assert "_id" in r.json()


# ─── Attachments ───────────────────────────────────────────────────────────
class TestAttachments:
    def test_upload_png_success(self, sess, ticket_id):
        png = _tiny_png()
        r = sess["admin"].post(
            f"{BASE_URL}/api/support-tickets/{ticket_id}/attachments",
            files={"file": ("shot.png", png, "image/png")},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "filename" in data and data["filename"].endswith(".png")
        assert "url" in data and ticket_id in data["url"]
        assert data["size"] == len(png)
        assert data["content_type"].startswith("image/")
        pytest.att_filename = data["filename"]

    def test_ticket_has_attachment_after_upload(self, sess, ticket_id):
        g = sess["admin"].get(f"{BASE_URL}/api/support-tickets/{ticket_id}")
        assert g.status_code == 200
        atts = g.json().get("attachments") or []
        assert len(atts) >= 1
        assert any(a.get("filename") == pytest.att_filename for a in atts)
        assert atts[0].get("storage_path", "").startswith("cortexia-optical/support/")

    def test_reject_non_image(self, sess, ticket_id):
        r = sess["admin"].post(
            f"{BASE_URL}/api/support-tickets/{ticket_id}/attachments",
            files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert r.status_code == 400, r.text

    def test_reject_too_large(self, sess, ticket_id):
        # 5MB + 1 byte
        big = b"\x00" * (5 * 1024 * 1024 + 1)
        r = sess["admin"].post(
            f"{BASE_URL}/api/support-tickets/{ticket_id}/attachments",
            files={"file": ("big.png", big, "image/png")},
        )
        assert r.status_code == 400, r.text

    def test_max_5_attachments(self, sess):
        # Crear un ticket dedicado para llenar hasta el máximo
        cr = sess["admin"].post(
            f"{BASE_URL}/api/support-tickets",
            json={"subject": "TEST_v2_max_attachments", "message": "prueba de limite adjuntos"},
        )
        tid = cr.json()["_id"]
        png = _tiny_png()
        # subir 5 OK
        for i in range(5):
            r = sess["admin"].post(
                f"{BASE_URL}/api/support-tickets/{tid}/attachments",
                files={"file": (f"s{i}.png", png, "image/png")},
            )
            assert r.status_code == 200, f"upload {i}: {r.text}"
        # 6th debe fallar
        r6 = sess["admin"].post(
            f"{BASE_URL}/api/support-tickets/{tid}/attachments",
            files={"file": ("s6.png", png, "image/png")},
        )
        assert r6.status_code == 400

    def test_download_returns_bytes(self, sess, ticket_id):
        r = sess["admin"].get(
            f"{BASE_URL}/api/support-tickets/{ticket_id}/attachments/{pytest.att_filename}"
        )
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/")
        assert len(r.content) > 50  # PNG mínimo

    def test_download_404_for_missing(self, sess, ticket_id):
        r = sess["admin"].get(
            f"{BASE_URL}/api/support-tickets/{ticket_id}/attachments/nope_nope.png"
        )
        assert r.status_code == 404

    def test_download_forbidden_for_other_user(self, sess, ticket_id):
        # vendedor no es owner (admin lo creó) ni superadmin
        r = sess["vendedor"].get(
            f"{BASE_URL}/api/support-tickets/{ticket_id}/attachments/{pytest.att_filename}"
        )
        assert r.status_code == 403

    def test_superadmin_can_download(self, sess, ticket_id):
        r = sess["superadmin"].get(
            f"{BASE_URL}/api/support-tickets/{ticket_id}/attachments/{pytest.att_filename}"
        )
        assert r.status_code == 200


# ─── Mark as read / Unread indicator ───────────────────────────────────────
class TestReadAndUnread:
    def test_creator_unread_false_after_create(self, sess):
        # Ticket recien creado: el creador ya "leyo" al crear (last_read_by_creator == created_at)
        cr = sess["admin"].post(
            f"{BASE_URL}/api/support-tickets",
            json={"subject": "TEST_v2_fresh_unread", "message": "verifica unread=false para el creador tras crear"},
        )
        tid = cr.json()["_id"]
        g = sess["admin"].get(f"{BASE_URL}/api/support-tickets/{tid}")
        assert g.status_code == 200
        assert not g.json().get("unread")

    def test_superadmin_unread_true_initially(self, sess, ticket_id):
        # Después del upload por admin, updated_at avanzó, superadmin no ha leído
        g = sess["superadmin"].get(f"{BASE_URL}/api/support-tickets/{ticket_id}")
        assert g.status_code == 200
        assert g.json().get("unread")

    def test_superadmin_mark_as_read(self, sess, ticket_id):
        r = sess["superadmin"].post(f"{BASE_URL}/api/support-tickets/{ticket_id}/read")
        assert r.status_code == 200
        assert "read_at" in r.json()

    def test_superadmin_unread_false_after_read(self, sess, ticket_id):
        g = sess["superadmin"].get(f"{BASE_URL}/api/support-tickets/{ticket_id}")
        assert not g.json().get("unread")

    def test_creator_reply_makes_super_unread_again(self, sess, ticket_id):
        rep = sess["admin"].post(
            f"{BASE_URL}/api/support-tickets/{ticket_id}/reply",
            json={"message": "seguimiento del creador"},
        )
        assert rep.status_code == 200
        g = sess["superadmin"].get(f"{BASE_URL}/api/support-tickets/{ticket_id}")
        assert g.json().get("unread")

    def test_reply_updates_own_read_marker(self, sess, ticket_id):
        # El propio creador no se debe ver a si mismo como unread despues de responder
        g = sess["admin"].get(f"{BASE_URL}/api/support-tickets/{ticket_id}")
        assert not g.json().get("unread")

    def test_read_forbidden_for_third_user(self, sess, ticket_id):
        r = sess["vendedor"].post(f"{BASE_URL}/api/support-tickets/{ticket_id}/read")
        assert r.status_code == 403

    def test_read_404_for_missing(self, sess):
        fake = "507f1f77bcf86cd799439099"
        r = sess["superadmin"].post(f"{BASE_URL}/api/support-tickets/{fake}/read")
        assert r.status_code == 404


# ─── List/Stats include unread + attachment_count ──────────────────────────
class TestListAndStatsFields:
    def test_list_has_unread_and_attachment_count(self, sess, ticket_id):
        r = sess["admin"].get(f"{BASE_URL}/api/support-tickets")
        assert r.status_code == 200
        items = r.json()
        target = next((t for t in items if t["_id"] == ticket_id), None)
        assert target is not None
        assert "unread" in target and isinstance(target["unread"], bool)
        assert "attachment_count" in target and isinstance(target["attachment_count"], int)
        assert target["attachment_count"] >= 1

    def test_stats_includes_unread(self, sess):
        r = sess["superadmin"].get(f"{BASE_URL}/api/support-tickets/stats/summary")
        assert r.status_code == 200
        data = r.json()
        assert "unread" in data
        assert isinstance(data["unread"], int)
        assert data["unread"] >= 0
