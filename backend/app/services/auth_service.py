"""
认证服务
"""
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.repositories.user_repo import user_repo
from app.schemas.auth import UserRegister, UserLogin, UserOut
from app.core.exceptions import AuthenticationException, BusinessException


async def register_user(db: AsyncSession, data: UserRegister) -> UserOut:
    """用户注册"""
    existing = await user_repo.get_by_username(db, data.username)
    if existing:
        raise BusinessException("用户名已存在")

    hashed = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
    user = await user_repo.create(db, {
        "username": data.username,
        "password": hashed,
        "phone": data.phone,
        "role": "customer",
    })
    return UserOut.model_validate(user)


async def login_user(db: AsyncSession, data: UserLogin) -> UserOut:
    """用户登录"""
    user = await user_repo.get_by_username(db, data.username)
    if not user:
        raise AuthenticationException("用户名或密码错误")

    if not bcrypt.checkpw(data.password.encode(), user.password.encode()):
        raise AuthenticationException("用户名或密码错误")

    return UserOut.model_validate(user)


async def init_admin_user(db: AsyncSession):
    """初始化商家账号"""
    admin = await user_repo.get_by_username(db, "admin")
    if not admin:
        hashed = bcrypt.hashpw("123456".encode(), bcrypt.gensalt()).decode()
        await user_repo.create(db, {
            "username": "admin",
            "password": hashed,
            "role": "admin",
            "phone": "13800138000",
        })
        print("[Init] 商家账号 admin/123456 已创建")
