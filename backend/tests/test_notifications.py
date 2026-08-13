"""Tests for SuperAdmin Notifications system (Iteration 19)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://eyecare-erp.preview.emergentagent.com").rstrip("/")

SUPERADMIN = {"email": "superadmin@cortexia.com", "password": "Admin123!"}
ADMIN = {"email": "analuhs@gmail.com", "password": os.getenv("TEST_ENTERPRISE_ADMIN_PASSWORD","")}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def super_client():
    return _login(SUPERADMIN)


@pytest.fixture(scope="module")
def admin_client():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def anon_client():
    return requests.Session()


# === GET /api/notifications ===
class TestListNotifications:
    def test_list_as_superadmin(self, super_client):
        r = super_client.get(f"{BASE_URL}/api/notifications")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            n = data[0]
            for k in ("_id", "event_type", "title", "message", "is_read", "created_at"):
                assert k in n, f"missing key {k} in {n}"
            assert isinstance(n["_id"], str)
            # ObjectId should be serialized to string (not contain $oid)
            assert "$oid" not in str(n["_id"])

    def test_list_sorted_desc_by_created_at(self, super_client):
        r = super_client.get(f"{BASE_URL}/api/notifications")
        assert r.status_code == 200
        data = r.json()
        if len(data) >= 2:
            for i in range(len(data) - 1):
                assert data[i]["created_at"] >= data[i + 1]["created_at"]

    def test_list_limit_param(self, super_client):
        r = super_client.get(f"{BASE_URL}/api/notifications?limit=5")
        assert r.status_code == 200
        assert len(r.json()) <= 5

    def test_list_forbidden_for_admin(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/notifications")
        assert r.status_code == 403

    def test_list_unauth(self, anon_client):
        r = anon_client.get(f"{BASE_URL}/api/notifications")
        assert r.status_code in (401, 403)


# === GET /api/notifications/unread-count ===
class TestUnreadCount:
    def test_count_as_superadmin(self, super_client):
        r = super_client.get(f"{BASE_URL}/api/notifications/unread-count")
        assert r.status_code == 200
        data = r.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0

    def test_count_for_admin_returns_zero(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/notifications/unread-count")
        assert r.status_code == 200
        assert r.json().get("count") == 0

    def test_count_unauth(self, anon_client):
        r = anon_client.get(f"{BASE_URL}/api/notifications/unread-count")
        assert r.status_code in (401, 403)


# === PUT /api/notifications/{id}/read & read-all ===
class TestMarkAsRead:
    def test_mark_single_as_read_and_verify(self, super_client):
        # First make sure at least one unread exists - trigger via plan_change is heavy;
        # instead pick any existing notification and mark it.
        lst = super_client.get(f"{BASE_URL}/api/notifications").json()
        if not lst:
            pytest.skip("No notifications in DB to mark as read")
        target = lst[0]
        nid = target["_id"]
        r = super_client.put(f"{BASE_URL}/api/notifications/{nid}/read")
        assert r.status_code == 200
        # Verify by re-fetching
        lst2 = super_client.get(f"{BASE_URL}/api/notifications").json()
        match = next((n for n in lst2 if n["_id"] == nid), None)
        assert match is not None
        assert match["is_read"] is True

    def test_mark_as_read_forbidden_for_admin(self, admin_client, super_client):
        lst = super_client.get(f"{BASE_URL}/api/notifications").json()
        if not lst:
            pytest.skip("No notifications")
        r = admin_client.put(f"{BASE_URL}/api/notifications/{lst[0]['_id']}/read")
        assert r.status_code == 403

    def test_mark_all_as_read_and_count_zero(self, super_client):
        r = super_client.put(f"{BASE_URL}/api/notifications/read-all")
        assert r.status_code == 200
        cnt = super_client.get(f"{BASE_URL}/api/notifications/unread-count").json()["count"]
        assert cnt == 0
        # verify all docs in list are is_read True
        lst = super_client.get(f"{BASE_URL}/api/notifications").json()
        for n in lst:
            assert n["is_read"] is True

    def test_mark_all_as_read_forbidden_admin(self, admin_client):
        r = admin_client.put(f"{BASE_URL}/api/notifications/read-all")
        assert r.status_code == 403


# === Auto-trigger via plan change ===
class TestPlanChangeTriggersNotification:
    def test_plan_change_creates_notification(self, super_client):
        # Get baseline count
        before_list = super_client.get(f"{BASE_URL}/api/notifications").json()
        before_plan_change = sum(1 for n in before_list if n.get("event_type") == "plan_change")

        # Find a company + 2 plans
        companies = super_client.get(f"{BASE_URL}/api/companies").json()
        plans = super_client.get(f"{BASE_URL}/api/plans").json()
        if not companies or len(plans) < 2:
            pytest.skip("Need >=1 company and >=2 plans")
        # pick a non-test company if possible
        company = next((c for c in companies if not c["name"].startswith("TEST_")), companies[0])
        cid = company["_id"]
        current_plan_id = company.get("plan_id")
        target_plan = next((p for p in plans if p["_id"] != current_plan_id), plans[0])

        r = super_client.put(f"{BASE_URL}/api/plans/assign/{cid}?plan_id={target_plan['_id']}")
        assert r.status_code == 200, f"assign failed: {r.text}"

        # Re-fetch notifications - should have +1 plan_change
        after_list = super_client.get(f"{BASE_URL}/api/notifications").json()
        after_plan_change = sum(1 for n in after_list if n.get("event_type") == "plan_change")
        assert after_plan_change == before_plan_change + 1, (
            f"plan_change count did not increase: before={before_plan_change} after={after_plan_change}"
        )

        # The newest notification should be plan_change and unread
        newest = after_list[0]
        assert newest["event_type"] == "plan_change"
        assert newest["is_read"] is False
        assert company["name"] in newest["message"] or company["name"] in newest.get("title", "")
        assert "metadata" in newest
        assert newest["metadata"].get("new_plan") == target_plan["name"]
