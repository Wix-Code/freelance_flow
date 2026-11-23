
from datetime import datetime

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