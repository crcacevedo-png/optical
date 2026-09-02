from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from bson import ObjectId
from datetime import datetime, timezone, date, timedelta
from urllib.parse import quote
from typing import Optional
import io
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

from db import db, serialize_doc, calculate_age, UPLOADS_DIR
from auth_utils import get_current_user
from models import EyeglassPrescriptionCreate, ContactLensPrescriptionCreate, MedicalPrescriptionCreate

router = APIRouter(prefix="/prescriptions", tags=["Recetas"])

HALF_LETTER = (8.5*inch, 5.5*inch)

def get_logo_path(company):
    if company and company.get("logo_filename"):
        candidate = UPLOADS_DIR / company["logo_filename"]
        if candidate.exists():
            return str(candidate)
    return None

def get_rx_style(company, rx_type="optica"):
    ps = (company or {}).get("prescription_style", {})
    style = ps.get(rx_type, ps)
    return {
        "font": style.get("font", "Helvetica"),
        "size": style.get("size", "standard"),
        "show_logo": style.get("show_logo", True),
        "header_text": style.get("header_text", ""),
        "footer_text": style.get("footer_text", ""),
        "template": style.get("template", "clasico"),
    }

def draw_rx_clasico(c, w, h, company, title, style, logo_path):
    c.setFillColor(colors.HexColor("#0F4C3A"))
    c.rect(0, h - 0.9*inch, w, 0.9*inch, fill=True, stroke=False)
    text_x = 0.4*inch
    if style["show_logo"] and logo_path:
        try:
            img = ImageReader(logo_path)
            iw, ih = img.getSize()
            aspect = iw / ih
            lh = 0.55*inch
            lw = min(lh * aspect, 1.2*inch)
            lh = lw / aspect
            c.drawImage(logo_path, 0.3*inch, h - 0.78*inch, width=lw, height=lh, preserveAspectRatio=True, mask='auto')
            text_x = 0.35*inch + lw + 0.15*inch
        except Exception:
            pass
    c.setFillColor(colors.white)
    font = style["font"]
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 13)
    c.drawString(text_x, h - 0.45*inch, (company or {}).get("name", "Cortexia Optical"))
    c.setFont(font, 7)
    c.drawString(text_x, h - 0.6*inch, (company or {}).get("address", ""))
    phone = (company or {}).get("phone", "")
    email = (company or {}).get("email", "")
    if phone or email:
        c.drawString(text_x, h - 0.72*inch, f"Tel: {phone}  |  {email}" if email else f"Tel: {phone}")
    c.setFillColor(colors.black)
    if style["header_text"]:
        c.setFont(font, 6)
        c.setFillColor(colors.HexColor("#666666"))
        c.drawCentredString(w/2, h - 1.02*inch, style["header_text"])
        c.setFillColor(colors.black)
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 10)
    c.drawCentredString(w/2, h - 1.18*inch, title)
    c.setStrokeColor(colors.HexColor("#0F4C3A"))
    c.setLineWidth(0.5)
    c.line(0.3*inch, h - 1.25*inch, w - 0.3*inch, h - 1.25*inch)
    c.setStrokeColor(colors.black)
    return h - 1.4*inch

def draw_rx_moderno(c, w, h, company, title, style, logo_path):
    c.setFillColor(colors.HexColor("#1ABC9C"))
    c.rect(0, 0, 0.18*inch, h, fill=True, stroke=False)
    c.setFillColor(colors.HexColor("#F8FAFB"))
    c.rect(0.18*inch, h - 1.1*inch, w - 0.18*inch, 1.1*inch, fill=True, stroke=False)
    text_x = 0.45*inch
    if style["show_logo"] and logo_path:
        try:
            img = ImageReader(logo_path)
            iw, ih = img.getSize()
            aspect = iw / ih
            lh = 0.6*inch
            lw = min(lh * aspect, 1.2*inch)
            lh = lw / aspect
            c.drawImage(logo_path, 0.4*inch, h - 0.85*inch, width=lw, height=lh, preserveAspectRatio=True, mask='auto')
            text_x = 0.45*inch + lw + 0.15*inch
        except Exception:
            pass
    font = style["font"]
    c.setFillColor(colors.HexColor("#1B2A49"))
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 14)
    c.drawString(text_x, h - 0.45*inch, (company or {}).get("name", "Cortexia Optical"))
    c.setFont(font, 7)
    c.setFillColor(colors.HexColor("#5A6A7A"))
    c.drawString(text_x, h - 0.6*inch, (company or {}).get("address", ""))
    phone = (company or {}).get("phone", "")
    email = (company or {}).get("email", "")
    if phone or email:
        c.drawString(text_x, h - 0.72*inch, f"Tel: {phone}  |  {email}" if email else f"Tel: {phone}")
    title_w = c.stringWidth(title, f"{font}-Bold" if font != "Courier" else font, 9) + 0.5*inch
    title_x = w/2 - title_w/2
    c.setFillColor(colors.HexColor("#1ABC9C"))
    c.roundRect(title_x, h - 1.25*inch, title_w, 0.28*inch, 0.1*inch, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 9)
    c.drawCentredString(w/2, h - 1.19*inch, title)
    if style["header_text"]:
        c.setFillColor(colors.HexColor("#888888"))
        c.setFont(font, 6)
        c.drawCentredString(w/2, h - 1.4*inch, style["header_text"])
    c.setFillColor(colors.black)
    return h - 1.55*inch

def draw_rx_elegante(c, w, h, company, title, style, logo_path):
    c.setStrokeColor(colors.HexColor("#5A2D82"))
    c.setLineWidth(1.5)
    c.rect(0.2*inch, 0.2*inch, w - 0.4*inch, h - 0.4*inch, fill=False, stroke=True)
    c.setLineWidth(0.5)
    c.rect(0.28*inch, 0.28*inch, w - 0.56*inch, h - 0.56*inch, fill=False, stroke=True)
    c.setStrokeColor(colors.black)
    if style["show_logo"] and logo_path:
        try:
            img = ImageReader(logo_path)
            iw, ih = img.getSize()
            aspect = iw / ih
            lh = 0.55*inch
            lw = min(lh * aspect, 1.2*inch)
            lh = lw / aspect
            c.drawImage(logo_path, w/2 - lw/2, h - 0.4*inch - lh, width=lw, height=lh, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    font = style["font"]
    y_top = h - 1.05*inch
    c.setFillColor(colors.HexColor("#5A2D82"))
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 14)
    c.drawCentredString(w/2, y_top, (company or {}).get("name", "Cortexia Optical"))
    c.setFont(font, 7)
    c.setFillColor(colors.HexColor("#666666"))
    c.drawCentredString(w/2, y_top - 0.16*inch, (company or {}).get("address", ""))
    phone = (company or {}).get("phone", "")
    email = (company or {}).get("email", "")
    if phone or email:
        c.drawCentredString(w/2, y_top - 0.3*inch, f"Tel: {phone}  |  {email}" if email else f"Tel: {phone}")
    c.setStrokeColor(colors.HexColor("#5A2D82"))
    c.setLineWidth(0.8)
    c.line(0.6*inch, y_top - 0.45*inch, w - 0.6*inch, y_top - 0.45*inch)
    c.setLineWidth(0.3)
    c.line(0.6*inch, y_top - 0.5*inch, w - 0.6*inch, y_top - 0.5*inch)
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.HexColor("#5A2D82"))
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 11)
    c.drawCentredString(w/2, y_top - 0.68*inch, title)
    if style["header_text"]:
        c.setFillColor(colors.HexColor("#888888"))
        c.setFont(font, 6)
        c.drawCentredString(w/2, y_top - 0.82*inch, style["header_text"])
    c.setFillColor(colors.black)
    return y_top - 0.95*inch

STYLE_RENDERERS = {"clasico": draw_rx_clasico, "moderno": draw_rx_moderno, "elegante": draw_rx_elegante}

def draw_rx_header(c, w, h, company, title, style, logo_path):
    template = style.get("template", "clasico")
    renderer = STYLE_RENDERERS.get(template, draw_rx_clasico)
    return renderer(c, w, h, company, title, style, logo_path)

def draw_rx_footer(c, w, style, professional_name):
    font = style["font"]
    y = 0.9*inch
    c.line(0.4*inch, y, 2.2*inch, y)
    c.setFont(font, 8)
    c.drawString(0.4*inch, y - 0.15*inch, professional_name or "")
    c.setFont(font, 7)
    c.drawString(0.4*inch, y - 0.3*inch, "Profesional de la Salud Visual")
    if style.get("footer_text"):
        c.setFillColor(colors.HexColor("#888888"))
        c.setFont(font, 6)
        c.drawCentredString(w/2, 0.35*inch, style["footer_text"])
        c.setFillColor(colors.black)

# ==================== EYEGLASS ====================
@router.get("/eyeglass")
async def list_eyeglass_prescriptions(user: dict = Depends(get_current_user), patient_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    query = {"company_id": ObjectId(user["company_id"])}
    if patient_id:
        query["patient_id"] = ObjectId(patient_id)
    prescriptions = await db.eyeglass_prescriptions.find(query).sort("created_at", -1).to_list(100)
    for rx in prescriptions:
        serialize_doc(rx)
    patient_ids = list({ObjectId(rx["patient_id"]) for rx in prescriptions if rx.get("patient_id")})
    if patient_ids:
        patients = await db.patients.find(
            {"_id": {"$in": patient_ids}},
            {"first_name": 1, "last_name": 1, "phone": 1, "whatsapp": 1},
        ).to_list(len(patient_ids))
        patient_map = {str(p["_id"]): p for p in patients}
        for rx in prescriptions:
            serialize_doc(rx)
            p = patient_map.get(rx.get("patient_id")) or {}
            rx["patient_name"] = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
            rx["patient_phone"] = p.get("phone", "") or ""
            rx["patient_whatsapp"] = p.get("whatsapp", "") or ""
    return [serialize_doc(rx) for rx in prescriptions]

@router.post("/eyeglass")
async def create_eyeglass_prescription(data: EyeglassPrescriptionCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    rx_doc = {
        "company_id": ObjectId(user["company_id"]), "patient_id": ObjectId(data.patient_id),
        "consultation_id": ObjectId(data.consultation_id) if data.consultation_id else None,
        "professional_name": data.professional_name or user["name"],
        "od_sphere": data.od_sphere, "od_cylinder": data.od_cylinder, "od_axis": data.od_axis,
        "od_addition": data.od_addition, "od_dp": data.od_dp,
        "oi_sphere": data.oi_sphere, "oi_cylinder": data.oi_cylinder, "oi_axis": data.oi_axis,
        "oi_addition": data.oi_addition, "oi_dp": data.oi_dp,
        "observations": data.observations, "lens_type": data.lens_type, "frame_type": data.frame_type,
        "created_at": datetime.now(timezone.utc).isoformat(), "created_by": ObjectId(user["_id"])
    }
    result = await db.eyeglass_prescriptions.insert_one(rx_doc)
    return {"_id": str(result.inserted_id), "message": "Receta creada"}

@router.get("/eyeglass/{rx_id}/pdf")
async def get_eyeglass_prescription_pdf(rx_id: str, user: dict = Depends(get_current_user)):
    rx = await db.eyeglass_prescriptions.find_one({"_id": ObjectId(rx_id)})
    if not rx or str(rx["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    patient = await db.patients.find_one({"_id": rx["patient_id"]})
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    style = get_rx_style(company, "optica")
    logo_path = get_logo_path(company)
    font = style["font"]
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=HALF_LETTER)
    w, h = HALF_LETTER
    y = draw_rx_header(c, w, h, company, "RECETA DE ANTEOJOS", style, logo_path)
    c.setFont(font, 8)
    c.drawString(0.4*inch, y, f"Paciente: {patient['first_name']} {patient['last_name']}" if patient else "")
    c.drawString(3.2*inch, y, f"Fecha: {rx['created_at'][:10]}")
    y -= 0.2*inch
    if patient and patient.get("birth_date"):
        age = calculate_age(patient["birth_date"])
        if age:
            c.drawString(0.4*inch, y, f"Edad: {age} anos")
    c.drawString(3.2*inch, y, f"Dr(a): {rx.get('professional_name', '')}")
    y -= 0.35*inch
    c.setFillColor(colors.HexColor("#F1F5F9"))
    c.rect(0.3*inch, y - 0.65*inch, w - 0.6*inch, 0.85*inch, fill=True, stroke=False)
    c.setFillColor(colors.black)
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 8)
    headers = ["", "ESFERA", "CIL", "EJE", "ADD", "D.P."]
    xp = [0.4*inch, 1.1*inch, 1.9*inch, 2.7*inch, 3.4*inch, 4.2*inch]
    for i, hdr in enumerate(headers):
        c.drawString(xp[i], y, hdr)
    y -= 0.28*inch
    c.setFont(font, 9)
    c.setFillColor(colors.HexColor("#1D4ED8"))
    c.drawString(xp[0], y, "OD")
    c.setFillColor(colors.black)
    c.drawString(xp[1], y, str(rx.get("od_sphere") or "-"))
    c.drawString(xp[2], y, str(rx.get("od_cylinder") or "-"))
    c.drawString(xp[3], y, (str(rx.get("od_axis")) + "\u00b0") if rx.get("od_axis") else "-")
    c.drawString(xp[4], y, str(rx.get("od_addition") or "-"))
    c.drawString(xp[5], y, str(rx.get("od_dp") or "-"))
    y -= 0.28*inch
    c.setFillColor(colors.HexColor("#15803D"))
    c.drawString(xp[0], y, "OS")
    c.setFillColor(colors.black)
    c.drawString(xp[1], y, str(rx.get("oi_sphere") or "-"))
    c.drawString(xp[2], y, str(rx.get("oi_cylinder") or "-"))
    c.drawString(xp[3], y, (str(rx.get("oi_axis")) + "\u00b0") if rx.get("oi_axis") else "-")
    c.drawString(xp[4], y, str(rx.get("oi_addition") or "-"))
    c.drawString(xp[5], y, str(rx.get("oi_dp") or "-"))
    y -= 0.45*inch
    if rx.get("lens_type"):
        c.setFont(f"{font}-Bold" if font != "Courier" else font, 8)
        c.drawString(0.4*inch, y, "Tipo de Lente:")
        c.setFont(font, 8)
        c.drawString(1.5*inch, y, rx["lens_type"])
        y -= 0.2*inch
    if rx.get("observations"):
        c.setFont(f"{font}-Bold" if font != "Courier" else font, 8)
        c.drawString(0.4*inch, y, "Observaciones:")
        c.setFont(font, 8)
        c.drawString(1.6*inch, y, rx["observations"][:60])
    draw_rx_footer(c, w, style, rx.get("professional_name", ""))
    c.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                           headers={"Content-Disposition": f"attachment; filename=receta_anteojos_{rx_id}.pdf"})

# ==================== CONTACT LENS ====================
@router.get("/contact")
async def list_contact_lens_prescriptions(user: dict = Depends(get_current_user), patient_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    query = {"company_id": ObjectId(user["company_id"])}
    if patient_id:
        query["patient_id"] = ObjectId(patient_id)
    prescriptions = await db.contact_lens_prescriptions.find(query).sort("created_at", -1).to_list(100)
    for rx in prescriptions:
        serialize_doc(rx)
    patient_ids = list({ObjectId(rx["patient_id"]) for rx in prescriptions if rx.get("patient_id")})
    if patient_ids:
        patients = await db.patients.find(
            {"_id": {"$in": patient_ids}},
            {"first_name": 1, "last_name": 1, "phone": 1, "whatsapp": 1},
        ).to_list(len(patient_ids))
        patient_map = {str(p["_id"]): p for p in patients}
        for rx in prescriptions:
            serialize_doc(rx)
            p = patient_map.get(rx.get("patient_id")) or {}
            rx["patient_name"] = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
            rx["patient_phone"] = p.get("phone", "") or ""
            rx["patient_whatsapp"] = p.get("whatsapp", "") or ""
    return [serialize_doc(rx) for rx in prescriptions]

# Dias de uso por tipo de reemplazo (base para calcular vencimiento).
# "Diario" = por caja (~30 dias). El resto segun su ciclo.
REPLACEMENT_DAYS = {
    "diario": 30,
    "quincenal": 15,
    "mensual": 30,
    "trimestral": 90,
    "anual": 365,
}

@router.get("/contact/replacement-reminders")
async def contact_replacement_reminders(
    user: dict = Depends(get_current_user),
    days_ahead: int = 5,
):
    """Lentes de contacto proximos a vencer (o vencidos) segun el tipo de
    reemplazo, contando desde la fecha de la receta. Devuelve un mensaje
    pre-armado para compartir por WhatsApp Web (envio manual)."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    if days_ahead < 0 or days_ahead > 60:
        raise HTTPException(status_code=400, detail="days_ahead debe estar entre 0 y 60")
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])}, {"name": 1}) or {}
    company_name = company.get("name") or "Cortexia Optical"
    rxs = await db.contact_lens_prescriptions.find(
        {"company_id": ObjectId(user["company_id"]), "replacement": {"$nin": [None, ""]}}
    ).sort("created_at", -1).to_list(3000)
    # Dedup por paciente: se conserva solo la receta mas reciente (la primera por sort desc).
    seen: set = set()
    latest: list = []
    for rx in rxs:
        key = str(rx.get("patient_id") or rx.get("_id"))
        if key in seen:
            continue
        seen.add(key)
        latest.append(rx)
    pids = [rx["patient_id"] for rx in latest if rx.get("patient_id")]
    pmap: dict = {}
    if pids:
        docs = await db.patients.find(
            {"_id": {"$in": pids}}, {"first_name": 1, "last_name": 1, "phone": 1, "whatsapp": 1}
        ).to_list(len(pids))
        pmap = {str(d["_id"]): d for d in docs}
    today = date.today()
    out: list = []
    for rx in latest:
        interval = REPLACEMENT_DAYS.get((rx.get("replacement") or "").strip().lower())
        if not interval:
            continue
        try:
            start = date.fromisoformat((rx.get("created_at") or "")[:10])
        except ValueError:
            continue
        due = start + timedelta(days=interval)
        days_remaining = (due - today).days
        if days_remaining > days_ahead:
            continue  # aun no entra en la ventana de aviso
        p = pmap.get(str(rx.get("patient_id"))) or {}
        first = p.get("first_name", "") or ""
        name = f"{first} {p.get('last_name','')}".strip() or "Paciente"
        phone = (p.get("whatsapp") or p.get("phone") or "").strip()
        digits = "".join(ch for ch in phone if ch.isdigit())
        if digits and len(digits) == 8:
            digits = "502" + digits
        overdue = days_remaining < 0
        when = f"vencieron el {due.isoformat()}" if overdue else f"vencen el {due.isoformat()}"
        message = (
            f"Hola {first}, en {company_name} le recordamos que sus lentes de contacto "
            f"({rx.get('replacement')}) {when}. Le recomendamos reponerlos a tiempo para "
            f"cuidar su salud visual. Con gusto le ayudamos a renovarlos. Gracias!"
        )
        out.append({
            "_id": str(rx["_id"]),
            "patient_id": str(rx.get("patient_id")) if rx.get("patient_id") else None,
            "patient_name": name,
            "patient_phone": phone,
            "brand": rx.get("brand") or "",
            "replacement": rx.get("replacement") or "",
            "created_at": (rx.get("created_at") or "")[:10],
            "due_date": due.isoformat(),
            "days_remaining": days_remaining,
            "status": "vencida" if overdue else "por_vencer",
            "whatsapp_url": (f"https://wa.me/{digits}?text={quote(message)}") if digits else None,
            "reminder_message": message,
        })
    out.sort(key=lambda x: x["due_date"])
    return {"count": len(out), "days_ahead": days_ahead, "items": out}

@router.post("/contact")
async def create_contact_lens_prescription(data: ContactLensPrescriptionCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    rx_doc = {
        "company_id": ObjectId(user["company_id"]), "patient_id": ObjectId(data.patient_id),
        "consultation_id": ObjectId(data.consultation_id) if data.consultation_id else None,
        "professional_name": data.professional_name or user["name"],
        "od_power": data.od_power, "od_bc": data.od_bc, "od_dia": data.od_dia,
        "od_cylinder": data.od_cylinder, "od_axis": data.od_axis, "od_addition": data.od_addition,
        "oi_power": data.oi_power, "oi_bc": data.oi_bc, "oi_dia": data.oi_dia,
        "oi_cylinder": data.oi_cylinder, "oi_axis": data.oi_axis, "oi_addition": data.oi_addition,
        "brand": data.brand, "lens_type": data.lens_type, "replacement": data.replacement,
        "observations": data.observations,
        "created_at": datetime.now(timezone.utc).isoformat(), "created_by": ObjectId(user["_id"])
    }
    result = await db.contact_lens_prescriptions.insert_one(rx_doc)
    return {"_id": str(result.inserted_id), "message": "Receta de lentes de contacto creada"}

@router.get("/contact/{rx_id}/pdf")
async def get_contact_lens_prescription_pdf(rx_id: str, user: dict = Depends(get_current_user)):
    rx = await db.contact_lens_prescriptions.find_one({"_id": ObjectId(rx_id)})
    if not rx or str(rx["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    patient = await db.patients.find_one({"_id": rx["patient_id"]})
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    style = get_rx_style(company, "optica")
    logo_path = get_logo_path(company)
    font = style["font"]
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=HALF_LETTER)
    w, h = HALF_LETTER
    y = draw_rx_header(c, w, h, company, "RECETA LENTES DE CONTACTO", style, logo_path)
    c.setFont(font, 8)
    c.drawString(0.4*inch, y, f"Paciente: {patient['first_name']} {patient['last_name']}" if patient else "")
    c.drawString(3.2*inch, y, f"Fecha: {rx['created_at'][:10]}")
    y -= 0.2*inch
    c.drawString(3.2*inch, y, f"Dr(a): {rx.get('professional_name', '')}")
    y -= 0.35*inch
    c.setFillColor(colors.HexColor("#F1F5F9"))
    c.rect(0.3*inch, y - 0.65*inch, w - 0.6*inch, 0.85*inch, fill=True, stroke=False)
    c.setFillColor(colors.black)
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 7)
    headers = ["", "ESF", "CIL", "EJE", "ADD", "DIA", "C.B."]
    xp = [0.4*inch, 1*inch, 1.6*inch, 2.2*inch, 2.8*inch, 3.5*inch, 4.2*inch]
    for i, hdr in enumerate(headers):
        c.drawString(xp[i], y, hdr)
    y -= 0.28*inch
    c.setFont(font, 8)
    c.setFillColor(colors.HexColor("#1D4ED8"))
    c.drawString(xp[0], y, "OD")
    c.setFillColor(colors.black)
    c.drawString(xp[1], y, str(rx.get("od_power") or "-"))
    c.drawString(xp[2], y, str(rx.get("od_cylinder") or "-"))
    c.drawString(xp[3], y, str(rx.get("od_axis") or "-"))
    c.drawString(xp[4], y, str(rx.get("od_addition") or "-"))
    c.drawString(xp[5], y, str(rx.get("od_dia") or "-"))
    c.drawString(xp[6], y, str(rx.get("od_bc") or "-"))
    y -= 0.28*inch
    c.setFillColor(colors.HexColor("#15803D"))
    c.drawString(xp[0], y, "OS")
    c.setFillColor(colors.black)
    c.drawString(xp[1], y, str(rx.get("oi_power") or "-"))
    c.drawString(xp[2], y, str(rx.get("oi_cylinder") or "-"))
    c.drawString(xp[3], y, str(rx.get("oi_axis") or "-"))
    c.drawString(xp[4], y, str(rx.get("oi_addition") or "-"))
    c.drawString(xp[5], y, str(rx.get("oi_dia") or "-"))
    c.drawString(xp[6], y, str(rx.get("oi_bc") or "-"))
    y -= 0.45*inch
    c.setFont(font, 8)
    if rx.get("brand"):
        c.setFont(f"{font}-Bold" if font != "Courier" else font, 8)
        c.drawString(0.4*inch, y, "Marca:")
        c.setFont(font, 8)
        c.drawString(1.1*inch, y, rx["brand"])
    if rx.get("lens_type"):
        c.drawString(2.8*inch, y, f"Tipo: {rx['lens_type']}")
    y -= 0.2*inch
    if rx.get("replacement"):
        c.drawString(0.4*inch, y, f"Reemplazo: {rx['replacement']}")
    if rx.get("observations"):
        y -= 0.25*inch
        c.setFont(f"{font}-Bold" if font != "Courier" else font, 8)
        c.drawString(0.4*inch, y, "Obs:")
        c.setFont(font, 8)
        c.drawString(0.9*inch, y, rx["observations"][:55])
    draw_rx_footer(c, w, style, rx.get("professional_name", ""))
    c.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                           headers={"Content-Disposition": f"attachment; filename=receta_contacto_{rx_id}.pdf"})

# ==================== MEDICAL ====================
@router.get("/medical")
async def list_medical_prescriptions(user: dict = Depends(get_current_user), patient_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    query = {"company_id": ObjectId(user["company_id"])}
    if patient_id:
        query["patient_id"] = ObjectId(patient_id)
    prescriptions = await db.medical_prescriptions.find(query).sort("created_at", -1).to_list(100)
    for rx in prescriptions:
        serialize_doc(rx)
    patient_ids = list({ObjectId(rx["patient_id"]) for rx in prescriptions if rx.get("patient_id")})
    if patient_ids:
        patients = await db.patients.find(
            {"_id": {"$in": patient_ids}},
            {"first_name": 1, "last_name": 1, "phone": 1, "whatsapp": 1},
        ).to_list(len(patient_ids))
        patient_map = {str(p["_id"]): p for p in patients}
        for rx in prescriptions:
            serialize_doc(rx)
            p = patient_map.get(rx.get("patient_id")) or {}
            rx["patient_name"] = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
            rx["patient_phone"] = p.get("phone", "") or ""
            rx["patient_whatsapp"] = p.get("whatsapp", "") or ""
    return [serialize_doc(rx) for rx in prescriptions]

@router.post("/medical")
async def create_medical_prescription(data: MedicalPrescriptionCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    rx_doc = {
        "company_id": ObjectId(user["company_id"]), "patient_id": ObjectId(data.patient_id),
        "consultation_id": ObjectId(data.consultation_id) if data.consultation_id else None,
        "professional_name": data.professional_name or user["name"],
        "diagnosis": data.diagnosis, "medications": data.medications, "instructions": data.instructions,
        "created_at": datetime.now(timezone.utc).isoformat(), "created_by": ObjectId(user["_id"])
    }
    result = await db.medical_prescriptions.insert_one(rx_doc)
    return {"_id": str(result.inserted_id), "message": "Receta medica creada"}

@router.get("/medical/{rx_id}/pdf")
async def get_medical_prescription_pdf(rx_id: str, user: dict = Depends(get_current_user)):
    rx = await db.medical_prescriptions.find_one({"_id": ObjectId(rx_id)})
    if not rx or str(rx["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    patient = await db.patients.find_one({"_id": rx["patient_id"]})
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    style = get_rx_style(company, "medica")
    logo_path = get_logo_path(company)
    font = style["font"]
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=HALF_LETTER)
    w, h = HALF_LETTER
    y = draw_rx_header(c, w, h, company, "RECETA MEDICA", style, logo_path)
    c.setFont(font, 8)
    c.drawString(0.4*inch, y, f"Paciente: {patient['first_name']} {patient['last_name']}" if patient else "")
    c.drawString(3.2*inch, y, f"Fecha: {rx['created_at'][:10]}")
    y -= 0.2*inch
    c.drawString(3.2*inch, y, f"Dr(a): {rx.get('professional_name', '')}")
    if rx.get("diagnosis"):
        y -= 0.35*inch
        c.setFont(f"{font}-Bold" if font != "Courier" else font, 8)
        c.drawString(0.4*inch, y, "Diagnostico:")
        c.setFont(font, 8)
        c.drawString(1.4*inch, y, rx["diagnosis"][:50])
    y -= 0.35*inch
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 9)
    c.drawString(0.4*inch, y, "Medicamentos:")
    y -= 0.22*inch
    c.setFont(font, 8)
    for med in rx.get("medications", []):
        c.drawString(0.5*inch, y, f"Rx  {med.get('name', '')}")
        y -= 0.18*inch
        if med.get("dosage"):
            c.drawString(0.7*inch, y, f"Dosis: {med['dosage']}")
            y -= 0.16*inch
        if med.get("frequency"):
            c.drawString(0.7*inch, y, f"Frecuencia: {med['frequency']}")
            y -= 0.16*inch
        if med.get("duration"):
            c.drawString(0.7*inch, y, f"Duracion: {med['duration']}")
            y -= 0.16*inch
        y -= 0.08*inch
        if y < 1.5*inch:
            break
    if rx.get("instructions"):
        y -= 0.15*inch
        c.setFont(f"{font}-Bold" if font != "Courier" else font, 8)
        c.drawString(0.4*inch, y, "Indicaciones:")
        c.setFont(font, 8)
        y -= 0.18*inch
        c.drawString(0.5*inch, y, rx["instructions"][:70])
    draw_rx_footer(c, w, style, rx.get("professional_name", ""))
    c.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                           headers={"Content-Disposition": f"attachment; filename=receta_medica_{rx_id}.pdf"})
