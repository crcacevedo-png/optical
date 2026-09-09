"""Modulo de Caja (Cash Register).
Permite abrir y cerrar caja por sucursal. Al cerrar computa totales
de pagos recibidos durante la ventana (agrupados por metodo) y las
ventas con saldo pendiente creadas en ese periodo.
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import StreamingResponse
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
import io
import asyncio

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)

from db import db, serialize_doc
from auth_utils import get_current_user
from audit import log_audit

router = APIRouter(prefix="/cash-register", tags=["Caja"])

_METHOD_LABELS = {
    "cash": "Efectivo", "card": "Tarjeta", "transfer": "Transferencia",
    "check": "Cheque", "other": "Otro",
}


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
    """Determina la sucursal donde operar.

    Reglas:
    1. Si viene `override` explicito, se usa.
    2. Si el usuario tiene `branch_id` propio (vendedores/doctores), se usa.
    3. Si el usuario es admin sin branch_id asignada, se toma la sucursal principal
       (`is_main=True`) o, si no existe, la primera sucursal activa de la empresa.
    4. Si la empresa no tiene ninguna sucursal, se retorna 400.
    """
    if override:
        return ObjectId(override)
    if user.get("branch_id"):
        return ObjectId(user["branch_id"])
    # Fallback: admins sin branch_id -> sucursal principal / primera de la empresa
    company_oid = ObjectId(user["company_id"])
    main = await db.branches.find_one(
        {"company_id": company_oid, "is_active": {"$ne": False}, "is_main": True},
        {"_id": 1},
    )
    if main:
        return main["_id"]
    any_branch = await db.branches.find_one(
        {"company_id": company_oid, "is_active": {"$ne": False}},
        {"_id": 1},
        sort=[("_id", 1)],
    )
    if any_branch:
        return any_branch["_id"]
    raise HTTPException(
        status_code=400,
        detail="La empresa no tiene sucursales activas. Crea una en Configuracion > Sucursales.",
    )


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
    return {"register": serialize_doc(reg)}


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
    expected_cash = round(
        float(reg.get("opening_amount", 0) or 0)
        + totals["totals_by_method"].get("cash", 0)
        - totals["egresos_cash"], 2
    )

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
        "egresos_by_method": totals["egresos_by_method"],
        "egresos_total": totals["egresos_total"],
        "egresos_cash": totals["egresos_cash"],
        "egresos_count": totals["egresos_count"],
        "egresos_detail": totals["egresos_detail"],
        "is_preview": True,
    })
    return serialize_doc(reg)


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

    # 2. Egresos (compras/gastos) creados en la ventana, en la sucursal.
    #    La salida de efectivo se resta del efectivo esperado (solo metodo 'cash').
    egresos_by_method = {"cash": 0.0, "card": 0.0, "transfer": 0.0, "check": 0.0, "other": 0.0}
    egresos_detail = []
    egresos_cursor = db.finance_entries.find({
        "company_id": company_id,
        "branch_id": branch_id,
        "type": "egreso",
        "is_voided": {"$ne": True},
        "created_at": {"$gte": opened_at_iso, "$lte": closed_at_iso},
    })
    async for e in egresos_cursor:
        method = e.get("payment_method", "cash") or "cash"
        if method not in egresos_by_method:
            method = "other"
        is_credit = bool(e.get("is_credit"))
        # Salida al momento de registrar: monto total (contado) o abono inicial (credito)
        out = float(e.get("amount_paid", 0) or 0) if is_credit else float(e.get("amount", 0) or 0)
        if out <= 0:
            continue
        egresos_by_method[method] += out
        egresos_detail.append({
            "entry_id": str(e["_id"]),
            "created_by": str(e.get("created_by")) if e.get("created_by") else None,
            "description": e.get("description", ""),
            "supplier_name": e.get("supplier_name", ""),
            "category": e.get("category", ""),
            "method": method,
            "amount": round(out, 2),
            "is_credit": is_credit,
            "created_at": e.get("created_at"),
        })
    egresos_total = round(sum(egresos_by_method.values()), 2)
    egresos_cash = round(egresos_by_method.get("cash", 0), 2)
    egresos_by_method = {k: round(v, 2) for k, v in egresos_by_method.items()}

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
        "egresos_by_method": egresos_by_method,
        "egresos_total": egresos_total,
        "egresos_cash": egresos_cash,
        "egresos_count": len(egresos_detail),
        "egresos_detail": egresos_detail,
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

    expected_cash = round(
        float(reg.get("opening_amount", 0) or 0)
        + totals["totals_by_method"].get("cash", 0)
        - totals["egresos_cash"], 2
    )
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
        "egresos_by_method": totals["egresos_by_method"],
        "egresos_total": totals["egresos_total"],
        "egresos_cash": totals["egresos_cash"],
        "egresos_count": totals["egresos_count"],
        "egresos_detail": totals["egresos_detail"],
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
    return {"message": "Caja cerrada", "register": serialize_doc(reg)}


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
    return [serialize_doc(r) for r in regs]


async def _build_report(user: dict, date_from: Optional[str], date_to: Optional[str], branch_id: Optional[str]) -> dict:
    """Agrega cierres de caja en un rango. Solo incluye cajas cerradas."""
    query = {"company_id": ObjectId(user["company_id"]), "status": "closed"}
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id") and user["role"] != "admin":
        query["branch_id"] = ObjectId(user["branch_id"])

    # Filter by closed_at date range (inclusive)
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = f"{date_from}T00:00:00"
        if date_to:
            rng["$lte"] = f"{date_to}T23:59:59.999999"
        query["closed_at"] = rng

    regs = await db.cash_registers.find(query).sort("closed_at", 1).to_list(1000)

    # Batch load branch names
    bids = list({r["branch_id"] for r in regs if r.get("branch_id")})
    branches_map = {}
    if bids:
        docs = await db.branches.find({"_id": {"$in": bids}}, {"name": 1}).to_list(len(bids))
        branches_map = {str(b["_id"]): b.get("name", "") for b in docs}

    totals_by_method = {"cash": 0.0, "card": 0.0, "transfer": 0.0, "check": 0.0, "other": 0.0}
    grand_total = 0.0
    grand_opening = 0.0
    grand_receivables = 0.0
    grand_diff = 0.0
    grand_egresos = 0.0
    grand_egresos_cash = 0.0
    diff_count = 0
    rows = []
    egresos_all = []

    for r in regs:
        _serialize(r)
        r["branch_name"] = branches_map.get(str(r.get("branch_id")), "")
        m = r.get("totals_by_method") or {}
        for k in totals_by_method:
            totals_by_method[k] += float(m.get(k, 0) or 0)
        grand_total += float(r.get("total_received", 0) or 0)
        grand_opening += float(r.get("opening_amount", 0) or 0)
        grand_receivables += float(r.get("receivables_total", 0) or 0)
        grand_egresos += float(r.get("egresos_total", 0) or 0)
        grand_egresos_cash += float(r.get("egresos_cash", 0) or 0)
        if r.get("cash_difference") is not None:
            grand_diff += float(r["cash_difference"])
            diff_count += 1
        for e in (r.get("egresos_detail") or []):
            egresos_all.append({
                "closed_at": r.get("closed_at"),
                "branch_name": r.get("branch_name"),
                "description": e.get("description", ""),
                "supplier_name": e.get("supplier_name", ""),
                "category": e.get("category", ""),
                "method": e.get("method", ""),
                "amount": float(e.get("amount", 0) or 0),
                "is_credit": bool(e.get("is_credit")),
            })
        rows.append({
            "_id": r.get("_id"),
            "branch_name": r.get("branch_name"),
            "opened_at": r.get("opened_at"),
            "closed_at": r.get("closed_at"),
            "opened_by_name": r.get("opened_by_name"),
            "closed_by_name": r.get("closed_by_name"),
            "opening_amount": float(r.get("opening_amount", 0) or 0),
            "total_received": float(r.get("total_received", 0) or 0),
            "expected_cash": r.get("expected_cash"),
            "counted_cash": r.get("counted_cash"),
            "cash_difference": r.get("cash_difference"),
            "totals_by_method": {k: float((m or {}).get(k, 0) or 0) for k in totals_by_method},
            "receivables_total": float(r.get("receivables_total", 0) or 0),
            "receivables_count": int(r.get("receivables_count", 0) or 0),
            "egresos_total": float(r.get("egresos_total", 0) or 0),
            "egresos_cash": float(r.get("egresos_cash", 0) or 0),
        })

    return {
        "date_from": date_from,
        "date_to": date_to,
        "branch_id": branch_id,
        "count": len(rows),
        "totals_by_method": {k: round(v, 2) for k, v in totals_by_method.items()},
        "grand_total_received": round(grand_total, 2),
        "grand_opening": round(grand_opening, 2),
        "grand_receivables_total": round(grand_receivables, 2),
        "grand_egresos_total": round(grand_egresos, 2),
        "grand_egresos_cash": round(grand_egresos_cash, 2),
        "grand_cash_difference": round(grand_diff, 2) if diff_count else None,
        "rows": rows,
        "egresos_detail": egresos_all,
    }


@router.get("/report")
async def cash_register_report(
    user: dict = Depends(get_current_user),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    branch_id: Optional[str] = None,
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return await _build_report(user, date_from, date_to, branch_id)


def _fmt_q(v) -> str:
    try:
        n = float(v or 0)
    except (TypeError, ValueError):
        n = 0.0
    return f"Q {n:,.2f}"


@router.get("/report/pdf")
async def cash_register_report_pdf(
    user: dict = Depends(get_current_user),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    branch_id: Optional[str] = None,
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    data = await _build_report(user, date_from, date_to, branch_id)

    # Company name
    company = await db.companies.find_one(
        {"_id": ObjectId(user["company_id"])}, {"name": 1}
    )
    company_name = (company or {}).get("name", "Optica")

    branch_name = None
    if branch_id:
        b = await db.branches.find_one({"_id": ObjectId(branch_id)}, {"name": 1})
        branch_name = (b or {}).get("name")

    pdf_bytes = await asyncio.to_thread(
        _render_cash_report_pdf, data, company_name, branch_name, date_from, date_to
    )

    await log_audit("CASH_REGISTER_REPORT_PDF", actor_id=user["_id"], actor_email=user.get("email"),
                    metadata={"date_from": date_from, "date_to": date_to, "count": data["count"]})

    filename = f"reporte_cierres_{date_from or 'todo'}_{date_to or 'hoy'}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


def _render_cash_report_pdf(data: dict, company_name: str, branch_name: Optional[str],
                            date_from: Optional[str], date_to: Optional[str]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
        title=f"Reporte de Cierres de Caja - {company_name}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('t', parent=styles['Title'], fontSize=16, textColor=colors.HexColor('#0F4C3A'))
    small = ParagraphStyle('s', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#475569'))

    story = []
    story.append(Paragraph(f"Reporte de Cierres de Caja", title_style))
    story.append(Paragraph(f"<b>{company_name}</b>", styles['Normal']))
    rango = f"{date_from or '(inicio)'} al {date_to or 'hoy'}"
    story.append(Paragraph(f"Periodo: {rango}" + (f" - Sucursal: {branch_name}" if branch_name else ""), small))
    story.append(Paragraph(f"Generado: {datetime.now(timezone.utc).isoformat()[:19].replace('T', ' ')}", small))
    story.append(Spacer(1, 12))

    # Summary totals table
    tm = data["totals_by_method"]
    summary_data = [
        ["Concepto", "Monto"],
        ["Efectivo", _fmt_q(tm.get("cash"))],
        ["Transferencia", _fmt_q(tm.get("transfer"))],
        ["Tarjeta de credito", _fmt_q(tm.get("card"))],
        ["Cheque", _fmt_q(tm.get("check"))],
        ["Otros", _fmt_q(tm.get("other"))],
        ["TOTAL RECAUDADO", _fmt_q(data["grand_total_received"])],
        ["Egresos del turno (efectivo)", _fmt_q(data.get("grand_egresos_cash"))],
        ["Egresos del turno (total)", _fmt_q(data.get("grand_egresos_total"))],
        ["Cuentas por cobrar generadas", _fmt_q(data["grand_receivables_total"])],
        ["Fondo inicial acumulado", _fmt_q(data["grand_opening"])],
    ]
    if data.get("grand_cash_difference") is not None:
        summary_data.append(["Diferencia efectivo acumulada", _fmt_q(data["grand_cash_difference"])])
    t = Table(summary_data, colWidths=[3.2 * inch, 2.0 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F4C3A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor('#ECFDF5')),
        ('FONTNAME', (0, 6), (-1, 6), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 16))

    # Rows per cierre
    story.append(Paragraph(f"<b>Cierres del periodo ({data['count']})</b>", styles['Heading3']))
    story.append(Spacer(1, 4))

    if data["count"] == 0:
        story.append(Paragraph("Sin cierres en el periodo seleccionado.", small))
    else:
        row_data = [[
            "Cierre", "Sucursal", "Efectivo", "Transf.", "Tarjeta", "Cheque", "Total", "Cta x Cob"
        ]]
        for r in data["rows"]:
            row_data.append([
                (r.get("closed_at") or "")[:16].replace('T', ' '),
                r.get("branch_name") or "-",
                _fmt_q(r["totals_by_method"].get("cash")),
                _fmt_q(r["totals_by_method"].get("transfer")),
                _fmt_q(r["totals_by_method"].get("card")),
                _fmt_q(r["totals_by_method"].get("check")),
                _fmt_q(r["total_received"]),
                _fmt_q(r["receivables_total"]),
            ])
        tbl = Table(row_data, colWidths=[1.0 * inch, 1.0 * inch, 0.85 * inch, 0.85 * inch, 0.85 * inch, 0.75 * inch, 0.95 * inch, 0.95 * inch])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F4C3A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#CBD5E1')),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(tbl)

    # Detalle de egresos del periodo (linea por linea)
    egresos = data.get("egresos_detail") or []
    if egresos:
        story.append(Spacer(1, 16))
        story.append(Paragraph(
            f"<b>Detalle de egresos del periodo ({len(egresos)} - {_fmt_q(data.get('grand_egresos_total'))})</b>",
            styles['Heading3']))
        story.append(Spacer(1, 4))
        eg_data = [["Cierre", "Sucursal", "Descripcion", "Proveedor", "Metodo", "Monto"]]
        for e in egresos:
            desc = (e.get("description") or "-")
            if e.get("is_credit"):
                desc = f"{desc} (credito)"
            eg_data.append([
                (e.get("closed_at") or "")[:16].replace('T', ' '),
                e.get("branch_name") or "-",
                desc[:40],
                e.get("supplier_name") or "-",
                _METHOD_LABELS.get(e.get("method"), e.get("method") or "-"),
                _fmt_q(e.get("amount")),
            ])
        eg_tbl = Table(eg_data, colWidths=[1.05 * inch, 0.95 * inch, 1.85 * inch, 1.2 * inch, 0.9 * inch, 0.85 * inch])
        eg_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7F1D1D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#CBD5E1')),
            ('ALIGN', (5, 0), (5, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEF2F2')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(eg_tbl)

    doc.build(story)
    return buf.getvalue()


def _render_single_cierre_pdf(reg: dict, company_name: str, branch_name: Optional[str]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch,
        title=f"Arqueo de Caja - {company_name}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('t', parent=styles['Title'], fontSize=16, textColor=colors.HexColor('#0F4C3A'))
    small = ParagraphStyle('s', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#475569'))
    label = ParagraphStyle('lbl', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#334155'))

    story = []
    story.append(Paragraph("Arqueo de Caja (Cierre)", title_style))
    story.append(Paragraph(f"<b>{company_name}</b>" + (f" - {branch_name}" if branch_name else ""), styles['Normal']))
    opened = (reg.get("opened_at") or "")[:16].replace('T', ' ')
    closed = (reg.get("closed_at") or "")[:16].replace('T', ' ') if reg.get("closed_at") else "En curso"
    story.append(Paragraph(f"Apertura: {opened} por {reg.get('opened_by_name','-')}", small))
    story.append(Paragraph(f"Cierre: {closed}" + (f" por {reg.get('closed_by_name','-')}" if reg.get('closed_at') else ""), small))
    story.append(Paragraph(f"Generado: {datetime.now(timezone.utc).isoformat()[:19].replace('T', ' ')}", small))
    story.append(Spacer(1, 12))

    tm = reg.get("totals_by_method") or {}
    summary_data = [
        ["Concepto", "Monto"],
        ["Fondo inicial", _fmt_q(reg.get("opening_amount"))],
        ["Efectivo (ventas)", _fmt_q(tm.get("cash"))],
        ["Transferencia", _fmt_q(tm.get("transfer"))],
        ["Tarjeta", _fmt_q(tm.get("card"))],
        ["Cheque", _fmt_q(tm.get("check"))],
        ["Otros", _fmt_q(tm.get("other"))],
        ["TOTAL RECAUDADO", _fmt_q(reg.get("total_received"))],
        ["Egresos del turno (efectivo)", _fmt_q(reg.get("egresos_cash"))],
        ["Egresos del turno (total)", _fmt_q(reg.get("egresos_total"))],
        ["EFECTIVO ESPERADO", _fmt_q(reg.get("expected_cash"))],
    ]
    if reg.get("counted_cash") is not None:
        summary_data.append(["Efectivo contado", _fmt_q(reg.get("counted_cash"))])
        summary_data.append(["Diferencia", _fmt_q(reg.get("cash_difference"))])
    if reg.get("receivables_total"):
        summary_data.append([f"Cuentas por cobrar ({int(reg.get('receivables_count', 0) or 0)})", _fmt_q(reg.get("receivables_total"))])
    t = Table(summary_data, colWidths=[3.4 * inch, 2.0 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F4C3A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor('#ECFDF5')),
        ('FONTNAME', (0, 7), (-1, 7), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 10), (-1, 10), colors.HexColor('#ECFDF5')),
        ('FONTNAME', (0, 10), (-1, 10), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)

    # Egresos linea por linea
    egresos = reg.get("egresos_detail") or []
    story.append(Spacer(1, 16))
    story.append(Paragraph(f"<b>Egresos del turno ({len(egresos)})</b>", styles['Heading3']))
    story.append(Spacer(1, 4))
    if not egresos:
        story.append(Paragraph("Sin egresos registrados en el turno.", small))
    else:
        eg_data = [["Hora", "Descripcion", "Proveedor", "Metodo", "Monto"]]
        for e in egresos:
            desc = (e.get("description") or "-")
            if e.get("is_credit"):
                desc = f"{desc} (credito)"
            eg_data.append([
                (e.get("created_at") or "")[11:16],
                desc[:44],
                e.get("supplier_name") or "-",
                _METHOD_LABELS.get(e.get("method"), e.get("method") or "-"),
                _fmt_q(e.get("amount")),
            ])
        eg_tbl = Table(eg_data, colWidths=[0.7 * inch, 2.5 * inch, 1.5 * inch, 1.0 * inch, 0.9 * inch])
        eg_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7F1D1D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#CBD5E1')),
            ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEF2F2')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(eg_tbl)

    # Cuentas por cobrar generadas
    recv = [s for s in (reg.get("sales_in_window") or []) if (s.get("balance") or 0) > 0]
    if recv:
        story.append(Spacer(1, 16))
        story.append(Paragraph(f"<b>Cuentas por cobrar generadas ({len(recv)})</b>", styles['Heading3']))
        story.append(Spacer(1, 4))
        rc_data = [["Cliente", "Total", "Pagado", "Saldo"]]
        for s in recv:
            rc_data.append([
                (s.get("patient_name") or "Consumidor final")[:40],
                _fmt_q(s.get("total")), _fmt_q(s.get("amount_paid")), _fmt_q(s.get("balance")),
            ])
        rc_tbl = Table(rc_data, colWidths=[3.0 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch])
        rc_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#B45309')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#CBD5E1')),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FFFBEB')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(rc_tbl)

    if reg.get("closing_notes"):
        story.append(Spacer(1, 14))
        story.append(Paragraph("<b>Notas de cierre</b>", label))
        story.append(Paragraph(str(reg.get("closing_notes")), small))

    doc.build(story)
    return buf.getvalue()


@router.get("/{register_id}/pdf")
async def cash_register_single_pdf(register_id: str, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        oid = ObjectId(register_id)
    except Exception:
        raise HTTPException(status_code=400, detail="register_id invalido")
    reg = await db.cash_registers.find_one({"_id": oid})
    if not reg or str(reg["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Caja no encontrada")

    branch_oid = reg.get("branch_id")
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

    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])}, {"name": 1})
    company_name = (company or {}).get("name", "Optica")
    branch_name = None
    if branch_oid:
        b = await db.branches.find_one({"_id": branch_oid}, {"name": 1})
        branch_name = (b or {}).get("name")

    pdf_bytes = await asyncio.to_thread(_render_single_cierre_pdf, reg, company_name, branch_name)

    await log_audit("CASH_REGISTER_CIERRE_PDF", actor_id=user["_id"], actor_email=user.get("email"),
                    metadata={"register_id": register_id})

    filename = f"arqueo_caja_{(reg.get('closed_at') or reg.get('opened_at') or '')[:10]}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )


def _render_cierre_egresos_xlsx(reg: dict, egresos: list, company_name: str, branch_name: Optional[str]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="7F1D1D", end_color="7F1D1D", fill_type="solid")
    money = 'Q #,##0.00'

    wb = Workbook()
    ws = wb.active
    ws.title = "Egresos del turno"
    ws.append([company_name])
    ws["A1"].font = Font(bold=True, size=14, color="1B2A49")
    opened = (reg.get("opened_at") or "")[:16].replace("T", " ")
    closed = (reg.get("closed_at") or "")[:16].replace("T", " ") if reg.get("closed_at") else "En curso"
    sub = f"Egresos del turno  |  Apertura {opened}  ->  Cierre {closed}"
    if branch_name:
        sub += f"  |  {branch_name}"
    ws.append([sub])
    ws["A2"].font = Font(size=10, color="666666")
    ws.append([])
    ws.append(["Fecha", "Hora", "Descripcion", "Proveedor", "Categoria", "Metodo", "Credito", "Monto"])
    for cell in ws[4]:
        cell.font = header_font
        cell.fill = header_fill

    for e in egresos:
        ca = e.get("created_at") or ""
        ws.append([
            ca[:10], ca[11:16],
            e.get("description", ""), e.get("supplier_name", ""),
            e.get("category", ""), _METHOD_LABELS.get(e.get("method"), e.get("method") or ""),
            "Si" if e.get("is_credit") else "No",
            float(e.get("amount", 0) or 0),
        ])

    total = sum(float(e.get("amount", 0) or 0) for e in egresos)
    total_cash = sum(float(e.get("amount", 0) or 0) for e in egresos if (e.get("method") or "cash") == "cash")
    ws.append(["", "", "", "", "", "", "TOTAL", total])
    ws.append(["", "", "", "", "", "", "En efectivo", total_cash])
    for r in (ws.max_row - 1, ws.max_row):
        for cell in ws[r]:
            cell.font = Font(bold=True)
    for r in range(5, ws.max_row + 1):
        ws.cell(row=r, column=8).number_format = money
    for col, w in zip("ABCDEFGH", [12, 8, 36, 24, 16, 14, 10, 16]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A5"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@router.get("/{register_id}/egresos.xlsx")
async def cash_register_egresos_xlsx(register_id: str, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        oid = ObjectId(register_id)
    except Exception:
        raise HTTPException(status_code=400, detail="register_id invalido")
    reg = await db.cash_registers.find_one({"_id": oid})
    if not reg or str(reg["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Caja no encontrada")

    branch_oid = reg.get("branch_id")
    if reg.get("status") == "open":
        totals = await _compute_close_totals(
            reg["company_id"], branch_oid, reg["opened_at"], datetime.now(timezone.utc).isoformat()
        )
        egresos = totals["egresos_detail"]
    else:
        egresos = reg.get("egresos_detail") or []

    _serialize(reg)
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])}, {"name": 1})
    company_name = (company or {}).get("name", "Optica")
    branch_name = None
    if branch_oid:
        b = await db.branches.find_one({"_id": branch_oid}, {"name": 1})
        branch_name = (b or {}).get("name")

    xlsx_bytes = await asyncio.to_thread(_render_cierre_egresos_xlsx, reg, egresos, company_name, branch_name)

    await log_audit("CASH_REGISTER_EGRESOS_XLSX", actor_id=user["_id"], actor_email=user.get("email"),
                    metadata={"register_id": register_id, "count": len(egresos)})

    filename = f"egresos_turno_{(reg.get('closed_at') or reg.get('opened_at') or '')[:10]}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


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
    return serialize_doc(reg)
