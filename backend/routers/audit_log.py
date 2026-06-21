"""Audit log (admin only)."""
from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, Depends, Request

from core.db import db
from core.deps import audit, require_role

router = APIRouter()


@router.get("/audit/log")
async def audit_log(
    limit: int = 100,
    request: Request = None,
    user: Dict[str, Any] = Depends(require_role("admin")),
):
    co_id = user.get("active_company_id")
    cursor = db.audit_log.find({"company_id": co_id}, {"_id": 0}).sort("created_at", -1).limit(min(500, max(1, limit)))
    entries = await cursor.to_list(500)
    for e in entries:
        if isinstance(e.get("created_at"), datetime):
            e["created_at"] = e["created_at"].isoformat()
    await audit(user, "view", "audit_log", request=request, meta={"limit": limit})
    return {"entries": entries, "count": len(entries)}
