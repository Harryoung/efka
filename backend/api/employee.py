"""
Employee API routes - 员工知识查询接口
使用 Employee Agent (kb_qa_agent.py)
支持基于 user_id 的持久化会话
"""
import logging
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json

from backend.services.kb_service_factory import get_employee_service
from backend.services.session_manager import get_session_manager

logger = logging.getLogger(__name__)

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
            # 获取或创建用户的 Claude session ID
            claude_session_id = await session_manager.get_or_create_user_session(user_id)
            logger.info(f"Processing employee query for user {user_id} (claude_session: {claude_session_id})")

            # 确保 Employee Service 已初始化
            if not employee_service.is_initialized:
                await employee_service.initialize()

            # 定义 SSE 生成器
            async def event_generator():
                """SSE 事件生成器（基于 user_id）"""
                try:
                    from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, ResultMessage

                    # 发送 claude_session_id
                    yield f"data: {json.dumps({'type': 'session', 'session_id': claude_session_id})}\n\n"

                    turn_count = None

                    # 流式接收 Employee Agent 响应
                    async for msg in employee_service.query(message, session_id=claude_session_id):
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
                    logger.error(f"Employee stream error: {e}", exc_info=True)
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )

        # 基于 session_id 的会话（向后兼容）
        else:
            if session_id:
                session = session_manager.get_session(session_id)
                if not session:
                    raise HTTPException(status_code=404, detail="会话不存在")
                session.update_activity()
            else:
                session = session_manager.create_session(user_id=None)

            logger.info(f"Processing employee query for session {session.session_id}")

            # 确保 Employee Service 已初始化
            if not employee_service.is_initialized:
                await employee_service.initialize()

            # 定义 SSE 生成器
            async def event_generator():
                """SSE 事件生成器（基于 session_id）"""
                try:
                    from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, ResultMessage

                    # 发送会话 ID
                    yield f"data: {json.dumps({'type': 'session', 'session_id': session.session_id})}\n\n"

                    # 流式接收 Employee Agent 响应
                    async for msg in employee_service.query(message, session_id=session.session_id):
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
                    logger.error(f"Employee stream error: {e}", exc_info=True)
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Employee query stream error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
