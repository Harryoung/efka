"""
Employee API routes - 员工知识查询接口
使用 Employee Agent (kb_qa_agent.py)
支持基于 user_id 的持久化会话
"""
import logging
import re
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.services.kb_service_factory import get_employee_service
from backend.services.session_manager import get_session_manager
from backend.api.streaming_utils import (
    create_sse_response,
    sse_session_event,
    sse_message_event,
    sse_tool_use_event,
    sse_done_event,
    sse_error_event
)

logger = logging.getLogger(__name__)

# 用于过滤 Agent 元数据的正则表达式
# 匹配 ```metadata\n{...}\n``` 或 ```json\n{...}\n``` 格式的元数据块
METADATA_PATTERN = re.compile(
    r'```(?:metadata|json)\s*\n\s*(\{[^`]*?\})\s*\n```',
    re.DOTALL
)


def filter_metadata_from_content(content: str) -> tuple[str, dict | None]:
    """
    从 Agent 输出中过滤元数据块，同时提取元数据供日志记录和会话管理使用

    设计说明：
    - 企微场景：Agent 通过 MCP 直接发送消息，元数据供脚手架层解析
    - Web 前端场景：元数据不应展示给用户，但需记录日志以便调试

    Args:
        content: Agent 输出的原始内容

    Returns:
        (过滤后的内容, 提取的元数据字典或None)
    """
    metadata = None

    # 查找元数据块
    match = METADATA_PATTERN.search(content)
    if match:
        json_str = match.group(1)
        try:
            metadata = json.loads(json_str)
            logger.info(f"[Metadata] Extracted from Agent output: {json.dumps(metadata, ensure_ascii=False)}")
        except json.JSONDecodeError as e:
            logger.warning(f"[Metadata] Failed to parse JSON: {e}, raw: {json_str[:100]}...")

        # 从内容中移除元数据块（前端不展示）
        content = METADATA_PATTERN.sub('', content).strip()

    return content, metadata

router = APIRouter(prefix="/api/employee", tags=["employee"])


class EmployeeQueryRequest(BaseModel):
    """员工查询请求"""
    session_id: Optional[str] = None
    message: str
    user_id: Optional[str] = None


@router.get("/query")
async def employee_query_stream(
    session_id: Optional[str] = None,
    message: str = "",
    user_id: Optional[str] = None
):
    """
    员工知识查询接口（SSE 流式）

    核心逻辑：
    1. 使用 Employee Agent (kb_qa_agent.py) 处理查询
    2. 仅支持知识查询功能，不支持文档上传和管理
    3. 使用 Server-Sent Events (SSE) 流式返回响应
    4. 支持基于 user_id 的持久化会话
    """
    try:
        employee_service = get_employee_service()
        session_manager = get_session_manager()

        # 基于 user_id 的持久化会话
        if user_id:
            # 获取 SDK session ID（用于 resume，如果是新会话则为 None）
            sdk_session_id = await session_manager.get_or_create_user_session(user_id)
            is_new_session = sdk_session_id is None
            logger.info(
                f"Processing employee query for user {user_id} "
                f"(sdk_session: {sdk_session_id or 'new'}, is_new: {is_new_session})"
            )

            # 确保 Employee Service 已初始化
            if not employee_service.is_initialized:
                await employee_service.initialize()

            # 定义 SSE 生成器
            async def event_generator():
                """
                SSE 事件生成器（基于 user_id）

                并发支持：使用 SDKClientPool 实现真正并发
                每个请求独占一个 Client，无需用户锁

                重要：从 ResultMessage 中提取真实的 SDK session ID 并保存
                """
                try:
                    from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, ResultMessage

                    # 发送会话状态信息
                    yield sse_session_event(sdk_session_id, is_new=is_new_session)

                    turn_count = None
                    real_sdk_session_id = None

                    # 流式接收 Employee Agent 响应（连接池已在 service 层处理并发）
                    async for msg in employee_service.query(message, sdk_session_id=sdk_session_id, user_id=user_id):
                        if isinstance(msg, AssistantMessage):
                            for block in msg.content:
                                if isinstance(block, TextBlock):
                                    # 过滤元数据，不展示给前端，但记录日志
                                    filtered_content, metadata = filter_metadata_from_content(block.text)
                                    if filtered_content:
                                        yield sse_message_event(filtered_content)
                                elif isinstance(block, ToolUseBlock):
                                    yield sse_tool_use_event(block.name)

                        elif isinstance(msg, ResultMessage):
                            turn_count = msg.num_turns
                            real_sdk_session_id = msg.session_id
                            logger.info(f"Received ResultMessage with session_id: {real_sdk_session_id}")
                            yield sse_done_event(msg.duration_ms)

                    # 保存真实的 SDK session ID（用于下次 resume）
                    if real_sdk_session_id:
                        await session_manager.save_sdk_session_id(user_id, real_sdk_session_id)
                        logger.info(f"Saved SDK session ID for user {user_id}: {real_sdk_session_id}")

                    # 更新会话活跃度
                    if turn_count is not None:
                        await session_manager.update_session_activity(user_id, turn_count=turn_count)

                except Exception as e:
                    logger.error(f"Employee stream error: {e}", exc_info=True)
                    yield sse_error_event(str(e))

            return create_sse_response(event_generator())

        # 基于 session_id 的会话（向后兼容，不使用 resume）
        else:
            if session_id:
                session = session_manager.get_session(session_id)
                if not session:
                    raise HTTPException(status_code=404, detail="会话不存在")
                session.update_activity()
            else:
                session = session_manager.create_session(user_id=None)

            logger.info(f"Processing employee query for session {session.session_id} (legacy mode, no resume)")

            # 确保 Employee Service 已初始化
            if not employee_service.is_initialized:
                await employee_service.initialize()

            # 定义 SSE 生成器
            async def event_generator():
                """SSE 事件生成器（基于 session_id，旧模式不使用 resume）"""
                try:
                    from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, ResultMessage

                    # 发送会话 ID
                    yield sse_session_event(session.session_id)

                    # 流式接收 Employee Agent 响应（旧模式：不传 sdk_session_id）
                    async for msg in employee_service.query(message, sdk_session_id=None, user_id=None):
                        if isinstance(msg, AssistantMessage):
                            for block in msg.content:
                                if isinstance(block, TextBlock):
                                    # 过滤元数据，不展示给前端，但记录日志
                                    filtered_content, metadata = filter_metadata_from_content(block.text)
                                    if filtered_content:
                                        yield sse_message_event(filtered_content)
                                elif isinstance(block, ToolUseBlock):
                                    yield sse_tool_use_event(block.name)

                        elif isinstance(msg, ResultMessage):
                            yield sse_done_event(msg.duration_ms)

                except Exception as e:
                    logger.error(f"Employee stream error: {e}", exc_info=True)
                    yield sse_error_event(str(e))

            return create_sse_response(event_generator())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Employee query stream error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
