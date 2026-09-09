from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user
from models import FinanceEntryCreate

router = APIRouter(prefix="/finance", tags=["Finanzas"])

@router.get("")
async def list_finance_entries(
    user: dict = Depends(get_current_user),
    type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[str] = None,
    category: Optional[str] = None
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if type:
        query["type"] = type
    if category:
        query["category"] = category
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    if date_from and date_to:
        query["date"] = {"$gte": date_from, "$lte": date_to}
    
    entries = await db.finance_entries.find(query).sort("date", -1).to_list(500)
    return [serialize_doc(e) for e in entries]

@router.post("")
async def create_finance_entry(data: FinanceEntryCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    entry_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(user["branch_id"]) if user.get("branch_id") else None,
        "type": data.type, "category": data.category, "amount": data.amount,
        "description": data.description,
        "date": data.date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "reference": data.reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    if data.supplier_id:
        try:
            sup_oid = ObjectId(data.supplier_id)
        except Exception:
            raise HTTPException(status_code=400, detail="supplier_id invalido")
        supplier = await db.suppliers.find_one({"_id": sup_oid, "company_id": ObjectId(user["company_id"])})
        if not supplier:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        entry_doc["supplier_id"] = sup_oid
        entry_doc["supplier_name"] = supplier.get("name")
    elif data.type == "egreso" and data.category == "suppliers":
        raise HTTPException(status_code=400, detail="Selecciona un proveedor para egresos de la categoria Proveedores.")
    result = await db.finance_entries.insert_one(entry_doc)
    return {"_id": str(result.inserted_id), "message": "Entrada registrada"}

@router.get("/summary")
async def get_finance_summary(
    user: dict = Depends(get_current_user),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
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
        query["date"] = {"$gte": date_from, "$lte": date_to}
    else:
        query["date"] = {"$gte": month_start, "$lte": today}
    
    entries = await db.finance_entries.find(query).to_list(1000)
    income = sum(e["amount"] for e in entries if e["type"] == "ingreso")
    expense = sum(e["amount"] for e in entries if e["type"] == "egreso")
    
    income_by_category = {}
    expense_by_category = {}
    for e in entries:
        if e["type"] == "ingreso":
            income_by_category[e["category"]] = income_by_category.get(e["category"], 0) + e["amount"]
        else:
            expense_by_category[e["category"]] = expense_by_category.get(e["category"], 0) + e["amount"]
    
    return {
        "income": income, "expense": expense, "profit": income - expense,
        "income_by_category": income_by_category, "expense_by_category": expense_by_category,
        "period": {"from": date_from or month_start, "to": date_to or today}
    }

@router.get("/dashboard")
async def get_finance_dashboard(user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    
    query = {"company_id": ObjectId(user["company_id"]), "date": {"$gte": month_start, "$lte": today}}
    if user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    entries = await db.finance_entries.find(query).to_list(1000)
    income = sum(e["amount"] for e in entries if e["type"] == "ingreso")
    expense = sum(e["amount"] for e in entries if e["type"] == "egreso")
    
    today_query = {**query, "date": today}
    today_entries = await db.finance_entries.find(today_query).to_list(100)
    today_income = sum(e["amount"] for e in today_entries if e["type"] == "ingreso")
    today_expense = sum(e["amount"] for e in today_entries if e["type"] == "egreso")
    
    return {
        "month": {"income": income, "expense": expense, "profit": income - expense},
        "today": {"income": today_income, "expense": today_expense, "profit": today_income - today_expense}
    }
