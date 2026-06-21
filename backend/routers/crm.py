"""CRM customers."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Header

from core.db import db
from core.deps import get_user_from_token

router = APIRouter()


@router.get("/crm/customers")
async def list_customers(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    cs = await db.customers.find({"company_id": co_id}, {"_id": 0}).to_list(500)
    for c in cs:
        if isinstance(c.get("created_at"), datetime):
            c["created_at"] = c["created_at"].isoformat()
    return {"customers": cs}
