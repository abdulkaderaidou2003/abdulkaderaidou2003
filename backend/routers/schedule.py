"""Schedule (shifts)."""
from typing import Optional
from fastapi import APIRouter, Header

from core.db import db
from core.deps import get_user_from_token

router = APIRouter()


@router.get("/schedule")
async def schedule_list(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    shifts = await db.shifts.find({"company_id": co_id}, {"_id": 0}).to_list(500)
    return {"shifts": shifts}
