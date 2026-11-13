"""Dibujo de recetas PDF por tipo (una receta por pagina, media carta).
- Recetas emitidas se dibujan desde su instantanea (reimprimir = mismos valores).
- Borradores/anuladas/sustituidas llevan marca de agua visible.
- OD = ojo derecho, OS = ojo izquierdo (campos internos oi_*)."""
import io
from typing import Optional
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors

from db import calculate_age
from rx_pdf_base import HALF_LETTER, get_logo_path, get_rx_style, draw_rx_header, draw_rx_footer

TITLES = {"eyeglass": "RECETA DE ANTEOJOS", "contact": "RECETA LENTES DE CONTACTO",
          "scleral": "RECETA LENTES ESCLERALES", "medical": "RECETA MEDICA"}
WATERMARKS = {"borrador": "BORRADOR \u00b7 SIN VALIDEZ", "anulada": "ANULADA \u00b7 SIN VALIDEZ",
              "sustituida": "SUSTITUIDA \u00b7 SIN VALIDEZ"}
EYES = (("od", "OD", "#1D4ED8"), ("oi", "OS", "#15803D"))


def effective_rx(rx: dict) -> dict:
    snap = rx.get("snapshot") or {}
    return {**rx, **(snap.get("values") or {})} if rx.get("status") in ("emitida", "sustituida") and snap else rx


def fp(v, plano=False):
    if v is None or str(v).strip() == "":
        return "-"
    try:
        n = float(str(v).replace(",", "."))
    except ValueError:
        return str(v)
    if n == 0:
        return "PL" if plano else "0.00"
    return f"{n:+.2f}"


def fn(v):
    if v is None or str(v).strip() == "":
        return "-"
    try:
        n = float(str(v).replace(",", "."))
        return f"{n:.2f}".rstrip("0").rstrip(".") if n != int(n) else f"{int(n)}"
    except ValueError:
        return str(v)


def fa(v):
    if v is None or str(v).strip() == "":
        return "-"
    try:
        return f"{int(float(v))}\u00b0"
    except ValueError:
        return str(v)


def fprism(p, b):
    if p is None or str(p).strip() == "":
        return "-"
    return f"{fn(p)} {(b or '').upper()}".strip()


def _bold(font):
    return f"{font}-Bold" if font != "Courier" else font


def _date(v):
    s = (v or "")[:10]
    return f"{s[8:10]}/{s[5:7]}/{s[0:4]}" if len(s) == 10 else s


def _wrap(c, text, font, size, max_w):
    words, lines, cur = str(text or "").split(), [], ""
    for wd in words:
        t = f"{cur} {wd}".strip()
        if c.stringWidth(t, font, size) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


class Pen:
    """Cursor vertical con salto controlado para no invadir el pie de firma."""
    def __init__(self, c, w, y, font):
        self.c, self.w, self.y, self.font = c, w, y, font
        self.floor = 1.12 * inch

    def label(self, label, value, size=7.5, max_lines=2, x=0.4 * inch):
        if value in (None, "") or self.y < self.floor:
            return
        c = self.c
        lines = _wrap(c, value, self.font, size, self.w - x - 0.4 * inch - c.stringWidth(f"{label}: ", _bold(self.font), size))[:max_lines]
        if not lines:
            return
        c.setFont(_bold(self.font), size)
        c.drawString(x, self.y, f"{label}:")
        lx = x + c.stringWidth(f"{label}: ", _bold(self.font), size)
        c.setFont(self.font, size)
        for line in lines:
            if self.y < self.floor:
                break
            c.drawString(lx, self.y, line)
            self.y -= size * 1.45


def _table(c, y, w, font, headers, rows, xp, size=8.5):
    c.setFillColor(colors.HexColor("#F1F5F9"))
    c.rect(0.3 * inch, y - 0.2 * inch - 0.26 * inch * len(rows), w - 0.6 * inch, 0.36 * inch + 0.26 * inch * len(rows), fill=True, stroke=False)
    c.setFillColor(colors.black)
    c.setFont(_bold(font), 7)
    for i, hdr in enumerate(headers):
        c.drawString(xp[i], y, hdr)
    y -= 0.26 * inch
    for label, color, vals in rows:
        c.setFont(_bold(font), size)
        c.setFillColor(colors.HexColor(color))
        c.drawString(xp[0], y, label)
        c.setFillColor(colors.black)
        c.setFont(font, size)
        for i, v in enumerate(vals):
            c.drawString(xp[i + 1], y, v)
        y -= 0.26 * inch
    return y - 0.12 * inch


def _info(c, w, y, rx, patient, font):
    snap = rx.get("snapshot") or {}
    pname = snap.get("patient_name") or (f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip() if patient else "")
    c.setFont(font, 8)
    c.drawString(0.4 * inch, y, f"Paciente: {pname}")
    issued = rx.get("issued_at") or rx.get("created_at") or ""
    c.drawString(4.6 * inch, y, f"Fecha de emision: {_date(issued)}")
    y -= 0.18 * inch
    age = snap.get("patient_age")
    if age is None and patient and patient.get("birth_date"):
        age = calculate_age(patient["birth_date"])
    left = []
    if age:
        left.append(f"Edad: {age} anos")
    dpi = snap.get("patient_dpi") if snap else (patient or {}).get("dpi")
    if dpi:
        left.append(f"Identificacion: {dpi}")
    c.drawString(0.4 * inch, y, "   ".join(left))
    if snap.get("exam_date"):
        c.drawString(4.6 * inch, y, f"Fecha de examen: {_date(snap['exam_date'])}")
    y -= 0.18 * inch
    head = []
    if rx.get("code"):
        head.append(f"Receta {rx['code']}" + (f" \u00b7 v{rx.get('version')}" if rx.get("version") else ""))
    if rx.get("name"):
        head.append(rx["name"])
    if head:
        c.setFont(_bold(font), 8)
        c.drawString(0.4 * inch, y, "  \u00b7  ".join(head)[:110])
    c.setFont(font, 8)
    c.drawString(4.6 * inch, y, f"Profesional: {rx.get('professional_name') or snap.get('professional_name') or ''}"[:60])
    return y - 0.3 * inch


def _closing(pen, rx):
    pen.label("Uso", rx.get("usage"))
    pen.label("Indicaciones", rx.get("indications"), max_lines=3)
    pen.label("Observaciones", rx.get("observations"), max_lines=2)
    ctrl = rx.get("control")
    valid = _date(rx.get("valid_until")) if rx.get("valid_until") else ""
    if ctrl or valid:
        pen.label("Control / vigencia", "  \u00b7  ".join([x for x in (f"Control: {ctrl}" if ctrl else "", f"Vigente hasta: {valid}" if valid else "") if x]))


def _draw_eyeglass(c, w, y, rx, font):
    rows = [(lbl, col, [fp(rx.get(f"{e}_sphere"), True), fp(rx.get(f"{e}_cylinder")), fa(rx.get(f"{e}_axis")),
                        fp(rx.get(f"{e}_addition")), fprism(rx.get(f"{e}_prism_h"), rx.get(f"{e}_base_h")),
                        fprism(rx.get(f"{e}_prism_v"), rx.get(f"{e}_base_v"))]) for e, lbl, col in EYES]
    xp = [0.4 * inch, 1.0 * inch, 1.85 * inch, 2.7 * inch, 3.4 * inch, 4.25 * inch, 5.45 * inch]
    y = _table(c, y, w, font, ["", "ESFERA (D)", "CIL (D)", "EJE", "ADD (D)", "PRISMA H", "PRISMA V"], rows, xp)
    pen = Pen(c, w, y, font)
    mode = {"lejos_add": "Receta de lejos con ADD (multifocal)", "cerca_final": "Potencia final de cerca (monofocal)",
            "monofocal": "Monofocal"}.get(rx.get("rx_mode") or "")
    pen.label("Diseno", mode)
    pen.label("Distancia de trabajo", f"{rx['working_distance']} cm" if rx.get("working_distance") else "")
    disp = []
    if rx.get("od_dp") or rx.get("oi_dp"):
        disp.append(f"DP OD {fn(rx.get('od_dp'))} / OS {fn(rx.get('oi_dp'))} mm")
    if rx.get("od_height") or rx.get("oi_height"):
        disp.append(f"Alturas OD {fn(rx.get('od_height'))} / OS {fn(rx.get('oi_height'))} mm")
    if rx.get("lens_type"):
        disp.append(f"Lente: {rx['lens_type']}")
    if rx.get("frame_type"):
        disp.append(f"Armazon: {rx['frame_type']}")
    pen.label("Dispensacion (no refractivo)", "  \u00b7  ".join(disp))
    _closing(pen, rx)


def _draw_contact(c, w, y, rx, font):
    rows = [(lbl, col, [fp(rx.get(f"{e}_power"), True), fp(rx.get(f"{e}_cylinder")), fa(rx.get(f"{e}_axis")),
                        fp(rx.get(f"{e}_addition")), fn(rx.get(f"{e}_bc")), fn(rx.get(f"{e}_dia"))]) for e, lbl, col in EYES]
    xp = [0.4 * inch, 1.0 * inch, 1.9 * inch, 2.75 * inch, 3.45 * inch, 4.3 * inch, 5.2 * inch]
    y = _table(c, y, w, font, ["", "POTENCIA (D)", "CIL (D)", "EJE", "ADD (D)", "C.B. (mm)", "DIAM (mm)"], rows, xp)
    pen = Pen(c, w, y, font)
    lens = "  \u00b7  ".join([x for x in (rx.get("manufacturer"), rx.get("brand"), rx.get("model")) if x])
    pen.label("Lente", lens)
    spec = "  \u00b7  ".join([x for x in (
        f"Material: {rx['material']}" if rx.get("material") else "", f"Diseno: {rx['design']}" if rx.get("design") else "",
        f"Modalidad: {rx['modality']}" if rx.get("modality") else "", f"Reemplazo: {rx['replacement']}" if rx.get("replacement") else "",
        f"Tipo: {rx['lens_type']}" if rx.get("lens_type") and not rx.get("design") else "") if x])
    pen.label("Especificaciones", spec)
    pen.label("Cuidados", rx.get("care_system"))
    for e, lbl, _ in EYES:
        pen.label(f"Parametros {lbl}", rx.get(f"{e}_extra"), max_lines=1)
    _closing(pen, rx)


def _draw_scleral(c, w, y, rx, font):
    unit = rx.get("sag_unit") or "um"
    rows = [(lbl, col, [fp(rx.get(f"{e}_power"), True), fp(rx.get(f"{e}_cylinder")), fa(rx.get(f"{e}_axis")),
                        fp(rx.get(f"{e}_addition")), fn(rx.get(f"{e}_dia")), fn(rx.get(f"{e}_sag")), fn(rx.get(f"{e}_ref_dia"))])
            for e, lbl, col in EYES]
    xp = [0.4 * inch, 0.95 * inch, 1.75 * inch, 2.5 * inch, 3.1 * inch, 3.85 * inch, 4.7 * inch, 5.6 * inch]
    y = _table(c, y, w, font, ["", "POT (D)", "CIL (D)", "EJE", "ADD", "DIAM (mm)", f"SAGITA ({unit})", "DIAM REF"], rows, xp, size=8)
    pen = Pen(c, w, y, font)
    for e, lbl, _ in EYES:
        parts = [f"Zona limbal {rx[f'{e}_limbal_zone']}" if rx.get(f"{e}_limbal_zone") else ""]
        hap = [f"{s} {rx.get(f'{e}_haptic_{k}')}" for k, s in (("sup", "S"), ("inf", "I"), ("nas", "N"), ("tem", "T")) if rx.get(f"{e}_haptic_{k}")]
        parts.append(f"Haptica {' / '.join(hap)}" if hap else "")
        parts.append(rx.get(f"{e}_extra") or "")
        pen.label(f"{lbl}", "  \u00b7  ".join([p for p in parts if p]), size=7, max_lines=1)
    pen.label("Laboratorio", "  \u00b7  ".join([x for x in (rx.get("lab"), rx.get("design"), f"Codigo {rx['lab_code']}" if rx.get("lab_code") else "") if x]), size=7)
    pen.label("Material", "  \u00b7  ".join([x for x in (rx.get("material"), f"Espesor {rx['thickness']}" if rx.get("thickness") else "",
                                                       f"Tratamiento {rx['surface_treatment']}" if rx.get("surface_treatment") else "") if x]), size=7)
    pen.label("Modificaciones", rx.get("special_mods"), size=7, max_lines=1)
    pen.label("Parametros del fabricante", rx.get("manufacturer_params"), size=7, max_lines=1)
    pen.label("Uso y cuidados", "  \u00b7  ".join([x for x in (rx.get("usage_instructions"), f"Llenado: {rx['filling_solution']}" if rx.get("filling_solution") else "",
                                                               f"Limpieza/desinfeccion: {rx['cleaning']}" if rx.get("cleaning") else "") if x]), size=7)
    _closing(pen, rx)


def _draw_medical(c, w, y, rx, font):
    if rx.get("diagnosis"):
        c.setFont(_bold(font), 8)
        c.drawString(0.4 * inch, y, "Diagnostico:")
        c.setFont(font, 8)
        c.drawString(1.4 * inch, y, rx["diagnosis"][:70])
        y -= 0.3 * inch
    c.setFont(_bold(font), 9)
    c.drawString(0.4 * inch, y, "Medicamentos:")
    y -= 0.22 * inch
    c.setFont(font, 8)
    for med in rx.get("medications", []):
        c.drawString(0.5 * inch, y, f"Rx  {med.get('name', '')}")
        y -= 0.18 * inch
        for k, lbl in (("dosage", "Dosis"), ("frequency", "Frecuencia"), ("duration", "Duracion")):
            if med.get(k):
                c.drawString(0.7 * inch, y, f"{lbl}: {med[k]}")
                y -= 0.16 * inch
        y -= 0.08 * inch
        if y < 1.5 * inch:
            break
    if rx.get("instructions"):
        pen = Pen(c, w, y - 0.1 * inch, font)
        pen.label("Indicaciones", rx["instructions"], size=8, max_lines=3)


DRAWERS = {"eyeglass": _draw_eyeglass, "contact": _draw_contact, "scleral": _draw_scleral, "medical": _draw_medical}


def _watermark(c, w, h, status):
    text = WATERMARKS.get(status or "")
    if not text:
        return
    c.saveState()
    c.setFillColor(colors.HexColor("#DC2626"))
    c.setFillAlpha(0.16)
    c.translate(w / 2, h / 2 - 0.2 * inch)
    c.rotate(22)
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(0, 0, text)
    c.restoreState()
    c.setFillColor(colors.HexColor("#DC2626"))
    c.setFont("Helvetica-Bold", 7.5)
    c.drawRightString(w - 0.4 * inch, 0.62 * inch, text)
    c.setFillColor(colors.black)


def draw_page(c, kind, rx, patient, company):
    rx = effective_rx(rx)
    style = get_rx_style(company, "medica" if kind == "medical" else "optica")
    w, h = HALF_LETTER
    y = draw_rx_header(c, w, h, company, TITLES[kind], style, get_logo_path(company))
    y = _info(c, w, y, rx, patient, style["font"])
    DRAWERS[kind](c, w, y, rx, style["font"])
    draw_rx_footer(c, w, style, rx.get("professional_name", ""))
    if rx.get("code"):
        c.setFont(style["font"], 6.5)
        c.setFillColor(colors.HexColor("#64748B"))
        c.drawRightString(w - 0.4 * inch, 0.48 * inch, f"{rx['code']}" + (f" v{rx['version']}" if rx.get("version") else ""))
        c.setFillColor(colors.black)
    _watermark(c, w, h, rx.get("status"))


def render_pages(pages, company: Optional[dict]) -> bytes:
    """pages: lista de (kind, rx, patient). Una receta por pagina."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=HALF_LETTER)
    for kind, rx, patient in pages:
        draw_page(c, kind, rx, patient, company)
        c.showPage()
    c.save()
    return buffer.getvalue()


def render_single(kind, rx, patient, company, copies=1) -> bytes:
    return render_pages([(kind, rx, patient)] * max(1, min(int(copies or 1), 10)), company)
