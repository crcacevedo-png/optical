from dotenv import load_dotenv
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, date
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

UPLOADS_DIR = ROOT_DIR / "uploads" / "logos"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

mongo_url = os.environ['MONGO_URL']

# Pool tuneado para produccion multi-pod (soporta ~1000 usuarios concurrentes).
# Env overrides opcionales para ajustar sin redeploy de codigo.
_max_pool = int(os.environ.get('MONGO_MAX_POOL_SIZE', '200'))
_min_pool = int(os.environ.get('MONGO_MIN_POOL_SIZE', '20'))
_max_idle_ms = int(os.environ.get('MONGO_MAX_IDLE_MS', '60000'))
_srv_sel_ms = int(os.environ.get('MONGO_SERVER_SELECTION_MS', '5000'))
_wait_queue_ms = int(os.environ.get('MONGO_WAIT_QUEUE_MS', '3000'))

client = AsyncIOMotorClient(
    mongo_url,
    maxPoolSize=_max_pool,
    minPoolSize=_min_pool,
    maxIdleTimeMS=_max_idle_ms,
    serverSelectionTimeoutMS=_srv_sel_ms,
    waitQueueTimeoutMS=_wait_queue_ms,
    retryWrites=True,
)
db = client[os.environ['DB_NAME']]

def serialize_doc(doc):
    """Convert all ObjectId fields in a MongoDB document to strings.
    Also handles top-level lists of ObjectIds (e.g. jornada_ids)."""
    if doc is None:
        return None
    for key, value in list(doc.items()):
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, list) and value and any(isinstance(x, ObjectId) for x in value):
            doc[key] = [str(x) if isinstance(x, ObjectId) else x for x in value]
    return doc

def calculate_age(birth_date_str: str) -> int:
    if not birth_date_str:
        return None
    try:
        birth = datetime.strptime(birth_date_str[:10], "%Y-%m-%d").date()
        today = date.today()
        return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    except (ValueError, TypeError):
        return None


def effective_max_patients(company, plan) -> int:
    """Límite efectivo de pacientes: usa el override de la óptica si está fijado
    (>0); de lo contrario, el max_patients del plan. Devuelve 0 si no hay límite."""
    if company:
        ov = company.get("patient_limit_override")
        if isinstance(ov, int) and ov > 0:
            return ov
    if plan:
        return int(plan.get("max_patients", 0) or 0)
    return 0


def effective_monthly_cost(company, plan) -> float:
    """Costo mensual efectivo: Q0 si la óptica es cuenta de cortesía; de lo
    contrario, el precio mensual del plan (price_monthly o price)."""
    if company and company.get("is_courtesy"):
        return 0.0
    if plan:
        return float(plan.get("price_monthly") or plan.get("price", 0) or 0)
    return 0.0


def is_billing_exempt(company) -> bool:
    """True si la óptica está exenta de reglas de inactivación por facturación/pago.
    Las cuentas de cortesía (is_courtesy) nunca se desactivan automáticamente por
    falta de pago (ni por expiración de activación)."""
    return bool(company and company.get("is_courtesy"))
