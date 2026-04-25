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
    
    # --- Total counts ---
    total_companies = await db.companies.count_documents({"is_active": {"$ne": False}})
    total_patients = await db.patients.count_documents({"is_deleted": {"$ne": True}})
    total_users = await db.users.count_documents({"role": {"$ne": "superadmin"}, "is_active": {"$ne": False}})
    total_branches = await db.branches.count_documents({})
    
    # --- Companies by plan ---
    plans = await db.plans.find({}).to_list(50)
    plan_map = {p["_id"]: p["name"] for p in plans}
    companies = await db.companies.find({"is_active": {"$ne": False}}).to_list(1000)
    
    companies_by_plan = {}
    for p in plans:
        companies_by_plan[p["name"]] = 0
    companies_by_plan["Sin plan"] = 0
    
    for c in companies:
        pname = plan_map.get(c.get("plan_id"), "Sin plan")
        companies_by_plan[pname] = companies_by_plan.get(pname, 0) + 1
    
    # --- Estimated monthly revenue ---
    plan_prices = {p["_id"]: p["price"] for p in plans}
    estimated_revenue = 0
    revenue_by_plan = {}
    for c in companies:
        pid = c.get("plan_id")
        price = plan_prices.get(pid, 0)
        estimated_revenue += price
        pname = plan_map.get(pid, "Sin plan")
        revenue_by_plan[pname] = revenue_by_plan.get(pname, 0) + price
    
    # --- Patient growth last 6 months ---
    patient_growth = []
    for i in range(5, -1, -1):
        month_dt = now - timedelta(days=i * 30)
        month_str = month_dt.strftime("%Y-%m")
        start = f"{month_str}-01"
        if i == 0:
            end = today + "T23:59:59"
        else:
            next_month_dt = month_dt + timedelta(days=30)
            end = f"{next_month_dt.strftime('%Y-%m')}-01"
        
        count = await db.patients.count_documents({
            "is_deleted": {"$ne": True},
            "created_at": {"$gte": start, "$lt": end}
        })
        patient_growth.append({
            "month": month_dt.strftime("%b %Y"),
            "count": count
        })
    
    # --- Companies at limit (patients or branches) ---
    companies_at_limit = []
    for c in companies:
        pid = c.get("plan_id")
        plan = None
        for p in plans:
            if p["_id"] == pid:
                plan = p
                break
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
                "name": c["name"],
                "plan_name": plan["name"],
                "patients": p_count,
                "max_patients": max_p,
                "branches": b_count,
                "max_branches": max_b,
                "patients_warning": p_warn,
                "branches_warning": b_warn,
                "patients_percent": round(p_count / max_p * 100) if max_p > 0 else 0,
                "branches_percent": round(b_count / max_b * 100) if max_b > 0 else 0,
            })
    
    # --- Recent plan changes ---
    recent_changes = await db.plan_history.find({}).sort("changed_at", -1).limit(10).to_list(10)
    for h in recent_changes:
        serialize_doc(h)
    
    # --- New companies this month ---
    month_start = now.strftime("%Y-%m-01")
    new_companies_month = await db.companies.count_documents({
        "created_at": {"$gte": month_start}
    })
    
    return {
        "totals": {
            "companies": total_companies,
            "patients": total_patients,
            "users": total_users,
            "branches": total_branches,
        },
        "companies_by_plan": [{"name": k, "value": v} for k, v in companies_by_plan.items() if v > 0],
        "estimated_revenue": estimated_revenue,
        "revenue_by_plan": [{"name": k, "value": v} for k, v in revenue_by_plan.items() if v > 0],
        "patient_growth": patient_growth,
        "companies_at_limit": companies_at_limit,
        "recent_plan_changes": recent_changes,
        "new_companies_month": new_companies_month,
    }
