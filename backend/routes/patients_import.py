"""Ingreso masivo de pacientes (importacion desde Excel/CSV).

Solo para el rol administrador de cada optica. Permite descargar una plantilla,
previsualizar un archivo y confirmar la importacion creando/actualizando pacientes
y, opcionalmente, una receta de anteojos por fila como historial inicial.
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Request
from fastapi.responses import StreamingResponse, Response
from bson import ObjectId
from datetime import datetime, timezone, date
from typing import Optional
import io
import csv
import re
import unicodedata
import asyncio

from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from db import db, effective_max_patients
from auth_utils import get_current_user
from audit import log_audit
from routes.patients import _notify_patient_limit

router = APIRouter(prefix="/patients/import", tags=["Importacion de Pacientes"])

MAX_ROWS = 2000
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
PREVIEW_SAMPLE = 10

# Columnas de la plantilla (orden exacto de escritura).
TEMPLATE_HEADERS = [
    "Nombre completo",
    "Telefono",
    "WhatsApp",
    "Correo electronico",
    "Fecha de nacimiento (AAAA-MM-DD)",
    "Sexo (M/F)",
    "Direccion",
    "OD Esfera",
    "OD Cilindro",
    "OD Eje",
    "OD Adicion",
    "OS Esfera",
    "OS Cilindro",
    "OS Eje",
    "OS Adicion",
    "Observaciones receta",
]

TEMPLATE_EXAMPLE = [
    "Maria Lopez Garcia", "55551234", "55551234", "maria@ejemplo.com",
    "1990-05-12", "F", "Zona 1, Ciudad de Guatemala",
    "-1.25", "-0.50", "90", "+1.00",
    "-1.00", "-0.75", "85", "+1.00",
    "Lentes para lectura y distancia",
]

# Normalizado -> campo canonico.
HEADER_MAP = {
    "nombre completo": "full_name", "nombre": "full_name", "paciente": "full_name",
    "telefono": "phone", "tel": "phone", "celular": "phone", "movil": "phone",
    "whatsapp": "whatsapp", "wa": "whatsapp",
    "correo electronico": "email", "correo": "email", "email": "email", "e-mail": "email",
    "fecha de nacimiento": "birth_date", "fecha nacimiento": "birth_date", "nacimiento": "birth_date",
    "sexo": "gender", "genero": "gender",
    "direccion": "address",
    "od esfera": "od_sphere", "od cilindro": "od_cylinder", "od eje": "od_axis", "od adicion": "od_addition",
    "os esfera": "oi_sphere", "os cilindro": "oi_cylinder", "os eje": "oi_axis", "os adicion": "oi_addition",
    "oi esfera": "oi_sphere", "oi cilindro": "oi_cylinder", "oi eje": "oi_axis", "oi adicion": "oi_addition",
    "observaciones receta": "rx_observations", "observaciones": "rx_observations", "observacion": "rx_observations",
}

RX_NUMERIC_FIELDS = ["od_sphere", "od_cylinder", "od_axis", "od_addition",
                     "oi_sphere", "oi_cylinder", "oi_axis", "oi_addition"]
RX_AXIS_FIELDS = {"od_axis", "oi_axis"}
RX_LABELS = {
    "od_sphere": "OD Esfera", "od_cylinder": "OD Cilindro", "od_axis": "OD Eje", "od_addition": "OD Adicion",
    "oi_sphere": "OS Esfera", "oi_cylinder": "OS Cilindro", "oi_axis": "OS Eje", "oi_addition": "OS Adicion",
}
_PLANO_ALIASES = ("plano", "pl", "piano", "neutro", "n", "0", "0.0", "0.00")


def _norm(s) -> str:
    s = str(s or "").strip()
    s = re.sub(r"\(.*?\)", "", s)  # quitar pistas entre parentesis
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower().strip())


def _cell_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, bool):
        return ""
    if isinstance(val, float):
        return str(int(val)) if val.is_integer() else str(val)
    if isinstance(val, int):
        return str(val)
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    return str(val).strip()


def _parse_optic(val, as_int=False):
    """Devuelve (valor, ok). '' -> (None, True). 'plano' -> 0. Invalido -> (None, False)."""
    if val is None:
        return None, True
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return (int(round(val)) if as_int else float(val)), True
    s = str(val).strip()
    if s == "":
        return None, True
    low = s.lower()
    if low in _PLANO_ALIASES:
        return (0 if as_int else 0.0), True
    s = s.replace(",", ".").replace("+", "").strip()
    try:
        f = float(s)
        return (int(round(f)) if as_int else f), True
    except (ValueError, TypeError):
        return None, False


def _parse_gender(val) -> Optional[str]:
    s = _norm(val)
    if s in ("m", "masculino", "hombre", "male"):
        return "M"
    if s in ("f", "femenino", "mujer", "female"):
        return "F"
    return None


def _parse_date(val):
    """Devuelve (iso_str|None, ok)."""
    if val is None:
        return None, True
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d"), True
    s = str(val).strip()
    if s == "":
        return None, True
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d"), True
        except ValueError:
            continue
    return None, False


def _read_rows(content: bytes, filename: str):
    """Lee el archivo y devuelve (headers_detectados, rows). Cada row = (excel_row_num, {canonical: raw})."""
    name = (filename or "").lower()
    raw_rows = []  # lista de listas de celdas

    if name.endswith(".xlsx"):
        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception:
            raise HTTPException(status_code=400, detail="No se pudo leer el archivo Excel. Verifica que sea un .xlsx valido.")
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            raw_rows.append(list(row))
        wb.close()
    elif name.endswith(".csv"):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = content.decode("latin-1")
            except Exception:
                raise HTTPException(status_code=400, detail="No se pudo leer el archivo CSV (codificacion no soportada).")
        reader = csv.reader(io.StringIO(text))
        for row in reader:
            raw_rows.append(list(row))
    else:
        raise HTTPException(status_code=400, detail="Formato no soportado. Sube un archivo .xlsx o .csv.")

    # Encontrar la primera fila no vacia = encabezados.
    header_idx = None
    for i, r in enumerate(raw_rows):
        if any(_cell_str(c) != "" for c in r):
            header_idx = i
            break
    if header_idx is None:
        raise HTTPException(status_code=400, detail="El archivo esta vacio.")

    headers = [_cell_str(c) for c in raw_rows[header_idx]]
    col_map = {}  # indice de columna -> campo canonico
    for idx, h in enumerate(headers):
        canonical = HEADER_MAP.get(_norm(h))
        if canonical and idx not in col_map.values():
            col_map[idx] = canonical
    if "full_name" not in col_map.values() or "phone" not in col_map.values():
        raise HTTPException(
            status_code=400,
            detail="El archivo no tiene las columnas obligatorias 'Nombre completo' y 'Telefono'. Descarga la plantilla.",
        )

    rows = []
    for offset, r in enumerate(raw_rows[header_idx + 1:]):
        excel_row = header_idx + 2 + offset  # fila real en la hoja (1-based)
        if not any(_cell_str(c) != "" for c in r):
            continue  # fila totalmente vacia
        d = {}
        for idx, field in col_map.items():
            val = r[idx] if idx < len(r) else None
            d[field] = val
        rows.append((excel_row, d))
        if len(rows) > MAX_ROWS:
            raise HTTPException(status_code=400, detail=f"El archivo supera el maximo de {MAX_ROWS} filas por carga.")

    return [h for h in headers if h], rows


def _validate_row(excel_row: int, d: dict):
    """Devuelve (clean|None, error|None). error = {'row', 'reason', 'name'}."""
    full = _cell_str(d.get("full_name"))
    phone = _cell_str(d.get("phone"))

    if not full:
        return None, {"row": excel_row, "name": full or phone or "-", "reason": "Falta el nombre completo"}
    if not phone:
        return None, {"row": excel_row, "name": full, "reason": "Falta el telefono"}

    birth_iso, ok = _parse_date(d.get("birth_date"))
    if not ok:
        return None, {"row": excel_row, "name": full, "reason": "Fecha de nacimiento invalida (use AAAA-MM-DD)"}

    rx_vals = {}
    rx_has = False
    for f in RX_NUMERIC_FIELDS:
        v, ok = _parse_optic(d.get(f), as_int=(f in RX_AXIS_FIELDS))
        if not ok:
            return None, {"row": excel_row, "name": full, "reason": f"Graduacion invalida en columna '{RX_LABELS[f]}'"}
        rx_vals[f] = v
        if v is not None:
            rx_has = True

    parts = full.split()
    first_name = parts[0]
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    email = _cell_str(d.get("email")).lower() or None
    whatsapp = _cell_str(d.get("whatsapp")) or phone

    clean = {
        "row": excel_row,
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full,
        "phone": phone,
        "whatsapp": whatsapp,
        "email": email,
        "birth_date": birth_iso,
        "gender": _parse_gender(d.get("gender")),
        "address": _cell_str(d.get("address")) or None,
        "rx": rx_vals if rx_has else None,
        "rx_observations": _cell_str(d.get("rx_observations")) or None,
        "match_key": ("email:" + email) if email else ("phone:" + phone),
    }
    return clean, None


async def _require_admin_company(user: dict):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo el administrador de la optica puede importar pacientes.")
    if not user.get("company_id"):
        raise HTTPException(status_code=400, detail="Usuario sin empresa asignada.")
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    plan = await db.plans.find_one({"_id": company["plan_id"]}) if company.get("plan_id") else None
    return company, plan


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="El archivo supera el tamano maximo permitido (5 MB).")
    if not content:
        raise HTTPException(status_code=400, detail="El archivo esta vacio.")
    return content


def _build_template_workbook() -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Pacientes"
    header_fill = PatternFill(start_color="1B5E4F", end_color="1B5E4F", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    for col, title in enumerate(TEMPLATE_HEADERS, start=1):
        cell = ws.cell(row=1, column=col, value=title)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[cell.column_letter].width = max(14, min(32, len(title) + 2))
    for col, val in enumerate(TEMPLATE_EXAMPLE, start=1):
        ws.cell(row=2, column=col, value=val)
    ws.freeze_panes = "A2"
    # Hoja de instrucciones
    ws2 = wb.create_sheet("Instrucciones")
    notes = [
        "Instrucciones para el ingreso masivo de pacientes",
        "",
        "1. Llena una fila por paciente. No borres la fila de encabezados.",
        "2. 'Nombre completo' y 'Telefono' son obligatorios.",
        "3. El primer nombre se toma como Nombre y el resto como Apellidos.",
        "4. Fecha de nacimiento en formato AAAA-MM-DD (ej. 1990-05-12).",
        "5. Sexo: escribe M o F.",
        "6. Si no pones WhatsApp, se usa el Telefono.",
        "7. Las columnas de graduacion (OD/OS) son opcionales: si las llenas se",
        "   guarda una receta de anteojos como historial inicial del paciente.",
        "8. En graduacion puedes escribir 'plano' o 'pl' para 0.00.",
        "9. Si un paciente ya existe (mismo correo o telefono) se actualizan sus datos.",
        "10. La fila de ejemplo de la hoja 'Pacientes' puedes borrarla antes de subir.",
    ]
    for i, line in enumerate(notes, start=1):
        c = ws2.cell(row=i, column=1, value=line)
        if i == 1:
            c.font = Font(bold=True, size=13, color="1B5E4F")
    ws2.column_dimensions["A"].width = 80
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@router.get("/template.xlsx")
async def download_template_xlsx(user: dict = Depends(get_current_user)):
    await _require_admin_company(user)
    buf = await asyncio.to_thread(_build_template_workbook)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="plantilla_pacientes_cortexia.xlsx"'},
    )


@router.get("/template.csv")
async def download_template_csv(user: dict = Depends(get_current_user)):
    await _require_admin_company(user)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(TEMPLATE_HEADERS)
    writer.writerow(TEMPLATE_EXAMPLE)
    data = "\ufeff" + out.getvalue()  # BOM para Excel
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="plantilla_pacientes_cortexia.csv"'},
    )


@router.post("/preview")
async def preview_import(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    company, plan = await _require_admin_company(user)
    content = await _read_upload(file)
    headers, rows = await asyncio.to_thread(_read_rows, content, file.filename)

    valid, errors, has_rx = [], [], 0
    for excel_row, d in rows:
        clean, err = _validate_row(excel_row, d)
        if err:
            errors.append(err)
        else:
            valid.append(clean)
            if clean["rx"]:
                has_rx += 1

    max_p = effective_max_patients(company, plan)
    current = await db.patients.count_documents({"company_id": ObjectId(user["company_id"]), "is_deleted": {"$ne": True}})
    unlimited = max_p <= 0
    available = None if unlimited else max(0, max_p - current)

    def _display(c):
        return {
            "row": c["row"], "name": c["full_name"], "phone": c["phone"],
            "email": c["email"] or "", "birth_date": c["birth_date"] or "",
            "gender": c["gender"] or "", "has_rx": bool(c["rx"]),
        }

    return {
        "total_rows": len(rows),
        "valid_count": len(valid),
        "error_count": len(errors),
        "has_rx_count": has_rx,
        "detected_columns": headers,
        "sample": [_display(c) for c in valid[:PREVIEW_SAMPLE]],
        "error_preview": errors[:PREVIEW_SAMPLE],
        "limit": {"unlimited": unlimited, "max": None if unlimited else max_p, "current": current, "available": available},
    }


@router.post("/commit")
async def commit_import(request: Request, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    company, plan = await _require_admin_company(user)
    content = await _read_upload(file)
    headers, rows = await asyncio.to_thread(_read_rows, content, file.filename)

    valid, error_rows = [], []
    for excel_row, d in rows:
        clean, err = _validate_row(excel_row, d)
        if err:
            error_rows.append(err)
        else:
            valid.append(clean)

    company_oid = ObjectId(user["company_id"])
    branch_oid = ObjectId(user["branch_id"]) if user.get("branch_id") else None
    actor_oid = ObjectId(user["_id"])
    now_iso = datetime.now(timezone.utc).isoformat()

    max_p = effective_max_patients(company, plan)
    unlimited = max_p <= 0
    current = await db.patients.count_documents({"company_id": company_oid, "is_deleted": {"$ne": True}})
    available = None if unlimited else max(0, max_p - current)

    created = updated = skipped = rx_created = 0
    skipped_rows = []
    seen = {}  # match_key -> patient_id (dentro de esta carga)

    async def _find_existing(clean):
        base = {"company_id": company_oid, "is_deleted": {"$ne": True}}
        if clean["email"]:
            doc = await db.patients.find_one({**base, "email": clean["email"]})
            if doc:
                return doc["_id"]
        doc = await db.patients.find_one({**base, "phone": clean["phone"]})
        return doc["_id"] if doc else None

    async def _create_rx(patient_oid, clean):
        nonlocal rx_created
        rx = clean["rx"]
        rx_doc = {
            "company_id": company_oid, "patient_id": patient_oid, "consultation_id": None,
            "professional_name": None,
            "od_sphere": rx["od_sphere"], "od_cylinder": rx["od_cylinder"], "od_axis": rx["od_axis"],
            "od_addition": rx["od_addition"], "od_dp": None,
            "oi_sphere": rx["oi_sphere"], "oi_cylinder": rx["oi_cylinder"], "oi_axis": rx["oi_axis"],
            "oi_addition": rx["oi_addition"], "oi_dp": None,
            "observations": clean["rx_observations"], "lens_type": None, "frame_type": None,
            "source": "import",
            "created_at": now_iso, "created_by": actor_oid,
        }
        await db.eyeglass_prescriptions.insert_one(rx_doc)
        rx_created += 1

    def _update_set(clean):
        s = {
            "first_name": clean["first_name"], "last_name": clean["last_name"],
            "phone": clean["phone"], "whatsapp": clean["whatsapp"], "updated_at": now_iso,
        }
        if clean["email"]:
            s["email"] = clean["email"]
        if clean["birth_date"]:
            s["birth_date"] = clean["birth_date"]
        if clean["gender"]:
            s["gender"] = clean["gender"]
        if clean["address"]:
            s["address"] = clean["address"]
        return s

    for clean in valid:
        key = clean["match_key"]
        existing_id = seen.get(key)
        is_new = False
        if existing_id is None:
            existing_id = await _find_existing(clean)
        if existing_id is not None:
            await db.patients.update_one({"_id": existing_id}, {"$set": _update_set(clean)})
            updated += 1
            patient_oid = existing_id
        else:
            if not unlimited and available <= 0:
                skipped += 1
                skipped_rows.append({"row": clean["row"], "name": clean["full_name"], "reason": "Tope de pacientes alcanzado"})
                continue
            doc = {
                "company_id": company_oid, "branch_id": branch_oid,
                "first_name": clean["first_name"], "last_name": clean["last_name"], "dpi": None,
                "birth_date": clean["birth_date"], "gender": clean["gender"], "phone": clean["phone"],
                "whatsapp": clean["whatsapp"], "email": clean["email"],
                "address": clean["address"], "city": None, "country": "Guatemala",
                "emergency_contact": None, "emergency_phone": None, "notes": None,
                "source": "import", "created_at": now_iso, "created_by": actor_oid,
            }
            res = await db.patients.insert_one(doc)
            patient_oid = res.inserted_id
            created += 1
            is_new = True
            if not unlimited:
                available -= 1
        seen[key] = patient_oid
        if clean["rx"]:
            await _create_rx(patient_oid, clean)

    if created:
        await _notify_patient_limit(company, plan, user["company_id"])

    await log_audit(
        "PATIENTS_IMPORTED", actor_id=user["_id"], actor_email=user.get("email"),
        actor_role=user["role"], company_id=user["company_id"],
        metadata={"created": created, "updated": updated, "skipped_limit": skipped,
                  "errors": len(error_rows), "prescriptions": rx_created, "filename": file.filename},
        request=request,
    )

    return {
        "total_rows": len(rows),
        "created": created,
        "updated": updated,
        "skipped_limit": skipped,
        "errors": len(error_rows),
        "prescriptions_created": rx_created,
        "error_rows": error_rows,
        "skipped_rows": skipped_rows,
        "limit": {"unlimited": unlimited, "max": None if unlimited else max_p},
    }
