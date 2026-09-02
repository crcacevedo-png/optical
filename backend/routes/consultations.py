from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user
from models import ConsultationCreate, ConsultationUpdate

router = APIRouter(prefix="/consultations", tags=["Consultas"])

@router.get("")
async def list_consultations(
    user: dict = Depends(get_current_user),
    patient_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if patient_id:
        query["patient_id"] = ObjectId(patient_id)
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    if date_from and date_to:
        query["consultation_date"] = {"$gte": date_from, "$lte": date_to}
    elif date_from:
        query["consultation_date"] = {"$gte": date_from}
    
    consultations = await db.optical_consultations.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    for c in consultations:
        serialize_doc(c)
        if c.get("patient_id"):
            patient = await db.patients.find_one({"_id": ObjectId(c["patient_id"])}, {"first_name": 1, "last_name": 1})
            if patient:
                c["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
        if c.get("professional_user_id"):
            prof = await db.users.find_one({"_id": ObjectId(c["professional_user_id"])}, {"name": 1})
            if prof:
                c["professional_name"] = prof["name"]
    return [serialize_doc(c) for c in consultations]

@router.post("")
async def create_consultation(data: ConsultationCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    branch_id = ObjectId(user["branch_id"]) if user.get("branch_id") else None
    now = datetime.now(timezone.utc)
    
    doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": branch_id,
        "patient_id": ObjectId(data.patient_id),
        "appointment_id": ObjectId(data.appointment_id) if data.appointment_id else None,
        "professional_user_id": ObjectId(user["_id"]),
        "consultation_date": data.consultation_date,
        "consultation_time": data.consultation_time or now.strftime("%H:%M"),
        "consultation_type": data.consultation_type,
        "chief_complaint": data.chief_complaint,
        "anamnesis": data.anamnesis or "",
        "findings": data.findings or "",
        "diagnosis": data.diagnosis or "",
        "treatment_plan": data.treatment_plan or "",
        "recommendations": data.recommendations or "",
        "notes": data.notes or "",
        "wears_glasses": data.wears_glasses,
        "glasses_since": data.glasses_since or "",
        "glasses_type": data.glasses_type or "",
        "ocular_surgeries": data.ocular_surgeries or "",
        "ocular_trauma": data.ocular_trauma or "",
        "ocular_diseases": data.ocular_diseases or "",
        "diabetes": data.diabetes,
        "hypertension": data.hypertension,
        "autoimmune_disease": data.autoimmune_disease,
        "autoimmune_details": data.autoimmune_details or "",
        "current_medications": data.current_medications or "",
        "allergies": data.allergies or "",
        "family_glaucoma": data.family_glaucoma,
        "family_glaucoma_relationship": data.family_glaucoma_relationship or "",
        "family_macular_degeneration": data.family_macular_degeneration,
        "family_macular_relationship": data.family_macular_relationship or "",
        "family_high_myopia": data.family_high_myopia,
        "family_high_myopia_relationship": data.family_high_myopia_relationship or "",
        "family_other_history": data.family_other_history or "",
        "va_distance_without_rx_od": data.va_distance_without_rx_od or "",
        "va_distance_without_rx_oi": data.va_distance_without_rx_oi or "",
        "va_distance_with_rx_od": data.va_distance_with_rx_od or "",
        "va_distance_with_rx_oi": data.va_distance_with_rx_oi or "",
        "va_near_without_rx_od": data.va_near_without_rx_od or "",
        "va_near_without_rx_oi": data.va_near_without_rx_oi or "",
        "va_near_with_rx_od": data.va_near_with_rx_od or "",
        "va_near_with_rx_oi": data.va_near_with_rx_oi or "",
        "va_pinhole_od": data.va_pinhole_od or "",
        "va_pinhole_oi": data.va_pinhole_oi or "",
        "visual_acuity_method": data.visual_acuity_method or "",
        "refractions": [r.model_dump() for r in (data.refractions or [])],
        "created_by": ObjectId(user["_id"]),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    }
    result = await db.optical_consultations.insert_one(doc)
    return {"_id": str(result.inserted_id), "message": "Consulta registrada"}

@router.get("/{consultation_id}")
async def get_consultation(consultation_id: str, user: dict = Depends(get_current_user)):
    c = await db.optical_consultations.find_one({"_id": ObjectId(consultation_id)})
    if not c or str(c["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")
    serialize_doc(c)
    
    if c.get("patient_id"):
        patient = await db.patients.find_one({"_id": ObjectId(c["patient_id"])}, {"first_name": 1, "last_name": 1, "phone": 1, "birth_date": 1, "gender": 1})
        if patient:
            c["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
            c["patient_phone"] = patient.get("phone", "")
            c["patient_birth_date"] = patient.get("birth_date", "")
            c["patient_gender"] = patient.get("gender", "")
    
    if c.get("professional_user_id"):
        prof = await db.users.find_one({"_id": ObjectId(c["professional_user_id"])}, {"name": 1, "email": 1})
        if prof:
            c["professional_name"] = prof["name"]
    
    eyeglass_rx = await db.eyeglass_prescriptions.find({"consultation_id": ObjectId(consultation_id)}).sort("created_at", -1).to_list(10)
    for rx in eyeglass_rx:
        serialize_doc(rx)
    c["eyeglass_prescriptions"] = eyeglass_rx
    
    contact_rx = await db.contact_lens_prescriptions.find({"consultation_id": ObjectId(consultation_id)}).sort("created_at", -1).to_list(10)
    for rx in contact_rx:
        serialize_doc(rx)
    c["contact_prescriptions"] = contact_rx
    
    medical_rx = await db.medical_prescriptions.find({"consultation_id": ObjectId(consultation_id)}).sort("created_at", -1).to_list(10)
    for rx in medical_rx:
        serialize_doc(rx)
    c["medical_prescriptions"] = medical_rx
    
    return serialize_doc(c)

@router.put("/{consultation_id}")
async def update_consultation(consultation_id: str, data: ConsultationUpdate, user: dict = Depends(get_current_user)):
    c = await db.optical_consultations.find_one({"_id": ObjectId(consultation_id)})
    if not c or str(c["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")
    
    update_data = {}
    all_fields = [
        "consultation_type", "chief_complaint", "anamnesis", "findings", "diagnosis",
        "treatment_plan", "recommendations", "notes",
        "wears_glasses", "glasses_since", "glasses_type", "ocular_surgeries", "ocular_trauma", "ocular_diseases",
        "diabetes", "hypertension", "autoimmune_disease", "autoimmune_details", "current_medications", "allergies",
        "family_glaucoma", "family_glaucoma_relationship", "family_macular_degeneration", "family_macular_relationship",
        "family_high_myopia", "family_high_myopia_relationship", "family_other_history",
        "va_distance_without_rx_od", "va_distance_without_rx_oi", "va_distance_with_rx_od", "va_distance_with_rx_oi",
        "va_near_without_rx_od", "va_near_without_rx_oi", "va_near_with_rx_od", "va_near_with_rx_oi",
        "va_pinhole_od", "va_pinhole_oi", "visual_acuity_method"
    ]
    for field in all_fields:
        val = getattr(data, field, None)
        if val is not None:
            update_data[field] = val
    
    if data.refractions is not None:
        update_data["refractions"] = [r.model_dump() for r in data.refractions]
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.optical_consultations.update_one({"_id": ObjectId(consultation_id)}, {"$set": update_data})
    return {"message": "Consulta actualizada"}
