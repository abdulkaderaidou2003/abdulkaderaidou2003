"""Tests for the 4 NEW modules added in iteration 2:
POS (products/sales), Payroll (runs/T4), Fleet GPS (vehicles), Inventory (items/lookup).
Each module re-validates: 401 without bearer, no _id leakage, multi-company isolation."""
import pytest


# ---------------- 401 without bearer ----------------
NEW_PROTECTED_GETS = [
    "/api/pos/products",
    "/api/pos/products?category=Hardware",
    "/api/pos/sales",
    "/api/payroll/runs",
    "/api/payroll/t4/emp_does_not_exist",
    "/api/fleet/vehicles",
    "/api/inventory/items",
    "/api/inventory/lookup?barcode=12345",
]


@pytest.mark.parametrize("path", NEW_PROTECTED_GETS)
def test_new_endpoints_require_bearer(api_client, base_url, path):
    r = api_client.get(f"{base_url}{path}")
    assert r.status_code == 401, f"{path} returned {r.status_code}"


def test_pos_sales_post_requires_bearer(api_client, base_url):
    r = api_client.post(f"{base_url}/api/pos/sales", json={"items": []})
    assert r.status_code == 401


# ---------------- Helpers ----------------
def _switch(api_client, base_url, headers, co_id):
    r = api_client.post(
        f"{base_url}/api/companies/switch",
        json={"company_id": co_id},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["active_company_id"] == co_id


# ---------------- POS Products ----------------
class TestPOSProducts:
    def test_list_products(self, api_client, base_url, seeded_user):
        _switch(api_client, base_url, seeded_user["headers"], "co_aidou_corp")
        r = api_client.get(f"{base_url}/api/pos/products", headers=seeded_user["headers"])
        assert r.status_code == 200
        data = r.json()
        assert "products" in data
        prods = data["products"]
        assert len(prods) >= 5, f"expected seeded products, got {len(prods)}"
        for p in prods:
            assert "_id" not in p
            assert p["company_id"] == "co_aidou_corp"
            assert "price" in p and "product_id" in p and "barcode" in p

    def test_list_products_category_filter(self, api_client, base_url, seeded_user):
        _switch(api_client, base_url, seeded_user["headers"], "co_aidou_corp")
        r = api_client.get(
            f"{base_url}/api/pos/products",
            params={"category": "Hardware"},
            headers=seeded_user["headers"],
        )
        assert r.status_code == 200
        prods = r.json()["products"]
        assert len(prods) > 0
        for p in prods:
            assert p["category"] == "Hardware"

    def test_list_products_category_all_returns_all(self, api_client, base_url, seeded_user):
        # 'all' should be a no-op (no filter)
        r = api_client.get(
            f"{base_url}/api/pos/products",
            params={"category": "all"},
            headers=seeded_user["headers"],
        )
        assert r.status_code == 200
        cats = {p["category"] for p in r.json()["products"]}
        assert len(cats) > 1

    def test_list_products_multi_company_isolation(self, api_client, base_url, seeded_user):
        h = seeded_user["headers"]
        _switch(api_client, base_url, h, "co_aidou_corp")
        p1 = api_client.get(f"{base_url}/api/pos/products", headers=h).json()["products"]
        ids1 = {p["product_id"] for p in p1}

        _switch(api_client, base_url, h, "co_northstar_isp")
        p2 = api_client.get(f"{base_url}/api/pos/products", headers=h).json()["products"]
        ids2 = {p["product_id"] for p in p2}

        assert ids1.isdisjoint(ids2), "product_ids must not overlap across companies"
        assert all(p["company_id"] == "co_northstar_isp" for p in p2)

        _switch(api_client, base_url, h, "co_aidou_corp")


# ---------------- POS Sales ----------------
class TestPOSSales:
    def test_create_sale_empty_cart_400(self, api_client, base_url, seeded_user):
        _switch(api_client, base_url, seeded_user["headers"], "co_aidou_corp")
        r = api_client.post(
            f"{base_url}/api/pos/sales",
            json={"items": [], "tender": "card"},
            headers=seeded_user["headers"],
        )
        assert r.status_code == 400

    def test_create_sale_all_invalid_product_ids_400(self, api_client, base_url, seeded_user):
        _switch(api_client, base_url, seeded_user["headers"], "co_aidou_corp")
        r = api_client.post(
            f"{base_url}/api/pos/sales",
            json={"items": [{"product_id": "prd_nope_999", "qty": 2}]},
            headers=seeded_user["headers"],
        )
        assert r.status_code == 400

    def test_create_sale_filters_invalid_and_persists(
        self, api_client, base_url, seeded_user, mongo
    ):
        h = seeded_user["headers"]
        _switch(api_client, base_url, h, "co_aidou_corp")
        prods = api_client.get(f"{base_url}/api/pos/products", headers=h).json()["products"]
        assert len(prods) >= 2
        p1, p2 = prods[0], prods[1]

        payload = {
            "items": [
                {"product_id": p1["product_id"], "qty": 2},
                {"product_id": "prd_does_not_exist", "qty": 5},  # filtered
                {"product_id": p2["product_id"], "qty": 1},
            ],
            "tender": "cash",
        }
        r = api_client.post(f"{base_url}/api/pos/sales", json=payload, headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "_id" not in body
        sale = body["sale"]
        assert "_id" not in sale
        # Should contain exactly 2 valid line items
        assert len(sale["items"]) == 2
        expected_subtotal = round(p1["price"] * 2 + p2["price"] * 1, 2)
        assert sale["subtotal"] == expected_subtotal, sale
        expected_hst = round(expected_subtotal * 0.13, 2)
        assert sale["hst"] == expected_hst
        assert sale["total"] == round(expected_subtotal + expected_hst, 2)
        assert sale["company_id"] == "co_aidou_corp"
        assert sale["tender"] == "cash"
        assert sale["sale_id"].startswith("sal_")

        # Persistence
        found = mongo.sales.find_one({"sale_id": sale["sale_id"]})
        assert found is not None
        assert found["total"] == sale["total"]
        mongo.sales.delete_one({"sale_id": sale["sale_id"]})

    def test_list_sales_returns_recent(self, api_client, base_url, seeded_user, mongo):
        h = seeded_user["headers"]
        _switch(api_client, base_url, h, "co_aidou_corp")
        prods = api_client.get(f"{base_url}/api/pos/products", headers=h).json()["products"]
        p = prods[0]
        r = api_client.post(
            f"{base_url}/api/pos/sales",
            json={"items": [{"product_id": p["product_id"], "qty": 1}], "tender": "card"},
            headers=h,
        )
        assert r.status_code == 200
        sale_id = r.json()["sale"]["sale_id"]

        r2 = api_client.get(f"{base_url}/api/pos/sales", headers=h)
        assert r2.status_code == 200
        sales = r2.json()["sales"]
        assert any(s["sale_id"] == sale_id for s in sales)
        for s in sales:
            assert "_id" not in s
            assert s["company_id"] == "co_aidou_corp"

        mongo.sales.delete_one({"sale_id": sale_id})


# ---------------- Payroll ----------------
class TestPayroll:
    def test_list_pay_runs(self, api_client, base_url, seeded_user):
        h = seeded_user["headers"]
        _switch(api_client, base_url, h, "co_aidou_corp")
        r = api_client.get(f"{base_url}/api/payroll/runs", headers=h)
        assert r.status_code == 200
        runs = r.json()["runs"]
        assert len(runs) >= 1
        for run in runs:
            assert "_id" not in run
            assert run["company_id"] == "co_aidou_corp"
            for k in ("run_id", "period", "pay_date", "gross", "net", "status"):
                assert k in run

    def test_pay_runs_isolation(self, api_client, base_url, seeded_user):
        h = seeded_user["headers"]
        _switch(api_client, base_url, h, "co_aidou_corp")
        r1 = api_client.get(f"{base_url}/api/payroll/runs", headers=h).json()["runs"]

        _switch(api_client, base_url, h, "co_summit_construction")
        r2 = api_client.get(f"{base_url}/api/payroll/runs", headers=h).json()["runs"]
        assert all(x["company_id"] == "co_summit_construction" for x in r2)
        ids1 = {x["run_id"] for x in r1}
        ids2 = {x["run_id"] for x in r2}
        assert ids1.isdisjoint(ids2)

        _switch(api_client, base_url, h, "co_aidou_corp")

    def test_t4_unknown_employee_404(self, api_client, base_url, seeded_user):
        _switch(api_client, base_url, seeded_user["headers"], "co_aidou_corp")
        r = api_client.get(
            f"{base_url}/api/payroll/t4/emp_does_not_exist_xyz",
            headers=seeded_user["headers"],
        )
        assert r.status_code == 404

    def test_t4_for_real_employee(self, api_client, base_url, seeded_user):
        h = seeded_user["headers"]
        _switch(api_client, base_url, h, "co_aidou_corp")
        emps = api_client.get(f"{base_url}/api/hr/employees", headers=h).json()["employees"]
        assert len(emps) > 0
        emp_id = emps[0]["employee_id"]
        r = api_client.get(f"{base_url}/api/payroll/t4/{emp_id}", headers=h)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "_id" not in data
        assert data["tax_year"] == 2025
        boxes = data["boxes"]
        for k in ("14_employment_income", "16_cpp_contrib", "18_ei_premium", "22_income_tax", "net"):
            assert k in boxes, f"missing T4 box {k}"
        # net = gross - cpp - ei - tax (within rounding)
        recomputed = round(
            boxes["14_employment_income"]
            - boxes["16_cpp_contrib"]
            - boxes["18_ei_premium"]
            - boxes["22_income_tax"],
            2,
        )
        assert abs(recomputed - boxes["net"]) < 0.05
        assert data["employer"]["co_id"] == "co_aidou_corp"
        assert "_id" not in data["employee"]


# ---------------- Fleet ----------------
class TestFleet:
    def test_list_vehicles(self, api_client, base_url, seeded_user):
        h = seeded_user["headers"]
        _switch(api_client, base_url, h, "co_aidou_corp")
        r = api_client.get(f"{base_url}/api/fleet/vehicles", headers=h)
        assert r.status_code == 200
        vehs = r.json()["vehicles"]
        assert len(vehs) >= 1
        for v in vehs:
            assert "_id" not in v
            assert v["company_id"] == "co_aidou_corp"
            for k in ("vehicle_id", "plate", "lat", "lng", "speed_kmh", "heading", "status"):
                assert k in v
            assert 0 <= v["heading"] <= 359
            assert v["speed_kmh"] >= 0

    def test_gps_drift_between_calls(self, api_client, base_url, seeded_user):
        h = seeded_user["headers"]
        _switch(api_client, base_url, h, "co_aidou_corp")
        a = api_client.get(f"{base_url}/api/fleet/vehicles", headers=h).json()["vehicles"]
        b = api_client.get(f"{base_url}/api/fleet/vehicles", headers=h).json()["vehicles"]
        # At least one vehicle's lat/lng should differ across two calls (random drift)
        by_id_a = {v["vehicle_id"]: v for v in a}
        by_id_b = {v["vehicle_id"]: v for v in b}
        any_diff = False
        for vid, va in by_id_a.items():
            vb = by_id_b.get(vid)
            if not vb:
                continue
            if va["lat"] != vb["lat"] or va["lng"] != vb["lng"]:
                any_diff = True
                break
        assert any_diff, "expected mock GPS drift between calls"

    def test_fleet_isolation(self, api_client, base_url, seeded_user):
        h = seeded_user["headers"]
        _switch(api_client, base_url, h, "co_northstar_isp")
        vehs = api_client.get(f"{base_url}/api/fleet/vehicles", headers=h).json()["vehicles"]
        assert all(v["company_id"] == "co_northstar_isp" for v in vehs)
        _switch(api_client, base_url, h, "co_aidou_corp")


# ---------------- Inventory ----------------
class TestInventory:
    def test_list_inventory(self, api_client, base_url, seeded_user):
        h = seeded_user["headers"]
        _switch(api_client, base_url, h, "co_aidou_corp")
        r = api_client.get(f"{base_url}/api/inventory/items", headers=h)
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        for it in items:
            assert "_id" not in it
            assert it["company_id"] == "co_aidou_corp"
            for k in ("item_id", "name", "category", "barcode", "stock"):
                assert k in it

    def test_inventory_isolation(self, api_client, base_url, seeded_user):
        h = seeded_user["headers"]
        _switch(api_client, base_url, h, "co_aidou_corp")
        i1 = api_client.get(f"{base_url}/api/inventory/items", headers=h).json()["items"]
        _switch(api_client, base_url, h, "co_summit_construction")
        i2 = api_client.get(f"{base_url}/api/inventory/items", headers=h).json()["items"]
        ids1 = {x["item_id"] for x in i1}
        ids2 = {x["item_id"] for x in i2}
        assert ids1.isdisjoint(ids2)
        _switch(api_client, base_url, h, "co_aidou_corp")

    def test_lookup_invalid_barcode(self, api_client, base_url, seeded_user):
        _switch(api_client, base_url, seeded_user["headers"], "co_aidou_corp")
        r = api_client.get(
            f"{base_url}/api/inventory/lookup",
            params={"barcode": "DOES_NOT_EXIST_999999"},
            headers=seeded_user["headers"],
        )
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is False
        assert body["item"] is None
        assert body["product"] is None

    def test_lookup_real_inventory_barcode(self, api_client, base_url, seeded_user):
        h = seeded_user["headers"]
        _switch(api_client, base_url, h, "co_aidou_corp")
        items = api_client.get(f"{base_url}/api/inventory/items", headers=h).json()["items"]
        bc = items[0]["barcode"]
        r = api_client.get(
            f"{base_url}/api/inventory/lookup",
            params={"barcode": bc},
            headers=h,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is True
        assert body["item"] is not None
        assert body["item"]["barcode"] == bc
        assert "_id" not in body["item"]

    def test_lookup_real_product_barcode(self, api_client, base_url, seeded_user):
        h = seeded_user["headers"]
        _switch(api_client, base_url, h, "co_aidou_corp")
        prods = api_client.get(f"{base_url}/api/pos/products", headers=h).json()["products"]
        bc = prods[0]["barcode"]
        r = api_client.get(
            f"{base_url}/api/inventory/lookup",
            params={"barcode": bc},
            headers=h,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is True
        # Could match inventory or product (we only assert product side here)
        assert body["product"] is not None
        assert body["product"]["barcode"] == bc
        assert "_id" not in body["product"]
