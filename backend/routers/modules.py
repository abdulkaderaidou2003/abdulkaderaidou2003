"""Modules catalog endpoint."""
from typing import Optional
from fastapi import APIRouter, Header

from core.deps import get_user_from_token
from core.catalog import MODULE_CATALOG

router = APIRouter()


@router.get("/modules")
async def modules(authorization: Optional[str] = Header(None)):
    await get_user_from_token(authorization)
    return {"catalog": MODULE_CATALOG}
