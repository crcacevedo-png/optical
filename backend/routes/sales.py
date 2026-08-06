from fastapi import APIRouter, HTTPException, Depends, Query, Request
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user
from models import SaleCreate
from audit import log_audit
from cache import invalidate_inventory

router = APIRouter(prefix="/sales", tags=["Ventas"])


def _serialize_payments(sale: dict) -> None:
    """Convierte ObjectIds dentro del array payments a strings."""
    for p in sale.get("payments", []) or []:
        if isinstance(p.get("created_by"), ObjectId):
            p["created_by"] = str(p["created_by"])

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
        _serialize_payments(s)
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
    now_iso = datetime.now(timezone.utc).isoformat()

    # ─── Normalizar pagos: array de {method, amount, note, created_at, created_by} ───
    payments = []
    if data.payments:
        for p in data.payments:
            amt = float(p.amount or 0)
            if amt <= 0:
                continue
            payments.append({
                "method": p.method,
                "amount": amt,
                "note": p.note or "",
                "created_at": now_iso,
                "created_by": ObjectId(user["_id"]),
            })
    elif data.amount_paid and data.amount_paid > 0:
        # Legacy path: un solo pago
        payments.append({
            "method": data.payment_method or "cash",
            "amount": float(data.amount_paid),
            "note": "",
            "created_at": now_iso,
            "created_by": ObjectId(user["_id"]),
        })

    total_paid = round(sum(p["amount"] for p in payments), 2)
    balance = round(data.total - total_paid, 2)
    # Metodo principal para displays legacy (el primero registrado)
    primary_method = payments[0]["method"] if payments else "cash"

    sale_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": branch_id,
        "patient_id": ObjectId(data.patient_id) if data.patient_id else None,
        "patient_name_override": data.patient_name_override,
        "items": data.items,
        "subtotal": data.subtotal, "discount": data.discount, "tax": data.tax, "total": data.total,
        "payment_method": primary_method,
        "payments": payments,
        "amount_paid": total_paid,
        "balance": max(0, balance),
        "status": "completada" if balance <= 0 else "pendiente",
        "notes": data.notes,
        "created_at": now_iso,
        "created_by": ObjectId(user["_id"])
    }
    result = await db.sales.insert_one(sale_doc)

    # ─── Descontar stock ───
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
                    "created_at": now_iso,
                    "created_by": ObjectId(user["_id"])
                })

    # ─── Registrar cada pago en finanzas (uno por metodo, para trazabilidad) ───
    for p in payments:
        await db.finance_entries.insert_one({
            "company_id": ObjectId(user["company_id"]),
            "branch_id": branch_id,
            "type": "ingreso",
            "category": "ventas",
            "amount": p["amount"],
            "description": f"Venta #{str(result.inserted_id)[-6:]} ({p['method']})",
            "reference_id": result.inserted_id,
            "reference_type": "sale",
            "payment_method": p["method"],
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "created_at": now_iso,
            "created_by": ObjectId(user["_id"])
        })

    await invalidate_inventory(user["company_id"], str(branch_id) if branch_id else None)
    return {"_id": str(result.inserted_id), "message": "Venta registrada", "balance": max(0, balance)}

@router.get("/receivables")
async def list_receivables(
    user: dict = Depends(get_current_user),
    branch_id: Optional[str] = None,
    limit: int = 200
):
    """Ventas con saldo pendiente (cuentas por cobrar). Solo admin/vendedor."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    query = {
        "company_id": ObjectId(user["company_id"]),
        "balance": {"$gt": 0},
        "status": {"$ne": "cancelada"},
    }
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])

    sales = await db.sales.find(query).sort("created_at", 1).limit(limit).to_list(limit)
    if not sales:
        return {"items": [], "total_pending": 0.0, "count": 0}

    # Batch load patient + seller
    patient_ids = list({s["patient_id"] for s in sales if s.get("patient_id")})
    seller_ids = list({s["created_by"] for s in sales if s.get("created_by")})
    patients_map = {}
    if patient_ids:
        docs = await db.patients.find({"_id": {"$in": patient_ids}}, {"first_name": 1, "last_name": 1, "phone": 1}).to_list(len(patient_ids))
        patients_map = {str(p["_id"]): p for p in docs}
    sellers_map = {}
    if seller_ids:
        docs = await db.users.find({"_id": {"$in": seller_ids}}, {"name": 1}).to_list(len(seller_ids))
        sellers_map = {str(u["_id"]): u.get("name", "") for u in docs}

    total_pending = 0.0
    for s in sales:
        serialize_doc(s)
        _serialize_payments(s)
        pid = s.get("patient_id")
        if pid:
            p = patients_map.get(pid)
            if p:
                s["patient_name"] = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
                s["patient_phone"] = p.get("phone", "")
        else:
            s["patient_name"] = s.get("patient_name_override") or "Consumidor final"
            s["patient_phone"] = ""
        cb = s.get("created_by")
        if cb:
            s["seller_name"] = sellers_map.get(cb, "")
        # Days since sale
        try:
            created = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
            s["days_pending"] = (datetime.now(timezone.utc) - created).days
        except Exception:
            s["days_pending"] = 0
        total_pending += float(s.get("balance", 0) or 0)

    return {
        "items": sales,
        "total_pending": round(total_pending, 2),
        "count": len(sales),
    }


@router.get("/{sale_id}")
async def get_sale(sale_id: str, user: dict = Depends(get_current_user)):
    sale = await db.sales.find_one({"_id": ObjectId(sale_id)})
    if not sale or str(sale["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    serialize_doc(sale)
    _serialize_payments(sale)
    if sale.get("patient_id"):
        patient = await db.patients.find_one({"_id": ObjectId(sale["patient_id"])}, {"first_name": 1, "last_name": 1})
        if patient:
            sale["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
    return sale

@router.post("/{sale_id}/payment")
async def add_payment(
    sale_id: str,
    amount: float = Query(..., gt=0),
    method: str = Query("cash"),
    note: str = Query(""),
    user: dict = Depends(get_current_user)
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    sale = await db.sales.find_one({"_id": ObjectId(sale_id)})
    if not sale or str(sale["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    now_iso = datetime.now(timezone.utc).isoformat()
    payment_entry = {
        "method": method,
        "amount": float(amount),
        "note": note or "",
        "created_at": now_iso,
        "created_by": ObjectId(user["_id"]),
    }
    new_paid = round(float(sale.get("amount_paid", 0) or 0) + float(amount), 2)
    new_balance = round(float(sale["total"]) - new_paid, 2)
    status = "completada" if new_balance <= 0 else "pendiente"

    await db.sales.update_one(
        {"_id": ObjectId(sale_id)},
        {
            "$push": {"payments": payment_entry},
            "$set": {"amount_paid": new_paid, "balance": max(0, new_balance), "status": status}
        }
    )

    await db.finance_entries.insert_one({
        "company_id": ObjectId(user["company_id"]),
        "branch_id": sale.get("branch_id"),
        "type": "ingreso",
        "category": "ventas",
        "amount": float(amount),
        "description": f"Abono venta #{sale_id[-6:]} ({method})",
        "reference_id": ObjectId(sale_id),
        "reference_type": "sale_payment",
        "payment_method": method,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_at": now_iso,
        "created_by": ObjectId(user["_id"])
    })

    return {"message": "Pago registrado", "new_balance": max(0, new_balance), "status": status}


@router.delete("/{sale_id}")
async def delete_sale(sale_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Elimina una venta y revierte sus efectos.
    Solo admin de la optica puede eliminar. Restaura stock, borra movimientos de
    inventario y entradas de finanzas relacionadas. Registra evento en audit log.
    """
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo el administrador puede eliminar ventas")

    try:
        oid = ObjectId(sale_id)
    except Exception:
        raise HTTPException(status_code=400, detail="sale_id invalido")

    sale = await db.sales.find_one({"_id": oid})
    if not sale or str(sale["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    # ─── 1. Restaurar stock ───
    stock_restored = 0
    for item in sale.get("items", []) or []:
        pid = item.get("product_id")
        qty = int(item.get("quantity") or 0)
        if not pid or qty <= 0:
            continue
        try:
            pid_oid = ObjectId(pid) if not isinstance(pid, ObjectId) else pid
        except Exception:
            continue
        stock_query = {"product_id": pid_oid, "company_id": sale["company_id"]}
        if sale.get("branch_id"):
            stock_query["branch_id"] = sale["branch_id"]
        stock_record = await db.stock.find_one(stock_query)
        if stock_record:
            await db.stock.update_one(
                {"_id": stock_record["_id"]},
                {"$inc": {"quantity": qty}}
            )
            stock_restored += qty

    # ─── 2. Borrar movimientos de inventario ligados a la venta ───
    inv_del = await db.inventory_movements.delete_many({"reference": sale_id})

    # ─── 3. Borrar entradas de finanzas ligadas (venta original + abonos) ───
    fin_del = await db.finance_entries.delete_many({
        "reference_id": oid,
        "reference_type": {"$in": ["sale", "sale_payment"]}
    })

    # ─── 4. Eliminar la venta ───
    await db.sales.delete_one({"_id": oid})

    # ─── 5. Audit log ───
    await log_audit(
        "SALE_DELETED",
        actor_id=user["_id"],
        actor_email=user.get("email"),
        metadata={
            "sale_id": sale_id,
            "total": sale.get("total"),
            "amount_paid": sale.get("amount_paid"),
            "patient_id": str(sale["patient_id"]) if sale.get("patient_id") else None,
            "items_count": len(sale.get("items", []) or []),
            "stock_restored": stock_restored,
            "inv_movements_deleted": inv_del.deleted_count,
            "finance_entries_deleted": fin_del.deleted_count,
        },
        request=request,
    )

    branch_str = str(sale.get("branch_id")) if sale.get("branch_id") else None
    await invalidate_inventory(str(sale["company_id"]), branch_str)

    return {
        "message": "Venta eliminada",
        "stock_restored": stock_restored,
        "inv_movements_deleted": inv_del.deleted_count,
        "finance_entries_deleted": fin_del.deleted_count,
    }
