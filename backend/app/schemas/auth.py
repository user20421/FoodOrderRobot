"""
认证相关 Pydantic Schema
"""
from typing import Literal
from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class UserLogin(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    role: Literal["customer", "admin"] = "customer"


class UserOut(BaseModel):
    id: int
    username: str
    role: str


class LoginResponse(BaseModel):
    user: UserOut
    message: str
