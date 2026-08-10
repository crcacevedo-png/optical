"""Modulo de Jornadas (brigadas visuales / eventos fuera de sucursal).

Una Jornada es un evento de atencion optica realizado fuera de la operacion
habitual (feria, empresa, colegio, municipalidad). Opera como unidad economica
independiente con su propia caja e inventario temporal.

Iteracion 1 (esta): Ciclo de vida completo (CRUD + estados) + listado + summary.
Iteraciones 2-3 anadiran caja propia, inventario, POS y liquidacion.
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user
from audit import log_audit
from models import JornadaCreate, JornadaUpdate, JornadaStatusChange

router = APIRouter(prefix="/jornadas", tags=["Jornadas"])


VALID_STATUSES = {"planificada", "activa", "en_cierre", "cerrada", "cancelada"}


async def _require_module(user: dict) -> None:
    """Verifica que la empresa tenga el modulo `jornadas` en su plan.
    SuperAdmin siempre pasa."""
    if user["role"] == "superadmin":
        return
    if not user.get("company_id"):
        raise HTTPException(status_code=403, detail="Usuario sin empresa asignada")
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])}, {"plan_id": 1})
    if not company or not company.get("plan_id"):
        raise HTTPException(
            status_code=402,
            detail="Modulo Jornadas no disponible en tu plan. Actualiza a Basic o Enterprise.",
        )
    plan = await db.plans.find_one({"_id": company["plan_id"]}, {"modules": 1})
    if not plan or "jornadas" not in (plan.get("modules") or []):
        raise HTTPException(
            status_code=402,
            detail="Modulo Jornadas no disponible en tu plan. Actualiza a Basic o Enterprise.",
        )


async def _get_jornada_or_404(jid: str, company_id: str) -> dict:
    try:
        oid = ObjectId(jid)
    except Exception:
        raise HTTPException(status_code=400, detail="ID invalido")
    query = {"_id": oid, "is_deleted": {"$ne": True}}
    if company_id:
        query["company_id"] = ObjectId(company_id)
    j = await db.jornadas.find_one(query)
    if not j:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    return j


def _serialize(doc: dict) -> dict:
    serialize_doc(doc)
    for key in (
        "responsible_branch_id", "manager_user_id", "created_by",
        "activated_by", "closed_by", "cancelled_by", "reopened_by",
    ):
        v = doc.get(key)
        if isinstance(v, ObjectId):
            doc[key] = str(v)
    # Nested lists of ObjectIds
    if isinstance(doc.get("team_user_ids"), list):
        doc["team_user_ids"] = [str(x) if isinstance(x, ObjectId) else x for x in doc["team_user_ids"]]
    return doc


async def _hydrate_branch_name(j: dict) -> None:
    """Adjunta responsible_branch_name para el listado."""
    bid = j.get("responsible_branch_id")
    if bid:
        try:
            branch = await db.branches.find_one({"_id": ObjectId(bid)}, {"name": 1})
            if branch:
                j["responsible_branch_name"] = branch["name"]
        except Exception:
            pass


# ─── LISTAR ────────────────────────────────────────────────────────────
@router.get("")
async def list_jornadas(
    user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="planificada|activa|en_cierre|cerrada|cancelada"),
    branch_id: Optional[str] = None,
    from_date: Optional[str] = Query(None, description="ISO YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="ISO YYYY-MM-DD"),
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    await _require_module(user)
    company_id = user.get("company_id")
    if user["role"] != "superadmin" and not company_id:
        raise HTTPException(status_code=403, detail="Sin empresa asignada")

    query: dict = {"is_deleted": {"$ne": True}}
    if company_id:
        query["company_id"] = ObjectId(company_id)
    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Estado invalido: {status}")
        query["status"] = status
    if branch_id:
        try:
            query["responsible_branch_id"] = ObjectId(branch_id)
        except Exception:
            raise HTTPException(status_code=400, detail="branch_id invalido")
    if from_date or to_date:
        date_q = {}
        if from_date:
            date_q["$gte"] = from_date
        if to_date:
            date_q["$lte"] = to_date
        query["start_date"] = date_q
    if search:
        query["name"] = {"$regex": search, "$options": "i"}

    total = await db.jornadas.count_documents(query)
    items = await (
        db.jornadas.find(query)
        .sort("start_date", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )
    for j in items:
        _serialize(j)
        await _hydrate_branch_name(j)
        # Totales operativos (defaults 0 hasta que Iter 2 los llene)
        j["total_sold"] = float(j.get("total_sold") or 0)
        j["patients_count"] = int(j.get("patients_count") or 0)
        j["cash_balance"] = float(j.get("cash_balance") or 0)

    return {"total": total, "items": items, "limit": limit, "skip": skip}


# ─── CREAR ─────────────────────────────────────────────────────────────
@router.post("")
async def create_jornada(
    data: JornadaCreate,
    request: Request,
    user: dict = Depends(get_current_user),
):
    await _require_module(user)
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Solo administradores pueden crear jornadas")
    company_id = user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="Sin empresa asignada")

    # Validar fechas
    if data.end_date < data.start_date:
        raise HTTPException(status_code=400, detail="end_date no puede ser anterior a start_date")

    # Validar sucursal existe y pertenece a la empresa
    try:
        branch_oid = ObjectId(data.responsible_branch_id)
    except Exception:
        raise HTTPException(status_code=400, detail="responsible_branch_id invalido")
    branch = await db.branches.find_one(
        {"_id": branch_oid, "company_id": ObjectId(company_id)}
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "company_id": ObjectId(company_id),
        "responsible_branch_id": branch_oid,
        "name": data.name.strip(),
        "start_date": data.start_date,
        "end_date": data.end_date,
        "location": data.location,
        "address": data.address,
        "municipality": data.municipality,
        "department": data.department,
        "partner_entity": data.partner_entity,
        "manager_user_id": ObjectId(data.manager_user_id) if data.manager_user_id else None,
        "team_user_ids": [ObjectId(u) for u in (data.team_user_ids or [])],
        "description": data.description,
        "cash_config": data.cash_config.model_dump(),
        "inventory_config": data.inventory_config.model_dump(),
        "price_list_discount_percent": data.price_list_discount_percent,
        "goal_amount": data.goal_amount,
        "goal_patients": data.goal_patients,
        # Ciclo de vida
        "status": "planificada",
        "activated_at": None,
        "activated_by": None,
        "closed_at": None,
        "closed_by": None,
        "cancelled_at": None,
        "cancelled_by": None,
        # Contadores agregados (iteraciones futuras)
        "total_sold": 0.0,
        "patients_count": 0,
        "cash_balance": 0.0,
        "sales_count": 0,
        # Auditoria
        "created_by": ObjectId(user["_id"]),
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
    }
    result = await db.jornadas.insert_one(doc)
    jid = str(result.inserted_id)

    await log_audit(
        action="JORNADA_CREATED",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=company_id, target_id=jid, target_type="jornada",
        metadata={"name": data.name, "start_date": data.start_date, "end_date": data.end_date},
        request=request,
    )
    return {"_id": jid, "message": "Jornada creada"}


# ─── DETALLE ───────────────────────────────────────────────────────────
@router.get("/{jid}")
async def get_jornada(jid: str, user: dict = Depends(get_current_user)):
    await _require_module(user)
    j = await _get_jornada_or_404(jid, user.get("company_id"))
    _serialize(j)
    await _hydrate_branch_name(j)
    # Adjuntar nombre del manager si aplica
    if j.get("manager_user_id"):
        mgr = await db.users.find_one({"_id": ObjectId(j["manager_user_id"])}, {"name": 1})
        if mgr:
            j["manager_name"] = mgr.get("name")
    return j


# ─── ACTUALIZAR ────────────────────────────────────────────────────────
@router.put("/{jid}")
async def update_jornada(
    jid: str, data: JornadaUpdate, request: Request,
    user: dict = Depends(get_current_user),
):
    await _require_module(user)
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Solo administradores pueden editar")
    j = await _get_jornada_or_404(jid, user.get("company_id"))
    if j["status"] not in ("planificada", "activa"):
        raise HTTPException(
            status_code=400,
            detail=f"No se puede editar una jornada en estado {j['status']}",
        )

    update = data.model_dump(exclude_unset=True)
    # Convertir IDs a ObjectId
    if "responsible_branch_id" in update and update["responsible_branch_id"]:
        try:
            update["responsible_branch_id"] = ObjectId(update["responsible_branch_id"])
        except Exception:
            raise HTTPException(status_code=400, detail="responsible_branch_id invalido")
    if "manager_user_id" in update:
        update["manager_user_id"] = ObjectId(update["manager_user_id"]) if update["manager_user_id"] else None
    if "team_user_ids" in update and isinstance(update["team_user_ids"], list):
        update["team_user_ids"] = [ObjectId(u) for u in update["team_user_ids"]]
    if "cash_config" in update and update["cash_config"] is not None:
        # ya viene como dict tras model_dump
        pass
    if "inventory_config" in update and update["inventory_config"] is not None:
        pass
    if "start_date" in update and "end_date" in update and update["end_date"] < update["start_date"]:
        raise HTTPException(status_code=400, detail="end_date no puede ser anterior a start_date")
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.jornadas.update_one({"_id": j["_id"]}, {"$set": update})
    await log_audit(
        action="JORNADA_UPDATED",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=jid, target_type="jornada",
        metadata={"fields": list(update.keys())}, request=request,
    )
    return {"message": "Jornada actualizada"}


# ─── ELIMINAR (soft) ───────────────────────────────────────────────────
@router.delete("/{jid}")
async def delete_jornada(jid: str, request: Request, user: dict = Depends(get_current_user)):
    await _require_module(user)
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Acceso denegado")
    j = await _get_jornada_or_404(jid, user.get("company_id"))
    if j["status"] not in ("planificada", "cancelada"):
        raise HTTPException(
            status_code=400,
            detail="Solo se puede eliminar una jornada Planificada o Cancelada",
        )
    if int(j.get("sales_count") or 0) > 0 or int(j.get("patients_count") or 0) > 0:
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar: la jornada tiene ventas o pacientes registrados",
        )
    await db.jornadas.update_one(
        {"_id": j["_id"]},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc).isoformat()}},
    )
    await log_audit(
        action="JORNADA_DELETED",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=jid, target_type="jornada",
        metadata={"name": j.get("name")}, request=request,
    )
    return {"message": "Jornada eliminada"}


# ─── TRANSICIONES DE ESTADO ────────────────────────────────────────────
async def _change_status(
    jid: str, new_status: str, allowed_from: set,
    audit_action: str, extra_fields: dict,
    user: dict, request: Request, reason: Optional[str] = None,
):
    j = await _get_jornada_or_404(jid, user.get("company_id"))
    if j["status"] not in allowed_from:
        raise HTTPException(
            status_code=400,
            detail=f"Transicion invalida: {j['status']} -> {new_status}",
        )
    now = datetime.now(timezone.utc).isoformat()
    set_fields = {"status": new_status, "updated_at": now, **extra_fields}
    await db.jornadas.update_one({"_id": j["_id"]}, {"$set": set_fields})
    await log_audit(
        action=audit_action,
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=jid, target_type="jornada",
        metadata={"from": j["status"], "to": new_status, "reason": reason, "name": j.get("name")},
        request=request,
    )
    return {"message": f"Jornada -> {new_status}"}


@router.post("/{jid}/activate")
async def activate_jornada(jid: str, request: Request, user: dict = Depends(get_current_user)):
    """Planificada -> Activa. Advierte si aun no llego la fecha de inicio."""
    await _require_module(user)
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Solo administradores")
    j = await _get_jornada_or_404(jid, user.get("company_id"))
    # Validacion de configuracion minima
    inv = j.get("inventory_config") or {}
    if not (inv.get("use_branch_stock") or inv.get("use_consignment")):
        raise HTTPException(
            status_code=400,
            detail="Configura al menos una fuente de inventario antes de activar",
        )
    warnings = []
    today = datetime.now(timezone.utc).date().isoformat()
    if j.get("start_date") and today < j["start_date"]:
        warnings.append(f"La jornada aun no comienza (inicia {j['start_date']})")
    now = datetime.now(timezone.utc).isoformat()
    res = await _change_status(
        jid, "activa", {"planificada"}, "JORNADA_ACTIVATED",
        {"activated_at": now, "activated_by": ObjectId(user["_id"])},
        user, request,
    )
    res["warnings"] = warnings
    return res


@router.post("/{jid}/start-closing")
async def start_closing(jid: str, request: Request, user: dict = Depends(get_current_user)):
    """Activa -> En cierre. Detiene operacion, pendiente de arqueo/liquidacion."""
    await _require_module(user)
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Solo administradores")
    return await _change_status(
        jid, "en_cierre", {"activa"}, "JORNADA_START_CLOSING", {}, user, request,
    )


@router.post("/{jid}/close")
async def close_jornada(
    jid: str, request: Request, user: dict = Depends(get_current_user),
):
    """En cierre -> Cerrada. Valida caja cerrada (si es propia) y devuelve
    inventario remanente de sucursal automaticamente."""
    await _require_module(user)
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Solo administradores")
    j = await _get_jornada_or_404(jid, user.get("company_id"))
    if j["status"] != "en_cierre":
        raise HTTPException(
            status_code=400,
            detail=f"Transicion invalida: {j['status']} -> cerrada. Inicia el cierre primero.",
        )

    # Validacion 1: si tiene caja propia, debe estar cerrada
    if (j.get("cash_config") or {}).get("mode") == "own":
        open_reg = await db.cash_registers.find_one({
            "company_id": ObjectId(user["company_id"]),
            "jornada_id": j["_id"], "status": "open",
        })
        if open_reg:
            raise HTTPException(
                status_code=400,
                detail="La caja de la jornada esta abierta. Ciera la caja antes de finalizar.",
            )

    # Validacion 2: ventas en borrador (por si en el futuro se agregan)
    draft_sales = await db.sales.count_documents({
        "company_id": ObjectId(user["company_id"]),
        "jornada_id": j["_id"], "status": "borrador",
    })
    if draft_sales > 0:
        raise HTTPException(status_code=400, detail=f"Hay {draft_sales} venta(s) en borrador")

    # Devolucion automatica del remanente de sucursal (si hay)
    company_oid = ObjectId(user["company_id"])
    remaining = await db.jornada_stock.find({
        "company_id": company_oid, "jornada_id": j["_id"],
        "source": "branch", "current_qty": {"$gt": 0},
    }).to_list(2000)
    now_iso = datetime.now(timezone.utc).isoformat()
    returned_count = 0
    for row in remaining:
        qty = int(row.get("current_qty") or 0)
        if qty <= 0:
            continue
        src_bid = row.get("source_branch_id")
        pid = row.get("product_id")
        stock_row = await db.stock.find_one({
            "company_id": company_oid, "branch_id": src_bid, "product_id": pid,
        })
        if stock_row:
            await db.stock.update_one({"_id": stock_row["_id"]}, {"$inc": {"quantity": qty}})
        else:
            await db.stock.insert_one({
                "company_id": company_oid, "branch_id": src_bid,
                "product_id": pid, "quantity": qty, "created_at": now_iso,
            })
        await db.inventory_movements.insert_one({
            "company_id": company_oid, "branch_id": src_bid, "product_id": pid,
            "type": "entrada", "quantity": qty,
            "notes": f"Devolucion desde Jornada: {j.get('name','')} (cierre)",
            "reference": jid, "reference_type": "jornada_return",
            "created_at": now_iso, "created_by": ObjectId(user["_id"]),
        })
        await db.jornada_stock.update_one(
            {"_id": row["_id"]},
            {"$set": {"current_qty": 0, "returned_qty": qty, "updated_at": now_iso}},
        )
        returned_count += 1

    res = await _change_status(
        jid, "cerrada", {"en_cierre"}, "JORNADA_CLOSED",
        {"closed_at": now_iso, "closed_by": ObjectId(user["_id"])},
        user, request,
    )
    res["returned_products"] = returned_count

    # Liquidacion de consignacion (info al cerrar)
    consign_count = await db.jornada_stock.count_documents({
        "company_id": company_oid, "jornada_id": j["_id"], "source": "consignment",
    })
    if consign_count > 0:
        res["consignment_liquidation_hint"] = (
            "Consulta /api/jornadas/{id}/liquidation y descarga el reporte PDF/Excel"
        )
    return res


@router.post("/{jid}/cancel")
async def cancel_jornada(
    jid: str, data: JornadaStatusChange, request: Request,
    user: dict = Depends(get_current_user),
):
    """Planificada -> Cancelada. Solo si no tiene ventas ni pacientes."""
    await _require_module(user)
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Solo administradores")
    j = await _get_jornada_or_404(jid, user.get("company_id"))
    if int(j.get("sales_count") or 0) > 0 or int(j.get("patients_count") or 0) > 0:
        raise HTTPException(
            status_code=400,
            detail="No se puede cancelar: la jornada tiene ventas o pacientes registrados",
        )
    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="Motivo obligatorio para cancelar")
    now = datetime.now(timezone.utc).isoformat()
    return await _change_status(
        jid, "cancelada", {"planificada", "activa"}, "JORNADA_CANCELLED",
        {
            "cancelled_at": now,
            "cancelled_by": ObjectId(user["_id"]),
            "cancel_reason": data.reason.strip(),
        },
        user, request, reason=data.reason,
    )


@router.post("/{jid}/reopen")
async def reopen_jornada(
    jid: str, data: JornadaStatusChange, request: Request,
    user: dict = Depends(get_current_user),
):
    """Cerrada -> En cierre. Requiere superadmin y motivo. Queda auditado."""
    await _require_module(user)
    if user["role"] != "superadmin":
        raise HTTPException(
            status_code=403,
            detail="Solo un SuperAdmin puede reabrir una jornada cerrada",
        )
    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="Motivo obligatorio para reabrir")
    now = datetime.now(timezone.utc).isoformat()
    return await _change_status(
        jid, "en_cierre", {"cerrada"}, "JORNADA_REOPENED",
        {
            "reopened_at": now,
            "reopened_by": ObjectId(user["_id"]),
            "reopen_reason": data.reason.strip(),
        },
        user, request, reason=data.reason,
    )


# ─── RESUMEN OPERATIVO ─────────────────────────────────────────────────
@router.get("/{jid}/summary")
async def get_summary(jid: str, user: dict = Depends(get_current_user)):
    """Resumen para el panel principal de la jornada.
    Iter 1: contadores basicos (0 hasta que las iteraciones 2-3 los llenen)."""
    await _require_module(user)
    j = await _get_jornada_or_404(jid, user.get("company_id"))
    _serialize(j)
    await _hydrate_branch_name(j)
    return {
        "jornada": j,
        "kpis": {
            "total_sold": float(j.get("total_sold") or 0),
            "sales_count": int(j.get("sales_count") or 0),
            "patients_count": int(j.get("patients_count") or 0),
            "cash_balance": float(j.get("cash_balance") or 0),
            "goal_amount": j.get("goal_amount"),
            "goal_patients": j.get("goal_patients"),
            "goal_amount_pct": (
                round((float(j.get("total_sold") or 0) / float(j["goal_amount"])) * 100, 1)
                if j.get("goal_amount") else None
            ),
            "goal_patients_pct": (
                round((int(j.get("patients_count") or 0) / int(j["goal_patients"])) * 100, 1)
                if j.get("goal_patients") else None
            ),
        },
    }
