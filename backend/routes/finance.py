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
    entry = await db.finance_entries.find_one({"_id": oid, "type": "egreso", "is_credit": True})
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
