"""
WeChat Work Callback API - 企业微信消息接收

职责:
1. URL验证（GET请求）
2. 消息接收与解密（POST请求）
3. 会话状态检查（区分员工提问和专家回复）
4. 调用Employee Agent处理
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
from backend.services.kb_service_factory import get_employee_service
from backend.services.conversation_state_manager import get_conversation_state_manager
from backend.services.user_identity_service import get_user_identity_service
from backend.services.session_router_service import get_session_router_service
from backend.services.routing_session_manager import get_routing_session_manager
from backend.services.audit_logger import get_audit_logger
from backend.config.settings import get_settings
from backend.models.session import SessionRole, SessionStatus, MessageSnapshot
from datetime import datetime
import re
import json

logger = logging.getLogger(__name__)

app = Flask(__name__)
settings = get_settings()

# 企微配置（从环境变量加载）
WEWORK_TOKEN = settings.WEWORK_TOKEN
WEWORK_ENCODING_AES_KEY = settings.WEWORK_ENCODING_AES_KEY
WEWORK_CORP_ID = settings.WEWORK_CORP_ID

# 初始化服务（将在wework_server.py中完成）
employee_service = None
state_manager = None

# 线程池执行器（用于运行异步任务）
executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="wework_async")


def init_services():
    """初始化服务（由wework_server.py调用）"""
    global employee_service, state_manager
    employee_service = get_employee_service()
    state_manager = get_conversation_state_manager(
        kb_root=Path(settings.KB_ROOT_PATH)
    )


def run_async_task(coro):
    """
    在独立线程中运行异步任务

    解决Flask同步上下文与asyncio的兼容性问题
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
        # 消息接收
        msg_signature = request.args.get('msg_signature')
        timestamp = request.args.get('timestamp')
        nonce = request.args.get('nonce')

        xml_content = request.data.decode('utf-8')

        try:
            # 解析XML获取加密内容
            root = ET.fromstring(xml_content)
            encrypt_element = root.find('Encrypt')
            encrypt_str = encrypt_element.text if encrypt_element is not None else ""

            # 解密消息
            decrypted_msg = decrypt_message(
                encrypt_str,
                WEWORK_ENCODING_AES_KEY,
                WEWORK_CORP_ID
            )

            # 解析消息
            message_data = parse_message(decrypted_msg)
            logger.info(f"Received message from {message_data.get('FromUserName')}: {message_data.get('MsgType')}")

            # 异步处理消息（不阻塞回调响应）
            # 使用独立线程运行异步任务
            run_async_task(process_wework_message(message_data))
            logger.info(f"Async task started for message from {message_data.get('FromUserName')}")

            # 立即返回成功
            response = make_response("success")
            response.headers['Content-Type'] = 'text/plain'
            return response

        except Exception as e:
            logger.error(f"Message processing failed: {str(e)}", exc_info=True)
            return f"Message processing failed: {str(e)}", 500


async def process_wework_message(message_data: dict):
    """
    处理企微消息（改造版 - 集成Session Router）

    核心逻辑:
    1. 用户身份识别（新增）
    2. Session Router决定session_id（新增）
    3. 低置信度日志记录（新增）
    4. 获取或创建Session（改造）
    5. 调用Employee Agent（改造）
    6. 异步更新Session摘要（新增）
    """

    message_type = message_data.get('MsgType')
    sender_userid = message_data.get('FromUserName')

    # 仅处理文本消息
    if message_type != 'text':
        logger.info(f"Ignoring non-text message type: {message_type}")
        return

    content = message_data.get('Content', '')
    logger.info(f"Processing text message from {sender_userid}: {content[:50]}...")

    try:
        # Step 1: 用户身份识别（新增）
        identity_service = get_user_identity_service()
        user_info = await identity_service.identify_user_role(sender_userid)
        logger.info(f"User identity: is_expert={user_info['is_expert']}, domains={user_info['expert_domains']}")

        # Step 2: Session Router决定session_id（新增）
        router_service = get_session_router_service()

        # 确保router service已初始化
        if not hasattr(router_service, 'is_initialized') or not router_service.is_initialized:
            await router_service.initialize()
            logger.info("Session Router service initialized")

        routing_result = await router_service.route_to_session(
            user_id=sender_userid,
            new_message=content,
            user_info=user_info
        )
        logger.info(f"Routing decision: {routing_result['decision']} (confidence={routing_result['confidence']})")

        # Step 3: 低置信度日志记录（新增）
        if routing_result['confidence'] < 0.7:
            audit_logger = get_audit_logger()
            await audit_logger.log_low_confidence_routing(
                user_id=sender_userid,
                message=content,
                result=routing_result,
                audit_required=True
            )

        # Step 4: 获取或创建Session（改造）
        routing_mgr = get_routing_session_manager()

        # 确保routing manager已初始化
        if not hasattr(routing_mgr, 'is_initialized') or not routing_mgr.is_initialized:
            await routing_mgr.initialize()
            logger.info("Routing Session Manager initialized")

        if routing_result['decision'] == 'NEW_SESSION':
            # 创建新Session
            # 判断角色
            if user_info['is_expert'] and routing_result.get('matched_role') == 'expert':
                role = SessionRole.EXPERT
            elif user_info['is_expert']:
                role = SessionRole.EXPERT_AS_EMPLOYEE
            else:
                role = SessionRole.EMPLOYEE

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

        # Step 5: 调用Employee Agent（改造）
        # 确保employee_service已初始化
        if not employee_service.is_initialized:
            await employee_service.initialize()
            logger.info("Employee service initialized")

        # 构造包含用户信息的消息
        user_name = user_info.get('name', '')
        name_display = f"{user_name}" if user_name else sender_userid

        formatted_message = f"""[用户信息]
user_id: {sender_userid}
name: {name_display}

[用户消息]
{content}"""

        # 收集Agent响应和元数据
        agent_response_text = ""
        metadata = None
        message_count = 0

        logger.info(f"Calling Employee Agent with session {session_id}")
        logger.info(f"📞 About to call employee_service.query()...")

        try:
            logger.info(f"🔄 Entering async for loop to receive messages...")
            async for message in employee_service.query(
                user_message=formatted_message,
                session_id=session_id,
                user_id=sender_userid
            ):
                message_count += 1
                logger.info(f"📨 Received message {message_count} from Employee Agent (text_len={len(message.text)})")
                agent_response_text += message.text

                # 检查是否包含元数据块
                if "```metadata" in message.text:
                    metadata = extract_metadata(message.text)
                    logger.info(f"✅ Metadata extracted from message {message_count}")

            logger.info(f"✅ Async for loop completed, total messages: {message_count}")

            # 检查是否收到响应
            if message_count == 0:
                logger.error(f"❌ No response from Employee Agent for user {sender_userid}")
                logger.error(f"   Session ID: {session_id}")
                logger.error(f"   This may indicate:")
                logger.error(f"   - API account insufficent balance (欠费)")
                logger.error(f"   - API rate limit exceeded")
                logger.error(f"   - Network timeout")
                logger.error(f"   - API service unavailable")
                return
            else:
                logger.info(f"✅ Received {message_count} messages from Employee Agent")

        except asyncio.TimeoutError:
            logger.error(f"❌ Employee Agent call timeout for user {sender_userid}")
            logger.error(f"   Session ID: {session_id}")
            logger.error(f"   Message: {content[:100]}...")
            logger.error(f"   This may indicate:")
            logger.error(f"   - Network connectivity issues")
            logger.error(f"   - API service overload")
            return
        except Exception as agent_error:
            logger.error(f"❌ Employee Agent call failed for user {sender_userid}")
            logger.error(f"   Error type: {type(agent_error).__name__}")
            logger.error(f"   Error message: {str(agent_error)}")
            logger.error(f"   Session ID: {session_id}")
            logger.error(f"   Message: {content[:100]}...")
            logger.error(f"   This may indicate:")
            logger.error(f"   - Invalid API key or token")
            logger.error(f"   - API account insufficent balance (欠费)")
            logger.error(f"   - Exceeded rate limits")
            logger.error(f"   - API service unavailable")
            return

        # Step 6: 异步更新Session摘要（新增）
        if metadata:
            # 创建消息快照
            user_snapshot = MessageSnapshot(
                content=content,
                timestamp=datetime.now(),
                role="user"
            )

            agent_snapshot = MessageSnapshot(
                content=agent_response_text[:200],  # 截断，避免过长
                timestamp=datetime.now(),
                role="agent"
            )

            # 更新用户消息
            await routing_mgr.update_session_summary(
                session_id=session_id,
                new_message=user_snapshot
            )

            # 更新Agent回复（带key_points和status）
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
    从Agent响应中提取元数据

    Args:
        text: Agent响应文本

    Returns:
        元数据字典，解析失败返回None
    """
    # 匹配 ```metadata ... ``` 块
    pattern = r'```metadata\s*\n(.*?)\n```'
    match = re.search(pattern, text, re.DOTALL)

    if match:
        try:
            metadata_json = match.group(1)
            metadata = json.loads(metadata_json)

            # 验证必需字段
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
