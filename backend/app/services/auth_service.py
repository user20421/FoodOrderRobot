"""
认证服务
"""
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.repositories.user_repo import user_repo
from app.schemas.auth import UserRegister, UserLogin, UserOut
from app.core.exceptions import AuthenticationException, BusinessException
from app.core.config import settings


def create_access_token(user_id: int, role: str) -> str:
    """生成 JWT 访问令牌"""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_access_token_expire_hours)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def register_user(db: AsyncSession, data: UserRegister) -> UserOut:
    """用户注册"""
    if data.username in ("admin", "管理员"):
        raise BusinessException("该用户名已被系统保留，请更换")

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
    await db.commit()
    return UserOut.model_validate(user)


async def login_user(db: AsyncSession, data: UserLogin) -> UserOut:
    """用户登录。admin 与 管理员 视为同一账号，系统中只保留 管理员。"""
    # admin 作为管理员的别名入口，统一映射到中文账号
    lookup_name = data.username
    if lookup_name == "admin":
        lookup_name = "管理员"

    user = await user_repo.get_by_username(db, lookup_name)
    if not user:
        raise AuthenticationException("用户名或密码错误")

    if not bcrypt.checkpw(data.password.encode(), user.password.encode()):
        raise AuthenticationException("用户名或密码错误")

    # 保护内置管理员账号：如果角色被篡改或注册时误为顾客，自动纠正
    if user.username == "管理员" and user.role != "admin":
        user.role = "admin"
        await db.commit()
        print("[Auth] 登录时修复 '管理员' 角色为 admin")

    return UserOut.model_validate(user)


async def init_admin_user(db: AsyncSession):
    """初始化商家账号'管理员'；若存在旧的 admin 账号则清理，确保系统中只有'管理员'。"""
    changed = False

    # 清理旧的英文 admin 账号（如果存在）
    old_admin = await user_repo.get_by_username(db, "admin")
    if old_admin:
        await user_repo.delete(db, old_admin.id)
        changed = True
        print("[Init] 已清理旧 admin 账号，统一使用'管理员'")

    # 确保中文管理员账号存在
    username = "管理员"
    existing = await user_repo.get_by_username(db, username)
    if not existing:
        hashed = bcrypt.hashpw("123456".encode(), bcrypt.gensalt()).decode()
        await user_repo.create(db, {
            "username": username,
            "password": hashed,
            "role": "admin",
            "phone": "13800138000",
        })
        changed = True
        print("[Init] 商家账号 管理员/123456 已创建")
    elif existing.role != "admin":
        # 若用户之前用"管理员"注册为顾客，自动升级为商家
        existing.role = "admin"
        await db.flush()
        changed = True
        print("[Init] 已修复'管理员'账号角色为商家")

    if changed:
        await db.commit()
