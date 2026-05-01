"""
系统信息 API
"""
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/system/startup")
async def get_startup_time(request: Request):
    """获取后端启动时间戳，用于前端判断是否需要清空聊天记录"""
    startup_time = getattr(request.app.state, "startup_time", "unknown")
    return {"startup_time": startup_time}
