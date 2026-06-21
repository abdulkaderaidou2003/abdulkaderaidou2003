"""Iteration 9 — Router split + tunable weights + credit-score history + public trust badge.

Validates the new endpoints introduced after the per-module router split:
- GET/PUT /api/underwriting/weights
- GET /api/credit-score/history
- POST /api/credit-score/snapshot-now
- GET /api/marketplace/trust-badge/{company_id} (public, no auth)
- POST /api/marketplace/trust-badge/verify (public, no auth)
- GET /api/marketplace/businesses?include_unverified=false trust badge presence
"""
import secrets
from datetime import datetime, timezone, timedelta

import pytest

from tests.conftest import BASE_URL


def _make_owner(mongo):
    user_id = f"user_{secrets.token_hex(6)}"
    token = f"TEST_{secrets.token_hex(16)}"
    mongo.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "email": f"TEST_{user_id}@example.com",
            "name": "Owner Test",
            "company_ids": ["co_aidou_corp"],
            "active_company_id": "co_aidou_corp",
            "active_role": "owner",
            "role": "admin",
            "created_at": datetime.now(timezone.utc),
            "last_login": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    mongo.memberships.update_one(
        {"user_id": user_id, "company_id": "co_aidou_corp", "role": "owner"},
        {"$setOnInsert": {
            "membership_id": f"mem_{secrets.token_hex(6)}",
            "user_id": user_id, "company_id": "co_aidou_corp", "role": "owner",
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    mongo.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        "created_at": datetime.now(timezone.utc),
    })
    return {"user_id": user_id, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


def _cleanup(mongo, user_id):
    mongo.user_sessions.delete_many({"user_id": user_id})
    mongo.users.delete_many({"user_id": user_id})
    mongo.memberships.delete_many({"user_id": user_id})


class TestTunableScoringWeights:
    def test_get_weights_returns_defaults(self, api_client, mongo):
        u = _make_owner(mongo)
        try:
            r = api_client.get(f"{BASE_URL}/api/underwriting/weights", headers=u["headers"])
            assert r.status_code == 200, r.text
            w = r.json()["weights"]
            assert w["pos_revenue_cap"] == 300
            assert w["baseline"] == 100
            assert w["ops_penalty_per_ticket"] == 3
        finally:
            _cleanup(mongo, u["user_id"])

    def test_put_weights_persists_and_changes_score(self, api_client, mongo):
        u = _make_owner(mongo)
        try:
            base = api_client.get(f"{BASE_URL}/api/credit-score", headers=u["headers"]).json()
            new_weights = {
                "pos_revenue_cap": 100, "pos_revenue_divisor": 1000,
                "payroll_cap": 50, "payroll_divisor": 5000,
                "consistency_cap": 50, "consistency_per_run": 25,
                "referrals_cap": 50, "referrals_divisor": 10,
                "repayment_cap": 50, "repayment_per_repaid": 60,
                "team_cap": 25, "team_per_employee": 4,
                "ops_penalty_cap": 25, "ops_penalty_per_ticket": 3,
                "baseline": 100,
            }
            r = api_client.put(
                f"{BASE_URL}/api/underwriting/weights", json=new_weights, headers=u["headers"],
            )
            assert r.status_code == 200, r.text
            after = api_client.get(f"{BASE_URL}/api/credit-score", headers=u["headers"]).json()
            assert after["weights"]["pos_revenue_cap"] == 100
            # Score must shift because caps changed.
            assert after["score"] != base["score"] or after["breakdown"] != base["breakdown"]
        finally:
            mongo.underwriting_policy.delete_one({"key": "weights"})
            _cleanup(mongo, u["user_id"])


class TestCreditScoreHistory:
    def test_history_creates_today_snapshot(self, api_client, mongo):
        u = _make_owner(mongo)
        try:
            today_iso = datetime.now(timezone.utc).date().isoformat()
            mongo.credit_score_snapshots.delete_many({
                "company_id": "co_aidou_corp", "date": today_iso,
            })
            r = api_client.get(f"{BASE_URL}/api/credit-score/history?days=30", headers=u["headers"])
            assert r.status_code == 200, r.text
            body = r.json()
            assert "snapshots" in body
            assert len(body["snapshots"]) >= 1
            assert body["snapshots"][-1]["date"] == today_iso
            assert body["trend"] in ("up", "down", "flat")
        finally:
            _cleanup(mongo, u["user_id"])

    def test_snapshot_now_writes_all_companies(self, api_client, mongo):
        u = _make_owner(mongo)
        try:
            r = api_client.post(
                f"{BASE_URL}/api/credit-score/snapshot-now", headers=u["headers"],
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["snapshotted"] >= 3  # at least the seeded companies
        finally:
            _cleanup(mongo, u["user_id"])


class TestPublicTrustBadge:
    def test_public_badge_no_auth_required(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/marketplace/trust-badge/co_aidou_corp")
        assert r.status_code == 200, r.text
        badge = r.json()["badge"]
        assert badge["company_id"] == "co_aidou_corp"
        assert "score" in badge and "signature" in badge
        assert isinstance(badge["verified"], bool)

    def test_badge_signature_verifies(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/marketplace/trust-badge/co_aidou_corp")
        badge = r.json()["badge"]
        # Verify endpoint
        v = api_client.post(f"{BASE_URL}/api/marketplace/trust-badge/verify", json=badge)
        assert v.status_code == 200
        assert v.json()["valid"] is True

    def test_badge_signature_rejects_tampered(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/marketplace/trust-badge/co_aidou_corp")
        badge = r.json()["badge"]
        badge["score"] = 999  # tamper
        v = api_client.post(f"{BASE_URL}/api/marketplace/trust-badge/verify", json=badge)
        assert v.status_code == 200
        assert v.json()["valid"] is False

    def test_unknown_company_404(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/marketplace/trust-badge/co_nonexistent_xyz")
        assert r.status_code == 404


class TestMarketplaceTrustBadgeOnBusinesses:
    def test_default_hides_unverified_low_score_extras(self, api_client, mongo):
        u = _make_owner(mongo)
        try:
            r = api_client.get(f"{BASE_URL}/api/marketplace/businesses", headers=u["headers"])
            assert r.status_code == 200, r.text
            body = r.json()
            # Owner is member of co_aidou_corp so it shows up
            ids = {b["company_id"] for b in body["businesses"]}
            assert "co_aidou_corp" in ids
            # All shown items must have trust_badge attached
            for b in body["businesses"]:
                assert "trust_badge" in b
                assert "signature" in b["trust_badge"]
            assert "hidden_count" in body
        finally:
            _cleanup(mongo, u["user_id"])

    def test_include_unverified_shows_all(self, api_client, mongo):
        u = _make_owner(mongo)
        try:
            r = api_client.get(
                f"{BASE_URL}/api/marketplace/businesses?include_unverified=true",
                headers=u["headers"],
            )
            assert r.status_code == 200, r.text
            body = r.json()
            ids = {b["company_id"] for b in body["businesses"]}
            # All seeded + marketplace stubs should be present
            assert {"co_aidou_corp", "co_northstar_isp", "co_summit_construction"}.issubset(ids)
            assert {"mp_ridgeline_logistics", "mp_acadia_medical", "mp_pinewood_school"}.issubset(ids)
            assert body["hidden_count"] == 0
        finally:
            _cleanup(mongo, u["user_id"])
