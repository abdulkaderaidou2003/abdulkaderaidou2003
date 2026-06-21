"""Iteration 8 backend tests — configurable underwriting policy
(db.underwriting_policy), Cash Advance repayment schedule, and Aidou Network
Credit Score (0–1000).

Endpoints under test:
  - GET  /api/underwriting/policy
  - PUT  /api/underwriting/policy
  - GET  /api/cash-advance/repayment-schedule
  - GET  /api/credit-score
  - Policy hot-reload effect on GET /api/cash-advance/offer

Uses shared fixtures from conftest.py.
"""
import secrets
from datetime import datetime, timezone, timedelta

import pytest


BASE_URL = None
DEFAULT_POLICY = {
    "pos_revenue_ltv": 0.15,
    "payroll_ltv": 0.05,
    "payout_projection_ltv": 0.80,
    "free_band_cap": 1000.0,
    "fee_above_free": 0.045,
    "floor": 1000.0,
}


@pytest.fixture(autouse=True, scope="module")
def _set_base_url(base_url):
    global BASE_URL
    BASE_URL = base_url


# ---------------- helpers (mirroring iter7 patterns) ----------------
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


def _make_iso_test_company(mongo, *, with_sales_total=0.0, with_payroll=0.0,
                           with_payout_inflow=0.0, with_employees=0,
                           posted_pay_runs=0):
    co_id = f"co_test_{secrets.token_hex(5)}"
    mongo.companies.insert_one({
        "company_id": co_id,
        "name": f"TEST Company {co_id}",
        "industry": "Test",
        "logo_color": "#000000",
        "created_at": datetime.now(timezone.utc),
    })
    if with_sales_total > 0:
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
            "status": "posted" if posted_pay_runs > 0 else "draft",
            "created_at": datetime.now(timezone.utc),
        })
    for _ in range(max(0, posted_pay_runs - (1 if with_payroll > 0 else 0))):
        mongo.pay_runs.insert_one({
            "pay_run_id": f"pr_TEST_{secrets.token_hex(4)}",
            "company_id": co_id,
            "gross": 1000.0,
            "status": "posted",
            "created_at": datetime.now(timezone.utc),
        })
    if with_payout_inflow > 0:
        mongo.payouts.insert_one({
            "payout_id": f"pay_TEST_{secrets.token_hex(4)}",
            "target_company_id": co_id,
            "amount": float(with_payout_inflow),
            "status": "paid",
            "created_at": datetime.now(timezone.utc),
        })
    for i in range(with_employees):
        mongo.employees.insert_one({
            "employee_id": f"emp_TEST_{secrets.token_hex(4)}",
            "company_id": co_id,
            "name": f"TEST Emp {i}",
            "created_at": datetime.now(timezone.utc),
        })
    return co_id


def _cleanup_company(mongo, co_id):
    mongo.companies.delete_many({"company_id": co_id})
    mongo.sales.delete_many({"company_id": co_id})
    mongo.pay_runs.delete_many({"company_id": co_id})
    mongo.cash_advances.delete_many({"company_id": co_id})
    mongo.employees.delete_many({"company_id": co_id})
    mongo.tickets.delete_many({"company_id": co_id})
    mongo.payouts.delete_many({"$or": [
        {"source_company_id": co_id}, {"target_company_id": co_id}
    ]})


def _restore_default_policy(mongo):
    mongo.underwriting_policy.delete_many({"key": "global"})


# ============================================================
# 1. GET/PUT /api/underwriting/policy
# ============================================================
class TestUnderwritingPolicyEndpoints:
    def test_get_policy_requires_bearer(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/underwriting/policy")
        assert r.status_code == 401

    def test_put_policy_requires_bearer(self, api_client):
        r = api_client.put(f"{BASE_URL}/api/underwriting/policy",
                           json=DEFAULT_POLICY)
        assert r.status_code == 401

    def test_get_policy_forbidden_for_non_owner_non_admin(self, api_client, mongo):
        u = _make_user(mongo, active_role="employee", role="member")
        try:
            r = api_client.get(f"{BASE_URL}/api/underwriting/policy",
                               headers=u["headers"])
            assert r.status_code == 403, r.text
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_put_policy_forbidden_for_non_owner_non_admin(self, api_client, mongo):
        u = _make_user(mongo, active_role="employee", role="member")
        try:
            r = api_client.put(f"{BASE_URL}/api/underwriting/policy",
                               json=DEFAULT_POLICY, headers=u["headers"])
            assert r.status_code == 403, r.text
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_get_policy_returns_defaults_when_collection_empty(self, api_client, mongo):
        # Wipe persisted policy first to assert defaults
        _restore_default_policy(mongo)
        u = _make_user(mongo, active_role="owner")
        try:
            r = api_client.get(f"{BASE_URL}/api/underwriting/policy",
                               headers=u["headers"])
            assert r.status_code == 200, r.text
            data = r.json()
            assert "policy" in data
            p = data["policy"]
            for key, val in DEFAULT_POLICY.items():
                assert key in p, f"missing {key}"
                assert p[key] == pytest.approx(val), f"{key} default mismatch: {p[key]} != {val}"
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_put_policy_persists_and_subsequent_get_returns_updated(
        self, api_client, mongo,
    ):
        u = _make_user(mongo, active_role="owner")
        new_policy = {
            "pos_revenue_ltv": 0.20,
            "payroll_ltv": 0.08,
            "payout_projection_ltv": 0.75,
            "free_band_cap": 1500.0,
            "fee_above_free": 0.05,
            "floor": 2000.0,
        }
        try:
            r = api_client.put(f"{BASE_URL}/api/underwriting/policy",
                               json=new_policy, headers=u["headers"])
            assert r.status_code == 200, r.text
            assert r.json()["policy"] == pytest.approx(new_policy)

            # GET back
            r2 = api_client.get(f"{BASE_URL}/api/underwriting/policy",
                                headers=u["headers"])
            assert r2.status_code == 200, r2.text
            got = r2.json()["policy"]
            for k, v in new_policy.items():
                assert got[k] == pytest.approx(v), f"{k} not persisted ({got[k]} != {v})"

            # Verify doc exists in mongo with key='global'
            doc = mongo.underwriting_policy.find_one({"key": "global"})
            assert doc is not None
            for k, v in new_policy.items():
                assert doc[k] == pytest.approx(v)

            # Audit entry created
            aud = mongo.audit_log.find_one({
                "user_id": u["user_id"],
                "action": "update",
                "resource": "underwriting_policy",
            })
            assert aud is not None, "audit entry for policy update not found"
            assert aud["meta"].get("floor") == pytest.approx(2000.0)
        finally:
            _restore_default_policy(mongo)
            _cleanup_user(mongo, u["user_id"])


# ============================================================
# 2. Policy hot-reload affects /cash-advance/offer
# ============================================================
class TestPolicyHotReload:
    def test_put_policy_floor_5000_reflects_in_offer_max_advance(
        self, api_client, mongo,
    ):
        co_id = _make_iso_test_company(mongo)  # zero sales/payroll/payouts
        u = _make_user(mongo, active_role="owner",
                       active_company_id=co_id, extra_company_ids=[co_id])
        try:
            # baseline offer first
            r_base = api_client.get(f"{BASE_URL}/api/cash-advance/offer",
                                    headers=u["headers"])
            assert r_base.status_code == 200, r_base.text
            base_max = r_base.json()["max_advance"]
            # default floor is 1000
            assert base_max == pytest.approx(1000.0)

            # update floor to 5000
            new_policy = {**DEFAULT_POLICY, "floor": 5000.0}
            r_put = api_client.put(f"{BASE_URL}/api/underwriting/policy",
                                   json=new_policy, headers=u["headers"])
            assert r_put.status_code == 200, r_put.text

            # re-query offer — should now reflect new floor
            r_after = api_client.get(f"{BASE_URL}/api/cash-advance/offer",
                                     headers=u["headers"])
            assert r_after.status_code == 200, r_after.text
            new_max = r_after.json()["max_advance"]
            assert new_max >= 5000.0, (
                f"Hot-reload failed: max_advance={new_max} did not respect floor=5000"
            )
        finally:
            _restore_default_policy(mongo)
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)


# ============================================================
# 3. GET /api/cash-advance/repayment-schedule
# ============================================================
class TestRepaymentSchedule:
    def test_repayment_requires_bearer(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/cash-advance/repayment-schedule")
        assert r.status_code == 401

    def test_repayment_forbidden_for_non_owner_non_admin(self, api_client, mongo):
        u = _make_user(mongo, active_role="employee", role="member")
        try:
            r = api_client.get(
                f"{BASE_URL}/api/cash-advance/repayment-schedule",
                headers=u["headers"],
            )
            assert r.status_code == 403, r.text
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_no_outstanding_advance_returns_has_advance_false(
        self, api_client, mongo,
    ):
        co_id = _make_iso_test_company(mongo)
        u = _make_user(mongo, active_role="owner",
                       active_company_id=co_id, extra_company_ids=[co_id])
        try:
            r = api_client.get(
                f"{BASE_URL}/api/cash-advance/repayment-schedule",
                headers=u["headers"],
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["has_advance"] is False
            assert data["schedule"] == []
            assert data["outstanding"] == pytest.approx(0.0)
        finally:
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)

    def test_with_advance_schedule_sums_to_total_repayable_and_remaining_zeroes(
        self, api_client, mongo,
    ):
        # large sales so $1000 advance allowed under default policy
        co_id = _make_iso_test_company(mongo, with_sales_total=100000.0)
        u = _make_user(mongo, active_role="owner",
                       active_company_id=co_id, extra_company_ids=[co_id])
        try:
            # request a $1000 advance (fee=0, total_repayable=1000)
            r_req = api_client.post(
                f"{BASE_URL}/api/cash-advance/request",
                json={"amount": 1000.0}, headers=u["headers"],
            )
            assert r_req.status_code == 200, r_req.text
            adv = r_req.json()["advance"]
            assert adv["fee"] == pytest.approx(0.0)
            assert adv["total_repayable"] == pytest.approx(1000.0)

            # schedule
            r = api_client.get(
                f"{BASE_URL}/api/cash-advance/repayment-schedule",
                headers=u["headers"],
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["has_advance"] is True
            assert data["advance_id"] == adv["advance_id"]
            assert data["outstanding"] == pytest.approx(1000.0)
            sched = data["schedule"]
            assert isinstance(sched, list) and len(sched) > 0
            # Sum of applied amounts ≈ total_repayable
            total_applied = sum(row["applied_to_advance"] for row in sched)
            assert total_applied == pytest.approx(
                adv["total_repayable"], abs=0.05
            ), f"sum(applied)={total_applied} != total_repayable={adv['total_repayable']}"
            # Last row remaining ≈ 0
            assert sched[-1]["remaining"] == pytest.approx(0.0, abs=0.05)
            # Required row keys
            row = sched[0]
            for key in ("week", "date", "expected_inflow",
                        "applied_to_advance", "remaining"):
                assert key in row, f"missing {key} in schedule row"
            # covered_in_weeks matches schedule length
            assert data["covered_in_weeks"] == len(sched)
        finally:
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)


# ============================================================
# 4. GET /api/credit-score
# ============================================================
class TestCreditScore:
    def test_credit_score_requires_bearer(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/credit-score")
        assert r.status_code == 401

    def test_credit_score_forbidden_for_plain_employee(self, api_client, mongo):
        u = _make_user(mongo, active_role="employee", role="member")
        try:
            r = api_client.get(f"{BASE_URL}/api/credit-score",
                               headers=u["headers"])
            assert r.status_code == 403, r.text
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_credit_score_allowed_for_manager(self, api_client, mongo):
        co_id = _make_iso_test_company(mongo)
        u = _make_user(mongo, active_role="manager", role="member",
                       active_company_id=co_id, extra_company_ids=[co_id])
        try:
            r = api_client.get(f"{BASE_URL}/api/credit-score",
                               headers=u["headers"])
            assert r.status_code == 200, r.text
        finally:
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)

    def test_credit_score_shape_and_band_range(self, api_client, mongo):
        co_id = _make_iso_test_company(
            mongo, with_sales_total=50000.0, with_payroll=20000.0,
            with_payout_inflow=500.0, with_employees=5, posted_pay_runs=3,
        )
        u = _make_user(mongo, active_role="owner",
                       active_company_id=co_id, extra_company_ids=[co_id])
        try:
            r = api_client.get(f"{BASE_URL}/api/credit-score",
                               headers=u["headers"])
            assert r.status_code == 200, r.text
            d = r.json()
            # required top-level keys
            for key in ("score", "band", "tone", "breakdown", "nudges",
                        "perks", "headline"):
                assert key in d, f"missing {key}"
            assert isinstance(d["score"], int)
            assert 0 <= d["score"] <= 1000
            assert d["band"] in {
                "Exceptional", "Excellent", "Good", "Fair", "Building",
            }
            assert isinstance(d["nudges"], list)
            assert isinstance(d["perks"], list)
            assert isinstance(d["breakdown"], dict)
            for k in ("pos_revenue", "payroll", "consistency", "referrals",
                      "repayment_history", "team_size", "ops_penalty",
                      "baseline"):
                assert k in d["breakdown"], f"breakdown missing {k}"
        finally:
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)

    def test_credit_score_consistent_across_calls(self, api_client, mongo):
        co_id = _make_iso_test_company(
            mongo, with_sales_total=80000.0, with_payroll=15000.0,
            with_employees=4,
        )
        u = _make_user(mongo, active_role="owner",
                       active_company_id=co_id, extra_company_ids=[co_id])
        try:
            r1 = api_client.get(f"{BASE_URL}/api/credit-score",
                                headers=u["headers"]).json()
            r2 = api_client.get(f"{BASE_URL}/api/credit-score",
                                headers=u["headers"]).json()
            assert r1["score"] == r2["score"]
            assert r1["band"] == r2["band"]
            assert r1["breakdown"] == r2["breakdown"]
        finally:
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)

    def test_credit_score_low_data_yields_building_band(self, api_client, mongo):
        co_id = _make_iso_test_company(mongo)  # empty
        u = _make_user(mongo, active_role="owner",
                       active_company_id=co_id, extra_company_ids=[co_id])
        try:
            r = api_client.get(f"{BASE_URL}/api/credit-score",
                               headers=u["headers"]).json()
            # empty company → score should sit at the bottom band
            assert r["band"] == "Building", f"got band={r['band']} score={r['score']}"
            assert r["score"] < 400
        finally:
            _cleanup_user(mongo, u["user_id"])
            _cleanup_company(mongo, co_id)
