
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field


class OverviewResponse(BaseModel):
    total_clients: int
    total_projects: int
    active_projects: int
    completed_projects: int
    total_tasks: int
    completed_tasks: int
    total_invoiced: Decimal
    payments_received: Decimal
    outstanding_balance: Decimal
    overdue_invoices: int


class ProjectStatsResponse(BaseModel):
    total: int
    pending: int
    in_progress: int
    completed: int
    cancelled: int


class TaskStatsResponse(BaseModel):
    total: int
    pending: int
    in_progress: int
    completed: int
    high_priority_open: int
    completion_rate: float


class FinancialStatsResponse(BaseModel):
    currency: str = "NGN"
    total_invoiced: Decimal
    payments_received: Decimal
    outstanding_balance: Decimal
    overdue_amount: Decimal
    overdue_invoices: int
    draft_invoices: int
    paid_invoices: int


class RevenueMonth(BaseModel):
    month: str
    amount: Decimal


class ActivityItem(BaseModel):
    type: str
    id: int
    title: str
    created_at: datetime


class ActivityResponse(BaseModel):
    activities: list[ActivityItem]
