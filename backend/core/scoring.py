"""Credit-score computation + nightly snapshot.

Used by /api/credit-score, /api/credit-score/history, /api/marketplace/trust-badge,
and the background snapshot job.
"""
from typing import Dict, Any, List, Tuple
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

from .db import db
from .deps import now_utc
from .models import DEFAULT_WEIGHTS


async def load_weights() -> Dict[str, Any]:
    """Return tunable scoring weights from db.underwriting_policy or defaults.
    Tunable weights live alongside the underwriting policy doc under key='weights'."""
    doc = await db.underwriting_policy.find_one({"key": "weights"}, {"_id": 0}) or {}
    return {**DEFAULT_WEIGHTS, **{k: v for k, v in doc.items() if k in DEFAULT_WEIGHTS}}


async def compute_credit_score(co_id: str) -> Dict[str, Any]:
    """Compute the full credit-score payload for a company (used by API + snapshots)."""
    weights = await load_weights()

    sales = await db.sales.find({"company_id": co_id}, {"_id": 0, "total": 1}).to_list(500)
    sales_total = sum(float(s.get("total", 0)) for s in sales)
    pay_runs = await db.pay_runs.find({"company_id": co_id}, {"_id": 0, "gross": 1, "status": 1}).to_list(50)
    payroll_total = sum(r.get("gross", 0) for r in pay_runs)
    posted_runs = sum(1 for r in pay_runs if r.get("status") == "posted")
    payouts = await db.payouts.find({"target_company_id": co_id}, {"_id": 0, "amount": 1}).to_list(500)
    payout_total = sum(p.get("amount", 0) for p in payouts)
    advances = await db.cash_advances.find({"company_id": co_id}, {"_id": 0, "status": 1}).to_list(50)
    repaid = sum(1 for a in advances if a.get("status") == "repaid")
    outstanding = sum(1 for a in advances if a.get("status") == "outstanding")
    employees = await db.employees.count_documents({"company_id": co_id})
    tickets_open = await db.tickets.count_documents({"company_id": co_id, "status": {"$in": ["open", "in_progress"]}})

    pos_score = min(int(weights["pos_revenue_cap"]), int(sales_total / max(1, weights["pos_revenue_divisor"])))
    payroll_score = min(int(weights["payroll_cap"]), int(payroll_total / max(1, weights["payroll_divisor"])))
    consistency = min(int(weights["consistency_cap"]), int(posted_runs * weights["consistency_per_run"]))
    referral_score = min(int(weights["referrals_cap"]), int(payout_total / max(1, weights["referrals_divisor"])))
    repayment_score = min(int(weights["repayment_cap"]), int(repaid * weights["repayment_per_repaid"]))
    team_score = min(int(weights["team_cap"]), int(employees * weights["team_per_employee"]))
    ops_penalty = min(int(weights["ops_penalty_cap"]), int(tickets_open * weights["ops_penalty_per_ticket"]))
    base = int(weights["baseline"])
    raw = base + pos_score + payroll_score + consistency + referral_score + repayment_score + team_score - ops_penalty
    score = max(0, min(1000, int(raw)))

    band, tone = (
        ("Exceptional", "success") if score >= 850 else
        ("Excellent", "success") if score >= 700 else
        ("Good", "ops") if score >= 550 else
        ("Fair", "warning") if score >= 400 else
        ("Building", "info")
    )

    nudges: List[Dict[str, str]] = []
    if posted_runs < 4:
        nudges.append({"text": "Post 3 more pay runs to unlock consistency boost", "delta": "+75"})
    if payout_total < 100:
        nudges.append({"text": "Fulfill marketplace referrals to add referral inflow signal", "delta": "+50"})
    if employees < 10:
        nudges.append({"text": "Add 4 more employees on the HR module", "delta": "+16"})
    if outstanding == 0 and repaid == 0:
        nudges.append({"text": "Take and repay a $1k Cash Advance to build repayment history", "delta": "+60"})
    if tickets_open > 8:
        nudges.append({"text": f"Resolve {tickets_open - 5} open tickets to lift the ops penalty", "delta": "+15"})

    perks = [p for p in [
        "Lower Cash Advance fee tiers" if score >= 700 else None,
        "Faster invoice factoring" if score >= 800 else None,
        "B2B credit line unlocked" if score >= 850 else None,
        "Marketplace verified badge" if score >= 600 else None,
    ] if p]

    return {
        "score": score,
        "band": band,
        "tone": tone,
        "breakdown": {
            "pos_revenue": pos_score,
            "payroll": payroll_score,
            "consistency": consistency,
            "referrals": referral_score,
            "repayment_history": repayment_score,
            "team_size": team_score,
            "ops_penalty": -ops_penalty,
            "baseline": base,
        },
        "nudges": nudges,
        "perks": perks,
        "headline": f"Aidou Network Score · {band} ({score}/1000)",
        "weights": weights,
    }


def _trust_signing_key() -> bytes:
    """Stable signing key for public trust badges. Uses TRUST_SIGNING_KEY env or DB_NAME-derived fallback."""
    key = os.environ.get("TRUST_SIGNING_KEY")
    if not key:
        # Deterministic fallback so badges still verify across worker restarts.
        key = f"aidou-trust-{os.environ.get('DB_NAME', 'default')}"
    return key.encode("utf-8")


def sign_trust_payload(payload: Dict[str, Any]) -> str:
    """HMAC-SHA256 sign a JSON payload (sorted keys) and return hex digest."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_trust_signing_key(), raw, hashlib.sha256).hexdigest()


def verify_trust_signature(payload: Dict[str, Any], signature: str) -> bool:
    expected = sign_trust_payload(payload)
    return hmac.compare_digest(expected, signature)


def build_trust_badge(company: Dict[str, Any], score_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Build a redacted, signed public trust badge for marketplace display."""
    score = int(score_doc.get("score", 0))
    band = score_doc.get("band", "Building")
    verified = score >= 600
    payload = {
        "company_id": company.get("company_id"),
        "company_name": company.get("name"),
        "industry": company.get("industry"),
        "score": score,
        "band": band,
        "verified": verified,
        "issued_at": now_utc().replace(microsecond=0).isoformat(),
    }
    payload["signature"] = sign_trust_payload(payload)
    return payload


async def snapshot_all_companies() -> List[Tuple[str, int]]:
    """Persist a daily snapshot of each company's score. Idempotent per (company_id, date).
    Returns list of (company_id, score) tuples for logging/testing."""
    today_iso = now_utc().date().isoformat()
    cos = await db.companies.find({}, {"_id": 0, "company_id": 1}).to_list(1000)
    written: List[Tuple[str, int]] = []
    for c in cos:
        co_id = c["company_id"]
        try:
            payload = await compute_credit_score(co_id)
        except Exception:
            continue
        await db.credit_score_snapshots.update_one(
            {"company_id": co_id, "date": today_iso},
            {"$set": {
                "company_id": co_id,
                "date": today_iso,
                "score": payload["score"],
                "band": payload["band"],
                "breakdown": payload["breakdown"],
                "created_at": now_utc(),
            }},
            upsert=True,
        )
        written.append((co_id, payload["score"]))
    return written
