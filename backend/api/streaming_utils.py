"""
SSE streaming response utility functions
Extracts common SSE processing logic from query.py and user.py
"""
import json
import logging
from typing import AsyncGenerator, Callable, Optional, Any
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# Standard SSE response headers
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no"  # Disable nginx buffering
}


def format_sse_event(data: dict) -> str:
    """
    Format SSE event

    Args:
        data: Data dictionary to send

    Returns:
        SSE formatted string
    """
    return f"data: {json.dumps(data)}\n\n"


def create_sse_response(generator: AsyncGenerator) -> StreamingResponse:
    """
    Create standard SSE response

    Args:
        generator: Async event generator

    Returns:
        StreamingResponse object
    """
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers=SSE_HEADERS
    )


def sse_session_event(session_id: Optional[str], is_new: bool = False) -> str:
    """
    Generate session state SSE event

    Args:
        session_id: Session ID
        is_new: Whether it's a new session

    Returns:
        SSE formatted session event
    """
    return format_sse_event({
        'type': 'session',
        'session_id': session_id or 'new',
        'is_new': is_new
    })


def sse_message_event(content: str) -> str:
    """
    Generate message content SSE event

    Args:
        content: Message content

    Returns:
        SSE formatted message event
    """
    return format_sse_event({
        'type': 'message',
        'content': content
    })


def sse_tool_use_event(tool_name: str) -> str:
    """
    Generate tool use SSE event

    Args:
        tool_name: Tool name

    Returns:
        SSE formatted tool event
    """
    return format_sse_event({
        'type': 'tool_use',
        'tool': tool_name
    })


def sse_done_event(duration_ms: Optional[int] = None) -> str:
    """
    Generate completion SSE event

    Args:
        duration_ms: Duration in milliseconds

    Returns:
        SSE formatted completion event
    """
    data = {'type': 'done'}
    if duration_ms is not None:
        data['duration_ms'] = duration_ms
    return format_sse_event(data)


def sse_error_event(message: str) -> str:
    """
    Generate error SSE event

    Args:
        message: Error message

    Returns:
        SSE formatted error event
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
    Process Agent messages and convert to SSE events

    Args:
        message_generator: Agent message generator
        content_filter: Optional content filter function (content) -> (filtered_content, metadata)

    Yields:
        SSE formatted event strings
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
