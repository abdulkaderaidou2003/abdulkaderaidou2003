"""Employee timeclock."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Header

from core.db import db
from core.deps import get_user_from_token, audit, now_utc, new_id
from core.models import TimeclockPunch

router = APIRouter()


@router.post("/timeclock/punch")
async def timeclock_punch(body: TimeclockPunch, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    open_punch = await db.timeclock.find_one(
        {"user_id": user["user_id"], "company_id": co_id, "clock_out": None},
        {"_id": 0},
    )
    if open_punch:
        end = now_utc()
        start = open_punch["clock_in"]
        if isinstance(start, datetime) and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        minutes = int((end - start).total_seconds() / 60)
        await db.timeclock.update_one(
            {"punch_id": open_punch["punch_id"]},
            {"$set": {"clock_out": end, "minutes": minutes}},
        )
        await audit(user, "punch_out", "timeclock", meta={"minutes": minutes})
        return {"action": "clock_out", "minutes": minutes, "punch_id": open_punch["punch_id"]}
    p = {
        "punch_id": new_id("pch"),
        "user_id": user["user_id"],
        "company_id": co_id,
        "user_name": user.get("name"),
        "clock_in": now_utc(),
        "clock_out": None,
        "minutes": 0,
        "note": body.note,
    }
    await db.timeclock.insert_one(p)
    p.pop("_id", None)
    p["clock_in"] = p["clock_in"].isoformat()
    await audit(user, "punch_in", "timeclock")
    return {"action": "clock_in", "punch": p}


@router.get("/timeclock/me")
async def timeclock_me(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    today_start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    punches = await db.timeclock.find(
        {"user_id": user["user_id"], "company_id": co_id, "clock_in": {"$gte": today_start}},
        {"_id": 0},
    ).sort("clock_in", -1).to_list(50)
    open_p = None
    minutes_today = 0
    for p in punches:
        if isinstance(p.get("clock_in"), datetime):
            p["clock_in"] = p["clock_in"].isoformat()
        if isinstance(p.get("clock_out"), datetime):
            p["clock_out"] = p["clock_out"].isoformat()
        if p.get("clock_out") is None and not open_p:
            open_p = p
        else:
            minutes_today += int(p.get("minutes", 0))
    if open_p:
        start = datetime.fromisoformat(open_p["clock_in"].replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        minutes_today += int((now_utc() - start).total_seconds() / 60)
    return {"punches": punches, "open_punch": open_p, "minutes_today": minutes_today}
