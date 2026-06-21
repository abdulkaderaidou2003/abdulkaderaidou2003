"""Company list & switch endpoints."""
from typing import Optional
from fastapi import APIRouter, Header, HTTPException

from core.db import db
from core.deps import get_user_from_token, audit
from core.models import CompanySwitch

router = APIRouter()


@router.get("/companies")
async def list_companies(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    ids = user.get("company_ids", [])
    cos = await db.companies.find({"company_id": {"$in": ids}}, {"_id": 0}).to_list(100)
    return {"companies": cos, "active_company_id": user.get("active_company_id")}


@router.post("/companies/switch")
async def switch_company(body: CompanySwitch, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    if body.company_id not in user.get("company_ids", []):
        raise HTTPException(status_code=403, detail="Not a member of this company")
    await db.users.update_one({"user_id": user["user_id"]},
                              {"$set": {"active_company_id": body.company_id}})
    await audit(user, "switch", "company", meta={"to": body.company_id})
    return {"active_company_id": body.company_id}
