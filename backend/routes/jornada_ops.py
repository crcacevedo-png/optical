"""Modulo de operaciones de la Jornada (Iteracion 2).

Cubre: Caja propia, Inventario (traslado desde sucursal), Punto de Venta, Pacientes.

Colecciones nuevas:
- `jornada_stock`: inventario de la jornada. Doc = {company_id, jornada_id, product_id,
    source, source_branch_id, initial_qty, current_qty, sold_qty, returned_qty,
    adjusted_qty, unit_cost, unit_price, ...}
- `jornada_transfers`: historial de traslados y ajustes.

Colecciones reutilizadas con campo `jornada_id`:
- `cash_registers`: caja con `jornada_id` = jornada-owned.
- `sales`: ventas con `jornada_id` marcan que es venta de jornada.
- `patients`: campos `jornada_id_first` (primera captacion) + `jornada_ids` (lista).
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

from db import db, serialize_doc
from auth_utils import get_current_user
from audit import log_audit

router = APIRouter(prefix="/jornadas", tags=["Jornadas - Operaciones"])


# ───────────────────────── HELPERS ─────────────────────────
async def _get_jornada_active_or_400(jid: str, company_id: str, allow_states: set) -> dict:
    try:
        oid = ObjectId(jid)
    except Exception:
        raise HTTPException(status_code=400, detail="jornada_id invalido")
    j = await db.jornadas.find_one(
        {"_id": oid, "company_id": ObjectId(company_id), "is_deleted": {"$ne": True}}
    )
    if not j:
        raise HTTPException(status_code=404, detail="Jornada no encontrada")
    if j["status"] not in allow_states:
        raise HTTPException(
            status_code=400,
            detail=f"Operacion no permitida en estado {j['status']}",
        )
    return j


def _svc(doc: dict) -> dict:
    """Serializa ObjectIds comunes recursivamente en el nivel superior."""
    if not doc:
        return doc
    serialize_doc(doc)
    for key in list(doc.keys()):
        v = doc[key]
        if isinstance(v, ObjectId):
            doc[key] = str(v)
        elif isinstance(v, list):
            doc[key] = [str(x) if isinstance(x, ObjectId) else x for x in v]
    return doc


# ═══════════════════════════════════════════════════════════════════════
# CAJA DE LA JORNADA
# ═══════════════════════════════════════════════════════════════════════
class JCashOpen(BaseModel):
    opening_amount: float = 0
    notes: Optional[str] = None


class JCashMovement(BaseModel):
    kind: Literal["ingreso", "egreso"]
    amount: float = Field(..., gt=0)
    method: str = "cash"  # cash | card | transfer | check | other
    description: str
    category: Optional[str] = None  # transporte, alimentacion, viaticos, alquiler, publicidad, colaboradores, otro
    reference: Optional[str] = None
    receipt_url: Optional[str] = None


class JCashClose(BaseModel):
    counted_cash: float
    counted_notes: Optional[str] = None
    transfer_to_branch: bool = True  # transfiere neto de efectivo a caja sucursal


async def _compute_jornada_cash_totals(jornada_id: ObjectId, register: dict) -> dict:
    """Suma ventas de la jornada + movimientos manuales de la caja."""
    # Ventas de la jornada (todas, no solo por ventana - la caja es exclusiva)
    sales = await db.sales.find(
        {"jornada_id": jornada_id, "status": {"$ne": "cancelada"}}
    ).to_list(2000)
    totals_by_method = {"cash": 0.0, "card": 0.0, "transfer": 0.0, "check": 0.0, "other": 0.0}
    total_sales = 0.0
    receivables_total = 0.0
    for s in sales:
        for p in (s.get("payments") or []):
            m = (p.get("method") or "cash").lower()
            if m not in totals_by_method:
                m = "other"
            totals_by_method[m] += float(p.get("amount") or 0)
        total_sales += float(s.get("total") or 0)
        receivables_total += float(s.get("balance") or 0)

    # Movimientos manuales (embebidos en el registro de caja)
    ingresos_extra = 0.0
    egresos_total = 0.0
    egresos_by_category: dict = {}
    for m in (register.get("movements") or []):
        amt = float(m.get("amount") or 0)
        if m.get("kind") == "ingreso":
            ingresos_extra += amt
            method_key = (m.get("method") or "cash").lower()
            if method_key not in totals_by_method:
                method_key = "other"
            totals_by_method[method_key] += amt
        else:  # egreso
            egresos_total += amt
            cat = m.get("category") or "otro"
            egresos_by_category[cat] = round(egresos_by_category.get(cat, 0) + amt, 2)

    opening = float(register.get("opening_amount") or 0)
    expected_cash = round(opening + totals_by_method["cash"] - egresos_total, 2)
    return {
        "opening_amount": opening,
        "totals_by_method": {k: round(v, 2) for k, v in totals_by_method.items()},
        "sales_count": len(sales),
        "sales_total": round(total_sales, 2),
        "receivables_total": round(receivables_total, 2),
        "ingresos_extra": round(ingresos_extra, 2),
        "egresos_total": round(egresos_total, 2),
        "egresos_by_category": egresos_by_category,
        "expected_cash": expected_cash,
    }


@router.post("/{jid}/cash/open")
async def open_cash(jid: str, data: JCashOpen, request: Request, user: dict = Depends(get_current_user)):
    j = await _get_jornada_active_or_400(jid, user["company_id"], {"planificada", "activa"})
    if (j.get("cash_config") or {}).get("mode") != "own":
        raise HTTPException(
            status_code=400,
            detail="Esta jornada usa la caja de la sucursal — no se abre caja propia.",
        )
    existing = await db.cash_registers.find_one({
        "company_id": ObjectId(user["company_id"]),
        "jornada_id": j["_id"],
        "status": "open",
    })
    if existing:
        raise HTTPException(status_code=400, detail="La caja de la jornada ya esta abierta")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": j["responsible_branch_id"],
        "jornada_id": j["_id"],
        "status": "open",
        "opening_amount": float(data.opening_amount or 0),
        "opening_notes": data.notes or "",
        "opened_at": now,
        "opened_by": ObjectId(user["_id"]),
        "opened_by_name": user.get("name", ""),
        "movements": [],
    }
    res = await db.cash_registers.insert_one(doc)
    await log_audit(
        "JORNADA_CASH_OPENED", actor_id=user["_id"], actor_email=user.get("email"),
        actor_role=user["role"], company_id=user.get("company_id"),
        target_id=str(res.inserted_id), target_type="cash_register",
        metadata={"jornada_id": jid, "opening_amount": doc["opening_amount"]},
        request=request,
    )
    doc["_id"] = str(res.inserted_id)
    return {"message": "Caja de jornada abierta", "register": _svc(doc)}


@router.get("/{jid}/cash")
async def get_cash_state(jid: str, user: dict = Depends(get_current_user)):
    """Estado actual de la caja de la jornada (abierta o cerrada mas reciente)."""
    # Validar que la jornada pertenece a la empresa del usuario (multi-tenant)
    await _get_jornada_active_or_400(jid, user["company_id"], {"planificada", "activa", "en_cierre", "cerrada", "cancelada"})
    joid = ObjectId(jid)
    reg = await db.cash_registers.find_one(
        {"company_id": ObjectId(user["company_id"]), "jornada_id": joid},
        sort=[("opened_at", -1)],
    )
    if not reg:
        return {"register": None, "totals": None}
    totals = await _compute_jornada_cash_totals(joid, reg)
    _svc(reg)
    return {"register": reg, "totals": totals}


@router.post("/{jid}/cash/movements")
async def add_cash_movement(
    jid: str, data: JCashMovement, request: Request,
    user: dict = Depends(get_current_user),
):
    j = await _get_jornada_active_or_400(jid, user["company_id"], {"activa", "en_cierre"})
    reg = await db.cash_registers.find_one({
        "company_id": ObjectId(user["company_id"]),
        "jornada_id": j["_id"],
        "status": "open",
    })
    if not reg:
        raise HTTPException(status_code=400, detail="Abre la caja antes de registrar movimientos")
    now = datetime.now(timezone.utc).isoformat()
    mv = {
        "id": str(ObjectId()),
        "kind": data.kind,
        "amount": float(data.amount),
        "method": data.method,
        "description": data.description,
        "category": data.category,
        "reference": data.reference,
        "receipt_url": data.receipt_url,
        "created_at": now,
        "created_by": str(user["_id"]),
        "created_by_name": user.get("name", ""),
    }
    await db.cash_registers.update_one(
        {"_id": reg["_id"]}, {"$push": {"movements": mv}}
    )
    await log_audit(
        "JORNADA_CASH_MOVEMENT",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=str(reg["_id"]),
        target_type="cash_register",
        metadata={"jornada_id": jid, "kind": data.kind, "amount": data.amount, "category": data.category},
        request=request,
    )
    return {"message": "Movimiento registrado", "movement": mv}


@router.post("/{jid}/cash/close")
async def close_jornada_cash(
    jid: str, data: JCashClose, request: Request,
    user: dict = Depends(get_current_user),
):
    """Arqueo + cierre. Compara conteo fisico vs esperado. Requiere motivo si difiere."""
    j = await _get_jornada_active_or_400(jid, user["company_id"], {"activa", "en_cierre"})
    reg = await db.cash_registers.find_one({
        "company_id": ObjectId(user["company_id"]),
        "jornada_id": j["_id"],
        "status": "open",
    })
    if not reg:
        raise HTTPException(status_code=400, detail="No hay caja abierta para esta jornada")
    totals = await _compute_jornada_cash_totals(j["_id"], reg)
    diff = round(float(data.counted_cash or 0) - float(totals["expected_cash"] or 0), 2)
    if abs(diff) > 0.01 and not (data.counted_notes or "").strip():
        raise HTTPException(status_code=400, detail=f"Diferencia de Q{diff}. Ingresa un motivo/justificacion.")
    now = datetime.now(timezone.utc).isoformat()
    set_fields = {
        "status": "closed",
        "closed_at": now,
        "closed_by": ObjectId(user["_id"]),
        "closed_by_name": user.get("name", ""),
        "counted_cash": float(data.counted_cash),
        "counted_notes": data.counted_notes or "",
        "diff": diff,
        "close_totals": totals,
    }
    await db.cash_registers.update_one({"_id": reg["_id"]}, {"$set": set_fields})

    # Si pide transfer_to_branch y el neto es positivo -> movimiento en la caja
    # abierta de la sucursal responsable (si existe).
    net_cash = round(float(totals["totals_by_method"]["cash"]) + float(totals["opening_amount"]) - float(totals["egresos_total"]), 2)
    if data.transfer_to_branch and net_cash > 0:
        branch_reg = await db.cash_registers.find_one({
            "company_id": ObjectId(user["company_id"]),
            "branch_id": j["responsible_branch_id"],
            "jornada_id": {"$exists": False},
            "status": "open",
        })
        if branch_reg:
            mv = {
                "id": str(ObjectId()),
                "kind": "ingreso",
                "amount": net_cash,
                "method": "cash",
                "description": f"Traslado neto de Jornada: {j.get('name','')}",
                "category": "traslado_jornada",
                "reference": jid,
                "created_at": now,
                "created_by": str(user["_id"]),
                "created_by_name": user.get("name", ""),
            }
            await db.cash_registers.update_one({"_id": branch_reg["_id"]}, {"$push": {"movements": mv}})

    # Actualizar la jornada con contadores agregados
    await db.jornadas.update_one(
        {"_id": j["_id"]},
        {"$set": {
            "cash_balance": net_cash,
            "total_sold": totals["sales_total"],
            "sales_count": totals["sales_count"],
            "updated_at": now,
        }},
    )
    await log_audit(
        "JORNADA_CASH_CLOSED",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=str(reg["_id"]),
        target_type="cash_register",
        metadata={"jornada_id": jid, "diff": diff, "net_cash": net_cash},
        request=request,
    )
    return {"message": "Caja de jornada cerrada", "diff": diff, "net_cash": net_cash, "totals": totals}


# ═══════════════════════════════════════════════════════════════════════
# INVENTARIO DE LA JORNADA (Traslado desde sucursal)
# ═══════════════════════════════════════════════════════════════════════
class TransferItem(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0)


class TransferRequest(BaseModel):
    source_branch_id: str
    items: List[TransferItem]
    notes: Optional[str] = None


class InventoryAdjust(BaseModel):
    product_id: str
    delta: int  # + o - (unidades)
    reason: str  # dano, perdida, obsequio, correccion_conteo, otro
    notes: Optional[str] = None


@router.post("/{jid}/inventory/transfer")
async def transfer_from_branch(
    jid: str, data: TransferRequest, request: Request,
    user: dict = Depends(get_current_user),
):
    j = await _get_jornada_active_or_400(jid, user["company_id"], {"planificada", "activa"})
    inv_cfg = j.get("inventory_config") or {}
    if not inv_cfg.get("use_branch_stock"):
        raise HTTPException(status_code=400, detail="La jornada no acepta traslado desde sucursal")

    try:
        src_bid = ObjectId(data.source_branch_id)
    except Exception:
        raise HTTPException(status_code=400, detail="source_branch_id invalido")

    # Validar que la sucursal fuente pertenece a la empresa
    src = await db.branches.find_one(
        {"_id": src_bid, "company_id": ObjectId(user["company_id"])}
    )
    if not src:
        raise HTTPException(status_code=404, detail="Sucursal fuente no encontrada")

    now = datetime.now(timezone.utc).isoformat()
    company_oid = ObjectId(user["company_id"])
    transferred: List[dict] = []
    errors: List[dict] = []

    for it in data.items:
        try:
            pid = ObjectId(it.product_id)
        except Exception:
            errors.append({"product_id": it.product_id, "error": "id invalido"})
            continue
        # Validar stock disponible en sucursal
        stock = await db.stock.find_one(
            {"company_id": company_oid, "branch_id": src_bid, "product_id": pid}
        )
        available = int((stock or {}).get("quantity") or 0)
        if available < it.quantity:
            errors.append({
                "product_id": it.product_id,
                "error": f"Stock insuficiente ({available} disponible, se piden {it.quantity})",
            })
            continue
        # Descontar de la sucursal
        await db.stock.update_one(
            {"_id": stock["_id"]}, {"$inc": {"quantity": -it.quantity}}
        )
        await db.inventory_movements.insert_one({
            "company_id": company_oid,
            "branch_id": src_bid,
            "product_id": pid,
            "type": "salida",
            "quantity": it.quantity,
            "notes": f"Traslado a Jornada: {j.get('name','')}",
            "reference": jid,
            "reference_type": "jornada_transfer",
            "created_at": now,
            "created_by": ObjectId(user["_id"]),
        })
        # Acumular en jornada_stock (upsert). Traer info de producto para snapshot.
        product = await db.products.find_one({"_id": pid}) or {}
        existing = await db.jornada_stock.find_one({
            "jornada_id": j["_id"], "product_id": pid, "source": "branch",
        })
        if existing:
            await db.jornada_stock.update_one(
                {"_id": existing["_id"]},
                {"$inc": {"initial_qty": it.quantity, "current_qty": it.quantity}, "$set": {"updated_at": now}},
            )
        else:
            await db.jornada_stock.insert_one({
                "company_id": company_oid,
                "jornada_id": j["_id"],
                "product_id": pid,
                "source": "branch",
                "source_branch_id": src_bid,
                "initial_qty": it.quantity,
                "current_qty": it.quantity,
                "sold_qty": 0,
                "returned_qty": 0,
                "adjusted_qty": 0,
                "unit_cost": float(product.get("cost") or 0),
                "unit_price": float(product.get("sale_price") or product.get("price") or 0),
                "product_name": product.get("name") or "",
                "product_sku": product.get("sku") or "",
                "product_category": product.get("category") or "",
                "product_brand": product.get("brand") or "",
                "created_at": now,
                "updated_at": now,
            })
        # Registro de traslado (audit)
        await db.jornada_transfers.insert_one({
            "company_id": company_oid,
            "jornada_id": j["_id"],
            "product_id": pid,
            "product_name": product.get("name") or "",
            "quantity": it.quantity,
            "kind": "in",  # entrada a la jornada
            "source_branch_id": src_bid,
            "unit_cost": float(product.get("cost") or 0),
            "unit_price": float(product.get("sale_price") or product.get("price") or 0),
            "notes": data.notes,
            "created_at": now,
            "created_by": ObjectId(user["_id"]),
        })
        transferred.append({"product_id": it.product_id, "quantity": it.quantity, "product_name": product.get("name") or ""})

    await log_audit(
        "JORNADA_INV_TRANSFER",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=jid, target_type="jornada",
        metadata={"source_branch_id": data.source_branch_id, "items": len(transferred), "errors": len(errors)},
        request=request,
    )
    return {
        "message": f"{len(transferred)} producto(s) trasladado(s)",
        "transferred": transferred,
        "errors": errors,
    }


@router.get("/{jid}/inventory")
async def list_jornada_inventory(
    jid: str, user: dict = Depends(get_current_user),
    search: Optional[str] = None,
):
    j = await _get_jornada_active_or_400(jid, user["company_id"], {"planificada", "activa", "en_cierre", "cerrada", "cancelada"})
    q = {"company_id": ObjectId(user["company_id"]), "jornada_id": j["_id"]}
    if search:
        q["$or"] = [
            {"product_name": {"$regex": search, "$options": "i"}},
            {"product_sku": {"$regex": search, "$options": "i"}},
            {"product_brand": {"$regex": search, "$options": "i"}},
        ]
    items = await db.jornada_stock.find(q).sort("product_name", 1).to_list(2000)
    total_value = 0.0
    for it in items:
        _svc(it)
        total_value += float(it.get("current_qty") or 0) * float(it.get("unit_price") or 0)
    return {"items": items, "total_units": sum(int(i.get("current_qty") or 0) for i in items), "total_value": round(total_value, 2)}


@router.post("/{jid}/inventory/adjust")
async def adjust_inventory(
    jid: str, data: InventoryAdjust, request: Request,
    user: dict = Depends(get_current_user),
):
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Solo admin puede ajustar inventario")
    j = await _get_jornada_active_or_400(jid, user["company_id"], {"activa", "en_cierre"})
    try:
        pid = ObjectId(data.product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="product_id invalido")
    row = await db.jornada_stock.find_one({"jornada_id": j["_id"], "product_id": pid})
    if not row:
        raise HTTPException(status_code=404, detail="Producto no esta en el inventario de la jornada")
    new_qty = int(row.get("current_qty") or 0) + data.delta
    if new_qty < 0:
        raise HTTPException(status_code=400, detail="Ajuste dejaria el stock en negativo")
    if not (data.reason or "").strip():
        raise HTTPException(status_code=400, detail="El motivo es obligatorio")
    now = datetime.now(timezone.utc).isoformat()
    await db.jornada_stock.update_one(
        {"_id": row["_id"]},
        {"$inc": {"current_qty": data.delta, "adjusted_qty": abs(data.delta)}, "$set": {"updated_at": now}},
    )
    await db.jornada_transfers.insert_one({
        "company_id": ObjectId(user["company_id"]),
        "jornada_id": j["_id"],
        "product_id": pid,
        "product_name": row.get("product_name") or "",
        "quantity": abs(data.delta),
        "kind": "adjust",
        "delta": data.delta,
        "reason": data.reason,
        "notes": data.notes,
        "created_at": now,
        "created_by": ObjectId(user["_id"]),
    })
    await log_audit(
        "JORNADA_INV_ADJUST",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=jid, target_type="jornada",
        metadata={"product_id": data.product_id, "delta": data.delta, "reason": data.reason},
        request=request,
    )
    return {"message": "Ajuste registrado", "new_qty": new_qty}


@router.post("/{jid}/inventory/return")
async def return_to_branch(
    jid: str, request: Request, user: dict = Depends(get_current_user),
):
    """Devuelve el remanente de fuente 'branch' a la sucursal origen mediante
    traslado inverso. Se llama automaticamente en el cierre (o manualmente)."""
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Solo admin")
    j = await _get_jornada_active_or_400(jid, user["company_id"], {"activa", "en_cierre"})
    company_oid = ObjectId(user["company_id"])
    now = datetime.now(timezone.utc).isoformat()
    returned: List[dict] = []
    rows = await db.jornada_stock.find({
        "company_id": company_oid, "jornada_id": j["_id"],
        "source": "branch", "current_qty": {"$gt": 0},
    }).to_list(2000)
    for row in rows:
        qty = int(row.get("current_qty") or 0)
        if qty <= 0:
            continue
        src_bid = row.get("source_branch_id")
        pid = row.get("product_id")
        # Reinyectar a stock
        stock_row = await db.stock.find_one({
            "company_id": company_oid, "branch_id": src_bid, "product_id": pid,
        })
        if stock_row:
            await db.stock.update_one({"_id": stock_row["_id"]}, {"$inc": {"quantity": qty}})
        else:
            await db.stock.insert_one({
                "company_id": company_oid, "branch_id": src_bid,
                "product_id": pid, "quantity": qty, "created_at": now,
            })
        await db.inventory_movements.insert_one({
            "company_id": company_oid, "branch_id": src_bid, "product_id": pid,
            "type": "entrada", "quantity": qty,
            "notes": f"Devolucion desde Jornada: {j.get('name','')}",
            "reference": jid, "reference_type": "jornada_return",
            "created_at": now, "created_by": ObjectId(user["_id"]),
        })
        await db.jornada_stock.update_one(
            {"_id": row["_id"]},
            {"$set": {"current_qty": 0, "returned_qty": qty, "updated_at": now}},
        )
        await db.jornada_transfers.insert_one({
            "company_id": company_oid, "jornada_id": j["_id"], "product_id": pid,
            "product_name": row.get("product_name") or "",
            "quantity": qty, "kind": "out_return", "source_branch_id": src_bid,
            "created_at": now, "created_by": ObjectId(user["_id"]),
        })
        returned.append({"product_id": str(pid), "product_name": row.get("product_name"), "quantity": qty})
    await log_audit(
        "JORNADA_INV_RETURN",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=jid, target_type="jornada",
        metadata={"items": len(returned)}, request=request,
    )
    return {"message": f"{len(returned)} producto(s) devueltos a sucursal", "returned": returned}


# ═══════════════════════════════════════════════════════════════════════
# PUNTO DE VENTA DE LA JORNADA
# ═══════════════════════════════════════════════════════════════════════
class JSalePayment(BaseModel):
    method: str
    amount: float
    reference: Optional[str] = None


class JSaleItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    price: float
    total: float


class JSaleCreate(BaseModel):
    patient_id: Optional[str] = None
    patient_name_override: Optional[str] = None
    items: List[JSaleItem]
    payments: List[JSalePayment]
    discount: float = 0
    notes: Optional[str] = None
    consultation_id: Optional[str] = None
    prescription_id: Optional[str] = None


@router.post("/{jid}/sales")
async def create_jornada_sale(
    jid: str, data: JSaleCreate, request: Request,
    user: dict = Depends(get_current_user),
):
    j = await _get_jornada_active_or_400(jid, user["company_id"], {"activa"})
    if (j.get("cash_config") or {}).get("mode") == "own":
        reg = await db.cash_registers.find_one({
            "company_id": ObjectId(user["company_id"]),
            "jornada_id": j["_id"], "status": "open",
        })
        if not reg:
            raise HTTPException(status_code=400, detail="Abre la caja de la jornada antes de vender")
    if not data.items:
        raise HTTPException(status_code=400, detail="La venta debe tener al menos un item")
    company_oid = ObjectId(user["company_id"])
    now = datetime.now(timezone.utc).isoformat()

    # Validar stock y descontar de jornada_stock
    for it in data.items:
        try:
            pid = ObjectId(it.product_id)
        except Exception:
            raise HTTPException(status_code=400, detail=f"product_id invalido: {it.product_id}")
        row = await db.jornada_stock.find_one({
            "jornada_id": j["_id"], "product_id": pid, "current_qty": {"$gte": it.quantity},
        })
        if not row:
            raise HTTPException(status_code=400, detail=f"Sin stock suficiente: {it.name}")

    # Todo OK: registrar venta
    subtotal = sum(float(i.total) for i in data.items)
    discount = float(data.discount or 0)
    total = round(subtotal - discount, 2)
    paid = round(sum(float(p.amount) for p in data.payments), 2)
    balance = round(total - paid, 2)

    payments = [
        {"method": p.method, "amount": float(p.amount), "reference": p.reference,
         "created_at": now, "created_by": ObjectId(user["_id"])}
        for p in data.payments if float(p.amount) > 0
    ]
    sale_doc = {
        "company_id": company_oid,
        "branch_id": j["responsible_branch_id"],
        "jornada_id": j["_id"],
        "patient_id": ObjectId(data.patient_id) if data.patient_id else None,
        "patient_name_override": data.patient_name_override,
        "consultation_id": ObjectId(data.consultation_id) if data.consultation_id else None,
        "prescription_id": ObjectId(data.prescription_id) if data.prescription_id else None,
        "items": [i.model_dump() for i in data.items],
        "subtotal": subtotal,
        "discount": discount,
        "tax": 0,
        "total": total,
        "payments": payments,
        "paid": paid,
        "balance": max(0.0, balance),
        "status": "completada" if balance <= 0 else "pendiente",
        "notes": data.notes,
        "created_at": now,
        "created_by": ObjectId(user["_id"]),
    }
    result = await db.sales.insert_one(sale_doc)

    # Descontar stock de la jornada
    for it in data.items:
        pid = ObjectId(it.product_id)
        await db.jornada_stock.update_one(
            {"jornada_id": j["_id"], "product_id": pid},
            {"$inc": {"current_qty": -it.quantity, "sold_qty": it.quantity}, "$set": {"updated_at": now}},
        )

    # Actualizar contadores agregados de la jornada
    await db.jornadas.update_one(
        {"_id": j["_id"]},
        {"$inc": {"total_sold": total, "sales_count": 1}, "$set": {"updated_at": now}},
    )
    await log_audit(
        "JORNADA_SALE_CREATED",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=str(result.inserted_id),
        target_type="sale",
        metadata={"jornada_id": jid, "total": total, "items": len(data.items)},
        request=request,
    )
    return {"_id": str(result.inserted_id), "message": "Venta registrada", "balance": max(0.0, balance)}


@router.get("/{jid}/sales")
async def list_jornada_sales(
    jid: str, user: dict = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=500),
):
    j = await _get_jornada_active_or_400(jid, user["company_id"], {"planificada", "activa", "en_cierre", "cerrada", "cancelada"})
    sales = await (
        db.sales.find({
            "company_id": ObjectId(user["company_id"]),
            "jornada_id": j["_id"],
        }).sort("_id", -1).limit(limit).to_list(limit)
    )
    # Batch load patients
    pids = list({s["patient_id"] for s in sales if s.get("patient_id")})
    pmap = {}
    if pids:
        docs = await db.patients.find({"_id": {"$in": pids}}, {"first_name": 1, "last_name": 1}).to_list(len(pids))
        pmap = {str(p["_id"]): f"{p.get('first_name','')} {p.get('last_name','')}".strip() for p in docs}
    for s in sales:
        _svc(s)
        for p in (s.get("payments") or []):
            if isinstance(p.get("created_by"), ObjectId):
                p["created_by"] = str(p["created_by"])
        pid = s.get("patient_id")
        s["patient_name"] = pmap.get(pid, s.get("patient_name_override") or "Consumidor final") if pid else (s.get("patient_name_override") or "Consumidor final")
    total_sold = sum(float(s.get("total") or 0) for s in sales)
    return {"items": sales, "count": len(sales), "total_sold": round(total_sold, 2)}


# ═══════════════════════════════════════════════════════════════════════
# PACIENTES DE LA JORNADA
# ═══════════════════════════════════════════════════════════════════════
class DuplicateSearch(BaseModel):
    dpi: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class JornadaPatientCreate(BaseModel):
    first_name: str
    last_name: str
    dpi: Optional[str] = None
    phone: str
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    link_to_patient_id: Optional[str] = None  # Si se vincula a un paciente existente


@router.post("/{jid}/patients/search")
async def find_duplicates(
    jid: str, data: DuplicateSearch, user: dict = Depends(get_current_user),
):
    """Busca pacientes existentes por DPI/telefono/nombre para evitar duplicados."""
    await _get_jornada_active_or_400(jid, user["company_id"], {"activa", "en_cierre", "planificada"})
    company_oid = ObjectId(user["company_id"])
    or_clauses: List[dict] = []
    if data.dpi and data.dpi.strip():
        or_clauses.append({"dpi": data.dpi.strip()})
    if data.phone and data.phone.strip():
        or_clauses.append({"phone": data.phone.strip()})
    if (data.first_name or "").strip() and (data.last_name or "").strip():
        or_clauses.append({
            "first_name": {"$regex": f"^{data.first_name.strip()}$", "$options": "i"},
            "last_name": {"$regex": f"^{data.last_name.strip()}$", "$options": "i"},
        })
    if not or_clauses:
        return {"matches": []}
    matches = await db.patients.find({
        "company_id": company_oid, "is_deleted": {"$ne": True}, "$or": or_clauses,
    }, {"first_name": 1, "last_name": 1, "phone": 1, "dpi": 1, "jornada_ids": 1}).limit(10).to_list(10)
    for m in matches:
        _svc(m)
    return {"matches": matches}


@router.post("/{jid}/patients")
async def create_jornada_patient(
    jid: str, data: JornadaPatientCreate, request: Request,
    user: dict = Depends(get_current_user),
):
    """Crea un paciente NUEVO en la base central marcandolo con la jornada, o
    vincula uno existente (agrega la jornada a su historial)."""
    j = await _get_jornada_active_or_400(jid, user["company_id"], {"activa", "planificada", "en_cierre"})
    company_oid = ObjectId(user["company_id"])
    joid = j["_id"]
    now = datetime.now(timezone.utc).isoformat()

    if data.link_to_patient_id:
        try:
            pid = ObjectId(data.link_to_patient_id)
        except Exception:
            raise HTTPException(status_code=400, detail="link_to_patient_id invalido")
        existing = await db.patients.find_one({"_id": pid, "company_id": company_oid})
        if not existing:
            raise HTTPException(status_code=404, detail="Paciente a vincular no encontrado")
        # Agregar la jornada al historial si no esta
        current_ids = existing.get("jornada_ids") or []
        already = any(str(x) == str(joid) for x in current_ids)
        if not already:
            update: dict = {"$push": {"jornada_ids": joid}, "$set": {"updated_at": now}}
            if not existing.get("jornada_id_first"):
                update["$set"]["jornada_id_first"] = joid
            await db.patients.update_one({"_id": pid}, update)
            await db.jornadas.update_one({"_id": joid}, {"$inc": {"patients_count": 1}})
        await log_audit(
            "JORNADA_PATIENT_LINKED",
            actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
            company_id=user.get("company_id"), target_id=str(pid), target_type="patient",
            metadata={"jornada_id": jid}, request=request,
        )
        return {"_id": str(pid), "linked": True, "message": "Paciente vinculado a la jornada"}

    # Crear paciente nuevo con marca de jornada
    doc = {
        "company_id": company_oid,
        "branch_id": j["responsible_branch_id"],
        "first_name": data.first_name.strip(),
        "last_name": data.last_name.strip(),
        "dpi": (data.dpi or "").strip() or None,
        "phone": data.phone.strip(),
        "whatsapp": (data.whatsapp or "").strip() or None,
        "email": (data.email or "").strip().lower() or None,
        "gender": data.gender,
        "birth_date": data.birth_date,
        "address": data.address,
        "country": "Guatemala",
        "notes": data.notes,
        "is_deleted": False,
        "jornada_id_first": joid,
        "jornada_ids": [joid],
        "captured_at_jornada": True,
        "created_at": now,
        "updated_at": now,
        "created_by": ObjectId(user["_id"]),
    }
    result = await db.patients.insert_one(doc)
    await db.jornadas.update_one({"_id": joid}, {"$inc": {"patients_count": 1}})
    await log_audit(
        "JORNADA_PATIENT_CREATED",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=str(result.inserted_id),
        target_type="patient", metadata={"jornada_id": jid}, request=request,
    )
    return {"_id": str(result.inserted_id), "linked": False, "message": "Paciente creado y vinculado a la jornada"}


@router.get("/{jid}/patients")
async def list_jornada_patients(
    jid: str, user: dict = Depends(get_current_user),
    limit: int = Query(200, ge=1, le=1000),
):
    j = await _get_jornada_active_or_400(jid, user["company_id"], {"planificada", "activa", "en_cierre", "cerrada", "cancelada"})
    joid = j["_id"]
    patients = await db.patients.find({
        "company_id": ObjectId(user["company_id"]),
        "is_deleted": {"$ne": True},
        "jornada_ids": joid,
    }, {
        "first_name": 1, "last_name": 1, "dpi": 1, "phone": 1, "whatsapp": 1,
        "email": 1, "jornada_id_first": 1, "jornada_ids": 1, "created_at": 1,
    }).sort("_id", -1).limit(limit).to_list(limit)
    for p in patients:
        _svc(p)
        p["is_first_capture_here"] = str(p.get("jornada_id_first") or "") == str(joid)
    return {"items": patients, "count": len(patients)}


# ═══════════════════════════════════════════════════════════════════════
# CONSULTA / RECETA RAPIDA + TICKET PDF (Iter 3.1 - encadenado en POS)
# ═══════════════════════════════════════════════════════════════════════
class JConsultationQuick(BaseModel):
    patient_id: str
    reason: Optional[str] = None
    observations: Optional[str] = None
    vision_od: Optional[str] = None
    vision_oi: Optional[str] = None


class JEyeglassRxQuick(BaseModel):
    patient_id: str
    consultation_id: Optional[str] = None
    professional_name: Optional[str] = None
    od_sphere: Optional[float] = None
    od_cylinder: Optional[float] = None
    od_axis: Optional[float] = None
    od_addition: Optional[float] = None
    od_dp: Optional[float] = None
    oi_sphere: Optional[float] = None
    oi_cylinder: Optional[float] = None
    oi_axis: Optional[float] = None
    oi_addition: Optional[float] = None
    oi_dp: Optional[float] = None
    observations: Optional[str] = None
    lens_type: Optional[str] = None
    frame_type: Optional[str] = None


@router.post("/{jid}/consultations")
async def create_jornada_consultation(
    jid: str, data: JConsultationQuick, request: Request,
    user: dict = Depends(get_current_user),
):
    j = await _get_jornada_active_or_400(jid, user["company_id"], {"activa"})
    try:
        pid = ObjectId(data.patient_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="patient_id invalido") from exc
    company_oid = ObjectId(user["company_id"])
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "company_id": company_oid,
        "branch_id": j["responsible_branch_id"],
        "jornada_id": j["_id"],
        "patient_id": pid,
        "professional_id": ObjectId(user["_id"]),
        "professional_name": user.get("name"),
        "date": now,
        "reason": data.reason,
        "observations": data.observations,
        "vision_od": data.vision_od,
        "vision_oi": data.vision_oi,
        "type": "jornada",
        "created_at": now,
        "created_by": ObjectId(user["_id"]),
    }
    result = await db.consultations.insert_one(doc)
    await log_audit(
        "JORNADA_CONSULTATION_CREATED",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=str(result.inserted_id),
        target_type="consultation", metadata={"jornada_id": jid, "patient_id": data.patient_id},
        request=request,
    )
    return {"_id": str(result.inserted_id), "message": "Consulta registrada"}


@router.post("/{jid}/prescriptions/eyeglass")
async def create_jornada_prescription(
    jid: str, data: JEyeglassRxQuick, request: Request,
    user: dict = Depends(get_current_user),
):
    j = await _get_jornada_active_or_400(jid, user["company_id"], {"activa"})
    try:
        pid = ObjectId(data.patient_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="patient_id invalido") from exc
    company_oid = ObjectId(user["company_id"])
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "company_id": company_oid,
        "patient_id": pid,
        "jornada_id": j["_id"],
        "consultation_id": ObjectId(data.consultation_id) if data.consultation_id else None,
        "professional_name": data.professional_name or user.get("name"),
        "od_sphere": data.od_sphere, "od_cylinder": data.od_cylinder,
        "od_axis": data.od_axis, "od_addition": data.od_addition, "od_dp": data.od_dp,
        "oi_sphere": data.oi_sphere, "oi_cylinder": data.oi_cylinder,
        "oi_axis": data.oi_axis, "oi_addition": data.oi_addition, "oi_dp": data.oi_dp,
        "observations": data.observations,
        "lens_type": data.lens_type, "frame_type": data.frame_type,
        "created_at": now, "created_by": ObjectId(user["_id"]),
    }
    result = await db.eyeglass_prescriptions.insert_one(doc)
    await log_audit(
        "JORNADA_RX_CREATED",
        actor_id=user["_id"], actor_email=user.get("email"), actor_role=user["role"],
        company_id=user.get("company_id"), target_id=str(result.inserted_id),
        target_type="prescription", metadata={"jornada_id": jid, "patient_id": data.patient_id},
        request=request,
    )
    return {"_id": str(result.inserted_id), "message": "Receta creada"}


@router.get("/{jid}/sales/{sale_id}/receipt.pdf")
async def sale_receipt_pdf(
    jid: str, sale_id: str, user: dict = Depends(get_current_user),
):
    """Ticket PDF 80mm para impresora termica o compartir por WhatsApp."""
    from fastapi.responses import StreamingResponse
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    import io as _io

    j = await _get_jornada_active_or_400(jid, user["company_id"], {"activa", "en_cierre", "cerrada"})
    try:
        soid = ObjectId(sale_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="sale_id invalido") from exc
    sale = await db.sales.find_one({
        "_id": soid,
        "company_id": ObjectId(user["company_id"]),
        "jornada_id": j["_id"],
    })
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])}) or {}
    patient_name = "Consumidor final"
    if sale.get("patient_id"):
        p = await db.patients.find_one({"_id": sale["patient_id"]})
        if p:
            patient_name = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
    elif sale.get("patient_name_override"):
        patient_name = sale["patient_name_override"]

    width = 80 * mm
    lines_items = len(sale.get("items") or [])
    lines_pay = len(sale.get("payments") or [])
    height = (60 + 6 * lines_items + 6 * lines_pay + 40) * mm
    buf = _io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))

    y = height - 8 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width / 2, y, str(company.get("name") or "Cortexia Optical"))
    y -= 4 * mm
    c.setFont("Helvetica", 7)
    if company.get("phone"):
        c.drawCentredString(width / 2, y, f"Tel: {company.get('phone')}")
        y -= 3 * mm
    if company.get("address"):
        c.drawCentredString(width / 2, y, str(company.get("address"))[:40])
        y -= 3 * mm
    y -= 2 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(width / 2, y, "* JORNADA *")
    y -= 3.5 * mm
    c.setFont("Helvetica", 7)
    c.drawCentredString(width / 2, y, str(j.get("name") or "")[:42])
    y -= 3 * mm
    if j.get("location"):
        c.drawCentredString(width / 2, y, str(j.get("location"))[:42])
        y -= 3 * mm
    y -= 1 * mm
    c.line(4 * mm, y, width - 4 * mm, y)
    y -= 3 * mm
    c.setFont("Helvetica", 7)
    date_str = (sale.get("created_at") or "")[:19].replace("T", " ")
    c.drawString(4 * mm, y, f"Ticket: {str(sale['_id'])[-8:].upper()}")
    c.drawRightString(width - 4 * mm, y, date_str)
    y -= 3.5 * mm
    c.drawString(4 * mm, y, f"Cliente: {patient_name[:35]}")
    y -= 3.5 * mm
    c.line(4 * mm, y, width - 4 * mm, y)
    y -= 3 * mm
    c.setFont("Helvetica-Bold", 7)
    c.drawString(4 * mm, y, "Producto")
    c.drawRightString(width - 4 * mm, y, "Total")
    y -= 3 * mm
    c.setFont("Helvetica", 7)
    for it in (sale.get("items") or []):
        name = str(it.get("name", ""))[:30]
        qty = int(it.get("quantity", 0))
        price = float(it.get("price", 0))
        line_total = float(it.get("total", qty * price))
        c.drawString(4 * mm, y, f"{name}")
        c.drawRightString(width - 4 * mm, y, f"Q {line_total:.2f}")
        y -= 3 * mm
        c.drawString(6 * mm, y, f"  {qty} x Q {price:.2f}")
        y -= 3.5 * mm
    y -= 1 * mm
    c.line(4 * mm, y, width - 4 * mm, y)
    y -= 3 * mm
    c.setFont("Helvetica", 7)
    c.drawString(4 * mm, y, "Subtotal")
    c.drawRightString(width - 4 * mm, y, f"Q {float(sale.get('subtotal', 0)):.2f}")
    y -= 3 * mm
    if float(sale.get("discount", 0)) > 0:
        c.drawString(4 * mm, y, "Descuento")
        c.drawRightString(width - 4 * mm, y, f"-Q {float(sale.get('discount', 0)):.2f}")
        y -= 3 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(4 * mm, y, "TOTAL")
    c.drawRightString(width - 4 * mm, y, f"Q {float(sale.get('total', 0)):.2f}")
    y -= 4 * mm
    c.setFont("Helvetica", 7)
    method_labels = {"cash": "Efectivo", "card": "Tarjeta", "transfer": "Transf.", "check": "Cheque", "other": "Otro"}
    for p in (sale.get("payments") or []):
        m = method_labels.get(p.get("method"), p.get("method", ""))
        c.drawString(4 * mm, y, f"Pago {m}")
        c.drawRightString(width - 4 * mm, y, f"Q {float(p.get('amount', 0)):.2f}")
        y -= 3 * mm
    if float(sale.get("balance", 0)) > 0.01:
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.HexColor("#d97706"))
        c.drawString(4 * mm, y, "SALDO PENDIENTE")
        c.drawRightString(width - 4 * mm, y, f"Q {float(sale.get('balance', 0)):.2f}")
        c.setFillColor(colors.black)
        y -= 3.5 * mm
    y -= 2 * mm
    c.line(4 * mm, y, width - 4 * mm, y)
    y -= 3 * mm
    c.setFont("Helvetica", 6)
    c.drawCentredString(width / 2, y, "Gracias por su compra")
    y -= 3 * mm
    c.drawCentredString(width / 2, y, "www.cortexiaoptical.com")

    c.showPage()
    c.save()
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=ticket_{sale_id}.pdf"},
    )
