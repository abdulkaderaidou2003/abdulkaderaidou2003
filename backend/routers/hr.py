"""HR employees."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Request

from core.db import db
from core.deps import get_user_from_token, audit, now_utc, new_id, has_role
from core.models import EmployeeIn

router = APIRouter()


@router.get("/hr/employees")
async def list_employees(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    emps = await db.employees.find({"company_id": co_id}, {"_id": 0}).to_list(500)
    for e in emps:
        if isinstance(e.get("hired_at"), datetime):
            e["hired_at"] = e["hired_at"].isoformat()
    return {"employees": emps}


@router.post("/hr/employees")
async def add_employee(body: EmployeeIn, request: Request, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    if not has_role(user, ["manager", "admin"]):
        raise HTTPException(status_code=403, detail="Requires manager or admin")
    co_id = user.get("active_company_id")
    emp = {
        "employee_id": new_id("emp"),
        "company_id": co_id,
        "name": body.name,
        "role": body.role,
        "department": body.department,
        "email": body.email,
        "status": body.status,
        "hired_at": now_utc(),
    }
    await db.employees.insert_one(emp)
    emp.pop("_id", None)
    emp["hired_at"] = emp["hired_at"].isoformat()
    await audit(user, "create", "employee", request=request,
                meta={"employee_id": emp["employee_id"], "name": emp["name"]})
    return {"employee": emp}
