from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from typing import Optional
import io
import asyncio
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

from db import db, serialize_doc, UPLOADS_DIR
from auth_utils import get_current_user
from models import QuotationCreate, QuotationStatusUpdate

router = APIRouter(prefix="/quotations", tags=["Cotizaciones"])

def get_logo_path(company):
    if company and company.get("logo_filename"):
        candidate = UPLOADS_DIR / company["logo_filename"]
        if candidate.exists():
            return str(candidate)
    return None

def draw_pdf_header(c, width, height, company, title):
    c.setFillColor(colors.HexColor("#0F4C3A"))
    c.rect(0, height - 1.2*inch, width, 1.2*inch, fill=True, stroke=False)
    logo_path = get_logo_path(company)
    text_x = 1*inch
    if logo_path:
        try:
            img = ImageReader(logo_path)
            iw, ih = img.getSize()
            aspect = iw / ih
            logo_h = 0.8 * inch
            logo_w = min(logo_h * aspect, 1.5 * inch)
            logo_h = logo_w / aspect
            c.drawImage(logo_path, 0.5*inch, height - 1.05*inch, width=logo_w, height=logo_h, preserveAspectRatio=True, mask='auto')
            text_x = 0.5*inch + logo_w + 0.2*inch
        except Exception:
            pass
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(text_x, height - 0.75*inch, company["name"] if company else "Cortexia Optical")
    c.setFont("Helvetica", 9)
    c.drawString(text_x, height - 0.95*inch, company.get("address", "") if company else "")
    phone = company.get("phone", "") if company else ""
    email = company.get("email", "") if company else ""
    if phone or email:
        c.drawString(text_x, height - 1.1*inch, f"Tel: {phone}  |  {email}")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, height - 1.55*inch, title)

@router.get("")
async def list_quotations(
    user: dict = Depends(get_current_user),
    status: Optional[str] = None,
    patient_id: Optional[str] = None,
    limit: int = 100
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    query = {"company_id": ObjectId(user["company_id"])}
    if status and status != "todas":
        query["status"] = status
    if patient_id:
        query["patient_id"] = ObjectId(patient_id)

    quotations = await db.quotations.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    if not quotations:
        return []

    # Batch fetch de pacientes y creadores (elimina N+1)
    patient_ids = {q["patient_id"] for q in quotations if q.get("patient_id")}
    creator_ids = {q["created_by"] for q in quotations if q.get("created_by")}

    patients_map = {}
    if patient_ids:
        docs = await db.patients.find(
            {"_id": {"$in": list(patient_ids)}},
            {"first_name": 1, "last_name": 1, "phone": 1, "email": 1, "whatsapp": 1},
        ).to_list(len(patient_ids))
        patients_map = {str(p["_id"]): p for p in docs}

    creators_map = {}
    if creator_ids:
        docs = await db.users.find(
            {"_id": {"$in": list(creator_ids)}},
            {"name": 1},
        ).to_list(len(creator_ids))
        creators_map = {str(u["_id"]): u.get("name", "") for u in docs}

    # Detectar cotizaciones vencidas y hacer un solo bulk_write al final
    now_dt = datetime.now(timezone.utc)
    expired_ids = []

    for q in quotations:
        serialize_doc(q)
        for e in q.get("emails_sent", []) or []:
            if isinstance(e.get("sent_by"), ObjectId):
                e["sent_by"] = str(e["sent_by"])
        pid = q.get("patient_id")
        if pid:
            p = patients_map.get(pid)
            if p:
                q["patient_name"] = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
                q["patient_phone"] = p.get("phone", "")
                q["patient_email"] = p.get("email", "")
                q["patient_whatsapp"] = p.get("whatsapp", "")
        cid = q.get("created_by")
        if cid:
            q["creator_name"] = creators_map.get(cid, "")
        if q["status"] == "pendiente":
            created_str = q["created_at"]
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00")) if isinstance(created_str, str) else created_str
                expiry = created + timedelta(days=q.get("validity_days", 15))
                if now_dt > expiry:
                    q["status"] = "vencida"
                    expired_ids.append(ObjectId(q["_id"]))
            except (ValueError, TypeError):
                pass

    # Un solo update masivo para las vencidas
    if expired_ids:
        await db.quotations.update_many(
            {"_id": {"$in": expired_ids}},
            {"$set": {"status": "vencida"}},
        )

    return [serialize_doc(q) for q in quotations]

@router.post("")
async def create_quotation(data: QuotationCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    branch_id = ObjectId(user["branch_id"]) if user.get("branch_id") else None
    count = await db.quotations.count_documents({"company_id": ObjectId(user["company_id"])})
    quotation_number = f"COT-{count + 1:04d}"
    now = datetime.now(timezone.utc)
    expiry_date = (now + timedelta(days=data.validity_days)).strftime("%Y-%m-%d")
    
    quotation_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": branch_id,
        "patient_id": ObjectId(data.patient_id),
        "quotation_number": quotation_number,
        "items": data.items,
        "subtotal": data.subtotal,
        "discount": data.discount,
        "discount_type": data.discount_type,
        "total": data.total,
        "notes": data.notes,
        "payment_conditions": data.payment_conditions,
        "validity_days": data.validity_days,
        "expiry_date": expiry_date,
        "status": "pendiente",
        "created_at": now.isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    result = await db.quotations.insert_one(quotation_doc)
    return {"_id": str(result.inserted_id), "quotation_number": quotation_number, "message": "Cotizacion creada"}

@router.get("/{quotation_id}")
async def get_quotation(quotation_id: str, user: dict = Depends(get_current_user)):
    q = await db.quotations.find_one({"_id": ObjectId(quotation_id)})
    if not q or str(q["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cotizacion no encontrada")
    serialize_doc(q)
    for e in q.get("emails_sent", []) or []:
        if isinstance(e.get("sent_by"), ObjectId):
            e["sent_by"] = str(e["sent_by"])
    if q.get("patient_id"):
        patient = await db.patients.find_one({"_id": ObjectId(q["patient_id"])}, {"first_name": 1, "last_name": 1, "phone": 1, "email": 1, "whatsapp": 1})
        if patient:
            q["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
            q["patient_phone"] = patient.get("phone", "")
            q["patient_email"] = patient.get("email", "")
            q["patient_whatsapp"] = patient.get("whatsapp", "")
    return serialize_doc(q)

@router.put("/{quotation_id}/status")
async def update_quotation_status(quotation_id: str, data: QuotationStatusUpdate, user: dict = Depends(get_current_user)):
    q = await db.quotations.find_one({"_id": ObjectId(quotation_id)})
    if not q or str(q["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cotizacion no encontrada")
    if data.status not in ["aceptada", "rechazada", "vencida"]:
        raise HTTPException(status_code=400, detail="Estado invalido")
    await db.quotations.update_one(
        {"_id": ObjectId(quotation_id)},
        {"$set": {"status": data.status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": f"Cotizacion {data.status}"}

@router.post("/{quotation_id}/convert")
async def convert_quotation_to_sale(quotation_id: str, payment_method: str = "efectivo", amount_paid: float = 0, user: dict = Depends(get_current_user)):
    q = await db.quotations.find_one({"_id": ObjectId(quotation_id)})
    if not q or str(q["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cotizacion no encontrada")
    if q["status"] != "pendiente" and q["status"] != "aceptada":
        raise HTTPException(status_code=400, detail="Solo cotizaciones pendientes o aceptadas pueden convertirse en venta")
    
    branch_id = q.get("branch_id")
    sale_doc = {
        "company_id": q["company_id"], "branch_id": branch_id,
        "patient_id": q.get("patient_id"), "items": q["items"],
        "subtotal": q["subtotal"], "discount": q["discount"], "tax": 0, "total": q["total"],
        "payment_method": payment_method,
        "amount_paid": amount_paid if amount_paid > 0 else q["total"],
        "balance": q["total"] - (amount_paid if amount_paid > 0 else q["total"]),
        "status": "completada" if (amount_paid if amount_paid > 0 else q["total"]) >= q["total"] else "pendiente",
        "notes": f"Generada desde cotizacion {q.get('quotation_number', quotation_id[-6:])}",
        "quotation_id": ObjectId(quotation_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    sale_result = await db.sales.insert_one(sale_doc)
    
    for item in q["items"]:
        if item.get("product_id") and branch_id:
            await db.stock.update_one(
                {"product_id": ObjectId(item["product_id"]), "branch_id": branch_id},
                {"$inc": {"quantity": -item.get("quantity", 1)}}
            )
            await db.inventory_movements.insert_one({
                "company_id": q["company_id"], "branch_id": branch_id,
                "product_id": ObjectId(item["product_id"]), "type": "salida",
                "quantity": item.get("quantity", 1),
                "notes": f"Venta desde cotizacion {q.get('quotation_number', '')}",
                "reference": str(sale_result.inserted_id),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": ObjectId(user["_id"])
            })
    
    paid = amount_paid if amount_paid > 0 else q["total"]
    finance_doc = {
        "company_id": q["company_id"], "branch_id": branch_id,
        "type": "ingreso", "category": "ventas", "amount": paid,
        "description": f"Venta #{str(sale_result.inserted_id)[-6:]} (cotizacion {q.get('quotation_number', '')})",
        "reference_id": sale_result.inserted_id, "reference_type": "sale",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    await db.finance_entries.insert_one(finance_doc)
    
    await db.quotations.update_one(
        {"_id": ObjectId(quotation_id)},
        {"$set": {"status": "convertida", "sale_id": sale_result.inserted_id, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"_id": str(sale_result.inserted_id), "message": "Cotizacion convertida a venta exitosamente"}

async def _build_quotation_pdf_bytes(q: dict, patient: Optional[dict], company: Optional[dict]) -> bytes:
    """Construye el PDF de una cotizacion y retorna los bytes. La generacion
    (CPU-bound reportlab) corre en un hilo para no bloquear el event loop."""
    return await asyncio.to_thread(_render_quotation_pdf, q, patient, company)


def _render_quotation_pdf(q: dict, patient: Optional[dict], company: Optional[dict]) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    draw_pdf_header(c, width, height, company, "COTIZACION")

    c.setFont("Helvetica-Bold", 11)
    y = height - 2.1*inch
    c.drawString(1*inch, y, f"No: {q.get('quotation_number', '')}")
    c.drawString(5*inch, y, f"Fecha: {q['created_at'][:10]}")
    y -= 0.25*inch
    c.setFont("Helvetica", 11)
    c.drawString(1*inch, y, f"Paciente: {patient['first_name']} {patient['last_name']}" if patient else "")
    c.drawString(5*inch, y, f"Vigencia: {q.get('expiry_date', '')}")
    y -= 0.2*inch
    if patient and patient.get("phone"):
        c.drawString(1*inch, y, f"Tel: {patient['phone']}")

    y -= 0.5*inch
    c.setFillColor(colors.HexColor("#0F4C3A"))
    c.rect(0.8*inch, y - 0.05*inch, 6.4*inch, 0.35*inch, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    col_x = [0.9*inch, 1.5*inch, 5*inch, 5.7*inch, 6.4*inch]
    c.drawString(col_x[0], y + 0.05*inch, "#")
    c.drawString(col_x[1], y + 0.05*inch, "DESCRIPCION")
    c.drawString(col_x[2], y + 0.05*inch, "CANT")
    c.drawString(col_x[3], y + 0.05*inch, "PRECIO")
    c.drawString(col_x[4], y + 0.05*inch, "TOTAL")

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    y -= 0.4*inch
    for i, item in enumerate(q.get("items", []), 1):
        if y < 2.5*inch:
            break
        c.drawString(col_x[0], y, str(i))
        c.drawString(col_x[1], y, item.get("name", "Producto")[:35])
        c.drawString(col_x[2], y, str(item.get("quantity", 1)))
        c.drawRightString(6.2*inch, y, f"Q{item.get('unit_price', 0):,.2f}")
        c.drawRightString(7.1*inch, y, f"Q{item.get('subtotal', 0):,.2f}")
        y -= 0.3*inch
        c.setStrokeColor(colors.HexColor("#E2E8F0"))
        c.line(0.8*inch, y + 0.15*inch, 7.2*inch, y + 0.15*inch)

    y -= 0.2*inch
    c.setFont("Helvetica", 11)
    c.drawRightString(6.2*inch, y, "Subtotal:")
    c.drawRightString(7.1*inch, y, f"Q{q.get('subtotal', 0):,.2f}")

    if q.get("discount", 0) > 0:
        y -= 0.3*inch
        c.drawRightString(6.2*inch, y, "Descuento:")
        c.setFillColor(colors.HexColor("#DC2626"))
        c.drawRightString(7.1*inch, y, f"-Q{q.get('discount', 0):,.2f}")
        c.setFillColor(colors.black)

    y -= 0.35*inch
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(6.2*inch, y, "TOTAL:")
    c.drawRightString(7.1*inch, y, f"Q{q.get('total', 0):,.2f}")

    y -= 0.6*inch
    if q.get("notes"):
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1*inch, y, "Notas:")
        c.setFont("Helvetica", 10)
        y -= 0.2*inch
        for line in q["notes"][:200].split("\n"):
            c.drawString(1*inch, y, line[:80])
            y -= 0.2*inch

    if q.get("payment_conditions"):
        y -= 0.15*inch
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1*inch, y, "Condiciones de Pago:")
        c.setFont("Helvetica", 10)
        y -= 0.2*inch
        c.drawString(1*inch, y, q["payment_conditions"][:100])

    y -= 0.5*inch
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.HexColor("#64748B"))
    c.drawString(1*inch, y, f"* Esta cotizacion es valida por {q.get('validity_days', 15)} dias hasta el {q.get('expiry_date', '')}.")

    c.setFillColor(colors.HexColor("#0F4C3A"))
    c.rect(0, 0, width, 0.5*inch, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 8)
    c.drawCentredString(width/2, 0.2*inch, f"{company['name'] if company else 'Cortexia Optical'} - {company.get('phone', '') if company else ''}")

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


@router.get("/{quotation_id}/pdf")
async def get_quotation_pdf(quotation_id: str, user: dict = Depends(get_current_user)):
    q = await db.quotations.find_one({"_id": ObjectId(quotation_id)})
    if not q or str(q["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cotizacion no encontrada")
    patient = await db.patients.find_one({"_id": q["patient_id"]})
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    pdf_bytes = await _build_quotation_pdf_bytes(q, patient, company)
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename=cotizacion_{q.get('quotation_number', quotation_id)}.pdf"})


@router.post("/{quotation_id}/send-email")
async def send_quotation_email(quotation_id: str, user: dict = Depends(get_current_user)):
    """Envia el PDF de la cotizacion al paciente via Resend."""
    from email_service import send_email, render_quotation_email

    q = await db.quotations.find_one({"_id": ObjectId(quotation_id)})
    if not q or str(q["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cotizacion no encontrada")

    patient = await db.patients.find_one({"_id": q["patient_id"]})
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    if not patient.get("email"):
        raise HTTPException(status_code=400, detail="El paciente no tiene email registrado")

    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    pdf_bytes = await _build_quotation_pdf_bytes(q, patient, company)

    quotation_number = q.get("quotation_number", str(q["_id"])[-6:])
    total_str = f"Q{q.get('total', 0):,.2f}"
    company_name = company.get("name", "Cortexia Optical") if company else "Cortexia Optical"

    html = render_quotation_email(
        patient_name=f"{patient['first_name']} {patient['last_name']}",
        company_name=company_name,
        quotation_number=quotation_number,
        total_str=total_str,
        expiry_date=q.get("expiry_date", ""),
        notes=q.get("notes"),
    )
    ok = await send_email(
        patient["email"],
        f"Cotizacion {quotation_number} - {company_name}",
        html,
        tag="quotation",
        attachments=[{
            "filename": f"cotizacion_{quotation_number}.pdf",
            "content": pdf_bytes,
            "content_type": "application/pdf",
        }],
    )
    if not ok:
        raise HTTPException(status_code=502, detail="No se pudo enviar el email. Revisa el log del servidor.")

    # Registrar el envio en la cotizacion
    await db.quotations.update_one(
        {"_id": q["_id"]},
        {"$push": {"emails_sent": {
            "to": patient["email"],
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "sent_by": ObjectId(user["_id"]),
            "sent_by_name": user.get("name", ""),
        }}}
    )

    return {"message": "Cotizacion enviada", "to": patient["email"]}

