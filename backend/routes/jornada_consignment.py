"""Jornadas Iter 3 - Consignacion (Excel) + Liquidacion + Reporte cierre.

Endpoints:
- POST /jornadas/{jid}/excel/preview  - sube archivo, retorna sugerencia de mapeo + preview
- POST /jornadas/{jid}/excel/import   - confirma mapeo, crea productos, insert jornada_stock
- GET  /jornadas/{jid}/excel/uploads  - historial de cargas
- POST /jornadas/{jid}/excel/{upload_id}/revert - reversion (si no hay ventas)
- GET  /jornadas/{jid}/liquidation    - calculo de liquidacion consignatario
- GET  /jornadas/{jid}/report.pdf     - reporte cierre PDF
- GET  /jornadas/{jid}/report.xlsx    - reporte cierre Excel

Colecciones nuevas:
- jornada_excel_uploads: {company_id, jornada_id, filename, sample_rows, mapping, rows_created, rows_linked, errors, status, created_at, created_by}
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel
import io
import re
import json
import hashlib

import openpyxl

from db import db, serialize_doc
from auth_utils import get_current_user
from audit import log_audit

router = APIRouter(prefix="/jornadas", tags=["Jornadas - Consignacion y Reporte"])


# ─── Helper: normalize monetary strings ────────────────────────────────
_NUMBER_RE = re.compile(r"[^\d\-.,]")

def _to_number(val) -> Optional[float]:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return None
    s = _NUMBER_RE.sub("", s)
    # Normalizar separador: si tiene coma Y punto, coma es miles.
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s and "." not in s:
        # Coma es decimal
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# Campos que puede mapear el archivo excel
FIELD_LABELS = {
    "code": ["codigo", "código", "sku", "id", "referencia", "item"],
    "description": ["descripcion", "descripción", "producto", "nombre", "articulo", "artículo"],
    "category": ["categoria", "categoría", "tipo"],
    "brand": ["marca"],
    "model": ["modelo"],
    "color": ["color"],
    "size": ["tamano", "tamaño", "medida", "talla"],
    "quantity": ["cantidad", "cant", "qty", "unidades", "stock"],
    "unit_cost": ["costo", "costo unitario", "precio costo", "coste"],
    "unit_price": ["precio", "precio venta", "precio publico", "precio público", "pvp"],
    "supplier": ["proveedor", "consignatario", "distribuidor"],
    "batch": ["lote", "referencia lote", "batch"],
}


def _suggest_mapping(headers: List[str]) -> dict:
    """Auto-mapea headers -> campos del sistema por similitud de palabras."""
    mapping = {}
    def _norm(h): return re.sub(r"[^a-zñ]", "", (h or "").lower())
    for field, labels in FIELD_LABELS.items():
        for idx, h in enumerate(headers):
            nh = _norm(h)
            if any(_norm(lb) == nh for lb in labels):
                mapping[field] = idx
                break
    return mapping


def _detect_header_row(sheet, max_scan: int = 15) -> int:
    """Busca la primera fila con >= 3 celdas no vacias (probablemente headers)."""
    for row_idx in range(1, min(max_scan, sheet.max_row) + 1):
        non_empty = sum(1 for c in sheet[row_idx] if c.value not in (None, ""))
        if non_empty >= 3:
            return row_idx
    return 1


async def _get_jornada_or_404(jid: str, company_id: str) -> dict:
    try:
        oid = ObjectId(jid)
    except Exception:
        raise HTTPException(status_code=400, detail="jornada_id invalido")
    j = await db.jornadas.find_one({
        "_id": oid, "company_id": ObjectId(company_id), "is_deleted": {"$ne": True}
    })
    if not j:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    return j


# ═══════════════════════════════════════════════════════════════════════
# EXCEL PREVIEW + IMPORT
# ═══════════════════════════════════════════════════════════════════════
@router.post("/{jid}/excel/preview")
async def preview_excel(
    jid: str, file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    j = await _get_jornada_or_404(jid, user["company_id"])
    if j["status"] not in ("planificada", "activa"):
        raise HTTPException(status_code=400, detail="No se puede cargar Excel en este estado")
    if not (j.get("inventory_config") or {}).get("use_consignment"):
        raise HTTPException(
            status_code=400,
            detail="La jornada no acepta consignacion. Activala en la configuracion.",
        )
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo > 5MB")
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el archivo: {exc}") from exc
    ws = wb.active
    header_row = _detect_header_row(ws)
    headers = [str(c.value).strip() if c.value else f"Col{idx+1}" for idx, c in enumerate(ws[header_row])]
    # Leer las siguientes 8 filas como preview
    sample_rows: list = []
    row_iter = ws.iter_rows(min_row=header_row + 1, max_row=header_row + 8, values_only=True)
    for row in row_iter:
        if all(v in (None, "") for v in row):
            continue
        sample_rows.append([("" if v is None else str(v)) for v in row])
    total_rows = ws.max_row - header_row
    wb.close()
    mapping = _suggest_mapping(headers)
    # Guardar contenido temporalmente en memoria via hash (podria ir a object storage; para MVP guardamos en Redis / o simplemente devolvemos preview y esperamos re-subida)
    return {
        "filename": file.filename,
        "sheet": ws.title,
        "header_row": header_row,
        "headers": headers,
        "sample_rows": sample_rows,
        "total_rows_estimate": max(0, total_rows),
        "suggested_mapping": mapping,
        "fields": list(FIELD_LABELS.keys()),
    }


class ImportMappingBody(BaseModel):
    header_row: int = 1
    mapping: dict  # {field_name: col_index}
    default_supplier: Optional[str] = None
    default_margin_percent: Optional[float] = None  # Si no hay precio, aplicar sobre costo


@router.post("/{jid}/excel/import")
async def import_excel(
    jid: str,
    request: Request,
    file: UploadFile = File(...),
    mapping_json: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """Confirma la carga con el mapeo. Idempotencia via hash del archivo."""
    j = await _get_jornada_or_404(jid, user["company_id"])
    if j["status"] not in ("planificada", "activa"):
        raise HTTPException(status_code=400, detail="No se puede cargar Excel en este estado")
    if not (j.get("inventory_config") or {}).get("use_consignment"):
        raise HTTPException(status_code=400, detail="La jornada no acepta consignacion")
    try:
        body = ImportMappingBody.model_validate_json(mapping_json)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"mapping_json invalido: {exc}") from exc
    if "quantity" not in body.mapping or "description" not in body.mapping:
        raise HTTPException(status_code=400, detail="mapping debe incluir 'description' y 'quantity'")

    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    # Idempotencia: si ya existe upload con este hash en la jornada -> avisar
    existing = await db.jornada_excel_uploads.find_one({
        "company_id": ObjectId(user["company_id"]),
        "jornada_id": j["_id"],
        "file_hash": file_hash,
        "status": "imported",
    })
    if existing:
        raise HTTPException(status_code=400, detail="Este archivo ya fue cargado (mismo hash)")

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    ws = wb.active

    rows_created = 0
    rows_linked = 0
    rows_errors: list = []
    product_ids: list = []  # productos autocreados durante esta carga
    stock_ids: list = []
    # Consolidar duplicados por codigo dentro del mismo archivo
    aggregate: dict = {}
    now_iso = datetime.now(timezone.utc).isoformat()

    row_iter = ws.iter_rows(min_row=body.header_row + 1, values_only=True)
    row_num = body.header_row
    for row in row_iter:
        row_num += 1
        if all(v in (None, "") for v in row):
            continue
        def _pick(field):
            idx = body.mapping.get(field)
            if idx is None or idx >= len(row):
                return None
            v = row[idx]
            return v if v not in (None, "") else None
        description = _pick("description")
        quantity_raw = _pick("quantity")
        qty = _to_number(quantity_raw)
        if not description or qty is None or qty <= 0:
            rows_errors.append({"row": row_num, "error": "descripcion o cantidad faltante/invalida"})
            continue
        code = (str(_pick("code") or "").strip() or None)
        cost = _to_number(_pick("unit_cost")) or 0
        price = _to_number(_pick("unit_price"))
        if price is None and body.default_margin_percent is not None:
            price = round(cost * (1 + body.default_margin_percent / 100), 2)
        price = price or 0
        supplier = (str(_pick("supplier") or body.default_supplier or "").strip() or None)
        key = code or f"desc:{str(description).lower().strip()}|{supplier or ''}"
        if key in aggregate:
            aggregate[key]["quantity"] += int(qty)
        else:
            aggregate[key] = {
                "code": code,
                "description": str(description).strip(),
                "category": (_pick("category") or "").strip() or None,
                "brand": (_pick("brand") or "").strip() or None,
                "model": (_pick("model") or "").strip() or None,
                "color": (_pick("color") or "").strip() or None,
                "size": (_pick("size") or "").strip() or None,
                "quantity": int(qty),
                "unit_cost": cost,
                "unit_price": price,
                "supplier": supplier,
                "batch": (_pick("batch") or "").strip() or None,
            }
    wb.close()

    company_oid = ObjectId(user["company_id"])
    for key, item in aggregate.items():
        # Buscar producto por SKU/codigo existente
        product = None
        if item["code"]:
            product = await db.products.find_one({
                "company_id": company_oid, "sku": item["code"],
            })
        if not product:
            # Autocrear
            sku = item["code"] or f"CONSIG-{ObjectId()}"
            new_prod = {
                "company_id": company_oid,
                "name": item["description"],
                "sku": sku,
                "category": item["category"] or "Consignacion",
                "brand": item["brand"],
                "cost_price": item["unit_cost"],
                "cost": item["unit_cost"],
                "price": item["unit_price"],
                "sale_price": item["unit_price"],
                "is_active": True,
                "is_consignment_source": True,  # Marca para distinguir del catalogo regular
                "origin_jornada_id": j["_id"],
                "created_at": now_iso,
                "created_by": ObjectId(user["_id"]),
            }
            res_p = await db.products.insert_one(new_prod)
            product_id = res_p.inserted_id
            product_ids.append(product_id)
            rows_created += 1
        else:
            product_id = product["_id"]
            rows_linked += 1
        # Insertar en jornada_stock
        stock_doc = {
            "company_id": company_oid,
            "jornada_id": j["_id"],
            "product_id": product_id,
            "source": "consignment",
            "supplier": item["supplier"],
            "batch": item["batch"],
            "initial_qty": item["quantity"],
            "current_qty": item["quantity"],
            "sold_qty": 0,
            "returned_qty": 0,
            "adjusted_qty": 0,
            "unit_cost": item["unit_cost"],
            "unit_price": item["unit_price"],
            "product_name": item["description"],
            "product_sku": item["code"] or "",
            "product_category": item["category"] or "",
            "product_brand": item["brand"] or "",
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        # Si ya existe misma combinacion product+supplier en consignment, sumar
        existing_stock = await db.jornada_stock.find_one({
            "jornada_id": j["_id"], "product_id": product_id,
            "source": "consignment", "supplier": item["supplier"],
        })
        if existing_stock:
            await db.jornada_stock.update_one(
                {"_id": existing_stock["_id"]},
                {"$inc": {"initial_qty": item["quantity"], "current_qty": item["quantity"]},
                 "$set": {"updated_at": now_iso}},
            )
            stock_ids.append(existing_stock["_id"])
        else:
            res_s = await db.jornada_stock.insert_one(stock_doc)
            stock_ids.append(res_s.inserted_id)
        await db.jornada_transfers.insert_one({
            "company_id": company_oid,
            "jornada_id": j["_id"],
            "product_id": product_id,
            "product_name": item["description"],
            "quantity": item["quantity"],
            "kind": "in_consignment",
            "supplier": item["supplier"],
            "batch": item["batch"],
            "unit_cost": item["unit_cost"],
            "unit_price": item["unit_price"],
            "created_at": now_iso,
            "created_by": ObjectId(user["_id"]),
        })

    # Registrar upload
    upload_doc = {
        "company_id": company_oid,
        "jornada_id": j["_id"],
        "filename": file.filename,
        "file_hash": file_hash,
        "mapping": body.mapping,
        "rows_created": rows_created,
        "rows_linked": rows_linked,
        "rows_errors": rows_errors,
        "rows_total": rows_created + rows_linked,
        "product_ids": product_ids,
        "stock_ids": stock_ids,
        "status": "imported",
        "default_supplier": body.default_supplier,
        "default_margin_percent": body.default_margin_percent,
        "created_at": now_iso,
        "created_by": ObjectId(user["_id"]),
    }
    up_res = await db.jornada_excel_uploads.insert_one(upload_doc)

    await log_audit(
        "JORNADA_EXCEL_IMPORT",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=str(up_res.inserted_id),
        target_type="jornada_excel_upload",
        metadata={"jornada_id": jid, "rows_created": rows_created, "rows_linked": rows_linked, "errors": len(rows_errors)},
        request=request,
    )
    return {
        "upload_id": str(up_res.inserted_id),
        "rows_created": rows_created,
        "rows_linked": rows_linked,
        "rows_errors": rows_errors,
        "rows_total": rows_created + rows_linked,
        "message": f"{rows_created + rows_linked} producto(s) cargado(s) de consignacion",
    }


@router.get("/{jid}/excel/uploads")
async def list_excel_uploads(jid: str, user: dict = Depends(get_current_user)):
    try:
        joid = ObjectId(jid)
    except Exception:
        raise HTTPException(status_code=400, detail="jornada_id invalido")
    rows = await db.jornada_excel_uploads.find({
        "company_id": ObjectId(user["company_id"]), "jornada_id": joid
    }).sort("_id", -1).to_list(100)
    for r in rows:
        serialize_doc(r)
        for k in ("jornada_id", "created_by"):
            if isinstance(r.get(k), ObjectId):
                r[k] = str(r[k])
        r["stock_ids"] = [str(x) for x in (r.get("stock_ids") or [])]
        r["product_ids"] = [str(x) for x in (r.get("product_ids") or [])]
    return {"items": rows}


@router.post("/{jid}/excel/{upload_id}/revert")
async def revert_excel(
    jid: str, upload_id: str, request: Request,
    user: dict = Depends(get_current_user),
):
    """Revierte una carga. Solo si ninguno de los productos tiene ventas."""
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Solo admin")
    j = await _get_jornada_or_404(jid, user["company_id"])
    try:
        uoid = ObjectId(upload_id)
    except Exception:
        raise HTTPException(status_code=400, detail="upload_id invalido")
    upload = await db.jornada_excel_uploads.find_one({
        "_id": uoid, "jornada_id": j["_id"],
        "company_id": ObjectId(user["company_id"]),
    })
    if not upload:
        raise HTTPException(status_code=404, detail="Carga no encontrada")
    if upload.get("status") == "reverted":
        raise HTTPException(status_code=400, detail="Ya fue revertida")
    stock_ids = upload.get("stock_ids") or []
    # Verificar que ninguno tenga sold_qty > 0
    for sid in stock_ids:
        row = await db.jornada_stock.find_one({"_id": sid})
        if row and int(row.get("sold_qty") or 0) > 0:
            raise HTTPException(
                status_code=400,
                detail=f"No se puede revertir: '{row.get('product_name','')}' ya tiene ventas",
            )
    # Delete jornada_stock rows y productos autocreados (si no tienen otras referencias)
    for sid in stock_ids:
        await db.jornada_stock.delete_one({"_id": sid})
    for pid in (upload.get("product_ids") or []):
        # Solo borra el producto si no tiene ventas globales
        has_sales = await db.sales.count_documents({"items.product_id": pid, "company_id": ObjectId(user["company_id"])})
        if not has_sales:
            await db.products.delete_one({"_id": pid, "is_consignment_source": True})
    await db.jornada_excel_uploads.update_one(
        {"_id": uoid},
        {"$set": {"status": "reverted", "reverted_at": datetime.now(timezone.utc).isoformat(), "reverted_by": ObjectId(user["_id"])}},
    )
    await log_audit(
        "JORNADA_EXCEL_REVERT",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=upload_id, target_type="jornada_excel_upload",
        metadata={"jornada_id": jid}, request=request,
    )
    return {"message": "Carga revertida"}


# ═══════════════════════════════════════════════════════════════════════
# LIQUIDACION DE CONSIGNACION
# ═══════════════════════════════════════════════════════════════════════
async def _compute_liquidation(company_id: ObjectId, jornada_id: ObjectId) -> dict:
    rows = await db.jornada_stock.find({
        "company_id": company_id, "jornada_id": jornada_id, "source": "consignment"
    }).to_list(5000)
    per_supplier: dict = {}
    total_sold_units = 0
    total_returned_units = 0
    total_missing_units = 0
    total_to_pay = 0.0
    total_revenue = 0.0
    total_margin = 0.0
    for r in rows:
        supplier = r.get("supplier") or "Sin proveedor"
        initial = int(r.get("initial_qty") or 0)
        sold = int(r.get("sold_qty") or 0)
        current = int(r.get("current_qty") or 0)
        adjusted = int(r.get("adjusted_qty") or 0)
        # missing = initial - sold - current - returned; simplificado: initial - sold - current
        missing = max(0, initial - sold - current)
        cost = float(r.get("unit_cost") or 0)
        price = float(r.get("unit_price") or 0)
        pay = round(sold * cost, 2)
        revenue = round(sold * price, 2)
        margin = round(revenue - pay, 2)
        if supplier not in per_supplier:
            per_supplier[supplier] = {"supplier": supplier, "items": [], "sold_units": 0, "returned_units": 0, "missing_units": 0, "to_pay": 0.0, "revenue": 0.0, "margin": 0.0}
        per_supplier[supplier]["items"].append({
            "product_id": str(r.get("product_id")),
            "product_name": r.get("product_name"),
            "sku": r.get("product_sku"),
            "initial_qty": initial, "sold_qty": sold, "current_qty": current,
            "missing_qty": missing, "adjusted_qty": adjusted,
            "unit_cost": cost, "unit_price": price,
            "to_pay": pay, "revenue": revenue, "margin": margin,
        })
        per_supplier[supplier]["sold_units"] += sold
        per_supplier[supplier]["returned_units"] += current  # remanente = devuelto
        per_supplier[supplier]["missing_units"] += missing
        per_supplier[supplier]["to_pay"] += pay
        per_supplier[supplier]["revenue"] += revenue
        per_supplier[supplier]["margin"] += margin
        total_sold_units += sold
        total_returned_units += current
        total_missing_units += missing
        total_to_pay += pay
        total_revenue += revenue
        total_margin += margin
    for s in per_supplier.values():
        s["to_pay"] = round(s["to_pay"], 2)
        s["revenue"] = round(s["revenue"], 2)
        s["margin"] = round(s["margin"], 2)
    return {
        "per_supplier": list(per_supplier.values()),
        "totals": {
            "sold_units": total_sold_units,
            "returned_units": total_returned_units,
            "missing_units": total_missing_units,
            "to_pay": round(total_to_pay, 2),
            "revenue": round(total_revenue, 2),
            "margin": round(total_margin, 2),
        },
    }


@router.get("/{jid}/liquidation")
async def get_liquidation(jid: str, user: dict = Depends(get_current_user)):
    j = await _get_jornada_or_404(jid, user["company_id"])
    liq = await _compute_liquidation(ObjectId(user["company_id"]), j["_id"])
    return liq


# ═══════════════════════════════════════════════════════════════════════
# REPORTE FINAL DE CIERRE (PDF + XLSX)
# ═══════════════════════════════════════════════════════════════════════
async def _build_report_data(company_id: ObjectId, j: dict) -> dict:
    joid = j["_id"]
    # Ventas de la jornada
    sales = await db.sales.find({
        "company_id": company_id, "jornada_id": joid, "status": {"$ne": "cancelada"}
    }).to_list(5000)
    total_sold = sum(float(s.get("total") or 0) for s in sales)
    total_by_method: dict = {}
    for s in sales:
        for p in (s.get("payments") or []):
            m = p.get("method", "cash")
            total_by_method[m] = round(total_by_method.get(m, 0) + float(p.get("amount") or 0), 2)
    units_sold = sum(sum(int(i.get("quantity") or 0) for i in (s.get("items") or [])) for s in sales)
    ticket_avg = round(total_sold / len(sales), 2) if sales else 0
    receivables_total = sum(float(s.get("balance") or 0) for s in sales)
    receivables_count = sum(1 for s in sales if float(s.get("balance") or 0) > 0)

    # Ventas por categoria/marca
    by_category: dict = {}
    by_brand: dict = {}
    by_source: dict = {"branch": {"units": 0, "revenue": 0.0}, "consignment": {"units": 0, "revenue": 0.0}}
    inv_rows = await db.jornada_stock.find({
        "company_id": company_id, "jornada_id": joid
    }).to_list(5000)
    inv_map = {str(r["product_id"]): r for r in inv_rows}
    for s in sales:
        for it in (s.get("items") or []):
            pid = str(it.get("product_id") or "")
            src = inv_map.get(pid, {})
            cat = src.get("product_category") or "Sin categoria"
            brand = src.get("product_brand") or "Sin marca"
            qty = int(it.get("quantity") or 0)
            rev = float(it.get("total") or 0)
            by_category[cat] = round(by_category.get(cat, 0) + rev, 2)
            by_brand[brand] = round(by_brand.get(brand, 0) + rev, 2)
            source = src.get("source", "branch")
            by_source[source] = {"units": by_source[source]["units"] + qty, "revenue": round(by_source[source]["revenue"] + rev, 2)}

    # Inventario resumen
    inv_sent = sum(int(r.get("initial_qty") or 0) for r in inv_rows)
    inv_sold = sum(int(r.get("sold_qty") or 0) for r in inv_rows)
    inv_returned = sum(int(r.get("current_qty") or 0) for r in inv_rows)
    inv_missing = max(0, inv_sent - inv_sold - inv_returned)
    inv_sent_value = round(sum(int(r.get("initial_qty") or 0) * float(r.get("unit_price") or 0) for r in inv_rows), 2)
    inv_sold_value = round(sum(int(r.get("sold_qty") or 0) * float(r.get("unit_price") or 0) for r in inv_rows), 2)
    inv_returned_value = round(sum(int(r.get("current_qty") or 0) * float(r.get("unit_price") or 0) for r in inv_rows), 2)

    # Pacientes
    patients = await db.patients.find({
        "company_id": company_id, "is_deleted": {"$ne": True}, "jornada_ids": joid,
    }, {"first_name": 1, "last_name": 1, "jornada_id_first": 1}).to_list(5000)
    patients_new = sum(1 for p in patients if str(p.get("jornada_id_first")) == str(joid))
    patients_recurring = len(patients) - patients_new
    prescriptions = await db.eyeglass_prescriptions.count_documents({
        "company_id": company_id, "patient_id": {"$in": [p["_id"] for p in patients]},
    }) if patients else 0
    patients_with_sale = len({s.get("patient_id") for s in sales if s.get("patient_id")})
    conversion_rate = round((patients_with_sale / len(patients)) * 100, 1) if patients else 0

    # Caja
    cash_reg = await db.cash_registers.find_one({
        "company_id": company_id, "jornada_id": joid,
    }, sort=[("opened_at", -1)])
    egresos_by_category: dict = {}
    egresos_total = 0.0
    if cash_reg:
        for m in (cash_reg.get("movements") or []):
            if m.get("kind") == "egreso":
                cat = m.get("category") or "otro"
                amt = float(m.get("amount") or 0)
                egresos_by_category[cat] = round(egresos_by_category.get(cat, 0) + amt, 2)
                egresos_total += amt
    net_cash = 0
    if cash_reg and cash_reg.get("close_totals"):
        ct = cash_reg["close_totals"]
        net_cash = round(float(ct.get("opening_amount", 0)) + float(ct.get("totals_by_method", {}).get("cash", 0)) - float(ct.get("egresos_total", 0)), 2)

    # Liquidacion
    liq = await _compute_liquidation(company_id, joid)

    # Meta
    goal_amount = float(j.get("goal_amount") or 0)
    goal_patients = int(j.get("goal_patients") or 0)
    goal_amount_pct = round((total_sold / goal_amount) * 100, 1) if goal_amount else None
    goal_patients_pct = round((len(patients) / goal_patients) * 100, 1) if goal_patients else None

    # Utilidad
    revenue_gross = round(total_sold, 2)
    revenue_net = round(total_sold - liq["totals"]["to_pay"] - egresos_total, 2)

    branch = None
    if j.get("responsible_branch_id"):
        b = await db.branches.find_one({"_id": j["responsible_branch_id"]})
        branch = (b or {}).get("name")

    return {
        "jornada": {
            "id": str(j["_id"]),
            "name": j.get("name"),
            "start_date": j.get("start_date"),
            "end_date": j.get("end_date"),
            "location": j.get("location"),
            "partner_entity": j.get("partner_entity"),
            "branch": branch,
        },
        "sales": {
            "total": round(total_sold, 2),
            "count": len(sales),
            "units_sold": units_sold,
            "ticket_avg": ticket_avg,
            "by_method": total_by_method,
            "receivables_total": round(receivables_total, 2),
            "receivables_count": receivables_count,
            "by_category": by_category,
            "by_brand": by_brand,
            "by_source": by_source,
        },
        "inventory": {
            "sent_units": inv_sent, "sold_units": inv_sold,
            "returned_units": inv_returned, "missing_units": inv_missing,
            "sent_value": inv_sent_value, "sold_value": inv_sold_value,
            "returned_value": inv_returned_value,
        },
        "patients": {
            "total": len(patients),
            "new_here": patients_new,
            "recurring": patients_recurring,
            "with_sale": patients_with_sale,
            "conversion_rate": conversion_rate,
            "prescriptions": prescriptions,
        },
        "cash": {
            "opening": float((cash_reg or {}).get("opening_amount") or 0),
            "net_cash": net_cash,
            "egresos_total": round(egresos_total, 2),
            "egresos_by_category": egresos_by_category,
            "counted_cash": float((cash_reg or {}).get("counted_cash") or 0) if cash_reg else 0,
            "diff": float((cash_reg or {}).get("diff") or 0) if cash_reg else 0,
        },
        "liquidation": liq,
        "goals": {
            "amount": goal_amount or None, "amount_pct": goal_amount_pct,
            "patients": goal_patients or None, "patients_pct": goal_patients_pct,
        },
        "profit": {
            "gross": revenue_gross,
            "net": revenue_net,
        },
    }


@router.get("/{jid}/report.pdf")
async def get_report_pdf(jid: str, user: dict = Depends(get_current_user)):
    j = await _get_jornada_or_404(jid, user["company_id"])
    data = await _build_report_data(ObjectId(user["company_id"]), j)
    # Generar PDF
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#0f3d2e"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor("#0f3d2e"), spaceAfter=6)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9)
    elems: list = []

    jm = data["jornada"]
    elems.append(Paragraph(f"Reporte de Cierre - {jm['name']}", h1))
    elems.append(Paragraph(f"Periodo: {jm['start_date']} a {jm['end_date']} | Sucursal: {jm.get('branch') or '-'} | Lugar: {jm.get('location') or '-'}", small))
    if jm.get("partner_entity"):
        elems.append(Paragraph(f"Entidad aliada: {jm['partner_entity']}", small))
    elems.append(Spacer(1, 12))

    # Ventas
    s = data["sales"]
    elems.append(Paragraph("Ventas", h2))
    sales_table = [["Total vendido", f"Q {s['total']:,.2f}"], ["Numero de ventas", s["count"]], ["Unidades", s["units_sold"]], ["Ticket promedio", f"Q {s['ticket_avg']:,.2f}"], ["Cuentas por cobrar", f"Q {s['receivables_total']:,.2f} ({s['receivables_count']})"]]
    elems.append(_fmt_table(sales_table))
    if s["by_method"]:
        elems.append(Spacer(1, 6))
        elems.append(Paragraph("Por metodo de pago", h2))
        elems.append(_fmt_table([[k.title(), f"Q {v:,.2f}"] for k, v in s["by_method"].items()]))
    elems.append(Spacer(1, 12))

    # Inventario
    inv = data["inventory"]
    elems.append(Paragraph("Inventario", h2))
    elems.append(_fmt_table([
        ["Enviado", f"{inv['sent_units']} un. / Q {inv['sent_value']:,.2f}"],
        ["Vendido", f"{inv['sold_units']} un. / Q {inv['sold_value']:,.2f}"],
        ["Devuelto", f"{inv['returned_units']} un. / Q {inv['returned_value']:,.2f}"],
        ["Faltante", f"{inv['missing_units']} un."],
    ]))
    elems.append(Spacer(1, 12))

    # Pacientes
    p = data["patients"]
    elems.append(Paragraph("Pacientes", h2))
    elems.append(_fmt_table([
        ["Total atendidos", p["total"]],
        ["Nuevos (aqui capturados)", p["new_here"]],
        ["Recurrentes", p["recurring"]],
        ["Con venta", p["with_sale"]],
        ["Tasa de conversion", f"{p['conversion_rate']}%"],
        ["Recetas emitidas", p["prescriptions"]],
    ]))
    elems.append(Spacer(1, 12))

    # Caja
    c = data["cash"]
    elems.append(Paragraph("Caja", h2))
    elems.append(_fmt_table([
        ["Fondo inicial", f"Q {c['opening']:,.2f}"],
        ["Efectivo neto", f"Q {c['net_cash']:,.2f}"],
        ["Egresos totales", f"Q {c['egresos_total']:,.2f}"],
        ["Diferencia arqueo", f"Q {c['diff']:,.2f}"],
    ]))
    if c["egresos_by_category"]:
        elems.append(Paragraph("Egresos por categoria", h2))
        elems.append(_fmt_table([[k.title(), f"Q {v:,.2f}"] for k, v in c["egresos_by_category"].items()]))
    elems.append(Spacer(1, 12))

    # Liquidacion
    liq = data["liquidation"]
    elems.append(Paragraph("Liquidacion de Consignacion", h2))
    if not liq["per_supplier"]:
        elems.append(Paragraph("Sin inventario de consignacion.", small))
    else:
        for sup in liq["per_supplier"]:
            elems.append(Paragraph(f"<b>{sup['supplier']}</b>", small))
            elems.append(_fmt_table([
                ["Vendido", sup["sold_units"]],
                ["Devuelto (remanente)", sup["returned_units"]],
                ["Faltante", sup["missing_units"]],
                ["A pagar al consignatario", f"Q {sup['to_pay']:,.2f}"],
                ["Ingreso", f"Q {sup['revenue']:,.2f}"],
                ["Utilidad", f"Q {sup['margin']:,.2f}"],
            ]))
            elems.append(Spacer(1, 6))
        t = liq["totals"]
        elems.append(Paragraph("<b>Totales</b>", small))
        elems.append(_fmt_table([
            ["Total a pagar", f"Q {t['to_pay']:,.2f}"],
            ["Ingreso consignacion", f"Q {t['revenue']:,.2f}"],
            ["Utilidad consignacion", f"Q {t['margin']:,.2f}"],
        ]))
    elems.append(Spacer(1, 12))

    # Meta + Utilidad
    prof = data["profit"]
    elems.append(Paragraph("Resultado", h2))
    elems.append(_fmt_table([
        ["Utilidad bruta (ventas)", f"Q {prof['gross']:,.2f}"],
        ["Utilidad neta (ventas − consignacion − egresos)", f"Q {prof['net']:,.2f}"],
    ]))
    g = data["goals"]
    if g["amount"] or g["patients"]:
        elems.append(Spacer(1, 6))
        elems.append(Paragraph("Meta comercial", h2))
        rows = []
        if g["amount"]:
            rows.append(["Meta venta", f"Q {g['amount']:,.2f} ({g['amount_pct']}% alcanzado)"])
        if g["patients"]:
            rows.append(["Meta pacientes", f"{g['patients']} ({g['patients_pct']}% alcanzado)"])
        elems.append(_fmt_table(rows))

    doc.build(elems)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=jornada_{jid}.pdf"},
    )


def _fmt_table(data: list):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.units import inch
    t = Table(data, colWidths=[3*inch, 3*inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.lightgrey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


@router.get("/{jid}/report.xlsx")
async def get_report_xlsx(jid: str, user: dict = Depends(get_current_user)):
    j = await _get_jornada_or_404(jid, user["company_id"])
    data = await _build_report_data(ObjectId(user["company_id"]), j)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Resumen"
    ws["A1"] = f"Reporte Jornada: {data['jornada']['name']}"
    ws["A1"].font = openpyxl.styles.Font(bold=True, size=14)
    ws["A2"] = f"{data['jornada']['start_date']} a {data['jornada']['end_date']}"
    row = 4
    def _section(title, rows):
        nonlocal row
        ws.cell(row=row, column=1, value=title).font = openpyxl.styles.Font(bold=True, size=12)
        row += 1
        for k, v in rows:
            ws.cell(row=row, column=1, value=k)
            ws.cell(row=row, column=2, value=v)
            row += 1
        row += 1
    _section("Ventas", [
        ("Total vendido", data["sales"]["total"]),
        ("Ventas", data["sales"]["count"]),
        ("Unidades", data["sales"]["units_sold"]),
        ("Ticket promedio", data["sales"]["ticket_avg"]),
        ("Cuentas por cobrar", data["sales"]["receivables_total"]),
    ])
    _section("Metodos de pago", [(k.title(), v) for k, v in data["sales"]["by_method"].items()])
    _section("Inventario", [
        ("Enviado", data["inventory"]["sent_units"]),
        ("Vendido", data["inventory"]["sold_units"]),
        ("Devuelto", data["inventory"]["returned_units"]),
        ("Faltante", data["inventory"]["missing_units"]),
    ])
    _section("Pacientes", [
        ("Total", data["patients"]["total"]),
        ("Nuevos", data["patients"]["new_here"]),
        ("Con venta", data["patients"]["with_sale"]),
        ("Conversion %", data["patients"]["conversion_rate"]),
        ("Recetas", data["patients"]["prescriptions"]),
    ])
    _section("Caja", [
        ("Fondo inicial", data["cash"]["opening"]),
        ("Neto", data["cash"]["net_cash"]),
        ("Egresos", data["cash"]["egresos_total"]),
        ("Diferencia arqueo", data["cash"]["diff"]),
    ])
    _section("Utilidad", [
        ("Bruta", data["profit"]["gross"]),
        ("Neta", data["profit"]["net"]),
    ])

    # Hoja de liquidacion
    ws2 = wb.create_sheet("Liquidacion")
    ws2.append(["Proveedor", "Producto", "SKU", "Inicial", "Vendido", "Devuelto", "Faltante", "Costo", "Precio", "A pagar", "Ingreso", "Utilidad"])
    for sup in data["liquidation"]["per_supplier"]:
        for it in sup["items"]:
            ws2.append([sup["supplier"], it["product_name"], it["sku"], it["initial_qty"], it["sold_qty"], it["current_qty"], it["missing_qty"], it["unit_cost"], it["unit_price"], it["to_pay"], it["revenue"], it["margin"]])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=jornada_{jid}.xlsx"},
    )
