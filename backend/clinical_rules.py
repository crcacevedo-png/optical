"""Reglas clinicas compartidas: parseo de valores opticos, validaciones OD/OS,
codigos de examen/receta, permisos clinicos e instantaneas de emision.
OD = ojo derecho, OS = ojo izquierdo. En las colecciones historicas de recetas
el ojo izquierdo se guarda con prefijo `oi_` (se muestra siempre como OS)."""
from datetime import datetime, timezone
from bson import ObjectId
from pymongo import ReturnDocument
from fastapi import HTTPException

from db import db

PLANO_WORDS = {"pl", "plano", "neutro", "n", "esf", "sph"}
SECTION_STATUSES = {"", "realizado", "con_hallazgos", "sin_hallazgos", "no_realizado", "no_indicado"}
RX_STATUSES = {"borrador", "emitida", "sustituida", "anulada"}
RX_KINDS = ("eyeglass", "contact", "scleral")
PRISM_BASES = {"", "BN", "BT", "BS", "BI"}

EVALUATION_KEYS = {
    "symptoms", "general_history", "habitual_correction", "visual_needs",
    "biomicroscopy", "iop", "fundus", "binocular", "accommodative", "studies",
    "lensometry_notes", "va_distance", "va_conditions",
    "objective_refraction", "subjective_refraction", "cycloplegic_refraction",
    "diagnoses", "interpretation", "referral", "next_control",
}

# Campos por tipo de receta (prefijo od_/oi_ por ojo en colecciones existentes).
EYE_FIELDS = {
    "eyeglass": ["sphere", "cylinder", "axis", "addition", "prism_h", "base_h", "prism_v", "base_v", "dp", "height"],
    "contact": ["power", "cylinder", "axis", "addition", "bc", "dia", "extra"],
    "scleral": ["power", "cylinder", "axis", "addition", "dia", "sag", "ref_dia", "limbal_zone",
                "haptic_sup", "haptic_inf", "haptic_nas", "haptic_tem", "extra"],
}
NUMERIC_EYE = {"sphere", "cylinder", "addition", "power", "prism_h", "prism_v", "dp", "height", "bc", "dia", "sag", "ref_dia"}
AXIS_EYE = {"axis"}
COMMON_FIELDS = ["name", "usage", "indications", "control", "valid_until", "observations"]
KIND_FIELDS = {
    "eyeglass": ["rx_mode", "working_distance", "lens_type", "frame_type", "cyl_convention"],
    "contact": ["manufacturer", "brand", "model", "material", "design", "modality", "replacement",
                "care_system", "lens_type"],
    "scleral": ["lab", "design", "lab_code", "material", "thickness", "surface_treatment",
                "special_mods", "manufacturer_params", "sag_unit", "usage_instructions",
                "filling_solution", "cleaning"],
}
KIND_LABEL = {"eyeglass": "Anteojos", "contact": "Lentes de contacto", "scleral": "Lentes esclerales"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def oid(value, label="ID"):
    try:
        return ObjectId(str(value))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"{label} invalido") from exc


def parse_power(value):
    """(ok, float|None). Vacio = no registrado (None); 'plano' = 0.0 explicito."""
    if value is None:
        return True, None
    s = str(value).strip().lower().replace(",", ".").replace(" ", "")
    if s == "":
        return True, None
    if s in PLANO_WORDS:
        return True, 0.0
    try:
        return True, float(s)
    except ValueError:
        return False, None


def parse_axis(value):
    if value is None or str(value).strip() == "":
        return True, None
    s = str(value).strip().replace("°", "")
    try:
        n = int(float(s))
    except ValueError:
        return False, None
    if n < 0 or n > 180 or float(s) != n:
        return False, None
    return True, n


def eye_errors(label: str, eye: dict, sphere_key="sphere", require_axis=True) -> list:
    """Errores de formato y coherencia para un ojo. Sin limites de rango arbitrarios."""
    errs = []
    for k in (sphere_key, "cylinder", "cyl", "addition", "add", "prism_h", "prism_v", "power"):
        if k in eye:
            ok, _ = parse_power(eye.get(k))
            if not ok:
                errs.append(f"{label}: valor no numerico en {k}")
    ok_ax, axis = parse_axis(eye.get("axis"))
    if not ok_ax:
        errs.append(f"{label}: el eje debe ser un entero entre 0 y 180")
    cyl_raw = eye.get("cylinder", eye.get("cyl"))
    _, cyl = parse_power(cyl_raw)
    if require_axis and cyl not in (None, 0.0) and axis is None and ok_ax:
        errs.append(f"{label}: el eje es obligatorio cuando el cilindro no es cero")
    for p, b in (("prism_h", "base_h"), ("prism_v", "base_v")):
        _, pv = parse_power(eye.get(p))
        base = (eye.get(b) or "").strip().upper()
        if base and base not in PRISM_BASES:
            errs.append(f"{label}: base de prisma invalida")
        if pv not in (None, 0.0) and not base:
            errs.append(f"{label}: indica la base del prisma")
    return errs


def has_value(v) -> bool:
    return v is not None and str(v).strip() != ""


async def next_code(company_id, prefix: str) -> str:
    year = datetime.now(timezone.utc).year
    doc = await db.clinical_counters.find_one_and_update(
        {"company_id": ObjectId(str(company_id)), "prefix": prefix, "year": year},
        {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER,
    )
    return f"{prefix}-{year}-{doc['seq']:05d}"


def short_code(prefix: str, doc_id) -> str:
    return f"{prefix}-{str(doc_id)[-6:].upper()}"


async def _role_perms(user) -> list:
    from routes.settings import get_role_permissions
    perms = await get_role_permissions(ObjectId(user["company_id"]), user["role"])
    return perms or []


def is_exam_professional(user, exam) -> bool:
    return bool(exam) and str(exam.get("professional_user_id")) == str(user["_id"])


def require_tenant(user):
    if user["role"] == "superadmin" or not user.get("company_id"):
        raise HTTPException(status_code=403, detail="Acceso denegado")


def require_clinical(user, exam=None):
    """Actos clinicos (validar refraccion, firmar examen, aceptar adaptacion)."""
    require_tenant(user)
    if user["role"] in ("admin", "doctor") or is_exam_professional(user, exam):
        return
    raise HTTPException(status_code=403, detail="Solo el profesional responsable o un perfil clinico puede realizar esta accion")


async def require_issue(user, exam=None):
    """Emitir/anular recetas: perfiles clinicos o con permiso de emision de recetas."""
    require_tenant(user)
    if user["role"] in ("admin", "doctor") or is_exam_professional(user, exam):
        return
    if "prescriptions" in await _role_perms(user):
        return
    raise HTTPException(status_code=403, detail="No tienes permiso para emitir o anular recetas")


async def load_exam(exam_id, user, projection=None):
    require_tenant(user)
    e = await db.optical_consultations.find_one({"_id": oid(exam_id, "Examen")}, projection)
    if not e or str(e.get("company_id")) != str(user["company_id"]):
        raise HTTPException(status_code=404, detail="Examen no encontrado")
    return e


async def load_patient(patient_id, user):
    p = await db.patients.find_one({"_id": oid(patient_id, "Paciente")})
    if not p or str(p.get("company_id")) != str(user["company_id"]):
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return p


def sanitize_evaluation(ev) -> dict:
    if not isinstance(ev, dict):
        return {}
    clean = {k: v for k, v in ev.items() if k in EVALUATION_KEYS}
    if len(str(clean)) > 60000:
        raise HTTPException(status_code=400, detail="La evaluacion es demasiado extensa")
    return clean
