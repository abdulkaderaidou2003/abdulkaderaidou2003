"""Point of Sale."""
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Header, HTTPException

from core.db import db
from core.deps import get_user_from_token, audit, now_utc, new_id
from core.models import SaleIn

router = APIRouter()


@router.get("/pos/products")
async def list_products(category: Optional[str] = None, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    q: Dict[str, Any] = {"company_id": co_id}
    if category and category != "all":
        q["category"] = category
    prods = await db.products.find(q, {"_id": 0}).to_list(500)
    return {"products": prods}


@router.post("/pos/sales")
async def create_sale(body: SaleIn, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    if not body.items:
        raise HTTPException(status_code=400, detail="cart is empty")
    ids = [it.get("product_id") for it in body.items]
    products = await db.products.find(
        {"company_id": co_id, "product_id": {"$in": ids}}, {"_id": 0},
    ).to_list(200)
    by_id = {p["product_id"]: p for p in products}
    subtotal = 0.0
    line_items = []
    for it in body.items:
        p = by_id.get(it.get("product_id"))
        if not p:
            continue
        qty = max(1, int(it.get("qty", 1)))
        line_total = round(p["price"] * qty, 2)
        subtotal += line_total
        line_items.append({
            "product_id": p["product_id"],
            "name": p["name"],
            "qty": qty,
            "price": p["price"],
            "line_total": line_total,
        })
    if not line_items:
        raise HTTPException(status_code=400, detail="no valid items")
    hst = round(subtotal * 0.13, 2)
    total = round(subtotal + hst, 2)
    sale = {
        "sale_id": new_id("sal"),
        "company_id": co_id,
        "tender": body.tender,
        "subtotal": round(subtotal, 2),
        "hst": hst,
        "total": total,
        "items": line_items,
        "cashier": user.get("name"),
        "created_at": now_utc(),
    }
    await db.sales.insert_one(sale)
    sale.pop("_id", None)
    sale["created_at"] = sale["created_at"].isoformat() if isinstance(sale["created_at"], datetime) else sale["created_at"]
    await audit(user, "create", "sale", meta={"sale_id": sale["sale_id"], "total": sale["total"]})
    return {"sale": sale}


@router.get("/pos/sales")
async def list_sales(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    sl = await db.sales.find({"company_id": co_id}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    for s in sl:
        if isinstance(s.get("created_at"), datetime):
            s["created_at"] = s["created_at"].isoformat()
    return {"sales": sl}
