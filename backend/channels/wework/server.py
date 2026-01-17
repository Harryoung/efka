"""
WeChat Work (企业微信) Callback Server (Flask)

Independent Flask process listening on WEWORK_PORT (default 8081)
Responsibilities:
1. URL verification (GET)
2. Message receiving (POST)
3. Call adapter to parse messages
4. Forward to User Agent via channel router
"""

import asyncio
import logging
import threading
import sys
from pathlib import Path

# Set event loop policy (Windows compatibility)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Load environment variables
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

# Global adapter instance
adapter: WeWorkAdapter = None

# Global event loop (for running async tasks in Flask sync context)
_event_loop = None
_loop_thread = None


def start_event_loop(loop):
    """Run event loop in a separate thread"""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def get_event_loop():
    """Get global event loop"""
    return _event_loop


async def initialize_services():
    """Initialize services"""
    global adapter

    logger.info("Initializing WeWork callback server...")

    # Initialize adapter
    adapter = WeWorkAdapter()

    if not adapter.is_configured():
        logger.error("❌ WeWork adapter is not configured!")
        logger.error("   Required environment variables:")
        for var in adapter.get_required_env_vars():
            logger.error(f"   - {var}")
        raise ValueError("WeWork adapter not configured")

    await adapter.initialize()
    logger.info("✅ WeWork adapter initialized")

    # Initialize global services in wework_callback.py
    # This sets up user_service and state_manager global variables
    from backend.api.wework_callback import init_services as init_callback_services
    init_callback_services()
    logger.info("✅ Callback services initialized (user_service, state_manager)")

    # Ensure User Service is initialized
    from backend.services.kb_service_factory import get_user_service
    from backend.services.conversation_state_manager import get_conversation_state_manager
    from backend.storage.redis_storage import RedisSessionStorage

    user_service = get_user_service()
    await user_service.initialize()
    logger.info("✅ User service initialized")

    # Initialize Conversation State Manager (Redis storage)
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
    """WeChat Work callback entry point"""

    if request.method == 'GET':
        # URL verification
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
        # Message receiving
        msg_signature = request.args.get('msg_signature')
        timestamp = request.args.get('timestamp')
        nonce = request.args.get('nonce')
        xml_content = request.data.decode('utf-8')

        try:
            # Use adapter to parse message
            request_data = {
                "xml_content": xml_content,
                "msg_signature": msg_signature,
                "timestamp": timestamp,
                "nonce": nonce
            }

            # Process message asynchronously (don't block callback response)
            run_async_task(process_message(request_data))

            # Return success immediately
            response = make_response("success")
            response.headers['Content-Type'] = 'text/plain'
            return response

        except Exception as e:
            logger.error(f"Message processing failed: {str(e)}", exc_info=True)
            return f"Message processing failed: {str(e)}", 500


def run_async_task(coro):
    """Run async task in a separate thread"""
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
    Process WeChat Work message (using adapter)

    Flow:
    1. Parse message → ChannelMessage
    2. Forward to channel router
    3. Channel router calls User Agent
    4. Agent response sent back to WeChat Work via adapter
    """
    try:
        # Parse message
        channel_msg = await adapter.parse_message(request_data)
        logger.info(f"Parsed message from {channel_msg.user.user_id}: {channel_msg.content[:50]}...")

        # Only process text messages
        if channel_msg.msg_type != "text":
            logger.info(f"Ignoring non-text message: {channel_msg.msg_type}")
            return

        # TODO: This should forward to User Agent via channel router
        # Currently keeping the original direct call logic (backward compatible)
        from backend.api.wework_callback import process_wework_message
        await process_wework_message(channel_msg.raw_data)

    except Exception as e:
        logger.error(f"Failed to process message: {e}", exc_info=True)


def main():
    """Main function"""
    global _event_loop, _loop_thread

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Get configuration
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
    logger.info(f"🚀 Starting WeChat Work callback server on port {wework_port}...")
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
