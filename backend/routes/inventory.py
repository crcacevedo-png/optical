from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from db import db, serialize_doc
from auth_utils import get_current_user
from models import ProductCreate, ProductUpdate, InventoryMovement

router = APIRouter(prefix="/inventory", tags=["Inventario"])

@router.get("/products")
async def list_products(user: dict = Depends(get_current_user), category: Optional[str] = None, search: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"]), "is_active": {"$ne": False}}
    if category:
        query["category"] = category
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
            {"brand": {"$regex": search, "$options": "i"}}
        ]
    
    products = await db.products.find(query).to_list(500)
    for p in products:
        serialize_doc(p)
    product_ids = [ObjectId(p["_id"]) for p in products]
    if product_ids:
        branch_id_val = ObjectId(user["branch_id"]) if user.get("branch_id") else None
        stock_query = {"company_id": ObjectId(user["company_id"]), "product_id": {"$in": product_ids}}
        if branch_id_val:
            stock_query["branch_id"] = branch_id_val
        stock_items = await db.stock.find(stock_query).to_list(len(product_ids))
        stock_map = {str(s["product_id"]): s["quantity"] for s in stock_items}
        for p in products:
            p["stock_actual"] = stock_map.get(p["_id"], 0)
    return products

@router.post("/products")
async def create_product(data: ProductCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Solo administradores pueden crear productos")
    
    product_doc = {
        "company_id": ObjectId(user["company_id"]),
        "name": data.name, "sku": data.sku, "category": data.category, "brand": data.brand,
        "description": data.description, "cost_price": data.cost_price, "sale_price": data.sale_price,
        "min_stock": data.min_stock, "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.products.insert_one(product_doc)
    product_id = result.inserted_id
    
    if data.initial_stock > 0:
        branch_id = ObjectId(data.branch_id) if data.branch_id else (ObjectId(user["branch_id"]) if user.get("branch_id") else None)
        if branch_id:
            await db.stock.update_one(
                {"company_id": ObjectId(user["company_id"]), "branch_id": branch_id, "product_id": product_id},
                {"$set": {"quantity": data.initial_stock}},
                upsert=True
            )
            await db.inventory_movements.insert_one({
                "company_id": ObjectId(user["company_id"]), "branch_id": branch_id,
                "product_id": product_id, "type": "entrada",
                "quantity": data.initial_stock, "notes": "Stock inicial",
                "created_by": ObjectId(user["_id"]),
                "created_at": datetime.now(timezone.utc).isoformat()
            })
    
    return {"_id": str(product_id), "message": "Producto creado"}

@router.put("/products/{product_id}")
async def update_product(product_id: str, data: ProductUpdate, user: dict = Depends(get_current_user)):
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Solo administradores pueden actualizar productos")
    product = await db.products.find_one({"_id": ObjectId(product_id)})
    if not product or str(product["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    await db.products.update_one({"_id": ObjectId(product_id)}, {"$set": update_data})
    return {"message": "Producto actualizado"}

@router.get("/stock")
async def get_stock(user: dict = Depends(get_current_user), branch_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    stock = await db.stock.find(query).to_list(1000)
    for s in stock:
        serialize_doc(s)
    product_ids = list({ObjectId(s["product_id"]) for s in stock if s.get("product_id")})
    if product_ids:
        products = await db.products.find({"_id": {"$in": product_ids}}, {"name": 1, "sku": 1, "min_stock": 1, "sale_price": 1, "cost_price": 1}).to_list(len(product_ids))
        product_map = {str(p["_id"]): p for p in products}
        for s in stock:
            prod = product_map.get(s.get("product_id"))
            if prod:
                s["product_name"] = prod["name"]
                s["sku"] = prod["sku"]
                s["min_stock"] = prod.get("min_stock", 5)
                s["sale_price"] = prod.get("sale_price", 0)
                s["cost_price"] = prod.get("cost_price", 0)
    return stock

@router.post("/movement")
async def create_inventory_movement(data: InventoryMovement, user: dict = Depends(get_current_user)):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    product = await db.products.find_one({"_id": ObjectId(data.product_id)})
    if not product or str(product["company_id"]) != user["company_id"]:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    stock = await db.stock.find_one({
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(data.branch_id),
        "product_id": ObjectId(data.product_id)
    })
    
    quantity_change = data.quantity if data.type == "entrada" else -data.quantity
    
    if stock:
        new_quantity = stock["quantity"] + quantity_change
        if new_quantity < 0:
            raise HTTPException(status_code=400, detail="Stock insuficiente")
        await db.stock.update_one(
            {"_id": stock["_id"]},
            {"$set": {"quantity": new_quantity, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    else:
        if quantity_change < 0:
            raise HTTPException(status_code=400, detail="Stock insuficiente")
        await db.stock.insert_one({
            "company_id": ObjectId(user["company_id"]),
            "branch_id": ObjectId(data.branch_id),
            "product_id": ObjectId(data.product_id),
            "quantity": quantity_change,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    movement_doc = {
        "company_id": ObjectId(user["company_id"]),
        "branch_id": ObjectId(data.branch_id),
        "product_id": ObjectId(data.product_id),
        "type": data.type,
        "quantity": data.quantity,
        "notes": data.notes,
        "reference": data.reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": ObjectId(user["_id"])
    }
    await db.inventory_movements.insert_one(movement_doc)
    
    return {"message": "Movimiento registrado"}

@router.get("/movements")
async def list_inventory_movements(
    user: dict = Depends(get_current_user),
    product_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    limit: int = 100
):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if product_id:
        query["product_id"] = ObjectId(product_id)
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    movements = await db.inventory_movements.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    for m in movements:
        serialize_doc(m)
    product_ids = list({ObjectId(m["product_id"]) for m in movements if m.get("product_id")})
    if product_ids:
        products = await db.products.find({"_id": {"$in": product_ids}}, {"name": 1}).to_list(len(product_ids))
        product_map = {str(p["_id"]): p["name"] for p in products}
        for m in movements:
            m["product_name"] = product_map.get(m.get("product_id"), "")
    return movements

@router.get("/alerts")
async def get_stock_alerts(user: dict = Depends(get_current_user), branch_id: Optional[str] = None):
    if user["role"] == "superadmin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    query = {"company_id": ObjectId(user["company_id"])}
    if branch_id:
        query["branch_id"] = ObjectId(branch_id)
    elif user.get("branch_id"):
        query["branch_id"] = ObjectId(user["branch_id"])
    
    stock_items = await db.stock.find(query).to_list(1000)
    product_ids = list({s["product_id"] for s in stock_items if s.get("product_id")})
    alerts = []
    if product_ids:
        products = await db.products.find({"_id": {"$in": product_ids}}, {"name": 1, "min_stock": 1, "sku": 1}).to_list(len(product_ids))
        product_map = {p["_id"]: p for p in products}
        for s in stock_items:
            product = product_map.get(s["product_id"])
            if product and s["quantity"] <= product.get("min_stock", 5):
                alerts.append({
                    "product_id": str(s["product_id"]),
                    "product_name": product["name"],
                    "sku": product.get("sku", ""),
                    "current_stock": s["quantity"],
                    "min_stock": product.get("min_stock", 5),
                    "branch_id": str(s["branch_id"])
                })
    return alerts
