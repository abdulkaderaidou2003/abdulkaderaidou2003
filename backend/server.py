"""Aidou Command Enterprise Ultimate - Backend API (thin app bootstrap).

All endpoints live in /app/backend/routers/*.py.
Shared infra (db, deps, models, scoring, seed) lives in /app/backend/core/.
"""
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

# Load env early so core.db can read MONGO_URL / DB_NAME / EMERGENT_LLM_KEY / SENDGRID_*.
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from core.db import client  # noqa: E402
from core.seed import run_startup_seed  # noqa: E402

from routers import (  # noqa: E402
    auth,
    companies,
    workspaces,
    admin_users,
    modules,
    dashboard,
    hr,
    tickets,
    schedule,
    crm,
    pos,
    payroll,
    fleet,
    inventory,
    alerts,
    ai,
    audit_log,
    timeclock,
    customer,
    marketplace,
    cash_advance,
    underwriting,
    root,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Aidou Command API")

# Register all routers under /api prefix.
for r in (
    auth.router,
    companies.router,
    workspaces.router,
    admin_users.router,
    modules.router,
    dashboard.router,
    hr.router,
    tickets.router,
    schedule.router,
    crm.router,
    pos.router,
    payroll.router,
    fleet.router,
    inventory.router,
    alerts.router,
    ai.router,
    audit_log.router,
    timeclock.router,
    customer.router,
    marketplace.router,
    cash_advance.router,
    underwriting.router,
    root.router,
):
    app.include_router(r, prefix="/api")


@app.on_event("startup")
async def startup():
    await run_startup_seed()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
