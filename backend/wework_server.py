"""
WeChat Work Callback Server - WeWork (企业微信) Message Receiving Service

Independent Flask process, listens on configurable port (default 8081)
Runs independently from FastAPI main service (port 8000)

Start command:
    python3 -m backend.wework_server
"""

import asyncio
import logging
import threading
from pathlib import Path
import sys

# Set event loop policy (solves Flask + asyncio compatibility issue)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Import config (must load environment variables before importing other modules)
import os
from dotenv import load_dotenv
load_dotenv()

from backend.api.wework_callback import app, init_services
from backend.services.kb_service_factory import KBServiceFactory, get_user_service
from backend.services.conversation_state_manager import get_conversation_state_manager
from backend.services.session_manager import get_session_manager
from backend.storage.redis_storage import RedisSessionStorage
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

# Global event loop (used to run async tasks in Flask sync context)
_event_loop = None
_loop_thread = None


def start_event_loop(loop):
    """Run event loop in dedicated thread"""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def get_event_loop():
    """Get global event loop"""
    return _event_loop


async def initialize_services():
    """Initialize all services"""
    settings = get_settings()

    logger.info("Initializing WeWork server services...")

    # Initialize User Service
    user_service = get_user_service()
    await user_service.initialize()
    logger.info("✅ User service initialized")

    # Initialize Conversation State Manager (Redis storage)
    try:
        # Build Redis URL
        redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"

        redis_storage = RedisSessionStorage(
            redis_url=redis_url,
            ttl_seconds=settings.CONVERSATION_STATE_TTL,
            password=settings.REDIS_PASSWORD,
            username=settings.REDIS_USERNAME
        )
        await redis_storage.connect()
        logger.info("✅ Redis storage connected")

        state_manager = get_conversation_state_manager(
            kb_root=Path(settings.KB_ROOT_PATH),
            storage=redis_storage
        )
        await state_manager.initialize_storage()
        logger.info("✅ Conversation state manager initialized with Redis")

        # Initialize Session Manager (for SDK session ID management)
        session_manager = get_session_manager()
        session_manager.storage = redis_storage
        await session_manager.initialize_storage()
        logger.info("✅ Session manager initialized with Redis")

    except Exception as e:
        logger.warning(f"Redis initialization failed: {e}, using memory fallback")
        state_manager = get_conversation_state_manager(
            kb_root=Path(settings.KB_ROOT_PATH),
            storage=None
        )
        logger.info("✅ Conversation state manager initialized with memory storage")

        # Initialize Session Manager (memory fallback mode)
        session_manager = get_session_manager()
        await session_manager.initialize_storage()
        logger.info("✅ Session manager initialized with memory storage")

    # Initialize services in wework_callback
    init_services()
    logger.info("✅ WeWork callback services initialized")

    logger.info("✅ All WeWork server services initialized successfully")


def main():
    """Main function"""
    global _event_loop, _loop_thread

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Get configuration
    settings = get_settings()
    wework_port = settings.WEWORK_PORT

    # Create and start event loop thread
    _event_loop = asyncio.new_event_loop()
    _loop_thread = threading.Thread(target=start_event_loop, args=(_event_loop,), daemon=True)
    _loop_thread.start()
    logger.info("✅ Event loop thread started")

    # Initialize services in event loop
    future = asyncio.run_coroutine_threadsafe(initialize_services(), _event_loop)
    try:
        future.result(timeout=30)  # Wait for initialization (max 30 seconds)
    except Exception as e:
        logger.error(f"❌ Service initialization failed: {e}", exc_info=True)
        sys.exit(1)

    # Start Flask server
    logger.info(f"Starting WeChat Work callback server on port {wework_port}...")
    try:
        app.run(host='0.0.0.0', port=wework_port, debug=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("Shutting down WeWork server...")
    finally:
        # Cleanup
        if _event_loop:
            _event_loop.call_soon_threadsafe(_event_loop.stop)
        logger.info("✅ WeWork server stopped")


if __name__ == '__main__':
    main()
