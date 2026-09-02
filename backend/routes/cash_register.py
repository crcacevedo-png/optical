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
    diff_count = 0
    rows = []

    for r in regs:
        _serialize(r)
        r["branch_name"] = branches_map.get(str(r.get("branch_id")), "")
        m = r.get("totals_by_method") or {}
        for k in totals_by_method:
            totals_by_method[k] += float(m.get(k, 0) or 0)
        grand_total += float(r.get("total_received", 0) or 0)
        grand_opening += float(r.get("opening_amount", 0) or 0)
        grand_receivables += float(r.get("receivables_total", 0) or 0)
        if r.get("cash_difference") is not None:
            grand_diff += float(r["cash_difference"])
            diff_count += 1
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
        "grand_cash_difference": round(grand_diff, 2) if diff_count else None,
        "rows": rows,
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
        ('BACKGROUND', (0, -4), (-1, -4), colors.HexColor('#ECFDF5')),
        ('FONTNAME', (0, -4), (-1, -4), 'Helvetica-Bold'),
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

    doc.build(story)
    return buf.getvalue()


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
