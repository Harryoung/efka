"""
SSE 流式响应工具函数
提取 query.py 和 employee.py 的公共 SSE 处理逻辑
"""
import json
import logging
from typing import AsyncGenerator, Callable, Optional, Any
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# 标准 SSE 响应头
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
}


def format_sse_event(data: dict) -> str:
    """
    格式化 SSE 事件

    Args:
        data: 要发送的数据字典

    Returns:
        SSE 格式的字符串
    """
    return f"data: {json.dumps(data)}\n\n"


def create_sse_response(generator: AsyncGenerator) -> StreamingResponse:
    """
    创建标准 SSE 响应

    Args:
        generator: 异步事件生成器

    Returns:
        StreamingResponse 对象
    """
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers=SSE_HEADERS
    )


def sse_session_event(session_id: Optional[str], is_new: bool = False) -> str:
    """
    生成会话状态 SSE 事件

    Args:
        session_id: 会话 ID
        is_new: 是否是新会话

    Returns:
        SSE 格式的会话事件
    """
    return format_sse_event({
        'type': 'session',
        'session_id': session_id or 'new',
        'is_new': is_new
    })


def sse_message_event(content: str) -> str:
    """
    生成消息内容 SSE 事件

    Args:
        content: 消息内容

    Returns:
        SSE 格式的消息事件
    """
    return format_sse_event({
        'type': 'message',
        'content': content
    })


def sse_tool_use_event(tool_name: str) -> str:
    """
    生成工具使用 SSE 事件

    Args:
        tool_name: 工具名称

    Returns:
        SSE 格式的工具事件
    """
    return format_sse_event({
        'type': 'tool_use',
        'tool': tool_name
    })


def sse_done_event(duration_ms: Optional[int] = None) -> str:
    """
    生成完成 SSE 事件

    Args:
        duration_ms: 持续时间（毫秒）

    Returns:
        SSE 格式的完成事件
    """
    data = {'type': 'done'}
    if duration_ms is not None:
        data['duration_ms'] = duration_ms
    return format_sse_event(data)


def sse_error_event(message: str) -> str:
    """
    生成错误 SSE 事件

    Args:
        message: 错误消息

    Returns:
        SSE 格式的错误事件
    """
    return format_sse_event({
        'type': 'error',
        'message': message
    })


async def process_agent_messages(
    message_generator: AsyncGenerator,
    content_filter: Optional[Callable[[str], tuple[str, Any]]] = None
) -> AsyncGenerator[str, None]:
    """
    处理 Agent 消息并转换为 SSE 事件

    Args:
        message_generator: Agent 消息生成器
        content_filter: 可选的内容过滤函数 (content) -> (filtered_content, metadata)

    Yields:
        SSE 格式的事件字符串
    """
    from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, ResultMessage

    async for msg in message_generator:
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    content = block.text
                    if content_filter:
                        content, _ = content_filter(content)
                    if content:
                        yield sse_message_event(content)
                elif isinstance(block, ToolUseBlock):
                    yield sse_tool_use_event(block.name)

        elif isinstance(msg, ResultMessage):
            yield sse_done_event(msg.duration_ms)
