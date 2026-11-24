
from datetime import datetime
from decimal import Decimal
from typing import Literal
from datetime import date


from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)


class RegisterRequest(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=100
    )
    email: EmailStr
    password: str = Field(
        min_length=12,
        max_length=128
    )


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(
        min_length=12,
        max_length=128
    )


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(
        min_length=12,
        max_length=128
    )


class MessageResponse(BaseModel):
    message: str
    


from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field
)

class ClientCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=100
    )
    email: EmailStr
    company: str = Field(
        min_length=2,
        max_length=100
    )

class ClientUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100
    )

    email: EmailStr | None = None

    company: str | None = Field(
        default=None,
        min_length=2,
        max_length=100
    )

class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    company: str
    owner_id: int
    


ProjectStatus = Literal[
    "pending",
    "in_progress",
    "completed",
    "cancelled"
]


class ProjectCreate(BaseModel):
    title: str = Field(
        min_length=3,
        max_length=250
    )

    description: str = Field(
        min_length=2
    )

    budget: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2
    )

    client_id: int = Field(gt=0)

    deadline: date | None = None


class ProjectUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=3,
        max_length=250
    )

    description: str | None = Field(
        default=None,
        min_length=2
    )

    budget: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=12,
        decimal_places=2
    )

    status: ProjectStatus | None = None

    client_id: int | None = Field(
        default=None,
        gt=0
    )

    deadline: date | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    budget: Decimal
    status: ProjectStatus
    client_id: int
    owner_id: int
    deadline: date | None


TaskStatus = Literal[
    "pending",
    "in_progress",
    "completed"
]

TaskPriority = Literal[
    "low",
    "medium",
    "high"
]


class TaskCreate(BaseModel):
    title: str = Field(
        min_length=3,
        max_length=200
    )

    description: str | None = None

    priority: TaskPriority = "medium"

    due_date: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=3,
        max_length=200
    )

    description: str | None = None

    priority: TaskPriority | None = None

    due_date: datetime | None = None


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: datetime | None
    project_id: int
    owner_id: int
    created_at: datetime
