"""Iteration 7 backend tests — marketplace partner companies seeded into db.companies,
Aidou Cash Advance (Square Capital-style) endpoints (offer, request, history),
including 401/403 gating, business rules (fee bands, cap, outstanding lock), and audit.

Uses shared fixtures from conftest.py.
"""
import secrets
from datetime import datetime, timezone, timedelta

import pytest


BASE_URL = None


@pytest.fixture(autouse=True, scope="module")
def _set_base_url(base_url):
    global BASE_URL
    BASE_URL = base_url


# ---------- helpers ----------
def _make_user(mongo, *, active_role=None, role="member",
               active_company_id="co_aidou_corp", extra_company_ids=None):
    user_id = f"user_{secrets.token_hex(6)}"
    token = f"TEST_{secrets.token_hex(16)}"
    now = datetime.now(timezone.utc)
    company_ids = ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"]
    if extra_company_ids:
        for cid in extra_company_ids:
            if cid not in company_ids:
                company_ids.append(cid)
    if active_company_id not in company_ids:
        company_ids.append(active_company_id)
    mongo.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "email": f"TEST_{user_id}@example.com",
            "name": "TEST User",
            "picture": "",
            "company_ids": company_ids,
            "active_company_id": active_company_id,
            "active_role": active_role,
            "role": role,
            "created_at": now,
        }},
        upsert=True,
    )
    mongo.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "expires_at": now + timedelta(days=7),
        "created_at": now,
    })
    return {"user_id": user_id, "token": token,
            "headers": {"Authorization": f"Bearer {token}"}}


def _cleanup_user(mongo, user_id):
    mongo.user_sessions.delete_many({"user_id": user_id})
    mongo.memberships.delete_many({"user_id": user_id})
    mongo.users.delete_many({"user_id": user_id})
    mongo.audit_log.delete_many({"user_id": user_id})


def _make_iso_test_company(mongo, *, with_sales_total=0.0, with_payroll=0.0):
    """Create an isolated company so cash advance state is independent across tests."""
    co_id = f"co_test_{secrets.token_hex(5)}"
    mongo.companies.insert_one({
        "company_id": co_id,
        "name": f"TEST Company {co_id}",
        "industry": "Test",
        "logo_color": "#000000",
        "created_at": datetime.now(timezone.utc),
    })
    if with_sales_total > 0:
        # one big sale so revenue_cap is large enough to allow >1000 advance
        mongo.sales.insert_one({
            "sale_id": f"sale_TEST_{secrets.token_hex(4)}",
            "company_id": co_id,
            "total": float(with_sales_total),
            "created_at": datetime.now(timezone.utc),
        })
    if with_payroll > 0:
        mongo.pay_runs.insert_one({
            "pay_run_id": f"pr_TEST_{secrets.token_hex(4)}",
            "company_id": co_id,
            "gross": float(with_payroll),
            "created_at": datetime.now(timezone.utc),
        })
    return co_id


def _cleanup_company(mongo, co_id):
    mongo.companies.delete_many({"company_id": co_id})
    mongo.sales.delete_many({"company_id": co_id})
    mongo.pay_runs.delete_many({"company_id": co_id})
    mongo.cash_advances.delete_many({"company_id": co_id})
    mongo.payouts.delete_many({"$or": [
        {"source_company_id": co_id}, {"target_company_id": co_id}
    ]})


# ============================================================
# 1. Marketplace partner companies seeded into db.companies
# ============================================================
class TestMarketplacePartnersSeeded:
    EXPECTED_MP_IDS = {
        "mp_ridgeline_logistics",
        "mp_acadia_medical",
        "mp_pinewood_school",
    }

    def test_mp_partners_present_in_db_companies(self, mongo):
        rows = list(mongo.companies.find(
            {"company_id": {"$in": list(self.EXPECTED_MP_IDS)}},
            {"_id": 0, "company_id": 1, "name": 1, "industry": 1},
        ))
        found_ids = {r["company_id"] for r in rows}
        assert self.EXPECTED_MP_IDS.issubset(found_ids), (
            f"expected mp_* companies missing from db.companies. "
            f"found={found_ids}, expected={self.EXPECTED_MP_IDS}"
        )
        # Sanity: industries match the iteration spec
        by_id = {r["company_id"]: r for r in rows}
        assert by_id["mp_ridgeline_logistics"]["industry"] == "Transportation"
        assert by_id["mp_acadia_medical"]["industry"] == "Healthcare"
        assert by_id["mp_pinewood_school"]["industry"] == "Education"

    def test_marketplace_businesses_endpoint_includes_mp_partners(self, api_client, mongo):
        u = _make_user(mongo)
        try:
            r = api_client.get(f"{BASE_URL}/api/marketplace/businesses?include_unverified=true",
                               headers=u["headers"])
            assert r.status_code == 200, r.text
            biz_ids = {b["company_id"] for b in r.json()["businesses"]}
            assert self.EXPECTED_MP_IDS.issubset(biz_ids), (
                f"/api/marketplace/businesses missing mp_* ids. got={biz_ids}"
            )
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_fulfill_referral_with_mp_partner_persists_payout_pointing_to_real_company(
        self, api_client, mongo,
    ):
        u = _make_user(mongo, active_role="owner", active_company_id="co_aidou_corp")
        # create referral targeting an mp_ partner that now exists in db.companies
        r1 = api_client.post(
            f"{BASE_URL}/api/marketplace/referrals",
            json={"target_company_id": "mp_pinewood_school", "note": "TEST iter7"},
            headers=u["headers"],
        )
        assert r1.status_code == 200, r1.text
        ref_id = r1.json()["referral"]["referral_id"]
        try:
            r2 = api_client.post(
                f"{BASE_URL}/api/marketplace/referrals/{ref_id}/fulfill",
                json={"booking_value": 400.0},
                headers=u["headers"],
            )
            assert r2.status_code == 200, r2.text
            d = r2.json()
            assert d["payout"] == pytest.approx(20.0)
            payout_doc = mongo.payouts.find_one({"referral_id": ref_id})
            assert payout_doc is not None
            assert payout_doc["target_company_id"] == "mp_pinewood_school"
            # Target company must really exist in db.companies (iter 7 contract)
            tgt = mongo.companies.find_one({"company_id": "mp_pinewood_school"})
            assert tgt is not None
        finally:
            mongo.payouts.delete_many({"referral_id": ref_id})
            mongo.referrals.delete_one({"referral_id": ref_id})
            _cleanup_user(mongo, u["user_id"])


# ============================================================
# 2. GET /api/cash-advance/offer
# ============================================================
class TestCashAdvanceOffer:
    def test_offer_requires_bearer(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/cash-advance/offer")
        assert r.status_code == 401

    def test_offer_forbidden_for_non_owner_non_admin(self, api_client, mongo):
        u = _make_user(mongo, active_role="employee", role="member")
        try:
            r = api_client.get(f"{BASE_URL}/api/cash-advance/offer",
                               headers=u["headers"])
            assert r.status_code == 403, r.text
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_offer_200_for_owner_returns_expected_shape(self, api_client, mongo):
        co_id = _make_iso_test_company(mongo, with_sales_total=20000.0)
        u = _make_user(mongo, active_role="owner", active_company_id=co_id,
                       extra_company_ids=[co_id])
        try:
            r = api_client.get(f"{BASE_URL}/api/cash-advance/offer",
                               headers=u["headers"])
            assert r.status_code == 200, r.text
            d = r.json()
            for k in ("eligible", "max_advance", "rate_first_1k", "rate_above_1k",
                      "underwriting_signals", "open_advance", "tagline"):
                assert k in d, f"missing key: {k} in offer response {d}"
            assert d["rate_first_1k"] == 0.0
            assert d["rate_above_1k"] == 4.5
            assert isinstance(d["max_advance"], (int, float))
            assert d["max_advance"] >= 1000.0  # floor
            assert d["eligible"] is True  # we seeded sales
            sig = d["underwriting_signals"]
            for k in ("pos_revenue_lifetime", "payroll_lifetime",
                      "referral_inflow_lifetime", "projected_payouts_30d"):
                assert k in sig
            # open_advance should be None when no outstanding advance exists
            assert d["open_advance"] in (None,)
            assert isinstance(d["tagline"], str) and d["tagline"]
        finally:
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)


# ============================================================
# 3. POST /api/cash-advance/request
# ============================================================
class TestCashAdvanceRequest:
    def test_request_requires_bearer(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/cash-advance/request",
                            json={"amount": 500.0})
        assert r.status_code == 401

    def test_request_forbidden_for_non_owner_non_admin(self, api_client, mongo):
        u = _make_user(mongo, active_role="employee", role="member")
        try:
            r = api_client.post(f"{BASE_URL}/api/cash-advance/request",
                                json={"amount": 500.0},
                                headers=u["headers"])
            assert r.status_code == 403, r.text
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_request_400_for_non_positive_amount(self, api_client, mongo):
        co_id = _make_iso_test_company(mongo, with_sales_total=20000.0)
        u = _make_user(mongo, active_role="owner", active_company_id=co_id,
                       extra_company_ids=[co_id])
        try:
            r1 = api_client.post(f"{BASE_URL}/api/cash-advance/request",
                                 json={"amount": 0},
                                 headers=u["headers"])
            assert r1.status_code == 400, r1.text
            r2 = api_client.post(f"{BASE_URL}/api/cash-advance/request",
                                 json={"amount": -50.0},
                                 headers=u["headers"])
            assert r2.status_code == 400, r2.text
        finally:
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)

    def test_request_400_when_amount_exceeds_max(self, api_client, mongo):
        co_id = _make_iso_test_company(mongo, with_sales_total=20000.0)
        u = _make_user(mongo, active_role="owner", active_company_id=co_id,
                       extra_company_ids=[co_id])
        try:
            # Fetch offer to learn max_advance
            ro = api_client.get(f"{BASE_URL}/api/cash-advance/offer",
                                headers=u["headers"])
            assert ro.status_code == 200
            max_adv = ro.json()["max_advance"]
            r = api_client.post(f"{BASE_URL}/api/cash-advance/request",
                                json={"amount": max_adv + 1000.0},
                                headers=u["headers"])
            assert r.status_code == 400, r.text
        finally:
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)

    def test_request_success_fee_zero_below_1k_and_audit_written(self, api_client, mongo):
        co_id = _make_iso_test_company(mongo, with_sales_total=20000.0)
        u = _make_user(mongo, active_role="owner", active_company_id=co_id,
                       extra_company_ids=[co_id])
        try:
            r = api_client.post(f"{BASE_URL}/api/cash-advance/request",
                                json={"amount": 800.0},
                                headers=u["headers"])
            assert r.status_code == 200, r.text
            d = r.json()
            adv = d["advance"]
            assert adv["amount"] == 800.0
            assert adv["fee"] == 0.0  # under 1k => no fee
            assert adv["total_repayable"] == 800.0
            assert adv["status"] == "outstanding"
            assert adv["company_id"] == co_id
            assert isinstance(adv["advance_id"], str) and adv["advance_id"].startswith("adv_")
            # Persisted
            row = mongo.cash_advances.find_one({"advance_id": adv["advance_id"]})
            assert row is not None and row["amount"] == 800.0 and row["fee"] == 0.0
            # Audit
            audits = list(mongo.audit_log.find({
                "user_id": u["user_id"], "resource": "cash_advance", "action": "request",
            }))
            assert len(audits) >= 1
            meta = audits[-1].get("meta") or {}
            assert meta.get("amount") == 800.0
            assert meta.get("fee") == 0.0
        finally:
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)

    def test_request_success_fee_for_above_1k_band(self, api_client, mongo):
        # max_advance formula:
        #   max_advance = min(max(projected_payouts_30d * 0.8, 1000), revenue_cap + 1000)
        #   projected_payouts_30d = payout_inflow * 0.5
        # To unlock > $1000, we need projected*0.8 > 1000 => payout_inflow > 2500.
        # Seed payouts targeting our test company so projected_payouts_30d is large.
        co_id = _make_iso_test_company(mongo, with_sales_total=200000.0)
        # Inbound payouts of 10_000 => projected=5000 => max base=4000, capped by
        # revenue_cap(=200000*0.15=30000)+1000=31000 => max_advance=4000. Plenty for $1500.
        payout_id = f"pay_TEST_{secrets.token_hex(4)}"
        mongo.payouts.insert_one({
            "payout_id": payout_id, "referral_id": f"ref_TEST_{secrets.token_hex(4)}",
            "amount": 10000.0, "source_company_id": "co_aidou_corp",
            "target_company_id": co_id,
            "status": "pending_disbursement",
            "created_at": datetime.now(timezone.utc),
        })
        u = _make_user(mongo, active_role="owner", active_company_id=co_id,
                       extra_company_ids=[co_id])
        try:
            r = api_client.post(f"{BASE_URL}/api/cash-advance/request",
                                json={"amount": 1500.0},
                                headers=u["headers"])
            assert r.status_code == 200, r.text
            adv = r.json()["advance"]
            # fee = (1500-1000) * 0.045 = 22.5
            assert adv["amount"] == 1500.0
            assert adv["fee"] == pytest.approx(22.5)
            assert adv["total_repayable"] == pytest.approx(1522.5)
            # Audit meta has both amount + fee
            audits = list(mongo.audit_log.find({
                "user_id": u["user_id"], "resource": "cash_advance", "action": "request",
            }))
            assert len(audits) >= 1
            meta = audits[-1].get("meta") or {}
            assert meta.get("amount") == 1500.0
            assert meta.get("fee") == pytest.approx(22.5)
        finally:
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)

    def test_request_409_when_outstanding_advance_exists(self, api_client, mongo):
        co_id = _make_iso_test_company(mongo, with_sales_total=20000.0)
        u = _make_user(mongo, active_role="owner", active_company_id=co_id,
                       extra_company_ids=[co_id])
        try:
            r1 = api_client.post(f"{BASE_URL}/api/cash-advance/request",
                                 json={"amount": 500.0},
                                 headers=u["headers"])
            assert r1.status_code == 200, r1.text
            # Second call should be locked out
            r2 = api_client.post(f"{BASE_URL}/api/cash-advance/request",
                                 json={"amount": 200.0},
                                 headers=u["headers"])
            assert r2.status_code == 409, r2.text
        finally:
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)


# ============================================================
# 4. GET /api/cash-advance/history
# ============================================================
class TestCashAdvanceHistory:
    def test_history_requires_bearer(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/cash-advance/history")
        assert r.status_code == 401

    def test_history_forbidden_for_non_owner(self, api_client, mongo):
        u = _make_user(mongo, active_role="employee", role="member")
        try:
            r = api_client.get(f"{BASE_URL}/api/cash-advance/history",
                               headers=u["headers"])
            assert r.status_code == 403, r.text
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_history_returns_advances_newest_first_for_active_company(
        self, api_client, mongo,
    ):
        co_id = _make_iso_test_company(mongo)
        u = _make_user(mongo, active_role="owner", active_company_id=co_id,
                       extra_company_ids=[co_id])
        # Insert 3 advances with explicit timestamps + one for another company
        now = datetime.now(timezone.utc)
        rows = [
            {"advance_id": f"adv_TEST_{secrets.token_hex(4)}", "company_id": co_id,
             "requested_by": u["user_id"], "amount": 100.0, "fee": 0.0,
             "total_repayable": 100.0, "status": "outstanding",
             "created_at": now - timedelta(days=2)},
            {"advance_id": f"adv_TEST_{secrets.token_hex(4)}", "company_id": co_id,
             "requested_by": u["user_id"], "amount": 200.0, "fee": 0.0,
             "total_repayable": 200.0, "status": "repaid",
             "created_at": now - timedelta(days=1)},
            {"advance_id": f"adv_TEST_{secrets.token_hex(4)}", "company_id": co_id,
             "requested_by": u["user_id"], "amount": 300.0, "fee": 0.0,
             "total_repayable": 300.0, "status": "repaid",
             "created_at": now},
            # Different company — must NOT appear
            {"advance_id": f"adv_TEST_{secrets.token_hex(4)}",
             "company_id": "co_aidou_corp",
             "requested_by": u["user_id"], "amount": 999.0, "fee": 0.0,
             "total_repayable": 999.0, "status": "repaid",
             "created_at": now},
        ]
        for r in rows:
            mongo.cash_advances.insert_one(r)
        ids = [r["advance_id"] for r in rows]
        try:
            r = api_client.get(f"{BASE_URL}/api/cash-advance/history",
                               headers=u["headers"])
            assert r.status_code == 200, r.text
            advances = r.json()["advances"]
            returned_ids = [a["advance_id"] for a in advances]
            # Only the 3 belonging to our test company, ordered newest first
            assert returned_ids == [ids[2], ids[1], ids[0]], (
                f"history order wrong. got={returned_ids}, expected="
                f"{[ids[2], ids[1], ids[0]]}"
            )
            # The unrelated other-company advance must NOT leak in
            assert ids[3] not in returned_ids
            # created_at must be ISO-serialized string
            assert all(isinstance(a["created_at"], str) for a in advances)
        finally:
            mongo.cash_advances.delete_many({"advance_id": {"$in": ids}})
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)
