"""
Main application entry point for EFKA - Embed-Free Knowledge Agent.
"""
# ⚠️ Must set environment variables before importing any modules
# This ensures that sub-Agents can also obtain authentication information
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Parse --mode argument (must be before other imports)
from backend.config.run_mode import set_cli_mode, get_run_mode, get_im_channel

for i, arg in enumerate(sys.argv):
    if arg in ["--mode", "-m"] and i + 1 < len(sys.argv):
        try:
            set_cli_mode(sys.argv[i + 1])
            print(f"✅ Run mode set via CLI: {sys.argv[i + 1]}")
        except ValueError as e:
            print(f"❌ Invalid run mode: {e}")
            sys.exit(1)
        break

# Immediately export authentication environment variables to process environment
# This allows all subprocesses (including sub-Agents) to access them
if os.getenv("ANTHROPIC_AUTH_TOKEN"):
    os.environ["ANTHROPIC_AUTH_TOKEN"] = os.getenv("ANTHROPIC_AUTH_TOKEN")
    print(f"✅ ANTHROPIC_AUTH_TOKEN loaded (ends with: ...{os.getenv('ANTHROPIC_AUTH_TOKEN')[-4:]})")

if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ["ANTHROPIC_BASE_URL"] = os.getenv("ANTHROPIC_BASE_URL")
    print(f"✅ ANTHROPIC_BASE_URL loaded: {os.getenv('ANTHROPIC_BASE_URL')}")

if os.getenv("CLAUDE_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = os.getenv("CLAUDE_API_KEY")
    print(f"✅ ANTHROPIC_API_KEY loaded (ends with: ...{os.getenv('CLAUDE_API_KEY')[-4:]})")

# Now it's safe to import other modules
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.config.settings import settings
from backend.services.kb_service_factory import get_admin_service, get_user_service
from backend.services.session_manager import get_session_manager
from backend.storage.redis_storage import RedisSessionStorage

# Configure logging
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
    """Application lifecycle management"""
    # Initialize on startup
    run_mode = get_run_mode()
    im_channel = get_im_channel()

    logger.info("Starting EFKA (Zhiliao/知了) - Embed-Free Knowledge Agent...")
    logger.info(f"Run mode: {run_mode.value}")

    if run_mode.value == "standalone":
        logger.info("Standalone mode: IM features disabled")
    else:
        logger.info(f"IM mode: {im_channel} channel enabled")

    # Initialize Redis storage (if REDIS_URL is configured)
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    redis_username = os.getenv("REDIS_USERNAME")
    redis_password = os.getenv("REDIS_PASSWORD")
    if redis_password:
        logger.info(
            "Redis authentication enabled (username: %s)",
            redis_username or "<default>"
        )
    redis_storage = RedisSessionStorage(
        redis_url=redis_url,
        username=redis_username,
        password=redis_password
    )

    # Initialize SessionManager and inject Redis storage
    session_manager = get_session_manager()
    session_manager.storage = redis_storage

    try:
        await session_manager.initialize_storage()
        logger.info(f"✅ Redis storage initialized successfully: {redis_url}")
    except Exception as e:
        logger.warning(f"⚠️  Redis storage initialization failed: {e}, will use in-memory storage")
        logger.info("✅ In-memory storage initialized successfully")

    # Initialize Admin Service (dual Agent architecture)
    admin_service = get_admin_service()
    await admin_service.initialize()
    logger.info("Admin Service initialized (kb_admin_agent.py)")

    # Initialize User Service (dual Agent architecture)
    user_service = get_user_service()
    await user_service.initialize()
    logger.info("User Service initialized (kb_qa_agent.py)")

    # Start SessionManager cleanup task
    await session_manager.start_cleanup_task()
    logger.info("SessionManager cleanup task started")

    logger.info("Application startup complete")

    yield

    # Cleanup on shutdown
    logger.info("Shutting down...")
    await session_manager.stop_cleanup_task()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="EFKA Zhiliao (知了)",
    version="3.0.0",
    description="Embed-Free Knowledge Agent - No vector database needed, let the Agent read your files directly",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
from backend.api.query import router as query_router
from backend.api.upload import router as upload_router
from backend.api.user import router as user_router

app.include_router(query_router)
app.include_router(upload_router)
app.include_router(user_router)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """System health check endpoint"""
    return {
        "status": "healthy",
        "version": "3.0.0",
        "service": "EFKA Zhiliao (知了)",
        "run_mode": get_run_mode().value
    }


# System information endpoint
@app.get("/info")
async def system_info():
    """Return system configuration information"""
    return {
        "run_mode": get_run_mode().value,
        "im_channel": get_im_channel(),
        "kb_root_path": settings.KB_ROOT_PATH,
        "small_file_threshold_kb": settings.SMALL_FILE_KB_THRESHOLD,
        "faq_max_entries": settings.FAQ_MAX_ENTRIES,
        "session_timeout": settings.SESSION_TIMEOUT,
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE / 1024 / 1024
    }


# Root path
@app.get("/")
async def root():
    """Root path"""
    return {
        "message": "Welcome to EFKA Zhiliao (知了) - Embed-Free Knowledge Agent",
        "version": "3.0.0",
        "run_mode": get_run_mode().value,
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
