"""Inventory items + barcode lookup."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Header, HTTPException

from core.db import db
from core.deps import get_user_from_token

router = APIRouter()


@router.get("/inventory/items")
async def list_inventory(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    items = await db.inventory.find({"company_id": co_id}, {"_id": 0}).to_list(500)
    for it in items:
        if isinstance(it.get("updated_at"), datetime):
            it["updated_at"] = it["updated_at"].isoformat()
    return {"items": items}


@router.get("/inventory/lookup")
async def lookup_barcode(barcode: str, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    if not barcode:
        raise HTTPException(status_code=400, detail="barcode required")
    item = await db.inventory.find_one(
        {"company_id": co_id, "barcode": barcode}, {"_id": 0},
    )
    if item and isinstance(item.get("updated_at"), datetime):
        item["updated_at"] = item["updated_at"].isoformat()
    prod = await db.products.find_one(
        {"company_id": co_id, "barcode": barcode}, {"_id": 0},
    )
    if prod and isinstance(prod.get("created_at"), datetime):
        prod["created_at"] = prod["created_at"].isoformat()
    return {"item": item, "product": prod, "found": bool(item or prod)}
