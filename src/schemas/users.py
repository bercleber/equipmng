from pydantic import BaseModel, EmailStr, Field, SecretStr

from src.models.models import RoleName


class RoleSummary(BaseModel):
    id: int
    name: RoleName


class RoleRead(RoleSummary):
    description: str


class UserCreate(BaseModel):
    name: str = Field(min_length=6, max_length=50)
    email: EmailStr = Field(min_length=8, max_length=40)
    phone: str = Field(min_length=10, max_length=12)
    password: SecretStr = Field(min_length=6)


class UserRead(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    active: bool
    role: RoleSummary
