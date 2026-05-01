"""
API 依赖注入
"""
from fastapi import Header, HTTPException

from app.core.database import get_db


# 统一导出 db 依赖
__all__ = ["get_db", "get_current_user", "require_admin"]


async def get_current_user(
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    x_user_role: str | None = Header(None, alias="X-User-Role"),
):
    """
    从请求头中获取当前用户信息。
    前端需在每次请求中通过 header 传递用户 ID 和角色。
    """
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    try:
        user_id = int(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="用户ID格式错误")
    return {"id": user_id, "role": x_user_role or "customer"}


async def require_admin(
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    x_user_role: str | None = Header(None, alias="X-User-Role"),
):
    """
    要求当前用户必须是管理员。
    """
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    try:
        user_id = int(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="用户ID格式错误")
    if x_user_role != "admin":
        raise HTTPException(status_code=403, detail="权限不足，仅管理员可访问")
    return {"id": user_id, "role": x_user_role}
