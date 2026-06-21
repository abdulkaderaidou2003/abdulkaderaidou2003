"""Job tickets."""
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Header

from core.db import db
from core.deps import get_user_from_token, audit, now_utc, new_id
from core.models import TicketIn

router = APIRouter()


@router.get("/tickets")
async def list_tickets(status: Optional[str] = None, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    q: Dict[str, Any] = {"company_id": co_id}
    if status and status != "all":
        q["status"] = status
    tks = await db.tickets.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    for t in tks:
        if isinstance(t.get("created_at"), datetime):
            t["created_at"] = t["created_at"].isoformat()
    return {"tickets": tks}


@router.post("/tickets")
async def create_ticket(body: TicketIn, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    t = {
        "ticket_id": new_id("tkt"),
        "company_id": co_id,
        "title": body.title,
        "description": body.description,
        "priority": body.priority,
        "status": "open",
        "assignee": body.assignee or user.get("name"),
        "sla_hours": 8,
        "created_at": now_utc(),
    }
    await db.tickets.insert_one(t)
    t.pop("_id", None)
    t["created_at"] = t["created_at"].isoformat()
    await audit(user, "create", "ticket", meta={"ticket_id": t["ticket_id"], "priority": t["priority"]})
    return {"ticket": t}
