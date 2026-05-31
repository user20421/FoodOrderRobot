"""
FastAPI 应用入口
"""
import os
# 彻底清除所有代理设置，防止 DashScope/requests 连接失败
for proxy_var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(proxy_var, None)
os.environ["NO_PROXY"] = "*"

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db, AsyncSessionLocal
from app.core.mongodb import init_mongodb, close_mongodb
from app.core.logging_config import setup_logging
from app.core.chroma_client import chroma_store
from app.ai.rag.indexer import rag_indexer
from app.api.v1 import auth, menu, order, chat, admin, system, image_search
from app.services.init_service import initialize_system

# 导入所有模型，确保 Base.metadata 包含所有表
import app.models  # noqa: F401

# 初始化日志
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    启动时：建表 + 初始化数据 + 连接MongoDB + 初始化RAG索引
    """
    app.state.startup_time = datetime.now(timezone.utc).isoformat()

    # 创建数据库表
    await init_db()

    # 初始化数据
    async with AsyncSessionLocal() as db:
        await initialize_system(db)

    # 连接 MongoDB
    await init_mongodb()

    # LLM 可用性自检
    from app.ai.llm import check_llm_health
    llm_health = await check_llm_health()
    if llm_health["ok"]:
        print(f"[LLM] 模型检查通过: {llm_health['model']}")
    else:
        print(f"[LLM] 警告: {llm_health['reason']}")

    # 初始化 RAG 索引（后台线程，避免阻塞启动）
    import threading
    def _init_rag():
        try:
            rag_indexer.initialize()
        except Exception as e:
            print(f"[RAG] 索引初始化失败（非阻塞）: {e}")
    threading.Thread(target=_init_rag, daemon=True, name="rag-init").start()

    yield

    # 关闭 MongoDB
    await close_mongodb()


app = FastAPI(
    title="智能点餐机器人",
    description="基于 FastAPI + LangGraph 多智能体架构 + DashScope 的智能点餐系统",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/v1", tags=["认证"])
app.include_router(menu.router, prefix="/api/v1", tags=["菜单"])
app.include_router(order.router, prefix="/api/v1", tags=["订单"])
app.include_router(chat.router, prefix="/api/v1", tags=["聊天"])
app.include_router(admin.router, prefix="/api/v1", tags=["商家管理"])
app.include_router(system.router, prefix="/api/v1", tags=["系统"])
app.include_router(image_search.router, prefix="/api/v1", tags=["图片搜菜"])


@app.get("/")
async def root():
    return {"message": "欢迎使用智能点餐机器人 API", "docs": "/docs", "version": "3.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "智能点餐机器人"}
