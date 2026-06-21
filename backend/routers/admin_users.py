"""Admin user management: list, role update, invite."""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Header, HTTPException

from core.db import db
from core.deps import get_user_from_token, audit, now_utc, new_id
from core.models import RoleUpdate, InviteIn
from core.email import send_magic_link_email

router = APIRouter()


@router.get("/admin/users")
async def list_admin_users(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    if user.get("active_role") not in ("owner", "manager") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner or manager required")
    co_id = user.get("active_company_id")
    memberships = await db.memberships.find({"company_id": co_id}, {"_id": 0}).to_list(500)
    user_ids = list({m["user_id"] for m in memberships})
    users = await db.users.find(
        {"user_id": {"$in": user_ids}},
        {"_id": 0, "user_id": 1, "email": 1, "name": 1, "picture": 1},
    ).to_list(500)
    by_user: Dict[str, Any] = {}
    for u in users:
        by_user[u["user_id"]] = {**u, "memberships": []}
    for m in memberships:
        if m["user_id"] in by_user:
            by_user[m["user_id"]]["memberships"].append(
                {"membership_id": m["membership_id"], "role": m["role"], "company_id": m["company_id"]},
            )
    return {"users": list(by_user.values()), "company_id": co_id}


@router.post("/admin/users/{user_id}/role")
async def set_user_role(user_id: str, body: RoleUpdate, authorization: Optional[str] = Header(None)):
    actor = await get_user_from_token(authorization)
    if actor.get("active_role") != "owner" and actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner role required")
    if body.role not in ("owner", "manager", "employee", "customer"):
        raise HTTPException(status_code=400, detail="Invalid role")
    target_exists = await db.users.find_one({"user_id": user_id}, {"_id": 0, "user_id": 1})
    if not target_exists:
        raise HTTPException(status_code=404, detail="Target user not found")
    co_id = actor.get("active_company_id")
    existing = await db.memberships.find_one(
        {"user_id": user_id, "company_id": co_id}, {"_id": 0},
    )
    if existing:
        await db.memberships.update_one(
            {"membership_id": existing["membership_id"]},
            {"$set": {"role": body.role}},
        )
    else:
        await db.memberships.insert_one({
            "membership_id": new_id("mem"),
            "user_id": user_id,
            "company_id": co_id,
            "role": body.role,
            "created_at": now_utc(),
        })
    await audit(actor, "update", "membership",
                meta={"target_user_id": user_id, "role": body.role, "company_id": co_id})
    return {"ok": True, "user_id": user_id, "role": body.role, "company_id": co_id}


@router.post("/admin/users/invite")
async def admin_invite(body: InviteIn, authorization: Optional[str] = Header(None)):
    actor = await get_user_from_token(authorization)
    if actor.get("active_role") != "owner" and actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner role required")
    if body.role not in ("owner", "manager", "employee", "customer"):
        raise HTTPException(status_code=400, detail="Invalid role")
    co_id = actor.get("active_company_id")
    existing = await db.users.find_one({"email": body.email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
    else:
        user_id = new_id("user")
        await db.users.insert_one({
            "user_id": user_id,
            "email": body.email,
            "name": body.name or body.email.split("@")[0].replace(".", " ").title(),
            "picture": "",
            "company_ids": [co_id],
            "active_company_id": co_id,
            "role": "member",
            "created_at": now_utc(),
            "invited_by": actor["user_id"],
        })
    m = await db.memberships.find_one(
        {"user_id": user_id, "company_id": co_id, "role": body.role}, {"_id": 0},
    )
    if not m:
        await db.memberships.insert_one({
            "membership_id": new_id("mem"),
            "user_id": user_id,
            "company_id": co_id,
            "role": body.role,
            "invited_by": actor["user_id"],
            "created_at": now_utc(),
        })
    co = await db.companies.find_one({"company_id": co_id}, {"_id": 0})
    company_name = co["name"] if co else "your workspace"
    invitee_name = body.name or body.email.split("@")[0].replace(".", " ").title()
    magic_link = f"https://aidou.app/invite/{user_id}?co={co_id}&role={body.role}"
    email_result = send_magic_link_email(body.email, invitee_name, company_name, body.role, magic_link)
    await audit(actor, "invite", "user",
                meta={"email": body.email, "role": body.role, "company_id": co_id, "email_sent": email_result.get("sent", False)})
    return {
        "ok": True,
        "user_id": user_id,
        "company_id": co_id,
        "role": body.role,
        "magic_link": magic_link,
        "email_sent": email_result.get("sent", False),
        "email_reason": email_result.get("reason"),
        "note": "Magic-link email delivery via SendGrid — falls back to MOCKED when keys aren't configured",
    }
