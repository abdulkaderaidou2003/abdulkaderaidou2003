"""Root health endpoint."""
from fastapi import APIRouter
from core.deps import now_utc

router = APIRouter()


@router.get("/")
async def root():
    return {"app": "Aidou Command Enterprise Ultimate", "status": "ok", "time": now_utc().isoformat()}
