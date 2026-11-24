
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user


router = APIRouter(
    tags=["Projects"]
)

Db = Annotated[Session, Depends(get_db)]

CurrentUser = Annotated[
    models.User,
    Depends(get_current_user)
]


def find_owned_client(
    db: Session,
    client_id: int,
    owner_id: int
):
    client = db.scalar(
        select(models.Client).where(
            models.Client.id == client_id,
            models.Client.owner_id == owner_id
        )
    )

    if client is None:
        raise HTTPException(
            status_code=404,
            detail="Client not found"
        )

    return client


def find_owned_project(
    db: Session,
    project_id: int,
    owner_id: int
):
    project = db.scalar(
        select(models.Project).where(
            models.Project.id == project_id,
            models.Project.owner_id == owner_id
        )
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return project


@router.post(
    "/projects",
    response_model=schemas.ProjectResponse,
    status_code=status.HTTP_201_CREATED
)
def create_project(
    payload: schemas.ProjectCreate,
    db: Db,
    current_user: CurrentUser
):
    find_owned_client(
        db,
        payload.client_id,
        current_user.id
    )

    new_project = models.Project(
        title=payload.title,
        description=payload.description,
        budget=payload.budget,
        client_id=payload.client_id,
        owner_id=current_user.id,
        deadline=payload.deadline,
        status="pending"
    )

    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    return new_project


@router.get(
    "/projects",
    response_model=list[schemas.ProjectResponse]
)
def get_projects(
    db: Db,
    current_user: CurrentUser,
    project_status: schemas.ProjectStatus | None = Query(
        default=None,
        alias="status"
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100)
):
    statement = select(models.Project).where(
        models.Project.owner_id == current_user.id
    )

    if project_status is not None:
        statement = statement.where(
            models.Project.status == project_status
        )

    statement = (
        statement
        .order_by(models.Project.id)
        .offset(skip)
        .limit(limit)
    )

    return db.scalars(statement).all()


@router.get(
    "/projects/{project_id}",
    response_model=schemas.ProjectResponse
)
def get_project(
    project_id: int,
    db: Db,
    current_user: CurrentUser
):
    return find_owned_project(
        db,
        project_id,
        current_user.id
    )


@router.patch(
    "/projects/{project_id}",
    response_model=schemas.ProjectResponse
)
def update_project(
    project_id: int,
    payload: schemas.ProjectUpdate,
    db: Db,
    current_user: CurrentUser
):
    project = find_owned_project(
        db,
        project_id,
        current_user.id
    )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    # Only deadline can be explicitly set to null.
    for field, value in update_data.items():
        if value is None and field != "deadline":
            raise HTTPException(
                status_code=422,
                detail=f"{field} cannot be null"
            )

    if "client_id" in update_data:
        find_owned_client(
            db,
            update_data["client_id"],
            current_user.id
        )

    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)

    return project


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_project(
    project_id: int,
    db: Db,
    current_user: CurrentUser
):
    project = find_owned_project(
        db,
        project_id,
        current_user.id
    )

    db.delete(project)
    db.commit()

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )



@router.get(
    "/clients/{client_id}/projects",
    response_model=list[schemas.ProjectResponse]
)
def get_client_projects(
    client_id: int,
    db: Db,
    current_user: CurrentUser
):
    find_owned_client(
        db,
        client_id,
        current_user.id
    )

    statement = (
        select(models.Project)
        .where(
            models.Project.client_id == client_id,
            models.Project.owner_id == current_user.id
        )
        .order_by(models.Project.id)
    )

    return db.scalars(statement).all()
