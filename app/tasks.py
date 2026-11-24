
from datetime import timezone
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
    tags=["Tasks"]
)

Db = Annotated[Session, Depends(get_db)]

CurrentUser = Annotated[
    models.User,
    Depends(get_current_user)
]


def get_owned_project(
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


def get_owned_task(
    db: Session,
    task_id: int,
    owner_id: int
):
    task = db.scalar(
        select(models.Task).where(
            models.Task.id == task_id,
            models.Task.owner_id == owner_id
        )
    )

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    return task


def normalize_due_date(value):
    if value is None:
        return None

    if value.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail="due_date must include a timezone"
        )

    return value.astimezone(timezone.utc)


@router.post(
    "/projects/{project_id}/tasks",
    response_model=schemas.TaskResponse,
    status_code=status.HTTP_201_CREATED
)
def create_task(
    project_id: int,
    payload: schemas.TaskCreate,
    db: Db,
    current_user: CurrentUser
):
    get_owned_project(
        db,
        project_id,
        current_user.id
    )

    new_task = models.Task(
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        status="pending",
        due_date=normalize_due_date(
            payload.due_date
        ),
        project_id=project_id,
        owner_id=current_user.id
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return new_task


@router.get(
    "/projects/{project_id}/tasks",
    response_model=list[schemas.TaskResponse]
)
def list_project_tasks(
    project_id: int,
    db: Db,
    current_user: CurrentUser,
    task_status: schemas.TaskStatus | None = Query(
        default=None,
        alias="status"
    ),
    priority: schemas.TaskPriority | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100)
):
    get_owned_project(
        db,
        project_id,
        current_user.id
    )

    statement = select(models.Task).where(
        models.Task.project_id == project_id,
        models.Task.owner_id == current_user.id
    )

    if task_status is not None:
        statement = statement.where(
            models.Task.status == task_status
        )

    if priority is not None:
        statement = statement.where(
            models.Task.priority == priority
        )

    statement = (
        statement
        .order_by(models.Task.id)
        .offset(skip)
        .limit(limit)
    )

    return db.scalars(statement).all()


@router.get(
    "/tasks",
    response_model=list[schemas.TaskResponse]
)
def list_my_tasks(
    db: Db,
    current_user: CurrentUser,
    task_status: schemas.TaskStatus | None = Query(
        default=None,
        alias="status"
    ),
    priority: schemas.TaskPriority | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100)
):
    statement = select(models.Task).where(
        models.Task.owner_id == current_user.id
    )

    if task_status is not None:
        statement = statement.where(
            models.Task.status == task_status
        )

    if priority is not None:
        statement = statement.where(
            models.Task.priority == priority
        )

    statement = (
        statement
        .order_by(models.Task.id)
        .offset(skip)
        .limit(limit)
    )

    return db.scalars(statement).all()


@router.get(
    "/tasks/{task_id}",
    response_model=schemas.TaskResponse
)
def get_task(
    task_id: int,
    db: Db,
    current_user: CurrentUser
):
    return get_owned_task(
        db,
        task_id,
        current_user.id
    )

@router.get(
    "/tasks/{task_id}",
    response_model=schemas.TaskResponse
)
def get_task(
    task_id: int,
    db: Db,
    current_user: CurrentUser
):
    return get_owned_task(
        db,
        task_id,
        current_user.id
    )


@router.patch(
    "/tasks/{task_id}",
    response_model=schemas.TaskResponse
)
def update_task(
    task_id: int,
    payload: schemas.TaskUpdate,
    db: Db,
    current_user: CurrentUser
):
    task = get_owned_task(
        db,
        task_id,
        current_user.id
    )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    for field in ("title", "priority"):
        if (
            field in update_data
            and update_data[field] is None
        ):
            raise HTTPException(
                status_code=422,
                detail=f"{field} cannot be null"
            )

    if (
        "due_date" in update_data
        and update_data["due_date"] is not None
    ):
        update_data["due_date"] = normalize_due_date(
            update_data["due_date"]
        )

    for field, value in update_data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)

    return task


@router.patch(
    "/tasks/{task_id}/status",
    response_model=schemas.TaskResponse
)
def update_task_status(
    task_id: int,
    payload: schemas.TaskStatusUpdate,
    db: Db,
    current_user: CurrentUser
):
    task = get_owned_task(
        db,
        task_id,
        current_user.id
    )

    task.status = payload.status

    db.commit()
    db.refresh(task)

    return task


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_task(
    task_id: int,
    db: Db,
    current_user: CurrentUser
):
    task = get_owned_task(
        db,
        task_id,
        current_user.id
    )

    db.delete(task)
    db.commit()

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )

