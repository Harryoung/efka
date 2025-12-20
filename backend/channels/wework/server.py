"""
企业微信回调服务器(Flask)

独立的Flask进程,监听WEWORK_PORT(默认8081)
负责:
1. URL验证(GET)
2. 消息接收(POST)
3. 调用适配器解析消息
4. 通过渠道路由器转发给User Agent
"""

import asyncio
import logging
import threading
import sys
from pathlib import Path

# 设置事件循环策略(Windows兼容)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 加载环境变量
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, make_response
import xml.etree.ElementTree as ET

from backend.channels.wework.adapter import WeWorkAdapter
from backend.utils.wework_crypto import verify_url
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

app = Flask(__name__)
settings = get_settings()

# 全局适配器实例
adapter: WeWorkAdapter = None

# 全局event loop(用于在Flask同步上下文中运行异步任务)
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
    """初始化服务"""
    global adapter

    logger.info("Initializing WeWork callback server...")

    # 初始化适配器
    adapter = WeWorkAdapter()

    if not adapter.is_configured():
        logger.error("❌ WeWork adapter is not configured!")
        logger.error("   Required environment variables:")
        for var in adapter.get_required_env_vars():
            logger.error(f"   - {var}")
        raise ValueError("WeWork adapter not configured")

    await adapter.initialize()
    logger.info("✅ WeWork adapter initialized")

    # 初始化 wework_callback.py 中的全局服务
    # 这会设置 user_service 和 state_manager 全局变量
    from backend.api.wework_callback import init_services as init_callback_services
    init_callback_services()
    logger.info("✅ Callback services initialized (user_service, state_manager)")

    # 确保 User Service 已初始化
    from backend.services.kb_service_factory import get_user_service
    from backend.services.conversation_state_manager import get_conversation_state_manager
    from backend.storage.redis_storage import RedisSessionStorage

    user_service = get_user_service()
    await user_service.initialize()
    logger.info("✅ User service initialized")

    # 初始化Conversation State Manager(Redis存储)
    try:
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

    except Exception as e:
        logger.warning(f"Redis initialization failed: {e}, using memory fallback")
        state_manager = get_conversation_state_manager(
            kb_root=Path(settings.KB_ROOT_PATH),
            storage=None
        )
        logger.info("✅ Conversation state manager initialized with memory storage")

    logger.info("✅ All WeWork callback services initialized")


@app.route('/api/wework/callback', methods=['GET', 'POST'])
def wework_callback():
    """企微回调入口"""

    if request.method == 'GET':
        # URL验证
        msg_signature = request.args.get('msg_signature')
        timestamp = request.args.get('timestamp')
        nonce = request.args.get('nonce')
        echo_str = request.args.get('echostr')

        if not all([msg_signature, timestamp, nonce, echo_str]):
            logger.error("URL validation: Missing parameters")
            return "Missing parameters", 400

        try:
            decrypted_echo = verify_url(
                msg_signature, timestamp, nonce, echo_str,
                adapter.token, adapter.encoding_aes_key, adapter.corp_id
            )
            response = make_response(decrypted_echo)
            response.headers['Content-Type'] = 'text/plain'
            logger.info("✅ URL validation successful")
            return response
        except Exception as e:
            logger.error(f"URL validation failed: {str(e)}")
            return f"Verification failed: {str(e)}", 400

    elif request.method == 'POST':
        # 消息接收
        msg_signature = request.args.get('msg_signature')
        timestamp = request.args.get('timestamp')
        nonce = request.args.get('nonce')
        xml_content = request.data.decode('utf-8')

        try:
            # 使用适配器解析消息
            request_data = {
                "xml_content": xml_content,
                "msg_signature": msg_signature,
                "timestamp": timestamp,
                "nonce": nonce
            }

            # 异步处理消息(不阻塞回调响应)
            run_async_task(process_message(request_data))

            # 立即返回成功
            response = make_response("success")
            response.headers['Content-Type'] = 'text/plain'
            return response

        except Exception as e:
            logger.error(f"Message processing failed: {str(e)}", exc_info=True)
            return f"Message processing failed: {str(e)}", 500


def run_async_task(coro):
    """在独立线程中运行异步任务"""
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            logger.info(f"🚀 Starting async task in thread {threading.current_thread().name}")
            loop.run_until_complete(coro)
            logger.info(f"✅ Async task completed successfully")
        except Exception as e:
            logger.error(f"❌ Async task failed: {type(e).__name__}: {str(e)}", exc_info=True)
        finally:
            loop.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


async def process_message(request_data: dict):
    """
    处理企微消息(使用适配器)

    流程:
    1. 解析消息 → ChannelMessage
    2. 转发给渠道路由器
    3. 渠道路由器调用User Agent
    4. Agent响应通过适配器发送回企微
    """
    try:
        # 解析消息
        channel_msg = await adapter.parse_message(request_data)
        logger.info(f"Parsed message from {channel_msg.user.user_id}: {channel_msg.content[:50]}...")

        # 仅处理文本消息
        if channel_msg.msg_type != "text":
            logger.info(f"Ignoring non-text message: {channel_msg.msg_type}")
            return

        # TODO: 这里应该通过渠道路由器转发给User Agent
        # 目前保留原有的直接调用逻辑(向后兼容)
        from backend.api.wework_callback import process_wework_message
        await process_wework_message(channel_msg.raw_data)

    except Exception as e:
        logger.error(f"Failed to process message: {e}", exc_info=True)


def main():
    """主函数"""
    global _event_loop, _loop_thread

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 获取配置
    wework_port = settings.WEWORK_PORT

    # 创建并启动event loop线程
    _event_loop = asyncio.new_event_loop()
    _loop_thread = threading.Thread(target=start_event_loop, args=(_event_loop,), daemon=True)
    _loop_thread.start()
    logger.info("✅ Event loop thread started")

    # 在event loop中初始化服务
    future = asyncio.run_coroutine_threadsafe(initialize_services(), _event_loop)
    try:
        future.result(timeout=30)  # 等待初始化完成(最多30秒)
    except Exception as e:
        logger.error(f"❌ Service initialization failed: {e}", exc_info=True)
        sys.exit(1)

    # 启动Flask服务器
    logger.info(f"🚀 Starting WeChat Work callback server on port {wework_port}...")
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
