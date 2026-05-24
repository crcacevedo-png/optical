from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from db import db, serialize_doc
from auth_utils import get_current_user

router = APIRouter(prefix="/superadmin", tags=["SuperAdmin"])

@router.get("/dashboard")
async def get_superadmin_dashboard(user: dict = Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    month_start = now.strftime("%Y-%m-01")
    
    # ========== TOTALS ==========
    total_companies = await db.companies.count_documents({"is_active": {"$ne": False}})
    inactive_companies = await db.companies.count_documents({"is_active": False})
    total_patients = await db.patients.count_documents({"is_deleted": {"$ne": True}})
    total_users = await db.users.count_documents({"role": {"$ne": "superadmin"}, "is_active": {"$ne": False}})
    total_branches = await db.branches.count_documents({})
    total_sales = await db.sales.count_documents({})
    
    new_companies_month = await db.companies.count_documents({"created_at": {"$gte": month_start}})
    
    # ========== PLANS & COMPANIES ==========
    plans = await db.plans.find({}).to_list(50)
    plan_map = {p["_id"]: p["name"] for p in plans}
    plan_prices = {p["_id"]: p["price"] for p in plans}
    companies = await db.companies.find({"is_active": {"$ne": False}}).to_list(1000)
    
    # Companies by plan
    companies_by_plan = {}
    for p in plans:
        companies_by_plan[p["name"]] = 0
    companies_by_plan["Sin plan"] = 0
    for c in companies:
        pname = plan_map.get(c.get("plan_id"), "Sin plan")
        companies_by_plan[pname] = companies_by_plan.get(pname, 0) + 1
    
    # ========== REVENUE METRICS ==========
    estimated_revenue = 0
    revenue_by_plan = {}
    for c in companies:
        pid = c.get("plan_id")
        price = plan_prices.get(pid, 0)
        estimated_revenue += price
        pname = plan_map.get(pid, "Sin plan")
        revenue_by_plan[pname] = revenue_by_plan.get(pname, 0) + price
    
    arpu = round(estimated_revenue / len(companies), 2) if companies else 0
    
    # MRR trend 6 months (based on plan_history to estimate past revenue)
    mrr_trend = []
    for i in range(5, -1, -1):
        m_dt = now - timedelta(days=i * 30)
        m_label = m_dt.strftime("%b %Y")
        # Simplified: current MRR minus changes after that month
        # For accuracy we just show current MRR for all months (real tracking would need snapshots)
        mrr_trend.append({"month": m_label, "mrr": estimated_revenue})
    # Adjust past months roughly by counting plan changes
    history = await db.plan_history.find({}).sort("changed_at", 1).to_list(500)
    # Simple approach: current MRR is our baseline, we won't backtrack for simplicity
    
    # Churn rate
    churn_rate = round((inactive_companies / (total_companies + inactive_companies)) * 100, 1) if (total_companies + inactive_companies) > 0 else 0
    
    # ========== PLAN CONVERSION FUNNEL ==========
    plan_order = {"Free": 0, "Basic": 1, "Enterprise": 2}
    upgrades = 0
    downgrades = 0
    for h in history:
        old_rank = plan_order.get(h.get("old_plan_name"), -1)
        new_rank = plan_order.get(h.get("new_plan_name"), -1)
        if new_rank > old_rank:
            upgrades += 1
        elif new_rank < old_rank and old_rank >= 0:
            downgrades += 1
    
    funnel = {
        "free": companies_by_plan.get("Free", 0),
        "basic": companies_by_plan.get("Basic", 0),
        "enterprise": companies_by_plan.get("Enterprise", 0),
        "upgrades_total": upgrades,
        "downgrades_total": downgrades
    }
    
    # ========== PATIENT GROWTH 6 MONTHS ==========
    patient_growth = []
    for i in range(5, -1, -1):
        m_dt = now - timedelta(days=i * 30)
        m_str = m_dt.strftime("%Y-%m")
        start = f"{m_str}-01"
        end = today + "T23:59:59" if i == 0 else f"{(m_dt + timedelta(days=30)).strftime('%Y-%m')}-01"
        count = await db.patients.count_documents({
            "is_deleted": {"$ne": True},
            "created_at": {"$gte": start, "$lt": end}
        })
        patient_growth.append({"month": m_dt.strftime("%b %Y"), "count": count})
    
    # ========== ENGAGEMENT: Active users last 7/30 days ==========
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    thirty_days_ago = (now - timedelta(days=30)).isoformat()
    
    active_7d = await db.login_attempts.count_documents({})  # Simplified
    # Better: count distinct users who logged in (use sales/appointments as proxy for activity)
    active_users_30d = set()
    active_users_7d = set()
    
    # Check recent sales as activity proxy
    recent_sales = await db.sales.find(
        {"created_at": {"$gte": thirty_days_ago}},
        {"created_by": 1, "created_at": 1}
    ).to_list(5000)
    for s in recent_sales:
        if s.get("created_by"):
            active_users_30d.add(str(s["created_by"]))
            if s.get("created_at", "") >= seven_days_ago:
                active_users_7d.add(str(s["created_by"]))
    
    # Check recent appointments
    recent_apts = await db.appointments.find(
        {"created_at": {"$gte": thirty_days_ago}},
        {"created_by": 1, "created_at": 1}
    ).to_list(5000)
    for a in recent_apts:
        if a.get("created_by"):
            active_users_30d.add(str(a["created_by"]))
            if a.get("created_at", "") >= seven_days_ago:
                active_users_7d.add(str(a["created_by"]))
    
    # Check recent consultations
    recent_cons = await db.optical_consultations.find(
        {"created_at": {"$gte": thirty_days_ago}},
        {"created_by": 1, "created_at": 1}
    ).to_list(5000)
    for c in recent_cons:
        if c.get("created_by"):
            active_users_30d.add(str(c["created_by"]))
            if c.get("created_at", "") >= seven_days_ago:
                active_users_7d.add(str(c["created_by"]))
    
    # Check recent patients created
    recent_patients = await db.patients.find(
        {"created_at": {"$gte": thirty_days_ago}},
        {"created_by": 1, "created_at": 1}
    ).to_list(5000)
    for p in recent_patients:
        if p.get("created_by"):
            active_users_30d.add(str(p["created_by"]))
            if p.get("created_at", "") >= seven_days_ago:
                active_users_7d.add(str(p["created_by"]))
    
    # ========== TOP 5 COMPANIES ==========
    top_companies = []
    for c in companies:
        cid = c["_id"]
        p_count = await db.patients.count_documents({"company_id": cid, "is_deleted": {"$ne": True}})
        s_count = await db.sales.count_documents({"company_id": cid})
        con_count = await db.optical_consultations.count_documents({"company_id": cid})
        top_companies.append({
            "name": c["name"],
            "plan": plan_map.get(c.get("plan_id"), "Free"),
            "patients": p_count,
            "sales": s_count,
            "consultations": con_count,
            "score": p_count + s_count * 2 + con_count
        })
    top_companies.sort(key=lambda x: x["score"], reverse=True)
    top_5 = top_companies[:5]
    
    # ========== MODULE USAGE ==========
    module_usage = {}
    optional_modules = ["inventario", "ventas", "proveedores", "finanzas"]
    for mod in optional_modules:
        count = 0
        for p in plans:
            if mod in p.get("modules", []):
                for c in companies:
                    if c.get("plan_id") == p["_id"]:
                        count += 1
        module_usage[mod] = count
    
    # ========== PLATFORM VOLUME ==========
    total_sales_volume = 0
    all_sales = await db.sales.find({}, {"total": 1}).to_list(10000)
    total_sales_volume = sum(s.get("total", 0) for s in all_sales)
    
    sales_this_month = await db.sales.find({"created_at": {"$gte": month_start}}, {"total": 1}).to_list(5000)
    sales_volume_month = sum(s.get("total", 0) for s in sales_this_month)
    
    # Patients per company (avg + distribution)
    patients_per_company = []
    for c in companies:
        pc = await db.patients.count_documents({"company_id": c["_id"], "is_deleted": {"$ne": True}})
        patients_per_company.append(pc)
    avg_patients = round(sum(patients_per_company) / len(patients_per_company), 1) if patients_per_company else 0
    
    # ========== COMPANIES AT LIMIT ==========
    companies_at_limit = []
    for c in companies:
        pid = c.get("plan_id")
        plan = next((p for p in plans if p["_id"] == pid), None)
        if not plan:
            continue
        cid = c["_id"]
        max_p = plan.get("max_patients", 0)
        max_b = plan.get("max_branches", 0)
        if max_p == 0 and max_b == 0:
            continue
        p_count = await db.patients.count_documents({"company_id": cid, "is_deleted": {"$ne": True}})
        b_count = await db.branches.count_documents({"company_id": cid})
        p_warn = max_p > 0 and p_count >= max_p * 0.8
        b_warn = max_b > 0 and b_count >= max_b * 0.8
        if p_warn or b_warn:
            companies_at_limit.append({
                "name": c["name"], "plan_name": plan["name"],
                "patients": p_count, "max_patients": max_p,
                "branches": b_count, "max_branches": max_b,
                "patients_warning": p_warn, "branches_warning": b_warn,
                "patients_percent": round(p_count / max_p * 100) if max_p > 0 else 0,
                "branches_percent": round(b_count / max_b * 100) if max_b > 0 else 0,
            })
    
    # ========== RECENT ACTIVITY ==========
    recent_changes = await db.plan_history.find({}).sort("changed_at", -1).limit(10).to_list(10)
    for h in recent_changes:
        serialize_doc(h)
    
    return {
        "totals": {
            "companies": total_companies, "patients": total_patients,
            "users": total_users, "branches": total_branches,
            "sales": total_sales, "inactive_companies": inactive_companies,
        },
        "companies_by_plan": [{"name": k, "value": v} for k, v in companies_by_plan.items() if v > 0],
        "estimated_revenue": estimated_revenue,
        "arpu": arpu,
        "churn_rate": churn_rate,
        "revenue_by_plan": [{"name": k, "value": v} for k, v in revenue_by_plan.items() if v > 0],
        "funnel": funnel,
        "patient_growth": patient_growth,
        "engagement": {
            "active_7d": len(active_users_7d),
            "active_30d": len(active_users_30d),
            "total_users": total_users,
        },
        "top_companies": top_5,
        "module_usage": [{"name": k.capitalize(), "count": v} for k, v in module_usage.items()],
        "platform_volume": {
            "total_sales_volume": round(total_sales_volume, 2),
            "sales_volume_month": round(sales_volume_month, 2),
            "total_transactions": total_sales,
            "avg_patients_per_company": avg_patients,
        },
        "companies_at_limit": companies_at_limit,
        "recent_plan_changes": recent_changes,
        "new_companies_month": new_companies_month,
    }
