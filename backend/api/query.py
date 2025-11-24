"""
Query API routes - 智能问答接口
核心原则：不硬编码业务逻辑，由 Admin Agent 自主判断和处理
支持基于 user_id 的持久化会话（Redis + 降级到内存）
双 Agent 架构：此接口使用 Admin Agent (kb_admin_agent.py)
"""
import logging
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json

from backend.services.kb_service_factory import get_admin_service
from backend.services.session_manager import get_session_manager

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
            # 获取或创建用户的 Claude session ID
            claude_session_id = await session_manager.get_or_create_user_session(req.user_id)
            logger.info(f"Processing query for user {req.user_id} (claude_session: {claude_session_id})")

            # 确保 Admin Service 已初始化
            if not admin_service.is_initialized:
                await admin_service.initialize()

            # 直接将用户消息发送给 Admin Agent
            response_parts = []
            turn_count = None

            from claude_agent_sdk import AssistantMessage, TextBlock, ResultMessage

            async for message in admin_service.query(req.message, session_id=claude_session_id):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_parts.append(block.text)
                elif isinstance(message, ResultMessage):
                    turn_count = message.num_turns

            # 更新会话活跃度
            if turn_count is not None:
                await session_manager.update_session_activity(req.user_id, turn_count=turn_count)

            response_text = "".join(response_parts) if response_parts else "未收到响应"

            return QueryResponse(
                session_id=claude_session_id,
                response=response_text,
                status="success"
            )

        # 旧逻辑：基于 session_id 的会话（向后兼容）
        else:
            if req.session_id:
                session = session_manager.get_session(req.session_id)
                if not session:
                    raise HTTPException(status_code=404, detail="会话不存在")
                session.update_activity()
            else:
                session = session_manager.create_session(user_id=None)

            logger.info(f"Processing query for session {session.session_id}: {req.message[:50]}...")

            # 确保 Admin Service 已初始化
            if not admin_service.is_initialized:
                await admin_service.initialize()

            # 直接将用户消息发送给 Admin Agent
            response_parts = []
            from claude_agent_sdk import AssistantMessage, TextBlock

            async for message in admin_service.query(req.message, session_id=session.session_id):
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
            # 获取或创建用户的 Claude session ID
            claude_session_id = await session_manager.get_or_create_user_session(user_id)
            logger.info(f"Processing streaming query for user {user_id} (claude_session: {claude_session_id})")

            # 确保 Admin Service 已初始化
            if not admin_service.is_initialized:
                await admin_service.initialize()

            # 定义 SSE 生成器
            async def event_generator():
                """SSE 事件生成器（基于 user_id）"""
                try:
                    from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, ResultMessage

                    # 发送 claude_session_id
                    yield f"data: {json.dumps({'type': 'session', 'session_id': claude_session_id})}\n\n"

                    turn_count = None

                    # 流式接收 Admin Agent 响应
                    async for msg in admin_service.query(message, session_id=claude_session_id):
                        if isinstance(msg, AssistantMessage):
                            # 提取文本块
                            for block in msg.content:
                                if isinstance(block, TextBlock):
                                    yield f"data: {json.dumps({'type': 'message', 'content': block.text})}\n\n"
                                elif isinstance(block, ToolUseBlock):
                                    # 可选：发送工具使用信息
                                    yield f"data: {json.dumps({'type': 'tool_use', 'tool': block.name})}\n\n"

                        elif isinstance(msg, ResultMessage):
                            turn_count = msg.num_turns
                            # 发送完成信息
                            yield f"data: {json.dumps({'type': 'done', 'duration_ms': msg.duration_ms})}\n\n"

                    # 更新会话活跃度
                    if turn_count is not None:
                        await session_manager.update_session_activity(user_id, turn_count=turn_count)

                except Exception as e:
                    logger.error(f"Stream error: {e}", exc_info=True)
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
                }
            )

        # 旧逻辑：基于 session_id 的会话（向后兼容）
        else:
            if session_id:
                session = session_manager.get_session(session_id)
                if not session:
                    raise HTTPException(status_code=404, detail="会话不存在")
                session.update_activity()
            else:
                session = session_manager.create_session(user_id=None)

            logger.info(f"Processing streaming query for session {session.session_id}")

            # 确保 Admin Service 已初始化
            if not admin_service.is_initialized:
                await admin_service.initialize()

            # 定义 SSE 生成器
            async def event_generator():
                """SSE 事件生成器（基于 session_id）"""
                try:
                    from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, ResultMessage

                    # 发送会话 ID
                    yield f"data: {json.dumps({'type': 'session', 'session_id': session.session_id})}\n\n"

                    # 流式接收 Admin Agent 响应
                    async for msg in admin_service.query(message, session_id=session.session_id):
                        if isinstance(msg, AssistantMessage):
                            # 提取文本块
                            for block in msg.content:
                                if isinstance(block, TextBlock):
                                    yield f"data: {json.dumps({'type': 'message', 'content': block.text})}\n\n"
                                elif isinstance(block, ToolUseBlock):
                                    # 可选：发送工具使用信息
                                    yield f"data: {json.dumps({'type': 'tool_use', 'tool': block.name})}\n\n"

                        elif isinstance(msg, ResultMessage):
                            # 发送完成信息
                            yield f"data: {json.dumps({'type': 'done', 'duration_ms': msg.duration_ms})}\n\n"

                except Exception as e:
                    logger.error(f"Stream error: {e}", exc_info=True)
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query stream error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear_context")
async def clear_context(request: dict):
    """
    清空用户上下文（新接口）

    归档旧会话，创建新会话
    """
    try:
        user_id = request.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="缺少 user_id 参数")

        session_manager = get_session_manager()

        # 清空用户上下文
        new_claude_session_id = await session_manager.clear_user_context(user_id)

        return {
            "success": True,
            "new_session_id": new_claude_session_id,
            "message": f"用户 {user_id} 的上下文已清空"
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
