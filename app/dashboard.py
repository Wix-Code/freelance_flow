
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app import dashboard_schemas as schemas
from app.database import get_db
from app.security import get_current_user
from datetime import date
from sqlalchemy import extract


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)

Db = Annotated[Session, Depends(get_db)]

CurrentUser = Annotated[
    models.User,
    Depends(get_current_user)
]

ZERO = Decimal("0.00")


def count_rows(db, model, *conditions):
    statement = (
        select(func.count())
        .select_from(model)
        .where(*conditions)
    )
    return db.scalar(statement) or 0


def sum_column(db, column, *conditions):
    statement = select(
        func.coalesce(func.sum(column), 0)
    ).where(*conditions)

    return db.scalar(statement) or ZERO


def get_financial_totals(db, owner_id):
    billable_statuses = (
        "issued",
        "partially_paid",
        "paid"
    )

    total_invoiced = sum_column(
        db,
        models.Invoice.total_amount,
        models.Invoice.owner_id == owner_id,
        models.Invoice.status.in_(billable_statuses)
    )

    payments_received = db.scalar(
        select(
            func.coalesce(
                func.sum(models.Payment.amount),
                0
            )
        )
        .join(
            models.Invoice,
            models.Payment.invoice_id == models.Invoice.id
        )
        .where(models.Invoice.owner_id == owner_id)
    ) or ZERO

    return {
        "total_invoiced": total_invoiced,
        "payments_received": payments_received,
        "outstanding_balance": (
            total_invoiced - payments_received
        )
    }


@router.get(
    "/overview",
    response_model=schemas.OverviewResponse
)
def dashboard_overview(
    db: Db,
    current_user: CurrentUser
):
    owner_id = current_user.id

    total_clients = count_rows(
        db,
        models.Client,
        models.Client.owner_id == owner_id
    )

    total_projects = count_rows(
        db,
        models.Project,
        models.Project.owner_id == owner_id
    )

    active_projects = count_rows(
        db,
        models.Project,
        models.Project.owner_id == owner_id,
        models.Project.status == "in_progress"
    )

    completed_projects = count_rows(
        db,
        models.Project,
        models.Project.owner_id == owner_id,
        models.Project.status == "completed"
    )

    total_tasks = count_rows(
        db,
        models.Task,
        models.Task.owner_id == owner_id
    )

    completed_tasks = count_rows(
        db,
        models.Task,
        models.Task.owner_id == owner_id,
        models.Task.status == "completed"
    )

    today = datetime.now(timezone.utc).date()

    overdue = count_rows(
        db,
        models.Invoice,
        models.Invoice.owner_id == owner_id,
        models.Invoice.due_date < today,
        models.Invoice.status.in_(
            ["issued", "partially_paid"]
        )
    )

    money = get_financial_totals(db, owner_id)

    return {
        "total_clients": total_clients,
        "total_projects": total_projects,
        "active_projects": active_projects,
        "completed_projects": completed_projects,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "overdue_invoices": overdue,
        **money
    }


@router.get(
    "/projects",
    response_model=schemas.ProjectStatsResponse
)
def project_statistics(
    db: Db,
    current_user: CurrentUser
):
    statement = (
        select(
            models.Project.status,
            func.count(models.Project.id)
        )
        .where(
            models.Project.owner_id == current_user.id
        )
        .group_by(models.Project.status)
    )

    rows = db.execute(statement).all()

    counts = {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "cancelled": 0
    }

    for project_status, count in rows:
        counts[project_status] = count

    return {
        "total": sum(counts.values()),
        **counts
    }


@router.get(
    "/tasks",
    response_model=schemas.TaskStatsResponse
)
def task_statistics(
    db: Db,
    current_user: CurrentUser
):
    owner_id = current_user.id

    statement = (
        select(
            models.Task.status,
            func.count(models.Task.id)
        )
        .where(models.Task.owner_id == owner_id)
        .group_by(models.Task.status)
    )

    rows = db.execute(statement).all()

    counts = {
        "pending": 0,
        "in_progress": 0,
        "completed": 0
    }

    for task_status, count in rows:
        counts[task_status] = count

    total = sum(counts.values())

    high_priority_open = count_rows(
        db,
        models.Task,
        models.Task.owner_id == owner_id,
        models.Task.priority == "high",
        models.Task.status != "completed"
    )

    completion_rate = (
        round(
            counts["completed"] / total * 100,
            2
        )
        if total > 0
        else 0.0
    )

    return {
        "total": total,
        **counts,
        "high_priority_open": high_priority_open,
        "completion_rate": completion_rate
    }


@router.get(
    "/financials",
    response_model=schemas.FinancialStatsResponse
)
def financial_statistics(
    db: Db,
    current_user: CurrentUser
):
    owner_id = current_user.id
    today = datetime.now(timezone.utc).date()

    money = get_financial_totals(
        db,
        owner_id
    )

    draft_count = count_rows(
        db,
        models.Invoice,
        models.Invoice.owner_id == owner_id,
        models.Invoice.status == "draft"
    )

    paid_count = count_rows(
        db,
        models.Invoice,
        models.Invoice.owner_id == owner_id,
        models.Invoice.status == "paid"
    )

    overdue_count = count_rows(
        db,
        models.Invoice,
        models.Invoice.owner_id == owner_id,
        models.Invoice.due_date < today,
        models.Invoice.status.in_(
            ["issued", "partially_paid"]
        )
    )

    # Aggregate payments per invoice first.
    payment_totals = (
        select(
            models.Payment.invoice_id.label("invoice_id"),
            func.sum(
                models.Payment.amount
            ).label("paid")
        )
        .group_by(models.Payment.invoice_id)
        .subquery()
    )

    outstanding = (
        models.Invoice.total_amount
        - func.coalesce(payment_totals.c.paid, 0)
    )

    overdue_amount = db.scalar(
        select(
            func.coalesce(
                func.sum(outstanding),
                0
            )
        )
        .select_from(models.Invoice)
        .outerjoin(
            payment_totals,
            models.Invoice.id
            == payment_totals.c.invoice_id
        )
        .where(
            models.Invoice.owner_id == owner_id,
            models.Invoice.due_date < today,
            models.Invoice.status.in_(
                ["issued", "partially_paid"]
            )
        )
    ) or ZERO

    return {
        "currency": "NGN",
        **money,
        "overdue_amount": overdue_amount,
        "overdue_invoices": overdue_count,
        "draft_invoices": draft_count,
        "paid_invoices": paid_count
    }


@router.get(
    "/revenue-trend",
    response_model=list[schemas.RevenueMonth]
)
def revenue_trend(
    db: Db,
    current_user: CurrentUser,
    months: int = Query(default=6, ge=1, le=12)
):
    today = datetime.now(timezone.utc).date()

    # Build the list of calendar months.
    month_keys = []

    for offset in range(months - 1, -1, -1):
        month_number = (
            today.year * 12
            + today.month - 1
            - offset
        )

        year = month_number // 12
        month = month_number % 12 + 1

        month_keys.append(
            f"{year}-{month:02d}"
        )

    first_year, first_month = map(
        int,
        month_keys[0].split("-")
    )

    start_date = datetime(
        first_year,
        first_month,
        1,
        tzinfo=timezone.utc
    )

    statement = (
        select(
            extract(
                "year",
                models.Payment.paid_at
            ).label("year"),
            extract(
                "month",
                models.Payment.paid_at
            ).label("month"),
            func.sum(
                models.Payment.amount
            ).label("amount")
        )
        .join(
            models.Invoice,
            models.Payment.invoice_id
            == models.Invoice.id
        )
        .where(
            models.Invoice.owner_id
            == current_user.id,
            models.Payment.paid_at >= start_date
        )
        .group_by(
            extract("year", models.Payment.paid_at),
            extract("month", models.Payment.paid_at)
        )
    )

    rows = db.execute(statement).all()

    totals = {
        key: ZERO
        for key in month_keys
    }

    for year, month, amount in rows:
        key = f"{int(year)}-{int(month):02d}"

        if key in totals:
            totals[key] = amount

    return [
        {
            "month": key,
            "amount": amount
        }
        for key, amount in totals.items()
    ]


@router.get(
    "/recent-activity",
    response_model=schemas.ActivityResponse
)
def recent_activity(
    db: Db,
    current_user: CurrentUser,
    limit: int = Query(default=10, ge=1, le=50)
):
    owner_id = current_user.id

    tasks = db.scalars(
        select(models.Task)
        .where(models.Task.owner_id == owner_id)
        .order_by(models.Task.created_at.desc())
        .limit(limit)
    ).all()

    invoices = db.scalars(
        select(models.Invoice)
        .where(models.Invoice.owner_id == owner_id)
        .order_by(models.Invoice.created_at.desc())
        .limit(limit)
    ).all()

    payments = db.execute(
        select(models.Payment)
        .join(
            models.Invoice,
            models.Payment.invoice_id
            == models.Invoice.id
        )
        .where(models.Invoice.owner_id == owner_id)
        .order_by(models.Payment.paid_at.desc())
        .limit(limit)
    ).scalars().all()

    activities = []

    for task in tasks:
        activities.append({
            "type": "task_created",
            "id": task.id,
            "title": task.title,
            "created_at": task.created_at
        })

    for invoice in invoices:
        activities.append({
            "type": "invoice_created",
            "id": invoice.id,
            "title": invoice.invoice_number,
            "created_at": invoice.created_at
        })

    for payment in payments:
        activities.append({
            "type": "payment_recorded",
            "id": payment.id,
            "title": f"Payment for invoice {payment.invoice_id}",
            "created_at": payment.paid_at
        })

    activities.sort(
        key=lambda x: x["created_at"].replace(
            tzinfo=x["created_at"].tzinfo
            or timezone.utc
        ),
        reverse=True
    )

    return {
        "activities": activities[:limit]
    }
