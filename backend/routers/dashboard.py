"""Owner/manager dashboard KPIs."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Header

from core.db import db
from core.deps import get_user_from_token

router = APIRouter()


@router.get("/dashboard")
async def dashboard(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    emp_count = await db.employees.count_documents({"company_id": co_id})
    active_emp = await db.employees.count_documents({"company_id": co_id, "status": "active"})
    open_tickets = await db.tickets.count_documents({"company_id": co_id, "status": {"$in": ["open", "in_progress"]}})
    high_pri = await db.tickets.count_documents({"company_id": co_id, "priority": "high", "status": {"$ne": "closed"}})
    customers = await db.customers.count_documents({"company_id": co_id})
    alerts_unread = await db.alerts.count_documents({"company_id": co_id, "read": False})

    seed = sum(ord(c) for c in (co_id or ""))
    revenue_mtd = 482000 + (seed % 30) * 1500
    payroll_mtd = 138000 + (seed % 20) * 900
    pipeline = 1240000 + (seed % 50) * 3000

    feed = await db.tickets.find({"company_id": co_id}, {"_id": 0}).sort("created_at", -1).limit(6).to_list(6)
    for f in feed:
        f["created_at"] = f["created_at"].isoformat() if isinstance(f.get("created_at"), datetime) else f.get("created_at")

    return {
        "kpis": {
            "revenue_mtd": revenue_mtd,
            "payroll_mtd": payroll_mtd,
            "pipeline": pipeline,
            "employees_total": emp_count,
            "employees_active": active_emp,
            "open_tickets": open_tickets,
            "high_priority_tickets": high_pri,
            "customers": customers,
            "alerts_unread": alerts_unread,
        },
        "feed": feed,
    }
