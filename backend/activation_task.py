"""
Task periodico que gestiona la activacion de opticas nuevas:
- Envia recordatorio al admin cuando faltan 7 dias para el deadline (dia 23)
- Envia recordatorio urgente cuando faltan 2 dias (dia 28)
- Desactiva la optica y notifica al admin cuando pasan >= 30 dias sin activarse

Corre cada 12 horas via asyncio.create_task en startup.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from bson import ObjectId

from db import db
from email_service import (
    queue_email, render_activation_reminder, render_deactivation_notice,
    render_onboarding_tips,
)
from routes.notifications import create_notification
from audit import log_audit

logger = logging.getLogger(__name__)

# Config
DEADLINE_DAYS = int(os.environ.get("ACTIVATION_DEADLINE_DAYS", "30"))
WELCOME_TIPS_DAY = int(os.environ.get("WELCOME_TIPS_DAY", "3"))
REMINDER_STAGES = [
    # (min_days_since_created, max_days, tag, remaining, marker)
    (DEADLINE_DAYS - 7, DEADLINE_DAYS - 5, "reminder_7d", 7, "reminder_7d_sent_at"),
    (DEADLINE_DAYS - 2, DEADLINE_DAYS - 1, "reminder_2d", 2, "reminder_2d_sent_at"),
]
CHECK_INTERVAL_SECONDS = int(os.environ.get("ACTIVATION_CHECK_INTERVAL", str(12 * 3600)))  # 12h default


def _parse_iso(iso_str):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


async def _process_welcome_tips(now: datetime, app_url: str):
    """Envia email de bienvenida con tips el dia N (default 3) SOLO si el admin
    aun no ha ingresado (motivador). Marcado con welcome_tips_sent_at para idempotencia."""
    pipeline = [
        {"$match": {
            "role": "admin",
            "$or": [{"first_login_at": None}, {"first_login_at": {"$exists": False}}],
            "is_active": True,
            "welcome_tips_sent_at": {"$exists": False},
        }},
        {"$lookup": {
            "from": "companies",
            "localField": "company_id",
            "foreignField": "_id",
            "as": "company",
        }},
        {"$unwind": "$company"},
        {"$match": {"company.is_active": True}},
    ]
    async for admin in db.users.aggregate(pipeline):
        company = admin["company"]
        created_at = _parse_iso(company.get("created_at"))
        if not created_at:
            continue
        days_old = (now - created_at).days
        # Solo se envia si el admin lleva AL MENOS WELCOME_TIPS_DAY dias creado
        # y aun no ha ingresado. Sirve tambien para "atrasados" (dias 4, 5, 6...).
        if days_old < WELCOME_TIPS_DAY:
            continue
        # No enviar si ya cae en la ventana del recordatorio de 7 dias (evita spam)
        if days_old >= DEADLINE_DAYS - 7:
            continue
        try:
            html = render_onboarding_tips(
                admin_name=admin.get("name", "Administrador"),
                company_name=company.get("name", "tu optica"),
                login_link=app_url,
            )
            await queue_email(
                admin["email"],
                f"[Cortexia] 5 tips para empezar con {company.get('name', 'tu optica')}",
                html,
                tag="welcome_tips",
            )
            await db.users.update_one(
                {"_id": admin["_id"]},
                {"$set": {"welcome_tips_sent_at": now.isoformat()}}
            )
            logger.info(f"[activation] Enviado welcome_tips a {admin['email']} (company={company.get('name')}, dias={days_old})")
        except Exception as e:
            logger.warning(f"[activation] Error enviando welcome_tips a {admin.get('email')}: {e}")


async def _process_reminders(now: datetime, app_url: str):
    """Envia emails de recordatorio en dias 23 y 28 (para deadline=30)."""
    for min_d, max_d, tag, remaining, marker in REMINDER_STAGES:
        # Buscar admins cuya company se creo hace entre min_d y max_d dias,
        # que nunca han hecho login y a los que aun NO se les envio este recordatorio.
        pipeline = [
            {"$match": {
                "role": "admin",
                "$or": [{"first_login_at": None}, {"first_login_at": {"$exists": False}}],
                "is_active": True,
                marker: {"$exists": False},
            }},
            {"$lookup": {
                "from": "companies",
                "localField": "company_id",
                "foreignField": "_id",
                "as": "company",
            }},
            {"$unwind": "$company"},
            {"$match": {"company.is_active": True}},
        ]
        async for admin in db.users.aggregate(pipeline):
            company = admin["company"]
            created_at = _parse_iso(company.get("created_at"))
            if not created_at:
                continue
            days_old = (now - created_at).days
            if not (min_d <= days_old <= max_d):
                continue
            # Enviar recordatorio
            try:
                html = render_activation_reminder(
                    admin_name=admin.get("name", "Administrador"),
                    company_name=company.get("name", "tu optica"),
                    days_remaining=remaining,
                    login_link=app_url,
                )
                await queue_email(
                    admin["email"],
                    f"[Cortexia] Recordatorio: activa tu optica ({remaining} dia{'s' if remaining != 1 else ''} restante{'s' if remaining != 1 else ''})",
                    html,
                    tag=tag,
                )
                await db.users.update_one(
                    {"_id": admin["_id"]},
                    {"$set": {marker: now.isoformat()}}
                )
                logger.info(f"[activation] Enviado {tag} a {admin['email']} (company={company.get('name')}, dias={days_old})")
            except Exception as e:
                logger.warning(f"[activation] Error enviando {tag} a {admin.get('email')}: {e}")


async def _process_deactivations(now: datetime):
    """Desactiva opticas SOLO cuando el admin NUNCA ha ingresado por primera vez
    despues del deadline (30 dias).

    IMPORTANTE (regla de negocio Feb 2026):
    - Esta desactivacion aplica UNICAMENTE a ópticas con first_login_at == None.
    - Ópticas ya activadas (con first_login_at establecido) NO se desactivan
      por inactividad — se dejan activas y se muestran en el Panel Retencion
      como "En riesgo" para que el SuperAdmin las contacte manualmente.
    - Otras reglas de desactivacion (falta de pago Stripe, etc.) se
      definiran cuando el modulo de pagos este completamente operativo.

    EXENCION (Jun 2026): las CUENTAS DE CORTESIA (company.is_courtesy) quedan
    EXENTAS de toda desactivacion automatica (por expiracion de activacion y por
    cualquier futura regla de falta de pago). Son accesos regalados por el
    SuperAdmin y permanecen activos hasta que el SuperAdmin quite la cortesia.
    """
    pipeline = [
        {"$match": {
            "role": "admin",
            "$or": [{"first_login_at": None}, {"first_login_at": {"$exists": False}}],
            "is_active": True,
            "deactivated_by_activation_expiry_at": {"$exists": False},
        }},
        {"$lookup": {
            "from": "companies",
            "localField": "company_id",
            "foreignField": "_id",
            "as": "company",
        }},
        {"$unwind": "$company"},
        {"$match": {"company.is_active": True, "company.is_courtesy": {"$ne": True}}},
    ]
    async for admin in db.users.aggregate(pipeline):
        company = admin["company"]
        created_at = _parse_iso(company.get("created_at"))
        if not created_at:
            continue
        days_old = (now - created_at).days
        if days_old < DEADLINE_DAYS:
            continue
        # Desactivar optica + admin
        try:
            await db.companies.update_one(
                {"_id": company["_id"]},
                {"$set": {
                    "is_active": False,
                    "deactivated_reason": "activation_expired",
                    "deactivated_at": now.isoformat(),
                }}
            )
            await db.users.update_one(
                {"_id": admin["_id"]},
                {"$set": {
                    "is_active": False,
                    "deactivated_by_activation_expiry_at": now.isoformat(),
                }}
            )
            # Email al admin
            try:
                html = render_deactivation_notice(
                    admin_name=admin.get("name", "Administrador"),
                    company_name=company.get("name", "tu optica"),
                )
                await queue_email(
                    admin["email"],
                    "[Cortexia] Tu optica fue desactivada por inactividad",
                    html,
                    tag="deactivation_notice",
                )
            except Exception as e:
                logger.warning(f"[activation] Error enviando deactivation notice: {e}")
            # Notificacion al SuperAdmin
            try:
                await create_notification(
                    event_type="company_deactivated_expiry",
                    title="Optica desactivada por inactividad",
                    message=f"{company.get('name', 'Optica')} fue desactivada porque el admin ({admin['email']}) no ingreso en {DEADLINE_DAYS} dias.",
                    metadata={
                        "company_id": str(company["_id"]),
                        "company_name": company.get("name"),
                        "admin_email": admin["email"],
                        "days_since_created": days_old,
                    }
                )
            except Exception as e:
                logger.warning(f"[activation] Error creando notification: {e}")
            # Audit
            try:
                await log_audit(
                    "COMPANY_DEACTIVATED_ACTIVATION_EXPIRED",
                    actor_email="system@activation-task",
                    actor_role="system",
                    company_id=str(company["_id"]),
                    metadata={"company_name": company.get("name"), "days": days_old}
                )
            except Exception:
                pass
            logger.info(f"[activation] Desactivada optica={company.get('name')} admin={admin['email']} dias={days_old}")
        except Exception as e:
            logger.error(f"[activation] Error desactivando company={company.get('name')}: {e}")


async def run_once():
    """Ejecuta un ciclo completo (util para tests o cron externo)."""
    now = datetime.now(timezone.utc)
    app_url = os.environ.get("APP_URL", "https://cortexiaoptical.com")
    logger.info(f"[activation] Ciclo iniciado at {now.isoformat()}")
    await _process_welcome_tips(now, app_url)
    await _process_reminders(now, app_url)
    await _process_deactivations(now)
    logger.info("[activation] Ciclo completado")


async def activation_task_loop():
    """Loop infinito que corre cada CHECK_INTERVAL_SECONDS."""
    # Espera inicial de 60s para que la app arranque limpiamente
    await asyncio.sleep(60)
    while True:
        try:
            await run_once()
        except Exception as e:
            logger.error(f"[activation] Ciclo fallo: {e}")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
