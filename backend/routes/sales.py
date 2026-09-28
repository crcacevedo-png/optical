from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from typing import Optional
import io
import asyncio
import os
import uuid
import logging
import jwt as pyjwt

from db import db, serialize_doc, UPLOADS_DIR
from auth_utils import get_current_user, get_jwt_secret, JWT_ALGORITHM
from models import SaleCreate
from audit import log_audit
from cache import invalidate_inventory
from rate_limiter import limiter
import object_storage as objstore

router = APIRouter(prefix="/sales", tags=["Ventas"])

logger = logging.getLogger(__name__)

RECEIPT_SHARE_SUB = "sale-receipt"
RECEIPT_SHARE_HOURS = int(os.environ.get("RECEIPT_SHARE_HOURS", "720"))  # 30d


def _normalize_phone(raw: str) -> str:
    """Solo digitos; antepone 502 (Guatemala) si son 8 digitos locales."""
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if len(digits) == 8:
        digits = "502" + digits
    return digits


async def _get_company_logo_bytes(company: dict) -> Optional[bytes]:
    """Devuelve los bytes del logo de la empresa (Object Storage o local), o None."""
    if not company or not company.get("logo_filename"):
        return None
    try:
        if company.get("logo_storage_path") and objstore.is_enabled():
            data, _ct = await asyncio.to_thread(objstore.get_object, company["logo_storage_path"])
            return data
        fp = UPLOADS_DIR / company["logo_filename"]
        if fp.exists():
            return fp.read_bytes()
    except Exception as e:
        logger.warning(f"No se pudo cargar el logo para el recibo: {e}")
    return None


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
    limit: int = 100,
    cursor: Optional[str] = None,
    include_cursor: bool = False,
):
    """Lista ventas con cursor pagination opcional.

    - Sin `cursor` ni `include_cursor=true`: devuelve una lista plana (retro-compat).
    - Con `cursor` (id de la ultima venta) o `include_cursor=true`: devuelve
      {items, next_cursor, has_more}. El cursor apunta al `_id` de la ultima venta
      recibida; internamente ordenamos por `_id desc` (equivalente cronologico).
    """
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    query = {"company_id": ObjectId(user["company_id"])}
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])

    if date_from and date_to:
        query["created_at"] = {"$gte": date_from, "$lte": date_to + "T23:59:59"}

    # Cursor: _id < cursor (ObjectId es cronologico y unico → mejor que skip/limit)
    if cursor:
        try:
            query["_id"] = {"$lt": ObjectId(cursor)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail="cursor invalido") from exc

    # Pedimos limit+1 para saber si hay mas paginas
    fetch_n = max(1, min(limit, 500)) + 1
    docs = await db.sales.find(query).sort("_id", -1).limit(fetch_n).to_list(fetch_n)
    has_more = len(docs) > limit
    sales = docs[:limit]

    # Batch fetch de pacientes y vendedores (elimina N+1)
    patient_ids = {s["patient_id"] for s in sales if s.get("patient_id")}
    seller_ids = {s["created_by"] for s in sales if s.get("created_by")}

    patients_map = {}
    if patient_ids:
        patients = await db.patients.find(
            {"_id": {"$in": list(patient_ids)}},
            {"first_name": 1, "last_name": 1},
        ).to_list(len(patient_ids))
        patients_map = {str(p["_id"]): f"{p.get('first_name','')} {p.get('last_name','')}".strip() for p in patients}

    sellers_map = {}
    if seller_ids:
        sellers = await db.users.find(
            {"_id": {"$in": list(seller_ids)}},
            {"name": 1},
        ).to_list(len(seller_ids))
        sellers_map = {str(u["_id"]): u.get("name", "") for u in sellers}

    for s in sales:
        serialize_doc(s)
        _serialize_payments(s)
        pid = s.get("patient_id")
        if pid:
            s["patient_name"] = patients_map.get(pid, "")
        cid = s.get("created_by")
        if cid:
            s["seller_name"] = sellers_map.get(cid, "")

    if cursor or include_cursor:
        next_cursor = sales[-1]["_id"] if sales and has_more else None
        return {"items": sales, "next_cursor": next_cursor, "has_more": has_more}
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

    # ─── Snapshot del COSTO unitario por item (para COGS / margen exacto, de aqui en adelante) ───
    # Se fotografia el cost_price vigente del producto al momento de vender; asi el margen no
    # cambia si el costo del producto se edita despues. Items sin producto de inventario quedan
    # marcados como "sin_costo" (no se puede calcular su margen).
    product_ids = [ObjectId(it["product_id"]) for it in data.items if it.get("product_id")]
    cost_map = {}
    if product_ids:
        async for p in db.products.find({"_id": {"$in": product_ids}}, {"cost_price": 1}):
            cost_map[str(p["_id"])] = round(float(p.get("cost_price") or 0), 2)
    enriched_items = []
    for it in data.items:
        item = dict(it)
        pid = it.get("product_id")
        if pid and str(pid) in cost_map:
            item["unit_cost"] = cost_map[str(pid)]
            item["cost_source"] = "product"
        else:
            item["unit_cost"] = None
            item["cost_source"] = "sin_costo"
        enriched_items.append(item)

    sale_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": branch_id,
        "patient_id": ObjectId(data.patient_id) if data.patient_id else None,
        "patient_name_override": data.patient_name_override,
        "items": enriched_items,
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


@router.get("/{sale_id}/receipt.pdf")
async def sale_receipt_pdf(sale_id: str, user: dict = Depends(get_current_user)):
    """Recibo de pago 80mm (impresora termica / compartir)."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        oid = ObjectId(sale_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="sale_id invalido") from exc
    sale = await db.sales.find_one({"_id": oid})
    if not sale or str(sale["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    pdf_bytes = await _build_sale_receipt_pdf(sale)
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=recibo_{sale_id[-8:]}.pdf"},
    )


async def _build_sale_receipt_pdf(sale: dict) -> bytes:
    """Resuelve empresa/cliente/vendedor/logo y renderiza el recibo (en hilo)."""
    company = await db.companies.find_one({"_id": sale["company_id"]}) or {}
    patient_name = sale.get("patient_name_override") or "Consumidor final"
    if sale.get("patient_id"):
        p = await db.patients.find_one({"_id": sale["patient_id"]}, {"first_name": 1, "last_name": 1})
        if p:
            patient_name = f"{p.get('first_name','')} {p.get('last_name','')}".strip() or patient_name
    seller_name = ""
    if sale.get("created_by"):
        u = await db.users.find_one({"_id": sale["created_by"]}, {"name": 1})
        if u:
            seller_name = u.get("name", "")
    logo_bytes = await _get_company_logo_bytes(company)
    return await asyncio.to_thread(_render_sale_receipt_pdf, sale, company, patient_name, seller_name, logo_bytes)


@router.get("/{sale_id}/receipt-share-link")
async def sale_receipt_share_link(sale_id: str, user: dict = Depends(get_current_user)):
    """Genera un enlace publico firmado (JWT) del recibo + datos para compartir por WhatsApp."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        oid = ObjectId(sale_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="sale_id invalido") from exc
    sale = await db.sales.find_one({"_id": oid})
    if not sale or str(sale["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    company = await db.companies.find_one({"_id": sale["company_id"]}, {"name": 1}) or {}
    patient_name = sale.get("patient_name_override") or "Consumidor final"
    phone = ""
    if sale.get("patient_id"):
        p = await db.patients.find_one({"_id": sale["patient_id"]}, {"first_name": 1, "last_name": 1, "phone": 1})
        if p:
            patient_name = f"{p.get('first_name','')} {p.get('last_name','')}".strip() or patient_name
            phone = _normalize_phone(p.get("phone", ""))

    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=RECEIPT_SHARE_HOURS)
    token = pyjwt.encode({
        "sub": RECEIPT_SHARE_SUB,
        "sale_id": str(sale["_id"]),
        "company_id": str(sale["company_id"]),
        "iat": int(now.timestamp()),
        "exp": exp,
        "jti": str(uuid.uuid4()),
    }, get_jwt_secret(), algorithm=JWT_ALGORITHM)

    first_name = patient_name.split(" ")[0] if patient_name and patient_name != "Consumidor final" else ""
    greeting = f"Hola {first_name}, " if first_name else "Hola, "
    message = (
        f"{greeting}aqui esta tu recibo de compra en {company.get('name') or 'Cortexia Optical'} "
        f"por un total de Q{float(sale.get('total', 0) or 0):.2f}. Puedes verlo aqui: "
    )
    return {
        "path": f"/api/sales/public/receipt?token={token}",
        "token": token,
        "expires_at": exp.isoformat(),
        "phone": phone,
        "patient_name": patient_name,
        "message": message,
    }


@router.get("/public/receipt")
@limiter.limit("20/minute")
async def public_sale_receipt(request: Request, token: str = Query(..., min_length=10, max_length=2048)):
    """Endpoint publico (sin auth): valida el JWT firmado y sirve el recibo PDF."""
    try:
        decoded = pyjwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=410, detail="El enlace expiro. Solicita uno nuevo.")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Enlace invalido.")
    if decoded.get("sub") != RECEIPT_SHARE_SUB:
        raise HTTPException(status_code=403, detail="Enlace invalido.")
    try:
        oid = ObjectId(decoded.get("sale_id"))
    except Exception as exc:
        raise HTTPException(status_code=403, detail="Enlace invalido.") from exc
    sale = await db.sales.find_one({"_id": oid})
    if not sale or str(sale.get("company_id")) != decoded.get("company_id"):
        raise HTTPException(status_code=404, detail="Recibo no encontrado")

    pdf_bytes = await _build_sale_receipt_pdf(sale)
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=recibo_{str(sale['_id'])[-8:]}.pdf",
            "Cache-Control": "public, max-age=3600",
        },
    )


def _render_sale_receipt_pdf(sale: dict, company: dict, patient_name: str, seller_name: str, logo_bytes: bytes = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    NAVY = colors.HexColor("#1B2A49")
    GRAY = colors.HexColor("#64748b")
    LIGHT = colors.HexColor("#eef2f7")
    AMBER = colors.HexColor("#d97706")

    w, h = 8.5 * inch, 5.5 * inch  # media carta horizontal (igual que recetas)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))

    # ── Banda de encabezado ──
    c.setFillColor(NAVY)
    c.rect(0, h - 0.9 * inch, w, 0.9 * inch, fill=True, stroke=False)
    text_x = 0.4 * inch
    if logo_bytes:
        try:
            img = ImageReader(io.BytesIO(logo_bytes))
            iw, ih = img.getSize()
            aspect = iw / ih
            lh = 0.55 * inch
            lw = min(lh * aspect, 1.2 * inch)
            lh = lw / aspect
            c.drawImage(img, 0.3 * inch, h - 0.72 * inch, width=lw, height=lh,
                        preserveAspectRatio=True, mask="auto")
            text_x = 0.3 * inch + lw + 0.2 * inch
        except Exception:
            pass
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(text_x, h - 0.42 * inch, str(company.get("name") or "Cortexia Optical"))
    c.setFont("Helvetica", 7.5)
    line2 = company.get("legal_name") or company.get("address") or ""
    if line2:
        c.drawString(text_x, h - 0.57 * inch, str(line2)[:70])
    bits = []
    if company.get("tax_id"):
        bits.append(f"NIT: {company['tax_id']}")
    if company.get("phone"):
        bits.append(f"Tel: {company['phone']}")
    if company.get("email"):
        bits.append(str(company["email"]))
    if bits:
        c.drawString(text_x, h - 0.72 * inch, "   ".join(bits)[:90])

    # ── Titulo ──
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(w / 2, h - 1.18 * inch, "RECIBO DE PAGO")
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.7)
    c.line(0.4 * inch, h - 1.28 * inch, w - 0.4 * inch, h - 1.28 * inch)

    # ── Meta (recibo / fecha / cliente / vendedor) ──
    y = h - 1.5 * inch
    c.setFont("Helvetica", 8.5)
    c.setFillColor(GRAY)
    c.drawString(0.4 * inch, y, "Recibo:")
    c.drawString(4.4 * inch, y, "Fecha:")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(1.0 * inch, y, str(sale["_id"])[-8:].upper())
    date_str = (sale.get("created_at") or "")[:19].replace("T", " ")
    c.drawString(4.95 * inch, y, date_str)
    y -= 0.22 * inch
    c.setFont("Helvetica", 8.5)
    c.setFillColor(GRAY)
    c.drawString(0.4 * inch, y, "Cliente:")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(1.0 * inch, y, patient_name[:48])
    if seller_name:
        c.setFont("Helvetica", 8.5)
        c.setFillColor(GRAY)
        c.drawString(4.4 * inch, y, "Atendio:")
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(4.95 * inch, y, seller_name[:32])
    y -= 0.3 * inch

    # ── Tabla de articulos ──
    x_prod = 0.42 * inch
    x_qty = 5.3 * inch
    x_price = 6.6 * inch
    x_total = w - 0.42 * inch
    c.setFillColor(LIGHT)
    c.rect(0.35 * inch, y - 0.06 * inch, w - 0.7 * inch, 0.24 * inch, fill=True, stroke=False)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x_prod, y, "PRODUCTO")
    c.drawRightString(x_qty, y, "CANT")
    c.drawRightString(x_price, y, "PRECIO")
    c.drawRightString(x_total, y, "TOTAL")
    y -= 0.26 * inch
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 8.5)
    for it in (sale.get("items") or []):
        name = str(it.get("name", ""))[:58]
        qty = int(it.get("quantity", 0) or 0)
        price = float(it.get("price", it.get("unit_price", 0)) or 0)
        line_total = float(it.get("total", it.get("subtotal", qty * price)) or 0)
        c.drawString(x_prod, y, name)
        c.drawRightString(x_qty, y, str(qty))
        c.drawRightString(x_price, y, f"Q {price:.2f}")
        c.drawRightString(x_total, y, f"Q {line_total:.2f}")
        y -= 0.2 * inch
        if y < 1.2 * inch:  # evitar invadir el pie
            break
    block_top = y + 0.02 * inch
    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.setLineWidth(0.5)
    c.line(0.4 * inch, block_top + 0.02 * inch, x_total, block_top + 0.02 * inch)

    # ── Totales (bloque derecho) ──
    ty = block_top - 0.18 * inch

    def _tot(label, value, bold=False, color=colors.black):
        c.setFillColor(GRAY if not bold else color)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10 if bold else 8.5)
        c.drawString(5.6 * inch, ty, label)
        c.setFillColor(color if bold else colors.black)
        c.drawRightString(x_total, ty, value)

    _tot("Subtotal", f"Q {float(sale.get('subtotal', 0) or 0):.2f}")
    ty -= 0.2 * inch
    if float(sale.get("discount", 0) or 0) > 0:
        _tot("Descuento", f"-Q {float(sale.get('discount', 0)):.2f}")
        ty -= 0.2 * inch
    _tot("TOTAL", f"Q {float(sale.get('total', 0) or 0):.2f}", bold=True, color=NAVY)
    ty -= 0.28 * inch
    _tot("Pagado", f"Q {float(sale.get('amount_paid', 0) or 0):.2f}")
    ty -= 0.2 * inch
    if float(sale.get("balance", 0) or 0) > 0.01:
        _tot("SALDO PENDIENTE", f"Q {float(sale.get('balance', 0)):.2f}", bold=True, color=AMBER)

    # ── Pagos (bloque izquierdo) ──
    py = block_top - 0.18 * inch
    method_labels = {"cash": "Efectivo", "card": "Tarjeta", "transfer": "Transferencia", "check": "Cheque", "other": "Otro"}
    pays = sale.get("payments") or []
    if pays:
        c.setFillColor(GRAY)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(0.42 * inch, py, "FORMA DE PAGO")
        py -= 0.22 * inch
        c.setFont("Helvetica", 8.5)
        for p in pays:
            m = method_labels.get(p.get("method"), p.get("method", ""))
            c.setFillColor(colors.black)
            c.drawString(0.42 * inch, py, m)
            c.drawString(2.2 * inch, py, f"Q {float(p.get('amount', 0) or 0):.2f}")
            py -= 0.2 * inch
            if py < 0.9 * inch:
                break

    # ── Pie ──
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 7)
    footer = (company.get("prescription_style", {}) or {}).get("footer_text") or "Gracias por su compra"
    c.drawCentredString(w / 2, 0.55 * inch, str(footer)[:90])
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.7)
    c.line(0.4 * inch, 0.75 * inch, w - 0.4 * inch, 0.75 * inch)
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(w / 2, 0.4 * inch, "www.cortexiaoptical.com")

    c.showPage()
    c.save()
    return buf.getvalue()


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
