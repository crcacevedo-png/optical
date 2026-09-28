"""Tests para 'Control de Cobros y Suspensión por Impago' (Fase 1 MVP).

Cubre:
- GET /api/billing/admin/collections (superadmin 200 / admin 403)
- GET /api/billing/account-status (admin 200 con campos)
- Muro de pago: sembrando billing_state='suspended' en la company demo,
  al pegarle a /api/patients y /api/finance devuelve 402, mientras
  /api/billing/account-status y /api/plans devuelven 200.

Al final RESTAURA la empresa demo a activo (unset de campos de billing).
"""
import os
import asyncio
import pytest
import requests
from bson import ObjectId
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://eyecare-erp.preview.emergentagent.com").rstrip("/")
COMPANY_ID = "69cac742cf7c7911e1282501"

from _credentials import ADMIN_EMAIL, ADMIN_PASSWORD, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD  # noqa: E402


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text[:200]}"
    csrf = s.cookies.get("csrf_token")
    if csrf:
        s.headers.update({"X-CSRF-Token": csrf})
    return s, r.json()


async def _set_state(state: str | None):
    from db import db
    if state is None:
        await db.companies.update_one(
            {"_id": ObjectId(COMPANY_ID)},
            {"$unset": {"billing_state": "", "suspended_at": "", "suspended_reason": "",
                        "grace_until": "", "payment_failed_at": "", "last_dunning_stage": "",
                        "subscription_status": ""}},
        )
    elif state == "suspended":
        now = datetime.now(timezone.utc).isoformat()
        await db.companies.update_one(
            {"_id": ObjectId(COMPANY_ID)},
            {"$set": {"billing_state": "suspended", "suspended_at": now,
                      "suspended_reason": "payment_failed", "subscription_status": "unpaid"}},
        )
    elif state == "grace":
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        await db.companies.update_one(
            {"_id": ObjectId(COMPANY_ID)},
            {"$set": {"billing_state": "grace",
                      "payment_failed_at": now.isoformat(),
                      "grace_until": (now + timedelta(days=2)).isoformat(),
                      "subscription_status": "past_due",
                      "last_dunning_stage": 0}},
        )


def set_state(state):
    # Use pymongo directly to avoid motor + event-loop issues in pytest
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    client = MongoClient(mongo_url)
    cdb = client[db_name]
    from datetime import timedelta
    if state is None:
        cdb.companies.update_one(
            {"_id": ObjectId(COMPANY_ID)},
            {"$unset": {"billing_state": "", "suspended_at": "", "suspended_reason": "",
                        "grace_until": "", "payment_failed_at": "", "last_dunning_stage": "",
                        "subscription_status": ""}},
        )
    elif state == "suspended":
        now = datetime.now(timezone.utc).isoformat()
        cdb.companies.update_one(
            {"_id": ObjectId(COMPANY_ID)},
            {"$set": {"billing_state": "suspended", "suspended_at": now,
                      "suspended_reason": "payment_failed", "subscription_status": "unpaid"}},
        )
    elif state == "grace":
        now = datetime.now(timezone.utc)
        cdb.companies.update_one(
            {"_id": ObjectId(COMPANY_ID)},
            {"$set": {"billing_state": "grace",
                      "payment_failed_at": now.isoformat(),
                      "grace_until": (now + timedelta(days=2)).isoformat(),
                      "subscription_status": "past_due",
                      "last_dunning_stage": 0}},
        )
    client.close()


# --- collections panel (superadmin) ---

def test_admin_collections_as_superadmin_returns_full_shape():
    s, _ = _login(SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)
    r = s.get(f"{BASE_URL}/api/billing/admin/collections", timeout=30)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    for key in ("kpis", "grace", "suspended", "upcoming", "mismatches"):
        assert key in data, f"missing top-level key {key}"
    for k in ("upcoming_renewals", "in_grace", "suspended", "amount_mismatches", "mrr_at_risk"):
        assert k in data["kpis"], f"missing kpi {k}"
    for k in ("grace", "suspended", "upcoming", "mismatches"):
        assert isinstance(data[k], list)


def test_admin_collections_as_admin_returns_403():
    s, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    r = s.get(f"{BASE_URL}/api/billing/admin/collections", timeout=30)
    assert r.status_code == 403, r.text[:300]


# --- account-status (admin, activo) ---

def test_account_status_admin_active_shape():
    set_state(None)  # ensure active
    s, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    r = s.get(f"{BASE_URL}/api/billing/account-status", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data.get("state") == "active"
    assert data.get("role") == "admin"
    # campos requeridos
    for k in ("plan_name", "amount", "currency", "billing_cycle"):
        assert k in data, f"missing {k} in account-status: {data}"


# --- payment wall enforcement ---

def test_payment_wall_402_on_suspended():
    try:
        set_state("suspended")
        s, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD)

        r_pat = s.get(f"{BASE_URL}/api/patients", timeout=30)
        assert r_pat.status_code == 402, f"patients expected 402, got {r_pat.status_code}: {r_pat.text[:200]}"

        r_fin = s.get(f"{BASE_URL}/api/finance", timeout=30)
        assert r_fin.status_code == 402, f"finance expected 402, got {r_fin.status_code}: {r_fin.text[:200]}"

        # Whitelist: billing/account-status y plans deben responder 200
        r_st = s.get(f"{BASE_URL}/api/billing/account-status", timeout=30)
        assert r_st.status_code == 200, r_st.text[:200]
        assert r_st.json().get("state") == "suspended"

        r_pl = s.get(f"{BASE_URL}/api/plans", timeout=30)
        assert r_pl.status_code == 200, r_pl.text[:200]
    finally:
        set_state(None)


def test_restore_active_final():
    # Safety net: dejar la empresa en activo
    set_state(None)
    s, _ = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    r = s.get(f"{BASE_URL}/api/billing/account-status", timeout=30)
    assert r.status_code == 200
    assert r.json().get("state") == "active"
