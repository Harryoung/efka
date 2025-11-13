"""
WeChat Work Callback Server - 企业微信消息接收服务

独立的Flask进程，监听可配置端口（默认8081）
与FastAPI主服务（8000端口）独立运行

启动命令:
    python3 -m backend.wework_server
"""

import asyncio
import logging
import threading
from pathlib import Path
import sys

# 设置事件循环策略（解决Flask + asyncio兼容性问题）
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 导入配置（必须在导入其他模块之前加载环境变量）
import os
from dotenv import load_dotenv
load_dotenv()

from backend.api.wework_callback import app, init_services
from backend.services.kb_service_factory import KBServiceFactory, get_employee_service
from backend.services.conversation_state_manager import get_conversation_state_manager
from backend.storage.redis_storage import RedisSessionStorage
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

# 全局event loop（用于在Flask同步上下文中运行异步任务）
_event_loop = None
_loop_thread = None


def start_event_loop(loop):
    """在独立线程中运行event loop"""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def get_event_loop():
    """获取全局event loop"""
    return _event_loop


async def initialize_services():
    """初始化所有服务"""
    settings = get_settings()

    logger.info("Initializing WeWork server services...")

    # 初始化Employee Service
    employee_service = get_employee_service()
    await employee_service.initialize()
    logger.info("✅ Employee service initialized")

    # 初始化Conversation State Manager（Redis存储）
    try:
        redis_storage = RedisSessionStorage(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
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

    except Exception as e:
        logger.warning(f"Redis initialization failed: {e}, using memory fallback")
        state_manager = get_conversation_state_manager(
            kb_root=Path(settings.KB_ROOT_PATH),
            storage=None
        )
        logger.info("✅ Conversation state manager initialized with memory storage")

    # 初始化wework_callback中的服务
    init_services()
    logger.info("✅ WeWork callback services initialized")

    logger.info("✅ All WeWork server services initialized successfully")


def main():
    """主函数"""
    global _event_loop, _loop_thread

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 获取配置
    settings = get_settings()
    wework_port = settings.WEWORK_PORT

    # 创建并启动event loop线程
    _event_loop = asyncio.new_event_loop()
    _loop_thread = threading.Thread(target=start_event_loop, args=(_event_loop,), daemon=True)
    _loop_thread.start()
    logger.info("✅ Event loop thread started")

    # 在event loop中初始化服务
    future = asyncio.run_coroutine_threadsafe(initialize_services(), _event_loop)
    try:
        future.result(timeout=30)  # 等待初始化完成（最多30秒）
    except Exception as e:
        logger.error(f"❌ Service initialization failed: {e}", exc_info=True)
        sys.exit(1)

    # 启动Flask服务器
    logger.info(f"Starting WeChat Work callback server on port {wework_port}...")
    try:
        app.run(host='0.0.0.0', port=wework_port, debug=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("Shutting down WeWork server...")
    finally:
        # 清理
        if _event_loop:
            _event_loop.call_soon_threadsafe(_event_loop.stop)
        logger.info("✅ WeWork server stopped")


if __name__ == '__main__':
    main()
