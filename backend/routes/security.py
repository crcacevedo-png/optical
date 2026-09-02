"""Manifiesto de Seguridad - PDF descargable para compartir con auditores, contadores
o pacientes que requieran documentacion formal de las practicas de seguridad de Cortexia."""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
import io
import asyncio

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib import colors

router = APIRouter(prefix="/security", tags=["Seguridad"])

# Marca y branding
BRAND_DARK = colors.HexColor("#1B2A49")
BRAND_TEAL = colors.HexColor("#1ABC9C")
BRAND_PURPLE = colors.HexColor("#5A2D82")
TEXT_DARK = colors.HexColor("#0F172A")
TEXT_MUTED = colors.HexColor("#64748B")
EMERALD = colors.HexColor("#059669")
EMERALD_LIGHT = colors.HexColor("#D1FAE5")
LINE_LIGHT = colors.HexColor("#E2E8F0")

CONTACT_EMAIL = "info@cortexiagt.com"

FEATURES = [
    ("Contrasenas con bcrypt", "Las contrasenas se almacenan con hash bcrypt usando un salt unico por usuario. No se almacenan ni transmiten en texto plano. Imposibles de revertir aun en caso de filtracion de la base de datos."),
    ("Autenticacion JWT + Cookies HttpOnly", "Tokens firmados con HMAC-SHA256, transmitidos exclusivamente en cookies HttpOnly + Secure. No accesibles desde JavaScript del navegador: proteccion estandar de la industria contra ataques XSS."),
    ("Aislamiento multi-empresa (Multi-Tenant)", "Cada optica accede unicamente a sus propios datos. El aislamiento se aplica a nivel de consulta en la base de datos (company_id) y se valida en cada endpoint del backend."),
    ("Rate Limiting y Anti Brute-Force", "Login limitado a 10 intentos/min por IP. Bloqueo automatico de la cuenta tras 5 fallos consecutivos por 15 minutos. Defensa en profundidad contra ataques automatizados."),
    ("Politica de contrasenas robusta", "Minimo 8 caracteres, mayuscula, minuscula y digito requeridos. Las sesiones se invalidan automaticamente al cambiar la contrasena (revocacion de tokens)."),
    ("Infraestructura cifrada", "HTTPS/TLS en todo el trafico cliente-servidor. Base de datos MongoDB Atlas con cifrado en reposo. Backups automaticos diarios con retencion segura."),
]


def _draw_header(c, width, height):
    """Dibuja el header con barra de marca."""
    c.setFillColor(BRAND_DARK)
    c.rect(0, height - 1.2 * inch, width, 1.2 * inch, fill=1, stroke=0)
    # Logo simbolico (escudo)
    c.setFillColor(BRAND_TEAL)
    c.circle(0.7 * inch, height - 0.6 * inch, 0.22 * inch, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(0.7 * inch - 0.06 * inch, height - 0.65 * inch, "C")
    # Titulo
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(1.15 * inch, height - 0.5 * inch, "CORTEXIA OPTICAL")
    c.setFillColor(BRAND_TEAL)
    c.setFont("Helvetica", 9)
    c.drawString(1.15 * inch, height - 0.7 * inch, "Plataforma SaaS para gestion integral de opticas")
    # Pill "MANIFIESTO DE SEGURIDAD"
    c.setFillColor(BRAND_TEAL)
    c.roundRect(width - 2.7 * inch, height - 0.75 * inch, 2.2 * inch, 0.3 * inch, 0.15 * inch, fill=1, stroke=0)
    c.setFillColor(BRAND_DARK)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width - 1.6 * inch, height - 0.57 * inch, "MANIFIESTO DE SEGURIDAD")
    # Fecha
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 8)
    c.drawRightString(width - 0.5 * inch, height - 0.95 * inch, f"Documento generado el {today}")


def _draw_intro(c, width, y):
    """Intro principal."""
    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(0.5 * inch, y, "Compromiso con la proteccion de datos clinicos")
    y -= 0.22 * inch
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 9.5)
    intro = (
        "Cortexia Optical implementa controles de seguridad de nivel empresarial para proteger los datos "
        "clinicos, recetas, diagnosticos y datos personales de pacientes que sus opticas almacenan en nuestra "
        "plataforma. Este documento resume las practicas actualmente vigentes."
    )
    # Word wrap manual
    words = intro.split()
    line = ""
    for w in words:
        test = (line + " " + w).strip()
        if c.stringWidth(test, "Helvetica", 9.5) < (width - 1.0 * inch):
            line = test
        else:
            c.drawString(0.5 * inch, y, line)
            y -= 0.16 * inch
            line = w
    if line:
        c.drawString(0.5 * inch, y, line)
        y -= 0.20 * inch
    return y


def _draw_feature(c, width, y, idx, title, desc):
    """Dibuja un bloque de feature."""
    # Numero circular
    c.setFillColor(EMERALD)
    c.circle(0.65 * inch, y + 0.04 * inch, 0.13 * inch, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(0.65 * inch, y, str(idx))
    # Titulo
    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(0.95 * inch, y + 0.02 * inch, title)
    y -= 0.18 * inch
    # Descripcion (word wrap)
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 9)
    max_width = width - 1.45 * inch
    words = desc.split()
    line = ""
    for w in words:
        test = (line + " " + w).strip()
        if c.stringWidth(test, "Helvetica", 9) < max_width:
            line = test
        else:
            c.drawString(0.95 * inch, y, line)
            y -= 0.14 * inch
            line = w
    if line:
        c.drawString(0.95 * inch, y, line)
        y -= 0.14 * inch
    y -= 0.10 * inch
    return y


def _draw_footer(c, width):
    """Footer con contacto."""
    # Banda inferior
    c.setFillColor(BRAND_DARK)
    c.rect(0, 0, width, 0.75 * inch, fill=1, stroke=0)
    # Linea teal arriba del footer
    c.setFillColor(BRAND_TEAL)
    c.rect(0, 0.75 * inch, width, 0.04 * inch, fill=1, stroke=0)
    # Texto
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.5 * inch, 0.48 * inch, "Reportes de seguridad / consultas:")
    c.setFillColor(BRAND_TEAL)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(0.5 * inch, 0.28 * inch, CONTACT_EMAIL)
    # Derecha
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.setFont("Helvetica", 8)
    c.drawRightString(width - 0.5 * inch, 0.48 * inch, "Cortexia Optical")
    c.drawRightString(width - 0.5 * inch, 0.34 * inch, "cortexiaoptical.com")
    c.drawRightString(width - 0.5 * inch, 0.20 * inch, "Manifiesto v1.0")


def generate_security_manifesto_pdf() -> io.BytesIO:
    buffer = io.BytesIO()
    width, height = LETTER
    c = canvas.Canvas(buffer, pagesize=LETTER)

    # Header
    _draw_header(c, width, height)

    # Intro
    y = height - 1.6 * inch
    y = _draw_intro(c, width, y)

    # Divider sutil
    c.setStrokeColor(LINE_LIGHT)
    c.setLineWidth(0.5)
    c.line(0.5 * inch, y, width - 0.5 * inch, y)
    y -= 0.25 * inch

    # Seccion features
    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(0.5 * inch, y, "Controles de seguridad implementados")
    y -= 0.28 * inch

    for idx, (title, desc) in enumerate(FEATURES, start=1):
        y = _draw_feature(c, width, y, idx, title, desc)

    # Caja de privacidad
    y -= 0.05 * inch
    c.setFillColor(EMERALD_LIGHT)
    c.setStrokeColor(EMERALD)
    c.setLineWidth(0.8)
    box_h = 0.75 * inch
    c.roundRect(0.5 * inch, y - box_h, width - 1.0 * inch, box_h, 0.08 * inch, fill=1, stroke=1)
    c.setFillColor(EMERALD)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.7 * inch, y - 0.25 * inch, "Sus datos clinicos son privados")
    c.setFillColor(TEXT_DARK)
    c.setFont("Helvetica", 8.5)
    c.drawString(0.7 * inch, y - 0.43 * inch, "Cortexia Optical no comparte, vende ni cede datos de pacientes a terceros bajo ninguna circunstancia.")
    c.drawString(0.7 * inch, y - 0.58 * inch, "Los datos clinicos se acceden unicamente mediante autenticacion valida del personal autorizado de cada optica.")

    # Footer
    _draw_footer(c, width)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


@router.get("/manifesto.pdf")
async def download_security_manifesto():
    """Endpoint publico para descargar el manifiesto de seguridad en PDF."""
    buffer = await asyncio.to_thread(generate_security_manifesto_pdf)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="Cortexia_Manifiesto_Seguridad.pdf"'},
    )
