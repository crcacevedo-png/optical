"""Adaptaciones de lentes de contacto y esclerales (registro clinico, separado de
la receta). Multiples pruebas por ojo y por consulta. La receta de contacto o
escleral solo se emite desde una adaptacion con estado 'aceptada'.
No se aprueba ningun lente por umbrales ni se calcula potencia automaticamente."""
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from db import db, serialize_doc
from auth_utils import get_current_user
from audit import log_audit
from clinical_rules import now_iso, oid, require_tenant, require_clinical, load_patient, load_exam, has_value

router = APIRouter(prefix="/clinical/adaptations", tags=["Adaptaciones"])

KINDS = ("contacto", "escleral")
TEXT_KEYS = ("title", "care_habits", "keratometry_od", "keratometry_os", "surface_notes",
             "decision", "follow_up", "params_requested", "params_received")
PARAM_KEYS = ("brand", "design", "material", "power", "cylinder", "axis", "addition", "bc", "dia",
              "sag", "sag_unit", "ref_dia", "limbal_zone", "haptic_sup", "haptic_inf", "haptic_nas", "haptic_tem", "extra")


class AdaptationIn(BaseModel):
    patient_id: Optional[str] = None
    consultation_id: Optional[str] = None
    kind: Optional[str] = None
    title: Optional[str] = None
    care_habits: Optional[str] = None
    keratometry_od: Optional[str] = None
    keratometry_os: Optional[str] = None
    surface_notes: Optional[str] = None
    trials: Optional[List[dict]] = None
    decision: Optional[str] = None
    follow_up: Optional[str] = None
    params_requested: Optional[str] = None
    params_received: Optional[str] = None
    accepted_params: Optional[dict] = None


class ReasonIn(BaseModel):
    reason: Optional[str] = ""


def _clean_text(v, n=2000):
    return (str(v) if v is not None else "").strip()[:n]


def _clean_trials(trials) -> list:
    out = []
    for t in (trials or [])[:60]:
        if not isinstance(t, dict):
            continue
        eye = t.get("eye") if t.get("eye") in ("od", "oi") else "od"
        item = {k: v for k, v in t.items() if isinstance(v, (str, int, float, bool, dict, type(None)))}
        item["eye"] = eye
        item["id"] = str(t.get("id") or uuid.uuid4().hex)
        out.append(item)
    if len(str(out)) > 80000:
        raise HTTPException(status_code=400, detail="Demasiada informacion en las pruebas")
    return out


def _clean_params(p) -> dict:
    p = p if isinstance(p, dict) else {}
    return {eye: {k: _clean_text((p.get(eye) or {}).get(k), 300) for k in PARAM_KEYS} for eye in ("od", "oi")}


def _audit(user, action, ad_id, request, **meta):
    return log_audit(action, actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
                     company_id=user["company_id"], target_id=str(ad_id), target_type="lens_adaptation",
                     metadata=meta, request=request)


async def _load(ad_id, user):
    require_tenant(user)
    ad = await db.lens_adaptations.find_one({"_id": oid(ad_id, "Adaptacion")})
    if not ad or str(ad.get("company_id")) != str(user["company_id"]):
        raise HTTPException(status_code=404, detail="Adaptacion no encontrada")
    return ad


@router.get("")
async def list_adaptations(patient_id: str, user: dict = Depends(get_current_user)):
    require_tenant(user)
    await load_patient(patient_id, user)
    rows = await db.lens_adaptations.find(
        {"company_id": oid(user["company_id"]), "patient_id": oid(patient_id)}).sort("created_at", -1).to_list(100)
    return [serialize_doc(r) for r in rows]


@router.post("")
async def create_adaptation(data: AdaptationIn, request: Request, user: dict = Depends(get_current_user)):
    require_tenant(user)
    if data.kind not in KINDS:
        raise HTTPException(status_code=400, detail="Tipo de adaptacion invalido (contacto o escleral)")
    patient = await load_patient(data.patient_id, user)
    cons_id = None
    if data.consultation_id:
        exam = await load_exam(data.consultation_id, user, {"company_id": 1, "patient_id": 1})
        if str(exam.get("patient_id")) != str(patient["_id"]):
            raise HTTPException(status_code=400, detail="El examen no corresponde al paciente")
        cons_id = exam["_id"]
    ts = now_iso()
    doc = {"company_id": oid(user["company_id"]), "patient_id": patient["_id"], "consultation_id": cons_id,
           "kind": data.kind, "status": "en_proceso",
           **{k: _clean_text(getattr(data, k)) for k in TEXT_KEYS},
           "trials": _clean_trials(data.trials), "accepted_params": _clean_params(data.accepted_params),
           "created_at": ts, "updated_at": ts, "created_by": user["_id"], "created_by_name": user.get("name", "")}
    if not doc["title"]:
        doc["title"] = "Adaptacion de lentes esclerales" if data.kind == "escleral" else "Adaptacion de lentes de contacto"
    res = await db.lens_adaptations.insert_one(doc)
    await _audit(user, "ADAPTATION_CREATED", res.inserted_id, request, kind=data.kind)
    doc["_id"] = res.inserted_id
    return serialize_doc(doc)


@router.put("/{ad_id}")
async def update_adaptation(ad_id: str, data: AdaptationIn, user: dict = Depends(get_current_user)):
    ad = await _load(ad_id, user)
    if ad.get("status") == "aceptada":
        raise HTTPException(status_code=409, detail="La adaptacion esta aceptada. Reabrela para modificarla.")
    upd = {k: _clean_text(getattr(data, k)) for k in TEXT_KEYS if getattr(data, k) is not None}
    if data.trials is not None:
        upd["trials"] = _clean_trials(data.trials)
    if data.accepted_params is not None:
        upd["accepted_params"] = _clean_params(data.accepted_params)
    upd["updated_at"] = now_iso()
    await db.lens_adaptations.update_one({"_id": ad["_id"]}, {"$set": upd})
    return serialize_doc(await db.lens_adaptations.find_one({"_id": ad["_id"]}))


@router.post("/{ad_id}/accept")
async def accept_adaptation(ad_id: str, request: Request, user: dict = Depends(get_current_user)):
    ad = await _load(ad_id, user)
    exam = await db.optical_consultations.find_one({"_id": ad.get("consultation_id")}, {"professional_user_id": 1}) if ad.get("consultation_id") else None
    require_clinical(user, exam)
    if ad.get("status") == "aceptada":
        return serialize_doc(ad)
    params = ad.get("accepted_params") or {}
    if not any(has_value((params.get(e) or {}).get("power")) for e in ("od", "oi")):
        raise HTTPException(status_code=400, detail="Registra los parametros aceptados (al menos la potencia de un ojo) antes de aceptar")
    if not (ad.get("decision") or "").strip():
        raise HTTPException(status_code=400, detail="Registra la decision clinica de la adaptacion")
    ts = now_iso()
    await db.lens_adaptations.update_one({"_id": ad["_id"]}, {"$set": {
        "status": "aceptada", "accepted_at": ts, "accepted_by": user["_id"], "accepted_by_name": user.get("name", "")}})
    await _audit(user, "ADAPTATION_ACCEPTED", ad["_id"], request, kind=ad.get("kind"))
    return serialize_doc(await db.lens_adaptations.find_one({"_id": ad["_id"]}))


@router.post("/{ad_id}/reopen")
async def reopen_adaptation(ad_id: str, data: ReasonIn, request: Request, user: dict = Depends(get_current_user)):
    ad = await _load(ad_id, user)
    exam = await db.optical_consultations.find_one({"_id": ad.get("consultation_id")}, {"professional_user_id": 1}) if ad.get("consultation_id") else None
    require_clinical(user, exam)
    reason = (data.reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="Indica el motivo de la reapertura (min. 5 caracteres)")
    await db.lens_adaptations.update_one({"_id": ad["_id"]}, {
        "$set": {"status": "en_proceso", "updated_at": now_iso()},
        "$push": {"reopen_history": {"at": now_iso(), "by": user.get("name", ""), "reason": reason[:300]}}})
    await _audit(user, "ADAPTATION_REOPENED", ad["_id"], request)
    return serialize_doc(await db.lens_adaptations.find_one({"_id": ad["_id"]}))
