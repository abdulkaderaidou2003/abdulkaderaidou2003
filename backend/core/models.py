"""Pydantic models shared across routers."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class SessionRequest(BaseModel):
    session_token: str


class CompanySwitch(BaseModel):
    company_id: str


class WorkspaceSwitch(BaseModel):
    company_id: str
    role: str  # owner | manager | employee | customer


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
    assistant: str
    session_id: str
    message: str


class SaleIn(BaseModel):
    items: List[Dict[str, Any]]
    tender: str = "card"


class RoleUpdate(BaseModel):
    role: str  # owner | manager | employee | customer
