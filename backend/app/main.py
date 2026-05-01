"""
FastAPI 应用入口
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from app.core.database import init_db, AsyncSessionLocal
from app.services.menu_service import init_menu_data
from app.services.auth_service import init_admin_user
from app.api.v1 import menu, order, chat, auth, admin, system

# 显式导入所有模型，确保 Base.metadata 包含所有表
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    启动时：建表 + 初始化菜单数据 + 初始化商家账号 + 记录启动时间
    """
    # 记录启动时间（用于前端判断是否需要清空聊天记录）
    app.state.startup_time = datetime.now(timezone.utc).isoformat()

    # 创建数据库表
    await init_db()
    async with AsyncSessionLocal() as db:
        # 初始化模拟菜单数据
        await init_menu_data(db)
        # 初始化商家账号 admin/123456
        await init_admin_user(db)
    yield


app = FastAPI(
    title="点餐机器人",
    description="基于 FastAPI + 多智能体架构 + DashScope 的智能点餐机器人",
    version="2.0.0",
    lifespan=lifespan,
)

# 注册路由
app.include_router(auth.router, prefix="/api/v1", tags=["认证"])
app.include_router(menu.router, prefix="/api/v1", tags=["菜单"])
app.include_router(order.router, prefix="/api/v1", tags=["订单"])
app.include_router(chat.router, prefix="/api/v1", tags=["聊天"])
app.include_router(admin.router, prefix="/api/v1", tags=["商家管理"])
app.include_router(system.router, prefix="/api/v1", tags=["系统"])


@app.get("/")
async def root():
    return {"message": "欢迎使用点餐机器人 API", "docs": "/docs"}