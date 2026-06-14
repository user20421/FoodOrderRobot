"""
认证路由
保持与原后端API格式兼容
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationException, BusinessException
from app.schemas.auth import UserRegister, UserLogin, UserOut, AuthResponse
from app.services.auth_service import register_user, login_user, create_access_token

router = APIRouter()


@router.post("/auth/register")
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    try:
        user = await register_user(db, data)
        return {"message": "注册成功", "user": user}
    except BusinessException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/auth/login", response_model=AuthResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    try:
        result = await login_user(db, data)
        token = create_access_token(result.id, result.role)
        return AuthResponse(user=result, message="登录成功", token=token)
    except AuthenticationException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
