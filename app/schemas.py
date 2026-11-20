
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class ClientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    company: str = Field(min_length=2, max_length=100)


class ClientResponse(ClientCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


