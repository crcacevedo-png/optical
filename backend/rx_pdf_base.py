"""Base visual de las recetas PDF (media carta): estilos por optica, encabezados
clasico/moderno/elegante con logo y pie con linea de firma. Compartido por las
recetas individuales y la impresion multiple."""
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

from db import UPLOADS_DIR

HALF_LETTER = (8.5*inch, 5.5*inch)

def get_logo_path(company):
    if company and company.get("logo_filename"):
        candidate = UPLOADS_DIR / company["logo_filename"]
        if candidate.exists():
            return str(candidate)
    return None

def get_rx_style(company, rx_type="optica"):
    ps = (company or {}).get("prescription_style", {})
    style = ps.get(rx_type, ps)
    return {
        "font": style.get("font", "Helvetica"),
        "size": style.get("size", "standard"),
        "show_logo": style.get("show_logo", True),
        "header_text": style.get("header_text", ""),
        "footer_text": style.get("footer_text", ""),
        "template": style.get("template", "clasico"),
    }

def draw_rx_clasico(c, w, h, company, title, style, logo_path):
    c.setFillColor(colors.HexColor("#0F4C3A"))
    c.rect(0, h - 0.9*inch, w, 0.9*inch, fill=True, stroke=False)
    text_x = 0.4*inch
    if style["show_logo"] and logo_path:
        try:
            img = ImageReader(logo_path)
            iw, ih = img.getSize()
            aspect = iw / ih
            lh = 0.55*inch
            lw = min(lh * aspect, 1.2*inch)
            lh = lw / aspect
            c.drawImage(logo_path, 0.3*inch, h - 0.78*inch, width=lw, height=lh, preserveAspectRatio=True, mask='auto')
            text_x = 0.35*inch + lw + 0.15*inch
        except Exception:
            pass
    c.setFillColor(colors.white)
    font = style["font"]
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 13)
    c.drawString(text_x, h - 0.45*inch, (company or {}).get("name", "Cortexia Optical"))
    c.setFont(font, 7)
    c.drawString(text_x, h - 0.6*inch, (company or {}).get("address", ""))
    phone = (company or {}).get("phone", "")
    email = (company or {}).get("email", "")
    if phone or email:
        c.drawString(text_x, h - 0.72*inch, f"Tel: {phone}  |  {email}" if email else f"Tel: {phone}")
    c.setFillColor(colors.black)
    if style["header_text"]:
        c.setFont(font, 6)
        c.setFillColor(colors.HexColor("#666666"))
        c.drawCentredString(w/2, h - 1.02*inch, style["header_text"])
        c.setFillColor(colors.black)
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 10)
    c.drawCentredString(w/2, h - 1.18*inch, title)
    c.setStrokeColor(colors.HexColor("#0F4C3A"))
    c.setLineWidth(0.5)
    c.line(0.3*inch, h - 1.25*inch, w - 0.3*inch, h - 1.25*inch)
    c.setStrokeColor(colors.black)
    return h - 1.4*inch

def draw_rx_moderno(c, w, h, company, title, style, logo_path):
    c.setFillColor(colors.HexColor("#1ABC9C"))
    c.rect(0, 0, 0.18*inch, h, fill=True, stroke=False)
    c.setFillColor(colors.HexColor("#F8FAFB"))
    c.rect(0.18*inch, h - 1.1*inch, w - 0.18*inch, 1.1*inch, fill=True, stroke=False)
    text_x = 0.45*inch
    if style["show_logo"] and logo_path:
        try:
            img = ImageReader(logo_path)
            iw, ih = img.getSize()
            aspect = iw / ih
            lh = 0.6*inch
            lw = min(lh * aspect, 1.2*inch)
            lh = lw / aspect
            c.drawImage(logo_path, 0.4*inch, h - 0.85*inch, width=lw, height=lh, preserveAspectRatio=True, mask='auto')
            text_x = 0.45*inch + lw + 0.15*inch
        except Exception:
            pass
    font = style["font"]
    c.setFillColor(colors.HexColor("#1B2A49"))
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 14)
    c.drawString(text_x, h - 0.45*inch, (company or {}).get("name", "Cortexia Optical"))
    c.setFont(font, 7)
    c.setFillColor(colors.HexColor("#5A6A7A"))
    c.drawString(text_x, h - 0.6*inch, (company or {}).get("address", ""))
    phone = (company or {}).get("phone", "")
    email = (company or {}).get("email", "")
    if phone or email:
        c.drawString(text_x, h - 0.72*inch, f"Tel: {phone}  |  {email}" if email else f"Tel: {phone}")
    title_w = c.stringWidth(title, f"{font}-Bold" if font != "Courier" else font, 9) + 0.5*inch
    title_x = w/2 - title_w/2
    c.setFillColor(colors.HexColor("#1ABC9C"))
    c.roundRect(title_x, h - 1.25*inch, title_w, 0.28*inch, 0.1*inch, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 9)
    c.drawCentredString(w/2, h - 1.19*inch, title)
    if style["header_text"]:
        c.setFillColor(colors.HexColor("#888888"))
        c.setFont(font, 6)
        c.drawCentredString(w/2, h - 1.4*inch, style["header_text"])
    c.setFillColor(colors.black)
    return h - 1.55*inch

def draw_rx_elegante(c, w, h, company, title, style, logo_path):
    c.setStrokeColor(colors.HexColor("#5A2D82"))
    c.setLineWidth(1.5)
    c.rect(0.2*inch, 0.2*inch, w - 0.4*inch, h - 0.4*inch, fill=False, stroke=True)
    c.setLineWidth(0.5)
    c.rect(0.28*inch, 0.28*inch, w - 0.56*inch, h - 0.56*inch, fill=False, stroke=True)
    c.setStrokeColor(colors.black)
    if style["show_logo"] and logo_path:
        try:
            img = ImageReader(logo_path)
            iw, ih = img.getSize()
            aspect = iw / ih
            lh = 0.55*inch
            lw = min(lh * aspect, 1.2*inch)
            lh = lw / aspect
            c.drawImage(logo_path, w/2 - lw/2, h - 0.4*inch - lh, width=lw, height=lh, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    font = style["font"]
    y_top = h - 1.05*inch
    c.setFillColor(colors.HexColor("#5A2D82"))
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 14)
    c.drawCentredString(w/2, y_top, (company or {}).get("name", "Cortexia Optical"))
    c.setFont(font, 7)
    c.setFillColor(colors.HexColor("#666666"))
    c.drawCentredString(w/2, y_top - 0.16*inch, (company or {}).get("address", ""))
    phone = (company or {}).get("phone", "")
    email = (company or {}).get("email", "")
    if phone or email:
        c.drawCentredString(w/2, y_top - 0.3*inch, f"Tel: {phone}  |  {email}" if email else f"Tel: {phone}")
    c.setStrokeColor(colors.HexColor("#5A2D82"))
    c.setLineWidth(0.8)
    c.line(0.6*inch, y_top - 0.45*inch, w - 0.6*inch, y_top - 0.45*inch)
    c.setLineWidth(0.3)
    c.line(0.6*inch, y_top - 0.5*inch, w - 0.6*inch, y_top - 0.5*inch)
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.HexColor("#5A2D82"))
    c.setFont(f"{font}-Bold" if font != "Courier" else font, 11)
    c.drawCentredString(w/2, y_top - 0.68*inch, title)
    if style["header_text"]:
        c.setFillColor(colors.HexColor("#888888"))
        c.setFont(font, 6)
        c.drawCentredString(w/2, y_top - 0.82*inch, style["header_text"])
    c.setFillColor(colors.black)
    return y_top - 0.95*inch

STYLE_RENDERERS = {"clasico": draw_rx_clasico, "moderno": draw_rx_moderno, "elegante": draw_rx_elegante}

def draw_rx_header(c, w, h, company, title, style, logo_path):
    template = style.get("template", "clasico")
    renderer = STYLE_RENDERERS.get(template, draw_rx_clasico)
    return renderer(c, w, h, company, title, style, logo_path)

def draw_rx_footer(c, w, style, professional_name):
    font = style["font"]
    y = 0.9*inch
    c.line(0.4*inch, y, 2.2*inch, y)
    c.setFont(font, 8)
    c.drawString(0.4*inch, y - 0.15*inch, professional_name or "")
    c.setFont(font, 7)
    c.drawString(0.4*inch, y - 0.3*inch, "Profesional de la Salud Visual")
    if style.get("footer_text"):
        c.setFillColor(colors.HexColor("#888888"))
        c.setFont(font, 6)
        c.drawCentredString(w/2, 0.35*inch, style["footer_text"])
        c.setFillColor(colors.black)
