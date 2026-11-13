"""Espacio de trabajo por examen: refraccion final versionada, firma/reapertura
y estudios adjuntos. La evaluacion clinica se guarda con PUT /consultations/{id}."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel

from db import db, serialize_doc
from auth_utils import get_current_user
from audit import log_audit
import object_storage as objstore
from clinical_rules import (
    now_iso, eye_errors, has_value, load_exam, require_clinical, require_issue,
    is_exam_professional, short_code,
)

router = APIRouter(prefix="/clinical/exams", tags=["Examen clinico"])

FR_EYE_KEYS = ("sphere", "cyl", "axis", "add", "prism_h", "base_h", "prism_v", "base_v", "va")
FR_KEYS = ("working_distance", "cyl_convention", "observations", "professional_name", "source")
ATT_EXTS = {"pdf", "png", "jpg", "jpeg", "webp"}
ATT_MAX_BYTES = 10 * 1024 * 1024
ATT_MAX_COUNT = 15


class EyeFR(BaseModel):
    sphere: Optional[str] = ""
    cyl: Optional[str] = ""
    axis: Optional[str] = ""
    add: Optional[str] = ""
    prism_h: Optional[str] = ""
    base_h: Optional[str] = ""
    prism_v: Optional[str] = ""
    base_v: Optional[str] = ""
    va: Optional[str] = ""


class FinalRefractionIn(BaseModel):
    od: EyeFR = EyeFR()
    os: EyeFR = EyeFR()
    working_distance: Optional[str] = ""
    cyl_convention: Optional[str] = "negativo"
    observations: Optional[str] = ""
    professional_name: Optional[str] = ""
    source: Optional[str] = "manual"


class ReasonIn(BaseModel):
    reason: Optional[str] = ""


def _audit(user, action, exam_id, request, **meta):
    return log_audit(action, actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
                     company_id=user["company_id"], target_id=str(exam_id), target_type="exam",
                     metadata=meta, request=request)


def _clean_eye(e: EyeFR) -> dict:
    d = {k: (getattr(e, k) or "").strip() for k in FR_EYE_KEYS}
    d["base_h"] = d["base_h"].upper()
    d["base_v"] = d["base_v"].upper()
    return d


def _fr_values(fr: dict) -> dict:
    return {"od": fr.get("od") or {}, "os": fr.get("os") or {}, **{k: fr.get(k) or "" for k in FR_KEYS if k != "source"}}


def _assert_open(exam):
    if exam.get("exam_status") == "firmado":
        raise HTTPException(status_code=409, detail="El examen esta firmado. Reabrelo para modificarlo.")


@router.get("/{exam_id}/workspace")
async def get_workspace(exam_id: str, user: dict = Depends(get_current_user)):
    exam = await load_exam(exam_id, user)
    patient = await db.patients.find_one(
        {"_id": exam["patient_id"]},
        {"first_name": 1, "last_name": 1, "phone": 1, "whatsapp": 1, "email": 1, "dpi": 1, "birth_date": 1, "gender": 1},
    ) or {}
    prof = await db.users.find_one({"_id": exam.get("professional_user_id")}, {"name": 1}) if exam.get("professional_user_id") else None
    serialize_doc(exam)
    for a in exam.get("attachments") or []:
        a.pop("storage_path", None)
    exam["attachments"] = [a for a in (exam.get("attachments") or []) if not a.get("deleted")]
    exam["exam_code"] = exam.get("exam_code") or short_code("EX", exam["_id"])
    exam["exam_status"] = exam.get("exam_status") or "en_curso"
    exam["professional_name"] = (prof or {}).get("name", "")
    exam["patient"] = {
        "_id": str(patient.get("_id", "")), "name": f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip(),
        "phone": patient.get("phone", ""), "whatsapp": patient.get("whatsapp", ""), "email": patient.get("email", ""),
        "dpi": patient.get("dpi", ""), "birth_date": patient.get("birth_date", ""), "gender": patient.get("gender", ""),
    }
    can_issue = True
    try:
        await require_issue(user, exam)
    except HTTPException:
        can_issue = False
    exam["permissions"] = {
        "clinical": user["role"] in ("admin", "doctor") or is_exam_professional(user, exam),
        "issue": can_issue,
    }
    return exam


@router.put("/{exam_id}/final-refraction")
async def save_final_refraction(exam_id: str, data: FinalRefractionIn, request: Request, user: dict = Depends(get_current_user)):
    exam = await load_exam(exam_id, user)
    _assert_open(exam)
    od, os_ = _clean_eye(data.od), _clean_eye(data.os)
    errs = eye_errors("OD", od, require_axis=False) + eye_errors("OS", os_, require_axis=False)
    if errs:
        raise HTTPException(status_code=400, detail=" · ".join(errs))
    values = {"od": od, "os": os_, "working_distance": (data.working_distance or "").strip(),
              "cyl_convention": data.cyl_convention if data.cyl_convention in ("negativo", "positivo") else "negativo",
              "observations": (data.observations or "").strip(),
              "professional_name": (data.professional_name or "").strip() or user.get("name", "")}
    current = exam.get("final_refraction") or {}
    update = {}
    if current.get("status") == "validada":
        if _fr_values(current) == values:
            return {"ok": True, "unchanged": True, "final_refraction": current}
        fr = {**values, "version": int(current.get("version") or 1) + 1, "status": "borrador"}
        update["$push"] = {"final_refraction_history": current}
        await _audit(user, "FINAL_REFRACTION_REVISED", exam_id, request, version=fr["version"])
    else:
        fr = {**values, "version": int(current.get("version") or 1), "status": "borrador"}
    fr.update({"source": (data.source or "manual")[:30], "updated_at": now_iso(), "updated_by": user["_id"]})
    update["$set"] = {"final_refraction": fr, "updated_at": now_iso()}
    await db.optical_consultations.update_one({"_id": exam["_id"]}, update)
    return {"ok": True, "final_refraction": fr}


@router.post("/{exam_id}/final-refraction/validate")
async def validate_final_refraction(exam_id: str, request: Request, user: dict = Depends(get_current_user)):
    exam = await load_exam(exam_id, user)
    require_clinical(user, exam)
    _assert_open(exam)
    fr = exam.get("final_refraction") or {}
    if not fr:
        raise HTTPException(status_code=400, detail="Registra la refraccion final antes de validarla")
    if fr.get("status") == "validada":
        return {"ok": True, "final_refraction": fr}
    od, os_ = fr.get("od") or {}, fr.get("os") or {}
    errs = eye_errors("OD", od) + eye_errors("OS", os_)
    if not (has_value(od.get("sphere")) or has_value(os_.get("sphere"))):
        errs.append("Indica la esfera de al menos un ojo (usa 'plano' para 0.00)")
    if errs:
        raise HTTPException(status_code=400, detail=" · ".join(errs))
    fr.update({"status": "validada", "validated_at": now_iso(), "validated_by": user["_id"],
               "validated_by_name": user.get("name", "")})
    await db.optical_consultations.update_one({"_id": exam["_id"]}, {"$set": {"final_refraction": fr}})
    await _audit(user, "FINAL_REFRACTION_VALIDATED", exam_id, request, version=fr.get("version"))
    return {"ok": True, "final_refraction": fr}


@router.post("/{exam_id}/final-refraction/discard-revision")
async def discard_revision(exam_id: str, request: Request, user: dict = Depends(get_current_user)):
    exam = await load_exam(exam_id, user)
    _assert_open(exam)
    fr = exam.get("final_refraction") or {}
    history = exam.get("final_refraction_history") or []
    if fr.get("status") != "borrador" or not history:
        raise HTTPException(status_code=400, detail="No hay una revision en curso para descartar")
    previous = history[-1]
    await db.optical_consultations.update_one(
        {"_id": exam["_id"]}, {"$set": {"final_refraction": previous}, "$pop": {"final_refraction_history": 1}})
    await _audit(user, "FINAL_REFRACTION_REVISION_DISCARDED", exam_id, request, version=fr.get("version"))
    return {"ok": True, "final_refraction": previous}


@router.post("/{exam_id}/sign")
async def sign_exam(exam_id: str, request: Request, user: dict = Depends(get_current_user)):
    exam = await load_exam(exam_id, user)
    require_clinical(user, exam)
    if exam.get("exam_status") == "firmado":
        return {"ok": True, "exam_status": "firmado"}
    if not (exam.get("chief_complaint") or "").strip():
        raise HTTPException(status_code=400, detail="Registra el motivo de consulta antes de firmar")
    fr = exam.get("final_refraction") or {}
    if fr and fr.get("status") != "validada":
        raise HTTPException(status_code=400, detail="Valida o descarta la refraccion final pendiente antes de firmar el examen")
    ts = now_iso()
    await db.optical_consultations.update_one({"_id": exam["_id"]}, {"$set": {
        "exam_status": "firmado", "signed_at": ts, "signed_by": user["_id"], "signed_by_name": user.get("name", "")}})
    await _audit(user, "EXAM_SIGNED", exam_id, request)
    return {"ok": True, "exam_status": "firmado", "signed_at": ts}


@router.post("/{exam_id}/reopen")
async def reopen_exam(exam_id: str, data: ReasonIn, request: Request, user: dict = Depends(get_current_user)):
    exam = await load_exam(exam_id, user)
    require_clinical(user, exam)
    reason = (data.reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="Indica el motivo de la reapertura (min. 5 caracteres)")
    if exam.get("exam_status") != "firmado":
        return {"ok": True, "exam_status": exam.get("exam_status") or "en_curso"}
    entry = {"signed_at": exam.get("signed_at"), "signed_by_name": exam.get("signed_by_name"),
             "reopened_at": now_iso(), "reopened_by_name": user.get("name", ""), "reason": reason[:300]}
    await db.optical_consultations.update_one({"_id": exam["_id"]}, {
        "$set": {"exam_status": "en_curso"}, "$unset": {"signed_at": "", "signed_by": "", "signed_by_name": ""},
        "$push": {"sign_history": entry}})
    await _audit(user, "EXAM_REOPENED", exam_id, request)
    return {"ok": True, "exam_status": "en_curso"}


@router.post("/{exam_id}/attachments")
async def upload_attachment(exam_id: str, request: Request, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    exam = await load_exam(exam_id, user)
    _assert_open(exam)
    active = [a for a in (exam.get("attachments") or []) if not a.get("deleted")]
    if len(active) >= ATT_MAX_COUNT:
        raise HTTPException(status_code=400, detail=f"Maximo {ATT_MAX_COUNT} archivos por examen")
    name = file.filename or "archivo"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ATT_EXTS:
        raise HTTPException(status_code=400, detail="Formatos permitidos: PDF, PNG, JPG, WEBP")
    content = await file.read()
    if len(content) > ATT_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande (max 10MB)")
    if not objstore.is_enabled():
        raise HTTPException(status_code=503, detail="Almacenamiento no disponible")
    att_id = uuid.uuid4().hex
    path = f"cortexia-optical/exams/{user['company_id']}/{exam_id}/{att_id}.{ext}"
    try:
        objstore.put_object(path, content, objstore.content_type_for(ext))
    except Exception as e:
        raise HTTPException(status_code=502, detail="No se pudo subir el archivo") from e
    att = {"id": att_id, "filename": name[:120], "storage_path": path, "content_type": objstore.content_type_for(ext),
           "size": len(content), "uploaded_at": now_iso(), "uploaded_by_name": user.get("name", "")}
    await db.optical_consultations.update_one({"_id": exam["_id"]}, {"$push": {"attachments": att}})
    await _audit(user, "EXAM_ATTACHMENT_ADDED", exam_id, request)
    return {k: v for k, v in att.items() if k != "storage_path"}


@router.get("/{exam_id}/attachments/{att_id}")
async def get_attachment(exam_id: str, att_id: str, user: dict = Depends(get_current_user)):
    exam = await load_exam(exam_id, user, {"company_id": 1, "attachments": 1})
    att = next((a for a in (exam.get("attachments") or []) if a.get("id") == att_id and not a.get("deleted")), None)
    if not att:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    try:
        data, ct = objstore.get_object(att["storage_path"])
    except Exception as e:
        raise HTTPException(status_code=502, detail="No se pudo descargar el archivo") from e
    return Response(content=data, media_type=ct or att.get("content_type"),
                    headers={"Content-Disposition": f'inline; filename="{att_id}"'})


@router.delete("/{exam_id}/attachments/{att_id}")
async def delete_attachment(exam_id: str, att_id: str, request: Request, user: dict = Depends(get_current_user)):
    exam = await load_exam(exam_id, user)
    _assert_open(exam)
    res = await db.optical_consultations.update_one(
        {"_id": exam["_id"], "attachments.id": att_id},
        {"$set": {"attachments.$.deleted": True, "attachments.$.deleted_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    await _audit(user, "EXAM_ATTACHMENT_REMOVED", exam_id, request)
    return {"ok": True}
