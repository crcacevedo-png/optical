from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc, calculate_age
from auth_utils import get_current_user
from models import PatientCreate, PatientUpdate
from routes.notifications import create_notification

router = APIRouter(prefix="/patients", tags=["Pacientes"])


async def _check_patient_limit(company_id: str):
    """Check plan patient limit. Raises 403 if limit reached. Returns (company, plan) or (None, None)."""
    company = await db.companies.find_one({"_id": ObjectId(company_id)})
    if not company or not company.get("plan_id"):
        return company, None
    plan = await db.plans.find_one({"_id": company["plan_id"]})
    if not plan or plan.get("max_patients", 0) <= 0:
        return company, plan
    current_count = await db.patients.count_documents({"company_id": ObjectId(company_id), "is_deleted": {"$ne": True}})
    if current_count >= plan["max_patients"]:
        raise HTTPException(status_code=403, detail=f"Limite de pacientes alcanzado ({plan['max_patients']}). Actualice su plan para agregar mas.")
    return company, plan


async def _notify_patient_limit(company, plan, company_id: str):
    """Send notification if company is near or at patient limit."""
    if not company or not plan or plan.get("max_patients", 0) <= 0:
        return
    max_p = plan["max_patients"]
    new_count = await db.patients.count_documents({"company_id": ObjectId(company_id), "is_deleted": {"$ne": True}})
    pct = new_count / max_p
    cname = company.get("name", "Optica")
    if pct >= 1.0:
        if not await db.notifications.find_one({"event_type": "limit_reached", "metadata.company_id": company_id, "metadata.resource": "pacientes"}):
            await create_notification("limit_reached", "Limite de pacientes alcanzado",
                f"{cname} alcanzo el limite de {max_p} pacientes (plan {plan['name']})",
                {"company_id": company_id, "company_name": cname, "resource": "pacientes", "current": new_count, "max": max_p})
    elif pct >= 0.8:
        if not await db.notifications.find_one({"event_type": "limit_warning", "metadata.company_id": company_id, "metadata.resource": "pacientes"}):
            await create_notification("limit_warning", "Optica cerca del limite de pacientes",
                f"{cname} tiene {new_count}/{max_p} pacientes ({round(pct*100)}%) en plan {plan['name']}",
                {"company_id": company_id, "company_name": cname, "resource": "pacientes", "current": new_count, "max": max_p})

@router.get("")
async def list_patients(
    user: dict = Depends(get_current_user),
    search: Optional[str] = None,
    limit: int = Query(50, le=200),
    skip: int = 0
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin no puede ver pacientes")
    
    query = {"company_id": ObjectId(user["company_id"]), "is_deleted": {"$ne": True}}
    if search:
        query["$or"] = [
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
            {"whatsapp": {"$regex": search, "$options": "i"}},
            {"dpi": {"$regex": search, "$options": "i"}}
        ]
    
    total = await db.patients.count_documents(query)
    patients = await db.patients.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    for p in patients:
        serialize_doc(p)
        p["age"] = calculate_age(p.get("birth_date"))
    
    return {"patients": patients, "total": total, "limit": limit, "skip": skip}

@router.post("")
async def create_patient(data: PatientCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin no puede crear pacientes")
    
    company, plan = await _check_patient_limit(user["company_id"])
    
    patient_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(data.branch_id) if data.branch_id else (ObjectId(user["branch_id"]) if user.get("branch_id") else None),
        "first_name": data.first_name, "last_name": data.last_name, "dpi": data.dpi,
        "birth_date": data.birth_date, "gender": data.gender, "phone": data.phone,
        "whatsapp": data.whatsapp or data.phone, "email": data.email.lower() if data.email else None,
        "address": data.address, "city": data.city, "country": data.country,
        "emergency_contact": data.emergency_contact, "emergency_phone": data.emergency_phone,
        "notes": data.notes, "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    result = await db.patients.insert_one(patient_doc)
    
    await _notify_patient_limit(company, plan, user["company_id"])
    
    return {"_id": str(result.inserted_id), "message": "Paciente creado"}

@router.get("/{patient_id}")
async def get_patient(patient_id: str, user: dict = Depends(get_current_user)):
    patient = await db.patients.find_one({"_id": ObjectId(patient_id)})
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    if user["role"] != "superadmin" and str(patient["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    serialize_doc(patient)
    patient["age"] = calculate_age(patient.get("birth_date"))
    
    eyeglass_rx = await db.eyeglass_prescriptions.find({"patient_id": ObjectId(patient_id)}).sort("created_at", -1).to_list(20)
    for rx in eyeglass_rx:
        serialize_doc(rx)
    patient["eyeglass_prescriptions"] = eyeglass_rx
    
    contact_rx = await db.contact_lens_prescriptions.find({"patient_id": ObjectId(patient_id)}).sort("created_at", -1).to_list(20)
    for rx in contact_rx:
        serialize_doc(rx)
    patient["contact_prescriptions"] = contact_rx
    
    medical_rx = await db.medical_prescriptions.find({"patient_id": ObjectId(patient_id)}).sort("created_at", -1).to_list(20)
    for rx in medical_rx:
        serialize_doc(rx)
    patient["medical_prescriptions"] = medical_rx
    
    appointments = await db.appointments.find({"patient_id": ObjectId(patient_id)}).sort("date", -1).to_list(30)
    for apt in appointments:
        serialize_doc(apt)
    patient["appointments"] = appointments
    
    sales = await db.sales.find({"patient_id": ObjectId(patient_id)}).sort("created_at", -1).to_list(30)
    for s in sales:
        serialize_doc(s)
    patient["sales"] = sales
    
    consultations = await db.optical_consultations.find({"patient_id": ObjectId(patient_id)}).sort("created_at", -1).to_list(50)
    for con in consultations:
        serialize_doc(con)
        if con.get("professional_user_id"):
            prof = await db.users.find_one({"_id": ObjectId(con["professional_user_id"])}, {"name": 1})
            if prof:
                con["professional_name"] = prof["name"]
    patient["consultations"] = consultations
    
    return patient

@router.put("/{patient_id}")
async def update_patient(patient_id: str, data: PatientUpdate, user: dict = Depends(get_current_user)):
    patient = await db.patients.find_one({"_id": ObjectId(patient_id)})
    if not patient or str(patient["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if "email" in update_data and update_data["email"]:
        update_data["email"] = update_data["email"].lower()
    if "branch_id" in update_data and update_data["branch_id"]:
        update_data["branch_id"] = ObjectId(update_data["branch_id"])
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.patients.update_one({"_id": ObjectId(patient_id)}, {"$set": update_data})
    return {"message": "Paciente actualizado"}

@router.delete("/{patient_id}")
async def delete_patient(patient_id: str, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar pacientes")
    patient = await db.patients.find_one({"_id": ObjectId(patient_id)})
    if not patient or str(patient["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    await db.patients.update_one({"_id": ObjectId(patient_id)}, {"$set": {"is_deleted": True}})
    return {"message": "Paciente eliminado"}
