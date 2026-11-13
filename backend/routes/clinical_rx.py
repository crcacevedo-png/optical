"""Flujo de recetas por examen (anteojos, contacto, esclerales).
Estados: borrador -> emitida -> (sustituida | anulada). Una receta emitida queda
congelada en una instantanea; reimprimir reproduce esos valores. Las recetas
historicas (sin estado) se conservan intactas y se muestran como emitidas."""
import io
import asyncio
from typing import Optional, List
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db import db, serialize_doc, calculate_age
from auth_utils import get_current_user
from audit import log_audit
from rx_pdf import render_pages
from clinical_rules import (
    now_iso, oid, parse_power, parse_axis, eye_errors, has_value, next_code, short_code,
    require_tenant, require_issue, load_patient, load_exam,
    EYE_FIELDS, NUMERIC_EYE, AXIS_EYE, COMMON_FIELDS, KIND_FIELDS, RX_KINDS,
)

router = APIRouter(prefix="/clinical/prescriptions", tags=["Recetas (flujo clinico)"])

NON_DELIVERABLE = ("borrador", "anulada", "sustituida")
ADAPT_KIND = {"contact": "contacto", "scleral": "escleral"}
LONG_TEXT = {"indications", "observations", "manufacturer_params", "special_mods", "usage_instructions", "cleaning"}


def _coll(kind):
    return {"eyeglass": db.eyeglass_prescriptions, "contact": db.contact_lens_prescriptions,
            "scleral": db.scleral_prescriptions, "medical": db.medical_prescriptions}[kind]


def _allowed(kind) -> list:
    return COMMON_FIELDS + KIND_FIELDS[kind] + [f"{e}_{f}" for e in ("od", "oi") for f in EYE_FIELDS[kind]]


def _clean_fields(kind, fields: dict):
    out, errs = {}, []
    for key in _allowed(kind):
        if key not in fields:
            continue
        raw = fields.get(key)
        base = key[3:] if key[:3] in ("od_", "oi_") else None
        label = ("OD " if key.startswith("od_") else "OS ") + base if base else key
        if base in NUMERIC_EYE:
            ok, val = parse_power(raw)
            if not ok:
                errs.append(f"{label}: valor no numerico")
            out[key] = val
        elif base in AXIS_EYE:
            ok, val = parse_axis(raw)
            if not ok:
                errs.append(f"{label}: el eje debe ser un entero entre 0 y 180")
            out[key] = val
        else:
            limit = 1500 if key in LONG_TEXT else 300
            out[key] = (str(raw) if raw is not None else "").strip()[:limit]
            if base in ("base_h", "base_v"):
                out[key] = out[key].upper()
    return out, errs


def _eye(rx, e, kind):
    sph = "sphere" if kind == "eyeglass" else "power"
    return {"sphere": rx.get(f"{e}_{sph}"), "cylinder": rx.get(f"{e}_cylinder"), "axis": rx.get(f"{e}_axis"),
            "addition": rx.get(f"{e}_addition"), "prism_h": rx.get(f"{e}_prism_h"), "base_h": rx.get(f"{e}_base_h"),
            "prism_v": rx.get(f"{e}_prism_v"), "base_v": rx.get(f"{e}_base_v")}


def _issue_errors(kind, rx) -> list:
    errs = []
    eyes = [(e, lbl, _eye(rx, e, kind)) for e, lbl in (("od", "OD"), ("oi", "OS"))]
    for _e, lbl, ev in eyes:
        errs += eye_errors(lbl, ev)
    with_power = [(e, lbl) for e, lbl, ev in eyes if has_value(ev["sphere"])]
    if not with_power:
        errs.append("Indica la " + ("esfera" if kind == "eyeglass" else "potencia") + " de al menos un ojo (usa 'plano' para 0.00)")
    if kind == "contact":
        design = (rx.get("design") or "").lower()
        for e, lbl in with_power:
            if not has_value(rx.get(f"{e}_bc")) or not has_value(rx.get(f"{e}_dia")):
                errs.append(f"{lbl}: indica curva base y diametro")
            if "toric" in design and (not has_value(rx.get(f"{e}_cylinder")) or not has_value(rx.get(f"{e}_axis"))):
                errs.append(f"{lbl}: el diseno torico requiere cilindro y eje")
            if "multifocal" in design and not has_value(rx.get(f"{e}_addition")):
                errs.append(f"{lbl}: el diseno multifocal requiere adicion")
    if kind == "scleral":
        for e, lbl in with_power:
            if not has_value(rx.get(f"{e}_dia")) or not has_value(rx.get(f"{e}_sag")):
                errs.append(f"{lbl}: indica diametro y profundidad sagital")
        if not (rx.get("lab") or rx.get("design")):
            errs.append("Indica el laboratorio o diseno del lente escleral")
    return errs


async def _load_rx(kind, rx_id, user):
    require_tenant(user)
    if kind not in RX_KINDS:
        raise HTTPException(status_code=404, detail="Tipo de receta invalido")
    rx = await _coll(kind).find_one({"_id": oid(rx_id, "Receta")})
    if not rx or str(rx.get("company_id")) != str(user["company_id"]):
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    return rx


async def _check_adaptation(kind, adaptation_id, patient_id, user, must_accept=False):
    if not adaptation_id:
        if must_accept:
            raise HTTPException(status_code=400, detail="Las recetas de contacto y esclerales se emiten desde una adaptacion aceptada")
        return None
    ad = await db.lens_adaptations.find_one({"_id": oid(adaptation_id, "Adaptacion")})
    if not ad or str(ad.get("company_id")) != str(user["company_id"]) or str(ad.get("patient_id")) != str(patient_id):
        raise HTTPException(status_code=400, detail="La adaptacion no corresponde a este paciente")
    if ad.get("kind") != ADAPT_KIND[kind]:
        raise HTTPException(status_code=400, detail="La adaptacion no corresponde al tipo de receta")
    if must_accept and ad.get("status") != "aceptada":
        raise HTTPException(status_code=400, detail="La adaptacion debe estar aceptada para emitir la receta")
    return ad


def _audit(user, action, rx, request, **meta):
    return log_audit(action, actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
                     company_id=user["company_id"], target_id=str(rx.get("_id")), target_type="prescription",
                     metadata={"code": rx.get("code"), "version": rx.get("version"), **meta}, request=request)


def _out(kind, rx, fr_version=None):
    rx = serialize_doc(rx)
    rx["kind"] = kind
    rx["is_historic"] = not rx.get("status")
    rx["code_display"] = rx.get("code") or short_code("RX", rx["_id"])
    src = rx.get("source_ref") or {}
    rx["from_previous_fr"] = bool(kind == "eyeglass" and fr_version and src.get("fr_version") and int(src["fr_version"]) < int(fr_version))
    return rx


class RxIn(BaseModel):
    kind: Optional[str] = None
    patient_id: Optional[str] = None
    consultation_id: Optional[str] = None
    adaptation_id: Optional[str] = None
    fr_version: Optional[int] = None
    fields: dict = {}


class IssueIn(BaseModel):
    confirm_reviewed: bool = False


class ReasonIn(BaseModel):
    reason: Optional[str] = ""


class PrintItem(BaseModel):
    kind: str
    id: str
    copies: int = 1


class PrintIn(BaseModel):
    items: List[PrintItem]
    internal_review: bool = False


@router.get("")
async def list_patient_prescriptions(patient_id: str, consultation_id: Optional[str] = None, scope: str = "exam",
                                     user: dict = Depends(get_current_user)):
    require_tenant(user)
    patient = await load_patient(patient_id, user)
    query = {"company_id": oid(user["company_id"]), "patient_id": patient["_id"]}
    fr_version = None
    if consultation_id:
        exam = await load_exam(consultation_id, user, {"company_id": 1, "final_refraction": 1})
        fr_version = (exam.get("final_refraction") or {}).get("version")
        if scope == "exam":
            query["consultation_id"] = exam["_id"]
    items = []
    for kind in RX_KINDS:
        rows = await _coll(kind).find(query).sort("created_at", -1).to_list(300)
        items += [_out(kind, r, fr_version) for r in rows]
    items.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    medical = [serialize_doc(r) for r in await db.medical_prescriptions.find(query).sort("created_at", -1).to_list(100)]
    return {"items": items, "medical": medical}


@router.post("")
async def create_prescription(data: RxIn, request: Request, user: dict = Depends(get_current_user)):
    require_tenant(user)
    if data.kind not in RX_KINDS:
        raise HTTPException(status_code=400, detail="Tipo de receta invalido")
    patient = await load_patient(data.patient_id, user)
    exam = None
    if data.consultation_id:
        exam = await load_exam(data.consultation_id, user)
        if str(exam.get("patient_id")) != str(patient["_id"]):
            raise HTTPException(status_code=400, detail="El examen no corresponde al paciente")
    if data.kind in ADAPT_KIND:
        await _check_adaptation(data.kind, data.adaptation_id, patient["_id"], user)
    fields, errs = _clean_fields(data.kind, data.fields or {})
    if errs:
        raise HTTPException(status_code=400, detail=" · ".join(errs))
    new_id = ObjectId()
    prof = await db.users.find_one({"_id": exam.get("professional_user_id")}, {"name": 1}) if exam and exam.get("professional_user_id") else None
    ts = now_iso()
    doc = {"_id": new_id, "company_id": oid(user["company_id"]), "patient_id": patient["_id"],
           "consultation_id": exam["_id"] if exam else None, **fields,
           "code": await next_code(user["company_id"], "RX"), "version": 1, "series_id": new_id,
           "status": "borrador", "origin": "workflow",
           "adaptation_id": oid(data.adaptation_id) if data.adaptation_id and data.kind in ADAPT_KIND else None,
           "source_ref": {"fr_version": data.fr_version, "copied_at": ts} if data.kind == "eyeglass" and data.fr_version else None,
           "professional_name": (prof or {}).get("name") or user.get("name", ""),
           "created_at": ts, "updated_at": ts, "created_by": oid(user["_id"])}
    await _coll(data.kind).insert_one(doc)
    await _audit(user, "RX_DRAFT_CREATED", doc, request, kind=data.kind)
    return _out(data.kind, doc)


@router.put("/{kind}/{rx_id}")
async def update_prescription(kind: str, rx_id: str, data: RxIn, user: dict = Depends(get_current_user)):
    rx = await _load_rx(kind, rx_id, user)
    if rx.get("status") != "borrador":
        raise HTTPException(status_code=409, detail="Solo se editan borradores. Crea una nueva version o duplica la receta.")
    fields, errs = _clean_fields(kind, data.fields or {})
    if errs:
        raise HTTPException(status_code=400, detail=" · ".join(errs))
    upd = {**fields, "updated_at": now_iso()}
    if kind in ADAPT_KIND and data.adaptation_id is not None:
        await _check_adaptation(kind, data.adaptation_id or None, rx["patient_id"], user)
        upd["adaptation_id"] = oid(data.adaptation_id) if data.adaptation_id else None
    if kind == "eyeglass" and data.fr_version:
        upd["source_ref"] = {"fr_version": data.fr_version, "copied_at": now_iso()}
    await _coll(kind).update_one({"_id": rx["_id"]}, {"$set": upd})
    return _out(kind, await _coll(kind).find_one({"_id": rx["_id"]}))


@router.post("/{kind}/{rx_id}/issue")
async def issue_prescription(kind: str, rx_id: str, data: IssueIn, request: Request, user: dict = Depends(get_current_user)):
    rx = await _load_rx(kind, rx_id, user)
    if rx.get("status") != "borrador":
        raise HTTPException(status_code=409, detail="Solo se puede emitir un borrador")
    exam = await db.optical_consultations.find_one({"_id": rx["consultation_id"]}) if rx.get("consultation_id") else None
    await require_issue(user, exam)
    if not data.confirm_reviewed:
        raise HTTPException(status_code=400, detail="Confirma que revisaste los valores de esta receta antes de emitirla")
    errs = _issue_errors(kind, rx)
    if errs:
        raise HTTPException(status_code=400, detail=" · ".join(errs))
    source_ref, adaptation = rx.get("source_ref") or {}, None
    if kind == "eyeglass":
        if not exam:
            raise HTTPException(status_code=400, detail="Una receta de anteojos se emite desde un examen con refraccion final validada")
        fr = exam.get("final_refraction") or {}
        validated = [int(h.get("version") or 1) for h in (exam.get("final_refraction_history") or []) if h.get("status") == "validada"]
        if fr.get("status") == "validada":
            validated.append(int(fr.get("version") or 1))
        if not validated:
            raise HTTPException(status_code=400, detail="La refraccion final del examen no esta validada")
        if not source_ref.get("fr_version") or int(source_ref["fr_version"]) not in validated:
            source_ref = {"fr_version": max(validated), "linked_at": now_iso()}
    else:
        adaptation = await _check_adaptation(kind, rx.get("adaptation_id"), rx["patient_id"], user, must_accept=True)
    patient = await db.patients.find_one({"_id": rx["patient_id"]}) or {}
    ts = now_iso()
    snapshot = {
        "values": {k: rx.get(k) for k in _allowed(kind)},
        "patient_name": f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip(),
        "patient_age": calculate_age(patient["birth_date"]) if patient.get("birth_date") else None,
        "patient_dpi": patient.get("dpi") or "",
        "exam_date": (exam or {}).get("consultation_date"), "exam_code": (exam or {}).get("exam_code") or (short_code("EX", exam["_id"]) if exam else None),
        "professional_name": rx.get("professional_name") or user.get("name", ""),
        "fr_version": source_ref.get("fr_version") if kind == "eyeglass" else None,
        "adaptation_title": (adaptation or {}).get("title"), "issued_at": ts,
    }
    await _coll(kind).update_one({"_id": rx["_id"]}, {"$set": {
        "status": "emitida", "issued_at": ts, "issued_by": oid(user["_id"]), "issued_by_name": user.get("name", ""),
        "snapshot": snapshot, "source_ref": source_ref or None}})
    if rx.get("previous_id"):
        await _coll(kind).update_one({"_id": rx["previous_id"], "status": "emitida"}, {"$set": {
            "status": "sustituida", "superseded_by": rx["_id"], "superseded_at": ts}})
    await _audit(user, "RX_ISSUED", rx, request, kind=kind)
    return _out(kind, await _coll(kind).find_one({"_id": rx["_id"]}))


def _copy_values(kind, rx) -> dict:
    snap = (rx.get("snapshot") or {}).get("values") if rx.get("status") in ("emitida", "sustituida") else None
    src = snap or rx
    return {k: src.get(k) for k in _allowed(kind) if k in src}


@router.post("/{kind}/{rx_id}/duplicate")
async def duplicate_prescription(kind: str, rx_id: str, request: Request, user: dict = Depends(get_current_user)):
    rx = await _load_rx(kind, rx_id, user)
    new_id, ts = ObjectId(), now_iso()
    doc = {"_id": new_id, "company_id": rx["company_id"], "patient_id": rx["patient_id"],
           "consultation_id": rx.get("consultation_id"), **_copy_values(kind, rx),
           "code": await next_code(user["company_id"], "RX"), "version": 1, "series_id": new_id,
           "status": "borrador", "origin": "duplicado", "duplicated_from": rx["_id"],
           "adaptation_id": rx.get("adaptation_id"), "source_ref": rx.get("source_ref"),
           "professional_name": rx.get("professional_name") or user.get("name", ""),
           "created_at": ts, "updated_at": ts, "created_by": oid(user["_id"])}
    if doc.get("name"):
        doc["name"] = f"{doc['name']} (copia)"[:300]
    await _coll(kind).insert_one(doc)
    await _audit(user, "RX_DUPLICATED", doc, request, kind=kind, source=str(rx["_id"]))
    return _out(kind, doc)


@router.post("/{kind}/{rx_id}/new-version")
async def new_version(kind: str, rx_id: str, request: Request, user: dict = Depends(get_current_user)):
    rx = await _load_rx(kind, rx_id, user)
    if rx.get("status") != "emitida":
        raise HTTPException(status_code=409, detail="Solo se crea una nueva version de una receta emitida en el flujo actual")
    existing = await _coll(kind).find_one({"previous_id": rx["_id"], "status": "borrador"})
    if existing:
        return _out(kind, existing)
    series = rx.get("series_id") or rx["_id"]
    last = await _coll(kind).find({"series_id": series}).sort("version", -1).limit(1).to_list(1)
    new_id, ts = ObjectId(), now_iso()
    doc = {"_id": new_id, "company_id": rx["company_id"], "patient_id": rx["patient_id"],
           "consultation_id": rx.get("consultation_id"), **_copy_values(kind, rx),
           "code": rx.get("code"), "version": int((last[0] if last else rx).get("version") or 1) + 1, "series_id": series,
           "previous_id": rx["_id"], "status": "borrador", "origin": "nueva_version",
           "adaptation_id": rx.get("adaptation_id"), "source_ref": rx.get("source_ref"),
           "professional_name": rx.get("professional_name") or user.get("name", ""),
           "created_at": ts, "updated_at": ts, "created_by": oid(user["_id"])}
    await _coll(kind).insert_one(doc)
    await _audit(user, "RX_NEW_VERSION", doc, request, kind=kind, previous=str(rx["_id"]))
    return _out(kind, doc)


@router.post("/{kind}/{rx_id}/void")
async def void_prescription(kind: str, rx_id: str, data: ReasonIn, request: Request, user: dict = Depends(get_current_user)):
    rx = await _load_rx(kind, rx_id, user)
    if rx.get("status") not in ("borrador", "emitida"):
        raise HTTPException(status_code=409, detail="Solo se anulan borradores o recetas emitidas del flujo actual")
    exam = await db.optical_consultations.find_one({"_id": rx["consultation_id"]}, {"professional_user_id": 1}) if rx.get("consultation_id") else None
    await require_issue(user, exam)
    reason = (data.reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="Indica el motivo de la anulacion (min. 5 caracteres)")
    await _coll(kind).update_one({"_id": rx["_id"]}, {"$set": {
        "status": "anulada", "voided_at": now_iso(), "voided_by": oid(user["_id"]),
        "voided_by_name": user.get("name", ""), "void_reason": reason[:300]}})
    await _audit(user, "RX_VOIDED", rx, request, kind=kind)
    return _out(kind, await _coll(kind).find_one({"_id": rx["_id"]}))


@router.post("/print")
async def print_prescriptions(data: PrintIn, request: Request, user: dict = Depends(get_current_user)):
    """PDF conjunto: una receta por pagina, copias por receta, sin mezclar pacientes."""
    require_tenant(user)
    if not data.items or len(data.items) > 30:
        raise HTTPException(status_code=400, detail="Selecciona entre 1 y 30 recetas")
    pages, patient_id, loaded = [], None, []
    for it in data.items:
        if it.kind not in RX_KINDS + ("medical",):
            raise HTTPException(status_code=400, detail="Tipo de receta invalido")
        rx = await _coll(it.kind).find_one({"_id": oid(it.id, "Receta")})
        if not rx or str(rx.get("company_id")) != str(user["company_id"]):
            raise HTTPException(status_code=404, detail="Receta no encontrada")
        if patient_id and str(rx.get("patient_id")) != patient_id:
            raise HTTPException(status_code=400, detail="No se pueden mezclar recetas de distintos pacientes")
        patient_id = str(rx.get("patient_id"))
        if rx.get("status") in NON_DELIVERABLE and not data.internal_review:
            raise HTTPException(status_code=400, detail="Solo recetas emitidas entran en la impresion de entrega")
        loaded.append((it, rx))
    patient = await db.patients.find_one({"_id": oid(patient_id)})
    company = await db.companies.find_one({"_id": oid(user["company_id"])})
    for it, rx in loaded:
        pages += [(it.kind, rx, patient)] * max(1, min(int(it.copies or 1), 10))
    if len(pages) > 120:
        raise HTTPException(status_code=400, detail="Demasiadas paginas en una sola impresion")
    pdf = await asyncio.to_thread(render_pages, pages, company)
    ts = now_iso()
    for it, rx in loaded:
        if rx.get("status") not in NON_DELIVERABLE:
            await _coll(it.kind).update_one({"_id": rx["_id"]}, {"$inc": {"print_count": 1}, "$set": {"last_printed_at": ts}})
    await log_audit("RX_PRINTED", actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
                    company_id=user["company_id"], target_id=patient_id, target_type="patient",
                    metadata={"count": len(loaded), "pages": len(pages), "internal_review": data.internal_review}, request=request)
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=recetas_seleccionadas.pdf"})
