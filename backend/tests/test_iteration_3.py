"""Iteration 3 backend tests: RBAC, audit log, AI Daily Ops Brief, regression sweep."""
import secrets
from datetime import datetime, timezone, timedelta

import pytest


# -------------- Fixture: a viewer-role user for RBAC tests --------------
@pytest.fixture(scope="module")
def viewer_user(mongo):
    user_id = f"user_{secrets.token_hex(6)}"
    token = f"TEST_VIEWER_{secrets.token_hex(16)}"
    mongo.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "email": f"TEST_{user_id}@example.com",
            "name": "TEST Viewer",
            "picture": "",
            "company_ids": ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"],
            "active_company_id": "co_aidou_corp",
            "role": "viewer",
            "created_at": datetime.now(timezone.utc),
            "last_login": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    mongo.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc),
    })
    yield {"user_id": user_id, "token": token, "headers": {"Authorization": f"Bearer {token}"}}
    mongo.user_sessions.delete_many({"user_id": user_id})
    mongo.users.delete_many({"user_id": user_id})


# ===================== Audit Log RBAC + shape =====================
class TestAuditLog:
    def test_audit_log_401_without_bearer(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/audit/log")
        assert r.status_code == 401, r.text

    def test_audit_log_403_for_viewer(self, api_client, base_url, viewer_user):
        r = api_client.get(f"{base_url}/api/audit/log", headers=viewer_user["headers"])
        assert r.status_code == 403, r.text

    def test_audit_log_200_for_admin_shape(self, api_client, base_url, seeded_user, mongo):
        # Seed an entry directly so the list is non-empty
        mongo.audit_log.insert_one({
            "audit_id": f"aud_{secrets.token_hex(6)}",
            "user_id": seeded_user["user_id"],
            "user_email": "TEST@example.com",
            "company_id": "co_aidou_corp",
            "role": "admin",
            "action": "create",
            "resource": "ticket",
            "meta": {"seed": True},
            "ip": None,
            "created_at": datetime.now(timezone.utc),
        })

        r = api_client.get(f"{base_url}/api/audit/log", headers=seeded_user["headers"])
        assert r.status_code == 200, r.text
        data = r.json()
        assert "entries" in data and isinstance(data["entries"], list)
        assert len(data["entries"]) >= 1
        for e in data["entries"]:
            assert "_id" not in e, "ObjectId leak"
            assert "audit_id" in e
            assert "action" in e
            assert "resource" in e
            assert "created_at" in e


# ===================== RBAC on HR Employees =====================
class TestRBACEmployees:
    def test_post_employee_403_for_viewer(self, api_client, base_url, viewer_user):
        payload = {"name": "TEST_NoPerm", "role": "Tech", "department": "Engineering"}
        r = api_client.post(f"{base_url}/api/hr/employees", json=payload, headers=viewer_user["headers"])
        assert r.status_code == 403, r.text

    def test_post_employee_200_for_admin(self, api_client, base_url, seeded_user, mongo):
        payload = {"name": "TEST_AdminCreated", "role": "Tech", "department": "Engineering",
                   "email": "TEST_adm@example.com"}
        r = api_client.post(f"{base_url}/api/hr/employees", json=payload, headers=seeded_user["headers"])
        assert r.status_code == 200, r.text
        emp = r.json()["employee"]
        assert "_id" not in emp
        assert emp["name"] == "TEST_AdminCreated"
        mongo.employees.delete_many({"employee_id": emp["employee_id"]})


# ===================== AI Daily Ops Brief =====================
class TestOpsBrief:
    def test_ops_brief_401_without_bearer(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/ai/ops-brief")
        assert r.status_code == 401, r.text

    def test_ops_brief_shape_and_cache(self, api_client, base_url, seeded_user):
        # Switch to a dedicated company to make cache state deterministic
        api_client.post(f"{base_url}/api/companies/switch",
                        json={"company_id": "co_summit_construction"},
                        headers=seeded_user["headers"])

        r1 = api_client.get(f"{base_url}/api/ai/ops-brief", headers=seeded_user["headers"], timeout=120)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert "brief" in d1 and isinstance(d1["brief"], str) and d1["brief"].strip()
        assert "metrics" in d1 and isinstance(d1["metrics"], dict)
        for k in ("open_tickets", "fleet_active", "inventory_low_stock", "alerts_unread"):
            assert k in d1["metrics"], f"missing metric: {k}"
        # First call may be cached if previously hit during this hour; assert boolean type
        assert isinstance(d1["cached"], bool)

        # Second call: must be cached=True now
        r2 = api_client.get(f"{base_url}/api/ai/ops-brief", headers=seeded_user["headers"], timeout=30)
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        assert d2["cached"] is True
        assert d2["brief"] == d1["brief"]


# ===================== Audit trail persistence =====================
class TestAuditTrailPersistence:
    def test_actions_create_audit_entries(self, api_client, base_url, seeded_user, mongo):
        uid = seeded_user["user_id"]
        # company switch
        r_sw = api_client.post(f"{base_url}/api/companies/switch",
                               json={"company_id": "co_aidou_corp"},
                               headers=seeded_user["headers"])
        assert r_sw.status_code == 200

        # create ticket
        r_t = api_client.post(f"{base_url}/api/tickets",
                              json={"title": "TEST_AuditTicket", "priority": "low"},
                              headers=seeded_user["headers"])
        assert r_t.status_code == 200
        tid = r_t.json()["ticket"]["ticket_id"]

        # create POS sale (need a real product id)
        prods = api_client.get(f"{base_url}/api/pos/products", headers=seeded_user["headers"]).json()["products"]
        assert prods, "need seeded products"
        r_s = api_client.post(f"{base_url}/api/pos/sales",
                              json={"items": [{"product_id": prods[0]["product_id"], "qty": 1}], "tender": "cash"},
                              headers=seeded_user["headers"])
        assert r_s.status_code == 200
        sid = r_s.json()["sale"]["sale_id"]

        # create employee
        r_e = api_client.post(f"{base_url}/api/hr/employees",
                              json={"name": "TEST_AuditEmp", "role": "X", "department": "Y"},
                              headers=seeded_user["headers"])
        assert r_e.status_code == 200
        eid = r_e.json()["employee"]["employee_id"]

        # view audit log
        r_a = api_client.get(f"{base_url}/api/audit/log", headers=seeded_user["headers"])
        assert r_a.status_code == 200

        # Now verify entries exist with allowed actions
        actions = set(mongo.audit_log.distinct("action", {"user_id": uid}))
        # login may not be there if session was inserted via fixture (no /auth/session call),
        # but switch / create / view must be present.
        for required in ("switch", "create", "view"):
            assert required in actions, f"missing audit action: {required} (got {actions})"

        # Cleanup created data
        mongo.tickets.delete_one({"ticket_id": tid})
        mongo.sales.delete_one({"sale_id": sid})
        mongo.employees.delete_one({"employee_id": eid})


# ===================== Regression sweep =====================
class TestRegression:
    """Light sweep of previously-shipped endpoints. Ensures iteration 3 didn't break them."""

    ENDPOINTS_GET = [
        "/api/auth/me",
        "/api/companies",
        "/api/modules",
        "/api/dashboard",
        "/api/hr/employees",
        "/api/tickets",
        "/api/schedule",
        "/api/crm/customers",
        "/api/pos/products",
        "/api/pos/sales",
        "/api/payroll/runs",
        "/api/fleet/vehicles",
        "/api/inventory/items",
        "/api/alerts",
    ]

    @pytest.mark.parametrize("path", ENDPOINTS_GET)
    def test_get_endpoint_200(self, api_client, base_url, seeded_user, path):
        r = api_client.get(f"{base_url}{path}", headers=seeded_user["headers"])
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
        # check no _id leak
        body_text = r.text
        # Allow false positive on word "_id" only if it's a key
        assert '"_id"' not in body_text, f"{path} leaked _id"

    def test_inventory_lookup_bogus(self, api_client, base_url, seeded_user):
        r = api_client.get(f"{base_url}/api/inventory/lookup?barcode=BOGUS_XYZ",
                           headers=seeded_user["headers"])
        assert r.status_code == 200
        assert r.json()["found"] is False

    def test_payroll_t4_404(self, api_client, base_url, seeded_user):
        r = api_client.get(f"{base_url}/api/payroll/t4/emp_doesnotexist",
                           headers=seeded_user["headers"])
        assert r.status_code == 404

    def test_root(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"
