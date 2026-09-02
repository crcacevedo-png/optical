"""Exportacion completa de base de datos por empresa (admin de cada optica)."""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from bson import ObjectId
from datetime import datetime, timezone
import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from db import db
from auth_utils import get_current_user
from audit import log_audit

router = APIRouter(prefix="/data-export", tags=["Exportacion Datos"])

HEADER_FILL = PatternFill(start_color="1B2A49", end_color="1B2A49", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
HEADER_ALIGN = Alignment(horizontal="center", vertical="center")


def _stringify(value):
    """Convert MongoDB types to safe string representations for Excel."""
    if value is None:
        return ""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, (dict, list)):
        return str(value)
    if isinstance(value, bool):
        return "Si" if value else "No"
    return value


def _write_sheet(wb, sheet_name: str, headers: list, rows: list):
    """Helper para escribir una hoja con header estilizado y autodetectar anchos."""
    ws = wb.create_sheet(sheet_name[:31])  # Excel sheet name limit
    # Header
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGN
    # Rows
    for r_idx, row in enumerate(rows, start=2):
        for c_idx, value in enumerate(row, start=1):
            ws.cell(row=r_idx, column=c_idx, value=_stringify(value))
    # Auto width (max 50)
    for col_idx, h in enumerate(headers, start=1):
        max_len = len(str(h))
        for row in rows:
            if col_idx - 1 < len(row):
                val_len = len(str(_stringify(row[col_idx - 1])))
                if val_len > max_len:
                    max_len = val_len
        col_letter = ws.cell(row=1, column=col_idx).column_letter
        ws.column_dimensions[col_letter].width = min(max_len + 2, 50)
    ws.freeze_panes = "A2"
    return ws


def _build_patient_map(patients):
    return {str(p["_id"]): f"{p.get('first_name','')} {p.get('last_name','')}".strip() for p in patients}


def _build_product_map(products):
    return {str(p["_id"]): p.get("name", "") for p in products}


def _build_branch_map(branches):
    return {str(b["_id"]): b.get("name", "") for b in branches}


def _build_user_map(users):
    return {str(u["_id"]): u.get("name", "") for u in users}


def _fam(flag, rel):
    """Formatea antecedente familiar: 'Si (parentesco)' / 'No'."""
    if not flag:
        return "No"
    return f"Si ({rel})" if rel else "Si"


def _format_refractions(refractions):
    """Serializa el array de refracciones a un texto legible para Excel."""
    if not refractions:
        return ""
    parts = []
    for i, r in enumerate(refractions, start=1):
        od = f"OD {r.get('od_sphere') or '-'}/{r.get('od_cylinder') or '-'}x{r.get('od_axis') or '-'} add {r.get('od_addition') or '-'}"
        os_ = f"OS {r.get('os_sphere') or '-'}/{r.get('os_cylinder') or '-'}x{r.get('os_axis') or '-'} add {r.get('os_addition') or '-'}"
        obs = f" ({r.get('observations')})" if r.get("observations") else ""
        parts.append(f"R{i}: {od} | {os_}{obs}")
    return " ; ".join(parts)


async def _export_company_data(company_id_str: str, company_name: str) -> io.BytesIO:
    """Genera un workbook Excel con todas las colecciones de la empresa."""
    company_id = ObjectId(company_id_str)
    wb = Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # ─────── Sucursales ───────
    branches = await db.branches.find({"company_id": company_id}).to_list(None)
    branch_map = _build_branch_map(branches)
    _write_sheet(wb, "Sucursales", [
        "ID", "Nombre", "Direccion", "Telefono", "Email", "Activa", "Creada"
    ], [[b.get("_id"), b.get("name"), b.get("address"), b.get("phone"),
         b.get("email"), b.get("is_active", True), b.get("created_at")] for b in branches])

    # ─────── Usuarios ───────
    users = await db.users.find({"company_id": company_id}, {"password_hash": 0}).to_list(None)
    user_map = _build_user_map(users)
    _write_sheet(wb, "Usuarios", [
        "ID", "Nombre", "Email", "Rol", "Sucursal", "Activo", "Creado"
    ], [[u.get("_id"), u.get("name"), u.get("email"), u.get("role"),
         branch_map.get(str(u.get("branch_id")), ""), u.get("is_active", True), u.get("created_at")] for u in users])

    # ─────── Pacientes ───────
    patients = await db.patients.find({"company_id": company_id, "is_deleted": {"$ne": True}}).to_list(None)
    patient_map = _build_patient_map(patients)
    _write_sheet(wb, "Pacientes", [
        "ID", "Nombre", "Apellido", "DPI", "Fecha Nac", "Genero",
        "Telefono", "WhatsApp", "Email", "Direccion", "Ciudad", "Pais",
        "Contacto Emergencia", "Tel Emergencia", "Notas", "Creado"
    ], [[p.get("_id"), p.get("first_name"), p.get("last_name"), p.get("dpi"),
         p.get("birth_date"), p.get("gender"), p.get("phone"), p.get("whatsapp"),
         p.get("email"), p.get("address"), p.get("city"), p.get("country"),
         p.get("emergency_contact"), p.get("emergency_phone"), p.get("notes"),
         p.get("created_at")] for p in patients])

    # ─────── Citas ───────
    appointments = await db.appointments.find({"company_id": company_id}).to_list(None)
    _write_sheet(wb, "Citas", [
        "ID", "Paciente", "Sucursal", "Fecha", "Hora", "Duracion",
        "Tipo", "Estado", "Profesional", "Notas", "Creada"
    ], [[a.get("_id"), patient_map.get(str(a.get("patient_id")), ""),
         branch_map.get(str(a.get("branch_id")), ""), a.get("date"), a.get("time"),
         a.get("duration"), a.get("type"), a.get("status"), a.get("professional_name"),
         a.get("notes"), a.get("created_at")] for a in appointments])

    # ─────── Consultas Opticas ───────
    consultations = await db.optical_consultations.find({"company_id": company_id}).to_list(None)
    _write_sheet(wb, "Consultas", [
        "ID", "Paciente", "Fecha", "Tipo", "Motivo", "Anamnesis", "Hallazgos",
        "Diagnostico", "Tratamiento", "Recomendaciones", "Notas",
        "Usa Lentes", "Lentes Desde", "Tipo Lentes", "Lensometria OD", "Lensometria OS",
        "Cirugias Oculares", "Traumatismos", "Enfermedades Oculares",
        "Diabetes", "Hipertension", "Autoinmune", "Detalle Autoinmune", "Medicamentos", "Alergias",
        "Fam. Glaucoma", "Fam. Deg. Macular", "Fam. Miopia Alta", "Otros Antec. Familiares",
        "AV Lejos s/Rx OD", "AV Lejos s/Rx OS", "AV Lejos c/Rx OD", "AV Lejos c/Rx OS",
        "AV Cerca s/Rx OD", "AV Cerca s/Rx OS", "AV Cerca c/Rx OD", "AV Cerca c/Rx OS",
        "AV Estenopeico OD", "AV Estenopeico OS", "Metodo AV",
        "Refracciones", "Profesional", "Creada"
    ], [[c.get("_id"), patient_map.get(str(c.get("patient_id")), ""),
         c.get("consultation_date"), c.get("consultation_type"), c.get("chief_complaint"),
         c.get("anamnesis"), c.get("findings"), c.get("diagnosis"), c.get("treatment_plan"),
         c.get("recommendations"), c.get("notes"),
         c.get("wears_glasses"), c.get("glasses_since"), c.get("glasses_type"),
         c.get("lensometry_od"), c.get("lensometry_oi"),
         c.get("ocular_surgeries"), c.get("ocular_trauma"), c.get("ocular_diseases"),
         c.get("diabetes"), c.get("hypertension"),
         c.get("autoimmune_disease"), c.get("autoimmune_details"),
         c.get("current_medications"), c.get("allergies"),
         _fam(c.get("family_glaucoma"), c.get("family_glaucoma_relationship")),
         _fam(c.get("family_macular_degeneration"), c.get("family_macular_relationship")),
         _fam(c.get("family_high_myopia"), c.get("family_high_myopia_relationship")),
         c.get("family_other_history"),
         c.get("va_distance_without_rx_od"), c.get("va_distance_without_rx_oi"),
         c.get("va_distance_with_rx_od"), c.get("va_distance_with_rx_oi"),
         c.get("va_near_without_rx_od"), c.get("va_near_without_rx_oi"),
         c.get("va_near_with_rx_od"), c.get("va_near_with_rx_oi"),
         c.get("va_pinhole_od"), c.get("va_pinhole_oi"), c.get("visual_acuity_method"),
         _format_refractions(c.get("refractions")),
         c.get("professional_name"), c.get("created_at")] for c in consultations])

    # ─────── Recetas Oftalmicas ───────
    rx_eye = await db.eyeglass_prescriptions.find({"company_id": company_id}).to_list(None)
    _write_sheet(wb, "Recetas_Oftalmicas", [
        "ID", "Paciente", "Profesional",
        "OD Esfera", "OD Cilindro", "OD Eje", "OD Adicion", "OD DP",
        "OS Esfera", "OS Cilindro", "OS Eje", "OS Adicion", "OS DP",
        "Tipo Lente", "Armazon", "Observaciones", "Creada"
    ], [[r.get("_id"), patient_map.get(str(r.get("patient_id")), ""),
         r.get("professional_name"),
         r.get("od_sphere"), r.get("od_cylinder"), r.get("od_axis"), r.get("od_addition"), r.get("od_dp"),
         r.get("oi_sphere"), r.get("oi_cylinder"), r.get("oi_axis"), r.get("oi_addition"), r.get("oi_dp"),
         r.get("lens_type"), r.get("frame_type"), r.get("observations"),
         r.get("created_at")] for r in rx_eye])

    # ─────── Recetas Lentes de Contacto ───────
    rx_cl = await db.contact_lens_prescriptions.find({"company_id": company_id}).to_list(None)
    _write_sheet(wb, "Recetas_Contacto", [
        "ID", "Paciente", "Profesional", "Marca", "Tipo",
        "OD Esfera", "OD Cilindro", "OD Eje", "OD Adicion", "OD BC", "OD DIA",
        "OS Esfera", "OS Cilindro", "OS Eje", "OS Adicion", "OS BC", "OS DIA",
        "Reemplazo", "Observaciones", "Creada"
    ], [[r.get("_id"), patient_map.get(str(r.get("patient_id")), ""),
         r.get("professional_name"), r.get("brand"), r.get("lens_type"),
         r.get("od_power"), r.get("od_cylinder"), r.get("od_axis"), r.get("od_addition"), r.get("od_bc"), r.get("od_dia"),
         r.get("oi_power"), r.get("oi_cylinder"), r.get("oi_axis"), r.get("oi_addition"), r.get("oi_bc"), r.get("oi_dia"),
         r.get("replacement"), r.get("observations"), r.get("created_at")] for r in rx_cl])

    # ─────── Recetas Medicas ───────
    rx_med = await db.medical_prescriptions.find({"company_id": company_id}).to_list(None)
    _write_sheet(wb, "Recetas_Medicas", [
        "ID", "Paciente", "Profesional", "Medicamentos", "Indicaciones", "Observaciones", "Creada"
    ], [[r.get("_id"), patient_map.get(str(r.get("patient_id")), ""),
         r.get("professional_name"), str(r.get("medications", [])),
         r.get("instructions"), r.get("observations"), r.get("created_at")] for r in rx_med])

    # ─────── Productos / Inventario ───────
    products = await db.products.find({"company_id": company_id}).to_list(None)
    product_map = _build_product_map(products)
    _write_sheet(wb, "Productos", [
        "ID", "Nombre", "SKU", "Categoria", "Marca", "Precio Costo",
        "Precio Venta", "Stock Minimo", "Activo", "Creado"
    ], [[p.get("_id"), p.get("name"), p.get("sku"), p.get("category"),
         p.get("brand"), p.get("cost_price"), p.get("sale_price"),
         p.get("min_stock"), p.get("is_active", True), p.get("created_at")] for p in products])

    # ─────── Stock por sucursal ───────
    stock = await db.stock.find({"company_id": company_id}).to_list(None)
    _write_sheet(wb, "Stock", [
        "ID", "Producto", "Sucursal", "Cantidad", "Actualizado"
    ], [[s.get("_id"), product_map.get(str(s.get("product_id")), ""),
         branch_map.get(str(s.get("branch_id")), ""), s.get("quantity"),
         s.get("updated_at") or s.get("created_at")] for s in stock])

    # ─────── Movimientos de Inventario ───────
    movements = await db.inventory_movements.find({"company_id": company_id}).sort("created_at", -1).to_list(2000)
    _write_sheet(wb, "Movimientos_Inventario", [
        "ID", "Producto", "Sucursal", "Tipo", "Cantidad", "Motivo", "Usuario", "Fecha"
    ], [[m.get("_id"), product_map.get(str(m.get("product_id")), ""),
         branch_map.get(str(m.get("branch_id")), ""), m.get("type"),
         m.get("quantity"), m.get("reason"), user_map.get(str(m.get("user_id")), ""),
         m.get("created_at")] for m in movements])

    # ─────── Ventas ───────
    sales = await db.sales.find({"company_id": company_id}).sort("created_at", -1).to_list(None)
    _write_sheet(wb, "Ventas", [
        "ID", "Numero", "Paciente", "Sucursal", "Vendedor", "Subtotal",
        "Descuento", "Impuesto", "Total", "Pagado", "Saldo", "Metodo Pago",
        "Estado", "Items (JSON)", "Fecha"
    ], [[s.get("_id"), s.get("sale_number"),
         patient_map.get(str(s.get("patient_id")), ""),
         branch_map.get(str(s.get("branch_id")), ""),
         user_map.get(str(s.get("user_id")), ""),
         s.get("subtotal"), s.get("discount"), s.get("tax"), s.get("total"),
         s.get("paid_amount"), s.get("balance"), s.get("payment_method"),
         s.get("status"), str(s.get("items", [])), s.get("created_at")] for s in sales])

    # ─────── Cotizaciones ───────
    quotes = await db.quotations.find({"company_id": company_id}).to_list(None)
    _write_sheet(wb, "Cotizaciones", [
        "ID", "Numero", "Paciente", "Sucursal", "Total", "Estado",
        "Valida hasta", "Items (JSON)", "Fecha"
    ], [[q.get("_id"), q.get("quote_number"),
         patient_map.get(str(q.get("patient_id")), ""),
         branch_map.get(str(q.get("branch_id")), ""),
         q.get("total"), q.get("status"), q.get("valid_until"),
         str(q.get("items", [])), q.get("created_at")] for q in quotes])

    # ─────── Proveedores ───────
    suppliers = await db.suppliers.find({"company_id": company_id}).to_list(None)
    _write_sheet(wb, "Proveedores", [
        "ID", "Nombre", "Contacto", "Telefono", "Email", "Direccion",
        "NIT", "Notas", "Activo", "Creado"
    ], [[s.get("_id"), s.get("name"), s.get("contact_name"), s.get("phone"),
         s.get("email"), s.get("address"), s.get("tax_id"), s.get("notes"),
         s.get("is_active", True), s.get("created_at")] for s in suppliers])

    # ─────── Finanzas ───────
    finance = await db.finance_entries.find({"company_id": company_id}).to_list(None)
    _write_sheet(wb, "Finanzas", [
        "ID", "Tipo", "Categoria", "Descripcion", "Monto", "Metodo Pago",
        "Sucursal", "Fecha", "Creada"
    ], [[f.get("_id"), f.get("type"), f.get("category"), f.get("description"),
         f.get("amount"), f.get("payment_method"),
         branch_map.get(str(f.get("branch_id")), ""), f.get("date"),
         f.get("created_at")] for f in finance])

    # ─────── Hoja resumen al inicio ───────
    summary_ws = wb.create_sheet("Resumen", 0)
    summary_ws["A1"] = "EXPORTACION COMPLETA DE BASE DE DATOS"
    summary_ws["A1"].font = Font(bold=True, size=16, color="1B2A49")
    summary_ws["A2"] = f"Empresa: {company_name}"
    summary_ws["A2"].font = Font(bold=True, size=12)
    summary_ws["A3"] = f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    summary_ws["A3"].font = Font(italic=True, color="64748B")
    summary_ws["A5"] = "CONTENIDO DEL ARCHIVO"
    summary_ws["A5"].font = Font(bold=True, size=12)
    summary_ws["A5"].fill = HEADER_FILL
    summary_ws["A5"].font = Font(bold=True, color="FFFFFF", size=12)
    summary_ws.merge_cells("A5:C5")
    rows_summary = [
        ("Sucursales", len(branches)),
        ("Usuarios", len(users)),
        ("Pacientes", len(patients)),
        ("Citas", len(appointments)),
        ("Consultas", len(consultations)),
        ("Recetas Oftalmicas", len(rx_eye)),
        ("Recetas Contacto", len(rx_cl)),
        ("Recetas Medicas", len(rx_med)),
        ("Productos", len(products)),
        ("Stock (registros)", len(stock)),
        ("Movimientos Inventario", len(movements)),
        ("Ventas", len(sales)),
        ("Cotizaciones", len(quotes)),
        ("Proveedores", len(suppliers)),
        ("Finanzas", len(finance)),
    ]
    summary_ws.cell(row=6, column=1, value="Hoja").font = Font(bold=True)
    summary_ws.cell(row=6, column=2, value="Registros").font = Font(bold=True)
    for idx, (name, count) in enumerate(rows_summary, start=7):
        summary_ws.cell(row=idx, column=1, value=name)
        summary_ws.cell(row=idx, column=2, value=count)
    summary_ws.column_dimensions["A"].width = 30
    summary_ws.column_dimensions["B"].width = 15

    # Nota legal
    note_row = 7 + len(rows_summary) + 2
    summary_ws.cell(row=note_row, column=1,
        value="Este archivo contiene informacion confidencial de su optica.")
    summary_ws.cell(row=note_row + 1, column=1,
        value="Almacenelo en un lugar seguro. Cortexia Optical no se responsabiliza por filtraciones posteriores a la descarga.")
    for r in [note_row, note_row + 1]:
        summary_ws.cell(row=r, column=1).font = Font(italic=True, color="64748B", size=9)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


@router.get("/full-database")
async def export_full_database(request: Request, user: dict = Depends(get_current_user)):
    """Permite al admin de una optica descargar TODA su base de datos en Excel."""
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Solo administradores pueden exportar la base de datos")
    if not user.get("company_id"):
        raise HTTPException(status_code=400, detail="Usuario sin empresa asignada")

    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    company_name = company.get("name", "Empresa")
    buffer = await _export_company_data(user["company_id"], company_name)

    safe_name = "".join(c if c.isalnum() else "_" for c in company_name)[:40]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"Cortexia_Export_{safe_name}_{timestamp}.xlsx"

    await log_audit("DATABASE_EXPORTED", actor_id=user["_id"], actor_email=user.get("email"),
                    actor_role=user["role"], company_id=user["company_id"],
                    metadata={"company_name": company_name, "filename": filename}, request=request)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
