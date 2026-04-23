from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user
from models import SaleCreate

router = APIRouter(prefix="/sales", tags=["Ventas"])

@router.get("")
async def list_sales(
    user: dict = Depends(get_current_user),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[str] = None,
    limit: int = 100
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    if date_from and date_to:
        query["created_at"] = {"$gte": date_from, "$lte": date_to + "T23:59:59"}
    
    sales = await db.sales.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    for s in sales:
        serialize_doc(s)
        if s.get("patient_id"):
            patient = await db.patients.find_one({"_id": ObjectId(s["patient_id"])}, {"first_name": 1, "last_name": 1})
            if patient:
                s["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
        if s.get("created_by"):
            seller = await db.users.find_one({"_id": ObjectId(s["created_by"])}, {"name": 1})
            if seller:
                s["seller_name"] = seller["name"]
    return sales

@router.post("")
async def create_sale(data: SaleCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    branch_id = ObjectId(user["branch_id"]) if user.get("branch_id") else None
    
    sale_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": branch_id,
        "patient_id": ObjectId(data.patient_id) if data.patient_id else None,
        "items": data.items,
        "subtotal": data.subtotal, "discount": data.discount, "tax": data.tax, "total": data.total,
        "payment_method": data.payment_method, "amount_paid": data.amount_paid,
        "balance": data.total - data.amount_paid,
        "status": "completada" if data.amount_paid >= data.total else "pendiente",
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    result = await db.sales.insert_one(sale_doc)
    
    for item in data.items:
        if item.get("product_id"):
            stock_query = {"product_id": ObjectId(item["product_id"]), "company_id": ObjectId(user["company_id"])}
            if branch_id:
                stock_query["branch_id"] = branch_id
            stock_record = await db.stock.find_one(stock_query)
            if stock_record:
                actual_branch = stock_record["branch_id"]
                await db.stock.update_one(
                    {"_id": stock_record["_id"]},
                    {"$inc": {"quantity": -item.get("quantity", 1)}}
                )
                await db.inventory_movements.insert_one({
                    "company_id": ObjectId(user["company_id"]),
                    "branch_id": actual_branch,
                    "product_id": ObjectId(item["product_id"]),
                    "type": "salida",
                    "quantity": item.get("quantity", 1),
                    "notes": f"Venta #{str(result.inserted_id)[-6:]}",
                    "reference": str(result.inserted_id),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "created_by": ObjectId(user["_id"])
                })
    
    finance_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": branch_id,
        "type": "ingreso",
        "category": "ventas",
        "amount": data.amount_paid,
        "description": f"Venta #{str(result.inserted_id)[-6:]}",
        "reference_id": result.inserted_id,
        "reference_type": "sale",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    await db.finance_entries.insert_one(finance_doc)
    
    return {"_id": str(result.inserted_id), "message": "Venta registrada"}

@router.get("/{sale_id}")
async def get_sale(sale_id: str, user: dict = Depends(get_current_user)):
    sale = await db.sales.find_one({"_id": ObjectId(sale_id)})
    if not sale or str(sale["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    serialize_doc(sale)
    if sale.get("patient_id"):
        patient = await db.patients.find_one({"_id": ObjectId(sale["patient_id"])}, {"first_name": 1, "last_name": 1})
        if patient:
            sale["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
    return sale

@router.post("/{sale_id}/payment")
async def add_payment(sale_id: str, amount: float = Query(...), user: dict = Depends(get_current_user)):
    sale = await db.sales.find_one({"_id": ObjectId(sale_id)})
    if not sale or str(sale["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    
    new_paid = sale.get("amount_paid", 0) + amount
    new_balance = sale["total"] - new_paid
    status = "completada" if new_balance <= 0 else "pendiente"
    
    await db.sales.update_one(
        {"_id": ObjectId(sale_id)},
        {"$set": {"amount_paid": new_paid, "balance": max(0, new_balance), "status": status}}
    )
    
    finance_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": sale.get("branch_id"),
        "type": "ingreso",
        "category": "ventas",
        "amount": amount,
        "description": f"Abono venta #{sale_id[-6:]}",
        "reference_id": ObjectId(sale_id),
        "reference_type": "sale_payment",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    await db.finance_entries.insert_one(finance_doc)
    
    return {"message": "Pago registrado", "new_balance": max(0, new_balance)}
