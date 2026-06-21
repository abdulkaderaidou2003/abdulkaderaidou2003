"""Fleet GPS."""
import random
from typing import Optional
from fastapi import APIRouter, Header

from core.db import db
from core.deps import get_user_from_token

router = APIRouter()


@router.get("/fleet/vehicles")
async def list_vehicles(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    vehs = await db.vehicles.find({"company_id": co_id}, {"_id": 0}).to_list(200)
    for v in vehs:
        v["lat"] = round(v["lat"] + random.uniform(-0.0015, 0.0015), 6)
        v["lng"] = round(v["lng"] + random.uniform(-0.0015, 0.0015), 6)
        v["speed_kmh"] = random.randint(0, 95) if v["status"] == "active" else 0
        v["heading"] = random.randint(0, 359)
    return {"vehicles": vehs}
