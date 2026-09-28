"""
Genera la guia de uso de Cortexia Optical en PDF.
Publico (auth requerido pero sin restriccion de rol) para que el equipo pueda descargarla
y compartirla con prospectos comerciales.

Endpoints:
- GET /api/docs/user-guide.pdf (admin/superadmin)
- POST /api/docs/share-link (admin/superadmin) -> genera URL firmada publica
- GET /api/docs/public/user-guide?token=... (publico, valida JWT, rate limited)
"""
import io
import os
import time
import uuid
import hashlib
import threading
import asyncio
import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta

from auth_utils import get_current_user, get_jwt_secret, JWT_ALGORITHM
from rate_limiter import limiter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, ListFlowable, ListItem,
)
from reportlab.pdfgen import canvas

router = APIRouter(prefix="/docs", tags=["Documentacion"])

# Configuracion del share link publico
SHARE_LINK_DEFAULT_HOURS = int(os.environ.get("USER_GUIDE_SHARE_HOURS", "720"))  # 30d
SHARE_LINK_MAX_HOURS = int(os.environ.get("USER_GUIDE_SHARE_MAX_HOURS", "2160"))  # 90d
GUIDE_SHARE_SUB = "guide-share"

# SEC-002 fix (Feb 2026): cache in-memory del PDF por (prospect_name hash) para amortiguar DoS.
# TTL corto para permitir personalizacion cambiante y no bloatear memoria.
# Formato: {hash: (pdf_bytes, expires_at_ts)}
_PDF_CACHE: dict = {}
_PDF_CACHE_LOCK = threading.Lock()
PDF_CACHE_TTL_SEC = int(os.environ.get("USER_GUIDE_CACHE_TTL", "300"))  # 5 min
PDF_CACHE_MAX_ENTRIES = int(os.environ.get("USER_GUIDE_CACHE_MAX", "50"))


def _cache_key(prospect_name: str = None) -> str:
    key = (prospect_name or "").strip()[:80]
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _cache_get(prospect_name: str = None):
    now = time.time()
    key = _cache_key(prospect_name)
    with _PDF_CACHE_LOCK:
        entry = _PDF_CACHE.get(key)
        if entry and entry[1] > now:
            return entry[0]
        if entry:  # expirado
            _PDF_CACHE.pop(key, None)
    return None


def _cache_set(prospect_name: str, pdf_bytes: bytes):
    now = time.time()
    key = _cache_key(prospect_name)
    with _PDF_CACHE_LOCK:
        # Eviction simple: si supera el maximo, dropea el mas viejo
        if len(_PDF_CACHE) >= PDF_CACHE_MAX_ENTRIES:
            oldest = min(_PDF_CACHE.items(), key=lambda kv: kv[1][1])
            _PDF_CACHE.pop(oldest[0], None)
        _PDF_CACHE[key] = (pdf_bytes, now + PDF_CACHE_TTL_SEC)


def _build_or_cache(prospect_name: str = None) -> bytes:
    """Devuelve el PDF (desde cache si existe, sino lo genera y cachea)."""
    cached = _cache_get(prospect_name)
    if cached is not None:
        return cached
    pdf_bytes = _build_pdf(prospect_name=prospect_name)
    _cache_set(prospect_name, pdf_bytes)
    return pdf_bytes

# Paleta de colores Cortexia
BRAND_DARK = colors.HexColor("#1B2A49")
BRAND_TEAL = colors.HexColor("#13B8B0")
BRAND_PURPLE = colors.HexColor("#6D35D8")
BRAND_EMERALD = colors.HexColor("#059669")
BRAND_AMBER = colors.HexColor("#F59E0B")
TEXT_DARK = colors.HexColor("#0F172A")
TEXT_MUTED = colors.HexColor("#64748B")
BG_SOFT = colors.HexColor("#F8FAFC")


def _make_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", fontName="Helvetica-Bold", fontSize=42,
                              textColor=BRAND_DARK, alignment=TA_CENTER, leading=48, spaceAfter=8))
    styles.add(ParagraphStyle(name="CoverSubtitle", fontName="Helvetica", fontSize=18,
                              textColor=BRAND_TEAL, alignment=TA_CENTER, leading=22, spaceAfter=24))
    styles.add(ParagraphStyle(name="CoverTagline", fontName="Helvetica-Oblique", fontSize=13,
                              textColor=TEXT_MUTED, alignment=TA_CENTER, leading=18, spaceAfter=40))
    styles.add(ParagraphStyle(name="H1", fontName="Helvetica-Bold", fontSize=22,
                              textColor=BRAND_DARK, leading=28, spaceBefore=8, spaceAfter=10))
    styles.add(ParagraphStyle(name="H2", fontName="Helvetica-Bold", fontSize=15,
                              textColor=BRAND_PURPLE, leading=19, spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle(name="H3", fontName="Helvetica-Bold", fontSize=12,
                              textColor=BRAND_DARK, leading=16, spaceBefore=10, spaceAfter=4))
    styles.add(ParagraphStyle(name="Body", fontName="Helvetica", fontSize=10.5,
                              textColor=TEXT_DARK, leading=15, alignment=TA_JUSTIFY, spaceAfter=6))
    styles.add(ParagraphStyle(name="BulletCX", fontName="Helvetica", fontSize=10.5,
                              textColor=TEXT_DARK, leading=15, leftIndent=14, bulletIndent=4, spaceAfter=3))
    styles.add(ParagraphStyle(name="Highlight", fontName="Helvetica-Oblique", fontSize=10.5,
                              textColor=TEXT_MUTED, leading=15, alignment=TA_LEFT, spaceAfter=6))
    styles.add(ParagraphStyle(name="TocItem", fontName="Helvetica", fontSize=11,
                              textColor=TEXT_DARK, leading=18, leftIndent=0))
    styles.add(ParagraphStyle(name="RoleBadge", fontName="Helvetica-Bold", fontSize=9,
                              textColor=colors.white, alignment=TA_CENTER, leading=11))
    return styles


def _draw_page_frame(canv: canvas.Canvas, doc):
    """Dibuja header/footer minimalista en cada pagina no-cover."""
    canv.saveState()
    page_num = canv.getPageNumber()
    if page_num == 1:
        canv.restoreState()
        return

    w, h = A4
    # Header line
    canv.setStrokeColor(BRAND_TEAL)
    canv.setLineWidth(2)
    canv.line(2 * cm, h - 1.6 * cm, w - 2 * cm, h - 1.6 * cm)
    canv.setFont("Helvetica-Bold", 9)
    canv.setFillColor(BRAND_DARK)
    canv.drawString(2 * cm, h - 1.35 * cm, "Cortexia Optical")
    canv.setFont("Helvetica", 9)
    canv.setFillColor(TEXT_MUTED)
    canv.drawRightString(w - 2 * cm, h - 1.35 * cm, "Guia de Usuario para Opticas")

    # Footer
    canv.setStrokeColor(colors.HexColor("#E2E8F0"))
    canv.setLineWidth(0.5)
    canv.line(2 * cm, 1.5 * cm, w - 2 * cm, 1.5 * cm)
    canv.setFont("Helvetica", 8)
    canv.setFillColor(TEXT_MUTED)
    canv.drawString(2 * cm, 1.1 * cm, f"cortexiaoptical.com  |  info@cortexiagt.com")
    canv.drawRightString(w - 2 * cm, 1.1 * cm, f"Pagina {page_num}")
    canv.restoreState()


def _cover_page(story, styles, prospect_name: str = None):
    story.append(Spacer(1, 5.5 * cm))
    story.append(Paragraph("CORTEXIA<br/>OPTICAL", styles["CoverTitle"]))
    story.append(Paragraph("Guia de Usuario para Opticas", styles["CoverSubtitle"]))
    story.append(Paragraph(
        "El SaaS que digitaliza la operacion completa de tu optica<br/>"
        "en Guatemala, Latinoamerica y el mundo hispano.",
        styles["CoverTagline"]
    ))

    # Marca personalizada del prospecto (opcional)
    if prospect_name:
        safe_name = _escape_prospect(prospect_name)
        stamp_data = [[Paragraph(
            f"<font size='10' color='#FFFFFF'>PREPARADA ESPECIALMENTE PARA</font><br/>"
            f"<font size='18' color='#FFFFFF'><b>{safe_name}</b></font>",
            ParagraphStyle("stamp", alignment=TA_CENTER, textColor=colors.white, leading=22)
        )]]
        stamp = Table(stamp_data, colWidths=[15 * cm])
        stamp.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BRAND_PURPLE),
            ("LEFTPADDING", (0, 0), (-1, -1), 18),
            ("RIGHTPADDING", (0, 0), (-1, -1), 18),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(stamp)
        story.append(Spacer(1, 20))

    # Callout box "Para quien es esta guia"
    callout_data = [[Paragraph(
        "<b>Esta guia esta pensada para:</b><br/><br/>"
        "• <b>Administradores</b> de la optica que gestionan todo el negocio<br/>"
        "• <b>Vendedores</b> que atienden a pacientes en el mostrador<br/>"
        "• <b>Optometristas / Doctores</b> que hacen consultas y recetas<br/><br/>"
        "Cada rol tiene acceso solo a las funciones que necesita.",
        styles["Body"]
    )]]
    tbl = Table(callout_data, colWidths=[15 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG_SOFT),
        ("BOX", (0, 0), (-1, -1), 1, BRAND_TEAL),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 2 * cm if prospect_name else 4 * cm))
    story.append(Paragraph(
        f"<font color='#64748B'>Documento generado el {datetime.now().strftime('%d de %B, %Y')}</font>",
        ParagraphStyle("date", fontSize=9, alignment=TA_CENTER, textColor=TEXT_MUTED)
    ))
    story.append(PageBreak())


def _toc(story, styles):
    story.append(Paragraph("Contenido", styles["H1"]))
    story.append(Spacer(1, 6))
    items = [
        ("1", "Introduccion a Cortexia Optical", "4"),
        ("2", "Antes de empezar: Primer ingreso", "5"),
        ("3", "Guia para el Administrador", "6"),
        ("3.1", "Configuracion inicial de la optica", "6"),
        ("3.2", "Gestion de sucursales y equipo", "6"),
        ("3.3", "Inventario y proveedores", "7"),
        ("3.4", "Caja y finanzas", "8"),
        ("3.5", "Reportes y auditoria", "10"),
        ("3.6", "Seguridad y sesiones activas", "11"),
        ("3.7", "Mi Plan, suscripcion y cobros", "12"),
        ("4", "Guia para el Vendedor", "13"),
        ("4.1", "Registro de pacientes", "13"),
        ("4.2", "Cotizaciones y ventas", "14"),
        ("4.3", "Manejo de caja diaria", "15"),
        ("4.4", "Agenda y citas", "16"),
        ("5", "Guia para el Doctor / Optometrista", "17"),
        ("5.1", "Consultas oftalmologicas", "17"),
        ("5.2", "Recetas de anteojos, contacto y medicas", "18"),
        ("5.3", "Historial clinico del paciente", "19"),
        ("6", "Modulo especial: Jornadas", "20"),
        ("7", "Buenas practicas y consejos", "21"),
        ("8", "Soporte y contacto", "22"),
    ]
    rows = []
    for num, title, page in items:
        indent = 0 if "." not in num else 20
        rows.append([
            Paragraph(f"<b>{num}</b>", ParagraphStyle("n", fontSize=10, textColor=BRAND_TEAL, leftIndent=indent)),
            Paragraph(title, ParagraphStyle("t", fontSize=10.5, textColor=TEXT_DARK, leftIndent=indent)),
            Paragraph(f"<font color='#94A3B8'>{page}</font>", ParagraphStyle("p", fontSize=10, alignment=2))
        ])
    t = Table(rows, colWidths=[1.2 * cm, 13.5 * cm, 1.5 * cm])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(t)
    story.append(PageBreak())


def _role_header(story, styles, role_name, tagline, color):
    """Header visual grande para inicio de seccion por rol."""
    data = [[Paragraph(
        f"<font size='11' color='#FFFFFF'>{role_name.upper()}</font><br/>"
        f"<font size='16' color='#FFFFFF'><b>Guia paso a paso</b></font><br/>"
        f"<font size='10' color='#FFFFFF'>{tagline}</font>",
        ParagraphStyle("rh", textColor=colors.white)
    )]]
    t = Table(data, colWidths=[16 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("LEFTPADDING", (0, 0), (-1, -1), 22),
        ("RIGHTPADDING", (0, 0), (-1, -1), 22),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))


def _bullets(items, styles):
    """Genera lista de bullets estilizada."""
    return ListFlowable(
        [ListItem(Paragraph(t, styles["Body"]), leftIndent=12) for t in items],
        bulletType='bullet', start='•', leftIndent=14, bulletColor=BRAND_TEAL,
    )


def _tip_box(text, styles, color=BRAND_AMBER, title="Tip"):
    data = [[Paragraph(f"<b>{title}:</b> {text}", styles["Body"])]]
    t = Table(data, colWidths=[15 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFBEB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBEFORE", (0, 0), (0, 0), 3, color),
    ]))
    return t


def _intro(story, styles):
    story.append(Paragraph("1. Introduccion a Cortexia Optical", styles["H1"]))
    story.append(Paragraph(
        "<b>Cortexia Optical</b> es una plataforma SaaS diseñada especificamente "
        "para opticas latinoamericanas. Digitaliza toda la operacion — desde el registro "
        "del paciente hasta la venta, pasando por consultas oftalmologicas, inventario, "
        "recetas y cobranza — en una sola interfaz clara y facil de usar.",
        styles["Body"]))
    story.append(Paragraph("Que resuelve", styles["H2"]))
    story.append(_bullets([
        "<b>Papel:</b> reemplaza los cuadernos y hojas sueltas donde se anotan pacientes, recetas y ventas.",
        "<b>Perdida de datos:</b> historial clinico completo respaldado en la nube.",
        "<b>Control:</b> tu equipo trabaja solo en lo que le corresponde — sin sobresaturar.",
        "<b>Errores en ventas:</b> descuento de stock automatico, calculo de impuestos, multi-pago.",
        "<b>Seguimiento:</b> agenda automatica de proximas consultas + recordatorios por WhatsApp.",
    ], styles))
    story.append(Paragraph("Modulos principales", styles["H2"]))
    modules = [
        ["Pacientes", "Registro completo, foto, DPI, alergias, historial familiar"],
        ["Consultas", "Anamnesis, refraccion, hallazgos, plan terapeutico"],
        ["Recetas", "Lentes graduados + medicamentos, PDF, envio WhatsApp"],
        ["Inventario", "Armazones, lentes, accesorios. Alertas de stock bajo"],
        ["Punto de Venta", "Multi-pago, ticket PDF, descuento stock, comisiones"],
        ["Caja", "Apertura/cierre diario, control de efectivo por sucursal"],
        ["Cotizaciones", "Envio por email/WhatsApp, expiracion, conversion a venta"],
        ["Cuentas por Cobrar", "Seguimiento de saldos pendientes con recordatorios"],
        ["Cuentas por Pagar", "Egresos a credito con abonos parciales y avisos de vencimiento"],
        ["Estado de Resultados", "P&L base caja: ingresos, egresos y utilidad neta exportable"],
        ["Agenda", "Citas con recordatorio automatico, proxima cita post-consulta"],
        ["Jornadas", "Modulo para brigadas medicas y eventos externos"],
    ]
    tbl = Table(
        [[Paragraph(f"<b>{m[0]}</b>", styles["Body"]), Paragraph(m[1], styles["Body"])] for m in modules],
        colWidths=[3.5 * cm, 12.5 * cm]
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), BG_SOFT),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)
    story.append(PageBreak())


def _first_time(story, styles):
    story.append(Paragraph("2. Antes de empezar: Primer ingreso", styles["H1"]))
    story.append(Paragraph(
        "Recibiste un correo con las credenciales de acceso. Sigue estos pasos:",
        styles["Body"]))
    steps = [
        "Abre <b>cortexiaoptical.com</b> en Chrome, Firefox, Safari o Edge (movil o desktop).",
        "Ingresa tu correo y contraseña temporal.",
        "El sistema te pedira <b>cambiar la contraseña</b> por seguridad.",
        "Vas a ver el <b>Onboarding</b> — 8 pasos para dejar todo listo en menos de 30 minutos. "
        "El <b>Paso 1</b> es <b>descargar esta Guia de usuarios</b> en PDF; tenla a mano mientras configuras tu optica.",
        "Puedes saltar pasos y retomarlos despues; el sistema lleva el progreso automaticamente.",
    ]
    story.append(_bullets(steps, styles))
    story.append(_tip_box(
        "Tienes 30 dias desde tu registro para hacer tu primer ingreso. "
        "Si no ingresas en ese plazo, la cuenta se desactivara automaticamente y "
        "tendras que pedir una nueva contraseña al equipo Cortexia.",
        styles, color=BRAND_AMBER, title="Importante"
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Requisitos tecnicos", styles["H3"]))
    story.append(_bullets([
        "<b>Conexion a internet</b> estable (funciona con 4G).",
        "<b>Navegador moderno</b>: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+.",
        "Impresora opcional para tickets — el sistema tambien puede generar PDF para enviar por WhatsApp.",
    ], styles))
    story.append(PageBreak())


def _admin_section(story, styles):
    _role_header(story, styles, "Administrador",
                 "Control total del negocio: equipo, planes, inventario, finanzas y reportes.",
                 BRAND_DARK)
    story.append(Paragraph("3.1 Configuracion inicial de la optica", styles["H2"]))
    story.append(Paragraph(
        "Es lo primero que debes hacer. Ve a <b>Configuracion</b> en el menu lateral.",
        styles["Body"]))
    story.append(_bullets([
        "<b>Datos de la empresa</b>: nombre comercial, NIT, direccion, telefono, correo.",
        "<b>Logo</b>: sube tu logo (PNG/JPG max 5MB). Aparecera en PDFs, tickets, recetas y cotizaciones.",
        "<b>Moneda</b>: por defecto Q (quetzales). Cambiala segun tu pais.",
        "<b>IVA</b>: default 12% (Guatemala). Editable segun regimen fiscal.",
    ], styles))

    story.append(Paragraph("3.2 Gestion de sucursales y equipo", styles["H2"]))
    story.append(Paragraph(
        "En <b>Configuracion → Sucursales</b> puedes crear las ubicaciones fisicas de tu optica.",
        styles["Body"]))
    story.append(_bullets([
        "Cada sucursal tiene su propio inventario y caja.",
        "Los usuarios se pueden asignar a una sucursal especifica.",
        "El plan basico permite <b>1 sucursal</b>; planes superiores hasta 10+.",
    ], styles))
    story.append(Paragraph("<b>Crear usuarios del equipo</b>:", styles["H3"]))
    story.append(_bullets([
        "Ve a <b>Configuracion → Usuarios</b>.",
        "Click en <b>Nuevo usuario</b>.",
        "Selecciona el rol: <b>Vendedor</b> o <b>Doctor</b>.",
        "Asigna sucursal (opcional).",
        "Establece contraseña temporal — el usuario la cambiara en su primer ingreso.",
    ], styles))
    story.append(_tip_box(
        "Los admins <b>no pueden</b> crear otros admins ni superadmins. "
        "Esto es una regla de seguridad para evitar escaladas de privilegios.",
        styles, color=BRAND_TEAL, title="Seguridad"
    ))

    story.append(PageBreak())
    story.append(Paragraph("3.3 Inventario y proveedores", styles["H2"]))
    story.append(Paragraph(
        "Ve a <b>Inventario</b> en el menu lateral. Aqui gestionas armazones, "
        "lentes, accesorios y consumibles.",
        styles["Body"]))
    story.append(Paragraph("<b>Registrar un producto nuevo</b>:", styles["H3"]))
    story.append(_bullets([
        "Click en <b>Nuevo producto</b>.",
        "SKU (opcional, se genera automatico si lo dejas vacio).",
        "Nombre, marca, categoria (armazon / lente / accesorio).",
        "<b>Costo</b> (lo que te cuesta a ti) y <b>Precio</b> (a lo que lo vendes).",
        "Stock actual y stock minimo (alerta cuando llegue a este umbral).",
        "Marca <b>Proveedor Externo</b> si es un producto fabricado en laboratorio externo — no dispara alertas de stock.",
    ], styles))
    story.append(Paragraph("<b>Alertas de stock bajo</b>", styles["H3"]))
    story.append(Paragraph(
        "El dashboard te muestra automaticamente los productos por debajo del stock minimo. "
        "Puedes exportarlos a Excel para el proveedor.",
        styles["Body"]))
    story.append(Paragraph("<b>Proveedores</b>", styles["H3"]))
    story.append(Paragraph(
        "En <b>Proveedores</b> registras a quien les compras (nombre, contacto, telefono, WhatsApp). "
        "Un mismo proveedor se puede vincular <b>tanto a productos del inventario</b> (para saber de "
        "donde vinieron) <b>como a los egresos / compras del modulo Finanzas</b>. Asi el sistema "
        "totaliza cuanto le compras a cada proveedor y cuanto le debes.",
        styles["Body"]))

    story.append(PageBreak())
    story.append(Paragraph("3.4 Caja y finanzas", styles["H2"]))
    story.append(Paragraph(
        "<b>Caja diaria</b>: el vendedor abre caja al iniciar el turno con un monto en efectivo. "
        "Durante el dia se registran ventas y egresos, y al cerrar el sistema calcula si sobra o "
        "falta dinero. Ve a <b>Caja</b>.",
        styles["Body"]))
    story.append(Paragraph("<b>El arqueo integra los egresos</b>", styles["H3"]))
    story.append(_bullets([
        "El <b>efectivo esperado</b> = fondo inicial + efectivo recaudado − <b>egresos en efectivo</b> del turno.",
        "Solo los egresos pagados en <b>efectivo</b> restan del efectivo esperado; tarjeta, "
        "transferencia o cheque no afectan el conteo de billetes.",
        "El <b>resumen del turno en vivo</b> muestra en todo momento lo recaudado, los egresos y el "
        "efectivo esperado sin necesidad de cerrar la caja.",
    ], styles))
    story.append(Paragraph("<b>Registrar un egreso desde Caja</b>", styles["H3"]))
    story.append(_bullets([
        "Con el boton <b>Registrar egreso</b> (en la misma pantalla de Caja) anotas un gasto sin salir del turno.",
        "Eliges la <b>categoria</b>, el <b>metodo de pago</b> y, cuando aplica, el <b>proveedor</b>.",
        "Queda reflejado al instante en el resumen del turno y en el arqueo de cierre.",
    ], styles))
    story.append(Paragraph("<b>Imprimir y exportar el turno</b>", styles["H3"]))
    story.append(_bullets([
        "<b>Imprimir cierre (PDF)</b>: arqueo completo con el detalle de egresos linea por linea.",
        "<b>Descargar egresos del turno (Excel)</b>: todos los gastos del turno para tu contabilidad.",
    ], styles))
    story.append(PageBreak())

    story.append(Paragraph("3.4 Caja y finanzas (continuacion)", styles["H2"]))
    story.append(Paragraph(
        "El <b>modulo Finanzas</b> (solo admin) concentra ingresos por sucursal y metodo de pago, "
        "gastos operativos, utilidad, tendencia de ventas y todo lo relacionado a egresos.",
        styles["Body"]))
    story.append(Paragraph("<b>Egresos con proveedor</b>", styles["H3"]))
    story.append(Paragraph(
        "Cada egreso puede llevar un <b>proveedor</b> (obligatorio en la categoria <b>Proveedores</b>), "
        "lo que permite filtrar y totalizar cuanto le compras a cada uno.",
        styles["Body"]))
    story.append(Paragraph("<b>Egresos a credito y Cuentas por Pagar</b>", styles["H3"]))
    story.append(_bullets([
        "Un egreso a <b>credito</b> deja un saldo que aparece en <b>Cuentas por Pagar</b>.",
        "Ahi registras <b>abonos parciales</b> y el sistema avisa de <b>vencimientos</b> (vencidos y por vencer).",
    ], styles))
    story.append(Paragraph("<b>Anular un movimiento</b>", styles["H3"]))
    story.append(Paragraph(
        "Si un ingreso o egreso quedo mal, <b>anulalo con un motivo</b> (no se borra): queda tachado y "
        "auditable y <b>deja de contar</b> en totales, reportes, Cuentas por Pagar y caja. Lo puede anular "
        "el <b>administrador</b> o <b>quien lo registro</b>.",
        styles["Body"]))
    story.append(Paragraph("<b>Estado de Resultados (P&amp;L)</b>", styles["H3"]))
    story.append(Paragraph(
        "En pantalla y exportable a <b>Excel y PDF</b>: ingresos y egresos por categoria y la <b>utilidad "
        "neta</b> del periodo. Usa <b>base caja</b> (los egresos a credito cuentan solo por lo ya abonado), "
        "a diferencia de la <b>utilidad bruta</b> Precio − Costo, que mide margen y no flujo de caja.",
        styles["Body"]))
    story.append(Paragraph("<b>Arrastre y Cuentas por Cobrar</b>", styles["H3"]))
    story.append(Paragraph(
        "Los saldos de ventas parciales van a <b>Cuentas por Cobrar</b> (con recordatorios por WhatsApp). "
        "Cobrar y pagar <b>se arrastran entre periodos</b> hasta saldarse o anularse; cada abono baja el saldo.",
        styles["Body"]))

    story.append(PageBreak())
    story.append(Paragraph("3.5 Reportes y auditoria", styles["H2"]))
    story.append(Paragraph(
        "En <b>Reportes</b> tienes reportes prediseñados:",
        styles["Body"]))
    story.append(_bullets([
        "<b>Ventas por rango de fechas</b> con desglose por vendedor.",
        "<b>Productos mas vendidos</b>: top 20 con % del total.",
        "<b>Pacientes nuevos vs recurrentes</b>.",
        "<b>Comisiones por vendedor</b> para pago quincenal/mensual.",
        "<b>Historico de precios</b>: cambios de precio de cada producto.",
    ], styles))
    story.append(Paragraph("<b>Todos exportables a Excel y PDF.</b>", styles["Body"]))
    story.append(Paragraph("<b>Reportes del modulo Finanzas</b>", styles["H3"]))
    story.append(_bullets([
        "<b>Compras por proveedor</b> (Excel): total comprado a cada proveedor en el periodo.",
        "<b>Egresos por rango de fechas</b> (Excel): todos los gastos entre dos fechas, por categoria y metodo.",
        "<b>Estado de Resultados</b> (Excel y PDF): utilidad neta en base caja del periodo.",
    ], styles))

    story.append(Paragraph("Auditoria", styles["H3"]))
    story.append(Paragraph(
        "En <b>Auditoria</b> ves cada accion del equipo: quien creo un paciente, "
        "quien modifico un precio, quien cerro caja, quien cambio permisos y "
        "<b>quien anulo un movimiento financiero y con que motivo</b>. "
        "Todo con fecha, hora, IP y usuario. Ideal para investigar discrepancias.",
        styles["Body"]))

    story.append(PageBreak())
    story.append(Paragraph("3.6 Seguridad y sesiones activas", styles["H2"]))
    story.append(Paragraph(
        "En <b>Configuracion → Sesiones Activas</b> puedes ver todos los dispositivos "
        "donde alguien de tu equipo esta logueado ahora mismo — nombre, dispositivo, IP, "
        "ultima actividad. Con un click puedes cerrar sesiones sospechosas.",
        styles["Body"]))
    story.append(_tip_box(
        "Si un empleado renuncia o pierde su celular, entra a Sesiones Activas y "
        "revoca todas sus sesiones para asegurar que no tenga acceso.",
        styles, color=BRAND_PURPLE, title="Consejo de seguridad"
    ))
    story.append(Paragraph("<b>Cambiar tu propia contraseña</b>", styles["H3"]))
    story.append(_bullets([
        "Configuracion → Cambiar contraseña.",
        "Debe tener 8+ caracteres, mayus/minus/numero.",
        "Al cambiarla, TODAS las sesiones se cierran automaticamente por seguridad.",
    ], styles))
    story.append(PageBreak())

    story.append(Paragraph("3.7 Mi Plan, suscripcion y cobros", styles["H2"]))
    story.append(Paragraph(
        "En <b>Mi Plan</b> (menu lateral) ves tu plan actual, tu uso y limites (pacientes, "
        "usuarios, sucursales) y el costo de tu membresia. La membresia de Cortexia se cobra "
        "en <b>USD</b>; la operacion de tu optica sigue en quetzales.",
        styles["Body"]))
    story.append(Paragraph("<b>Suscribirte o cambiar de plan</b>", styles["H3"]))
    story.append(_bullets([
        "Elige el plan y el ciclo (<b>mensual</b> o <b>anual</b>) y confirma.",
        "La <b>primera vez</b> pasas por el <b>checkout seguro de Stripe</b> (tarjeta). Al completarlo, "
        "tu plan queda activo automaticamente.",
        "Si <b>ya tienes una suscripcion activa</b> y cambias de plan, el cambio es <b>inmediato y con "
        "prorrateo</b>: se acredita lo no usado del plan anterior y solo se cobra la diferencia en tu "
        "proxima factura, <b>sin volver a pasar por el checkout</b>.",
    ], styles))
    story.append(Paragraph("<b>Gestionar tu suscripcion (Portal de Stripe)</b>", styles["H3"]))
    story.append(_bullets([
        "El boton <b>Gestionar suscripcion</b> abre el Portal de Stripe.",
        "Ahi puedes <b>actualizar tu tarjeta</b>, ver y descargar tus <b>facturas</b> y <b>cancelar</b> la suscripcion.",
        "El <b>cambio de plan NO se hace en el portal</b>: se hace desde <b>Mi Plan</b> en Cortexia.",
    ], styles))
    story.append(Paragraph("<b>Que pasa si un pago falla</b>", styles["H3"]))
    story.append(Paragraph(
        "Cortexia te da un <b>periodo de gracia</b> antes de suspender el acceso, para que nunca "
        "pierdas la operacion por un cobro fallido de un dia:",
        styles["Body"]))
    story.append(_bullets([
        "<b>Dia 0</b>: te avisamos (en la app y por correo) e inicia una <b>gracia de 3 dias</b>. Tu optica "
        "<b>sigue operando normal</b>, con un aviso visible.",
        "<b>Dias 1-2</b>: recordatorios para que regularices tu pago.",
        "<b>Dia 3 sin pago</b>: la cuenta se <b>suspende</b> (muro de pago). El <b>administrador</b> solo ve la "
        "pantalla para pagar o actualizar su tarjeta; el resto del equipo ve <i>\"cuenta suspendida, "
        "contacta a tu administrador\"</i>.",
        "<b>Reactivacion automatica</b>: en cuanto el pago se confirma, tu optica recupera el acceso "
        "completo sin que tengas que hacer nada mas.",
    ], styles))
    story.append(_tip_box(
        "Para evitar suspensiones, manten tu tarjeta al dia desde <b>Gestionar suscripcion</b>. "
        "Si esta por vencer, actualizala antes del proximo cobro. Las cuentas marcadas como "
        "<b>cortesia</b> estan exentas de cobro y de suspension.",
        styles, color=BRAND_AMBER, title="Evita suspensiones"
    ))
    story.append(PageBreak())


def _vendor_section(story, styles):
    _role_header(story, styles, "Vendedor",
                 "Atencion al paciente en el mostrador: registro, cotizaciones, ventas y caja.",
                 BRAND_EMERALD)

    story.append(Paragraph("4.1 Registro de pacientes", styles["H2"]))
    story.append(Paragraph(
        "Cuando llega un paciente nuevo:",
        styles["Body"]))
    story.append(_bullets([
        "Ve a <b>Pacientes</b> → <b>Nuevo paciente</b>.",
        "Datos basicos: nombre, apellido, DPI/pasaporte, fecha de nacimiento, sexo.",
        "Contacto: telefono, WhatsApp (importante para recordatorios), correo.",
        "Direccion y ocupacion (opcional).",
        "<b>Foto</b>: puedes tomarla con la webcam o subirla desde galeria.",
        "Alergias, medicamentos actuales, antecedentes familiares (opcional pero recomendado).",
    ], styles))
    story.append(_tip_box(
        "Antes de crear un paciente, usa la <b>busqueda</b> por DPI o telefono. "
        "El sistema detecta duplicados y te avisa si el paciente ya existe.",
        styles, color=BRAND_EMERALD, title="Evita duplicados"
    ))

    story.append(PageBreak())
    story.append(Paragraph("4.2 Cotizaciones y ventas", styles["H2"]))
    story.append(Paragraph("<b>Hacer una cotizacion</b> (paso previo a la venta):", styles["H3"]))
    story.append(_bullets([
        "Ve a <b>Cotizaciones</b> → <b>Nueva</b>.",
        "Selecciona el paciente (o crealo en el momento).",
        "Agrega productos del inventario con cantidad.",
        "Aplica descuentos si el admin te lo autoriza.",
        "El sistema calcula subtotal, IVA y total.",
        "<b>Envio</b>: descarga PDF o mandalo por WhatsApp/correo directamente.",
    ], styles))
    story.append(Paragraph("<b>Convertir cotizacion en venta</b>", styles["H3"]))
    story.append(Paragraph(
        "Cuando el paciente confirma, abre la cotizacion y click en <b>Convertir a venta</b>. "
        "El sistema mantiene los mismos productos y descuentos.",
        styles["Body"]))
    story.append(Paragraph("<b>Registrar venta directa (sin cotizacion previa)</b>", styles["H3"]))
    story.append(_bullets([
        "Ve a <b>Punto de Venta</b>.",
        "Busca el paciente o crealo.",
        "Agrega productos por SKU o buscando por nombre.",
        "Elige metodo(s) de pago — puedes combinar efectivo + tarjeta + transferencia.",
        "Si el pago es parcial, el saldo pendiente va a <b>Cuentas por cobrar</b>.",
        "El sistema descuenta el stock automaticamente e imprime el ticket.",
        "Desde el detalle de la venta puedes <b>Imprimir el recibo</b> (PDF) o "
        "<b>Compartirlo por WhatsApp</b> al paciente con un click.",
    ], styles))

    story.append(PageBreak())
    story.append(Paragraph("4.3 Manejo de caja diaria", styles["H2"]))
    story.append(Paragraph("<b>Al iniciar tu turno</b>:", styles["H3"]))
    story.append(_bullets([
        "Ve a <b>Caja</b> → <b>Abrir caja</b>.",
        "Ingresa el monto inicial en efectivo con el que empiezas.",
        "El sistema registra tu apertura con fecha y hora.",
    ], styles))
    story.append(Paragraph("<b>Durante el dia</b>:", styles["H3"]))
    story.append(_bullets([
        "Cada venta se registra automaticamente en tu caja.",
        "Para sacar dinero por un gasto usa el boton <b>Registrar egreso</b> desde la misma pantalla "
        "de Caja (eliges el metodo de pago y, si aplica, el proveedor).",
        "El <b>resumen del turno en vivo</b> te muestra lo recaudado, los egresos y el <b>efectivo esperado</b> "
        "sin tener que cerrar la caja.",
        "Solo los egresos <b>en efectivo</b> restan del efectivo esperado; tarjeta, transferencia o cheque no.",
    ], styles))
    story.append(Paragraph("<b>Al cerrar tu turno</b>:", styles["H3"]))
    story.append(_bullets([
        "Cuenta el efectivo real que tienes en la caja.",
        "Ve a <b>Caja</b> → <b>Cerrar caja</b> e ingresa el monto real; el sistema te muestra si sobra o falta.",
        "Usa <b>Imprimir cierre (PDF)</b> para el arqueo (incluye el detalle de egresos linea por linea).",
        "Con <b>Descargar egresos del turno (Excel)</b> bajas todos los gastos del turno.",
    ], styles))

    story.append(PageBreak())
    story.append(Paragraph("4.4 Agenda y citas", styles["H2"]))
    story.append(Paragraph(
        "En <b>Agenda</b> ves todas las citas del dia por sucursal y por doctor. "
        "Para agendar una cita:",
        styles["Body"]))
    story.append(_bullets([
        "Click en el horario disponible del calendario.",
        "Selecciona paciente (o crealo).",
        "Motivo de consulta y notas.",
        "Confirma. El sistema envia un WhatsApp de recordatorio 1 dia antes.",
    ], styles))
    story.append(Paragraph("<b>Widget 'Recordatorios mañana'</b>", styles["H3"]))
    story.append(Paragraph(
        "En la parte superior de la Agenda ves un widget con las citas de mañana. "
        "Util para confirmar por WhatsApp al final del dia.",
        styles["Body"]))
    story.append(PageBreak())


def _doctor_section(story, styles):
    _role_header(story, styles, "Doctor / Optometrista",
                 "Consultas oftalmologicas, recetas de lentes y medicamentos, historial clinico.",
                 BRAND_PURPLE)

    story.append(Paragraph("5.1 Consultas oftalmologicas", styles["H2"]))
    story.append(Paragraph(
        "Cuando un paciente entra al consultorio, ve a <b>Consultas</b> → <b>Nueva consulta</b>.",
        styles["Body"]))
    story.append(Paragraph("<b>Secciones de la consulta</b>:", styles["H3"]))
    story.append(_bullets([
        "<b>Motivo</b>: lo que trae al paciente (dolor, borroso, control anual).",
        "<b>Anamnesis</b>: historia clinica breve, medicamentos, alergias.",
        "<b>Refraccion</b>: OD/OS esfera, cilindro, eje, adicion, DP, altura.",
        "<b>Examenes fisicos</b>: presion intraocular, fondo de ojo, motilidad, campimetria.",
        "<b>Diagnostico</b> con CIE-10 (autocompleta al escribir).",
        "<b>Plan terapeutico</b>: receta, controles, referencias.",
        "<b>Notas privadas</b>: solo tu las ves.",
    ], styles))
    story.append(_tip_box(
        "Al terminar la consulta el sistema te <b>propone agendar la proxima cita</b> automaticamente "
        "(por defecto en 6 meses). Puedes ajustarlo o dejarlo pendiente.",
        styles, color=BRAND_PURPLE, title="Nueva funcion"
    ))

    story.append(PageBreak())
    story.append(Paragraph("5.2 Recetas de anteojos, contacto y medicas", styles["H2"]))
    story.append(Paragraph("<b>Receta de lentes graduados</b>", styles["H3"]))
    story.append(_bullets([
        "Dentro de la consulta, click en <b>Receta de lentes</b>.",
        "Copia automaticamente los datos de refraccion.",
        "Especifica tipo de lente (monofocal, bifocal, progresivo), material, tratamientos.",
        "Firma digital (guardada una vez, se reutiliza).",
        "PDF generado con logo de la optica y colegiado.",
        "Envio directo por WhatsApp al paciente con un click.",
    ], styles))

    story.append(Paragraph("<b>Receta de lentes de contacto</b>", styles["H3"]))
    story.append(_bullets([
        "Pestaña <b>Lentes de Contacto</b> en Recetas: datos por ojo (<b>OD / OS</b>) con esfera, "
        "cilindro, eje, adicion, <b>diametro</b> y <b>curva base</b>.",
        "Marca, tipo de reemplazo y fecha de vencimiento del lente.",
        "PDF con logo y envio por WhatsApp; el sistema avisa cuando el lente esta por vencer.",
    ], styles))

    story.append(Paragraph("<b>Receta medica (medicamentos)</b>", styles["H3"]))
    story.append(_bullets([
        "Click en <b>Receta medica</b> dentro de la consulta.",
        "Agrega medicamento (autocompleta con base de datos comun).",
        "Especifica presentacion, dosis, frecuencia, duracion.",
        "El sistema tambien la exporta a PDF.",
    ], styles))

    story.append(PageBreak())
    story.append(Paragraph("5.3 Historial clinico del paciente", styles["H2"]))
    story.append(Paragraph(
        "Al abrir un paciente, tienes acceso completo a su historia:",
        styles["Body"]))
    story.append(_bullets([
        "Todas las consultas anteriores en orden cronologico.",
        "Grafica de evolucion de la refraccion en el tiempo.",
        "Recetas emitidas.",
        "Ventas realizadas (que lentes se ha comprado).",
        "Alergias y contraindicaciones destacadas.",
        "Fotos anexas (fondo de ojo, evolucion externa, etc.).",
    ], styles))
    story.append(_tip_box(
        "Puedes exportar la <b>historia clinica completa</b> del paciente a PDF "
        "para compartirla con otro especialista si el paciente lo autoriza.",
        styles, color=BRAND_TEAL, title="Continuidad de cuidado"
    ))
    story.append(PageBreak())


def _jornadas_section(story, styles):
    story.append(Paragraph("6. Modulo especial: Jornadas", styles["H1"]))
    story.append(Paragraph(
        "Las <b>Jornadas</b> son eventos externos temporales — brigadas medicas, "
        "campañas en escuelas, ferias, atenciones en municipios. Cortexia tiene un modulo "
        "dedicado que funciona como una <b>optica portatil</b>.",
        styles["Body"]))
    story.append(Paragraph("Que se puede hacer en una Jornada", styles["H2"]))
    story.append(_bullets([
        "Crear el evento con fechas, ubicacion y equipo asignado.",
        "<b>Caja propia</b> — separada de la sucursal principal.",
        "<b>Inventario propio</b>: traspaso desde una sucursal o consignacion via Excel.",
        "<b>POS aislado</b>: ventas rapidas sin descontar del stock principal.",
        "Registro de pacientes con etiqueta 'origen: Jornada X'.",
        "Consulta + receta encadenadas al vuelo desde el POS de Jornada.",
        "<b>Modo sin internet (offline)</b>: si te quedas sin señal, puedes seguir capturando "
        "pacientes; los datos se guardan cifrados en el dispositivo y se <b>sincronizan solos</b> "
        "al volver la conexion.",
        "<b>Liquidacion final</b>: reporte PDF/Excel con ventas, saldos, stock restante.",
    ], styles))
    story.append(_tip_box(
        "Al finalizar la jornada, el sistema genera automaticamente un reporte de liquidacion "
        "con todo lo vendido y el saldo pendiente por cobrar. Ideal para brigadas cientificas.",
        styles, color=BRAND_AMBER, title="Ideal para"
    ))
    story.append(_tip_box(
        "Un indicador en la barra superior te avisa cuando estas sin conexion y cuantos registros "
        "faltan por sincronizar. Busca señal antes de cerrar la jornada para no perder capturas.",
        styles, color=BRAND_TEAL, title="Modo offline"
    ))
    story.append(PageBreak())


def _best_practices(story, styles):
    story.append(Paragraph("7. Buenas practicas y consejos", styles["H1"]))
    tips = [
        ("Registra el paciente ANTES de la consulta",
         "Ahorra tiempo al doctor. El vendedor puede tomar datos basicos y foto mientras el paciente espera."),
        ("Usa el numero de WhatsApp real",
         "El sistema envia recordatorios de cita y de saldo pendiente por WhatsApp. Si el numero es incorrecto, no llegara."),
        ("Cierra caja todos los dias",
         "Aunque hayan sido pocas ventas. El cierre diario evita diferencias acumuladas."),
        ("No compartas tu contraseña",
         "Cada usuario debe tener la suya. Si alguien mas necesita entrar, creale un usuario aparte."),
        ("Revisa las alertas del dashboard",
         "Muestra stock bajo, saldos vencidos, cotizaciones por expirar. Actua sobre ellas."),
        ("Backup automatico",
         "Todos tus datos estan respaldados en la nube. No necesitas hacer nada."),
        ("Compartir la responsabilidad",
         "El admin puede delegar tareas creando roles con permisos especificos. No todo lo debe hacer el dueño."),
        ("Anula, no borres",
         "Si un ingreso o egreso quedo mal, anulalo con su motivo en vez de eliminarlo. Queda tachado y "
         "auditable y deja de contar en los totales; asi mantienes la trazabilidad."),
        ("Revisa Cuentas por Pagar y sus vencimientos",
         "Manten al dia los egresos a credito: registra los abonos y atiende los avisos de vencimiento "
         "para cuidar la relacion con tus proveedores."),
    ]
    for t, d in tips:
        story.append(Paragraph(f"<b>· {t}</b>", styles["Body"]))
        story.append(Paragraph(f"<font color='#64748B'>{d}</font>", styles["Body"]))
        story.append(Spacer(1, 6))
    story.append(PageBreak())


def _support(story, styles):
    story.append(Paragraph("8. Soporte y contacto", styles["H1"]))
    story.append(Paragraph(
        "El equipo de Cortexia esta disponible para ayudarte:",
        styles["Body"]))
    story.append(Spacer(1, 8))
    data = [
        ["Correo", "info@cortexiagt.com"],
        ["Web", "cortexiaoptical.com"],
        ["Soporte tecnico", "Desde la plataforma → Menu → Soporte → Crear ticket"],
        ["Horario", "Lunes a Viernes 8:00 - 18:00 (GT-6)"],
    ]
    t = Table([[Paragraph(f"<b>{a}</b>", styles["Body"]), Paragraph(b, styles["Body"])] for a, b in data],
              colWidths=[3.5 * cm, 12 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), BG_SOFT),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "<b>¿Encontraste un error o tienes una sugerencia?</b>",
        styles["H3"]))
    story.append(Paragraph(
        "Desde el mismo sistema puedes crear un ticket con categoria "
        "(<i>bug, sugerencia, ayuda, cobros</i>) y prioridad. "
        "Nuestro equipo responde en menos de 24h en dias habiles.",
        styles["Body"]))
    story.append(Spacer(1, 30))
    story.append(Paragraph(
        "<font color='#94A3B8' size='9'>Cortexia Optical © 2026 · Todos los derechos reservados.<br/>"
        "Este documento es propiedad intelectual de Cortexia Optical y se comparte "
        "unicamente con fines demostrativos y comerciales.</font>",
        ParagraphStyle("footer", alignment=TA_CENTER, fontSize=9, textColor=TEXT_MUTED)
    ))


def _escape_prospect(name: str) -> str:
    """Escapa HTML/reportlab-unsafe chars y limita longitud."""
    if not name:
        return ""
    s = str(name).strip()[:80]
    # Escape XML/HTML entities para prevenir inyeccion en el markup de reportlab
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s


def _safe_filename_prospect(name: str) -> str:
    """Sanitiza nombre para uso en filename."""
    if not name:
        return ""
    import re as _re
    s = _re.sub(r"[^\w\s\-]", "", str(name).strip())[:40]
    s = _re.sub(r"\s+", "-", s).lower()
    return s


def _build_pdf(prospect_name: str = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2.5 * cm, bottomMargin=2.2 * cm,
        title="Cortexia Optical - Guia de Usuario",
        author="Cortexia Optical",
    )
    styles = _make_styles()
    story = []
    _cover_page(story, styles, prospect_name=prospect_name)
    _toc(story, styles)
    _intro(story, styles)
    _first_time(story, styles)
    _admin_section(story, styles)
    _vendor_section(story, styles)
    _doctor_section(story, styles)
    _jornadas_section(story, styles)
    _best_practices(story, styles)
    _support(story, styles)
    doc.build(story, onFirstPage=_draw_page_frame, onLaterPages=_draw_page_frame)
    return buf.getvalue()


def _stream_pdf(pdf_bytes: bytes, prospect_name: str = None) -> StreamingResponse:
    date_str = datetime.now().strftime('%Y%m%d')
    slug = _safe_filename_prospect(prospect_name)
    filename = (
        f"cortexia-optical-guia-{slug}-{date_str}.pdf"
        if slug else f"cortexia-optical-guia-usuario-{date_str}.pdf"
    )
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        }
    )


@router.get("/user-guide.pdf")
@limiter.limit("30/minute")
async def user_guide_pdf(
    request: Request,
    prospect: str = Query(None, max_length=80),
    user: dict = Depends(get_current_user),
):
    """Genera y descarga la guia completa de usuario en PDF.

    Restringido a Admin de optica y Superadmin (uso comercial / onboarding).
    Query param opcional `prospect`: estampa el nombre del prospecto en la portada.
    Rate limit: 30/min por IP para prevenir DoS por generacion pesada.
    """
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Solo administradores pueden descargar la guia.")
    pdf_bytes = await asyncio.to_thread(_build_or_cache, prospect)
    return _stream_pdf(pdf_bytes, prospect_name=prospect)


class ShareLinkRequest(BaseModel):
    prospect_name: str = Field(..., min_length=1, max_length=80)
    expires_hours: int = Field(default=SHARE_LINK_DEFAULT_HOURS, ge=1, le=SHARE_LINK_MAX_HOURS)


@router.post("/share-link")
async def create_share_link(payload: ShareLinkRequest, user: dict = Depends(get_current_user)):
    """Genera un URL publico firmado para compartir la guia personalizada con un prospecto.

    Restringido a admin/superadmin. El JWT contiene el nombre del prospecto y la expiracion.
    SEC-003 fix (Feb 2026): quitamos user_id del payload (privacy) y agregamos jti unico
    (deja abierta la puerta a revocacion futura via denylist).
    """
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Solo administradores pueden generar links.")
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=payload.expires_hours)
    token_payload = {
        "sub": GUIDE_SHARE_SUB,
        "prospect": payload.prospect_name.strip()[:80],
        "iat": int(now.timestamp()),
        "exp": exp,
        "jti": str(uuid.uuid4()),
    }
    token = pyjwt.encode(token_payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)
    public_url_path = f"/api/docs/public/user-guide?token={token}"
    return {
        "path": public_url_path,
        "token": token,
        "expires_at": exp.isoformat(),
        "prospect_name": payload.prospect_name,
    }


@router.get("/public/user-guide")
@limiter.limit("10/minute")
async def public_user_guide(request: Request, token: str = Query(..., min_length=10, max_length=2048)):
    """Endpoint publico (sin auth) que valida un JWT firmado y sirve la guia personalizada.

    Diseñado para compartir con prospectos comerciales via WhatsApp/email.
    El token expira segun se configuro en /docs/share-link (default 30d).
    SEC-002 fix (Feb 2026): rate limit 10/min por IP + cache de PDF por prospect_name (TTL 5min)
    para prevenir DoS por generacion repetida de PDFs pesados.
    """
    try:
        decoded = pyjwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=410, detail="El enlace expiro. Solicita uno nuevo.")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Enlace invalido.")
    if decoded.get("sub") != GUIDE_SHARE_SUB:
        raise HTTPException(status_code=403, detail="Enlace invalido.")
    prospect = decoded.get("prospect")
    pdf_bytes = await asyncio.to_thread(_build_or_cache, prospect)
    # inline para preview en el navegador (mejor UX en WhatsApp Web)
    date_str = datetime.now().strftime('%Y%m%d')
    slug = _safe_filename_prospect(prospect)
    filename = (
        f"cortexia-optical-guia-{slug}-{date_str}.pdf"
        if slug else f"cortexia-optical-guia-usuario-{date_str}.pdf"
    )
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            "Cache-Control": "public, max-age=3600",
        }
    )
