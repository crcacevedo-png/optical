"""Servicio de email transaccional con Resend.
Maneja envios no-bloqueantes con asyncio.to_thread + plantillas HTML inline-styled
para maxima compatibilidad con clientes de email.
"""
import os
import asyncio
import logging
from typing import Optional
import resend

logger = logging.getLogger(__name__)

BRAND_DARK = "#1B2A49"
BRAND_TEAL = "#1ABC9C"
BRAND_EMERALD = "#059669"
BRAND_RED = "#DC2626"
TEXT_MUTED = "#64748B"


def _get_config():
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = os.environ.get("SENDER_EMAIL", "noreply@mail.cortexiaoptical.com").strip()
    app_url = os.environ.get("APP_URL", "https://cortexiaoptical.com").strip().rstrip("/")
    return api_key, sender, app_url


async def send_email(to: str, subject: str, html: str, *, tag: Optional[str] = None) -> bool:
    """Envia un email no-bloqueante. Retorna True si exitoso, False si fallo (no lanza excepcion)."""
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
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email enviado: to={to} subject='{subject}' id={result.get('id') if isinstance(result, dict) else 'n/a'}")
        return True
    except Exception as e:
        logger.error(f"Error enviando email a {to}: {e}")
        return False


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
        <tr><td style="background-color:{BRAND_DARK};padding:20px 32px;text-align:left;">
          <img src="https://customer-assets.emergentagent.com/job_eyecare-erp/artifacts/80lobcqc_logo%20cortexia%20optical%20transparente.png"
               alt="Cortexia Optical"
               width="160"
               style="display:inline-block;height:auto;max-height:64px;border:0;outline:none;text-decoration:none;" />
        </td></tr>
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


def render_password_reset(name: str, reset_link: str) -> str:
    """Email de restablecimiento de contrasena."""
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
      <p style="color:#475569;font-size:14px;line-height:1.6;margin:24px 0 0 0;">
        Si necesitas ayuda, escribenos a
        <a href="mailto:info@cortexiagt.com" style="color:{BRAND_TEAL};">info@cortexiagt.com</a>.
        Estamos para apoyarte.
      </p>
    """
    return _wrapper(content, f"Bienvenido, {company_name}")


def render_security_alert(name: str, event_title: str, event_description: str, event_meta: dict, app_url: str) -> str:
    """Email de alerta de seguridad."""
    meta_rows = ""
    for k, v in event_meta.items():
        meta_rows += f"""<tr>
          <td style="padding:6px 12px 6px 0;color:{TEXT_MUTED};font-size:12px;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;vertical-align:top;">{k}</td>
          <td style="padding:6px 0;color:#0F172A;font-size:13px;word-break:break-word;">{v}</td>
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
