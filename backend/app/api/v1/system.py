"""
系统路由
保持与原后端API格式兼容
"""
from fastapi import APIRouter, Request
from datetime import datetime, timezone

router = APIRouter()


@router.get("/system/startup")
async def get_startup_time(request: Request):
    """获取后端启动时间"""
    startup_time = getattr(request.app.state, "startup_time", datetime.now(timezone.utc).isoformat())
    return {"startup_time": startup_time}
