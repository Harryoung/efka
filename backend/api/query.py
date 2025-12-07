"""
Query API routes - 智能问答接口
核心原则：不硬编码业务逻辑，由 Admin Agent 自主判断和处理
支持基于 user_id 的持久化会话（Redis + 降级到内存）
双 Agent 架构：此接口使用 Admin Agent (kb_admin_agent.py)
"""
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from backend.services.kb_service_factory import get_admin_service
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

router = APIRouter(prefix="/api", tags=["query"])


class QueryRequest(BaseModel):
    """查询请求"""
    session_id: Optional[str] = None
    message: str
    user_id: Optional[str] = None


class QueryResponse(BaseModel):
    """查询响应"""
    session_id: str
    response: str
    status: str


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """
    智能问答接口（非流式）

    核心逻辑：
    1. 获取或创建会话（支持基于 user_id 的持久化）
    2. 将用户消息传递给 Admin Agent (kb_admin_agent.py)
    3. Admin Agent 自主判断意图并直接处理（文档入库、知识库管理、批量通知）
    4. 等待 Agent 完成处理并返回结果

    不在此处做任何意图判断或业务逻辑！
    """
    try:
        admin_service = get_admin_service()
        session_manager = get_session_manager()

        # 新逻辑：基于 user_id 的持久化会话
        if req.user_id:
            # 获取 SDK session ID（用于 resume，如果是新会话则为 None）
            sdk_session_id = await session_manager.get_or_create_user_session(req.user_id)
            is_new_session = sdk_session_id is None
            logger.info(
                f"Processing query for user {req.user_id} "
                f"(sdk_session: {sdk_session_id or 'new'}, is_new: {is_new_session})"
            )

            # 确保 Admin Service 已初始化
            if not admin_service.is_initialized:
                await admin_service.initialize()

            # 直接将用户消息发送给 Admin Agent
            response_parts = []
            turn_count = None
            real_sdk_session_id = None

            from claude_agent_sdk import AssistantMessage, TextBlock, ResultMessage

            # 流式接收 Admin Agent 响应（连接池已在 service 层处理并发）
            async for message in admin_service.query(req.message, sdk_session_id=sdk_session_id):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_parts.append(block.text)
                elif isinstance(message, ResultMessage):
                    turn_count = message.num_turns
                    real_sdk_session_id = message.session_id  # 提取真实的 SDK session ID

            # 保存真实的 SDK session ID（用于下次 resume）
            if real_sdk_session_id:
                await session_manager.save_sdk_session_id(req.user_id, real_sdk_session_id)
                logger.info(f"Saved SDK session ID for user {req.user_id}: {real_sdk_session_id}")

            # 更新会话活跃度
            if turn_count is not None:
                await session_manager.update_session_activity(req.user_id, turn_count=turn_count)

            response_text = "".join(response_parts) if response_parts else "未收到响应"

            return QueryResponse(
                session_id=real_sdk_session_id or "new",
                response=response_text,
                status="success"
            )

        # 旧逻辑：基于 session_id 的会话（向后兼容，不使用 resume）
        else:
            if req.session_id:
                session = session_manager.get_session(req.session_id)
                if not session:
                    raise HTTPException(status_code=404, detail="会话不存在")
                session.update_activity()
            else:
                session = session_manager.create_session(user_id=None)

            logger.info(f"Processing query for session {session.session_id}: {req.message[:50]}... (legacy mode)")

            # 确保 Admin Service 已初始化
            if not admin_service.is_initialized:
                await admin_service.initialize()

            # 直接将用户消息发送给 Admin Agent（旧模式：不使用 resume）
            response_parts = []
            from claude_agent_sdk import AssistantMessage, TextBlock

            async for message in admin_service.query(req.message, sdk_session_id=None):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_parts.append(block.text)

            response_text = "".join(response_parts) if response_parts else "未收到响应"

            return QueryResponse(
                session_id=session.session_id,
                response=response_text,
                status="success"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query/stream")
async def query_stream(
    session_id: Optional[str] = None,
    message: str = "",
    user_id: Optional[str] = None
):
    """
    智能问答接口（SSE 流式）

    核心逻辑：
    1. 与 /query 相同的流程（支持基于 user_id 的持久化）
    2. 使用 Server-Sent Events (SSE) 流式返回 Admin Agent 的响应
    3. Admin Agent 的输出会实时推送给前端

    不做任何业务逻辑判断！

    注意：SSE 只能使用 GET 请求，所以参数通过查询字符串传递
    """
    try:
        admin_service = get_admin_service()
        session_manager = get_session_manager()

        # 新逻辑：基于 user_id 的持久化会话
        if user_id:
            # 获取 SDK session ID（用于 resume，如果是新会话则为 None）
            sdk_session_id = await session_manager.get_or_create_user_session(user_id)
            is_new_session = sdk_session_id is None
            logger.info(
                f"Processing streaming query for user {user_id} "
                f"(sdk_session: {sdk_session_id or 'new'}, is_new: {is_new_session})"
            )

            # 确保 Admin Service 已初始化
            if not admin_service.is_initialized:
                await admin_service.initialize()

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

                    # 流式接收 Admin Agent 响应（连接池已在 service 层处理并发）
                    async for msg in admin_service.query(message, sdk_session_id=sdk_session_id):
                        if isinstance(msg, AssistantMessage):
                            for block in msg.content:
                                if isinstance(block, TextBlock):
                                    yield sse_message_event(block.text)
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
                    logger.error(f"Stream error: {e}", exc_info=True)
                    yield sse_error_event(str(e))

            return create_sse_response(event_generator())

        # 旧逻辑：基于 session_id 的会话（向后兼容，不使用 resume）
        else:
            if session_id:
                session = session_manager.get_session(session_id)
                if not session:
                    raise HTTPException(status_code=404, detail="会话不存在")
                session.update_activity()
            else:
                session = session_manager.create_session(user_id=None)

            logger.info(f"Processing streaming query for session {session.session_id} (legacy mode, no resume)")

            # 确保 Admin Service 已初始化
            if not admin_service.is_initialized:
                await admin_service.initialize()

            # 定义 SSE 生成器
            async def event_generator():
                """SSE 事件生成器（基于 session_id，旧模式不使用 resume）"""
                try:
                    from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, ResultMessage

                    # 发送会话 ID
                    yield sse_session_event(session.session_id)

                    # 流式接收 Admin Agent 响应（旧模式：不传 sdk_session_id，每次都是新会话）
                    async for msg in admin_service.query(message, sdk_session_id=None):
                        if isinstance(msg, AssistantMessage):
                            for block in msg.content:
                                if isinstance(block, TextBlock):
                                    yield sse_message_event(block.text)
                                elif isinstance(block, ToolUseBlock):
                                    yield sse_tool_use_event(block.name)

                        elif isinstance(msg, ResultMessage):
                            yield sse_done_event(msg.duration_ms)

                except Exception as e:
                    logger.error(f"Stream error: {e}", exc_info=True)
                    yield sse_error_event(str(e))

            return create_sse_response(event_generator())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query stream error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear_context")
async def clear_context(request: dict):
    """
    清空用户上下文（新接口）

    归档旧会话，创建新会话（sdk_session_id 将被清空）
    """
    try:
        user_id = request.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="缺少 user_id 参数")

        session_manager = get_session_manager()

        # 清空用户上下文（下次查询会创建新的 SDK 会话）
        await session_manager.clear_user_context(user_id)

        return {
            "success": True,
            "message": f"用户 {user_id} 的上下文已清空，下次查询将创建新会话"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clear context error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/create")
async def create_session(user_id: Optional[str] = None):
    """
    创建新会话（原有接口，保留向后兼容）
    """
    try:
        session_manager = get_session_manager()
        session = session_manager.create_session(user_id=user_id)

        return {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "status": "created"
        }
    except Exception as e:
        logger.error(f"Create session error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    删除会话（原有接口，保留向后兼容）
    """
    try:
        session_manager = get_session_manager()
        success = await session_manager.delete_session(session_id)

        if not success:
            raise HTTPException(status_code=404, detail="会话不存在")

        return {"status": "deleted", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete session error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
