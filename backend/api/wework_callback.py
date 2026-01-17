"""
WeChat Work Callback API - WeChat Work (企业微信) Message Receiving

Responsibilities:
1. URL verification (GET request)
2. Message receiving and decryption (POST request)
3. Session state checking (distinguish employee questions from expert replies)
4. Call User Agent for processing
"""

from flask import Flask, request, make_response
from typing import Optional, Dict
import xml.etree.ElementTree as ET
import asyncio
import time
from pathlib import Path
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from backend.utils.wework_crypto import verify_url, decrypt_message, parse_message
from backend.services.kb_service_factory import get_user_service
from backend.services.conversation_state_manager import get_conversation_state_manager
from backend.services.user_identity_service import get_user_identity_service
from backend.services.session_router_service import get_session_router_service
from backend.services.routing_session_manager import get_routing_session_manager
from backend.services.audit_logger import get_audit_logger
from backend.services.session_manager import get_session_manager
from backend.config.settings import get_settings
from backend.models.session import SessionRole, SessionStatus, MessageSnapshot
from claude_agent_sdk import AssistantMessage, TextBlock, ResultMessage
from datetime import datetime
import re
import json

logger = logging.getLogger(__name__)

app = Flask(__name__)
settings = get_settings()

# WeChat Work configuration (loaded from environment variables)
WEWORK_TOKEN = settings.WEWORK_TOKEN
WEWORK_ENCODING_AES_KEY = settings.WEWORK_ENCODING_AES_KEY
WEWORK_CORP_ID = settings.WEWORK_CORP_ID

# Initialize services (will be done in wework_server.py)
user_service = None
state_manager = None

# Thread pool executor (for running async tasks)
executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="wework_async")


def init_services():
    """Initialize services (called by wework_server.py)"""
    global user_service, state_manager
    user_service = get_user_service()
    state_manager = get_conversation_state_manager(
        kb_root=Path(settings.KB_ROOT_PATH)
    )


def run_async_task(coro):
    """
    Run async task in a separate thread

    Solves compatibility issues between Flask sync context and asyncio
    """
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            logger.info(f"🚀 Starting async task in thread {threading.current_thread().name}")
            loop.run_until_complete(coro)
            logger.info(f"✅ Async task completed successfully")
        except Exception as e:
            logger.error(f"❌ Async task failed with exception")
            logger.error(f"   Exception type: {type(e).__name__}")
            logger.error(f"   Exception message: {str(e)}")
            logger.error(f"   Thread: {threading.current_thread().name}", exc_info=True)
        finally:
            loop.close()
            logger.debug(f"🔒 Event loop closed")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    logger.debug(f"🧵 Created async task thread: {thread.name}")


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
                WEWORK_TOKEN, WEWORK_ENCODING_AES_KEY, WEWORK_CORP_ID
            )
            response = make_response(decrypted_echo)
            response.headers['Content-Type'] = 'text/plain'
            logger.info("URL validation successful")
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
            # Parse XML to get encrypted content
            root = ET.fromstring(xml_content)
            encrypt_element = root.find('Encrypt')
            encrypt_str = encrypt_element.text if encrypt_element is not None else ""

            # Decrypt message
            decrypted_msg = decrypt_message(
                encrypt_str,
                WEWORK_ENCODING_AES_KEY,
                WEWORK_CORP_ID
            )

            # Parse message
            message_data = parse_message(decrypted_msg)
            logger.info(f"Received message from {message_data.get('FromUserName')}: {message_data.get('MsgType')}")

            # Process message asynchronously (don't block callback response)
            # Run async task in separate thread
            run_async_task(process_wework_message(message_data))
            logger.info(f"Async task started for message from {message_data.get('FromUserName')}")

            # Return success immediately
            response = make_response("success")
            response.headers['Content-Type'] = 'text/plain'
            return response

        except Exception as e:
            logger.error(f"Message processing failed: {str(e)}", exc_info=True)
            return f"Message processing failed: {str(e)}", 500


async def process_wework_message(message_data: dict):
    """
    Process WeChat Work message (refactored version - integrated with Session Router)

    Core logic:
    1. User identity recognition (new)
    2. Session Router determines session_id (new)
    3. Low confidence logging (new)
    4. Get or create Session (refactored)
    5. Call User Agent (refactored)
    6. Async update Session summary (new)
    """

    message_type = message_data.get('MsgType')
    sender_userid = message_data.get('FromUserName')

    # Only process text messages
    if message_type != 'text':
        logger.info(f"Ignoring non-text message type: {message_type}")
        return

    content = message_data.get('Content', '')
    logger.info(f"Processing text message from {sender_userid}: {content[:50]}...")

    try:
        # Step 1: User identity recognition (new)
        identity_service = get_user_identity_service()
        user_info = await identity_service.identify_user_role(sender_userid)
        logger.info(f"User identity: is_expert={user_info['is_expert']}, domains={user_info['expert_domains']}")

        # Step 2: Session Router determines session_id (new)
        router_service = get_session_router_service()

        # Ensure router service is initialized
        if not hasattr(router_service, 'is_initialized') or not router_service.is_initialized:
            await router_service.initialize()
            logger.info("Session Router service initialized")

        routing_result = await router_service.route_to_session(
            user_id=sender_userid,
            new_message=content,
            user_info=user_info
        )
        logger.info(f"Routing decision: {routing_result['decision']} (confidence={routing_result['confidence']})")

        # Step 3: Low confidence logging (new)
        if routing_result['confidence'] < 0.7:
            audit_logger = get_audit_logger()
            await audit_logger.log_low_confidence_routing(
                user_id=sender_userid,
                message=content,
                result=routing_result,
                audit_required=True
            )

        # Step 4: Get or create Session (refactored)
        routing_mgr = get_routing_session_manager()

        # Ensure routing manager is initialized
        if not hasattr(routing_mgr, 'is_initialized') or not routing_mgr.is_initialized:
            await routing_mgr.initialize()
            logger.info("Routing Session Manager initialized")

        if routing_result['decision'] == 'NEW_SESSION':
            # Create new Session
            # Determine role
            if user_info['is_expert'] and routing_result.get('matched_role') == 'expert':
                role = SessionRole.EXPERT
            elif user_info['is_expert']:
                role = SessionRole.EXPERT_AS_USER
            else:
                role = SessionRole.USER

            session = await routing_mgr.create_session(
                user_id=sender_userid,
                role=role,
                original_question=content
            )
            session_id = session.session_id
            logger.info(f"Created new session {session_id} for {sender_userid} (role={role.value})")
        else:
            session_id = routing_result['decision']
            logger.info(f"Matched existing session {session_id} for {sender_userid}")

        # Step 5: Call User Agent (refactored)
        # Ensure user_service is initialized
        if not user_service.is_initialized:
            await user_service.initialize()
            logger.info("User service initialized")

        # Get SDK session ID (for resume, note: this is different from routing session_id!)
        # - routing session_id (sess_xxx format): for business layer session routing
        # - sdk_session_id (UUID format): for Claude SDK --resume parameter to restore context
        session_mgr = get_session_manager()
        sdk_session_id = await session_mgr.get_or_create_user_session(sender_userid)
        is_new_sdk_session = sdk_session_id is None
        logger.info(f"SDK session: {sdk_session_id or 'new'} (is_new={is_new_sdk_session}), routing_session: {session_id}")

        # Construct message with user info
        user_name = user_info.get('name', '')
        name_display = f"{user_name}" if user_name else sender_userid

        formatted_message = f"""[User Info]
user_id: {sender_userid}
name: {name_display}

[User Message]
{content}"""

        # Collect Agent response and metadata
        agent_response_text = ""
        metadata = None
        message_count = 0
        real_sdk_session_id = None  # Real SDK session ID extracted from ResultMessage

        logger.info(f"Calling User Agent (routing_session={session_id}, sdk_session={sdk_session_id or 'new'})")
        logger.info(f"📞 About to call user_service.query()...")

        try:
            logger.info(f"🔄 Entering async for loop to receive messages...")
            async for message in user_service.query(
                user_message=formatted_message,
                sdk_session_id=sdk_session_id,  # Pass SDK session ID (or None for new session)
                user_id=sender_userid
            ):
                message_count += 1
                msg_type = type(message).__name__

                # Handle AssistantMessage - contains actual response content
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            logger.info(f"📨 Received TextBlock from AssistantMessage (text_len={len(block.text)})")
                            agent_response_text += block.text

                            # Check if metadata block is present
                            if "```metadata" in block.text:
                                metadata = extract_metadata(block.text)
                                logger.info(f"✅ Metadata extracted from TextBlock")

                # Handle ResultMessage - contains session metadata and real SDK session ID
                elif isinstance(message, ResultMessage):
                    real_sdk_session_id = getattr(message, 'session_id', None)
                    logger.info(f"📨 Received ResultMessage: sdk_session_id={real_sdk_session_id}, cost={getattr(message, 'total_cost_usd', None)}")

                # Other message types (e.g., SystemMessage) - just log
                else:
                    logger.debug(f"📨 Received message {message_count}: type={msg_type} (ignored)")

            logger.info(f"✅ Async for loop completed, total messages: {message_count}")

            # Save real SDK session ID (for next resume)
            if real_sdk_session_id:
                await session_mgr.save_sdk_session_id(sender_userid, real_sdk_session_id)
                logger.info(f"Saved SDK session ID for user {sender_userid}: {real_sdk_session_id}")

            # Check if response was received
            if message_count == 0:
                logger.error(f"❌ No response from User Agent for user {sender_userid}")
                logger.error(f"   Routing Session ID: {session_id}")
                logger.error(f"   SDK Session ID: {sdk_session_id or 'new'}")
                logger.error(f"   This may indicate:")
                logger.error(f"   - API account insufficient balance")
                logger.error(f"   - API rate limit exceeded")
                logger.error(f"   - Network timeout")
                logger.error(f"   - API service unavailable")
                return
            else:
                logger.info(f"✅ Received {message_count} messages from User Agent")

        except asyncio.TimeoutError:
            logger.error(f"❌ User Agent call timeout for user {sender_userid}")
            logger.error(f"   Session ID: {session_id}")
            logger.error(f"   Message: {content[:100]}...")
            logger.error(f"   This may indicate:")
            logger.error(f"   - Network connectivity issues")
            logger.error(f"   - API service overload")
            return
        except Exception as agent_error:
            logger.error(f"❌ User Agent call failed for user {sender_userid}")
            logger.error(f"   Error type: {type(agent_error).__name__}")
            logger.error(f"   Error message: {str(agent_error)}")
            logger.error(f"   Session ID: {session_id}")
            logger.error(f"   Message: {content[:100]}...")
            logger.error(f"   This may indicate:")
            logger.error(f"   - Invalid API key or token")
            logger.error(f"   - API account insufficient balance")
            logger.error(f"   - Exceeded rate limits")
            logger.error(f"   - API service unavailable")
            return

        # Step 6: Async update Session summary (new)
        if metadata:
            # Create message snapshots
            user_snapshot = MessageSnapshot(
                content=content,
                timestamp=datetime.now(),
                role="user"
            )

            agent_snapshot = MessageSnapshot(
                content=agent_response_text[:200],  # Truncate to avoid excessive length
                timestamp=datetime.now(),
                role="agent"
            )

            # Update user message
            await routing_mgr.update_session_summary(
                session_id=session_id,
                new_message=user_snapshot
            )

            # Update Agent reply (with key_points and status)
            session_status = SessionStatus.RESOLVED if metadata.get('session_status') == 'resolved' else None

            await routing_mgr.update_session_summary(
                session_id=session_id,
                new_message=agent_snapshot,
                key_points=metadata.get('key_points', []),
                session_status=session_status
            )

            logger.info(f"Session {session_id} summary updated with metadata")
        else:
            logger.warning(f"No metadata found in agent response for session {session_id}")

        logger.info(f"Message processing completed for {sender_userid}")

    except Exception as e:
        logger.error(f"Error processing message from {sender_userid}: {str(e)}", exc_info=True)


def extract_metadata(text: str) -> Optional[Dict]:
    """
    Extract metadata from Agent response

    Args:
        text: Agent response text

    Returns:
        Metadata dictionary, returns None if parsing fails
    """
    # Match ```metadata ... ``` block
    pattern = r'```metadata\s*\n(.*?)\n```'
    match = re.search(pattern, text, re.DOTALL)

    if match:
        try:
            metadata_json = match.group(1)
            metadata = json.loads(metadata_json)

            # Verify required fields
            assert 'key_points' in metadata
            assert 'answer_source' in metadata
            assert 'session_status' in metadata

            return metadata
        except Exception as e:
            logger.error(f"Failed to parse metadata: {e}")
            logger.error(f"Metadata text: {match.group(1)}")
            return None
    else:
        return None


if __name__ == '__main__':
    wework_port = settings.WEWORK_PORT
    app.run(host='0.0.0.0', port=wework_port, debug=False)
