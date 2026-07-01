"""
FastAPI 应用入口
"""
import os
# 彻底清除所有代理设置，防止智谱 AI/requests 连接失败
for proxy_var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(proxy_var, None)
os.environ["NO_PROXY"] = "*"

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.core.exceptions import AppException

from app.core.database import init_db, AsyncSessionLocal
from app.core.mongodb import init_mongodb, close_mongodb
from app.core.redis import init_redis, close_redis
from app.core.logging_config import setup_logging, get_logger
from app.core.chroma_client import chroma_store
from app.ai.rag.indexer import rag_indexer
from app.api.v1 import auth, menu, order, chat, admin, system, image_search
from app.services.init_service import initialize_system

# 导入所有模型，确保 Base.metadata 包含所有表
import app.models  # noqa: F401

# 初始化日志
setup_logging()
logger = get_logger(__name__)


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

    # 连接 Redis
    await init_redis()

    # LLM 可用性自检
    from app.ai.llm import check_llm_health
    llm_health = await check_llm_health()
    if llm_health["ok"]:
        print(f"[LLM] 模型检查通过: {llm_health['model']}")
    else:
        print(f"[LLM] 警告: {llm_health['reason']}")

    # 初始化 RAG 索引（后台异步任务，避免阻塞启动）
    async def _init_rag():
        try:
            await asyncio.to_thread(rag_indexer.initialize)
            logger.info("[RAG] 索引初始化完成")
        except Exception as e:
            logger.warning(f"[RAG] 索引初始化失败（非阻塞）: {e}")
    asyncio.create_task(_init_rag())

    yield

    # 关闭 Redis
    await close_redis()

    # 关闭 MongoDB
    await close_mongodb()


app = FastAPI(
    title="美味餐厅",
    description="基于 FastAPI + LangGraph 多智能体架构 + 智谱 AI 的美味餐厅",
    version="3.0.0",
    lifespan=lifespan,
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """统一业务异常处理"""
    logger.warning(f"[Exception] {exc.status_code}: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )

# CORS 配置：开发模式允许所有来源但不允许携带凭证，生产模式从环境变量读取
is_prod = os.environ.get("SERVE_STATIC", "false").lower() == "true"
if is_prod:
    # 生产环境建议配置具体域名
    cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
    allow_creds = os.environ.get("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
else:
    cors_origins = ["*"]
    allow_creds = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_creds,
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


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "美味餐厅"}


# 生产模式：托管前端静态文件（必须在 API 路由之后挂载，保证 API 优先）
if is_prod:
    static_dir = os.environ.get("STATIC_DIR", "../frontend/dist")
    if os.path.isdir(static_dir):
        # 挂载静态文件目录；html=True 表示对于不存在的路径自动返回 index.html
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
        print(f"[生产模式] 已挂载静态文件目录: {static_dir}")
    else:
        print(f"[警告] 生产模式静态文件目录不存在: {static_dir}")
else:
    @app.get("/")
    async def root():
        """开发模式 API 根路径信息"""
        return {"message": "欢迎使用美味餐厅 API", "docs": "/docs", "version": "3.0.0"}
