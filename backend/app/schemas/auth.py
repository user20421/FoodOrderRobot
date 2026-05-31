"""
认证相关Schema
"""
from pydantic import BaseModel, Field
from typing import Optional


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    phone: Optional[str] = Field(None, description="手机号")


class UserLogin(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    role: Optional[str] = Field(None, description="角色")


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    phone: Optional[str] = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserOut
    message: str
    token: Optional[str] = None
