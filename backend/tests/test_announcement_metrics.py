"""Tests for the Announcement Metrics feature (track + metrics endpoints).

Covers:
- POST /api/announcements/{id}/track?action=view  -> records a view (unique per company)
- POST /api/announcements/{id}/track?action=dismiss -> records a dismiss
- Deduplication: calling view twice for same company only stores 1 entry
- GET /api/announcements/{id}/metrics -> views/dismissals counts + details (SuperAdmin only)
- GET /api/announcements list includes views_count and dismissals_count per announcement
- Authorization: admin cannot read metrics; track requires authenticated user
- Action validation: invalid action returns 400
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://eyecare-erp.preview.emergentagent.com').rstrip('/')

SUPERADMIN = {"email": "superadmin@cortexia.com", "password": "Admin123!"}
ADMIN_ENTERPRISE = {"email": "analuhs@gmail.com", "password": os.getenv("TEST_ENTERPRISE_ADMIN_PASSWORD","")}
ADMIN_FREE = {"email": "admin@cortexia.gt", "password": os.getenv("TEST_ADMIN_PASSWORD") or os.getenv("DEMO_PASSWORD","")}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def super_session():
    return _login(SUPERADMIN)


@pytest.fixture(scope="module")
def enterprise_session():
    return _login(ADMIN_ENTERPRISE)


@pytest.fixture(scope="module")
def free_session():
    return _login(ADMIN_FREE)


@pytest.fixture
def fresh_announcement(super_session):
    """Create a fresh announcement targeting all plans, yield its id, then delete it."""
    payload = {
        "title": "TEST_Metrics_Announcement",
        "message": "Test metrics tracking",
        "type": "info",
        "target_plans": [],   # all plans
        "target_cities": [],  # all cities
        "start_date": "2026-01-01",
        "end_date": "2030-12-31"
    }
    r = super_session.post(f"{BASE_URL}/api/announcements", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    aid = r.json()["_id"]
    yield aid
    # cleanup (also removes related metrics)
    super_session.delete(f"{BASE_URL}/api/announcements/{aid}")


# ---------- TRACK endpoint ----------
class TestTrack:
    def test_track_view_records_metric(self, fresh_announcement, enterprise_session, super_session):
        r = enterprise_session.post(f"{BASE_URL}/api/announcements/{fresh_announcement}/track?action=view", timeout=20)
        assert r.status_code == 200, r.text
        # Verify via metrics endpoint
        m = super_session.get(f"{BASE_URL}/api/announcements/{fresh_announcement}/metrics").json()
        assert m["views_count"] == 1
        assert m["dismissals_count"] == 0
        assert len(m["view_details"]) == 1
        v = m["view_details"][0]
        # Altavista should be Enterprise admin company; just assert it's non-empty
        assert isinstance(v.get("company_name"), str) and v["company_name"] != ""
        assert isinstance(v.get("user_name"), str)
        assert isinstance(v.get("date"), str) and len(v["date"]) == 10  # YYYY-MM-DD

    def test_track_dismiss_records_metric(self, fresh_announcement, enterprise_session, super_session):
        r = enterprise_session.post(f"{BASE_URL}/api/announcements/{fresh_announcement}/track?action=dismiss", timeout=20)
        assert r.status_code == 200, r.text
        m = super_session.get(f"{BASE_URL}/api/announcements/{fresh_announcement}/metrics").json()
        assert m["dismissals_count"] == 1
        assert len(m["dismiss_details"]) == 1
        d = m["dismiss_details"][0]
        assert d["company_name"] != ""

    def test_track_view_deduplicates_same_company(self, fresh_announcement, enterprise_session, super_session):
        # Call view 3 times from same session/company
        for _ in range(3):
            r = enterprise_session.post(f"{BASE_URL}/api/announcements/{fresh_announcement}/track?action=view", timeout=20)
            assert r.status_code == 200
        m = super_session.get(f"{BASE_URL}/api/announcements/{fresh_announcement}/metrics").json()
        assert m["views_count"] == 1, f"deduplication failed - got {m['views_count']} views"

    def test_track_two_companies_two_views(self, fresh_announcement, enterprise_session, free_session, super_session):
        # Enterprise + Free admins each view once -> 2 unique views
        r1 = enterprise_session.post(f"{BASE_URL}/api/announcements/{fresh_announcement}/track?action=view")
        r2 = free_session.post(f"{BASE_URL}/api/announcements/{fresh_announcement}/track?action=view")
        assert r1.status_code == 200 and r2.status_code == 200
        m = super_session.get(f"{BASE_URL}/api/announcements/{fresh_announcement}/metrics").json()
        assert m["views_count"] == 2
        company_names = sorted([v["company_name"] for v in m["view_details"]])
        assert len(set(company_names)) == 2

    def test_track_view_and_dismiss_independent(self, fresh_announcement, enterprise_session, super_session):
        # view + dismiss from same company should both be recorded (different actions)
        enterprise_session.post(f"{BASE_URL}/api/announcements/{fresh_announcement}/track?action=view")
        enterprise_session.post(f"{BASE_URL}/api/announcements/{fresh_announcement}/track?action=dismiss")
        m = super_session.get(f"{BASE_URL}/api/announcements/{fresh_announcement}/metrics").json()
        assert m["views_count"] == 1
        assert m["dismissals_count"] == 1

    def test_track_invalid_action_returns_400(self, fresh_announcement, enterprise_session):
        r = enterprise_session.post(f"{BASE_URL}/api/announcements/{fresh_announcement}/track?action=clicked", timeout=20)
        assert r.status_code == 400

    def test_track_invalid_announcement_id_returns_400(self, enterprise_session):
        r = enterprise_session.post(f"{BASE_URL}/api/announcements/not-valid-id/track?action=view", timeout=20)
        assert r.status_code == 400

    def test_track_unauthenticated(self, fresh_announcement):
        r = requests.post(f"{BASE_URL}/api/announcements/{fresh_announcement}/track?action=view", timeout=20)
        assert r.status_code in (401, 403)


# ---------- METRICS endpoint ----------
class TestMetrics:
    def test_metrics_superadmin_zero_counts_new_announcement(self, fresh_announcement, super_session):
        m = super_session.get(f"{BASE_URL}/api/announcements/{fresh_announcement}/metrics").json()
        assert m["views_count"] == 0
        assert m["dismissals_count"] == 0
        assert m["view_details"] == []
        assert m["dismiss_details"] == []

    def test_metrics_schema(self, fresh_announcement, enterprise_session, super_session):
        enterprise_session.post(f"{BASE_URL}/api/announcements/{fresh_announcement}/track?action=view")
        r = super_session.get(f"{BASE_URL}/api/announcements/{fresh_announcement}/metrics", timeout=20)
        assert r.status_code == 200
        m = r.json()
        # Required keys
        for key in ("views_count", "dismissals_count", "view_details", "dismiss_details"):
            assert key in m, f"missing key: {key}"
        assert isinstance(m["views_count"], int)
        assert isinstance(m["dismissals_count"], int)
        assert isinstance(m["view_details"], list)
        assert isinstance(m["dismiss_details"], list)
        # Each detail row must have company_name, user_name, date
        for row in m["view_details"]:
            assert "company_name" in row
            assert "user_name" in row
            assert "date" in row

    def test_metrics_forbidden_for_admin(self, fresh_announcement, enterprise_session):
        r = enterprise_session.get(f"{BASE_URL}/api/announcements/{fresh_announcement}/metrics", timeout=20)
        assert r.status_code == 403

    def test_metrics_invalid_id_returns_400(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/announcements/not-valid-id/metrics", timeout=20)
        assert r.status_code == 400

    def test_metrics_unauthenticated(self, fresh_announcement):
        r = requests.get(f"{BASE_URL}/api/announcements/{fresh_announcement}/metrics", timeout=20)
        assert r.status_code in (401, 403)


# ---------- LIST includes counts ----------
class TestListIncludesCounts:
    def test_list_has_counts_fields(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/announcements", timeout=20)
        assert r.status_code == 200
        data = r.json()
        for a in data:
            assert "views_count" in a, f"announcement {a.get('_id')} missing views_count"
            assert "dismissals_count" in a, f"announcement {a.get('_id')} missing dismissals_count"
            assert isinstance(a["views_count"], int)
            assert isinstance(a["dismissals_count"], int)

    def test_list_counts_reflect_tracked_metrics(self, fresh_announcement, enterprise_session, free_session, super_session):
        # Track 2 views, 1 dismiss
        enterprise_session.post(f"{BASE_URL}/api/announcements/{fresh_announcement}/track?action=view")
        free_session.post(f"{BASE_URL}/api/announcements/{fresh_announcement}/track?action=view")
        enterprise_session.post(f"{BASE_URL}/api/announcements/{fresh_announcement}/track?action=dismiss")
        # Verify via list
        listed = super_session.get(f"{BASE_URL}/api/announcements").json()
        target = next((a for a in listed if a["_id"] == fresh_announcement), None)
        assert target is not None
        assert target["views_count"] == 2
        assert target["dismissals_count"] == 1
