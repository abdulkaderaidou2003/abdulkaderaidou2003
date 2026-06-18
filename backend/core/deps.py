"""Auth, RBAC, and audit log helpers."""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Sequence
import uuid

from fastapi import Header, HTTPException, Request

from .db import db


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# Role hierarchy: admin > manager > operator > viewer
ROLE_RANK = {"viewer": 1, "operator": 2, "manager": 3, "admin": 4}


def has_role(user: Dict[str, Any], allowed: Sequence[str]) -> bool:
    if not allowed:
        return True
    role = (user or {}).get("role", "viewer")
    min_rank = min(ROLE_RANK.get(r, 99) for r in allowed)
    return ROLE_RANK.get(role, 0) >= min_rank


async def get_user_from_token(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = sess.get("expires_at")
    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now_utc():
            raise HTTPException(status_code=401, detail="Session expired")
    user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_role(*roles: str):
    """FastAPI dependency factory: enforce that current user holds one of the given roles."""

    async def _dep(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
        user = await get_user_from_token(authorization)
        if not has_role(user, roles):
            raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(roles)}")
        return user

    return _dep


async def audit(
    user: Dict[str, Any],
    action: str,
    resource: str,
    *,
    request: Optional[Request] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Append an entry to the audit log. Never raises — best-effort."""
    try:
        entry = {
            "audit_id": new_id("aud"),
            "user_id": user.get("user_id"),
            "user_email": user.get("email"),
            "company_id": user.get("active_company_id"),
            "role": user.get("role"),
            "action": action,
            "resource": resource,
            "meta": meta or {},
            "ip": (request.client.host if request and request.client else None),
            "created_at": now_utc(),
        }
        await db.audit_log.insert_one(entry)
    except Exception as exc:  # pragma: no cover — best-effort logging
        import logging
        logging.getLogger(__name__).warning("audit() failed: %s", exc)
