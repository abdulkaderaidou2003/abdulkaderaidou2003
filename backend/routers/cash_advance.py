"""Aidou Cash Advance: offer, request, history, repayment schedule."""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Header, HTTPException

from core.db import db
from core.deps import get_user_from_token, audit, now_utc, new_id
from core.models import CashAdvanceRequest, DEFAULT_POLICY

router = APIRouter()


async def _build_offer_payload(user) -> dict:
    co_id = user.get("active_company_id")
    sales = await db.sales.find({"company_id": co_id}, {"_id": 0, "total": 1}).to_list(500)
    sales_total = sum(float(s.get("total", 0)) for s in sales)
    pay_runs = await db.pay_runs.find({"company_id": co_id}, {"_id": 0, "gross": 1}).to_list(50)
    payroll_total = sum(r.get("gross", 0) for r in pay_runs)
    payouts = await db.payouts.find(
        {"target_company_id": co_id}, {"_id": 0, "amount": 1, "status": 1},
    ).to_list(500)
    payout_inflow = sum(p.get("amount", 0) for p in payouts)
    projected_payouts_30d = round(payout_inflow * 0.5, 2)
    policy_doc = await db.underwriting_policy.find_one({"key": "global"}, {"_id": 0}) or {}
    policy = {**DEFAULT_POLICY, **{k: v for k, v in policy_doc.items() if k in DEFAULT_POLICY}}
    revenue_cap = max(sales_total * policy["pos_revenue_ltv"], payroll_total * policy["payroll_ltv"])
    raw_cap = max(projected_payouts_30d * policy["payout_projection_ltv"], revenue_cap)
    max_advance = round(max(policy["floor"], raw_cap), 2)
    eligible = (sales_total + payroll_total + payout_inflow) > 0
    open_adv = await db.cash_advances.find_one(
        {"company_id": co_id, "status": "outstanding"}, {"_id": 0},
    )
    if open_adv and isinstance(open_adv.get("created_at"), datetime):
        open_adv["created_at"] = open_adv["created_at"].isoformat()
    return {
        "eligible": eligible,
        "max_advance": max_advance,
        "rate_first_1k": 0.0,
        "rate_above_1k": 4.5,
        "underwriting_signals": {
            "pos_revenue_lifetime": round(sales_total, 2),
            "payroll_lifetime": round(payroll_total, 2),
            "referral_inflow_lifetime": round(payout_inflow, 2),
            "projected_payouts_30d": projected_payouts_30d,
        },
        "open_advance": open_adv,
        "tagline": "0% fee on your first $1,000 · funded in 24h · auto-repaid from future payouts",
    }


@router.get("/cash-advance/offer")
async def cash_advance_offer(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    if user.get("active_role") != "owner" and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner only")
    return await _build_offer_payload(user)


@router.post("/cash-advance/request")
async def request_cash_advance(body: CashAdvanceRequest, authorization: Optional[str] = Header(None)):
    actor = await get_user_from_token(authorization)
    if actor.get("active_role") != "owner" and actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner only")
    co_id = actor.get("active_company_id")
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    offer = await _build_offer_payload(actor)
    if body.amount > offer["max_advance"]:
        raise HTTPException(status_code=400, detail=f"Amount exceeds approved max ${offer['max_advance']:.2f}")
    if offer.get("open_advance"):
        raise HTTPException(status_code=409, detail="An outstanding advance already exists")
    policy_doc = await db.underwriting_policy.find_one({"key": "global"}, {"_id": 0}) or {}
    free_cap = float(policy_doc.get("free_band_cap", DEFAULT_POLICY["free_band_cap"]))
    fee_rate = float(policy_doc.get("fee_above_free", DEFAULT_POLICY["fee_above_free"]))
    fee = 0.0 if body.amount <= free_cap else round((body.amount - free_cap) * fee_rate, 2)
    adv = {
        "advance_id": new_id("adv"),
        "company_id": co_id,
        "requested_by": actor["user_id"],
        "amount": round(body.amount, 2),
        "fee": fee,
        "total_repayable": round(body.amount + fee, 2),
        "status": "outstanding",
        "created_at": now_utc(),
        "expected_repayment_source": "future_referral_payouts",
    }
    await db.cash_advances.insert_one(adv)
    adv.pop("_id", None)
    adv["created_at"] = adv["created_at"].isoformat()
    await audit(actor, "request", "cash_advance", meta={"amount": adv["amount"], "fee": fee})
    return {"advance": adv, "note": "Funds will land in your linked account within 24h. MOCKED — banking rails not yet integrated."}


@router.get("/cash-advance/history")
async def cash_advance_history(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    if user.get("active_role") != "owner" and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner only")
    co_id = user.get("active_company_id")
    rows = await db.cash_advances.find({"company_id": co_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
    return {"advances": rows}


@router.get("/cash-advance/repayment-schedule")
async def repayment_schedule(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    if user.get("active_role") != "owner" and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner only")
    co_id = user.get("active_company_id")
    adv = await db.cash_advances.find_one({"company_id": co_id, "status": "outstanding"}, {"_id": 0})
    if not adv:
        return {"has_advance": False, "schedule": [], "outstanding": 0.0, "covered_in_weeks": 0}
    payouts = await db.payouts.find({"target_company_id": co_id}, {"_id": 0, "amount": 1}).to_list(500)
    lifetime = sum(p.get("amount", 0) for p in payouts)
    weekly = max(lifetime / 12.0, adv["total_repayable"] / 8.0)
    schedule = []
    remaining = adv["total_repayable"]
    week = 0
    while remaining > 0.01 and week < 26:
        week += 1
        applied = round(min(weekly, remaining), 2)
        remaining = round(remaining - applied, 2)
        schedule.append({
            "week": week,
            "date": (now_utc() + timedelta(weeks=week)).date().isoformat(),
            "expected_inflow": round(weekly, 2),
            "applied_to_advance": applied,
            "remaining": remaining,
        })
    return {
        "has_advance": True,
        "advance_id": adv["advance_id"],
        "outstanding": adv["total_repayable"],
        "weekly_estimate": round(weekly, 2),
        "schedule": schedule,
        "covered_in_weeks": len(schedule),
    }
