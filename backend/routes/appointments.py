from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user
from models import AppointmentCreate, AppointmentUpdate

router = APIRouter(prefix="/appointments", tags=["Agenda"])

@router.get("")
async def list_appointments(
    user: dict = Depends(get_current_user),
    date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    branch_id: Optional[str] = None,
    view: Optional[str] = "day"
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin no puede ver citas")
    
    query = {"company_id": ObjectId(user["company_id"])}
    
    if date:
        query["date"] = date
    elif date_from and date_to:
        query["date"] = {"$gte": date_from, "$lte": date_to}
    
    if status:
        query["status"] = status
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    appointments = await db.appointments.find(query).sort([("date", 1), ("time", 1)]).to_list(500)
    for apt in appointments:
        serialize_doc(apt)
    patient_ids = list({ObjectId(a["patient_id"]) for a in appointments if a.get("patient_id")})
    if patient_ids:
        patients = await db.patients.find({"_id": {"$in": patient_ids}}, {"first_name": 1, "last_name": 1, "phone": 1}).to_list(len(patient_ids))
        patient_map = {str(p["_id"]): p for p in patients}
        for apt in appointments:
            p = patient_map.get(apt.get("patient_id"))
            if p:
                apt["patient_name"] = f"{p['first_name']} {p['last_name']}"
                apt["patient_phone"] = p.get("phone", "")
    
    return appointments

@router.post("")
async def create_appointment(data: AppointmentCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="SuperAdmin no puede crear citas")
    
    apt_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(data.branch_id) if data.branch_id else (ObjectId(user["branch_id"]) if user.get("branch_id") else None),
        "patient_id": ObjectId(data.patient_id),
        "professional_id": ObjectId(data.professional_id) if data.professional_id else None,
        "professional_name": data.professional_name,
        "date": data.date, "time": data.time, "duration": data.duration, "type": data.type,
        "status": data.status or "pendiente", "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    result = await db.appointments.insert_one(apt_doc)
    return {"_id": str(result.inserted_id), "message": "Cita creada"}

@router.get("/{appointment_id}")
async def get_appointment(appointment_id: str, user: dict = Depends(get_current_user)):
    apt = await db.appointments.find_one({"_id": ObjectId(appointment_id)})
    if not apt or str(apt["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    serialize_doc(apt)
    patient = await db.patients.find_one({"_id": ObjectId(apt["patient_id"])}, {"first_name": 1, "last_name": 1})
    if patient:
        apt["patient_name"] = f"{patient['first_name']} {patient['last_name']}"
    return apt

@router.put("/{appointment_id}")
async def update_appointment(appointment_id: str, data: AppointmentUpdate, user: dict = Depends(get_current_user)):
    apt = await db.appointments.find_one({"_id": ObjectId(appointment_id)})
    if not apt or str(apt["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.appointments.update_one({"_id": ObjectId(appointment_id)}, {"$set": update_data})
    return {"message": "Cita actualizada"}

@router.delete("/{appointment_id}")
async def cancel_appointment(appointment_id: str, user: dict = Depends(get_current_user)):
    apt = await db.appointments.find_one({"_id": ObjectId(appointment_id)})
    if not apt or str(apt["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    await db.appointments.update_one({"_id": ObjectId(appointment_id)}, {"$set": {"status": "cancelada"}})
    return {"message": "Cita cancelada"}
