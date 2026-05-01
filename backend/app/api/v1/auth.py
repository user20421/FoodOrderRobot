"""
认证 API
POST /api/v1/auth/register
POST /api/v1/auth/login
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.auth import UserRegister, UserLogin, LoginResponse, UserOut
from app.services.auth_service import register_user, authenticate_user

router = APIRouter()


@router.post("/auth/register")
async def user_register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """用户注册（仅支持顾客注册）"""
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    user = await register_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    return {"message": "注册成功", "user": UserOut(id=user.id, username=user.username, role=user.role)}


@router.post("/auth/login", response_model=LoginResponse)
async def user_login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """用户/商家登录"""
    user = await authenticate_user(db, data.username, data.password, data.role)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return LoginResponse(
        user=UserOut(id=user.id, username=user.username, role=user.role),
        message="登录成功",
    )
