"""Servicio de email transaccional con Resend.
Maneja envios no-bloqueantes con asyncio.to_thread + plantillas HTML inline-styled
para maxima compatibilidad con clientes de email.
"""
import os
import asyncio
import base64
import logging
import html
from datetime import datetime, timezone, timedelta
from typing import Optional
import resend
from pymongo import ReturnDocument
from db import db

logger = logging.getLogger(__name__)

BRAND_DARK = "#1B2A49"
BRAND_TEAL = "#1ABC9C"
BRAND_EMERALD = "#059669"
BRAND_RED = "#DC2626"
TEXT_MUTED = "#64748B"


def _e(s) -> str:
    """HTML-escape para prevenir HTML injection en interpolaciones de nombres/company/etc.
    (P3 hardening Feb 2026). Uso: interpolar variables externas dentro de plantillas HTML.
    """
    if s is None:
        return ""
    return html.escape(str(s), quote=True)


def _get_config():
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = os.environ.get("SENDER_EMAIL", "noreply@mail.cortexiaoptical.com").strip()
    app_url = os.environ.get("APP_URL", "https://cortexiaoptical.com").strip().rstrip("/")
    return api_key, sender, app_url


async def send_email(to: str, subject: str, html: str, *, tag: Optional[str] = None, attachments: Optional[list] = None) -> bool:
    """Envia un email no-bloqueante. Retorna True si exitoso, False si fallo (no lanza excepcion).

    attachments: lista opcional de dicts {filename, content (bytes o base64 str)}.
    """
    api_key, sender, _ = _get_config()
    if not api_key:
        logger.warning(f"RESEND_API_KEY no configurado. Email a {to} NO enviado.")
        return False
    try:
        resend.api_key = api_key
        params = {
            "from": f"Cortexia Optical <{sender}>",
            "to": [to],
            "subject": subject,
            "html": html,
        }
        if tag:
            params["tags"] = [{"name": "category", "value": tag}]
        if attachments:
            import base64
            enc_atts = []
            for att in attachments:
                content = att.get("content")
                if isinstance(content, (bytes, bytearray)):
                    content = base64.b64encode(content).decode("ascii")
                enc_atts.append({
                    "filename": att["filename"],
                    "content": content,
                    **({"content_type": att["content_type"]} if att.get("content_type") else {}),
                })
            params["attachments"] = enc_atts
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email enviado: to={to} subject='{subject}' id={result.get('id') if isinstance(result, dict) else 'n/a'}")
        return True
    except Exception as e:
        logger.error(f"Error enviando email a {to}: {e}")
        return False


# ─────────────────────────── COLA DURABLE DE EMAILS ───────────────────────────
# Los emails se persisten en la coleccion `email_queue` y un worker interno los
# envia con reintentos + backoff exponencial. Sobrevive reinicios del pod, da
# visibilidad (la coleccion es inspeccionable) y no bloquea la respuesta HTTP.
EMAIL_MAX_ATTEMPTS = int(os.environ.get("EMAIL_MAX_ATTEMPTS", "5"))
EMAIL_WORKER_INTERVAL = int(os.environ.get("EMAIL_WORKER_INTERVAL", "5"))          # segundos entre polls
EMAIL_STALE_SENDING_SEC = int(os.environ.get("EMAIL_STALE_SENDING_SEC", "300"))    # reclamar "sending" colgados
EMAIL_BATCH = int(os.environ.get("EMAIL_WORKER_BATCH", "20"))

# Mantiene referencias fuertes de tareas fallback para evitar GC prematuro.
_BG_TASKS: set = set()


def _encode_attachments(attachments):
    """Convierte el content (bytes) de cada adjunto a base64 str para guardar en Mongo."""
    if not attachments:
        return None
    out = []
    for att in attachments:
        content = att.get("content")
        if isinstance(content, (bytes, bytearray)):
            content = base64.b64encode(content).decode("ascii")
        out.append({
            "filename": att["filename"],
            "content": content,
            **({"content_type": att["content_type"]} if att.get("content_type") else {}),
        })
    return out


async def queue_email(to: str, subject: str, html: str, *, tag: Optional[str] = None,
                      attachments: Optional[list] = None) -> None:
    """Encola un email de forma DURABLE (lo persiste en `email_queue`).

    La respuesta HTTP no espera el envio real; el worker interno lo procesa con
    reintentos. Best-effort: si el insert en Mongo falla, hace fallback a un
    envio directo en background (con referencia fuerte para no ser GC'd).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = {
        "to": to,
        "subject": subject,
        "html": html,
        "tag": tag,
        "attachments": _encode_attachments(attachments),
        "status": "pending",
        "attempts": 0,
        "max_attempts": EMAIL_MAX_ATTEMPTS,
        "next_attempt_at": now_iso,
        "last_error": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    try:
        await db.email_queue.insert_one(doc)
    except Exception as e:
        logger.error(f"No se pudo encolar email a {to}: {e}. Fallback a envio directo.")
        _t = asyncio.create_task(send_email(to, subject, html, tag=tag, attachments=attachments))
        _BG_TASKS.add(_t)
        _t.add_done_callback(_BG_TASKS.discard)


async def _process_email_queue_once() -> int:
    """Procesa hasta EMAIL_BATCH emails pendientes cuyo next_attempt_at ya vencio.
    Reclama cada doc de forma atomica (pending -> sending) para ser multi-pod safe.
    Retorna cuantos emails intento enviar."""
    processed = 0
    for _ in range(EMAIL_BATCH):
        now_iso = datetime.now(timezone.utc).isoformat()
        doc = await db.email_queue.find_one_and_update(
            {"status": "pending", "next_attempt_at": {"$lte": now_iso}},
            {"$set": {"status": "sending", "updated_at": now_iso}},
            sort=[("next_attempt_at", 1)],
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            break
        processed += 1
        ok = await send_email(
            doc["to"], doc["subject"], doc["html"],
            tag=doc.get("tag"), attachments=doc.get("attachments"),
        )
        done = datetime.now(timezone.utc)
        if ok:
            await db.email_queue.update_one(
                {"_id": doc["_id"]},
                {"$set": {"status": "sent", "completed_at": done, "updated_at": done.isoformat()}},
            )
        else:
            attempts = int(doc.get("attempts", 0)) + 1
            if attempts >= int(doc.get("max_attempts", EMAIL_MAX_ATTEMPTS)):
                await db.email_queue.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"status": "failed", "attempts": attempts,
                              "completed_at": done, "updated_at": done.isoformat(),
                              "last_error": "max_attempts alcanzado"}},
                )
                logger.error(f"Email a {doc.get('to')} FALLIDO tras {attempts} intentos.")
            else:
                backoff = min(30 * (2 ** (attempts - 1)), 1800)  # 30s,60s,120s,...max 30min
                nxt = (done + timedelta(seconds=backoff)).isoformat()
                await db.email_queue.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"status": "pending", "attempts": attempts,
                              "next_attempt_at": nxt, "updated_at": done.isoformat(),
                              "last_error": "envio fallido (reintentara)"}},
                )
    return processed


async def _recover_stale_sending():
    """Devuelve a 'pending' los emails que quedaron en 'sending' (pod muerto a mitad del envio)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=EMAIL_STALE_SENDING_SEC)).isoformat()
    try:
        await db.email_queue.update_many(
            {"status": "sending", "updated_at": {"$lt": cutoff}},
            {"$set": {"status": "pending"}},
        )
    except Exception as e:
        logger.error(f"Error recuperando emails colgados: {e}")


async def email_worker_loop():
    """Loop interno que drena la cola de emails. Se arranca en el startup del server
    (mismo patron que activation_task_loop). Corre en el mismo pod, sin proceso worker aparte."""
    logger.info(f"Email worker loop started (interval={EMAIL_WORKER_INTERVAL}s, max_attempts={EMAIL_MAX_ATTEMPTS})")
    while True:
        try:
            await _recover_stale_sending()
            n = await _process_email_queue_once()
            if n >= EMAIL_BATCH:
                continue  # habia mucho trabajo: sigue drenando sin dormir
        except Exception as e:
            logger.error(f"Email worker error: {e}")
        await asyncio.sleep(EMAIL_WORKER_INTERVAL)


# ─────────────────────────────────── TEMPLATES ───────────────────────────────────

def _wrapper(content: str, heading: str = "Cortexia Optical") -> str:
    """Envoltorio comun (header dark + content + footer)."""
    _, _, app_url = _get_config()
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background-color:#F1F5F9;font-family:Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#F1F5F9;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background-color:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.04);max-width:600px;">
        <tr><td style="background-color:#FFFFFF;padding:28px 32px 20px 32px;text-align:center;border-bottom:1px solid #E2E8F0;">
          <img src="https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png"
               alt="Cortexia Optical"
               width="180"
               style="display:block;margin:0 auto;height:auto;max-height:90px;border:0;outline:none;text-decoration:none;" />
        </td></tr>
        <tr><td style="height:4px;background:linear-gradient(90deg,{BRAND_DARK} 0%,{BRAND_TEAL} 100%);line-height:4px;font-size:0;">&nbsp;</td></tr>
        <tr><td style="padding:36px 36px 16px 36px;">
          <h1 style="color:{BRAND_DARK};margin:0 0 24px 0;font-size:22px;font-weight:bold;line-height:1.3;">{heading}</h1>
          {content}
        </td></tr>
        <tr><td style="padding:24px 36px;background-color:#F8FAFC;border-top:1px solid #E2E8F0;">
          <p style="color:{TEXT_MUTED};font-size:12px;margin:0 0 6px 0;line-height:1.5;">
            Este mensaje fue enviado automaticamente por Cortexia Optical.
          </p>
          <p style="color:{TEXT_MUTED};font-size:12px;margin:0;line-height:1.5;">
            <a href="{app_url}" style="color:{BRAND_TEAL};text-decoration:none;">{app_url}</a>
            &nbsp;·&nbsp;
            <a href="mailto:info@cortexiagt.com" style="color:{BRAND_TEAL};text-decoration:none;">info@cortexiagt.com</a>
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _button(text: str, href: str, color: str = BRAND_EMERALD) -> str:
    return f"""<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:24px 0;"><tr><td style="background-color:{color};border-radius:8px;">
        <a href="{href}" style="display:inline-block;padding:14px 28px;color:#FFFFFF;text-decoration:none;font-size:15px;font-weight:bold;font-family:Helvetica,Arial,sans-serif;">{text}</a>
    </td></tr></table>"""


def render_quotation_email(patient_name: str, company_name: str, quotation_number: str, total_str: str, expiry_date: str, notes: Optional[str] = None) -> str:
    """Email para enviar la cotizacion (con PDF adjunto) al paciente."""
    patient_name, company_name = _e(patient_name), _e(company_name)
    quotation_number, total_str, expiry_date = _e(quotation_number), _e(total_str), _e(expiry_date)
    notes_block = ""
    if notes:
        notes_block = f'<p style="color:#475569;font-size:14px;line-height:1.6;margin:16px 0 0 0;"><strong>Notas:</strong> {_e(notes[:300])}</p>'
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{patient_name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        Adjuntamos la cotizacion <strong style="color:{BRAND_DARK};">{quotation_number}</strong> preparada especialmente para ti por <strong>{company_name}</strong>.
      </p>
      <div style="background-color:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:16px 20px;margin:20px 0;">
        <p style="color:#065F46;font-size:13px;margin:0 0 4px 0;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;">Resumen</p>
        <p style="color:#0F172A;font-size:14px;margin:4px 0;"><strong>No. Cotizacion:</strong> {quotation_number}</p>
        <p style="color:#0F172A;font-size:14px;margin:4px 0;"><strong>Total:</strong> {total_str}</p>
        <p style="color:#0F172A;font-size:14px;margin:4px 0;"><strong>Vigencia hasta:</strong> {expiry_date}</p>
      </div>
      {notes_block}
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:24px 0 0 0;">
        Encontraras el detalle completo en el archivo PDF adjunto.
        Si tienes preguntas o deseas confirmar tu pedido, no dudes en contactarnos.
      </p>
      <p style="color:#475569;font-size:13px;line-height:1.6;margin:16px 0 0 0;color:{TEXT_MUTED};">Este correo fue enviado por {company_name} a traves de Cortexia Optical.</p>
    """
    return _wrapper(content, "Tu cotizacion esta lista")


def render_password_reset(name: str, reset_link: str) -> str:
    """Email de restablecimiento de contrasena."""
    name = _e(name)
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        Recibimos una solicitud para restablecer la contrasena de tu cuenta en Cortexia Optical.
        Si no fuiste tu, puedes ignorar este mensaje sin problema.
      </p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 8px 0;">
        Si si lo solicitaste, haz clic en el siguiente boton para crear una nueva contrasena:
      </p>
      {_button("Restablecer mi contrasena", reset_link, BRAND_EMERALD)}
      <div style="background-color:#FEF3C7;border-left:3px solid #F59E0B;padding:12px 16px;border-radius:6px;margin:24px 0;">
        <p style="color:#92400E;font-size:13px;margin:0;line-height:1.5;">
          <strong>Importante:</strong> Este enlace expira en <strong>1 hora</strong> por seguridad.
          Si no se usa, sera invalidado automaticamente.
        </p>
      </div>
      <p style="color:{TEXT_MUTED};font-size:12px;line-height:1.5;margin:24px 0 0 0;">
        Si el boton no funciona, copia y pega este enlace en tu navegador:<br>
        <span style="word-break:break-all;color:#475569;">{reset_link}</span>
      </p>
    """
    return _wrapper(content, "Restablece tu contrasena")


def render_welcome_company(admin_name: str, company_name: str, admin_email: str, admin_password: str, login_link: str) -> str:
    """Email de bienvenida cuando se crea una nueva optica."""
    admin_name, company_name, admin_email = _e(admin_name), _e(company_name), _e(admin_email)
    # admin_password NO se escapa: se muestra en <span monospace>; contiene solo chars alfanumerciso generados por servidor
    admin_password = _e(admin_password)
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{admin_name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        Bienvenido a Cortexia Optical. Tu optica <strong style="color:{BRAND_DARK};">{company_name}</strong>
        ha sido creada exitosamente en nuestra plataforma.
      </p>
      <div style="background-color:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:16px 20px;margin:24px 0;">
        <p style="color:#065F46;font-size:13px;margin:0 0 8px 0;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;">Tus credenciales de acceso</p>
        <p style="color:#0F172A;font-size:14px;margin:4px 0;"><strong>Email:</strong> {admin_email}</p>
        <p style="color:#0F172A;font-size:14px;margin:4px 0;"><strong>Contrasena temporal:</strong> <span style="font-family:'Courier New',monospace;background-color:#FFFFFF;padding:3px 8px;border-radius:4px;border:1px solid #BBF7D0;color:#065F46;font-weight:bold;letter-spacing:0.5px;">{admin_password}</span></p>
        <p style="color:#B45309;font-size:12px;margin:10px 0 0 0;background-color:#FFFBEB;border-left:3px solid #F59E0B;padding:8px 10px;border-radius:4px;">
          <strong>Por seguridad:</strong> cambia esta contrasena la primera vez que ingreses, desde el menu superior derecho &rarr; <em>Cambiar mi contrasena</em>.
        </p>
      </div>
      {_button("Ingresar a Cortexia", login_link, BRAND_EMERALD)}

      <div style="background:linear-gradient(135deg,#6D35D8 0%,#13B8B0 100%);border-radius:10px;padding:20px 22px;margin:28px 0 8px 0;">
        <p style="color:#FFFFFF;font-size:13px;margin:0 0 4px 0;font-weight:bold;text-transform:uppercase;letter-spacing:0.6px;opacity:0.85;">&#x1F680; Inicio rapido recomendado</p>
        <p style="color:#FFFFFF;font-size:15px;line-height:1.5;margin:0 0 14px 0;font-weight:600;">
          Completa la configuracion inicial en 7 pasos guiados para dejar tu optica 100% operativa.
        </p>
        <p style="color:#FFFFFF;font-size:13px;line-height:1.6;margin:0 0 14px 0;opacity:0.9;">
          Al iniciar sesion, dirigete al menu lateral &rarr; <strong style="color:#FFFFFF;">Inicio rapido</strong>,
          o haz clic en el boton de abajo para ir directamente. Veras el progreso en tu Dashboard.
        </p>
        <table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>
          <td style="background-color:#FFFFFF;border-radius:8px;">
            <a href="{login_link}/onboarding" style="display:inline-block;padding:11px 22px;color:#0F172A;text-decoration:none;font-size:14px;font-weight:bold;font-family:Helvetica,Arial,sans-serif;">
              Ir al Inicio rapido &rarr;
            </a>
          </td>
        </tr></table>
      </div>

      <h3 style="color:{BRAND_DARK};font-size:16px;margin:32px 0 12px 0;">Primeros pasos recomendados</h3>
      <ol style="color:#475569;font-size:14px;line-height:1.8;margin:0;padding-left:20px;">
        <li>Configura los datos de tu optica (logo, direccion, telefono) en <em>Configuracion</em>.</li>
        <li>Crea tus sucursales si tienes varias ubicaciones.</li>
        <li>Da de alta a tu equipo en <em>Usuarios</em> (optometristas, vendedores, etc.).</li>
        <li>Empieza a registrar pacientes y consultas.</li>
        <li>Carga tu inventario inicial de productos.</li>
      </ol>
      <div style="background-color:#FEF3C7;border-left:3px solid #F59E0B;padding:12px 16px;border-radius:6px;margin:24px 0;">
        <p style="color:#92400E;font-size:13px;margin:0;line-height:1.5;">
          <strong>Importante:</strong> tienes <strong>30 dias</strong> para ingresar por primera vez.
          Si no activas tu cuenta en ese plazo, la optica sera desactivada y necesitaras solicitar
          una nueva contrasena a nuestro equipo para reactivarla.
        </p>
      </div>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:24px 0 0 0;">
        Si necesitas ayuda, escribenos a
        <a href="mailto:info@cortexiagt.com" style="color:{BRAND_TEAL};">info@cortexiagt.com</a>.
        Estamos para apoyarte.
      </p>
    """
    return _wrapper(content, f"Bienvenido, {company_name}")


def render_activation_reminder(admin_name: str, company_name: str, days_remaining: int, login_link: str) -> str:
    """Recordatorio al admin cuando faltan pocos dias para desactivar la optica por falta de activacion."""
    admin_name, company_name = _e(admin_name), _e(company_name)
    urgency = "urgente" if days_remaining <= 3 else "importante"
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{admin_name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        Notamos que aun no has iniciado sesion en tu cuenta de Cortexia Optical para
        <strong style="color:{BRAND_DARK};">{company_name}</strong>.
      </p>
      <div style="background-color:#FEF2F2;border:1px solid #FECACA;border-radius:8px;padding:16px 20px;margin:24px 0;">
        <p style="color:#991B1B;font-size:14px;margin:0 0 6px 0;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;">Recordatorio {urgency}</p>
        <p style="color:#0F172A;font-size:15px;margin:0;line-height:1.6;">
          Te quedan <strong style="color:#DC2626;">{days_remaining} dia{'s' if days_remaining != 1 else ''}</strong>
          para activar tu cuenta. Si no ingresas antes, la optica sera <strong>desactivada</strong> y tendras que
          solicitar una nueva contrasena a nuestro equipo para reactivarla.
        </p>
      </div>
      {_button("Ingresar ahora a mi cuenta", login_link, BRAND_EMERALD)}
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:24px 0 0 0;">
        Si perdiste tu contrasena, puedes usar <em>Olvide mi contrasena</em> en la pantalla de login.
        Si necesitas ayuda, escribenos a
        <a href="mailto:info@cortexiagt.com" style="color:{BRAND_TEAL};">info@cortexiagt.com</a>.
      </p>
    """
    return _wrapper(content, "Activa tu cuenta antes que expire")


def render_deactivation_notice(admin_name: str, company_name: str) -> str:
    """Email cuando la optica se desactiva por no haber sido activada en 30 dias."""
    admin_name, company_name = _e(admin_name), _e(company_name)
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{admin_name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        Como no registramos ningun inicio de sesion en tu cuenta de Cortexia Optical para
        <strong style="color:{BRAND_DARK};">{company_name}</strong> en los ultimos 30 dias,
        la optica ha sido <strong>desactivada</strong> automaticamente por seguridad.
      </p>
      <div style="background-color:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:16px 20px;margin:24px 0;">
        <p style="color:#065F46;font-size:13px;margin:0 0 8px 0;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;">Como reactivarla</p>
        <p style="color:#0F172A;font-size:14px;margin:0;line-height:1.6;">
          Contactanos a <a href="mailto:info@cortexiagt.com" style="color:{BRAND_TEAL};font-weight:bold;">info@cortexiagt.com</a>
          o al WhatsApp de soporte y con gusto te generaremos una nueva contrasena para que ingreses y
          reactivemos tu optica en pocos minutos.
        </p>
      </div>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:24px 0 0 0;">
        Gracias por tu interes en Cortexia Optical. Estamos aqui cuando estes listo para empezar.
      </p>
    """
    return _wrapper(content, "Tu optica fue desactivada")


def render_onboarding_tips(admin_name: str, company_name: str, login_link: str) -> str:
    """Email amigable dia 3 al admin que aun no ha ingresado - motivador con tips practicos."""
    admin_name, company_name = _e(admin_name), _e(company_name)
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{admin_name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        Notamos que aun no has empezado a explorar Cortexia Optical con
        <strong style="color:{BRAND_DARK};">{company_name}</strong>.
        No te preocupes, es normal — sabemos que estas ocupado atendiendo tu optica.
      </p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        Te comparto <strong>5 tips</strong> que otras opticas usaron para dejar Cortexia
        <strong>operativo en menos de 30 minutos</strong>:
      </p>
      <div style="background-color:#F8FAFC;border-radius:10px;padding:20px 22px;margin:24px 0;">
        <div style="margin-bottom:14px;">
          <p style="color:{BRAND_DARK};font-size:14px;margin:0 0 4px 0;font-weight:bold;">1. Empieza por lo esencial</p>
          <p style="color:#475569;font-size:13px;margin:0;line-height:1.5;">Registra 5 pacientes reales de esta semana. No necesitas migrar todos de golpe.</p>
        </div>
        <div style="margin-bottom:14px;">
          <p style="color:{BRAND_DARK};font-size:14px;margin:0 0 4px 0;font-weight:bold;">2. Configura tu logo y datos de la optica</p>
          <p style="color:#475569;font-size:13px;margin:0;line-height:1.5;">Ve a Configuracion &rarr; Empresa y sube tu logo. Aparecera en PDFs, recetas y cotizaciones.</p>
        </div>
        <div style="margin-bottom:14px;">
          <p style="color:{BRAND_DARK};font-size:14px;margin:0 0 4px 0;font-weight:bold;">3. Crea tu primer inventario</p>
          <p style="color:#475569;font-size:13px;margin:0;line-height:1.5;">Registra 10 armazones y 5 lentes que mas vendes. Puedes agregar el resto despues.</p>
        </div>
        <div style="margin-bottom:14px;">
          <p style="color:{BRAND_DARK};font-size:14px;margin:0 0 4px 0;font-weight:bold;">4. Registra una venta de prueba</p>
          <p style="color:#475569;font-size:13px;margin:0;line-height:1.5;">Simula una venta real con multi-pago. Veras como el ticket, la caja y el stock se actualizan solos.</p>
        </div>
        <div>
          <p style="color:{BRAND_DARK};font-size:14px;margin:0 0 4px 0;font-weight:bold;">5. Invita a tu equipo</p>
          <p style="color:#475569;font-size:13px;margin:0;line-height:1.5;">Da de alta a tus optometristas y vendedores. Cada uno tendra su propio acceso con permisos.</p>
        </div>
      </div>
      <div style="background:linear-gradient(135deg,#6D35D8 0%,#13B8B0 100%);border-radius:10px;padding:20px 22px;margin:24px 0 8px 0;">
        <p style="color:#FFFFFF;font-size:13px;margin:0 0 4px 0;font-weight:bold;text-transform:uppercase;letter-spacing:0.6px;opacity:0.85;">Recomendacion</p>
        <p style="color:#FFFFFF;font-size:15px;line-height:1.5;margin:0 0 14px 0;font-weight:600;">
          Sigue nuestra guia "Inicio Rapido" — son 7 pasos con checklist y toma menos de 30 minutos.
        </p>
        <table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>
          <td style="background-color:#FFFFFF;border-radius:8px;">
            <a href="{login_link}/onboarding" style="display:inline-block;padding:11px 22px;color:#0F172A;text-decoration:none;font-size:14px;font-weight:bold;font-family:Helvetica,Arial,sans-serif;">
              Empezar Inicio Rapido &rarr;
            </a>
          </td>
        </tr></table>
      </div>
      {_button("Ingresar a Cortexia", login_link, BRAND_EMERALD)}
      <p style="color:{TEXT_MUTED};font-size:12px;line-height:1.5;margin:24px 0 0 0;">
        Recuerda que tienes hasta el <strong>dia 30</strong> desde tu registro para activar la cuenta.
        Si necesitas ayuda, escribenos a
        <a href="mailto:info@cortexiagt.com" style="color:{BRAND_TEAL};">info@cortexiagt.com</a>.
      </p>
    """
    return _wrapper(content, f"Tips para empezar con {company_name}")


def render_reactivation_notice(admin_name: str, company_name: str, reset_link: str) -> str:
    """Email cuando el SuperAdmin reactiva una optica manualmente."""
    admin_name, company_name = _e(admin_name), _e(company_name)
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{admin_name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        Buenas noticias — tu optica <strong style="color:{BRAND_DARK};">{company_name}</strong> ha sido
        <strong>reactivada</strong> por el equipo de Cortexia Optical.
      </p>
      <div style="background-color:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:16px 20px;margin:24px 0;">
        <p style="color:#065F46;font-size:13px;margin:0 0 8px 0;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;">Ultimo paso</p>
        <p style="color:#0F172A;font-size:14px;margin:0;line-height:1.6;">
          Por seguridad, necesitas establecer una <strong>nueva contrasena</strong>. Haz clic en el boton
          y en pocos segundos podras ingresar a tu cuenta.
        </p>
      </div>
      {_button("Establecer nueva contrasena", reset_link, BRAND_EMERALD)}
      <div style="background-color:#FEF3C7;border-left:3px solid #F59E0B;padding:12px 16px;border-radius:6px;margin:24px 0;">
        <p style="color:#92400E;font-size:13px;margin:0;line-height:1.5;">
          <strong>Importante:</strong> este enlace expira en <strong>24 horas</strong>. Si necesitas otro,
          escribenos a <a href="mailto:info@cortexiagt.com" style="color:{BRAND_TEAL};">info@cortexiagt.com</a>.
        </p>
      </div>
      <p style="color:{TEXT_MUTED};font-size:12px;line-height:1.5;margin:24px 0 0 0;">
        Si el boton no funciona, copia y pega este enlace en tu navegador:<br>
        <span style="word-break:break-all;color:#475569;">{reset_link}</span>
      </p>
    """
    return _wrapper(content, f"Tu optica {company_name} fue reactivada")


def render_security_alert(name: str, event_title: str, event_description: str, event_meta: dict, app_url: str) -> str:
    """Email de alerta de seguridad."""
    name, event_title, event_description = _e(name), _e(event_title), _e(event_description)
    meta_rows = ""
    for k, v in event_meta.items():
        meta_rows += f"""<tr>
          <td style="padding:6px 12px 6px 0;color:{TEXT_MUTED};font-size:12px;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;vertical-align:top;">{_e(k)}</td>
          <td style="padding:6px 0;color:#0F172A;font-size:13px;word-break:break-word;">{_e(v)}</td>
        </tr>"""
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        Detectamos un evento de seguridad en tu cuenta de Cortexia Optical que requiere tu atencion:
      </p>
      <div style="background-color:#FEF2F2;border-left:4px solid {BRAND_RED};border-radius:6px;padding:16px 20px;margin:20px 0;">
        <p style="color:{BRAND_RED};font-size:15px;margin:0 0 6px 0;font-weight:bold;">{event_title}</p>
        <p style="color:#7F1D1D;font-size:13px;margin:0;line-height:1.5;">{event_description}</p>
      </div>
      <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="width:100%;background-color:#F8FAFC;border-radius:8px;padding:16px 20px;margin:16px 0;">
        {meta_rows}
      </table>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:24px 0 8px 0;">
        <strong>Si no reconoces esta actividad</strong>, te recomendamos:
      </p>
      <ul style="color:#475569;font-size:14px;line-height:1.7;margin:0 0 24px 0;padding-left:20px;">
        <li>Cambiar tu contrasena inmediatamente.</li>
        <li>Revisar el historial de auditoria de la plataforma.</li>
        <li>Reportar el incidente a <a href="mailto:info@cortexiagt.com" style="color:{BRAND_TEAL};">info@cortexiagt.com</a>.</li>
      </ul>
      {_button("Ir a mi cuenta", app_url, BRAND_DARK)}
    """
    return _wrapper(content, "Alerta de seguridad")



def render_support_ticket(*, ticket_id: str, subject: str, message: str, category: str, priority: str,
                          creator_name: str, creator_email: str, company_name: str) -> str:
    """Email al equipo Cortexia cuando llega un ticket nuevo."""
    subject_e, message_e = _e(subject), _e(message)
    category_e, priority_e = _e(category), _e(priority)
    creator_name_e, creator_email_e, company_name_e = _e(creator_name), _e(creator_email), _e(company_name)
    ticket_id_e = _e(ticket_id)
    _, _, app_url = _get_config()
    priority_colors = {
        "alta": ("#DC2626", "#FEE2E2"),
        "media": ("#D97706", "#FEF3C7"),
        "baja": ("#475569", "#F1F5F9"),
    }
    color, bg = priority_colors.get(priority, priority_colors["media"])
    detail_url = f"{app_url}/admin/soporte"
    content = f"""
      <p style="color:#334155;font-size:15px;line-height:1.6;margin:0 0 12px 0;">
        Se ha creado un nuevo ticket de soporte en la plataforma.
      </p>
      <div style="background-color:{bg};border-left:4px solid {color};padding:16px 20px;border-radius:6px;margin:16px 0;">
        <p style="color:{color};font-size:11px;margin:0 0 4px 0;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;">
          Prioridad: {priority_e}  ·  {category_e}
        </p>
        <p style="color:#0F172A;font-size:16px;margin:0;font-weight:bold;">{subject_e}</p>
      </div>
      <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="width:100%;background-color:#F8FAFC;border-radius:8px;padding:14px 18px;margin:16px 0;">
        <tr><td style="padding:4px 0;color:#64748B;font-size:13px;">Optica:</td><td style="padding:4px 0;color:#0F172A;font-size:13px;font-weight:bold;text-align:right;">{company_name_e}</td></tr>
        <tr><td style="padding:4px 0;color:#64748B;font-size:13px;">Usuario:</td><td style="padding:4px 0;color:#0F172A;font-size:13px;text-align:right;">{creator_name_e}</td></tr>
        <tr><td style="padding:4px 0;color:#64748B;font-size:13px;">Email:</td><td style="padding:4px 0;color:#0F172A;font-size:13px;text-align:right;"><a href="mailto:{creator_email_e}" style="color:{BRAND_TEAL};text-decoration:none;">{creator_email_e}</a></td></tr>
        <tr><td style="padding:4px 0;color:#64748B;font-size:13px;">Ticket ID:</td><td style="padding:4px 0;color:#0F172A;font-size:11px;text-align:right;font-family:monospace;">{ticket_id_e}</td></tr>
      </table>
      <div style="background-color:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:16px 20px;margin:16px 0;">
        <p style="color:#64748B;font-size:11px;margin:0 0 8px 0;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;">Mensaje</p>
        <p style="color:#0F172A;font-size:14px;line-height:1.6;margin:0;white-space:pre-wrap;">{message_e}</p>
      </div>
      {_button("Abrir el ticket", detail_url, BRAND_DARK)}
    """
    return _wrapper(content, f"Nuevo ticket: {subject[:60]}")


def render_payment_failed(admin_name: str, company_name: str, plan_name: str, amount_str: str,
                          grace_days: int, grace_until_str: str, pay_link: str) -> str:
    """Aviso al admin (dia 0) cuando falla el cobro de la membresia. Inicia periodo de gracia."""
    admin_name, company_name, plan_name = _e(admin_name), _e(company_name), _e(plan_name)
    amount_str, grace_until_str = _e(amount_str), _e(grace_until_str)
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{admin_name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        No pudimos procesar el pago de la membresia de <strong style="color:{BRAND_DARK};">{company_name}</strong>
        ({plan_name}{f' · {amount_str}' if amount_str else ''}).
      </p>
      <div style="background-color:#FFFBEB;border:1px solid #FDE68A;border-radius:8px;padding:16px 20px;margin:24px 0;">
        <p style="color:#92400E;font-size:13px;margin:0 0 6px 0;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;">Periodo de gracia</p>
        <p style="color:#0F172A;font-size:15px;margin:0;line-height:1.6;">
          Tu optica <strong>sigue funcionando normalmente</strong>, pero tienes hasta el
          <strong style="color:#B45309;">{grace_until_str}</strong> ({grace_days} dias) para regularizar el pago.
          Pasado ese plazo, la cuenta se <strong>suspendera</strong> hasta que se complete el pago.
        </p>
      </div>
      {_button("Actualizar mi pago", pay_link, BRAND_EMERALD)}
      <p style="color:{TEXT_MUTED};font-size:13px;line-height:1.6;margin:16px 0 0 0;">
        Si ya actualizaste tu tarjeta, ignora este mensaje: reactivaremos todo automaticamente en cuanto el banco confirme el cobro.
      </p>
    """
    return _wrapper(content, "Tu pago no se pudo procesar")


def render_grace_reminder(admin_name: str, company_name: str, days_remaining: int,
                          grace_until_str: str, pay_link: str) -> str:
    """Recordatorio durante el periodo de gracia (dias 1 y 2)."""
    admin_name, company_name, grace_until_str = _e(admin_name), _e(company_name), _e(grace_until_str)
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{admin_name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        Seguimos sin poder procesar el pago de la membresia de <strong style="color:{BRAND_DARK};">{company_name}</strong>.
      </p>
      <div style="background-color:#FEF2F2;border:1px solid #FECACA;border-radius:8px;padding:16px 20px;margin:24px 0;">
        <p style="color:#991B1B;font-size:14px;margin:0;line-height:1.6;">
          Te queda{'n' if days_remaining != 1 else ''} <strong style="color:#DC2626;">{days_remaining} dia{'s' if days_remaining != 1 else ''}</strong>
          (hasta el <strong>{grace_until_str}</strong>) para regularizar antes de que la cuenta se suspenda.
        </p>
      </div>
      {_button("Regularizar mi pago ahora", pay_link, BRAND_EMERALD)}
    """
    return _wrapper(content, "Recordatorio: regulariza tu pago")


def render_suspension_notice(admin_name: str, company_name: str, pay_link: str, reason: str) -> str:
    """Aviso al admin cuando la cuenta queda suspendida (muro de pago)."""
    admin_name, company_name, reason = _e(admin_name), _e(company_name), _e(reason)
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{admin_name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        La cuenta de <strong style="color:{BRAND_DARK};">{company_name}</strong> ha sido
        <strong style="color:{BRAND_RED};">suspendida</strong> por {reason}.
      </p>
      <div style="background-color:#FEF2F2;border-left:4px solid {BRAND_RED};border-radius:6px;padding:16px 20px;margin:20px 0;">
        <p style="color:#7F1D1D;font-size:14px;margin:0;line-height:1.6;">
          Mientras la cuenta este suspendida, tu equipo no podra operar. Para reactivarla al instante,
          actualiza tu metodo de pago o completa el pago pendiente.
        </p>
      </div>
      {_button("Pagar y reactivar mi cuenta", pay_link, BRAND_RED)}
      <p style="color:{TEXT_MUTED};font-size:13px;line-height:1.6;margin:16px 0 0 0;">
        La reactivacion es automatica: en cuanto el pago se confirme, tu optica recupera el acceso completo.
      </p>
    """
    return _wrapper(content, "Tu cuenta fue suspendida")


def render_payment_restored(admin_name: str, company_name: str, plan_name: str) -> str:
    """Aviso al admin cuando el pago se regulariza y la cuenta se reactiva."""
    admin_name, company_name, plan_name = _e(admin_name), _e(company_name), _e(plan_name)
    _, _, app_url = _get_config()
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{admin_name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        Buenas noticias: recibimos tu pago y la cuenta de
        <strong style="color:{BRAND_DARK};">{company_name}</strong> quedo <strong style="color:{BRAND_EMERALD};">reactivada</strong>{f' con el plan {plan_name}' if plan_name else ''}.
      </p>
      <div style="background-color:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:16px 20px;margin:24px 0;">
        <p style="color:#065F46;font-size:14px;margin:0;line-height:1.6;">
          Tu equipo ya puede operar con normalidad. Gracias por seguir con Cortexia Optical.
        </p>
      </div>
      {_button("Ingresar a mi cuenta", app_url, BRAND_EMERALD)}
    """
    return _wrapper(content, "Tu cuenta fue reactivada")



def render_verify_registration(name: str, optica_name: str, verify_link: str, hours: int = 48) -> str:
    """Correo de verificacion (doble opt-in) del autoservicio de registro."""
    name, optica_name = _e(name), _e(optica_name)
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        Gracias por crear la cuenta de tu optica <strong style="color:{BRAND_DARK};">{optica_name}</strong> en Cortexia Optical.
        Para activarla y poder ingresar, solo necesitas confirmar tu correo electronico.
      </p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 8px 0;">
        Haz clic en el siguiente boton para verificar tu correo y activar tu cuenta:
      </p>
      {_button("Verificar mi correo y activar", verify_link, BRAND_EMERALD)}
      <div style="background-color:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:14px 18px;margin:20px 0;">
        <p style="color:#065F46;font-size:13px;margin:0;line-height:1.6;">
          Tu cuenta arranca con el <strong>Plan gratuito</strong>: sin tarjeta y sin costo. Empieza hoy mismo a
          registrar pacientes. Cuando tu optica crezca, podras actualizar de plan desde la app.
        </p>
      </div>
      <div style="background-color:#FEF3C7;border-left:3px solid #F59E0B;padding:12px 16px;border-radius:6px;margin:24px 0;">
        <p style="color:#92400E;font-size:13px;margin:0;line-height:1.5;">
          <strong>Importante:</strong> este enlace expira en <strong>{hours} horas</strong> por seguridad.
          Si no fuiste tu quien se registro, puedes ignorar este mensaje.
        </p>
      </div>
      <p style="color:{TEXT_MUTED};font-size:12px;line-height:1.5;margin:24px 0 0 0;">
        Si el boton no funciona, copia y pega este enlace en tu navegador:<br>
        <span style="word-break:break-all;color:#475569;">{verify_link}</span>
      </p>
    """
    return _wrapper(content, "Verifica tu correo")


def render_welcome_self_service(admin_name: str, company_name: str, login_link: str) -> str:
    """Bienvenida tras verificar el correo (autoservicio). El usuario ya definio su
    propia contrasena, por lo que este correo NO incluye credenciales."""
    admin_name, company_name = _e(admin_name), _e(company_name)
    content = f"""
      <p style="color:#0F172A;font-size:15px;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{admin_name}</strong>,</p>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px 0;">
        Tu correo fue verificado y la cuenta de tu optica
        <strong style="color:{BRAND_DARK};">{company_name}</strong> ya esta <strong style="color:{BRAND_EMERALD};">activa</strong>.
        Puedes iniciar sesion con el correo y la contrasena que elegiste al registrarte.
      </p>
      {_button("Ingresar a Cortexia", login_link, BRAND_EMERALD)}
      <div style="background:linear-gradient(135deg,#6D35D8 0%,#13B8B0 100%);border-radius:10px;padding:20px 22px;margin:28px 0 8px 0;">
        <p style="color:#FFFFFF;font-size:13px;margin:0 0 4px 0;font-weight:bold;text-transform:uppercase;letter-spacing:0.6px;opacity:0.85;">Inicio rapido recomendado</p>
        <p style="color:#FFFFFF;font-size:15px;line-height:1.5;margin:0 0 14px 0;font-weight:600;">
          Deja tu optica lista en unos minutos con los pasos guiados del Inicio rapido.
        </p>
        <table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>
          <td style="background-color:#FFFFFF;border-radius:8px;">
            <a href="{login_link}/onboarding" style="display:inline-block;padding:11px 22px;color:#0F172A;text-decoration:none;font-size:14px;font-weight:bold;font-family:Helvetica,Arial,sans-serif;">
              Ir al Inicio rapido &rarr;
            </a>
          </td>
        </tr></table>
      </div>
      <div style="background-color:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:14px 18px;margin:20px 0;">
        <p style="color:#065F46;font-size:13px;margin:0;line-height:1.6;">
          Estas en el <strong>Plan gratuito</strong>. Cuando te acerques al limite de pacientes, la app te
          avisara y podras actualizar de plan para seguir creciendo.
        </p>
      </div>
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:24px 0 0 0;">
        Si necesitas ayuda, escribenos a
        <a href="mailto:info@cortexiagt.com" style="color:{BRAND_TEAL};">info@cortexiagt.com</a>.
      </p>
    """
    return _wrapper(content, f"Bienvenido, {company_name}")
