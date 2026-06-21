"""Auth endpoints: session, me, logout."""
from datetime import timedelta
from typing import Optional
import httpx

from fastapi import APIRouter, HTTPException, Header

from core.db import db
from core.deps import now_utc, new_id, get_user_from_token, audit
from core.models import SessionRequest

router = APIRouter()


@router.post("/auth/session")
async def create_session(body: SessionRequest):
    """Verify session token with Emergent and create/refresh local session."""
    if not body.session_token:
        raise HTTPException(status_code=400, detail="session_token required")
    async with httpx.AsyncClient(timeout=15.0) as hc:
        r = await hc.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": body.session_token},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session token")
    data = r.json()
    email = data.get("email")
    name = data.get("name") or email
    picture = data.get("picture", "")
    token = data.get("session_token") or body.session_token

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture, "last_login": now_utc()}},
        )
        member_cos = existing.get("company_ids", [])
        if not member_cos:
            member_cos = ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"]
            await db.users.update_one({"user_id": user_id}, {"$set": {"company_ids": member_cos,
                                                                      "active_company_id": member_cos[0]}})
    else:
        user_id = new_id("user")
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "company_ids": ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"],
            "active_company_id": "co_aidou_corp",
            "role": "admin",
            "created_at": now_utc(),
            "last_login": now_utc(),
        })

    existing_memberships = await db.memberships.count_documents({"user_id": user_id})
    if existing_memberships == 0:
        default_memberships = [
            {"membership_id": new_id("mem"), "user_id": user_id, "company_id": "co_aidou_corp",
             "role": "owner", "created_at": now_utc()},
            {"membership_id": new_id("mem"), "user_id": user_id, "company_id": "co_northstar_isp",
             "role": "manager", "created_at": now_utc()},
            {"membership_id": new_id("mem"), "user_id": user_id, "company_id": "co_summit_construction",
             "role": "employee", "created_at": now_utc()},
        ]
        await db.memberships.insert_many(default_memberships)
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"active_company_id": "co_aidou_corp", "active_role": "owner"}},
        )

    await db.user_sessions.delete_many({"session_token": token})
    await db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "expires_at": now_utc() + timedelta(days=7),
        "created_at": now_utc(),
    })

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    await audit(user, "login", "auth", meta={"email": email})
    return {"session_token": token, "user": user}


@router.get("/auth/me")
async def me(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    return {"user": user}


@router.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        await db.user_sessions.delete_many({"session_token": token})
    return {"ok": True}
