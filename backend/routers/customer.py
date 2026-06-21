"""Customer-facing endpoints: orders, invoices, appointments."""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Header

from core.db import db
from core.deps import get_user_from_token, audit, now_utc, new_id
from core.models import AppointmentIn

router = APIRouter()


@router.get("/customer/orders")
async def customer_orders(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
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


@router.get("/customer/invoices")
async def customer_invoices(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
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


@router.get("/customer/appointments")
async def customer_appointments(authorization: Optional[str] = Header(None)):
    user = await get_user_from_token(authorization)
    appts = await db.appointments.find(
        {"customer_user_id": user["user_id"]}, {"_id": 0},
    ).sort("when", 1).to_list(50)
    for a in appts:
        if isinstance(a.get("when"), datetime):
            a["when"] = a["when"].isoformat()
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


@router.post("/customer/appointments")
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
