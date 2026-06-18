"""Aidou Command Enterprise Ultimate - Backend API"""
from fastapi import FastAPI, APIRouter, HTTPException, Header, Request, Depends
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import json
import httpx
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from core.deps import has_role, require_role, audit  # noqa: F401

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

app = FastAPI(title="Aidou Command API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ------------ Helpers ------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


async def get_user_from_token(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = sess.get("expires_at")
    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now_utc():
            raise HTTPException(status_code=401, detail="Session expired")
    user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ------------ Models ------------
class SessionRequest(BaseModel):
    session_token: str


class CompanySwitch(BaseModel):
    company_id: str


class EmployeeIn(BaseModel):
    name: str
    role: str
    department: str
    email: Optional[str] = None
    status: str = "active"


class TicketIn(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: str = "medium"
    assignee: Optional[str] = None


class ChatRequest(BaseModel):
    assistant: str  # hr | accountant | scheduler | support | marketing | analytics | advisor
    session_id: str
    message: str


class WorkspaceSwitch(BaseModel):
    company_id: str
    role: str  # owner | manager | employee | customer


class RoleUpdate(BaseModel):
    role: str


# ------------ Module Catalog ------------
MODULE_CATALOG = [
    {"category": "People", "modules": [
        {"id": "hr", "name": "Human Resources", "icon": "users", "desc": "Records, recruiting, onboarding"},
        {"id": "payroll", "name": "Payroll", "icon": "credit-card", "desc": "Pay stubs, deductions, T4"},
        {"id": "schedule", "name": "Workforce", "icon": "calendar", "desc": "Shifts & attendance"},
        {"id": "training", "name": "Training", "icon": "book-open", "desc": "Courses & certifications"},
        {"id": "recognition", "name": "Recognition", "icon": "award", "desc": "Employee awards"},
        {"id": "labour", "name": "Labour Relations", "icon": "shield", "desc": "Unions & grievances"},
    ]},
    {"category": "Finance", "modules": [
        {"id": "accounting", "name": "Accounting", "icon": "bar-chart-2", "desc": "GL, AP/AR"},
        {"id": "tax", "name": "Tax", "icon": "file-text", "desc": "HST/GST, corp tax"},
        {"id": "insurance", "name": "Insurance", "icon": "umbrella", "desc": "Claims & renewals"},
        {"id": "treasury", "name": "Treasury", "icon": "trending-up", "desc": "Banking & loans"},
        {"id": "billing", "name": "Billing", "icon": "dollar-sign", "desc": "Invoices & payments"},
        {"id": "procurement", "name": "Procurement", "icon": "shopping-cart", "desc": "Purchase orders"},
    ]},
    {"category": "Sales & Customers", "modules": [
        {"id": "crm", "name": "CRM", "icon": "user-check", "desc": "Customer records"},
        {"id": "sales", "name": "Sales", "icon": "trending-up", "desc": "Pipeline & leads"},
        {"id": "pos", "name": "Point of Sale", "icon": "shopping-bag", "desc": "Retail & restaurant"},
        {"id": "marketing", "name": "Marketing", "icon": "send", "desc": "Campaigns & reviews"},
        {"id": "portal", "name": "Customer Portal", "icon": "globe", "desc": "Self-serve access"},
        {"id": "events", "name": "Events", "icon": "calendar", "desc": "Bookings & catering"},
    ]},
    {"category": "Operations", "modules": [
        {"id": "tickets", "name": "Job Tickets", "icon": "clipboard", "desc": "Work orders"},
        {"id": "inventory", "name": "Inventory", "icon": "package", "desc": "Stock & barcodes"},
        {"id": "fleet", "name": "Fleet", "icon": "truck", "desc": "GPS, fuel, drivers"},
        {"id": "projects", "name": "Projects", "icon": "git-branch", "desc": "Gantt & milestones"},
        {"id": "facilities", "name": "Facilities", "icon": "home", "desc": "Assets & maintenance"},
        {"id": "isp", "name": "ISP Ops", "icon": "wifi", "desc": "Provisioning & outages"},
        {"id": "property", "name": "Property Mgmt", "icon": "key", "desc": "Tenants & leases"},
        {"id": "repair", "name": "Repair Shop", "icon": "tool", "desc": "Device intake & parts"},
        {"id": "drone", "name": "Drone Ops", "icon": "navigation", "desc": "Flights & missions"},
    ]},
    {"category": "Compliance & Safety", "modules": [
        {"id": "safety", "name": "Health & Safety", "icon": "alert-triangle", "desc": "Incidents & PPE"},
        {"id": "legal", "name": "Legal", "icon": "book", "desc": "Contracts & cases"},
        {"id": "govt", "name": "Govt Compliance", "icon": "flag", "desc": "Federal & provincial"},
        {"id": "emergency", "name": "Emergency", "icon": "alert-octagon", "desc": "Crisis & continuity"},
        {"id": "soc", "name": "Security Ops", "icon": "video", "desc": "Cameras & access"},
        {"id": "documents", "name": "Documents", "icon": "folder", "desc": "Contracts & files"},
    ]},
    {"category": "Communications", "modules": [
        {"id": "chat", "name": "Chat", "icon": "message-circle", "desc": "Team & announcements"},
        {"id": "knowledge", "name": "Knowledge Base", "icon": "book-open", "desc": "SOPs & wiki"},
        {"id": "vendor", "name": "Vendor Portal", "icon": "briefcase", "desc": "Contractors & suppliers"},
    ]},
    {"category": "Intelligence", "modules": [
        {"id": "bi", "name": "Business Intel", "icon": "pie-chart", "desc": "KPIs & forecasts"},
        {"id": "gis", "name": "GIS & Maps", "icon": "map", "desc": "Routes & coverage"},
        {"id": "ai", "name": "AI Command", "icon": "cpu", "desc": "AI assistants"},
    ]},
    {"category": "IT & Future", "modules": [
        {"id": "it", "name": "IT & Cloud", "icon": "server", "desc": "Devices & backups"},
        {"id": "security", "name": "Cybersecurity", "icon": "lock", "desc": "MFA & audit"},
        {"id": "iot", "name": "IoT", "icon": "radio", "desc": "Smart sensors"},
        {"id": "wallet", "name": "Digital Wallet", "icon": "credit-card", "desc": "Employee IDs"},
    ]},
]


# ------------ Startup / Seed ------------
@app.on_event("startup")
async def startup():
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

    # Seed companies if none exist
    if await db.companies.count_documents({}) == 0:
        seed_companies = [
            {"company_id": "co_aidou_corp", "name": "Aidou Corporate", "industry": "Conglomerate",
             "logo_color": "#E25822", "created_at": now_utc()},
            {"company_id": "co_northstar_isp", "name": "Northstar ISP", "industry": "Telecom",
             "logo_color": "#10B981", "created_at": now_utc()},
            {"company_id": "co_summit_construction", "name": "Summit Construction", "industry": "Construction",
             "logo_color": "#F59E0B", "created_at": now_utc()},
        ]
        await db.companies.insert_many(seed_companies)

    # Seed sample employees per company
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

    # Seed sample tickets
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

    # Seed shifts
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

    # Seed CRM customers
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

    # Seed alerts
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

    # Seed POS products
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

    # Seed Fleet vehicles
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

    # Seed Inventory items
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

    # Seed Payroll pay runs + YTD records
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


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


# ------------ Auth ------------
@api_router.post("/auth/session")
async def create_session(body: SessionRequest):
    """Verify session token with Emergent and create/refresh local session."""
    if not body.session_token:
        raise HTTPException(status_code=400, detail="session_token required")
    async with httpx.AsyncClient(timeout=15.0) as hc:
        r = await hc.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": body.session_token},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session token")
    data = r.json()
    email = data.get("email")
    name = data.get("name") or email
    picture = data.get("picture", "")
    token = data.get("session_token") or body.session_token

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture, "last_login": now_utc()}},
        )
        # Make sure user is member of demo companies (for shared multi-company demo)
        member_cos = existing.get("company_ids", [])
        if not member_cos:
            member_cos = ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"]
            await db.users.update_one({"user_id": user_id}, {"$set": {"company_ids": member_cos,
                                                                      "active_company_id": member_cos[0]}})
    else:
        user_id = new_id("user")
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "company_ids": ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"],
            "active_company_id": "co_aidou_corp",
            "role": "admin",
            "created_at": now_utc(),
            "last_login": now_utc(),
        })

    # Ensure memberships exist (multi-role / multi-workspace identity).
    # New users get owner@aidou_corp + manager@northstar_isp + customer@summit_construction
    # so the workspace selector showcases the multi-role experience.
    existing_memberships = await db.memberships.count_documents({"user_id": user_id})
    if existing_memberships == 0:
        default_memberships = [
            {"membership_id": new_id("mem"), "user_id": user_id, "company_id": "co_aidou_corp",
             "role": "owner", "created_at": now_utc()},
            {"membership_id": new_id("mem"), "user_id": user_id, "company_id": "co_northstar_isp",
             "role": "manager", "created_at": now_utc()},
            {"membership_id": new_id("mem"), "user_id": user_id, "company_id": "co_summit_construction",
             "role": "employee", "created_at": now_utc()},
        ]
        await db.memberships.insert_many(default_memberships)
        # default active workspace = first one (owner)
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "active_company_id": "co_aidou_corp",
                "active_role": "owner",
            }},
        )

    # Replace existing token entry
    await db.user_sessions.delete_many({"session_token": token})
    await db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "expires_at": now_utc() + timedelta(days=7),
        "created_at": now_utc(),
    })

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    await audit(user, "login", "auth", meta={"email": email})
    return {"session_token": token, "user": user}


@api_router.get("/auth/me")
async def me(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    return {"user": user}


@api_router.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        await db.user_sessions.delete_many({"session_token": token})
    return {"ok": True}


# ------------ Companies ------------
@api_router.get("/companies")
async def list_companies(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    ids = user.get("company_ids", [])
    cos = await db.companies.find({"company_id": {"$in": ids}}, {"_id": 0}).to_list(100)
    return {"companies": cos, "active_company_id": user.get("active_company_id")}


@api_router.post("/companies/switch")
async def switch_company(body: CompanySwitch, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    if body.company_id not in user.get("company_ids", []):
        raise HTTPException(status_code=403, detail="Not a member of this company")
    await db.users.update_one({"user_id": user["user_id"]},
                              {"$set": {"active_company_id": body.company_id}})
    await audit(user, "switch", "company", meta={"to": body.company_id})
    return {"active_company_id": body.company_id}


# ------------ Workspaces (multi-role identity) ------------
@api_router.get("/workspaces")
async def list_workspaces(authorization: Optional[str] = Header(None)):
    """Return all workspaces (memberships + company info) for the current user."""
    user = await get_user_from_token(authorization)
    memberships = await db.memberships.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(100)
    company_ids = list({m["company_id"] for m in memberships})
    cos = await db.companies.find({"company_id": {"$in": company_ids}}, {"_id": 0}).to_list(100)
    co_by_id = {c["company_id"]: c for c in cos}
    workspaces = []
    for m in memberships:
        co = co_by_id.get(m["company_id"])
        if not co:
            continue
        workspaces.append({
            "membership_id": m["membership_id"],
            "company_id": m["company_id"],
            "company_name": co["name"],
            "industry": co["industry"],
            "logo_color": co["logo_color"],
            "role": m["role"],
        })
    return {
        "workspaces": workspaces,
        "active_company_id": user.get("active_company_id"),
        "active_role": user.get("active_role"),
    }


@api_router.post("/workspaces/switch")
async def switch_workspace(body: WorkspaceSwitch, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    m = await db.memberships.find_one(
        {"user_id": user["user_id"], "company_id": body.company_id, "role": body.role},
        {"_id": 0},
    )
    if not m:
        raise HTTPException(status_code=403, detail="No matching workspace membership")
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"active_company_id": body.company_id, "active_role": body.role}},
    )
    await audit(user, "switch", "workspace", meta={"company": body.company_id, "role": body.role})
    return {"active_company_id": body.company_id, "active_role": body.role}


# ------------ Admin: User & Role Management ------------
@api_router.get("/admin/users")
async def list_admin_users(
    authorization: Optional[str] = Header(None),
):
    """List all users that share a company with the current user (admin scope per workspace)."""
    user = await get_user_from_token(authorization)
    if user.get("active_role") not in ("owner", "manager") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner or manager required")
    co_id = user.get("active_company_id")
    memberships = await db.memberships.find({"company_id": co_id}, {"_id": 0}).to_list(500)
    user_ids = list({m["user_id"] for m in memberships})
    users = await db.users.find(
        {"user_id": {"$in": user_ids}},
        {"_id": 0, "user_id": 1, "email": 1, "name": 1, "picture": 1},
    ).to_list(500)
    by_user: Dict[str, Any] = {}
    for u in users:
        by_user[u["user_id"]] = {**u, "memberships": []}
    for m in memberships:
        if m["user_id"] in by_user:
            by_user[m["user_id"]]["memberships"].append(
                {"membership_id": m["membership_id"], "role": m["role"], "company_id": m["company_id"]},
            )
    return {"users": list(by_user.values()), "company_id": co_id}


@api_router.post("/admin/users/{user_id}/role")
async def set_user_role(
    user_id: str,
    body: RoleUpdate,
    authorization: Optional[str] = Header(None),
):
    """Update the role of a user's membership in the active company."""
    actor = await get_user_from_token(authorization)
    if actor.get("active_role") != "owner" and actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner role required")
    if body.role not in ("owner", "manager", "employee", "customer"):
        raise HTTPException(status_code=400, detail="Invalid role")
    co_id = actor.get("active_company_id")
    existing = await db.memberships.find_one(
        {"user_id": user_id, "company_id": co_id}, {"_id": 0},
    )
    if existing:
        await db.memberships.update_one(
            {"membership_id": existing["membership_id"]},
            {"$set": {"role": body.role}},
        )
    else:
        await db.memberships.insert_one({
            "membership_id": new_id("mem"),
            "user_id": user_id,
            "company_id": co_id,
            "role": body.role,
            "created_at": now_utc(),
        })
    await audit(actor, "update", "membership",
                meta={"target_user_id": user_id, "role": body.role, "company_id": co_id})
    return {"ok": True, "user_id": user_id, "role": body.role, "company_id": co_id}



# ------------ Modules catalog ------------
@api_router.get("/modules")
async def modules(authorization: Optional[str] = Header(None)):
    await get_user_from_token(authorization)
    return {"catalog": MODULE_CATALOG}


# ------------ Dashboard ------------
@api_router.get("/dashboard")
async def dashboard(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    emp_count = await db.employees.count_documents({"company_id": co_id})
    active_emp = await db.employees.count_documents({"company_id": co_id, "status": "active"})
    open_tickets = await db.tickets.count_documents({"company_id": co_id, "status": {"$in": ["open", "in_progress"]}})
    high_pri = await db.tickets.count_documents({"company_id": co_id, "priority": "high", "status": {"$ne": "closed"}})
    customers = await db.customers.count_documents({"company_id": co_id})
    alerts_unread = await db.alerts.count_documents({"company_id": co_id, "read": False})

    # Pseudo financial KPIs (deterministic from co_id for demo)
    seed = sum(ord(c) for c in (co_id or ""))
    revenue_mtd = 482000 + (seed % 30) * 1500
    payroll_mtd = 138000 + (seed % 20) * 900
    pipeline = 1240000 + (seed % 50) * 3000

    feed = await db.tickets.find({"company_id": co_id}, {"_id": 0}).sort("created_at", -1).limit(6).to_list(6)
    for f in feed:
        f["created_at"] = f["created_at"].isoformat() if isinstance(f.get("created_at"), datetime) else f.get("created_at")

    return {
        "kpis": {
            "revenue_mtd": revenue_mtd,
            "payroll_mtd": payroll_mtd,
            "pipeline": pipeline,
            "employees_total": emp_count,
            "employees_active": active_emp,
            "open_tickets": open_tickets,
            "high_priority_tickets": high_pri,
            "customers": customers,
            "alerts_unread": alerts_unread,
        },
        "feed": feed,
    }


# ------------ HR ------------
@api_router.get("/hr/employees")
async def list_employees(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    emps = await db.employees.find({"company_id": co_id}, {"_id": 0}).to_list(500)
    for e in emps:
        if isinstance(e.get("hired_at"), datetime):
            e["hired_at"] = e["hired_at"].isoformat()
    return {"employees": emps}


@api_router.post("/hr/employees")
async def add_employee(body: EmployeeIn, request: Request, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    if not has_role(user, ["manager", "admin"]):
        raise HTTPException(status_code=403, detail="Requires manager or admin")
    co_id = user.get("active_company_id")
    emp = {
        "employee_id": new_id("emp"),
        "company_id": co_id,
        "name": body.name,
        "role": body.role,
        "department": body.department,
        "email": body.email,
        "status": body.status,
        "hired_at": now_utc(),
    }
    await db.employees.insert_one(emp)
    emp.pop("_id", None)
    emp["hired_at"] = emp["hired_at"].isoformat()
    await audit(user, "create", "employee", request=request, meta={"employee_id": emp["employee_id"], "name": emp["name"]})
    return {"employee": emp}


# ------------ Tickets ------------
@api_router.get("/tickets")
async def list_tickets(status: Optional[str] = None, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    q: Dict[str, Any] = {"company_id": co_id}
    if status and status != "all":
        q["status"] = status
    tks = await db.tickets.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    for t in tks:
        if isinstance(t.get("created_at"), datetime):
            t["created_at"] = t["created_at"].isoformat()
    return {"tickets": tks}


@api_router.post("/tickets")
async def create_ticket(body: TicketIn, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    t = {
        "ticket_id": new_id("tkt"),
        "company_id": co_id,
        "title": body.title,
        "description": body.description,
        "priority": body.priority,
        "status": "open",
        "assignee": body.assignee or user.get("name"),
        "sla_hours": 8,
        "created_at": now_utc(),
    }
    await db.tickets.insert_one(t)
    t.pop("_id", None)
    t["created_at"] = t["created_at"].isoformat()
    await audit(user, "create", "ticket", meta={"ticket_id": t["ticket_id"], "priority": t["priority"]})
    return {"ticket": t}


# ------------ Schedule ------------
@api_router.get("/schedule")
async def schedule_list(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    shifts = await db.shifts.find({"company_id": co_id}, {"_id": 0}).to_list(500)
    return {"shifts": shifts}


# ------------ CRM ------------
@api_router.get("/crm/customers")
async def list_customers(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    cs = await db.customers.find({"company_id": co_id}, {"_id": 0}).to_list(500)
    for c in cs:
        if isinstance(c.get("created_at"), datetime):
            c["created_at"] = c["created_at"].isoformat()
    return {"customers": cs}


# ------------ POS ------------
class SaleIn(BaseModel):
    items: List[Dict[str, Any]]  # [{product_id, qty}]
    tender: str = "card"  # card | cash | etransfer


@api_router.get("/pos/products")
async def list_products(category: Optional[str] = None, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    q: Dict[str, Any] = {"company_id": co_id}
    if category and category != "all":
        q["category"] = category
    prods = await db.products.find(q, {"_id": 0}).to_list(500)
    return {"products": prods}


@api_router.post("/pos/sales")
async def create_sale(body: SaleIn, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    if not body.items:
        raise HTTPException(status_code=400, detail="cart is empty")
    # Resolve product prices
    ids = [it.get("product_id") for it in body.items]
    products = await db.products.find(
        {"company_id": co_id, "product_id": {"$in": ids}}, {"_id": 0},
    ).to_list(200)
    by_id = {p["product_id"]: p for p in products}
    subtotal = 0.0
    line_items = []
    for it in body.items:
        p = by_id.get(it.get("product_id"))
        if not p:
            continue
        qty = max(1, int(it.get("qty", 1)))
        line_total = round(p["price"] * qty, 2)
        subtotal += line_total
        line_items.append({
            "product_id": p["product_id"],
            "name": p["name"],
            "qty": qty,
            "price": p["price"],
            "line_total": line_total,
        })
    if not line_items:
        raise HTTPException(status_code=400, detail="no valid items")
    hst = round(subtotal * 0.13, 2)
    total = round(subtotal + hst, 2)
    sale = {
        "sale_id": new_id("sal"),
        "company_id": co_id,
        "tender": body.tender,
        "subtotal": round(subtotal, 2),
        "hst": hst,
        "total": total,
        "items": line_items,
        "cashier": user.get("name"),
        "created_at": now_utc(),
    }
    await db.sales.insert_one(sale)
    sale.pop("_id", None)
    sale["created_at"] = sale["created_at"].isoformat() if isinstance(sale["created_at"], datetime) else sale["created_at"]
    await audit(user, "create", "sale", meta={"sale_id": sale["sale_id"], "total": sale["total"]})
    return {"sale": sale}


@api_router.get("/pos/sales")
async def list_sales(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    sl = await db.sales.find({"company_id": co_id}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    for s in sl:
        if isinstance(s.get("created_at"), datetime):
            s["created_at"] = s["created_at"].isoformat()
    return {"sales": sl}


# ------------ Payroll T4 ------------
@api_router.get("/payroll/runs")
async def list_pay_runs(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    runs = await db.pay_runs.find({"company_id": co_id}, {"_id": 0}).sort("pay_date", -1).to_list(100)
    return {"runs": runs}


@api_router.get("/payroll/t4/{employee_id}")
async def t4(employee_id: str, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    emp = await db.employees.find_one({"company_id": co_id, "employee_id": employee_id}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="employee not found")
    # Deterministic mock YTD from name
    base = (sum(ord(c) for c in emp["name"]) % 50) * 1200 + 52_400
    ytd_gross = base
    ytd_cpp = round(ytd_gross * 0.0595, 2)
    ytd_ei = round(ytd_gross * 0.0163, 2)
    ytd_tax = round(ytd_gross * 0.21, 2)
    ytd_net = round(ytd_gross - ytd_cpp - ytd_ei - ytd_tax, 2)
    return {
        "employee": emp,
        "tax_year": 2025,
        "boxes": {
            "14_employment_income": ytd_gross,
            "16_cpp_contrib": ytd_cpp,
            "18_ei_premium": ytd_ei,
            "22_income_tax": ytd_tax,
            "net": ytd_net,
        },
        "employer": {"co_id": co_id, "name": "Aidou Command"},
    }


# ------------ Fleet GPS ------------
@api_router.get("/fleet/vehicles")
async def list_vehicles(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    vehs = await db.vehicles.find({"company_id": co_id}, {"_id": 0}).to_list(200)
    # Apply small live drift to mock GPS
    import random
    for v in vehs:
        v["lat"] = round(v["lat"] + random.uniform(-0.0015, 0.0015), 6)
        v["lng"] = round(v["lng"] + random.uniform(-0.0015, 0.0015), 6)
        v["speed_kmh"] = random.randint(0, 95) if v["status"] == "active" else 0
        v["heading"] = random.randint(0, 359)
    return {"vehicles": vehs}


# ------------ Inventory ------------
@api_router.get("/inventory/items")
async def list_inventory(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    items = await db.inventory.find({"company_id": co_id}, {"_id": 0}).to_list(500)
    for it in items:
        if isinstance(it.get("updated_at"), datetime):
            it["updated_at"] = it["updated_at"].isoformat()
    return {"items": items}


@api_router.get("/inventory/lookup")
async def lookup_barcode(barcode: str, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    if not barcode:
        raise HTTPException(status_code=400, detail="barcode required")
    item = await db.inventory.find_one(
        {"company_id": co_id, "barcode": barcode}, {"_id": 0},
    )
    if item and isinstance(item.get("updated_at"), datetime):
        item["updated_at"] = item["updated_at"].isoformat()
    # Also check products
    prod = await db.products.find_one(
        {"company_id": co_id, "barcode": barcode}, {"_id": 0},
    )
    if prod and isinstance(prod.get("created_at"), datetime):
        prod["created_at"] = prod["created_at"].isoformat()
    return {"item": item, "product": prod, "found": bool(item or prod)}


# ------------ Alerts ------------
@api_router.get("/alerts")
async def list_alerts(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    al = await db.alerts.find({"company_id": co_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    for a in al:
        if isinstance(a.get("created_at"), datetime):
            a["created_at"] = a["created_at"].isoformat()
    return {"alerts": al}


@api_router.post("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    await db.alerts.update_one({"alert_id": alert_id, "company_id": co_id}, {"$set": {"read": True}})
    return {"ok": True}


# ------------ AI Command Center ------------
ASSISTANT_SYSTEM_PROMPTS = {
    "hr": "You are Aidou's AI HR Assistant. Help with employee records, recruiting, onboarding, leave, performance reviews, and Canadian employment standards. Be concise and actionable.",
    "accountant": "You are Aidou's AI Accountant. Help with AP/AR, general ledger, HST/GST, payroll taxes, Canadian corporate tax, budgeting and forecasting. Be precise with numbers.",
    "scheduler": "You are Aidou's AI Scheduler. Help with workforce shift planning, attendance, time-off, union seniority rules, and capacity optimization. Be operational.",
    "support": "You are Aidou's AI Customer Support specialist. Help draft replies, summarize tickets, and resolve customer issues with empathy and brevity.",
    "marketing": "You are Aidou's AI Marketing Assistant. Help craft campaigns, social posts, email copy, promotions and review responses. Be on-brand and concise.",
    "analytics": "You are Aidou's AI Analytics Assistant. Help interpret KPIs, build executive summaries, and propose data-driven actions.",
    "advisor": "You are Aidou's AI Business Advisor. Provide strategic advice across HR, finance, ops and compliance for Canadian SMB to enterprise. Be pragmatic and senior in tone.",
}


@api_router.post("/ai/chat")
async def ai_chat(body: ChatRequest, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    assistant = body.assistant if body.assistant in ASSISTANT_SYSTEM_PROMPTS else "advisor"
    system = ASSISTANT_SYSTEM_PROMPTS[assistant]

    # Persist user message
    await db.ai_messages.insert_one({
        "session_id": body.session_id,
        "user_id": user["user_id"],
        "assistant": assistant,
        "role": "user",
        "content": body.message,
        "created_at": now_utc(),
    })

    async def event_generator():
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
        except Exception as e:
            yield f"data: [error] LLM lib unavailable: {e}\n\n"
            return

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"{user['user_id']}:{assistant}:{body.session_id}",
            system_message=system,
        ).with_model("openai", "gpt-5.2")

        # Replay history (last 12 turns) for continuity is handled by LlmChat per session_id

        full_text = ""
        try:
            async for event in chat.stream_message(UserMessage(text=body.message)):
                if isinstance(event, TextDelta):
                    full_text += event.content
                    yield f"data: {event.content}\n\n"
                elif isinstance(event, StreamDone):
                    break
        except Exception as e:
            yield f"data: [error] {str(e)}\n\n"
            return

        # Persist assistant response
        await db.ai_messages.insert_one({
            "session_id": body.session_id,
            "user_id": user["user_id"],
            "assistant": assistant,
            "role": "assistant",
            "content": full_text,
            "created_at": now_utc(),
        })
        yield "data: [done]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@api_router.get("/ai/history")
async def ai_history(session_id: str, assistant: str, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    msgs = await db.ai_messages.find(
        {"session_id": session_id, "assistant": assistant, "user_id": user["user_id"]},
        {"_id": 0},
    ).sort("created_at", 1).to_list(500)
    for m in msgs:
        if isinstance(m.get("created_at"), datetime):
            m["created_at"] = m["created_at"].isoformat()
    return {"messages": msgs}


# ------------ Audit Log (admin only) ------------
@api_router.get("/audit/log")
async def audit_log(
    limit: int = 100,
    request: Request = None,
    user: Dict[str, Any] = Depends(require_role("admin")),
):
    """Return the audit log for the active company (admin only)."""
    co_id = user.get("active_company_id")
    cursor = db.audit_log.find({"company_id": co_id}, {"_id": 0}).sort("created_at", -1).limit(min(500, max(1, limit)))
    entries = await cursor.to_list(500)
    for e in entries:
        if isinstance(e.get("created_at"), datetime):
            e["created_at"] = e["created_at"].isoformat()
    await audit(user, "view", "audit_log", request=request, meta={"limit": limit})
    return {"entries": entries, "count": len(entries)}


# ------------ AI Daily Ops Brief (cached per hour per company, db-backed for multi-worker) ------------
@api_router.get("/ai/ops-brief")
async def ops_brief(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    cache_key = f"ops_brief:{co_id}"
    cached = await db.cache.find_one({"key": cache_key}, {"_id": 0})
    if cached:
        fetched_at = cached.get("fetched_at")
        if isinstance(fetched_at, datetime):
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            if (now_utc() - fetched_at).total_seconds() < 3600:
                return {"brief": cached["brief"], "metrics": cached["metrics"], "cached": True}

    # Aggregate live metrics
    revenue_today = 0.0
    sales = await db.sales.find({"company_id": co_id}, {"_id": 0}).to_list(200)
    today_iso = now_utc().date().isoformat()
    for s in sales:
        created = s.get("created_at")
        if isinstance(created, datetime) and created.date().isoformat() == today_iso:
            revenue_today += float(s.get("total", 0))

    open_tickets = await db.tickets.count_documents({"company_id": co_id, "status": {"$in": ["open", "in_progress"]}})
    high_pri = await db.tickets.count_documents({"company_id": co_id, "priority": "high", "status": {"$ne": "closed"}})
    emps_active = await db.employees.count_documents({"company_id": co_id, "status": "active"})
    vehs = await db.vehicles.find({"company_id": co_id}, {"_id": 0, "status": 1, "fuel_pct": 1}).to_list(50)
    veh_active = sum(1 for v in vehs if v.get("status") == "active")
    low_fuel = sum(1 for v in vehs if v.get("fuel_pct", 100) < 30)
    inv = await db.inventory.find({"company_id": co_id}, {"_id": 0, "stock": 1, "reorder_at": 1}).to_list(500)
    low_stock = sum(1 for it in inv if it.get("stock", 0) <= it.get("reorder_at", 0))
    alerts_unread = await db.alerts.count_documents({"company_id": co_id, "read": False})
    company = await db.companies.find_one({"company_id": co_id}, {"_id": 0})
    co_name = company.get("name") if company else "this company"

    metrics = {
        "company": co_name,
        "date": today_iso,
        "pos_revenue_today": round(revenue_today, 2),
        "open_tickets": open_tickets,
        "high_priority_tickets": high_pri,
        "active_employees": emps_active,
        "fleet_active": veh_active,
        "fleet_total": len(vehs),
        "fleet_low_fuel": low_fuel,
        "inventory_low_stock": low_stock,
        "alerts_unread": alerts_unread,
    }

    prompt = (
        "You are Aidou's AI Business Advisor. Write a single concise paragraph (max 60 words) "
        "as a Daily Ops Brief for an executive opening their app today. Reference the most "
        "important live numbers and end with one specific action recommendation. Do not list bullets. "
        f"Metrics JSON: {json.dumps(metrics)}"
    )

    brief_text = ""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"ops-brief:{co_id}:{today_iso}",
            system_message="You are a senior operations advisor. Be brief and decisive.",
        ).with_model("openai", "gpt-5.2")
        resp = await chat.send_message(UserMessage(text=prompt))
        brief_text = resp if isinstance(resp, str) else getattr(resp, "content", str(resp))
    except Exception as e:
        logger.warning(f"ops_brief LLM failed: {e}")
        brief_text = (
            f"{co_name} has {open_tickets} open tickets ({high_pri} high priority), "
            f"{veh_active}/{len(vehs)} vehicles active, {low_stock} items below reorder, "
            f"and {alerts_unread} unread alerts. Recommend triaging the high-priority tickets first."
        )

    await db.cache.update_one(
        {"key": cache_key},
        {"$set": {
            "key": cache_key,
            "brief": brief_text,
            "metrics": metrics,
            "fetched_at": now_utc(),
        }},
        upsert=True,
    )
    return {"brief": brief_text, "metrics": metrics, "cached": False}


# ------------ Root ------------
@api_router.get("/")
async def root():
    return {"app": "Aidou Command Enterprise Ultimate", "status": "ok", "time": now_utc().isoformat()}


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
