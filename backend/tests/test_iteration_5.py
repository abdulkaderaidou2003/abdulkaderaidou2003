"""Iteration 5 backend tests — Time Clock, Customer Portal (orders/invoices/appointments),
Owner invite-member, Marketplace + referrals. Plus audit-trail assertions.

Uses the shared `mongo` and `api_client` fixtures from conftest.py.
"""
import secrets
from datetime import datetime, timezone, timedelta

import pytest


BASE_URL = None  # set in autouse fixture


@pytest.fixture(autouse=True, scope="module")
def _set_base_url(base_url):
    global BASE_URL
    BASE_URL = base_url


# ---------- Helpers ----------
def _make_user(mongo, *, active_role=None, role="member", customer_companies=None,
               active_company_id="co_aidou_corp"):
    """Insert a real user + bearer session directly into Mongo and return creds."""
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
    if customer_companies:
        for co in customer_companies:
            mongo.memberships.update_one(
                {"user_id": user_id, "company_id": co, "role": "customer"},
                {"$setOnInsert": {
                    "membership_id": f"mem_{secrets.token_hex(6)}",
                    "user_id": user_id, "company_id": co, "role": "customer",
                    "created_at": now,
                }},
                upsert=True,
            )
    return {
        "user_id": user_id,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def _cleanup_user(mongo, user_id):
    mongo.user_sessions.delete_many({"user_id": user_id})
    mongo.memberships.delete_many({"user_id": user_id})
    mongo.users.delete_many({"user_id": user_id})
    mongo.timeclock.delete_many({"user_id": user_id})
    mongo.appointments.delete_many({"customer_user_id": user_id})
    mongo.referrals.delete_many({"source_user_id": user_id})
    mongo.audit_log.delete_many({"user_id": user_id})


# ============================================================
# Employee Time Clock
# ============================================================
class TestTimeClock:
    def test_punch_requires_bearer(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/timeclock/punch", json={})
        assert r.status_code == 401

    def test_punch_toggles_in_out_and_isolates_by_company(self, api_client, mongo):
        u = _make_user(mongo, active_company_id="co_aidou_corp")
        try:
            # First punch -> clock_in
            r1 = api_client.post(
                f"{BASE_URL}/api/timeclock/punch", json={"note": "start"}, headers=u["headers"],
            )
            assert r1.status_code == 200, r1.text
            d1 = r1.json()
            assert d1["action"] == "clock_in"
            assert "punch" in d1 and d1["punch"]["clock_out"] is None
            assert d1["punch"]["company_id"] == "co_aidou_corp"

            # Second punch (same company) -> clock_out with non-negative minutes
            r2 = api_client.post(
                f"{BASE_URL}/api/timeclock/punch", json={}, headers=u["headers"],
            )
            assert r2.status_code == 200, r2.text
            d2 = r2.json()
            assert d2["action"] == "clock_out"
            assert isinstance(d2["minutes"], int) and d2["minutes"] >= 0

            # Switch active company -> a new punch should be clock_in (isolation)
            mongo.users.update_one(
                {"user_id": u["user_id"]},
                {"$set": {"active_company_id": "co_northstar_isp"}},
            )
            r3 = api_client.post(
                f"{BASE_URL}/api/timeclock/punch", json={}, headers=u["headers"],
            )
            assert r3.status_code == 200
            d3 = r3.json()
            assert d3["action"] == "clock_in"
            assert d3["punch"]["company_id"] == "co_northstar_isp"
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_timeclock_me_returns_structure(self, api_client, mongo):
        u = _make_user(mongo)
        try:
            # No punches yet -> empty list, no open punch, 0 minutes
            r0 = api_client.get(f"{BASE_URL}/api/timeclock/me", headers=u["headers"])
            assert r0.status_code == 200
            d0 = r0.json()
            assert d0["punches"] == []
            assert d0["open_punch"] is None
            assert isinstance(d0["minutes_today"], int) and d0["minutes_today"] >= 0

            # Clock in -> open_punch set
            api_client.post(f"{BASE_URL}/api/timeclock/punch", json={}, headers=u["headers"])
            d1 = api_client.get(f"{BASE_URL}/api/timeclock/me", headers=u["headers"]).json()
            assert d1["open_punch"] is not None
            assert isinstance(d1["minutes_today"], int) and d1["minutes_today"] >= 0
            assert len(d1["punches"]) >= 1

            # Clock out -> no open punch, minutes_today >= 0
            api_client.post(f"{BASE_URL}/api/timeclock/punch", json={}, headers=u["headers"])
            d2 = api_client.get(f"{BASE_URL}/api/timeclock/me", headers=u["headers"]).json()
            assert d2["open_punch"] is None
            assert isinstance(d2["minutes_today"], int) and d2["minutes_today"] >= 0
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_audit_trail_punch_in_and_out(self, api_client, mongo):
        u = _make_user(mongo)
        try:
            api_client.post(f"{BASE_URL}/api/timeclock/punch", json={}, headers=u["headers"])
            api_client.post(f"{BASE_URL}/api/timeclock/punch", json={}, headers=u["headers"])
            actions = {
                e["action"] for e in mongo.audit_log.find(
                    {"user_id": u["user_id"], "resource": "timeclock"},
                )
            }
            assert "punch_in" in actions
            assert "punch_out" in actions
        finally:
            _cleanup_user(mongo, u["user_id"])


# ============================================================
# Customer: Orders / Invoices / Appointments
# ============================================================
class TestCustomerPortal:
    def test_orders_requires_bearer(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/customer/orders")
        assert r.status_code == 401

    def test_orders_empty_when_no_customer_membership(self, api_client, mongo):
        u = _make_user(mongo)  # no customer membership
        try:
            r = api_client.get(f"{BASE_URL}/api/customer/orders", headers=u["headers"])
            assert r.status_code == 200
            assert r.json()["orders"] == []
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_orders_enriched_with_company_name(self, api_client, mongo):
        u = _make_user(mongo, customer_companies=["co_aidou_corp", "co_northstar_isp"])
        try:
            # Ensure at least one sale exists for one of the customer companies
            sale_id = f"sal_{secrets.token_hex(6)}"
            mongo.sales.insert_one({
                "sale_id": sale_id,
                "company_id": "co_aidou_corp",
                "tender": "card",
                "subtotal": 100.0, "hst": 13.0, "total": 113.0,
                "items": [{"product_id": "x", "name": "Test", "qty": 1, "price": 100.0, "line_total": 100.0}],
                "cashier": "TEST",
                "created_at": datetime.now(timezone.utc),
            })
            try:
                r = api_client.get(f"{BASE_URL}/api/customer/orders", headers=u["headers"])
                assert r.status_code == 200
                orders = r.json()["orders"]
                assert isinstance(orders, list) and len(orders) > 0
                for o in orders:
                    assert "company_name" in o and o["company_name"]
                    assert o["company_id"] in {"co_aidou_corp", "co_northstar_isp"}
            finally:
                mongo.sales.delete_one({"sale_id": sale_id})
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_invoices_status_and_due_sum(self, api_client, mongo):
        u = _make_user(mongo, customer_companies=["co_aidou_corp"])
        try:
            # Insert 3 sales to derive >=3 invoices (paid/due/overdue mix)
            sids = []
            for i in range(3):
                sid = f"sal_{secrets.token_hex(6)}"
                sids.append(sid)
                mongo.sales.insert_one({
                    "sale_id": sid, "company_id": "co_aidou_corp",
                    "tender": "card", "subtotal": 50.0 + i, "hst": 6.5,
                    "total": 56.5 + i, "items": [],
                    "cashier": "TEST",
                    "created_at": datetime.now(timezone.utc) - timedelta(hours=i),
                })
            try:
                r = api_client.get(f"{BASE_URL}/api/customer/invoices", headers=u["headers"])
                assert r.status_code == 200
                invoices = r.json()["invoices"]
                assert len(invoices) >= 3
                for inv in invoices:
                    assert inv["status"] in {"paid", "due", "overdue"}
                    assert "company_name" in inv
                # Sum of due+overdue equals filtered sum (trivially consistent)
                unpaid = [i for i in invoices if i["status"] in ("due", "overdue")]
                total_unpaid = round(sum(i["amount"] for i in unpaid), 2)
                manual = round(sum(i["amount"] for i in invoices if i["status"] != "paid"), 2)
                assert total_unpaid == manual
            finally:
                mongo.sales.delete_many({"sale_id": {"$in": sids}})
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_appointments_seed_and_create(self, api_client, mongo):
        u = _make_user(mongo, customer_companies=["co_aidou_corp", "co_northstar_isp"])
        try:
            # Clean any pre-existing appointments for isolation
            mongo.appointments.delete_many({"customer_user_id": u["user_id"]})
            r1 = api_client.get(f"{BASE_URL}/api/customer/appointments", headers=u["headers"])
            assert r1.status_code == 200
            seeded = r1.json()["appointments"]
            assert isinstance(seeded, list) and len(seeded) >= 1
            for a in seeded:
                assert "company_name" in a
                # `when` is an ISO string
                assert isinstance(a["when"], str)
                datetime.fromisoformat(a["when"].replace("Z", "+00:00"))

            # Create a new appointment
            when_iso = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
            r2 = api_client.post(
                f"{BASE_URL}/api/customer/appointments",
                json={"title": "TEST Site visit", "when_iso": when_iso, "location": "HQ"},
                headers=u["headers"],
            )
            assert r2.status_code == 200, r2.text
            appt = r2.json()["appointment"]
            assert appt["status"] == "requested"
            assert appt["title"] == "TEST Site visit"
            assert appt["company_id"]  # active company set

            # Verify subsequent GET contains it
            r3 = api_client.get(f"{BASE_URL}/api/customer/appointments", headers=u["headers"])
            titles = [a["title"] for a in r3.json()["appointments"]]
            assert "TEST Site visit" in titles

            # Audit
            audit_actions = list(mongo.audit_log.find(
                {"user_id": u["user_id"], "resource": "appointment", "action": "create"},
            ))
            assert len(audit_actions) >= 1
        finally:
            _cleanup_user(mongo, u["user_id"])


# ============================================================
# Owner Invite-Member Flow
# ============================================================
class TestInvite:
    def test_invite_requires_bearer(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/admin/users/invite",
            json={"email": "x@y.com", "role": "employee"},
        )
        assert r.status_code == 401

    def test_invite_forbidden_for_non_owner(self, api_client, mongo):
        u = _make_user(mongo, active_role="employee", role="member")
        try:
            r = api_client.post(
                f"{BASE_URL}/api/admin/users/invite",
                json={"email": "x@y.com", "name": "X", "role": "employee"},
                headers=u["headers"],
            )
            assert r.status_code == 403
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_invite_rejects_invalid_role(self, api_client, mongo):
        u = _make_user(mongo, active_role="owner")
        try:
            r = api_client.post(
                f"{BASE_URL}/api/admin/users/invite",
                json={"email": "bad@y.com", "name": "Bad", "role": "superadmin"},
                headers=u["headers"],
            )
            assert r.status_code == 400
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_invite_creates_user_and_membership_idempotent(self, api_client, mongo):
        u = _make_user(mongo, active_role="owner", active_company_id="co_aidou_corp")
        invitee_email = f"TEST_invitee_{secrets.token_hex(4)}@example.com"
        try:
            r1 = api_client.post(
                f"{BASE_URL}/api/admin/users/invite",
                json={"email": invitee_email, "name": "TEST Invitee", "role": "employee"},
                headers=u["headers"],
            )
            assert r1.status_code == 200, r1.text
            d1 = r1.json()
            assert d1["ok"] is True
            assert isinstance(d1.get("magic_link"), str) and d1["magic_link"].startswith("https://")
            assert d1["email_sent"] is False
            assert d1["role"] == "employee"
            assert d1["company_id"] == "co_aidou_corp"
            new_user_id = d1["user_id"]

            # User must exist in DB
            invitee = mongo.users.find_one({"user_id": new_user_id})
            assert invitee is not None and invitee["email"] == invitee_email

            # Membership must exist
            mem_count_1 = mongo.memberships.count_documents({
                "user_id": new_user_id, "company_id": "co_aidou_corp", "role": "employee",
            })
            assert mem_count_1 == 1

            # Idempotent: repeat call -> still exactly 1 membership row
            r2 = api_client.post(
                f"{BASE_URL}/api/admin/users/invite",
                json={"email": invitee_email, "name": "TEST Invitee", "role": "employee"},
                headers=u["headers"],
            )
            assert r2.status_code == 200
            assert r2.json()["user_id"] == new_user_id
            mem_count_2 = mongo.memberships.count_documents({
                "user_id": new_user_id, "company_id": "co_aidou_corp", "role": "employee",
            })
            assert mem_count_2 == 1

            # Audit trail
            audits = list(mongo.audit_log.find({
                "user_id": u["user_id"], "resource": "user", "action": "invite",
            }))
            assert len(audits) >= 1
        finally:
            # Cleanup invited user and audit
            invitee = mongo.users.find_one({"email": invitee_email})
            if invitee:
                mongo.memberships.delete_many({"user_id": invitee["user_id"]})
                mongo.users.delete_many({"user_id": invitee["user_id"]})
            _cleanup_user(mongo, u["user_id"])


# ============================================================
# Marketplace + Referrals
# ============================================================
class TestMarketplace:
    def test_businesses_requires_bearer(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/marketplace/businesses")
        assert r.status_code == 401

    def test_businesses_includes_seeded_and_extras(self, api_client, mongo):
        u = _make_user(mongo)
        try:
            r = api_client.get(f"{BASE_URL}/api/marketplace/businesses?include_unverified=true", headers=u["headers"])
            assert r.status_code == 200, r.text
            biz = r.json()["businesses"]
            assert isinstance(biz, list)
            # Every entry has rating/specialty/min_price
            for b in biz:
                assert "rating" in b
                assert "specialty" in b
                assert "min_price" in b
            ids = {b["company_id"] for b in biz}
            # 3 seeded companies present
            assert {"co_aidou_corp", "co_northstar_isp", "co_summit_construction"}.issubset(ids)
            # 3 marketplace extras present
            assert {"mp_ridgeline_logistics", "mp_acadia_medical", "mp_pinewood_school"}.issubset(ids)
        finally:
            _cleanup_user(mongo, u["user_id"])

    def test_create_and_list_referrals(self, api_client, mongo):
        u = _make_user(mongo, active_company_id="co_aidou_corp")
        try:
            r1 = api_client.post(
                f"{BASE_URL}/api/marketplace/referrals",
                json={"target_company_id": "mp_acadia_medical", "note": "TEST referral"},
                headers=u["headers"],
            )
            assert r1.status_code == 200, r1.text
            ref = r1.json()["referral"]
            assert ref["status"] == "pending"
            assert ref["share_percent"] == 5.0
            assert ref["target_company_id"] == "mp_acadia_medical"
            assert ref["source_company_id"] == "co_aidou_corp"
            assert ref["source_user_id"] == u["user_id"]

            # Create a second referral, then list newest-first
            r2 = api_client.post(
                f"{BASE_URL}/api/marketplace/referrals",
                json={"target_company_id": "mp_ridgeline_logistics"},
                headers=u["headers"],
            )
            assert r2.status_code == 200

            r3 = api_client.get(f"{BASE_URL}/api/marketplace/referrals", headers=u["headers"])
            assert r3.status_code == 200
            refs = r3.json()["referrals"]
            assert len(refs) >= 2
            # newest-first sort: created_at desc
            timestamps = [r["created_at"] for r in refs]
            assert timestamps == sorted(timestamps, reverse=True)
            # All belong to this user
            assert all(r["source_user_id"] == u["user_id"] for r in refs)

            # Audit trail for referral creation
            audits = list(mongo.audit_log.find({
                "user_id": u["user_id"], "resource": "referral", "action": "create",
            }))
            assert len(audits) >= 2
        finally:
            _cleanup_user(mongo, u["user_id"])


# ============================================================
# Smoke: regression on previously-passing endpoints
# ============================================================
class TestRegressionSmoke:
    """Light smoke on previously-passing endpoints to confirm iter-5 doesn't break them."""

    @pytest.fixture(scope="class")
    def smoke_user(self, mongo):
        u = _make_user(mongo, role="admin", active_role="owner")
        yield u
        _cleanup_user(mongo, u["user_id"])

    @pytest.mark.parametrize("path", [
        "/api/auth/me",
        "/api/companies",
        "/api/workspaces",
        "/api/modules",
        "/api/dashboard",
        "/api/hr/employees",
        "/api/tickets",
        "/api/schedule",
        "/api/crm/customers",
        "/api/pos/products",
        "/api/payroll/runs",
        "/api/fleet/vehicles",
        "/api/inventory/items",
        "/api/alerts",
    ])
    def test_get_200(self, api_client, smoke_user, path):
        r = api_client.get(f"{BASE_URL}{path}", headers=smoke_user["headers"])
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"
        # No raw mongo _id leakage
        assert "_id" not in r.text or '"_id"' not in r.text
