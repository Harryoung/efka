"""
Main application entry point for EFKA - Embed-Free Knowledge Agent.
"""
# ⚠️ 必须在导入任何模块之前先设置环境变量
# 这样可以确保子 Agent 也能获得认证信息
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 立即导出认证环境变量到进程环境
# 这样所有子进程（包括子 Agent）都能访问
if os.getenv("ANTHROPIC_AUTH_TOKEN"):
    os.environ["ANTHROPIC_AUTH_TOKEN"] = os.getenv("ANTHROPIC_AUTH_TOKEN")
    print(f"✅ ANTHROPIC_AUTH_TOKEN loaded (ends with: ...{os.getenv('ANTHROPIC_AUTH_TOKEN')[-4:]})")

if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ["ANTHROPIC_BASE_URL"] = os.getenv("ANTHROPIC_BASE_URL")
    print(f"✅ ANTHROPIC_BASE_URL loaded: {os.getenv('ANTHROPIC_BASE_URL')}")

if os.getenv("CLAUDE_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = os.getenv("CLAUDE_API_KEY")
    print(f"✅ ANTHROPIC_API_KEY loaded (ends with: ...{os.getenv('CLAUDE_API_KEY')[-4:]})")

# 现在可以安全地导入其他模块
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.config.settings import settings
from backend.services.kb_service_factory import get_admin_service, get_user_service
from backend.services.session_manager import get_session_manager
from backend.storage.redis_storage import RedisSessionStorage

# 配置日志
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("Starting EFKA (知了) - Embed-Free Knowledge Agent...")

    # 初始化 Redis 存储（如果配置了 REDIS_URL）
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    redis_username = os.getenv("REDIS_USERNAME")
    redis_password = os.getenv("REDIS_PASSWORD")
    if redis_password:
        logger.info(
            "Redis 认证已启用（用户名: %s）",
            redis_username or "<default>"
        )
    redis_storage = RedisSessionStorage(
        redis_url=redis_url,
        username=redis_username,
        password=redis_password
    )

    # 初始化 SessionManager 并注入 Redis 存储
    session_manager = get_session_manager()
    session_manager.storage = redis_storage

    try:
        await session_manager.initialize_storage()
        logger.info(f"✅ Redis 存储初始化成功: {redis_url}")
    except Exception as e:
        logger.warning(f"⚠️  Redis 存储初始化失败: {e}, 将使用内存存储")
        logger.info("✅ 内存存储初始化成功")

    # 初始化 Admin Service（双 Agent 架构）
    admin_service = get_admin_service()
    await admin_service.initialize()
    logger.info("Admin Service initialized (kb_admin_agent.py)")

    # 初始化 User Service（双 Agent 架构）
    user_service = get_user_service()
    await user_service.initialize()
    logger.info("User Service initialized (kb_qa_agent.py)")

    # 启动 SessionManager 清理任务
    await session_manager.start_cleanup_task()
    logger.info("SessionManager cleanup task started")

    logger.info("Application startup complete")

    yield

    # 关闭时清理
    logger.info("Shutting down...")
    await session_manager.stop_cleanup_task()
    logger.info("Application shutdown complete")


# 创建FastAPI应用
app = FastAPI(
    title="EFKA 知了",
    version="2.0.0",
    description="Embed-Free Knowledge Agent - 无需向量数据库，让 Agent 直接阅读你的文件",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from backend.api.query import router as query_router
from backend.api.upload import router as upload_router
from backend.api.user import router as user_router

app.include_router(query_router)
app.include_router(upload_router)
app.include_router(user_router)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )


# 健康检查端点
@app.get("/health")
async def health_check():
    """系统健康检查端点"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "service": "EFKA 知了"
    }


# 系统信息端点
@app.get("/info")
async def system_info():
    """返回系统配置信息"""
    return {
        "kb_root_path": settings.KB_ROOT_PATH,
        "small_file_threshold_kb": settings.SMALL_FILE_KB_THRESHOLD,
        "faq_max_entries": settings.FAQ_MAX_ENTRIES,
        "session_timeout": settings.SESSION_TIMEOUT,
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE / 1024 / 1024
    }


# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Welcome to EFKA 知了 - Embed-Free Knowledge Agent",
        "version": "2.0.0",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower()
    )
