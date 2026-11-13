from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from bson import ObjectId
from datetime import datetime, timezone, date, timedelta
from urllib.parse import quote
from typing import Optional
import io
import asyncio
from fastapi import Query

from db import db, serialize_doc
from rx_pdf import render_single
from auth_utils import get_current_user
from models import EyeglassPrescriptionCreate, ContactLensPrescriptionCreate, MedicalPrescriptionCreate
from email_service import queue_email, render_prescription_email
import os
import secrets

router = APIRouter(prefix="/prescriptions", tags=["Recetas"])

NON_DELIVERABLE = ("borrador", "anulada", "sustituida")


def _render_eyeglass_pdf(rx, patient, company, copies=1):
    return render_single("eyeglass", rx, patient, company, copies)


def _render_contact_pdf(rx, patient, company, copies=1):
    return render_single("contact", rx, patient, company, copies)


def _render_scleral_pdf(rx, patient, company, copies=1):
    return render_single("scleral", rx, patient, company, copies)


def _render_medical_pdf(rx, patient, company, copies=1):
    return render_single("medical", rx, patient, company, copies)


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
        {"company_id": ObjectId(user["company_id"]), "replacement": {"$nin": [None, ""]}, "status": {"$nin": list(NON_DELIVERABLE)}}
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

# ==================== SCLERAL (solo listado; se crean en el flujo clinico) ====================
@router.get("/scleral")
async def list_scleral_prescriptions(user: dict = Depends(get_current_user), patient_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    query = {"company_id": ObjectId(user["company_id"])}
    if patient_id:
        query["patient_id"] = ObjectId(patient_id)
    rows = await db.scleral_prescriptions.find(query).sort("created_at", -1).to_list(100)
    pids = list({rx["patient_id"] for rx in rows if rx.get("patient_id")})
    pmap = {}
    if pids:
        docs = await db.patients.find({"_id": {"$in": pids}}, {"first_name": 1, "last_name": 1, "phone": 1, "whatsapp": 1}).to_list(len(pids))
        pmap = {d["_id"]: d for d in docs}
    out = []
    for rx in rows:
        p = pmap.get(rx.get("patient_id")) or {}
        rx = serialize_doc(rx)
        rx["patient_name"] = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        rx["patient_phone"] = p.get("phone", "") or ""
        rx["patient_whatsapp"] = p.get("whatsapp", "") or ""
        out.append(rx)
    return out

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

# ==================== ENVIO AL PACIENTE (enlace WhatsApp + correo con PDF) ====================
SHARE_LINK_DAYS = int(os.environ.get("RX_SHARE_LINK_DAYS", "30"))


def _rx_registry():
    """type -> (coleccion, render_fn, etiqueta, prefijo_archivo). Definido como funcion
    para usar los _render_* ya declarados arriba en el modulo."""
    return {
        "eyeglass": (db.eyeglass_prescriptions, _render_eyeglass_pdf, "anteojos", "receta_anteojos"),
        "contact": (db.contact_lens_prescriptions, _render_contact_pdf, "lentes de contacto", "receta_contacto"),
        "scleral": (db.scleral_prescriptions, _render_scleral_pdf, "lentes esclerales", "receta_escleral"),
        "medical": (db.medical_prescriptions, _render_medical_pdf, "medica", "receta_medica"),
    }


async def _load_rx_ctx(rx_type: str, rx_id: str, company_id: str):
    reg = _rx_registry().get(rx_type)
    if not reg:
        raise HTTPException(status_code=404, detail="Tipo de receta invalido")
    coll, render, label, fileprefix = reg
    rx = await coll.find_one({"_id": ObjectId(rx_id)})
    if not rx or str(rx["company_id"]) != str(company_id):
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    patient = await db.patients.find_one({"_id": rx["patient_id"]}) if rx.get("patient_id") else None
    company = await db.companies.find_one({"_id": ObjectId(company_id)})
    return rx, patient, company, render, label, fileprefix


def _assert_deliverable(rx):
    if rx.get("status") in NON_DELIVERABLE:
        raise HTTPException(status_code=400, detail="Solo se pueden enviar recetas emitidas (no borradores, anuladas ni sustituidas)")


@router.get("/{rx_type}/{rx_id}/pdf")
async def get_prescription_pdf(rx_type: str, rx_id: str, copies: int = Query(1, ge=1, le=10),
                               user: dict = Depends(get_current_user)):
    """PDF individual. Borradores/anuladas/sustituidas salen con marca de agua 'SIN VALIDEZ'."""
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    rx, patient, company, render, _label, fileprefix = await _load_rx_ctx(rx_type, rx_id, user["company_id"])
    pdf_bytes = await asyncio.to_thread(render, rx, patient, company, copies)
    if rx.get("status") == "emitida":
        await _rx_registry()[rx_type][0].update_one(
            {"_id": rx["_id"]}, {"$inc": {"print_count": 1}, "$set": {"last_printed_at": datetime.now(timezone.utc).isoformat()}})
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename={fileprefix}_{rx_id}.pdf"})


@router.post("/{rx_type}/{rx_id}/share-link")
async def create_rx_share_link(rx_type: str, rx_id: str, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    rx, _patient, _company, _render, _label, _fp = await _load_rx_ctx(rx_type, rx_id, user["company_id"])
    _assert_deliverable(rx)
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    await db.rx_share_links.insert_one({
        "token": token,
        "rx_type": rx_type,
        "rx_id": ObjectId(rx_id),
        "company_id": ObjectId(user["company_id"]),
        "created_at": now.isoformat(),
        "created_by": ObjectId(user["_id"]),
        "expires_at": now + timedelta(days=SHARE_LINK_DAYS),
    })
    return {"token": token, "expires_in_days": SHARE_LINK_DAYS}


@router.get("/public/{token}")
async def public_rx_pdf(token: str):
    """Descarga publica (sin auth) de la receta mediante un token con expiracion.
    El enlace se comparte por WhatsApp para que el paciente obtenga su PDF."""
    link = await db.rx_share_links.find_one({"token": token})
    if not link:
        raise HTTPException(status_code=404, detail="Enlace invalido o no encontrado")
    exp = link.get("expires_at")
    if isinstance(exp, datetime):
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="El enlace expiro")
    reg = _rx_registry().get(link.get("rx_type"))
    if not reg:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    coll, render, _label, fileprefix = reg
    rx = await coll.find_one({"_id": link["rx_id"]})
    if not rx or rx.get("status") in NON_DELIVERABLE:
        raise HTTPException(status_code=404, detail="Receta no disponible")
    patient = await db.patients.find_one({"_id": rx["patient_id"]}) if rx.get("patient_id") else None
    company = await db.companies.find_one({"_id": rx["company_id"]})
    pdf_bytes = await asyncio.to_thread(render, rx, patient, company)
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                             headers={"Content-Disposition": f"inline; filename={fileprefix}_{str(rx['_id'])}.pdf"})


@router.post("/{rx_type}/{rx_id}/email")
async def email_rx_to_patient(rx_type: str, rx_id: str, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    rx, patient, company, render, label, fileprefix = await _load_rx_ctx(rx_type, rx_id, user["company_id"])
    _assert_deliverable(rx)
    to_email = (patient or {}).get("email")
    if not to_email:
        raise HTTPException(status_code=400, detail="El paciente no tiene correo registrado.")
    pdf_bytes = await asyncio.to_thread(render, rx, patient, company)
    pname = f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip() if patient else ""
    cname = (company or {}).get("name") or "tu optica"
    subject = f"Tu receta de {label} - {cname}"
    html_body = render_prescription_email(pname, label, cname)
    await queue_email(to_email, subject, html_body, tag="prescription", attachments=[
        {"filename": f"{fileprefix}.pdf", "content": pdf_bytes, "content_type": "application/pdf"},
    ])
    return {"ok": True, "email": to_email}
