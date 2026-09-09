"""Onboarding progress tracking por usuario."""
from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from pydantic import BaseModel

from db import db
from auth_utils import get_current_user

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])

# SEC hardening (Feb 2026): allowlist explicita de step_ids validos.
# Sin esto, un cliente podria inyectar keys arbitrarias en el sub-documento
# `onboarding_progress` via el $set con clave construida a partir de input.
ALLOWED_STEP_IDS = {
    "download_guide",
    "company_data",
    "branches",
    "users",
    "inventory",
    "first_patient",
    "first_sale",
    "change_password",
}


class OnboardingUpdate(BaseModel):
    step_id: str
    completed: bool


@router.get("/status")
async def get_onboarding_status(user: dict = Depends(get_current_user)):
    """Retorna el progreso de onboarding del usuario actual."""
    db_user = await db.users.find_one(
        {"_id": ObjectId(user["_id"])},
        {"onboarding_progress": 1, "onboarding_dismissed": 1}
    )
    progress = (db_user or {}).get("onboarding_progress", {}) or {}
    dismissed = (db_user or {}).get("onboarding_dismissed", False)
    return {"progress": progress, "dismissed": dismissed}


@router.put("/status")
async def update_onboarding_step(data: OnboardingUpdate, user: dict = Depends(get_current_user)):
    """Marca un paso del onboarding como completado/pendiente."""
    if data.step_id not in ALLOWED_STEP_IDS:
        raise HTTPException(status_code=400, detail="step_id invalido")
    await db.users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {f"onboarding_progress.{data.step_id}": data.completed}}
    )
    return {"message": "Progreso actualizado"}


@router.post("/dismiss")
async def dismiss_onboarding(user: dict = Depends(get_current_user)):
    """Marca el onboarding como cerrado (oculta el banner del dashboard)."""
    await db.users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {"onboarding_dismissed": True}}
    )
    return {"message": "Onboarding cerrado"}
