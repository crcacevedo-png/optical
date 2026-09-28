from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from typing import Optional
import io
import asyncio

from db import db, serialize_doc
from auth_utils import get_current_user
from models import FinanceEntryCreate
from audit import log_audit
from pydantic import BaseModel

router = APIRouter(prefix="/finance", tags=["Finanzas"])


async def _resolve_branch_id(user: dict) -> Optional[ObjectId]:
    """Sucursal a la que se atribuye un movimiento financiero.
    Vendedores/doctores usan su branch; admins sin branch_id usan la sucursal
    principal (o la primera activa) — consistente con la caja para que los
    egresos en efectivo se reflejen en el arqueo del turno del admin."""
    if user.get("branch_id"):
        return ObjectId(user["branch_id"])
    company_oid = ObjectId(user["company_id"])
    main = await db.branches.find_one(
        {"company_id": company_oid, "is_active": {"$ne": False}, "is_main": True}, {"_id": 1}
    )
    if main:
        return main["_id"]
    any_branch = await db.branches.find_one(
        {"company_id": company_oid, "is_active": {"$ne": False}}, {"_id": 1}, sort=[("_id", 1)]
    )
    return any_branch["_id"] if any_branch else None


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
    for e in entries:
        serialize_doc(e)
        for p in e.get("payments", []) or []:
            if isinstance(p.get("created_by"), ObjectId):
                p["created_by"] = str(p["created_by"])
    return [serialize_doc(e) for e in entries]

@router.post("")
async def create_finance_entry(data: FinanceEntryCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    branch_oid = await _resolve_branch_id(user)
    entry_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": branch_oid,
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
    elif data.type == "egreso" and (data.category == "suppliers" or data.is_credit):
        raise HTTPException(status_code=400, detail="Selecciona un proveedor para egresos de la categoria Proveedores.")

    # Metodo de pago del egreso (para el arqueo de caja). Default efectivo.
    if data.type == "egreso":
        pm = (data.payment_method or "cash")
        if pm not in ("cash", "card", "transfer", "check", "other"):
            pm = "cash"
        entry_doc["payment_method"] = pm

    # Egreso a credito (devengado): el monto total cuenta como gasto desde el registro;
    # los abonos solo bajan el saldo (no generan nuevos movimientos).
    if data.type == "egreso" and data.is_credit:
        total = float(data.amount)
        paid = max(0.0, min(float(data.amount_paid or 0), total))
        balance = round(total - paid, 2)
        entry_doc["is_credit"] = True
        entry_doc["amount_paid"] = round(paid, 2)
        entry_doc["balance"] = max(0.0, balance)
        entry_doc["status"] = "pagado" if balance <= 0 else "pendiente"
        entry_doc["due_date"] = data.due_date
        entry_doc["payments"] = []
        if paid > 0:
            entry_doc["payments"].append({
                "method": entry_doc.get("payment_method", "cash"),
                "amount": round(paid, 2),
                "note": "Abono inicial",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": ObjectId(user["_id"]),
            })

    result = await db.finance_entries.insert_one(entry_doc)
    return {"_id": str(result.inserted_id), "message": "Entrada registrada"}


class VoidRequest(BaseModel):
    reason: str


@router.post("/{entry_id}/void")
async def void_finance_entry(entry_id: str, data: VoidRequest, user: dict = Depends(get_current_user)):
    """Anula (soft-void) un movimiento financiero. Queda visible tachado en el
    historial y deja de contar en totales, cuentas por pagar y caja. Solo el
    administrador o quien lo registro pueden anular."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        oid = ObjectId(entry_id)
    except Exception:
        raise HTTPException(status_code=400, detail="entry_id invalido")
    entry = await db.finance_entries.find_one({"_id": oid})
    if not entry or str(entry["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    is_admin = user["role"] == "admin"
    is_creator = str(entry.get("created_by")) == user["_id"]
    if not (is_admin or is_creator):
        raise HTTPException(status_code=403, detail="Solo el administrador o quien lo registro puede anular este movimiento.")
    if entry.get("is_voided"):
        raise HTTPException(status_code=400, detail="El movimiento ya esta anulado.")
    reason = (data.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Indica el motivo de la anulacion.")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.finance_entries.update_one(
        {"_id": oid},
        {"$set": {
            "is_voided": True,
            "voided_at": now_iso,
            "voided_by": ObjectId(user["_id"]),
            "voided_by_name": user.get("name", ""),
            "void_reason": reason,
        }},
    )
    await log_audit("FINANCE_ENTRY_VOIDED", actor_id=user["_id"], actor_email=user.get("email"),
                    metadata={"entry_id": entry_id, "type": entry.get("type"),
                              "amount": entry.get("amount"), "reason": reason})
    return {"ok": True, "id": entry_id, "message": "Movimiento anulado"}


@router.get("/payables")
async def list_payables(
    user: dict = Depends(get_current_user),
    branch_id: Optional[str] = None,
    limit: int = 300,
):
    """Egresos a credito con saldo pendiente (cuentas por pagar)."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    query = {
        "company_id": ObjectId(user["company_id"]),
        "type": "egreso",
        "is_credit": True,
        "balance": {"$gt": 0},
        "is_voided": {"$ne": True},
    }
    if branch_id:
        try:
            query["branch_id"] = ObjectId(branch_id)
        except Exception:
            raise HTTPException(status_code=400, detail="branch_id invalido")
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])

    entries = await db.finance_entries.find(query).sort("created_at", 1).limit(limit).to_list(limit)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total_pending = 0.0
    by_supplier = {}
    for e in entries:
        serialize_doc(e)
        for p in e.get("payments", []) or []:
            if isinstance(p.get("created_by"), ObjectId):
                p["created_by"] = str(p["created_by"])
        try:
            created = datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
            e["days_pending"] = (datetime.now(timezone.utc) - created).days
        except Exception:
            e["days_pending"] = 0
        e["is_overdue"] = bool(e.get("due_date") and e["due_date"] < today)
        if e.get("due_date"):
            try:
                due_d = datetime.strptime(e["due_date"][:10], "%Y-%m-%d").date()
                e["days_until_due"] = (due_d - datetime.now(timezone.utc).date()).days
                e["is_due_soon"] = 0 <= e["days_until_due"] <= 7
            except Exception:
                e["days_until_due"] = None
                e["is_due_soon"] = False
        else:
            e["days_until_due"] = None
            e["is_due_soon"] = False
        bal = float(e.get("balance", 0) or 0)
        total_pending += bal
        name = e.get("supplier_name") or "(sin proveedor)"
        by_supplier[name] = round(by_supplier.get(name, 0) + bal, 2)

    supplier_summary = sorted(
        [{"name": k, "balance": v} for k, v in by_supplier.items()],
        key=lambda x: -x["balance"],
    )
    return {
        "items": [serialize_doc(e) for e in entries],
        "total_pending": round(total_pending, 2),
        "count": len(entries),
        "by_supplier": supplier_summary,
    }


@router.get("/payables/alerts")
async def payables_alerts(
    user: dict = Depends(get_current_user),
    days: int = 7,
    branch_id: Optional[str] = None,
):
    """Resumen de cuentas por pagar vencidas o por vencer (para avisar al admin)."""
    if user["role"] == "superadmin":
        return {"days": days, "overdue": {"count": 0, "total": 0.0}, "due_soon": {"count": 0, "total": 0.0}}

    query = {
        "company_id": ObjectId(user["company_id"]),
        "type": "egreso",
        "is_credit": True,
        "balance": {"$gt": 0},
        "is_voided": {"$ne": True},
        "due_date": {"$exists": True, "$ne": None},
    }
    if branch_id:
        try:
            query["branch_id"] = ObjectId(branch_id)
        except Exception:
            raise HTTPException(status_code=400, detail="branch_id invalido")
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    limit_date = (datetime.now(timezone.utc).date() + timedelta(days=max(0, days))).strftime("%Y-%m-%d")

    overdue_count = overdue_total = 0
    due_soon_count = due_soon_total = 0
    async for e in db.finance_entries.find(query, {"balance": 1, "due_date": 1}):
        bal = float(e.get("balance", 0) or 0)
        dd = e.get("due_date")
        if dd < today:
            overdue_count += 1
            overdue_total += bal
        elif dd <= limit_date:
            due_soon_count += 1
            due_soon_total += bal
    return {
        "days": days,
        "overdue": {"count": overdue_count, "total": round(overdue_total, 2)},
        "due_soon": {"count": due_soon_count, "total": round(due_soon_total, 2)},
    }


@router.post("/payables/{entry_id}/payment")
async def add_payable_payment(
    entry_id: str,
    amount: float = Query(..., gt=0),
    method: str = Query("cash"),
    note: str = Query(""),
    user: dict = Depends(get_current_user),
):
    """Registra un abono a un egreso a credito. Solo baja el saldo (devengado)."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        oid = ObjectId(entry_id)
    except Exception:
        raise HTTPException(status_code=400, detail="entry_id invalido")
    entry = await db.finance_entries.find_one({"_id": oid, "type": "egreso", "is_credit": True, "is_voided": {"$ne": True}})
    if not entry or str(entry["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Egreso no encontrado")

    balance = float(entry.get("balance", 0) or 0)
    if amount > balance + 0.001:
        raise HTTPException(status_code=400, detail="El abono excede el saldo pendiente.")

    now_iso = datetime.now(timezone.utc).isoformat()
    new_paid = round(float(entry.get("amount_paid", 0) or 0) + float(amount), 2)
    new_balance = round(float(entry["amount"]) - new_paid, 2)
    status = "pagado" if new_balance <= 0 else "pendiente"
    await db.finance_entries.update_one(
        {"_id": oid},
        {
            "$push": {"payments": {
                "method": method, "amount": float(amount), "note": note or "",
                "created_at": now_iso, "created_by": ObjectId(user["_id"]),
            }},
            "$set": {"amount_paid": new_paid, "balance": max(0.0, new_balance), "status": status},
        },
    )
    return {"message": "Abono registrado", "new_balance": max(0.0, new_balance), "status": status}

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
    
    query = {"company_id": ObjectId(user["company_id"]), "is_voided": {"$ne": True}}
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

@router.get("/purchases-report.xlsx")
async def purchases_report_xlsx(
    user: dict = Depends(get_current_user),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[str] = None,
):
    """Reporte de compras: total pagado por proveedor en el periodo (Excel)."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    d_from = date_from or month_start
    d_to = date_to or today

    query = {"company_id": ObjectId(user["company_id"]), "type": "egreso",
             "is_voided": {"$ne": True},
             "supplier_id": {"$exists": True, "$ne": None},
             "date": {"$gte": d_from, "$lte": d_to}}
    if branch_id:
        try:
            query["branch_id"] = ObjectId(branch_id)
        except Exception:
            raise HTTPException(status_code=400, detail="branch_id invalido")
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])

    entries = await db.finance_entries.find(query).sort("date", -1).to_list(5000)
    for e in entries:
        serialize_doc(e)
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])}, {"name": 1}) or {}

    xlsx_bytes = await asyncio.to_thread(_render_purchases_xlsx, entries, company.get("name", "Cortexia Optical"), d_from, d_to)
    filename = f"compras-proveedores-{d_from}-a-{d_to}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _render_purchases_xlsx(entries: list, company_name: str, d_from: str, d_to: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1B2A49", end_color="1B2A49", fill_type="solid")
    money = 'Q #,##0.00'

    # Agrupar por proveedor
    by_supplier = {}
    for e in entries:
        name = e.get("supplier_name") or "(sin nombre)"
        if name not in by_supplier:
            by_supplier[name] = {"total": 0.0, "count": 0}
        by_supplier[name]["total"] += float(e.get("amount", 0) or 0)
        by_supplier[name]["count"] += 1
    ranked = sorted(by_supplier.items(), key=lambda kv: -kv[1]["total"])
    grand_total = sum(v["total"] for _, v in ranked)

    wb = Workbook()
    # Hoja 1: Resumen por proveedor
    ws = wb.active
    ws.title = "Por Proveedor"
    ws.append([company_name])
    ws["A1"].font = Font(bold=True, size=14, color="1B2A49")
    ws.append([f"Compras por proveedor  |  {d_from} a {d_to}"])
    ws["A2"].font = Font(size=10, color="666666")
    ws.append([])
    ws.append(["Proveedor", "No. de egresos", "Total pagado"])
    for cell in ws[4]:
        cell.font = header_font
        cell.fill = header_fill
    for name, v in ranked:
        ws.append([name, v["count"], v["total"]])
    ws.append(["TOTAL", sum(v["count"] for _, v in ranked), grand_total])
    total_row = ws.max_row
    for cell in ws[total_row]:
        cell.font = Font(bold=True)
    for r in range(5, ws.max_row + 1):
        ws.cell(row=r, column=3).number_format = money
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 18

    # Hoja 2: Detalle de compras
    ws2 = wb.create_sheet("Detalle")
    ws2.append(["Fecha", "Proveedor", "Categoria", "Descripcion", "Referencia", "Monto"])
    for cell in ws2[1]:
        cell.font = header_font
        cell.fill = header_fill
    for e in entries:
        ws2.append([
            e.get("date", ""),
            e.get("supplier_name", ""),
            e.get("category", ""),
            e.get("description", ""),
            e.get("reference", ""),
            float(e.get("amount", 0) or 0),
        ])
    for r in range(2, ws2.max_row + 1):
        ws2.cell(row=r, column=6).number_format = money
    for col, w in zip("ABCDEF", [12, 30, 16, 40, 18, 16]):
        ws2.column_dimensions[col].width = w
    ws2.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


_EXPENSE_CATEGORY_LABELS = {
    'payroll': 'Planilla', 'rent': 'Alquiler', 'utilities': 'Servicios',
    'suppliers': 'Proveedores', 'marketing': 'Marketing',
    'maintenance': 'Mantenimiento', 'other_expense': 'Otros Gastos',
}
_EXP_METHOD_LABELS = {
    'cash': 'Efectivo', 'card': 'Tarjeta', 'transfer': 'Transferencia',
    'check': 'Cheque', 'other': 'Otro',
}


@router.get("/expenses-report.xlsx")
async def expenses_report_xlsx(
    user: dict = Depends(get_current_user),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[str] = None,
):
    """Reporte de TODOS los egresos entre dos fechas (cierre contable). Excluye anulados."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    d_from = date_from or month_start
    d_to = date_to or today

    query = {"company_id": ObjectId(user["company_id"]), "type": "egreso",
             "is_voided": {"$ne": True},
             "date": {"$gte": d_from, "$lte": d_to}}
    if branch_id:
        try:
            query["branch_id"] = ObjectId(branch_id)
        except Exception:
            raise HTTPException(status_code=400, detail="branch_id invalido")
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])

    entries = await db.finance_entries.find(query).sort("date", -1).to_list(10000)
    for e in entries:
        serialize_doc(e)
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])}, {"name": 1}) or {}

    xlsx_bytes = await asyncio.to_thread(_render_expenses_xlsx, entries, company.get("name", "Cortexia Optical"), d_from, d_to)

    await log_audit("FINANCE_EXPENSES_REPORT", actor_id=user["_id"], actor_email=user.get("email"),
                    metadata={"date_from": d_from, "date_to": d_to, "count": len(entries)})

    filename = f"egresos-{d_from}-a-{d_to}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _render_expenses_xlsx(entries: list, company_name: str, d_from: str, d_to: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="7F1D1D", end_color="7F1D1D", fill_type="solid")
    money = 'Q #,##0.00'

    by_cat, by_method, total = {}, {}, 0.0
    for e in entries:
        amt = float(e.get("amount", 0) or 0)
        total += amt
        c = _EXPENSE_CATEGORY_LABELS.get(e.get("category"), e.get("category") or "—")
        by_cat[c] = round(by_cat.get(c, 0) + amt, 2)
        m = _EXP_METHOD_LABELS.get(e.get("payment_method"), e.get("payment_method") or "Efectivo")
        by_method[m] = round(by_method.get(m, 0) + amt, 2)

    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen"
    ws.append([company_name]); ws["A1"].font = Font(bold=True, size=14, color="1B2A49")
    ws.append([f"Egresos  |  {d_from} a {d_to}"]); ws["A2"].font = Font(size=10, color="666666")
    ws.append([])
    ws.append(["TOTAL EGRESOS", round(total, 2)])
    ws["A4"].font = Font(bold=True, size=12); ws["B4"].font = Font(bold=True, size=12); ws["B4"].number_format = money
    ws.append([])
    ws.append(["Por Categoria", "Total"])
    for cell in ws[ws.max_row]:
        cell.font = header_font; cell.fill = header_fill
    for name, v in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        ws.append([name, v]); ws.cell(row=ws.max_row, column=2).number_format = money
    ws.append([])
    ws.append(["Por Metodo de Pago", "Total"])
    for cell in ws[ws.max_row]:
        cell.font = header_font; cell.fill = header_fill
    for name, v in sorted(by_method.items(), key=lambda kv: -kv[1]):
        ws.append([name, v]); ws.cell(row=ws.max_row, column=2).number_format = money
    ws.column_dimensions["A"].width = 28; ws.column_dimensions["B"].width = 18

    ws2 = wb.create_sheet("Detalle")
    ws2.append(["Fecha", "Categoria", "Proveedor", "Descripcion", "Metodo", "Credito", "Pagado", "Saldo", "Referencia", "Monto"])
    for cell in ws2[1]:
        cell.font = header_font; cell.fill = header_fill
    for e in entries:
        is_credit = bool(e.get("is_credit"))
        ws2.append([
            e.get("date", ""),
            _EXPENSE_CATEGORY_LABELS.get(e.get("category"), e.get("category") or ""),
            e.get("supplier_name", ""),
            e.get("description", ""),
            _EXP_METHOD_LABELS.get(e.get("payment_method"), e.get("payment_method") or ""),
            "Si" if is_credit else "No",
            (float(e.get("amount_paid", 0) or 0) if is_credit else float(e.get("amount", 0) or 0)),
            (float(e.get("balance", 0) or 0) if is_credit else 0.0),
            e.get("reference", ""),
            float(e.get("amount", 0) or 0),
        ])
    for r in range(2, ws2.max_row + 1):
        for col in (7, 8, 10):
            ws2.cell(row=r, column=col).number_format = money
    for col, w in zip("ABCDEFGHIJ", [12, 16, 24, 34, 14, 8, 12, 12, 16, 14]):
        ws2.column_dimensions[col].width = w
    ws2.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


_INCOME_CATEGORY_LABELS = {
    'sales': 'Ventas', 'ventas': 'Ventas', 'services': 'Servicios', 'other_income': 'Otros Ingresos',
}


async def _compute_income_statement(user: dict, date_from: Optional[str], date_to: Optional[str], branch_id: Optional[str]) -> dict:
    """Estado de Resultados (P&L) en BASE CAJA:
    - Ingresos: entradas type='ingreso' por fecha (ya son base caja: una por pago real).
    - Egresos de contado: type='egreso' no credito, por fecha, monto total.
    - Egresos a credito: SOLO los abonos (payments[]) cuya fecha de pago cae en el rango.
    Excluye anulados (is_voided)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    d_from = date_from or month_start
    d_to = date_to or today

    base = {"company_id": ObjectId(user["company_id"]), "is_voided": {"$ne": True}}
    if branch_id:
        try:
            base["branch_id"] = ObjectId(branch_id)
        except Exception:
            raise HTTPException(status_code=400, detail="branch_id invalido")
    elif user.get("branch_id"):
        base["branch_id"] = ObjectId(user["branch_id"])

    income_by_cat: dict = {}
    async for e in db.finance_entries.find({**base, "type": "ingreso", "date": {"$gte": d_from, "$lte": d_to}}):
        c = e.get("category") or "other_income"
        income_by_cat[c] = round(income_by_cat.get(c, 0) + float(e.get("amount", 0) or 0), 2)

    expense_by_cat: dict = {}
    async for e in db.finance_entries.find({**base, "type": "egreso", "is_credit": {"$ne": True}, "date": {"$gte": d_from, "$lte": d_to}}):
        c = e.get("category") or "other_expense"
        expense_by_cat[c] = round(expense_by_cat.get(c, 0) + float(e.get("amount", 0) or 0), 2)

    # Egresos a credito: abonos pagados dentro del rango (base caja)
    async for e in db.finance_entries.find({**base, "type": "egreso", "is_credit": True}):
        c = e.get("category") or "other_expense"
        for p in e.get("payments", []) or []:
            pd = (p.get("created_at") or "")[:10]
            if d_from <= pd <= d_to:
                expense_by_cat[c] = round(expense_by_cat.get(c, 0) + float(p.get("amount", 0) or 0), 2)

    income_rows = [{"category": k, "label": _INCOME_CATEGORY_LABELS.get(k, k), "amount": v}
                   for k, v in sorted(income_by_cat.items(), key=lambda kv: -kv[1])]
    expense_rows = [{"category": k, "label": _EXPENSE_CATEGORY_LABELS.get(k, k), "amount": v}
                    for k, v in sorted(expense_by_cat.items(), key=lambda kv: -kv[1])]
    total_income = round(sum(income_by_cat.values()), 2)
    total_expense = round(sum(expense_by_cat.values()), 2)
    return {
        "period": {"from": d_from, "to": d_to},
        "basis": "caja",
        "income": income_rows,
        "expenses": expense_rows,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_profit": round(total_income - total_expense, 2),
    }


@router.get("/income-statement")
async def income_statement(
    user: dict = Depends(get_current_user),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[str] = None,
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return await _compute_income_statement(user, date_from, date_to, branch_id)


@router.get("/profitability")
async def profitability(
    user: dict = Depends(get_current_user),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[str] = None,
):
    """Rentabilidad por productos vendidos (BASE DEVENGADO, por fecha de venta):
    margen = ingreso de venta − COGS (costo fotografiado en la venta). Distinto del
    flujo de caja neto (cobros − pagos). Solo cuenta ventas no canceladas y con costo
    registrado; los items sin costo se reportan aparte (no se puede calcular su margen)."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    d_from = date_from or month_start
    d_to = date_to or today

    q = {"company_id": ObjectId(user["company_id"]), "status": {"$ne": "cancelada"},
         "created_at": {"$gte": f"{d_from}T00:00:00", "$lte": f"{d_to}T23:59:59.999999"}}
    if branch_id:
        try:
            q["branch_id"] = ObjectId(branch_id)
        except Exception:
            raise HTTPException(status_code=400, detail="branch_id invalido")
    elif user.get("branch_id"):
        q["branch_id"] = ObjectId(user["branch_id"])

    revenue_with_cost = 0.0   # ingreso de items con costo conocido
    cogs = 0.0                # costo de la mercaderia vendida
    revenue_without_cost = 0.0
    items_without_cost = 0
    by_product: dict = {}

    async for s in db.sales.find(q):
        for it in s.get("items", []) or []:
            qty = float(it.get("quantity") or 1)
            price = float(it.get("price") or 0)
            line_rev = float(it.get("total")) if it.get("total") is not None else round(price * qty, 2)
            name = it.get("name") or "Item"
            pid = it.get("product_id")
            key = str(pid) if pid else f"manual::{name}"
            b = by_product.setdefault(key, {
                "product_id": str(pid) if pid else None, "name": name,
                "units": 0.0, "revenue": 0.0, "cogs": 0.0, "margin": 0.0, "has_cost": True,
            })
            b["units"] += qty
            b["revenue"] = round(b["revenue"] + line_rev, 2)
            uc = it.get("unit_cost")
            if uc is None:
                revenue_without_cost += line_rev
                items_without_cost += 1
                b["has_cost"] = False
            else:
                line_cost = round(float(uc) * qty, 2)
                cogs += line_cost
                revenue_with_cost += line_rev
                b["cogs"] = round(b["cogs"] + line_cost, 2)
                b["margin"] = round(b["margin"] + (line_rev - line_cost), 2)

    gross_margin = round(revenue_with_cost - cogs, 2)
    margin_pct = round((gross_margin / revenue_with_cost * 100), 1) if revenue_with_cost > 0 else 0.0

    products = []
    for b in by_product.values():
        b["revenue"] = round(b["revenue"], 2)
        b["margin_pct"] = round((b["margin"] / b["revenue"] * 100), 1) if (b["has_cost"] and b["revenue"] > 0) else None
        products.append(b)
    products.sort(key=lambda x: (x["margin"] if x["has_cost"] else -1), reverse=True)

    return {
        "period": {"from": d_from, "to": d_to},
        "basis": "devengado",
        "revenue_with_cost": round(revenue_with_cost, 2),
        "cogs": round(cogs, 2),
        "gross_margin": gross_margin,
        "gross_margin_pct": margin_pct,
        "revenue_without_cost": round(revenue_without_cost, 2),
        "items_without_cost": items_without_cost,
        "by_product": products,
    }


@router.get("/income-statement.xlsx")
async def income_statement_xlsx(
    user: dict = Depends(get_current_user),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[str] = None,
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    data = await _compute_income_statement(user, date_from, date_to, branch_id)
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])}, {"name": 1}) or {}
    xlsx_bytes = await asyncio.to_thread(_render_pl_xlsx, data, company.get("name", "Cortexia Optical"))
    await log_audit("FINANCE_INCOME_STATEMENT", actor_id=user["_id"], actor_email=user.get("email"),
                    metadata={"format": "xlsx", **data["period"]})
    p = data["period"]
    filename = f"estado-resultados-{p['from']}-a-{p['to']}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/income-statement.pdf")
async def income_statement_pdf(
    user: dict = Depends(get_current_user),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[str] = None,
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    data = await _compute_income_statement(user, date_from, date_to, branch_id)
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])}, {"name": 1}) or {}
    pdf_bytes = await asyncio.to_thread(_render_pl_pdf, data, company.get("name", "Cortexia Optical"))
    await log_audit("FINANCE_INCOME_STATEMENT", actor_id=user["_id"], actor_email=user.get("email"),
                    metadata={"format": "pdf", **data["period"]})
    p = data["period"]
    filename = f"estado-resultados-{p['from']}-a-{p['to']}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


def _render_pl_xlsx(data: dict, company_name: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    money = 'Q #,##0.00'
    green_fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
    red_fill = PatternFill(start_color="FEF2F2", end_color="FEF2F2", fill_type="solid")

    wb = Workbook()
    ws = wb.active
    ws.title = "Estado de Resultados"
    ws.append([company_name]); ws["A1"].font = Font(bold=True, size=14, color="1B2A49")
    p = data["period"]
    ws.append([f"Estado de Resultados (base caja)  |  {p['from']} a {p['to']}"]); ws["A2"].font = Font(size=10, color="666666")
    ws.append([])

    ws.append(["INGRESOS", ""]); r = ws.max_row
    ws[f"A{r}"].font = Font(bold=True, color="15803D"); ws[f"A{r}"].fill = green_fill; ws[f"B{r}"].fill = green_fill
    for row in data["income"]:
        ws.append([row["label"], row["amount"]]); ws.cell(row=ws.max_row, column=2).number_format = money
    ws.append(["Total ingresos", data["total_income"]]); r = ws.max_row
    ws[f"A{r}"].font = Font(bold=True); ws[f"B{r}"].font = Font(bold=True); ws[f"B{r}"].number_format = money
    ws.append([])

    ws.append(["EGRESOS", ""]); r = ws.max_row
    ws[f"A{r}"].font = Font(bold=True, color="B91C1C"); ws[f"A{r}"].fill = red_fill; ws[f"B{r}"].fill = red_fill
    for row in data["expenses"]:
        ws.append([row["label"], row["amount"]]); ws.cell(row=ws.max_row, column=2).number_format = money
    ws.append(["Total egresos", data["total_expense"]]); r = ws.max_row
    ws[f"A{r}"].font = Font(bold=True); ws[f"B{r}"].font = Font(bold=True); ws[f"B{r}"].number_format = money
    ws.append([])

    ws.append(["UTILIDAD NETA", data["net_profit"]]); r = ws.max_row
    ws[f"A{r}"].font = Font(bold=True, size=12); ws[f"B{r}"].font = Font(bold=True, size=12); ws[f"B{r}"].number_format = money
    ws.column_dimensions["A"].width = 30; ws.column_dimensions["B"].width = 18

    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def _render_pl_pdf(data: dict, company_name: str) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    def _q(v):
        try:
            return f"Q {float(v or 0):,.2f}"
        except (TypeError, ValueError):
            return "Q 0.00"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            title=f"Estado de Resultados - {company_name}")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('t', parent=styles['Title'], fontSize=16, textColor=colors.HexColor('#0F4C3A'))
    small = ParagraphStyle('s', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#475569'))

    p = data["period"]
    story = [
        Paragraph("Estado de Resultados", title_style),
        Paragraph(f"<b>{company_name}</b>", styles['Normal']),
        Paragraph(f"Base caja  |  Periodo: {p['from']} a {p['to']}", small),
        Paragraph(f"Generado: {datetime.now(timezone.utc).isoformat()[:19].replace('T', ' ')}", small),
        Spacer(1, 14),
    ]

    rows = [["Concepto", "Monto"]]
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F4C3A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    rows.append(["INGRESOS", ""])
    hdr_i = len(rows) - 1
    for row in data["income"]:
        rows.append([f"   {row['label']}", _q(row["amount"])])
    rows.append(["Total ingresos", _q(data["total_income"])])
    tot_i = len(rows) - 1
    rows.append(["EGRESOS", ""])
    hdr_e = len(rows) - 1
    for row in data["expenses"]:
        rows.append([f"   {row['label']}", _q(row["amount"])])
    rows.append(["Total egresos", _q(data["total_expense"])])
    tot_e = len(rows) - 1
    rows.append(["UTILIDAD NETA", _q(data["net_profit"])])
    net_i = len(rows) - 1

    style_cmds += [
        ('BACKGROUND', (0, hdr_i), (-1, hdr_i), colors.HexColor('#ECFDF5')),
        ('FONTNAME', (0, hdr_i), (-1, hdr_i), 'Helvetica-Bold'),
        ('BACKGROUND', (0, hdr_e), (-1, hdr_e), colors.HexColor('#FEF2F2')),
        ('FONTNAME', (0, hdr_e), (-1, hdr_e), 'Helvetica-Bold'),
        ('FONTNAME', (0, tot_i), (-1, tot_i), 'Helvetica-Bold'),
        ('FONTNAME', (0, tot_e), (-1, tot_e), 'Helvetica-Bold'),
        ('BACKGROUND', (0, net_i), (-1, net_i), colors.HexColor('#0F4C3A')),
        ('TEXTCOLOR', (0, net_i), (-1, net_i), colors.white),
        ('FONTNAME', (0, net_i), (-1, net_i), 'Helvetica-Bold'),
        ('FONTSIZE', (0, net_i), (-1, net_i), 12),
    ]
    t = Table(rows, colWidths=[3.8 * inch, 2.2 * inch])
    t.setStyle(TableStyle(style_cmds))
    story.append(t)
    doc.build(story)
    return buf.getvalue()


@router.get("/dashboard")
async def get_finance_dashboard(user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")

    query = {"company_id": ObjectId(user["company_id"]), "is_voided": {"$ne": True}, "date": {"$gte": month_start, "$lte": today}}
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
