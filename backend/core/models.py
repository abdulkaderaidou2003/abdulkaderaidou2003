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
    assistant: str  # hr | accountant | scheduler | support | marketing | analytics | advisor
    session_id: str
    message: str


class RoleUpdate(BaseModel):
    role: str  # owner | manager | employee | customer


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


class SaleIn(BaseModel):
    items: List[Dict[str, Any]]  # [{product_id, qty}]
    tender: str = "card"  # card | cash | etransfer


class UnderwritingPolicy(BaseModel):
    pos_revenue_ltv: float = 0.15
    payroll_ltv: float = 0.05
    payout_projection_ltv: float = 0.80
    free_band_cap: float = 1000.0
    fee_above_free: float = 0.045
    floor: float = 1000.0


class ScoringWeights(BaseModel):
    """Tunable signal weights for the Aidou Network Credit Score.
    Each weight caps how many points that signal can contribute."""
    pos_revenue_cap: int = 300
    pos_revenue_divisor: float = 1000.0  # 1 point per $X of POS revenue
    payroll_cap: int = 200
    payroll_divisor: float = 5000.0
    consistency_cap: int = 150
    consistency_per_run: int = 25
    referrals_cap: int = 150
    referrals_divisor: float = 10.0
    repayment_cap: int = 120
    repayment_per_repaid: int = 60
    team_cap: int = 50
    team_per_employee: int = 4
    ops_penalty_cap: int = 50
    ops_penalty_per_ticket: int = 3
    baseline: int = 100


DEFAULT_POLICY: Dict[str, float] = UnderwritingPolicy().model_dump()
DEFAULT_WEIGHTS: Dict[str, Any] = ScoringWeights().model_dump()
