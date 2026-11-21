
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user


router = APIRouter(
    prefix="/clients",
    tags=["Clients"]
)


Db = Annotated[Session, Depends(get_db)]

CurrentUser = Annotated[
    models.User,
    Depends(get_current_user)
]


@router.post(
    "",
    response_model=schemas.ClientResponse,
    status_code=status.HTTP_201_CREATED
)
def create_client(
    payload: schemas.ClientCreate,
    db: Db,
    current_user: CurrentUser
):
    new_client = models.Client(
        name=payload.name,
        email=str(payload.email),
        company=payload.company,
        owner_id=current_user.id
    )

    db.add(new_client)
    db.commit()
    db.refresh(new_client)

    return new_client


@router.post(
    "",
    response_model=schemas.ClientResponse,
    status_code=status.HTTP_201_CREATED
)
def create_client(
    payload: schemas.ClientCreate,
    db: Db,
    current_user: CurrentUser
):
    new_client = models.Client(
        name=payload.name,
        email=str(payload.email),
        company=payload.company,
        owner_id=current_user.id
    )

    db.add(new_client)
    db.commit()
    db.refresh(new_client)

    return new_client


@router.get(
    "",
    response_model=list[schemas.ClientResponse]
)
def get_clients(
    db: Db,
    current_user: CurrentUser
):
    statement = select(models.Client).where(
        models.Client.owner_id == current_user.id
    )

    clients = db.scalars(statement).all()

    return clients


@router.get(
    "/{client_id}",
    response_model=schemas.ClientResponse
)
def get_client(
    client_id: int,
    db: Db,
    current_user: CurrentUser
):
    statement = select(models.Client).where(
        models.Client.id == client_id,
        models.Client.owner_id == current_user.id
    )

    client = db.scalar(statement)

    if client is None:
        raise HTTPException(
            status_code=404,
            detail="Client not found"
        )

    return client