"""DB seeding: idempotent index + sample-data inserts. Called from FastAPI startup."""
from datetime import timedelta
import logging

from .db import db
from .deps import now_utc, new_id

logger = logging.getLogger(__name__)


async def run_startup_seed() -> None:
    """Create indexes + seed demo data if collections are empty. Safe to run repeatedly."""
    # --- Indexes ---
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.user_sessions.create_index("user_id")
    await db.user_sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.companies.create_index("company_id", unique=True)
    await db.employees.create_index([("company_id", 1), ("employee_id", 1)], unique=True)
    await db.tickets.create_index("ticket_id", unique=True)
    await db.memberships.create_index([("user_id", 1), ("company_id", 1), ("role", 1)], unique=True)
    await db.cache.create_index("key", unique=True)
    await db.credit_score_snapshots.create_index([("company_id", 1), ("date", 1)], unique=True)

    # --- Seed companies if none exist ---
    if await db.companies.count_documents({}) == 0:
        seed_companies = [
            {"company_id": "co_aidou_corp", "name": "Aidou Corporate", "industry": "Conglomerate",
             "logo_color": "#E25822", "created_at": now_utc()},
            {"company_id": "co_northstar_isp", "name": "Northstar ISP", "industry": "Telecom",
             "logo_color": "#10B981", "created_at": now_utc()},
            {"company_id": "co_summit_construction", "name": "Summit Construction", "industry": "Construction",
             "logo_color": "#F59E0B", "created_at": now_utc()},
            {"company_id": "mp_ridgeline_logistics", "name": "RidgeLine Logistics", "industry": "Transportation",
             "logo_color": "#3B82F6", "created_at": now_utc(), "is_marketplace": True},
            {"company_id": "mp_acadia_medical", "name": "Acadia Medical Group", "industry": "Healthcare",
             "logo_color": "#10B981", "created_at": now_utc(), "is_marketplace": True},
            {"company_id": "mp_pinewood_school", "name": "Pinewood Training Studio", "industry": "Education",
             "logo_color": "#F59E0B", "created_at": now_utc(), "is_marketplace": True},
        ]
        await db.companies.insert_many(seed_companies)

    # Backfill marketplace partner companies idempotently for existing DBs.
    for mp in [
        {"company_id": "mp_ridgeline_logistics", "name": "RidgeLine Logistics", "industry": "Transportation", "logo_color": "#3B82F6", "is_marketplace": True},
        {"company_id": "mp_acadia_medical", "name": "Acadia Medical Group", "industry": "Healthcare", "logo_color": "#10B981", "is_marketplace": True},
        {"company_id": "mp_pinewood_school", "name": "Pinewood Training Studio", "industry": "Education", "logo_color": "#F59E0B", "is_marketplace": True},
    ]:
        await db.companies.update_one(
            {"company_id": mp["company_id"]},
            {"$setOnInsert": {**mp, "created_at": now_utc()}},
            upsert=True,
        )

    # --- Employees ---
    if await db.employees.count_documents({}) == 0:
        depts = ["Engineering", "Field Ops", "Finance", "HR", "Sales", "Support"]
        roles = ["Senior Technician", "Account Manager", "Field Supervisor", "Payroll Lead",
                 "HR Coordinator", "Sales Rep", "Customer Success", "Network Engineer"]
        names = ["Alex Chen", "Priya Nair", "Marcus Reid", "Sofia Lopez", "Jordan Park",
                 "Mei Tanaka", "Owen Walsh", "Aisha Khan", "Lucas Bauer", "Hana Sato",
                 "Noah Okafor", "Camille Dubois"]
        statuses = ["active", "active", "active", "on_leave", "active", "active"]
        employees = []
        for co in ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"]:
            for i, nm in enumerate(names):
                employees.append({
                    "employee_id": new_id("emp"),
                    "company_id": co,
                    "name": nm,
                    "role": roles[i % len(roles)],
                    "department": depts[i % len(depts)],
                    "email": f"{nm.lower().replace(' ', '.')}@{co.split('_', 1)[1]}.com",
                    "status": statuses[i % len(statuses)],
                    "hired_at": now_utc() - timedelta(days=(i + 1) * 90),
                })
        await db.employees.insert_many(employees)

    # --- Tickets ---
    if await db.tickets.count_documents({}) == 0:
        ticket_titles = [
            ("Fiber outage – Block 14", "high", "in_progress"),
            ("Vehicle inspection overdue – Truck 207", "medium", "open"),
            ("Onsite installation – 88 Maple Ave", "medium", "open"),
            ("HVAC service – HQ Floor 3", "low", "open"),
            ("Permit renewal – Site C", "high", "open"),
            ("Equipment recalibration – Crane 4", "medium", "in_progress"),
            ("Customer complaint – Account #4521", "high", "open"),
            ("Software rollout – Field tablets", "low", "closed"),
            ("Safety incident report – Warehouse B", "high", "closed"),
        ]
        tickets = []
        for co in ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"]:
            for i, (title, pri, status) in enumerate(ticket_titles):
                tickets.append({
                    "ticket_id": new_id("tkt"),
                    "company_id": co,
                    "title": title,
                    "priority": pri,
                    "status": status,
                    "assignee": ["Alex Chen", "Marcus Reid", "Jordan Park"][i % 3],
                    "sla_hours": [2, 8, 24][i % 3],
                    "created_at": now_utc() - timedelta(hours=i * 3),
                })
        await db.tickets.insert_many(tickets)

    # --- Shifts ---
    if await db.shifts.count_documents({}) == 0:
        shifts = []
        for co in ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"]:
            for i in range(8):
                start_h = 7 + (i % 3) * 4
                shifts.append({
                    "shift_id": new_id("shf"),
                    "company_id": co,
                    "employee": ["Alex Chen", "Priya Nair", "Marcus Reid", "Sofia Lopez", "Hana Sato"][i % 5],
                    "department": ["Field Ops", "Engineering", "Support"][i % 3],
                    "start": f"{start_h:02d}:00",
                    "end": f"{(start_h + 8) % 24:02d}:00",
                    "date": (now_utc() + timedelta(days=i // 3)).date().isoformat(),
                })
        await db.shifts.insert_many(shifts)

    # --- CRM customers ---
    if await db.customers.count_documents({}) == 0:
        customers = []
        for co in ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"]:
            for i, nm in enumerate(["BlueRiver Holdings", "Maple Leaf Foods Co", "Stratford Hospitality",
                                     "Pinewood School District", "Acadia Medical Group", "RidgeLine Logistics",
                                     "Vista Property Trust", "Granite Industrial"]):
                customers.append({
                    "customer_id": new_id("cus"),
                    "company_id": co,
                    "name": nm,
                    "contact": ["Sam Boyd", "Lin Wei", "Rosa Diaz", "Tom Mehta"][i % 4],
                    "stage": ["lead", "qualified", "proposal", "won", "won", "active"][i % 6],
                    "value": (i + 1) * 12500,
                    "created_at": now_utc() - timedelta(days=i * 7),
                })
        await db.customers.insert_many(customers)

    # --- Alerts ---
    if await db.alerts.count_documents({}) == 0:
        alerts = []
        for co in ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"]:
            for i, (title, severity, kind) in enumerate([
                ("HST quarterly remittance due in 5 days", "high", "tax"),
                ("Cyber insurance renewal needed", "medium", "insurance"),
                ("Provincial WSIB filing reminder", "high", "compliance"),
                ("Fleet inspection due – 3 vehicles", "medium", "fleet"),
                ("Union collective bargaining review", "low", "labour"),
                ("Penetration test scheduled this week", "low", "security"),
            ]):
                alerts.append({
                    "alert_id": new_id("alt"),
                    "company_id": co,
                    "title": title,
                    "severity": severity,
                    "kind": kind,
                    "created_at": now_utc() - timedelta(hours=i),
                    "read": False,
                })
        await db.alerts.insert_many(alerts)

    # --- POS products ---
    if await db.products.count_documents({}) == 0:
        catalog = [
            ("Fiber Modem – Gigabit", "Hardware", 149.99, "8901-FBM-001"),
            ("Cat6 Patch Cable 25ft", "Hardware", 24.99, "8901-CAT-025"),
            ("On-site Install (1hr)", "Service", 95.00, "SRV-INSTALL-1"),
            ("Equipment Rental – Lift", "Service", 320.00, "SRV-LIFT-DAY"),
            ("Safety Helmet – Class E", "PPE", 38.50, "PPE-HLM-001"),
            ("Hi-Vis Vest – XL", "PPE", 22.00, "PPE-VEST-XL"),
            ("Concrete Mix 60lb", "Materials", 8.75, "MAT-CON-060"),
            ("Diesel Fuel (litre)", "Materials", 1.62, "MAT-DSL-1L"),
            ("Hotel Night Stay – Standard", "Hospitality", 189.00, "HSP-RM-STD"),
            ("Coffee – Large", "Food", 4.25, "FOD-CFE-LG"),
            ("Sandwich – Turkey Club", "Food", 12.50, "FOD-SND-TC"),
            ("Tablet – Field Ops", "Hardware", 489.00, "HW-TBL-FLD"),
        ]
        prods = []
        for co in ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"]:
            for i, (name, cat, price, sku) in enumerate(catalog):
                prods.append({
                    "product_id": new_id("prd"),
                    "company_id": co,
                    "name": name,
                    "category": cat,
                    "price": price,
                    "sku": sku,
                    "barcode": f"7{(hash(co + sku) % 10**11):011d}",
                    "stock": 50 + (i * 7) % 200,
                    "created_at": now_utc(),
                })
        await db.products.insert_many(prods)

    # --- Fleet vehicles ---
    if await db.vehicles.count_documents({}) == 0:
        veh_specs = [
            ("Truck 207", "Ford F-150", "Marcus Reid", 43.6532, -79.3832, "active", 78, 142_300),
            ("Van 14", "Mercedes Sprinter", "Sofia Lopez", 43.7001, -79.4163, "active", 54, 88_120),
            ("Crane 4", "Liebherr LTM", "Lucas Bauer", 43.6426, -79.3871, "idle", 91, 12_550),
            ("Truck 102", "Chevy Silverado", "Jordan Park", 43.5890, -79.6441, "maintenance", 23, 201_800),
            ("Service Car 8", "Honda Civic", "Mei Tanaka", 43.7615, -79.4111, "active", 67, 65_440),
            ("Snowplow 3", "Western Star", "Owen Walsh", 43.6850, -79.7080, "idle", 88, 31_220),
        ]
        vehs = []
        for co in ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"]:
            for plate, model, driver, lat, lng, status, fuel, mileage in veh_specs:
                vehs.append({
                    "vehicle_id": new_id("veh"),
                    "company_id": co,
                    "plate": plate,
                    "model": model,
                    "driver": driver,
                    "lat": lat,
                    "lng": lng,
                    "status": status,
                    "fuel_pct": fuel,
                    "mileage_km": mileage,
                    "next_inspection": (now_utc() + timedelta(days=(hash(plate) % 60) - 10)).date().isoformat(),
                })
        await db.vehicles.insert_many(vehs)

    # --- Inventory ---
    if await db.inventory.count_documents({}) == 0:
        items_def = [
            ("Optical Splitter 1x8", "Network", "Warehouse A", 124, 50, "5901123400201"),
            ("Underground Conduit 4in", "Materials", "Yard B", 38, 60, "5901123400202"),
            ("Splice Closure", "Network", "Warehouse A", 88, 30, "5901123400203"),
            ("LED Worklight 2400lm", "Tools", "Truck 207", 6, 10, "5901123400204"),
            ("First Aid Kit", "Safety", "HQ Storage", 22, 15, "5901123400205"),
            ("Battery Pack 18V", "Tools", "Warehouse A", 14, 20, "5901123400206"),
            ("Reflective Cone", "Safety", "Yard B", 210, 100, "5901123400207"),
            ("Hand Saw 24in", "Tools", "Truck 102", 9, 8, "5901123400208"),
            ("Industrial Adhesive", "Materials", "Warehouse A", 47, 25, "5901123400209"),
            ("Network Switch 24-port", "Network", "HQ Storage", 12, 6, "5901123400210"),
        ]
        items = []
        for co in ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"]:
            for name, cat, loc, stock, reorder, base_bar in items_def:
                items.append({
                    "item_id": new_id("inv"),
                    "company_id": co,
                    "name": name,
                    "category": cat,
                    "location": loc,
                    "stock": stock,
                    "reorder_at": reorder,
                    "barcode": f"{base_bar}{abs(hash(co)) % 9}",
                    "updated_at": now_utc(),
                })
        await db.inventory.insert_many(items)

    # --- Payroll ---
    if await db.pay_runs.count_documents({}) == 0:
        runs = []
        for co in ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"]:
            for q, label in enumerate(["Jan 1–15", "Jan 16–31", "Feb 1–15", "Feb 16–28"]):
                runs.append({
                    "run_id": new_id("run"),
                    "company_id": co,
                    "period": label,
                    "pay_date": (now_utc() - timedelta(days=(3 - q) * 14)).date().isoformat(),
                    "headcount": 12,
                    "gross": 48200 + q * 1200,
                    "tax": 9100 + q * 240,
                    "cpp_ei": 3200 + q * 95,
                    "net": 35900 + q * 865,
                    "status": "posted" if q < 3 else "draft",
                })
        await db.pay_runs.insert_many(runs)

    logger.info("Aidou Command backend started with seeded data.")
