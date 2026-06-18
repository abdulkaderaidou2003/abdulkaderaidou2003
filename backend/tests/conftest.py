"""Shared fixtures for Aidou Command backend tests."""
import os
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

# Load backend env for Mongo access
load_dotenv(Path("/app/backend/.env"))

_url = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://enterprise-ops-hub-12.preview.emergentagent.com"
)
BASE_URL = _url.rstrip("/")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def mongo():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def seeded_user(mongo):
    """Insert a real user + session directly into Mongo and yield bearer token."""
    user_id = f"user_{secrets.token_hex(6)}"
    token = f"TEST_{secrets.token_hex(16)}"
    mongo.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "email": f"TEST_{user_id}@example.com",
            "name": "TEST User",
            "picture": "",
            "company_ids": ["co_aidou_corp", "co_northstar_isp", "co_summit_construction"],
            "active_company_id": "co_aidou_corp",
            "role": "admin",
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
    # Cleanup
    mongo.user_sessions.delete_many({"user_id": user_id})
    mongo.users.delete_many({"user_id": user_id})
