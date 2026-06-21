"""Marketplace: business discovery, referrals, payouts, public trust badges."""
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Header, HTTPException

from core.db import db
from core.deps import get_user_from_token, audit, now_utc, new_id
from core.models import ReferralIn, ReferralFulfill
from core.scoring import compute_credit_score, build_trust_badge, verify_trust_signature

router = APIRouter()


@router.get("/marketplace/businesses")
async def marketplace_businesses(
    include_unverified: bool = False,
    authorization: Optional[str] = Header(None),
):
    """Industry-affinity-ranked Aidou-powered businesses, with public trust badges.

    By default, businesses with score < 600 are HIDDEN (quality-curated network).
    Pass include_unverified=true to see everyone."""
    user = await get_user_from_token(authorization)
    customer_mems = await db.memberships.find(
        {"user_id": user["user_id"], "role": "customer"}, {"_id": 0},
    ).to_list(100)
    customer_co_ids = {m["company_id"] for m in customer_mems}

    all_user_mems = await db.memberships.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(200)
    user_co_ids = {m["company_id"] for m in all_user_mems}
    user_industries: Dict[str, int] = {}
    if user_co_ids:
        cos_user = await db.companies.find({"company_id": {"$in": list(user_co_ids)}}, {"_id": 0}).to_list(200)
        for c in cos_user:
            ind = c.get("industry", "Other")
            user_industries[ind] = user_industries.get(ind, 0) + 1

    all_cos = await db.companies.find({}, {"_id": 0}).to_list(500)
    seen_ids = {c["company_id"] for c in all_cos}
    extras_raw = [
        {"company_id": "mp_ridgeline_logistics", "name": "RidgeLine Logistics", "industry": "Transportation",
         "logo_color": "#3B82F6", "rating": 4.7, "specialty": "Same-day freight", "min_price": "$80/run"},
        {"company_id": "mp_acadia_medical", "name": "Acadia Medical Group", "industry": "Healthcare",
         "logo_color": "#10B981", "rating": 4.9, "specialty": "Workplace clinics", "min_price": "$240/visit"},
        {"company_id": "mp_pinewood_school", "name": "Pinewood Training Studio", "industry": "Education",
         "logo_color": "#F59E0B", "rating": 4.6, "specialty": "Safety certifications", "min_price": "$95/seat"},
    ]
    extras = [e for e in extras_raw if e["company_id"] not in seen_ids]
    enriched = [
        {**c, "rating": 4.6, "specialty": f"{c.get('industry', 'Pro')} services",
         "min_price": "Custom quote", "is_member": c["company_id"] in customer_co_ids}
        for c in all_cos
    ] + extras

    def score(b: Dict[str, Any]) -> float:
        s = (b.get("rating", 4.0)) * 10.0
        ind = b.get("industry", "")
        affinity = user_industries.get(ind, 0)
        s += min(affinity, 3) * 8.0
        if b.get("company_id") not in user_co_ids:
            s += 12.0
        if b.get("company_id", "").startswith("mp_"):
            s += 6.0
        return round(s, 2)

    for b in enriched:
        b["score"] = score(b)
        b["recommended"] = b["score"] >= 60.0 and b["company_id"] not in user_co_ids
        b["match_reason"] = (
            f"Matches your {b['industry']} industry footprint"
            if user_industries.get(b.get("industry", "")) and b["company_id"] not in user_co_ids
            else ("New on the platform" if b.get("company_id", "").startswith("mp_") else "Top-rated")
        )

    # Attach public trust badge from latest snapshot (or live compute on miss).
    co_ids = [b["company_id"] for b in enriched]
    snaps = await db.credit_score_snapshots.find(
        {"company_id": {"$in": co_ids}}, {"_id": 0},
    ).sort("date", -1).to_list(2000)
    latest_by_co: Dict[str, Dict[str, Any]] = {}
    for snap in snaps:
        if snap["company_id"] not in latest_by_co:
            latest_by_co[snap["company_id"]] = snap

    visible: List[Dict[str, Any]] = []
    for b in enriched:
        co_id = b["company_id"]
        snap = latest_by_co.get(co_id)
        if snap is None:
            try:
                score_doc = await compute_credit_score(co_id)
            except Exception:
                score_doc = {"score": 0, "band": "Building"}
        else:
            score_doc = {"score": snap["score"], "band": snap["band"]}
        badge = build_trust_badge(b, score_doc)
        b["trust_badge"] = badge
        # Always show: companies user belongs to (any role), or verified (>=600), or include_unverified.
        is_own = co_id in user_co_ids
        if include_unverified or badge["verified"] or b.get("is_member") or is_own:
            visible.append(b)

    visible.sort(key=lambda x: x["score"], reverse=True)
    return {
        "businesses": visible,
        "user_industries": user_industries,
        "hidden_count": len(enriched) - len(visible),
    }


@router.get("/marketplace/trust-badge/{company_id}")
async def public_trust_badge(company_id: str):
    """Public, unauthenticated endpoint returning a signed trust badge for a company.

    Pairs with verify_trust_signature() for off-platform verification."""
    company = await db.companies.find_one({"company_id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="company not found")
    snap = await db.credit_score_snapshots.find_one(
        {"company_id": company_id}, {"_id": 0},
        sort=[("date", -1)],
    )
    if snap is None:
        score_doc = await compute_credit_score(company_id)
    else:
        score_doc = {"score": snap["score"], "band": snap["band"]}
    badge = build_trust_badge(company, score_doc)
    return {"badge": badge}


@router.post("/marketplace/trust-badge/verify")
async def verify_trust_badge(payload: Dict[str, Any]):
    """Verify a badge signature without DB access. Useful for third-party widgets."""
    sig = payload.pop("signature", None)
    if not sig:
        raise HTTPException(status_code=400, detail="signature missing")
    ok = verify_trust_signature(payload, sig)
    return {"valid": ok}


@router.post("/marketplace/referrals")
async def create_referral(body: ReferralIn, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    source_co = user.get("active_company_id")
    ref = {
        "referral_id": new_id("ref"),
        "source_user_id": user["user_id"],
        "source_company_id": source_co,
        "target_company_id": body.target_company_id,
        "note": body.note,
        "status": "pending",
        "share_percent": 5.0,
        "estimated_payout": 0.0,
        "created_at": now_utc(),
    }
    await db.referrals.insert_one(ref)
    ref.pop("_id", None)
    ref["created_at"] = ref["created_at"].isoformat()
    await audit(user, "create", "referral", meta={"target": body.target_company_id})
    return {"referral": ref}


@router.get("/marketplace/referrals")
async def list_referrals(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    refs = await db.referrals.find(
        {"source_user_id": user["user_id"]}, {"_id": 0},
    ).sort("created_at", -1).limit(50).to_list(50)
    for r in refs:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
    return {"referrals": refs}


@router.post("/marketplace/referrals/{referral_id}/fulfill")
async def fulfill_referral(referral_id: str, body: ReferralFulfill, authorization: Optional[str] = Header(None)):
    actor = await get_user_from_token(authorization)
    if actor.get("active_role") not in ("owner", "manager") and actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner/manager required to fulfill referrals")
    ref = await db.referrals.find_one({"referral_id": referral_id}, {"_id": 0})
    if not ref:
        raise HTTPException(status_code=404, detail="Referral not found")
    if ref.get("status") == "fulfilled":
        return {"referral": ref, "note": "already fulfilled"}
    if body.booking_value <= 0:
        raise HTTPException(status_code=400, detail="booking_value must be positive")
    payout = round(body.booking_value * (ref.get("share_percent", 5.0) / 100.0), 2)
    await db.referrals.update_one(
        {"referral_id": referral_id},
        {"$set": {
            "status": "fulfilled",
            "booking_value": body.booking_value,
            "estimated_payout": payout,
            "fulfilled_at": now_utc(),
            "fulfilled_by": actor["user_id"],
        }},
    )
    await db.payouts.insert_one({
        "payout_id": new_id("pay"),
        "referral_id": referral_id,
        "amount": payout,
        "source_company_id": ref.get("source_company_id"),
        "target_company_id": ref.get("target_company_id"),
        "status": "pending_disbursement",
        "created_at": now_utc(),
    })
    await audit(actor, "fulfill", "referral", meta={"referral_id": referral_id, "payout": payout})
    fresh = await db.referrals.find_one({"referral_id": referral_id}, {"_id": 0})
    if isinstance(fresh.get("created_at"), datetime):
        fresh["created_at"] = fresh["created_at"].isoformat()
    if isinstance(fresh.get("fulfilled_at"), datetime):
        fresh["fulfilled_at"] = fresh["fulfilled_at"].isoformat()
    return {"referral": fresh, "payout": payout}


@router.get("/marketplace/payouts")
async def list_payouts(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    if user.get("active_role") not in ("owner", "manager") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner/manager required")
    co_id = user.get("active_company_id")
    rows = await db.payouts.find(
        {"$or": [{"source_company_id": co_id}, {"target_company_id": co_id}]}, {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
    total_pending = sum(r["amount"] for r in rows if r.get("status") == "pending_disbursement")
    return {"payouts": rows, "total_pending": round(total_pending, 2)}
