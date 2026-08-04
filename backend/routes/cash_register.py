"""Modulo de Caja (Cash Register).
Permite abrir y cerrar caja por sucursal. Al cerrar computa totales
de pagos recibidos durante la ventana (agrupados por metodo) y las
ventas con saldo pendiente creadas en ese periodo.
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

from db import db, serialize_doc
from auth_utils import get_current_user
from audit import log_audit

router = APIRouter(prefix="/cash-register", tags=["Caja"])


class OpenCashRegister(BaseModel):
    opening_amount: float = 0
    opening_notes: Optional[str] = None


class CloseCashRegister(BaseModel):
    counted_cash: Optional[float] = None  # Efectivo contado fisicamente al cierre (para deteccion de faltantes)
    closing_notes: Optional[str] = None


def _serialize(doc: dict) -> dict:
    serialize_doc(doc)
    for k in ("opened_by", "closed_by"):
        v = doc.get(k)
        if isinstance(v, ObjectId):
            doc[k] = str(v)
    return doc


async def _get_branch_id_or_400(user: dict, override: Optional[str] = None) -> ObjectId:
    """Determina la sucursal donde operar. Vendedores usan la propia. Admins pueden pasar override."""
    if override:
        return ObjectId(override)
    if user.get("branch_id"):
        return ObjectId(user["branch_id"])
    raise HTTPException(status_code=400, detail="El usuario no tiene sucursal asignada. Especifica una.")


@router.get("/current")
async def get_current_register(
    branch_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Retorna la caja abierta del usuario/sucursal actual, o null."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    bid = await _get_branch_id_or_400(user, branch_id)
    reg = await db.cash_registers.find_one({
        "company_id": ObjectId(user["company_id"]),
        "branch_id": bid,
        "status": "open",
    }, sort=[("opened_at", -1)])
    if not reg:
        return {"register": None}
    _serialize(reg)
    return {"register": reg}


@router.get("/current/preview")
async def get_current_preview(
    branch_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Preview en vivo del cierre para la caja abierta.
    Calcula totales por metodo de pago y ventas del turno sin cerrar la caja."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    bid = await _get_branch_id_or_400(user, branch_id)
    reg = await db.cash_registers.find_one({
        "company_id": ObjectId(user["company_id"]),
        "branch_id": bid,
        "status": "open",
    }, sort=[("opened_at", -1)])
    if not reg:
        raise HTTPException(status_code=404, detail="No hay caja abierta")

    now_iso = datetime.now(timezone.utc).isoformat()
    totals = await _compute_close_totals(
        ObjectId(user["company_id"]), bid, reg["opened_at"], now_iso
    )
    expected_cash = round(float(reg.get("opening_amount", 0) or 0) + totals["totals_by_method"].get("cash", 0), 2)

    # Attach patient names to receivables (parity con GET /{id})
    if totals.get("sales_in_window"):
        pids = list({s["patient_id"] for s in totals["sales_in_window"] if s.get("patient_id")})
        pmap = {}
        if pids:
            try:
                docs = await db.patients.find(
                    {"_id": {"$in": [ObjectId(p) for p in pids]}},
                    {"first_name": 1, "last_name": 1}
                ).to_list(len(pids))
                pmap = {str(p["_id"]): f"{p.get('first_name','')} {p.get('last_name','')}".strip() for p in docs}
            except Exception:
                pass
        for s in totals["sales_in_window"]:
            s["patient_name"] = pmap.get(s.get("patient_id"), "Consumidor final")

    _serialize(reg)
    reg.update({
        "expected_cash": expected_cash,
        "totals_by_method": totals["totals_by_method"],
        "total_received": totals["total_received"],
        "payments_count": totals["payments_count"],
        "sales_in_window_count": totals["sales_in_window_count"],
        "receivables_count": totals["receivables_count"],
        "receivables_total": totals["receivables_total"],
        "payments_detail": totals["payments_detail"],
        "sales_in_window": totals["sales_in_window"],
        "is_preview": True,
    })
    return reg


@router.post("/open")
async def open_register(data: OpenCashRegister, request: Request, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    bid = await _get_branch_id_or_400(user)

    # No permitir dos cajas abiertas en la misma sucursal
    existing = await db.cash_registers.find_one({
        "company_id": ObjectId(user["company_id"]),
        "branch_id": bid,
        "status": "open",
    })
    if existing:
        raise HTTPException(status_code=400, detail="Ya hay una caja abierta en esta sucursal")

    now = datetime.now(timezone.utc)
    doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": bid,
        "status": "open",
        "opening_amount": float(data.opening_amount or 0),
        "opening_notes": data.opening_notes or "",
        "opened_at": now.isoformat(),
        "opened_by": ObjectId(user["_id"]),
        "opened_by_name": user.get("name", ""),
    }
    result = await db.cash_registers.insert_one(doc)

    await log_audit("CASH_REGISTER_OPENED", actor_id=user["_id"], actor_email=user.get("email"),
                    metadata={"register_id": str(result.inserted_id), "opening_amount": doc["opening_amount"], "branch_id": str(bid)},
                    request=request)

    doc["_id"] = str(result.inserted_id)
    _serialize(doc)
    return {"message": "Caja abierta", "register": doc}


async def _compute_close_totals(company_id: ObjectId, branch_id: ObjectId, opened_at_iso: str, closed_at_iso: str) -> dict:
    """Suma pagos por metodo durante la ventana + cuentas por cobrar creadas."""
    # 1. Todos los sales de la sucursal con al menos un payment en la ventana
    sales_cursor = db.sales.find({
        "company_id": company_id,
        "branch_id": branch_id,
        # No filtramos por sale.created_at para capturar tambien abonos a ventas viejas
    })

    totals_by_method = {"cash": 0.0, "card": 0.0, "transfer": 0.0, "check": 0.0, "other": 0.0}
    payments_detail = []
    sales_in_window = []
    receivables_in_window = []

    async for sale in sales_cursor:
        sale_id_str = str(sale["_id"])
        sale_created_in_window = opened_at_iso <= sale.get("created_at", "") <= closed_at_iso

        # Sumar pagos que caen en la ventana
        window_paid_for_this_sale = 0.0
        for p in sale.get("payments", []) or []:
            pdate = p.get("created_at", "")
            if opened_at_iso <= pdate <= closed_at_iso:
                method = p.get("method", "other")
                amt = float(p.get("amount") or 0)
                totals_by_method[method] = totals_by_method.get(method, 0) + amt
                window_paid_for_this_sale += amt
                payments_detail.append({
                    "sale_id": sale_id_str,
                    "method": method,
                    "amount": amt,
                    "note": p.get("note", ""),
                    "created_at": pdate,
                })

        # Si la venta se creo en la ventana, contarla como venta del dia
        if sale_created_in_window:
            sales_in_window.append({
                "sale_id": sale_id_str,
                "total": float(sale.get("total") or 0),
                "amount_paid": float(sale.get("amount_paid") or 0),
                "balance": float(sale.get("balance") or 0),
                "patient_id": str(sale["patient_id"]) if sale.get("patient_id") else None,
                "status": sale.get("status"),
                "created_at": sale.get("created_at"),
            })
            if float(sale.get("balance") or 0) > 0:
                receivables_in_window.append(sale_id_str)

    total_received = round(sum(totals_by_method.values()), 2)
    totals_by_method = {k: round(v, 2) for k, v in totals_by_method.items()}
    receivables_total = round(
        sum(s["balance"] for s in sales_in_window if s["balance"] > 0), 2
    )

    return {
        "totals_by_method": totals_by_method,
        "total_received": total_received,
        "payments_count": len(payments_detail),
        "sales_in_window_count": len(sales_in_window),
        "receivables_count": len(receivables_in_window),
        "receivables_total": receivables_total,
        "receivables_sale_ids": receivables_in_window,
        "payments_detail": payments_detail,
        "sales_in_window": sales_in_window,
    }


@router.post("/close")
async def close_register(data: CloseCashRegister, request: Request, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    bid = await _get_branch_id_or_400(user)
    reg = await db.cash_registers.find_one({
        "company_id": ObjectId(user["company_id"]),
        "branch_id": bid,
        "status": "open",
    })
    if not reg:
        raise HTTPException(status_code=404, detail="No hay caja abierta en esta sucursal")

    now = datetime.now(timezone.utc)
    closed_at_iso = now.isoformat()

    totals = await _compute_close_totals(
        ObjectId(user["company_id"]), bid,
        reg["opened_at"], closed_at_iso
    )

    expected_cash = round(float(reg.get("opening_amount", 0) or 0) + totals["totals_by_method"].get("cash", 0), 2)
    counted_cash = float(data.counted_cash) if data.counted_cash is not None else None
    cash_difference = round((counted_cash - expected_cash), 2) if counted_cash is not None else None

    update = {
        "status": "closed",
        "closed_at": closed_at_iso,
        "closed_by": ObjectId(user["_id"]),
        "closed_by_name": user.get("name", ""),
        "closing_notes": data.closing_notes or "",
        "expected_cash": expected_cash,
        "counted_cash": counted_cash,
        "cash_difference": cash_difference,
        "totals_by_method": totals["totals_by_method"],
        "total_received": totals["total_received"],
        "payments_count": totals["payments_count"],
        "sales_in_window_count": totals["sales_in_window_count"],
        "receivables_count": totals["receivables_count"],
        "receivables_total": totals["receivables_total"],
        "receivables_sale_ids": totals["receivables_sale_ids"],
        "payments_detail": totals["payments_detail"],
        "sales_in_window": totals["sales_in_window"],
    }
    await db.cash_registers.update_one({"_id": reg["_id"]}, {"$set": update})

    await log_audit("CASH_REGISTER_CLOSED", actor_id=user["_id"], actor_email=user.get("email"),
                    metadata={
                        "register_id": str(reg["_id"]),
                        "total_received": update["total_received"],
                        "expected_cash": expected_cash,
                        "counted_cash": counted_cash,
                        "cash_difference": cash_difference,
                        "receivables_count": update["receivables_count"],
                    }, request=request)

    reg.update(update)
    _serialize(reg)
    return {"message": "Caja cerrada", "register": reg}


@router.get("")
async def list_registers(
    user: dict = Depends(get_current_user),
    branch_id: Optional[str] = None,
    limit: int = Query(30, ge=1, le=200),
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    query = {"company_id": ObjectId(user["company_id"])}
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id") and user["role"] != "admin":
        query["branch_id"] = ObjectId(user["branch_id"])

    regs = await db.cash_registers.find(query).sort("opened_at", -1).limit(limit).to_list(limit)
    # Batch load branches
    bids = list({r["branch_id"] for r in regs if r.get("branch_id")})
    branches_map = {}
    if bids:
        docs = await db.branches.find({"_id": {"$in": bids}}, {"name": 1}).to_list(len(bids))
        branches_map = {str(b["_id"]): b.get("name", "") for b in docs}
    for r in regs:
        _serialize(r)
        r["branch_name"] = branches_map.get(str(r.get("branch_id")), "")
    return regs


@router.get("/{register_id}")
async def get_register(register_id: str, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        oid = ObjectId(register_id)
    except Exception:
        raise HTTPException(status_code=400, detail="register_id invalido")
    reg = await db.cash_registers.find_one({"_id": oid})
    if not reg or str(reg["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Caja no encontrada")
    _serialize(reg)
    # Attach patient names for receivables
    if reg.get("sales_in_window"):
        pids = list({s["patient_id"] for s in reg["sales_in_window"] if s.get("patient_id")})
        pmap = {}
        if pids:
            try:
                docs = await db.patients.find({"_id": {"$in": [ObjectId(p) for p in pids]}}, {"first_name": 1, "last_name": 1}).to_list(len(pids))
                pmap = {str(p["_id"]): f"{p.get('first_name','')} {p.get('last_name','')}".strip() for p in docs}
            except Exception:
                pass
        for s in reg["sales_in_window"]:
            s["patient_name"] = pmap.get(s.get("patient_id"), "Consumidor final")
    return reg
