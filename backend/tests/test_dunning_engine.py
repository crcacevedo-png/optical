"""Verificacion determinista del motor de cobros (dunning) SIN depender de Stripe.
Prueba las transiciones internas: gracia -> suspension -> reactivacion + snapshot.
Ejecutar: cd /app/backend && python -m tests.test_dunning_engine
"""
import asyncio
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from db import db
import dunning


async def _mk_company(**extra):
    doc = {
        "name": "QA Dunning Optica",
        "is_active": True,
        "plan_id": None,
        "billing_cycle": "monthly",
        "stripe_subscription_id": "sub_qa_fake",
        "created_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    res = await db.companies.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


async def main():
    passed, failed = 0, 0

    # Evitar spam de correos/notificaciones a superadmins durante el test (no-op).
    async def _noop(*a, **k):
        return None
    dunning.queue_email = _noop
    dunning.create_notification = _noop

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  PASS {name}")
        else:
            failed += 1
            print(f"  FAIL {name}")

    now = datetime.now(timezone.utc)

    # 1) Pago fallido -> gracia
    c = await _mk_company()
    await dunning._handle_problem(c, {"subscription_status": "past_due"}, now, "Basic", "$ 299.00")
    doc = await db.companies.find_one({"_id": c["_id"]})
    check("past_due inicia gracia", doc.get("billing_state") == "grace")
    check("grace_until seteado", bool(doc.get("grace_until")))
    check("payment_failed_at seteado", bool(doc.get("payment_failed_at")))

    # snapshot en gracia
    snap = dunning.build_billing_snapshot(doc)
    check("snapshot state=grace", snap["state"] == "grace")
    check("snapshot days_remaining>=0", (snap.get("days_remaining") or 0) >= 0)

    # 2) Gracia vencida -> suspension
    doc["grace_until"] = (now - timedelta(hours=1)).isoformat()
    await db.companies.update_one({"_id": c["_id"]}, {"$set": {"grace_until": doc["grace_until"]}})
    doc = await db.companies.find_one({"_id": c["_id"]})
    await dunning._handle_problem(doc, {"subscription_status": "unpaid"}, now, "Basic", "$ 299.00")
    doc = await db.companies.find_one({"_id": c["_id"]})
    check("gracia vencida -> suspended", doc.get("billing_state") == "suspended")
    check("suspended_at seteado", bool(doc.get("suspended_at")))
    check("suspended_reason=payment_failed", doc.get("suspended_reason") == "payment_failed")

    # snapshot suspendido
    snap = dunning.build_billing_snapshot(doc)
    check("snapshot state=suspended", snap["state"] == "suspended")

    # 3) Pago OK -> reactivacion
    await dunning._handle_ok(doc, {"current_period_start": int(now.timestamp())}, {"subscription_status": "active"})
    doc = await db.companies.find_one({"_id": c["_id"]})
    check("active -> reactivado", doc.get("billing_state") == "active")
    check("grace_until limpiado", doc.get("grace_until") is None)
    check("suspended_at limpiado", doc.get("suspended_at") is None)

    # 4) Cancelacion -> suspension
    c2 = await _mk_company()
    await dunning._handle_dead(c2, {"subscription_status": "canceled"}, now)
    doc2 = await db.companies.find_one({"_id": c2["_id"]})
    check("canceled -> suspended", doc2.get("billing_state") == "suspended")
    check("reason=subscription_canceled", doc2.get("suspended_reason") == "subscription_canceled")

    # 5) Cortesia exenta: process_company no suspende (retorna active)
    c3 = await _mk_company(is_courtesy=True, billing_state="grace",
                           grace_until=(now - timedelta(days=1)).isoformat())
    state = await dunning.process_company(c3, now)
    check("cortesia -> exenta (active)", state == "active")
    doc3 = await db.companies.find_one({"_id": c3["_id"]})
    check("cortesia billing_state=active", doc3.get("billing_state") == "active")

    # 6) Panel de cobros incluye la suspendida y la cancelada
    panel = await dunning.build_collections_panel(7)
    names = [r["company_name"] for r in panel["suspended"]]
    check("panel lista suspendidas", "QA Dunning Optica" in names)
    check("kpi suspended>=1", panel["kpis"]["suspended"] >= 1)

    # cleanup
    await db.companies.delete_many({"name": "QA Dunning Optica"})

    print(f"\nRESULT: {passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    rc = asyncio.get_event_loop().run_until_complete(main())
    raise SystemExit(1 if rc else 0)
