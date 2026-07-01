"""
API 依赖注入
"""
import jwt
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Optional

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AuthorizationException


# OAuth2 密码 Bearer 方案（tokenUrl 为登录接口）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _decode_token(token: str) -> dict:
    """解码并校验 JWT"""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        role = payload.get("role", "customer")
        if user_id is None:
            raise AuthorizationException("无效的认证令牌")
        return {"id": int(user_id), "role": role}
    except jwt.ExpiredSignatureError:
        raise AuthorizationException("登录已过期，请重新登录")
    except jwt.InvalidTokenError as e:
        raise AuthorizationException(f"无效的认证令牌: {e}")


async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
) -> dict:
    """
    获取当前登录用户。
    优先从 Authorization: Bearer <token> 头解析；若未提供，则兼容旧的 X-User-ID/X-User-Role 头。
    """
    # 1. 优先 JWT
    if token:
        return _decode_token(token)

    # 2. 兼容旧的请求头（方便测试和前端未完全迁移时过渡）
    user_id = request.headers.get("X-User-ID")
    user_role = request.headers.get("X-User-Role", "customer")
    if user_id:
        try:
            return {"id": int(user_id), "role": user_role}
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的用户ID",
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录或登录已过期",
    )


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """要求管理员权限"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要管理员权限",
        )
    return current_user
