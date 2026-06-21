"""Iteration 6 backend tests — SendGrid-wired invite (mocked), marketplace scoring,
referral fulfillment + 5% payouts, workspace trust-signal stats endpoint.

Uses shared fixtures from conftest.py.
"""
import re
import secrets
from datetime import datetime, timezone, timedelta

import pytest


BASE_URL = None


@pytest.fixture(autouse=True, scope="module")
def _set_base_url(base_url):
    global BASE_URL
    BASE_URL = base_url


# ---------- helpers ----------
def _make_user(mongo, *, active_role=None, role="member", active_company_id="co_aidou_corp",
               memberships=None):
    user_id = f"user_{secrets.token_hex(6)}"
    token = f"TEST_{secrets.token_hex(16)}"
    now = datetime.now(timezone.utc)
    mongo.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "email": f"TEST_{user_id}@example.com",
            "name": "TEST User",
            "picture": "",
            "company_ids": ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"],
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
    if memberships:
        for co, r in memberships:
            mongo.memberships.update_one(
                {"user_id": user_id, "company_id": co, "role": r},
                {"$setOnInsert": {
                    "membership_id": f"mem_{secrets.token_hex(6)}",
                    "user_id": user_id, "company_id": co, "role": r,
                    "created_at": now,
                }},
                upsert=True,
            )
    return {"user_id": user_id, "token": token,
            "headers": {"Authorization": f"Bearer {token}"}}


def _cleanup_user(mongo, user_id):
    mongo.user_sessions.delete_many({"user_id": user_id})
    mongo.memberships.delete_many({"user_id": user_id})
    mongo.users.delete_many({"user_id": user_id})
    mongo.timeclock.delete_many({"user_id": user_id})
    mongo.appointments.delete_many({"customer_user_id": user_id})
    mongo.referrals.delete_many({"source_user_id": user_id})
    mongo.audit_log.delete_many({"user_id": user_id})


# ============================================================
# 1. Invite — SendGrid graceful fallback (keys are intentionally blank)
# ============================================================
class TestInviteSendGridFallback:
    def test_invite_returns_magic_link_with_email_sent_false_and_reason(self, api_client, mongo):
        actor = _make_user(mongo, active_role="owner", active_company_id="co_aidou_corp")
        invitee = f"TEST_iter6_invitee_{secrets.token_hex(4)}@example.com"
        try:
            r = api_client.post(
                f"{BASE_URL}/api/admin/users/invite",
                json={"email": invitee, "name": "TEST Invitee6", "role": "manager"},
                headers=actor["headers"],
            )
            assert r.status_code == 200, r.text
            d = r.json()
            # magic link present
            assert isinstance(d.get("magic_link"), str) and d["magic_link"].startswith("https://")
            # email NOT sent because SENDGRID_API_KEY blank
            assert d["email_sent"] is False
            # reason should mention SENDGRID_API_KEY
            reason = d.get("email_reason") or ""
            assert "SENDGRID_API_KEY" in reason, f"email_reason must mention SENDGRID_API_KEY, got: {reason!r}"
            new_user_id = d["user_id"]

            # User + membership persisted
            assert mongo.users.find_one({"user_id": new_user_id}) is not None
            mc = mongo.memberships.count_documents({
                "user_id": new_user_id, "company_id": "co_aidou_corp", "role": "manager",
            })
            assert mc == 1

            # Idempotent
            r2 = api_client.post(
                f"{BASE_URL}/api/admin/users/invite",
                json={"email": invitee, "name": "TEST Invitee6", "role": "manager"},
                headers=actor["headers"],
            )
            assert r2.status_code == 200
            mc2 = mongo.memberships.count_documents({
                "user_id": new_user_id, "company_id": "co_aidou_corp", "role": "manager",
            })
            assert mc2 == 1

            # Audit meta must include email_sent
            audits = list(mongo.audit_log.find({
                "user_id": actor["user_id"], "resource": "user", "action": "invite",
            }))
            assert len(audits) >= 1
            assert any("email_sent" in (a.get("meta") or {}) for a in audits), \
                f"audit meta should include email_sent, got: {[a.get('meta') for a in audits]}"
            # And the value should be False (matching this env)
            latest = audits[-1]
            assert latest["meta"]["email_sent"] is False
        finally:
            # cleanup invitee
            inv = mongo.users.find_one({"email": invitee})
            if inv:
                mongo.memberships.delete_many({"user_id": inv["user_id"]})
                mongo.users.delete_many({"user_id": inv["user_id"]})
            _cleanup_user(mongo, actor["user_id"])


# ============================================================
# 2. Marketplace businesses — scoring + recommendation + sort
# ============================================================
class TestMarketplaceScoring:
    def test_businesses_have_score_recommended_match_reason_and_sorted(self, api_client, mongo):
        u = _make_user(mongo)
        try:
            r = api_client.get(f"{BASE_URL}/api/marketplace/businesses", headers=u["headers"])
            assert r.status_code == 200, r.text
            body = r.json()
            biz = body["businesses"]
            assert isinstance(biz, list) and len(biz) > 0

            # user_industries is a dict
            assert "user_industries" in body
            assert isinstance(body["user_industries"], dict)

            # every business has score/recommended/match_reason
            for b in biz:
                assert isinstance(b.get("score"), (int, float)), f"score missing/invalid: {b}"
                assert isinstance(b.get("recommended"), bool), f"recommended missing/invalid: {b}"
                assert isinstance(b.get("match_reason"), str) and b["match_reason"], \
                    f"match_reason missing/invalid: {b}"

            # sorted by score desc
            scores = [b["score"] for b in biz]
            assert scores == sorted(scores, reverse=True), f"businesses not sorted desc by score: {scores}"
        finally:
            _cleanup_user(mongo, u["user_id"])


# ============================================================
# 3. Fulfill referral — auth + 404/400 + payout persistence + idempotent
# ============================================================
class TestFulfillReferral:
    def test_fulfill_requires_bearer(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/marketplace/referrals/ref_nope/fulfill",
                            json={"booking_value": 100.0})
        assert r.status_code == 401

    def test_fulfill_forbidden_for_employee(self, api_client, mongo):
        # Create a referral row directly so the 403 gate fires before 404.
        u = _make_user(mongo, active_role="employee", role="member",
                       active_company_id="co_aidou_corp")
        ref_id = f"ref_{secrets.token_hex(6)}"
        mongo.referrals.insert_one({
            "referral_id": ref_id, "source_user_id": u["user_id"],
            "source_company_id": "co_aidou_corp",
            "target_company_id": "mp_acadia_medical",
            "status": "pending", "share_percent": 5.0,
            "estimated_payout": 0.0, "created_at": datetime.now(timezone.utc),
        })
        try:
            r = api_client.post(
                f"{BASE_URL}/api/marketplace/referrals/{ref_id}/fulfill",
                json={"booking_value": 100.0},
                headers=u["headers"],
            )
            assert r.status_code == 403, r.text
        finally:
            mongo.referrals.delete_one({"referral_id": ref_id})
            _cleanup_user(mongo, u["user_id"])

    def test_fulfill_404_for_unknown_referral(self, api_client, mongo):
        u = _make_user(mongo, active_role="owner")
        try:
            r = api_client.post(
                f"{BASE_URL}/api/marketplace/referrals/ref_does_not_exist/fulfill",
                json={"booking_value": 100.0},
                headers=u["headers"],
            )
            assert r.status_code == 404
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_fulfill_400_for_non_positive_value(self, api_client, mongo):
        u = _make_user(mongo, active_role="owner", active_company_id="co_aidou_corp")
        # create real referral
        r1 = api_client.post(
            f"{BASE_URL}/api/marketplace/referrals",
            json={"target_company_id": "mp_acadia_medical", "note": "TEST iter6"},
            headers=u["headers"],
        )
        assert r1.status_code == 200
        ref_id = r1.json()["referral"]["referral_id"]
        try:
            r = api_client.post(
                f"{BASE_URL}/api/marketplace/referrals/{ref_id}/fulfill",
                json={"booking_value": 0},
                headers=u["headers"],
            )
            assert r.status_code == 400
            r2 = api_client.post(
                f"{BASE_URL}/api/marketplace/referrals/{ref_id}/fulfill",
                json={"booking_value": -10.5},
                headers=u["headers"],
            )
            assert r2.status_code == 400
        finally:
            mongo.referrals.delete_one({"referral_id": ref_id})
            _cleanup_user(mongo, u["user_id"])

    def test_fulfill_computes_5pct_payout_persists_and_is_idempotent(self, api_client, mongo):
        u = _make_user(mongo, active_role="owner", active_company_id="co_aidou_corp")
        # create referral
        r1 = api_client.post(
            f"{BASE_URL}/api/marketplace/referrals",
            json={"target_company_id": "mp_ridgeline_logistics", "note": "TEST iter6 fulfill"},
            headers=u["headers"],
        )
        assert r1.status_code == 200
        ref_id = r1.json()["referral"]["referral_id"]
        try:
            # Fulfill with 2000 -> payout 100.0
            booking = 2000.0
            r2 = api_client.post(
                f"{BASE_URL}/api/marketplace/referrals/{ref_id}/fulfill",
                json={"booking_value": booking},
                headers=u["headers"],
            )
            assert r2.status_code == 200, r2.text
            d = r2.json()
            assert d["payout"] == round(booking * 0.05, 2) == 100.0
            assert d["referral"]["status"] == "fulfilled"
            assert d["referral"]["booking_value"] == booking
            assert d["referral"]["estimated_payout"] == 100.0

            # payouts collection persisted with pending_disbursement
            payout_doc = mongo.payouts.find_one({"referral_id": ref_id})
            assert payout_doc is not None
            assert payout_doc["amount"] == 100.0
            assert payout_doc["status"] == "pending_disbursement"
            assert payout_doc["source_company_id"] == "co_aidou_corp"
            assert payout_doc["target_company_id"] == "mp_ridgeline_logistics"

            # Idempotent: second call returns 'already fulfilled' note, no new payout row
            r3 = api_client.post(
                f"{BASE_URL}/api/marketplace/referrals/{ref_id}/fulfill",
                json={"booking_value": 9999.0},
                headers=u["headers"],
            )
            assert r3.status_code == 200
            d3 = r3.json()
            assert d3.get("note") == "already fulfilled"
            payouts_after = mongo.payouts.count_documents({"referral_id": ref_id})
            assert payouts_after == 1, f"expected exactly 1 payout, got {payouts_after}"

            # Audit
            audits = list(mongo.audit_log.find({
                "user_id": u["user_id"], "resource": "referral", "action": "fulfill",
            }))
            assert len(audits) >= 1
        finally:
            mongo.payouts.delete_many({"referral_id": ref_id})
            mongo.referrals.delete_one({"referral_id": ref_id})
            _cleanup_user(mongo, u["user_id"])


# ============================================================
# 4. Marketplace payouts list
# ============================================================
class TestPayoutsList:
    def test_payouts_requires_bearer(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/marketplace/payouts")
        assert r.status_code == 401

    def test_payouts_forbidden_for_employee(self, api_client, mongo):
        u = _make_user(mongo, active_role="employee", role="member")
        try:
            r = api_client.get(f"{BASE_URL}/api/marketplace/payouts", headers=u["headers"])
            assert r.status_code == 403
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_payouts_filter_by_source_or_target_and_total_pending(self, api_client, mongo):
        u = _make_user(mongo, active_role="owner", active_company_id="co_aidou_corp")
        # Insert deterministic payout rows
        ids = []
        rows = [
            # source = active_company -> should be in
            {"payout_id": f"pay_{secrets.token_hex(4)}", "referral_id": "ref_a",
             "amount": 50.0, "source_company_id": "co_aidou_corp",
             "target_company_id": "mp_acadia_medical",
             "status": "pending_disbursement", "created_at": datetime.now(timezone.utc)},
            # target = active_company -> should be in
            {"payout_id": f"pay_{secrets.token_hex(4)}", "referral_id": "ref_b",
             "amount": 25.0, "source_company_id": "mp_ridgeline_logistics",
             "target_company_id": "co_aidou_corp",
             "status": "pending_disbursement", "created_at": datetime.now(timezone.utc)},
            # unrelated -> should NOT be in
            {"payout_id": f"pay_{secrets.token_hex(4)}", "referral_id": "ref_c",
             "amount": 999.0, "source_company_id": "co_northstar_isp",
             "target_company_id": "mp_acadia_medical",
             "status": "pending_disbursement", "created_at": datetime.now(timezone.utc)},
            # related but already disbursed -> in list but NOT in total_pending
            {"payout_id": f"pay_{secrets.token_hex(4)}", "referral_id": "ref_d",
             "amount": 70.0, "source_company_id": "co_aidou_corp",
             "target_company_id": "mp_acadia_medical",
             "status": "disbursed", "created_at": datetime.now(timezone.utc)},
        ]
        for row in rows:
            mongo.payouts.insert_one(row)
            ids.append(row["payout_id"])
        try:
            r = api_client.get(f"{BASE_URL}/api/marketplace/payouts", headers=u["headers"])
            assert r.status_code == 200, r.text
            data = r.json()
            returned_ids = {p["payout_id"] for p in data["payouts"]}
            # 2 pending + 1 disbursed all touching co_aidou_corp
            assert ids[0] in returned_ids
            assert ids[1] in returned_ids
            assert ids[2] not in returned_ids
            assert ids[3] in returned_ids

            # total_pending = 50 + 25 = 75 (disbursed not counted) — but other tests may have
            # added pending payouts touching co_aidou_corp; assert at least 75 of "our" rows
            # is present and the disbursed amount is excluded.
            mine_pending = sum(p["amount"] for p in data["payouts"]
                               if p["payout_id"] in {ids[0], ids[1]})
            assert mine_pending == 75.0
            assert data["total_pending"] >= 75.0
            # disbursed must not contribute to total_pending; verify by removing my pending rows
            # equal-or-greater than (total - 75) excludes ids[3] (70.0 disbursed).
            assert data["total_pending"] - mine_pending == pytest.approx(
                sum(p["amount"] for p in data["payouts"]
                    if p["status"] == "pending_disbursement"
                    and p["payout_id"] not in {ids[0], ids[1]}),
                rel=1e-6,
            )
        finally:
            mongo.payouts.delete_many({"payout_id": {"$in": ids}})
            _cleanup_user(mongo, u["user_id"])


# ============================================================
# 5. Workspaces stats — owner/manager / employee / customer shapes
# ============================================================
class TestWorkspaceStats:
    def test_stats_requires_bearer(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/workspaces/stats")
        assert r.status_code == 401

    def test_stats_for_owner_manager_employee_customer_keys(self, api_client, mongo):
        u = _make_user(
            mongo,
            active_role="owner",
            active_company_id="co_aidou_corp",
            memberships=[
                ("co_aidou_corp", "owner"),
                ("co_northstar_isp", "manager"),
                ("co_summit_construction", "employee"),
                ("co_aidou_corp", "customer"),
            ],
        )
        try:
            r = api_client.get(f"{BASE_URL}/api/workspaces/stats", headers=u["headers"])
            assert r.status_code == 200, r.text
            stats = r.json()["stats"]
            assert isinstance(stats, dict)

            owner_key = "co_aidou_corp:owner"
            mgr_key = "co_northstar_isp:manager"
            emp_key = "co_summit_construction:employee"
            cust_key = "co_aidou_corp:customer"
            for k in (owner_key, mgr_key, emp_key, cust_key):
                assert k in stats, f"missing key {k}; got {list(stats.keys())}"

            # owner/manager: 'N employees' + '$X.X K payroll YTD'
            for k in (owner_key, mgr_key):
                head = stats[k]["headline"]
                metric = stats[k]["metric"]
                assert re.match(r"^\d+ employees$", head), \
                    f"owner/manager headline shape wrong for {k}: {head!r}"
                assert re.match(r"^\$\d+(?:\.\d+)?K payroll YTD$", metric), \
                    f"owner/manager metric shape wrong for {k}: {metric!r}"

            # employee: 'Xh logged...' + 'N shifts...'
            emp_head = stats[emp_key]["headline"]
            emp_metric = stats[emp_key]["metric"]
            assert re.match(r"^\d+(?:\.\d+)?h logged", emp_head), \
                f"employee headline shape wrong: {emp_head!r}"
            assert re.match(r"^\d+ shifts", emp_metric), \
                f"employee metric shape wrong: {emp_metric!r}"

            # customer: 'N invoices on file' + 'N upcoming appointments'
            cust_head = stats[cust_key]["headline"]
            cust_metric = stats[cust_key]["metric"]
            assert re.match(r"^\d+ invoices on file$", cust_head), \
                f"customer headline shape wrong: {cust_head!r}"
            assert re.match(r"^\d+ upcoming appointments$", cust_metric), \
                f"customer metric shape wrong: {cust_metric!r}"
        finally:
            _cleanup_user(mongo, u["user_id"])
