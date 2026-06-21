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

from core.deps import (
    has_role,
    require_role,
    audit,
    now_utc,
    new_id,
    get_user_from_token,
)  # noqa: F401

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")


def _send_magic_link_email(to_email: str, name: str, company_name: str, role: str, magic_link: str) -> Dict[str, Any]:
    """Send a magic-link invite via SendGrid. Returns {sent: bool, reason?: str}."""
    if not SENDGRID_API_KEY or not SENDER_EMAIL:
        return {"sent": False, "reason": "SENDGRID_API_KEY or SENDER_EMAIL not configured"}
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        html = f"""
        <div style=\"font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:#0F0F12; color:#F8F9FA; padding:32px; max-width:560px; margin:0 auto;\">
          <div style=\"font-size:11px; letter-spacing:3px; color:#E25822; font-weight:800;\">AIDOU COMMAND</div>
          <h1 style=\"font-size:24px; margin:8px 0 4px;\">You're invited, {name}.</h1>
          <p style=\"color:#A1A1AA; font-size:14px; line-height:20px;\">
            You've been granted access to <strong style=\"color:#F8F9FA;\">{company_name}</strong> as
            <strong style=\"color:#E25822;\">{role.upper()}</strong> on Aidou Command Enterprise Ultimate.
          </p>
          <a href=\"{magic_link}\" style=\"display:inline-block; margin-top:24px; background:#E25822; color:#fff; padding:14px 22px; border-radius:8px; text-decoration:none; font-weight:800; letter-spacing:0.5px;\">Accept invitation →</a>
          <p style=\"color:#6B7280; font-size:11px; margin-top:28px;\">If you weren't expecting this email, just ignore it. The link is single-use and expires in 7 days.</p>
        </div>
        """
        msg = Mail(
            from_email=SENDER_EMAIL,
            to_emails=to_email,
            subject=f"You're invited to Aidou Command — {company_name}",
            html_content=html,
        )
        sg_client = SendGridAPIClient(SENDGRID_API_KEY)
        resp = sg_client.send(msg)
        return {"sent": 200 <= resp.status_code < 300, "status": resp.status_code}
    except Exception as e:  # pragma: no cover — best-effort; never break the invite endpoint
        logger.warning(f"SendGrid send failed: {e}")
        return {"sent": False, "reason": str(e)}
app = FastAPI(title="Aidou Command API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ------------ Helpers ------------
# now_utc, new_id, get_user_from_token are imported from core.deps (single source of truth).


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


class TimeclockPunch(BaseModel):
    note: Optional[str] = None


class AppointmentIn(BaseModel):
    title: str
    when_iso: str
    location: Optional[str] = None


class InviteIn(BaseModel):
    email: str
    name: Optional[str] = None
    role: str  # owner | manager | employee | customer


class ReferralIn(BaseModel):
    target_company_id: str
    note: Optional[str] = None


class ReferralFulfill(BaseModel):
    booking_value: float


class CashAdvanceRequest(BaseModel):
    amount: float


class UnderwritingPolicy(BaseModel):
    pos_revenue_ltv: float = 0.15
    payroll_ltv: float = 0.05
    payout_projection_ltv: float = 0.80
    free_band_cap: float = 1000.0
    fee_above_free: float = 0.045
    floor: float = 1000.0


# Default underwriting policy (used when db.underwriting_policy is empty)
DEFAULT_POLICY: Dict[str, float] = UnderwritingPolicy().model_dump()


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
            # Marketplace partner companies — seeded so referral-fulfilled flow has real targets.
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
    target_exists = await db.users.find_one({"user_id": user_id}, {"_id": 0, "user_id": 1})
    if not target_exists:
        raise HTTPException(status_code=404, detail="Target user not found")
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


# ------------ Employee: Time Clock ------------
@api_router.post("/timeclock/punch")
async def timeclock_punch(body: TimeclockPunch, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    # Find open punch (no clock_out)
    open_punch = await db.timeclock.find_one(
        {"user_id": user["user_id"], "company_id": co_id, "clock_out": None},
        {"_id": 0},
    )
    if open_punch:
        end = now_utc()
        start = open_punch["clock_in"]
        if isinstance(start, datetime) and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        minutes = int((end - start).total_seconds() / 60)
        await db.timeclock.update_one(
            {"punch_id": open_punch["punch_id"]},
            {"$set": {"clock_out": end, "minutes": minutes}},
        )
        await audit(user, "punch_out", "timeclock", meta={"minutes": minutes})
        return {"action": "clock_out", "minutes": minutes, "punch_id": open_punch["punch_id"]}
    # New punch
    p = {
        "punch_id": new_id("pch"),
        "user_id": user["user_id"],
        "company_id": co_id,
        "user_name": user.get("name"),
        "clock_in": now_utc(),
        "clock_out": None,
        "minutes": 0,
        "note": body.note,
    }
    await db.timeclock.insert_one(p)
    p.pop("_id", None)
    p["clock_in"] = p["clock_in"].isoformat()
    await audit(user, "punch_in", "timeclock")
    return {"action": "clock_in", "punch": p}


@api_router.get("/timeclock/me")
async def timeclock_me(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    today_start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    punches = await db.timeclock.find(
        {"user_id": user["user_id"], "company_id": co_id, "clock_in": {"$gte": today_start}},
        {"_id": 0},
    ).sort("clock_in", -1).to_list(50)
    open_p = None
    minutes_today = 0
    for p in punches:
        if isinstance(p.get("clock_in"), datetime):
            p["clock_in"] = p["clock_in"].isoformat()
        if isinstance(p.get("clock_out"), datetime):
            p["clock_out"] = p["clock_out"].isoformat()
        if p.get("clock_out") is None and not open_p:
            open_p = p
        else:
            minutes_today += int(p.get("minutes", 0))
    # Add running minutes if punch is open
    if open_p:
        start = datetime.fromisoformat(open_p["clock_in"].replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        minutes_today += int((now_utc() - start).total_seconds() / 60)
    return {"punches": punches, "open_punch": open_p, "minutes_today": minutes_today}


# ------------ Customer: Orders / Invoices / Appointments ------------
@api_router.get("/customer/orders")
async def customer_orders(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    # All sales across user's customer-memberships represent their orders from those businesses.
    customer_mems = await db.memberships.find(
        {"user_id": user["user_id"], "role": "customer"}, {"_id": 0},
    ).to_list(100)
    if not customer_mems:
        return {"orders": []}
    co_ids = [m["company_id"] for m in customer_mems]
    sales = await db.sales.find(
        {"company_id": {"$in": co_ids}}, {"_id": 0},
    ).sort("created_at", -1).limit(40).to_list(40)
    cos = await db.companies.find({"company_id": {"$in": co_ids}}, {"_id": 0}).to_list(100)
    co_by_id = {c["company_id"]: c for c in cos}
    for s in sales:
        if isinstance(s.get("created_at"), datetime):
            s["created_at"] = s["created_at"].isoformat()
        s["company_name"] = co_by_id.get(s.get("company_id"), {}).get("name", "Business")
    return {"orders": sales}


@api_router.get("/customer/invoices")
async def customer_invoices(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    # Derived from sales — deterministic mock invoices with paid/due/overdue status
    customer_mems = await db.memberships.find(
        {"user_id": user["user_id"], "role": "customer"}, {"_id": 0},
    ).to_list(100)
    co_ids = [m["company_id"] for m in customer_mems]
    sales = await db.sales.find(
        {"company_id": {"$in": co_ids}}, {"_id": 0},
    ).sort("created_at", -1).limit(20).to_list(20)
    cos = await db.companies.find({"company_id": {"$in": co_ids}}, {"_id": 0}).to_list(100)
    co_by_id = {c["company_id"]: c for c in cos}
    invoices = []
    for i, s in enumerate(sales):
        created = s.get("created_at")
        if isinstance(created, datetime):
            iso = created.isoformat()
        else:
            iso = created
        status = "paid" if i % 3 != 0 else ("due" if i % 2 == 0 else "overdue")
        invoices.append({
            "invoice_id": f"inv_{s['sale_id'].split('_')[1]}",
            "company_id": s["company_id"],
            "company_name": co_by_id.get(s["company_id"], {}).get("name", "Business"),
            "amount": s.get("total", 0),
            "status": status,
            "issued_at": iso,
            "items_count": len(s.get("items", [])),
        })
    return {"invoices": invoices}


@api_router.get("/customer/appointments")
async def customer_appointments(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    appts = await db.appointments.find(
        {"customer_user_id": user["user_id"]}, {"_id": 0},
    ).sort("when", 1).to_list(50)
    for a in appts:
        if isinstance(a.get("when"), datetime):
            a["when"] = a["when"].isoformat()
    # Seed if empty
    if not appts:
        customer_mems = await db.memberships.find(
            {"user_id": user["user_id"], "role": "customer"}, {"_id": 0},
        ).to_list(10)
        if customer_mems:
            seed = []
            for i, m in enumerate(customer_mems):
                co = await db.companies.find_one({"company_id": m["company_id"]}, {"_id": 0})
                seed.append({
                    "appointment_id": new_id("apt"),
                    "customer_user_id": user["user_id"],
                    "company_id": m["company_id"],
                    "company_name": co["name"] if co else "Business",
                    "title": ["Service install", "Quarterly review", "On-site inspection"][i % 3],
                    "when": now_utc() + timedelta(days=i + 1),
                    "location": ["88 Maple Ave", "Remote", "Customer site"][i % 3],
                    "status": "confirmed",
                })
            await db.appointments.insert_many(seed)
            for s in seed:
                s["when"] = s["when"].isoformat()
                s.pop("_id", None)
            appts = seed
    return {"appointments": appts}


@api_router.post("/customer/appointments")
async def create_appointment(body: AppointmentIn, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    co_id = user.get("active_company_id")
    co = await db.companies.find_one({"company_id": co_id}, {"_id": 0})
    appt = {
        "appointment_id": new_id("apt"),
        "customer_user_id": user["user_id"],
        "company_id": co_id,
        "company_name": co["name"] if co else "Business",
        "title": body.title,
        "when": datetime.fromisoformat(body.when_iso.replace("Z", "+00:00")),
        "location": body.location,
        "status": "requested",
    }
    await db.appointments.insert_one(appt)
    appt.pop("_id", None)
    appt["when"] = appt["when"].isoformat()
    await audit(user, "create", "appointment", meta={"company_id": co_id})
    return {"appointment": appt}


# ------------ Admin: Invite (create user + membership) ------------
@api_router.post("/admin/users/invite")
async def admin_invite(body: InviteIn, authorization: Optional[str] = Header(None)):
    actor = await get_user_from_token(authorization)
    if actor.get("active_role") != "owner" and actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner role required")
    if body.role not in ("owner", "manager", "employee", "customer"):
        raise HTTPException(status_code=400, detail="Invalid role")
    co_id = actor.get("active_company_id")
    # Find or create the user
    existing = await db.users.find_one({"email": body.email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
    else:
        user_id = new_id("user")
        await db.users.insert_one({
            "user_id": user_id,
            "email": body.email,
            "name": body.name or body.email.split("@")[0].replace(".", " ").title(),
            "picture": "",
            "company_ids": [co_id],
            "active_company_id": co_id,
            "role": "member",
            "created_at": now_utc(),
            "invited_by": actor["user_id"],
        })
    # Upsert membership
    m = await db.memberships.find_one(
        {"user_id": user_id, "company_id": co_id, "role": body.role}, {"_id": 0},
    )
    if not m:
        await db.memberships.insert_one({
            "membership_id": new_id("mem"),
            "user_id": user_id,
            "company_id": co_id,
            "role": body.role,
            "invited_by": actor["user_id"],
            "created_at": now_utc(),
        })
    # Send invite email via SendGrid (graceful no-op when keys aren't set)
    co = await db.companies.find_one({"company_id": co_id}, {"_id": 0})
    company_name = co["name"] if co else "your workspace"
    invitee_name = body.name or body.email.split("@")[0].replace(".", " ").title()
    magic_link = f"https://aidou.app/invite/{user_id}?co={co_id}&role={body.role}"
    email_result = _send_magic_link_email(body.email, invitee_name, company_name, body.role, magic_link)
    await audit(actor, "invite", "user", meta={"email": body.email, "role": body.role, "company_id": co_id, "email_sent": email_result.get("sent", False)})
    return {
        "ok": True,
        "user_id": user_id,
        "company_id": co_id,
        "role": body.role,
        "magic_link": magic_link,
        "email_sent": email_result.get("sent", False),
        "email_reason": email_result.get("reason"),
        "note": "Magic-link email delivery via SendGrid — falls back to MOCKED when keys aren't configured",
    }


# ------------ Marketplace (cross-sell + referrals) ------------
@api_router.get("/marketplace/businesses")
async def marketplace_businesses(authorization: Optional[str] = Header(None)):
    """Industry-affinity-ranked list of Aidou-powered businesses the user can hire."""
    user = await get_user_from_token(authorization)
    customer_mems = await db.memberships.find(
        {"user_id": user["user_id"], "role": "customer"}, {"_id": 0},
    ).to_list(100)
    customer_co_ids = {m["company_id"] for m in customer_mems}

    # The user's affinity bag = industries of companies they're already a member of (any role).
    all_user_mems = await db.memberships.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(200)
    user_co_ids = {m["company_id"] for m in all_user_mems}
    user_industries: Dict[str, int] = {}
    if user_co_ids:
        cos_user = await db.companies.find({"company_id": {"$in": list(user_co_ids)}}, {"_id": 0}).to_list(200)
        for c in cos_user:
            ind = c.get("industry", "Other")
            user_industries[ind] = user_industries.get(ind, 0) + 1

    all_cos = await db.companies.find({}, {"_id": 0}).to_list(500)
    seen_ids = {c["company_id"] for c in all_cos}
    extras_raw = [
        {"company_id": "mp_ridgeline_logistics", "name": "RidgeLine Logistics", "industry": "Transportation",
         "logo_color": "#3B82F6", "rating": 4.7, "specialty": "Same-day freight", "min_price": "$80/run"},
        {"company_id": "mp_acadia_medical", "name": "Acadia Medical Group", "industry": "Healthcare",
         "logo_color": "#10B981", "rating": 4.9, "specialty": "Workplace clinics", "min_price": "$240/visit"},
        {"company_id": "mp_pinewood_school", "name": "Pinewood Training Studio", "industry": "Education",
         "logo_color": "#F59E0B", "rating": 4.6, "specialty": "Safety certifications", "min_price": "$95/seat"},
    ]
    # Drop any partner that's already in db.companies — prevents duplicates after backfill.
    extras = [e for e in extras_raw if e["company_id"] not in seen_ids]
    enriched = [
        {**c, "rating": 4.6, "specialty": f"{c.get('industry', 'Pro')} services",
         "min_price": "Custom quote", "is_member": c["company_id"] in customer_co_ids}
        for c in all_cos
    ] + extras

    def score(b: Dict[str, Any]) -> float:
        s = (b.get("rating", 4.0)) * 10.0
        # Industry affinity boost (clamped)
        ind = b.get("industry", "")
        affinity = user_industries.get(ind, 0)
        s += min(affinity, 3) * 8.0
        # New-to-user discovery boost
        if b.get("company_id") not in user_co_ids:
            s += 12.0
        # Marketplace partners get a small surfacing nudge
        if b.get("company_id", "").startswith("mp_"):
            s += 6.0
        return round(s, 2)

    for b in enriched:
        b["score"] = score(b)
        b["recommended"] = b["score"] >= 60.0 and b["company_id"] not in user_co_ids
        b["match_reason"] = (
            f"Matches your {b['industry']} industry footprint"
            if user_industries.get(b.get("industry", "")) and b["company_id"] not in user_co_ids
            else ("New on the platform" if b.get("company_id", "").startswith("mp_") else "Top-rated")
        )

    enriched.sort(key=lambda x: x["score"], reverse=True)
    return {"businesses": enriched, "user_industries": user_industries}


@api_router.post("/marketplace/referrals/{referral_id}/fulfill")
async def fulfill_referral(referral_id: str, body: ReferralFulfill, authorization: Optional[str] = Header(None)):
    """Mark a referral as fulfilled and compute the platform payout (5% revenue share)."""
    actor = await get_user_from_token(authorization)
    if actor.get("active_role") not in ("owner", "manager") and actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner/manager required to fulfill referrals")
    ref = await db.referrals.find_one({"referral_id": referral_id}, {"_id": 0})
    if not ref:
        raise HTTPException(status_code=404, detail="Referral not found")
    if ref.get("status") == "fulfilled":
        return {"referral": ref, "note": "already fulfilled"}
    if body.booking_value <= 0:
        raise HTTPException(status_code=400, detail="booking_value must be positive")
    payout = round(body.booking_value * (ref.get("share_percent", 5.0) / 100.0), 2)
    await db.referrals.update_one(
        {"referral_id": referral_id},
        {"$set": {
            "status": "fulfilled",
            "booking_value": body.booking_value,
            "estimated_payout": payout,
            "fulfilled_at": now_utc(),
            "fulfilled_by": actor["user_id"],
        }},
    )
    # Persist a payout record for billing/finance reconciliation
    await db.payouts.insert_one({
        "payout_id": new_id("pay"),
        "referral_id": referral_id,
        "amount": payout,
        "source_company_id": ref.get("source_company_id"),
        "target_company_id": ref.get("target_company_id"),
        "status": "pending_disbursement",
        "created_at": now_utc(),
    })
    await audit(actor, "fulfill", "referral", meta={"referral_id": referral_id, "payout": payout})
    fresh = await db.referrals.find_one({"referral_id": referral_id}, {"_id": 0})
    if isinstance(fresh.get("created_at"), datetime):
        fresh["created_at"] = fresh["created_at"].isoformat()
    if isinstance(fresh.get("fulfilled_at"), datetime):
        fresh["fulfilled_at"] = fresh["fulfilled_at"].isoformat()
    return {"referral": fresh, "payout": payout}


@api_router.get("/marketplace/payouts")
async def list_payouts(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    if user.get("active_role") not in ("owner", "manager") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner/manager required")
    co_id = user.get("active_company_id")
    rows = await db.payouts.find(
        {"$or": [{"source_company_id": co_id}, {"target_company_id": co_id}]}, {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
    total_pending = sum(r["amount"] for r in rows if r.get("status") == "pending_disbursement")
    return {"payouts": rows, "total_pending": round(total_pending, 2)}


# ------------ Workspace Trust Signals ------------
@api_router.get("/workspaces/stats")
async def workspace_stats(authorization: Optional[str] = Header(None)):
    """Per-workspace KPIs powering the trust-signal badges on the Workspace Selector."""
    user = await get_user_from_token(authorization)
    memberships = await db.memberships.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(100)
    stats: Dict[str, Dict[str, Any]] = {}
    for m in memberships:
        co_id = m["company_id"]
        role = m["role"]
        key = f"{co_id}:{role}"
        if role in ("owner", "manager"):
            emp_count = await db.employees.count_documents({"company_id": co_id, "status": "active"})
            # Sum of recent pay runs as proxy for YTD payroll (deterministic from seed)
            runs = await db.pay_runs.find({"company_id": co_id}, {"_id": 0, "gross": 1}).to_list(50)
            payroll_ytd = sum(r.get("gross", 0) for r in runs)
            stats[key] = {
                "headline": f"{emp_count} employees",
                "metric": f"${(payroll_ytd / 1000):.1f}K payroll YTD",
                "tone": "ops",
            }
        elif role == "employee":
            punches = await db.timeclock.find(
                {"user_id": user["user_id"], "company_id": co_id}, {"_id": 0, "minutes": 1},
            ).to_list(500)
            hours = sum(p.get("minutes", 0) for p in punches) / 60.0
            shifts = await db.shifts.count_documents({"company_id": co_id})
            stats[key] = {
                "headline": f"{hours:.1f}h logged this period",
                "metric": f"{shifts} shifts in rotation",
                "tone": "work",
            }
        else:  # customer
            sales = await db.sales.count_documents({"company_id": co_id})
            apts = await db.appointments.count_documents({"customer_user_id": user["user_id"], "company_id": co_id})
            stats[key] = {
                "headline": f"{sales} invoices on file",
                "metric": f"{apts} upcoming appointments",
                "tone": "customer",
            }
    return {"stats": stats}


# ------------ Aidou Cash Advance (Square Capital-style) ------------
@api_router.get("/cash-advance/offer")
async def cash_advance_offer(authorization: Optional[str] = Header(None)):
    """Compute a real-time advance offer using POS sales + payroll + referral payout signals."""
    user = await get_user_from_token(authorization)
    if user.get("active_role") != "owner" and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner only")
    co_id = user.get("active_company_id")

    # Underwriting signals
    sales_total = 0.0
    sales = await db.sales.find({"company_id": co_id}, {"_id": 0, "total": 1}).to_list(500)
    sales_total = sum(float(s.get("total", 0)) for s in sales)
    pay_runs = await db.pay_runs.find({"company_id": co_id}, {"_id": 0, "gross": 1}).to_list(50)
    payroll_total = sum(r.get("gross", 0) for r in pay_runs)
    payouts = await db.payouts.find(
        {"target_company_id": co_id}, {"_id": 0, "amount": 1, "status": 1},
    ).to_list(500)
    payout_inflow = sum(p.get("amount", 0) for p in payouts)

    # Projected next-30d referral payouts = trailing average × 1.0
    projected_payouts_30d = round(payout_inflow * 0.5, 2)
    # Load policy (db.underwriting_policy.global or default)
    policy_doc = await db.underwriting_policy.find_one({"key": "global"}, {"_id": 0}) or {}
    policy = {**DEFAULT_POLICY, **{k: v for k, v in policy_doc.items() if k in DEFAULT_POLICY}}
    revenue_cap = max(sales_total * policy["pos_revenue_ltv"], payroll_total * policy["payroll_ltv"])
    raw_cap = max(projected_payouts_30d * policy["payout_projection_ltv"], revenue_cap)
    max_advance = round(max(policy["floor"], raw_cap), 2)

    # Status: eligible if any of (sales, payroll, payouts) is non-zero
    eligible = (sales_total + payroll_total + payout_inflow) > 0

    # Outstanding advance (if any)
    open_adv = await db.cash_advances.find_one(
        {"company_id": co_id, "status": "outstanding"}, {"_id": 0},
    )
    if open_adv and isinstance(open_adv.get("created_at"), datetime):
        open_adv["created_at"] = open_adv["created_at"].isoformat()

    return {
        "eligible": eligible,
        "max_advance": max_advance,
        "rate_first_1k": 0.0,
        "rate_above_1k": 4.5,
        "underwriting_signals": {
            "pos_revenue_lifetime": round(sales_total, 2),
            "payroll_lifetime": round(payroll_total, 2),
            "referral_inflow_lifetime": round(payout_inflow, 2),
            "projected_payouts_30d": projected_payouts_30d,
        },
        "open_advance": open_adv,
        "tagline": "0% fee on your first $1,000 · funded in 24h · auto-repaid from future payouts",
    }


@api_router.post("/cash-advance/request")
async def request_cash_advance(body: CashAdvanceRequest, authorization: Optional[str] = Header(None)):
    actor = await get_user_from_token(authorization)
    if actor.get("active_role") != "owner" and actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner only")
    co_id = actor.get("active_company_id")
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    # Recompute offer to enforce cap
    offer = await cash_advance_offer(authorization)
    if body.amount > offer["max_advance"]:
        raise HTTPException(status_code=400, detail=f"Amount exceeds approved max ${offer['max_advance']:.2f}")
    if offer.get("open_advance"):
        raise HTTPException(status_code=409, detail="An outstanding advance already exists")
    # Pull live policy for fee schedule (free_band_cap + fee_above_free)
    policy_doc = await db.underwriting_policy.find_one({"key": "global"}, {"_id": 0}) or {}
    free_cap = float(policy_doc.get("free_band_cap", DEFAULT_POLICY["free_band_cap"]))
    fee_rate = float(policy_doc.get("fee_above_free", DEFAULT_POLICY["fee_above_free"]))
    fee = 0.0 if body.amount <= free_cap else round((body.amount - free_cap) * fee_rate, 2)
    adv = {
        "advance_id": new_id("adv"),
        "company_id": co_id,
        "requested_by": actor["user_id"],
        "amount": round(body.amount, 2),
        "fee": fee,
        "total_repayable": round(body.amount + fee, 2),
        "status": "outstanding",
        "created_at": now_utc(),
        "expected_repayment_source": "future_referral_payouts",
    }
    await db.cash_advances.insert_one(adv)
    adv.pop("_id", None)
    adv["created_at"] = adv["created_at"].isoformat()
    await audit(actor, "request", "cash_advance", meta={"amount": adv["amount"], "fee": fee})
    return {"advance": adv, "note": "Funds will land in your linked account within 24h. MOCKED — banking rails not yet integrated."}


@api_router.get("/cash-advance/history")
async def cash_advance_history(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    if user.get("active_role") != "owner" and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner only")
    co_id = user.get("active_company_id")
    rows = await db.cash_advances.find({"company_id": co_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
    return {"advances": rows}


@api_router.get("/cash-advance/repayment-schedule")
async def repayment_schedule(authorization: Optional[str] = Header(None)):
    """CRA-style preview of how future referral payouts will repay an outstanding advance."""
    user = await get_user_from_token(authorization)
    if user.get("active_role") != "owner" and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner only")
    co_id = user.get("active_company_id")
    adv = await db.cash_advances.find_one({"company_id": co_id, "status": "outstanding"}, {"_id": 0})
    if not adv:
        return {"has_advance": False, "schedule": [], "outstanding": 0.0, "covered_in_weeks": 0}
    payouts = await db.payouts.find({"target_company_id": co_id}, {"_id": 0, "amount": 1}).to_list(500)
    lifetime = sum(p.get("amount", 0) for p in payouts)
    weekly = max(lifetime / 12.0, adv["total_repayable"] / 8.0)
    schedule = []
    remaining = adv["total_repayable"]
    week = 0
    while remaining > 0.01 and week < 26:
        week += 1
        applied = round(min(weekly, remaining), 2)
        remaining = round(remaining - applied, 2)
        schedule.append({
            "week": week,
            "date": (now_utc() + timedelta(weeks=week)).date().isoformat(),
            "expected_inflow": round(weekly, 2),
            "applied_to_advance": applied,
            "remaining": remaining,
        })
    return {
        "has_advance": True,
        "advance_id": adv["advance_id"],
        "outstanding": adv["total_repayable"],
        "weekly_estimate": round(weekly, 2),
        "schedule": schedule,
        "covered_in_weeks": len(schedule),
    }


@api_router.get("/underwriting/policy")
async def get_policy(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    if user.get("active_role") != "owner" and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner only")
    doc = await db.underwriting_policy.find_one({"key": "global"}, {"_id": 0}) or {}
    return {"policy": {**DEFAULT_POLICY, **{k: v for k, v in doc.items() if k in DEFAULT_POLICY}}}


@api_router.put("/underwriting/policy")
async def put_policy(body: UnderwritingPolicy, authorization: Optional[str] = Header(None)):
    actor = await get_user_from_token(authorization)
    if actor.get("active_role") != "owner" and actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner only")
    payload = body.model_dump()
    await db.underwriting_policy.update_one(
        {"key": "global"},
        {"$set": {"key": "global", **payload, "updated_by": actor["user_id"], "updated_at": now_utc()}},
        upsert=True,
    )
    await audit(actor, "update", "underwriting_policy", meta=payload)
    return {"policy": payload}


@api_router.get("/credit-score")
async def credit_score(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    if user.get("active_role") not in ("owner", "manager") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Owner/manager required")
    co_id = user.get("active_company_id")
    sales = await db.sales.find({"company_id": co_id}, {"_id": 0, "total": 1}).to_list(500)
    sales_total = sum(float(s.get("total", 0)) for s in sales)
    pay_runs = await db.pay_runs.find({"company_id": co_id}, {"_id": 0, "gross": 1, "status": 1}).to_list(50)
    payroll_total = sum(r.get("gross", 0) for r in pay_runs)
    posted_runs = sum(1 for r in pay_runs if r.get("status") == "posted")
    payouts = await db.payouts.find({"target_company_id": co_id}, {"_id": 0, "amount": 1}).to_list(500)
    payout_total = sum(p.get("amount", 0) for p in payouts)
    advances = await db.cash_advances.find({"company_id": co_id}, {"_id": 0, "status": 1}).to_list(50)
    repaid = sum(1 for a in advances if a.get("status") == "repaid")
    outstanding = sum(1 for a in advances if a.get("status") == "outstanding")
    employees = await db.employees.count_documents({"company_id": co_id})
    tickets_open = await db.tickets.count_documents({"company_id": co_id, "status": {"$in": ["open", "in_progress"]}})

    pos_score = min(300, int(sales_total / 1000))
    payroll_score = min(200, int(payroll_total / 5000))
    consistency = min(150, posted_runs * 25)
    referral_score = min(150, int(payout_total / 10))
    repayment_score = min(120, repaid * 60)
    team_score = min(50, int(employees * 4))
    ops_penalty = min(50, tickets_open * 3)
    base = 100
    raw = base + pos_score + payroll_score + consistency + referral_score + repayment_score + team_score - ops_penalty
    score = max(0, min(1000, int(raw)))

    band, tone = (
        ("Exceptional", "success") if score >= 850 else
        ("Excellent", "success") if score >= 700 else
        ("Good", "ops") if score >= 550 else
        ("Fair", "warning") if score >= 400 else
        ("Building", "info")
    )

    nudges: List[Dict[str, str]] = []
    if posted_runs < 4:
        nudges.append({"text": "Post 3 more pay runs to unlock consistency boost", "delta": "+75"})
    if payout_total < 100:
        nudges.append({"text": "Fulfill marketplace referrals to add referral inflow signal", "delta": "+50"})
    if employees < 10:
        nudges.append({"text": "Add 4 more employees on the HR module", "delta": "+16"})
    if outstanding == 0 and repaid == 0:
        nudges.append({"text": "Take and repay a $1k Cash Advance to build repayment history", "delta": "+60"})
    if tickets_open > 8:
        nudges.append({"text": f"Resolve {tickets_open - 5} open tickets to lift the ops penalty", "delta": "+15"})

    perks = [p for p in [
        "Lower Cash Advance fee tiers" if score >= 700 else None,
        "Faster invoice factoring" if score >= 800 else None,
        "B2B credit line unlocked" if score >= 850 else None,
        "Marketplace verified badge" if score >= 600 else None,
    ] if p]

    return {
        "score": score,
        "band": band,
        "tone": tone,
        "breakdown": {
            "pos_revenue": pos_score,
            "payroll": payroll_score,
            "consistency": consistency,
            "referrals": referral_score,
            "repayment_history": repayment_score,
            "team_size": team_score,
            "ops_penalty": -ops_penalty,
            "baseline": base,
        },
        "nudges": nudges,
        "perks": perks,
        "headline": f"Aidou Network Score · {band} ({score}/1000)",
    }






@api_router.post("/marketplace/referrals")
async def create_referral(body: ReferralIn, authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    source_co = user.get("active_company_id")
    # Revenue-share record (5% of estimated booking value as placeholder)
    ref = {
        "referral_id": new_id("ref"),
        "source_user_id": user["user_id"],
        "source_company_id": source_co,
        "target_company_id": body.target_company_id,
        "note": body.note,
        "status": "pending",
        "share_percent": 5.0,
        "estimated_payout": 0.0,
        "created_at": now_utc(),
    }
    await db.referrals.insert_one(ref)
    ref.pop("_id", None)
    ref["created_at"] = ref["created_at"].isoformat()
    await audit(user, "create", "referral", meta={"target": body.target_company_id})
    return {"referral": ref}


@api_router.get("/marketplace/referrals")
async def list_referrals(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    refs = await db.referrals.find(
        {"source_user_id": user["user_id"]}, {"_id": 0},
    ).sort("created_at", -1).limit(50).to_list(50)
    for r in refs:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
    return {"referrals": refs}


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
