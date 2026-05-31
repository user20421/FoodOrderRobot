"""
API 依赖注入
"""
from fastapi import Request, HTTPException, status
from typing import Optional

from app.core.database import get_db
from app.core.exceptions import AuthorizationException


async def get_current_user(request: Request) -> dict:
    """从请求头获取当前用户"""
    user_id = request.headers.get("X-User-ID")
    user_role = request.headers.get("X-User-Role", "customer")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期",
        )

    try:
        user_id = int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的用户ID",
        )

    return {"id": user_id, "role": user_role}


async def require_admin(current_user: dict = None) -> dict:
    """要求管理员权限"""
    # 从request中获取
    pass


def check_admin(request: Request):
    """检查是否为管理员"""
    user_role = request.headers.get("X-User-Role", "")
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要管理员权限",
        )
    return True
