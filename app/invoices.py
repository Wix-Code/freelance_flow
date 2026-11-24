
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user


router = APIRouter(
    prefix="/invoices",
    tags=["Invoices & Payments"]
)

Db = Annotated[Session, Depends(get_db)]

CurrentUser = Annotated[
    models.User,
    Depends(get_current_user)
]


ZERO = Decimal("0.00")


def get_owned_invoice(
    db: Session,
    invoice_id: int,
    owner_id: int,
    lock: bool = False
):
    statement = select(models.Invoice).where(
        models.Invoice.id == invoice_id,
        models.Invoice.owner_id == owner_id
    )

    if lock:
        statement = statement.with_for_update()

    invoice = db.scalar(statement)

    if invoice is None:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found"
        )

    return invoice


def build_invoice_response(
    db: Session,
    invoice: models.Invoice
):
    items = db.scalars(
        select(models.InvoiceItem)
        .where(
            models.InvoiceItem.invoice_id == invoice.id
        )
        .order_by(models.InvoiceItem.id)
    ).all()

    payments = db.scalars(
        select(models.Payment)
        .where(
            models.Payment.invoice_id == invoice.id
        )
        .order_by(models.Payment.id)
    ).all()

    amount_paid = sum(
        (payment.amount for payment in payments),
        ZERO
    )

    item_data = [
        {
            "id": item.id,
            "description": item.description,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "line_total": (
                item.quantity * item.unit_price
            ),
        }
        for item in items
    ]

    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "project_id": invoice.project_id,
        "owner_id": invoice.owner_id,
        "currency": invoice.currency,
        "status": invoice.status,
        "due_date": invoice.due_date,
        "issued_at": invoice.issued_at,
        "created_at": invoice.created_at,
        "total_amount": invoice.total_amount,
        "amount_paid": amount_paid,
        "balance_due": (
            invoice.total_amount - amount_paid
        ),
        "items": item_data,
        "payments": payments,
    }


@router.post(
    "",
    response_model=schemas.InvoiceResponse,
    status_code=status.HTTP_201_CREATED
)
def create_invoice(
    payload: schemas.InvoiceCreate,
    db: Db,
    current_user: CurrentUser
):
    project = db.scalar(
        select(models.Project).where(
            models.Project.id == payload.project_id,
            models.Project.owner_id == current_user.id
        )
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    total = sum(
        (
            item.quantity * item.unit_price
            for item in payload.items
        ),
        ZERO
    )

    if total > Decimal("99999999999999.99"):
        raise HTTPException(
            status_code=422,
            detail="Invoice total is too large"
        )

    invoice = models.Invoice(
        invoice_number=(
            f"INV-{uuid4().hex[:16].upper()}"
        ),
        project_id=project.id,
        owner_id=current_user.id,
        currency="NGN",
        status="draft",
        due_date=payload.due_date,
        total_amount=total
    )

    db.add(invoice)
    db.flush()

    for item in payload.items:
        invoice_item = models.InvoiceItem(
            invoice_id=invoice.id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price
        )

        db.add(invoice_item)

    db.commit()
    db.refresh(invoice)

    return build_invoice_response(db, invoice)


@router.get(
    "",
    response_model=list[schemas.InvoiceResponse]
)
def list_invoices(
    db: Db,
    current_user: CurrentUser,
    invoice_status: schemas.InvoiceStatus | None = Query(
        default=None,
        alias="status"
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100)
):
    statement = select(models.Invoice).where(
        models.Invoice.owner_id == current_user.id
    )

    if invoice_status is not None:
        statement = statement.where(
            models.Invoice.status == invoice_status
        )

    statement = (
        statement
        .order_by(models.Invoice.id.desc())
        .offset(skip)
        .limit(limit)
    )

    invoices = db.scalars(statement).all()

    return [
        build_invoice_response(db, invoice)
        for invoice in invoices
    ]



@router.get(
    "/{invoice_id}",
    response_model=schemas.InvoiceResponse
)
def get_invoice(
    invoice_id: int,
    db: Db,
    current_user: CurrentUser
):
    invoice = get_owned_invoice(
        db,
        invoice_id,
        current_user.id
    )

    return build_invoice_response(
        db,
        invoice
    )



@router.post(
    "/{invoice_id}/issue",
    response_model=schemas.InvoiceResponse
)
def issue_invoice(
    invoice_id: int,
    db: Db,
    current_user: CurrentUser
):
    invoice = get_owned_invoice(
        db,
        invoice_id,
        current_user.id,
        lock=True
    )

    if invoice.status != "draft":
        raise HTTPException(
            status_code=409,
            detail="Only draft invoices can be issued"
        )

    invoice.status = "issued"
    invoice.issued_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(invoice)

    return build_invoice_response(db, invoice)



@router.post(
    "/{invoice_id}/payments",
    response_model=schemas.PaymentResponse,
    status_code=status.HTTP_201_CREATED
)
def record_payment(
    invoice_id: int,
    payload: schemas.PaymentCreate,
    db: Db,
    current_user: CurrentUser
):
    invoice = get_owned_invoice(
        db,
        invoice_id,
        current_user.id,
        lock=True
    )

    if invoice.status not in (
        "issued",
        "partially_paid"
    ):
        raise HTTPException(
            status_code=409,
            detail="Invoice cannot accept payments"
        )

    payments = db.scalars(
        select(models.Payment).where(
            models.Payment.invoice_id == invoice.id
        )
    ).all()

    amount_paid = sum(
        (payment.amount for payment in payments),
        ZERO
    )

    balance = invoice.total_amount - amount_paid

    if payload.amount > balance:
        raise HTTPException(
            status_code=400,
            detail="Payment exceeds outstanding balance"
        )

    payment = models.Payment(
        invoice_id=invoice.id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        reference=payload.reference
    )

    db.add(payment)

    new_total_paid = amount_paid + payload.amount

    if new_total_paid == invoice.total_amount:
        invoice.status = "paid"
    else:
        invoice.status = "partially_paid"

    db.commit()
    db.refresh(payment)

    return payment



@router.get(
    "/{invoice_id}/payments",
    response_model=list[schemas.PaymentResponse]
)
def list_invoice_payments(
    invoice_id: int,
    db: Db,
    current_user: CurrentUser
):
    get_owned_invoice(
        db,
        invoice_id,
        current_user.id
    )

    statement = (
        select(models.Payment)
        .where(
            models.Payment.invoice_id == invoice_id
        )
        .order_by(models.Payment.id)
    )

    return db.scalars(statement).all()


