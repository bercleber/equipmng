from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, SecretStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    refresh_expires_at: datetime
    token_type: Literal["bearer"] = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: SecretStr = Field(min_length=1, max_length=256)
