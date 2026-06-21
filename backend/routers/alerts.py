"""Alerts."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Header

from core.db import db
from core.deps import get_user_from_token

router = APIRouter()


@router.get("/alerts")
async def list_alerts(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    al = await db.alerts.find({"company_id": co_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    for a in al:
        if isinstance(a.get("created_at"), datetime):
            a["created_at"] = a["created_at"].isoformat()
    return {"alerts": al}


@router.post("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    await db.alerts.update_one({"alert_id": alert_id, "company_id": co_id}, {"$set": {"read": True}})
    return {"ok": True}
