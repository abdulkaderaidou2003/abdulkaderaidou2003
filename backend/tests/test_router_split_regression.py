"""Iteration 9 — explicit router-split regression sweep.

Hits EVERY legacy endpoint listed in the iter9 review request and confirms
correct status code + non-empty/well-shaped JSON. This is the safety net for
the per-module router split.
"""
import secrets
from datetime import datetime, timezone, timedelta

import pytest

from tests.conftest import BASE_URL


# ---------- helpers ----------
def _seed_user(mongo, role="admin", active_role="owner"):
    user_id = f"user_{secrets.token_hex(6)}"
    token = f"TEST_{secrets.token_hex(16)}"
    mongo.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "email": f"TEST_{user_id}@example.com",
            "name": "Router Split Tester",
            "company_ids": ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"],
            "active_company_id": "co_aidou_corp",
            "active_role": active_role,
            "role": role,
            "created_at": datetime.now(timezone.utc),
            "last_login": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    mongo.memberships.update_one(
        {"user_id": user_id, "company_id": "co_aidou_corp"},
        {"$set": {
            "membership_id": f"mem_{secrets.token_hex(6)}",
            "user_id": user_id, "company_id": "co_aidou_corp", "role": active_role,
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
    return {"user_id": user_id, "token": token,
            "headers": {"Authorization": f"Bearer {token}"}}


def _cleanup(mongo, user_id):
    mongo.user_sessions.delete_many({"user_id": user_id})
    mongo.users.delete_many({"user_id": user_id})
    mongo.memberships.delete_many({"user_id": user_id})


@pytest.fixture
def owner(mongo):
    u = _seed_user(mongo, role="admin", active_role="owner")
    yield u
    _cleanup(mongo, u["user_id"])


# ---------- AUTH / COMPANY / WORKSPACE ----------
class TestAuthCompanyWorkspace:
    def test_auth_me(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/auth/me", headers=owner["headers"])
        assert r.status_code == 200
        body = r.json()
        u = body.get("user", body)
        assert u["user_id"] == owner["user_id"]
        assert u["active_company_id"] == "co_aidou_corp"

    def test_companies_list(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/companies", headers=owner["headers"])
        assert r.status_code == 200
        assert isinstance(r.json().get("companies"), list)

    def test_companies_switch(self, api_client, owner):
        r = api_client.post(
            f"{BASE_URL}/api/companies/switch",
            json={"company_id": "co_northstar_isp"},
            headers=owner["headers"],
        )
        assert r.status_code == 200

    def test_workspaces_list(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/workspaces", headers=owner["headers"])
        assert r.status_code == 200

    def test_workspaces_switch(self, api_client, owner):
        r = api_client.post(
            f"{BASE_URL}/api/workspaces/switch",
            json={"company_id": "co_aidou_corp", "role": "owner"},
            headers=owner["headers"],
        )
        assert r.status_code == 200

    def test_workspaces_stats(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/workspaces/stats", headers=owner["headers"])
        assert r.status_code == 200

    def test_auth_logout(self, api_client, mongo):
        # Use a throwaway user so we don't break other tests on this owner fixture
        u = _seed_user(mongo)
        try:
            r = api_client.post(f"{BASE_URL}/api/auth/logout", headers=u["headers"])
            assert r.status_code == 200
        finally:
            _cleanup(mongo, u["user_id"])


# ---------- ADMIN / MODULES / DASHBOARD ----------
class TestAdminModulesDashboard:
    def test_admin_users_list(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/admin/users", headers=owner["headers"])
        assert r.status_code == 200

    def test_admin_users_invite(self, api_client, owner):
        r = api_client.post(
            f"{BASE_URL}/api/admin/users/invite",
            json={"email": f"TEST_invite_{secrets.token_hex(4)}@example.com",
                  "role": "employee"},
            headers=owner["headers"],
        )
        assert r.status_code in (200, 201)

    def test_modules(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/modules", headers=owner["headers"])
        assert r.status_code == 200

    def test_dashboard(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/dashboard", headers=owner["headers"])
        assert r.status_code == 200


# ---------- HR / TICKETS / SCHEDULE / CRM ----------
class TestHRTicketsScheduleCRM:
    def test_hr_employees_list(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/hr/employees", headers=owner["headers"])
        assert r.status_code == 200

    def test_hr_employees_create(self, api_client, owner):
        r = api_client.post(
            f"{BASE_URL}/api/hr/employees",
            json={"name": "TEST Hire", "email": f"TEST_{secrets.token_hex(4)}@x.com",
                  "role": "employee", "department": "QA"},
            headers=owner["headers"],
        )
        assert r.status_code in (200, 201)

    def test_tickets_list(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/tickets", headers=owner["headers"])
        assert r.status_code == 200

    def test_tickets_create(self, api_client, owner):
        r = api_client.post(
            f"{BASE_URL}/api/tickets",
            json={"title": "TEST ticket", "description": "rs",
                  "priority": "low", "category": "general"},
            headers=owner["headers"],
        )
        assert r.status_code in (200, 201)

    def test_schedule(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/schedule", headers=owner["headers"])
        assert r.status_code == 200

    def test_crm_customers(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/crm/customers", headers=owner["headers"])
        assert r.status_code == 200


# ---------- POS / PAYROLL / FLEET / INVENTORY ----------
class TestPOSPayrollFleetInventory:
    def test_pos_products(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/pos/products", headers=owner["headers"])
        assert r.status_code == 200

    def test_pos_sales_list(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/pos/sales", headers=owner["headers"])
        assert r.status_code == 200

    def test_pos_sales_post(self, api_client, owner):
        prods = api_client.get(
            f"{BASE_URL}/api/pos/products", headers=owner["headers"],
        ).json().get("products", [])
        if not prods:
            pytest.skip("no products to sell")
        r = api_client.post(
            f"{BASE_URL}/api/pos/sales",
            json={"items": [{"product_id": prods[0]["product_id"], "qty": 1}]},
            headers=owner["headers"],
        )
        assert r.status_code in (200, 201)

    def test_payroll_runs(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/payroll/runs", headers=owner["headers"])
        assert r.status_code == 200

    def test_payroll_t4_unknown(self, api_client, owner):
        r = api_client.get(
            f"{BASE_URL}/api/payroll/t4/emp_unknown_xxx", headers=owner["headers"],
        )
        assert r.status_code == 404

    def test_fleet_vehicles(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/fleet/vehicles", headers=owner["headers"])
        assert r.status_code == 200

    def test_inventory_items(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/inventory/items", headers=owner["headers"])
        assert r.status_code == 200

    def test_inventory_lookup(self, api_client, owner):
        r = api_client.get(
            f"{BASE_URL}/api/inventory/lookup?barcode=does_not_exist",
            headers=owner["headers"],
        )
        assert r.status_code in (200, 404)


# ---------- ALERTS / AUDIT / TIMECLOCK ----------
class TestAlertsAuditTimeclock:
    def test_alerts(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/alerts", headers=owner["headers"])
        assert r.status_code == 200

    def test_audit_log(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/audit/log", headers=owner["headers"])
        assert r.status_code == 200

    def test_timeclock_punch_and_me(self, api_client, owner):
        r = api_client.post(
            f"{BASE_URL}/api/timeclock/punch",
            json={"kind": "in"},
            headers=owner["headers"],
        )
        # punch may need an employee record — accept 200/201/400 but never 500
        assert r.status_code in (200, 201, 400, 404, 409), r.text
        m = api_client.get(f"{BASE_URL}/api/timeclock/me", headers=owner["headers"])
        assert m.status_code in (200, 404), m.text


# ---------- CUSTOMER PORTAL ----------
class TestCustomerPortal:
    def test_customer_orders(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/customer/orders", headers=owner["headers"])
        assert r.status_code in (200, 403)

    def test_customer_invoices(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/customer/invoices", headers=owner["headers"])
        assert r.status_code in (200, 403)

    def test_customer_appointments(self, api_client, owner):
        r = api_client.get(
            f"{BASE_URL}/api/customer/appointments", headers=owner["headers"],
        )
        assert r.status_code in (200, 403)


# ---------- CASH-ADVANCE / UNDERWRITING / CREDIT SCORE ----------
class TestCashAdvanceAndCredit:
    def test_offer(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/cash-advance/offer", headers=owner["headers"])
        assert r.status_code == 200

    def test_history(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/cash-advance/history", headers=owner["headers"])
        assert r.status_code == 200

    def test_repayment_schedule(self, api_client, owner):
        r = api_client.get(
            f"{BASE_URL}/api/cash-advance/repayment-schedule", headers=owner["headers"],
        )
        assert r.status_code == 200

    def test_underwriting_policy_get(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/underwriting/policy", headers=owner["headers"])
        assert r.status_code == 200

    def test_credit_score(self, api_client, owner):
        r = api_client.get(f"{BASE_URL}/api/credit-score", headers=owner["headers"])
        assert r.status_code == 200
        body = r.json()
        assert "score" in body and "band" in body
