"""Underwriting policy, tunable scoring weights, credit score, history."""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Header, HTTPException

from core.db import db
from core.deps import get_user_from_token, audit, now_utc
from core.models import UnderwritingPolicy, ScoringWeights, DEFAULT_POLICY, DEFAULT_WEIGHTS
from core.scoring import compute_credit_score, snapshot_all_companies, load_weights

router = APIRouter()


def _require_owner_or_admin(user):
    if user.get("active_role") != "owner" and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner only")


def _require_owner_manager_or_admin(user):
    if user.get("active_role") not in ("owner", "manager") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner/manager required")


@router.get("/underwriting/policy")
async def get_policy(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    _require_owner_or_admin(user)
    doc = await db.underwriting_policy.find_one({"key": "global"}, {"_id": 0}) or {}
    return {"policy": {**DEFAULT_POLICY, **{k: v for k, v in doc.items() if k in DEFAULT_POLICY}}}


@router.put("/underwriting/policy")
async def put_policy(body: UnderwritingPolicy, authorization: Optional[str] = Header(None)):
    actor = await get_user_from_token(authorization)
    _require_owner_or_admin(actor)
    payload = body.model_dump()
    await db.underwriting_policy.update_one(
        {"key": "global"},
        {"$set": {"key": "global", **payload, "updated_by": actor["user_id"], "updated_at": now_utc()}},
        upsert=True,
    )
    await audit(actor, "update", "underwriting_policy", meta=payload)
    return {"policy": payload}


@router.get("/underwriting/weights")
async def get_weights(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    _require_owner_or_admin(user)
    return {"weights": await load_weights()}


@router.put("/underwriting/weights")
async def put_weights(body: ScoringWeights, authorization: Optional[str] = Header(None)):
    actor = await get_user_from_token(authorization)
    _require_owner_or_admin(actor)
    payload = body.model_dump()
    await db.underwriting_policy.update_one(
        {"key": "weights"},
        {"$set": {"key": "weights", **payload, "updated_by": actor["user_id"], "updated_at": now_utc()}},
        upsert=True,
    )
    await audit(actor, "update", "scoring_weights", meta=payload)
    return {"weights": payload}


@router.get("/credit-score")
async def credit_score(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    _require_owner_manager_or_admin(user)
    co_id = user.get("active_company_id")
    return await compute_credit_score(co_id)


@router.get("/credit-score/history")
async def credit_score_history(
    days: int = 30,
    authorization: Optional[str] = Header(None),
):
    """Return up to `days` of daily score snapshots for the active company.

    Used by the trajectory chart on the Owner dashboard.
    Triggers a fresh snapshot for today if missing so the chart always shows the latest point."""
    user = await get_user_from_token(authorization)
    _require_owner_manager_or_admin(user)
    co_id = user.get("active_company_id")
    days = max(7, min(365, days))
    cutoff_iso = (now_utc() - timedelta(days=days)).date().isoformat()

    today_iso = now_utc().date().isoformat()
    existing_today = await db.credit_score_snapshots.find_one(
        {"company_id": co_id, "date": today_iso}, {"_id": 0},
    )
    if not existing_today:
        payload = await compute_credit_score(co_id)
        await db.credit_score_snapshots.update_one(
            {"company_id": co_id, "date": today_iso},
            {"$set": {
                "company_id": co_id, "date": today_iso,
                "score": payload["score"], "band": payload["band"],
                "breakdown": payload["breakdown"], "created_at": now_utc(),
            }},
            upsert=True,
        )

    snaps = await db.credit_score_snapshots.find(
        {"company_id": co_id, "date": {"$gte": cutoff_iso}},
        {"_id": 0, "date": 1, "score": 1, "band": 1},
    ).sort("date", 1).to_list(500)

    delta_30d = 0
    if len(snaps) >= 2:
        delta_30d = snaps[-1]["score"] - snaps[0]["score"]
    return {
        "company_id": co_id,
        "days": days,
        "snapshots": snaps,
        "latest_score": snaps[-1]["score"] if snaps else 0,
        "trend": "up" if delta_30d > 0 else ("down" if delta_30d < 0 else "flat"),
        "delta_period": delta_30d,
    }


@router.post("/credit-score/snapshot-now")
async def snapshot_now(authorization: Optional[str] = Header(None)):
    """Manually trigger a snapshot of ALL companies (admin only). Idempotent per date."""
    actor = await get_user_from_token(authorization)
    if actor.get("role") != "admin" and actor.get("active_role") != "owner":
        raise HTTPException(status_code=403, detail="Owner/admin required")
    written = await snapshot_all_companies()
    await audit(actor, "snapshot", "credit_scores", meta={"count": len(written)})
    return {"snapshotted": len(written), "date": now_utc().date().isoformat()}
