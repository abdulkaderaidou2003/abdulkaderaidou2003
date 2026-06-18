"""Backend API tests for Aidou Command Enterprise Ultimate."""
import json
import re

import pytest


# ---------------- Root / health ----------------
class TestRoot:
    def test_root_ok(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert "Aidou" in data.get("app", "")
        assert "_id" not in data


# ---------------- Auth ----------------
class TestAuth:
    def test_session_empty_body(self, api_client, base_url):
        # missing field -> Pydantic 422 (FastAPI default for invalid body)
        r = api_client.post(f"{base_url}/api/auth/session", json={})
        assert r.status_code in (400, 422), f"expected 400/422 got {r.status_code}"

    def test_session_empty_string(self, api_client, base_url):
        # explicit empty session_token -> backend raises 400
        r = api_client.post(f"{base_url}/api/auth/session", json={"session_token": ""})
        assert r.status_code == 400

    def test_session_invalid_token(self, api_client, base_url):
        r = api_client.post(
            f"{base_url}/api/auth/session",
            json={"session_token": "definitely_not_valid_xyz_12345"},
        )
        assert r.status_code == 401

    def test_me_without_token(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/auth/me")
        assert r.status_code == 401

    def test_me_with_invalid_token(self, api_client, base_url):
        r = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": "Bearer bogus_token_value"},
        )
        assert r.status_code == 401

    def test_me_with_valid_token(self, api_client, base_url, seeded_user):
        r = api_client.get(f"{base_url}/api/auth/me", headers=seeded_user["headers"])
        assert r.status_code == 200
        body = r.json()
        assert "user" in body
        assert body["user"]["user_id"] == seeded_user["user_id"]
        assert body["user"]["active_company_id"] == "co_aidou_corp"
        assert "_id" not in body["user"]


# ---------------- Protected endpoints (401 without bearer) ----------------
PROTECTED_GETS = [
    "/api/companies",
    "/api/modules",
    "/api/dashboard",
    "/api/hr/employees",
    "/api/tickets",
    "/api/schedule",
    "/api/crm/customers",
    "/api/alerts",
    "/api/ai/history?session_id=x&assistant=advisor",
]


@pytest.mark.parametrize("path", PROTECTED_GETS)
def test_protected_requires_bearer(api_client, base_url, path):
    r = api_client.get(f"{base_url}{path}")
    assert r.status_code == 401, f"{path} returned {r.status_code}"


# ---------------- Seed data presence ----------------
class TestSeedData:
    def test_companies_seeded(self, mongo):
        ids = {d["company_id"] for d in mongo.companies.find({}, {"company_id": 1, "_id": 0})}
        assert {"co_aidou_corp", "co_northstar_isp", "co_summit_construction"}.issubset(ids)

    def test_collections_populated(self, mongo):
        for coll in ("employees", "tickets", "shifts", "customers", "alerts"):
            assert mongo[coll].count_documents({}) > 0, f"{coll} not seeded"

    def test_companies_endpoint(self, api_client, base_url, seeded_user):
        r = api_client.get(f"{base_url}/api/companies", headers=seeded_user["headers"])
        assert r.status_code == 200
        data = r.json()
        assert len(data["companies"]) == 3
        # No _id leakage
        for c in data["companies"]:
            assert "_id" not in c
        assert data["active_company_id"] == "co_aidou_corp"


# ---------------- Modules / Dashboard ----------------
class TestModulesAndDashboard:
    def test_modules(self, api_client, base_url, seeded_user):
        r = api_client.get(f"{base_url}/api/modules", headers=seeded_user["headers"])
        assert r.status_code == 200
        cat = r.json()["catalog"]
        assert isinstance(cat, list) and len(cat) >= 5

    def test_dashboard_kpis(self, api_client, base_url, seeded_user):
        r = api_client.get(f"{base_url}/api/dashboard", headers=seeded_user["headers"])
        assert r.status_code == 200
        d = r.json()
        for k in ("revenue_mtd", "payroll_mtd", "employees_total", "open_tickets", "alerts_unread"):
            assert k in d["kpis"]
        assert d["kpis"]["employees_total"] > 0
        # feed items shouldn't have _id
        for f in d["feed"]:
            assert "_id" not in f


# ---------------- Multi-company isolation ----------------
class TestCompanySwitch:
    def test_switch_changes_results(self, api_client, base_url, seeded_user):
        h = seeded_user["headers"]

        # initial dashboard for co_aidou_corp
        d1 = api_client.get(f"{base_url}/api/dashboard", headers=h).json()
        emps1 = api_client.get(f"{base_url}/api/hr/employees", headers=h).json()["employees"]
        tks1 = api_client.get(f"{base_url}/api/tickets", headers=h).json()["tickets"]
        assert all(e["company_id"] == "co_aidou_corp" for e in emps1)
        assert all(t["company_id"] == "co_aidou_corp" for t in tks1)

        # switch
        sw = api_client.post(
            f"{base_url}/api/companies/switch",
            json={"company_id": "co_northstar_isp"},
            headers=h,
        )
        assert sw.status_code == 200
        assert sw.json()["active_company_id"] == "co_northstar_isp"

        emps2 = api_client.get(f"{base_url}/api/hr/employees", headers=h).json()["employees"]
        tks2 = api_client.get(f"{base_url}/api/tickets", headers=h).json()["tickets"]
        assert all(e["company_id"] == "co_northstar_isp" for e in emps2)
        assert all(t["company_id"] == "co_northstar_isp" for t in tks2)

        d2 = api_client.get(f"{base_url}/api/dashboard", headers=h).json()
        # Pseudo KPIs differ between companies (different seed hash)
        assert d1["kpis"]["revenue_mtd"] != d2["kpis"]["revenue_mtd"]

        # switch back for downstream tests
        api_client.post(
            f"{base_url}/api/companies/switch",
            json={"company_id": "co_aidou_corp"},
            headers=h,
        )

    def test_switch_unauthorized_company(self, api_client, base_url, seeded_user):
        r = api_client.post(
            f"{base_url}/api/companies/switch",
            json={"company_id": "co_does_not_exist"},
            headers=seeded_user["headers"],
        )
        assert r.status_code == 403


# ---------------- Alerts mark read ----------------
class TestAlerts:
    def test_mark_alert_read(self, api_client, base_url, seeded_user):
        h = seeded_user["headers"]
        # ensure on co_aidou_corp
        api_client.post(
            f"{base_url}/api/companies/switch",
            json={"company_id": "co_aidou_corp"},
            headers=h,
        )
        alerts = api_client.get(f"{base_url}/api/alerts", headers=h).json()["alerts"]
        assert len(alerts) > 0
        for a in alerts:
            assert "_id" not in a
        target = next((a for a in alerts if not a["read"]), alerts[0])
        r = api_client.post(f"{base_url}/api/alerts/{target['alert_id']}/read", headers=h)
        assert r.status_code == 200
        assert r.json().get("ok") is True

        # verify persistence
        alerts2 = api_client.get(f"{base_url}/api/alerts", headers=h).json()["alerts"]
        match = next((a for a in alerts2 if a["alert_id"] == target["alert_id"]), None)
        assert match is not None and match["read"] is True


# ---------------- AI chat SSE ----------------
class TestAIChat:
    def test_ai_chat_sse_stream(self, base_url, seeded_user):
        import requests
        url = f"{base_url}/api/ai/chat"
        payload = {
            "assistant": "advisor",
            "session_id": "TEST_sess_1",
            "message": "In one short sentence, what is HST?",
        }
        with requests.post(
            url,
            json=payload,
            headers={**seeded_user["headers"], "Accept": "text/event-stream"},
            stream=True,
            timeout=60,
        ) as resp:
            assert resp.status_code == 200
            ctype = resp.headers.get("content-type", "")
            assert "text/event-stream" in ctype, f"got content-type={ctype}"
            chunks = []
            for raw in resp.iter_lines(decode_unicode=True):
                if raw is None:
                    continue
                if raw.startswith("data:"):
                    chunks.append(raw[5:].strip())
                if "[done]" in raw or len(chunks) > 200:
                    break
            assert len(chunks) > 0, "no SSE data chunks received"
            joined = " ".join(chunks)
            assert "[error]" not in joined, f"AI errored: {joined[:300]}"


# ---------------- AI history ----------------
class TestAIHistory:
    def test_history_returns_persisted_messages(self, api_client, base_url, seeded_user):
        r = api_client.get(
            f"{base_url}/api/ai/history",
            params={"session_id": "TEST_sess_1", "assistant": "advisor"},
            headers=seeded_user["headers"],
        )
        assert r.status_code == 200
        data = r.json()
        assert "messages" in data
        for m in data["messages"]:
            assert "_id" not in m


# ---------------- HR Create + verify ----------------
class TestEmployeesCreate:
    def test_create_employee_persists(self, api_client, base_url, seeded_user, mongo):
        h = seeded_user["headers"]
        payload = {"name": "TEST_Emp", "role": "QA", "department": "Engineering",
                   "email": "TEST_emp@example.com", "status": "active"}
        r = api_client.post(f"{base_url}/api/hr/employees", json=payload, headers=h)
        assert r.status_code == 200
        emp = r.json()["employee"]
        assert emp["company_id"] == "co_aidou_corp"
        assert "_id" not in emp
        # Verify in DB
        found = mongo.employees.find_one({"employee_id": emp["employee_id"]})
        assert found is not None
        mongo.employees.delete_one({"employee_id": emp["employee_id"]})
