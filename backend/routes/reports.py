from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user

router = APIRouter(prefix="/reports", tags=["Reportes"])

async def get_stock_alerts_count(company_id, branch_id=None):
    query = {"company_id": company_id}
    if branch_id:
        query["branch_id"] = branch_id
    stock_items = await db.stock.find(query).to_list(1000)
    count = 0
    for s in stock_items:
        product = await db.products.find_one({"_id": s["product_id"]}, {"min_stock": 1})
        if product and s["quantity"] <= product.get("min_stock", 5):
            count += 1
    return count

@router.get("/dashboard")
async def get_dashboard(user: dict = Depends(get_current_user), branch_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    
    company_id = ObjectId(user["company_id"])
    branch_filter = {}
    if branch_id:
        try:
            branch_filter["branch_id"] = ObjectId(branch_id)
        except Exception:
            raise HTTPException(status_code=400, detail="branch_id invalido")
    elif user.get("branch_id"):
        branch_filter["branch_id"] = ObjectId(user["branch_id"])
    
    apt_query = {"company_id": company_id, "date": today, **branch_filter}
    appointments_today = await db.appointments.count_documents(apt_query)
    appointments_pending = await db.appointments.count_documents({**apt_query, "status": "pendiente"})
    
    patients_query = {"company_id": company_id, "created_at": {"$gte": month_start}}
    new_patients = await db.patients.count_documents(patients_query)
    
    sales_today_query = {"company_id": company_id, "created_at": {"$gte": today}, **branch_filter}
    sales_today = await db.sales.find(sales_today_query).to_list(100)
    total_sales_today = sum(s.get("total", 0) for s in sales_today)
    sales_count_today = len(sales_today)
    
    sales_month_query = {"company_id": company_id, "created_at": {"$gte": month_start}, **branch_filter}
    sales_month = await db.sales.find(sales_month_query).to_list(1000)
    total_sales_month = sum(s.get("total", 0) for s in sales_month)
    
    finance_query = {"company_id": company_id, "date": {"$gte": month_start, "$lte": today}, **branch_filter}
    finance_entries = await db.finance_entries.find(finance_query).to_list(1000)
    income = sum(e["amount"] for e in finance_entries if e["type"] == "ingreso")
    expense = sum(e["amount"] for e in finance_entries if e["type"] == "egreso")
    
    stock_alerts = await get_stock_alerts_count(company_id, branch_filter.get("branch_id"))
    
    upcoming_apts = await db.appointments.find({
        "company_id": company_id, "date": {"$gte": today}, "status": {"$in": ["pendiente", "confirmada"]},
        **branch_filter
    }).sort([("date", 1), ("time", 1)]).limit(5).to_list(5)
    
    for apt in upcoming_apts:
        serialize_doc(apt)
        patient = await db.patients.find_one({"_id": ObjectId(apt["patient_id"])}, {"first_name": 1, "last_name": 1})
        if patient:
            apt["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
    
    return {
        "appointments_today": appointments_today, "appointments_pending": appointments_pending,
        "new_patients": new_patients, "sales_count_today": sales_count_today,
        "total_sales_today": total_sales_today, "total_sales_month": total_sales_month,
        "income": income, "expense": expense, "profit": income - expense,
        "stock_alerts": stock_alerts, "upcoming_appointments": upcoming_apts
    }

@router.get("/sales")
async def get_sales_report(
    user: dict = Depends(get_current_user),
    date_from: str = None,
    date_to: str = None,
    branch_id: Optional[str] = None
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if branch_id:
        try:
            query["branch_id"] = ObjectId(branch_id)
        except Exception:
            raise HTTPException(status_code=400, detail="branch_id invalido")
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    if date_from and date_to:
        query["created_at"] = {"$gte": date_from, "$lte": date_to + "T23:59:59"}
    else:
        query["created_at"] = {"$gte": month_start, "$lte": today + "T23:59:59"}
    
    sales = await db.sales.find(query).to_list(1000)
    total = sum(s.get("total", 0) for s in sales)
    count = len(sales)
    by_payment = {}
    for s in sales:
        pm = s.get("payment_method", "otro")
        by_payment[pm] = by_payment.get(pm, 0) + s.get("total", 0)
    
    return {
        "total": total, "count": count,
        "average": total / count if count > 0 else 0,
        "by_payment_method": by_payment,
        "period": {"from": date_from or month_start, "to": date_to or today}
    }
