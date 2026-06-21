"""Workspaces (multi-role identity) + per-workspace stats."""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Header, HTTPException

from core.db import db
from core.deps import get_user_from_token, audit
from core.models import WorkspaceSwitch

router = APIRouter()


@router.get("/workspaces")
async def list_workspaces(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    memberships = await db.memberships.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(100)
    company_ids = list({m["company_id"] for m in memberships})
    cos = await db.companies.find({"company_id": {"$in": company_ids}}, {"_id": 0}).to_list(100)
    co_by_id = {c["company_id"]: c for c in cos}
    workspaces = []
    for m in memberships:
        co = co_by_id.get(m["company_id"])
        if not co:
            continue
        workspaces.append({
            "membership_id": m["membership_id"],
            "company_id": m["company_id"],
            "company_name": co["name"],
            "industry": co["industry"],
            "logo_color": co["logo_color"],
            "role": m["role"],
        })
    return {
        "workspaces": workspaces,
        "active_company_id": user.get("active_company_id"),
        "active_role": user.get("active_role"),
    }


@router.post("/workspaces/switch")
async def switch_workspace(body: WorkspaceSwitch, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    m = await db.memberships.find_one(
        {"user_id": user["user_id"], "company_id": body.company_id, "role": body.role},
        {"_id": 0},
    )
    if not m:
        raise HTTPException(status_code=403, detail="No matching workspace membership")
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"active_company_id": body.company_id, "active_role": body.role}},
    )
    await audit(user, "switch", "workspace", meta={"company": body.company_id, "role": body.role})
    return {"active_company_id": body.company_id, "active_role": body.role}


@router.get("/workspaces/stats")
async def workspace_stats(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    memberships = await db.memberships.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(100)
    stats: Dict[str, Dict[str, Any]] = {}
    for m in memberships:
        co_id = m["company_id"]
        role = m["role"]
        key = f"{co_id}:{role}"
        if role in ("owner", "manager"):
            emp_count = await db.employees.count_documents({"company_id": co_id, "status": "active"})
            runs = await db.pay_runs.find({"company_id": co_id}, {"_id": 0, "gross": 1}).to_list(50)
            payroll_ytd = sum(r.get("gross", 0) for r in runs)
            stats[key] = {
                "headline": f"{emp_count} employees",
                "metric": f"${(payroll_ytd / 1000):.1f}K payroll YTD",
                "tone": "ops",
            }
        elif role == "employee":
            punches = await db.timeclock.find(
                {"user_id": user["user_id"], "company_id": co_id}, {"_id": 0, "minutes": 1},
            ).to_list(500)
            hours = sum(p.get("minutes", 0) for p in punches) / 60.0
            shifts = await db.shifts.count_documents({"company_id": co_id})
            stats[key] = {
                "headline": f"{hours:.1f}h logged this period",
                "metric": f"{shifts} shifts in rotation",
                "tone": "work",
            }
        else:
            sales = await db.sales.count_documents({"company_id": co_id})
            apts = await db.appointments.count_documents({"customer_user_id": user["user_id"], "company_id": co_id})
            stats[key] = {
                "headline": f"{sales} invoices on file",
                "metric": f"{apts} upcoming appointments",
                "tone": "customer",
            }
    return {"stats": stats}
