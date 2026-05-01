"""
认证业务服务
"""
import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_username(db: AsyncSession, username: str):
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


async def register_user(db: AsyncSession, username: str, password: str):
    existing = await get_user_by_username(db, username)
    if existing:
        return None
    user = User(
        username=username,
        password=_hash_password(password),
        role="customer",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, username: str, password: str, role: str = "customer"):
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not _verify_password(password, user.password):
        return None
    # 商家登录时验证角色
    if role == "admin" and user.role != "admin":
        return None
    if role == "customer" and user.role == "admin":
        # admin 也可以登录用户端（可选）
        pass
    return user


async def init_admin_user(db: AsyncSession):
    """初始化商家账号 admin/123456"""
    admin = await get_user_by_username(db, "admin")
    if not admin:
        user = User(
            username="admin",
            password=_hash_password("123456"),
            role="admin",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    return admin
