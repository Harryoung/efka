"""
User API routes - User knowledge query interface
Uses User Agent (kb_qa_agent.py)
Supports user_id-based persistent sessions
"""
import logging
import re
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.services.kb_service_factory import get_user_service
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

# Regular expression for filtering Agent metadata
# Matches metadata blocks in ```metadata\n{...}\n``` or ```json\n{...}\n``` format
METADATA_PATTERN = re.compile(
    r'```(?:metadata|json)\s*\n\s*(\{[^`]*?\})\s*\n```',
    re.DOTALL
)

def _is_claude_code_login_required_error(text: str) -> bool:
    return "Please run /login" in text


def filter_metadata_from_content(content: str) -> tuple[str, dict | None]:
    """
    Filter metadata blocks from Agent output, and extract metadata for logging and session management

    Design notes:
    - WeCom scenario: Agent sends messages directly via MCP, metadata parsed by scaffolding layer
    - Web frontend scenario: Metadata should not be shown to users, but logged for debugging

    Args:
        content: Raw content output by Agent

    Returns:
        (filtered content, extracted metadata dict or None)
    """
    metadata = None

    # Find metadata block
    match = METADATA_PATTERN.search(content)
    if match:
        json_str = match.group(1)
        try:
            metadata = json.loads(json_str)
            logger.info(f"[Metadata] Extracted from Agent output: {json.dumps(metadata, ensure_ascii=False)}")
        except json.JSONDecodeError as e:
            logger.warning(f"[Metadata] Failed to parse JSON: {e}, raw: {json_str[:100]}...")

        # Remove metadata block from content (not shown on frontend)
        content = METADATA_PATTERN.sub('', content).strip()

    return content, metadata

router = APIRouter(prefix="/api/user", tags=["user"])


class UserQueryRequest(BaseModel):
    """User query request"""
    session_id: Optional[str] = None
    message: str
    user_id: Optional[str] = None


@router.get("/query")
async def user_query_stream(
    session_id: Optional[str] = None,
    message: str = "",
    user_id: Optional[str] = None
):
    """
    User knowledge query interface (SSE streaming)

    Core logic:
    1. Use User Agent (kb_qa_agent.py) to process query
    2. Only supports knowledge query function, does not support document upload and management
    3. Use Server-Sent Events (SSE) to stream responses
    4. Supports user_id-based persistent sessions
    """
    try:
        user_service = get_user_service()
        session_manager = get_session_manager()

        # user_id-based persistent sessions
        if user_id:
            # Get SDK session ID (for resume, None if new session)
            sdk_session_id = await session_manager.get_or_create_user_session(user_id)
            is_new_session = sdk_session_id is None
            logger.info(
                f"Processing user query for user {user_id} "
                f"(sdk_session: {sdk_session_id or 'new'}, is_new: {is_new_session})"
            )

            # Ensure User Service is initialized
            if not user_service.is_initialized:
                await user_service.initialize()

            # Define SSE generator
            async def event_generator():
                """
                SSE event generator (based on user_id)

                Concurrency support: use SDKClientPool for true concurrency
                Each request has exclusive Client, no user locks needed

                Important: extract real SDK session ID from ResultMessage and save
                """
                try:
                    from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, ResultMessage

                    # Send session status information
                    yield sse_session_event(sdk_session_id, is_new=is_new_session)

                    turn_count = None
                    real_sdk_session_id = None

                    # Stream User Agent responses (connection pool handles concurrency at service layer)
                    async for msg in user_service.query(message, sdk_session_id=sdk_session_id, user_id=user_id):
                        if isinstance(msg, AssistantMessage):
                            for block in msg.content:
                                if isinstance(block, TextBlock):
                                    # Filter metadata, don't show to frontend, but log it
                                    filtered_content, _metadata = filter_metadata_from_content(block.text)
                                    if _is_claude_code_login_required_error(filtered_content or block.text):
                                        yield sse_error_event(filtered_content or block.text)
                                        return
                                    if filtered_content:
                                        yield sse_message_event(filtered_content)
                                elif isinstance(block, ToolUseBlock):
                                    yield sse_tool_use_event(block.id, block.name, block.input)

                        elif isinstance(msg, ResultMessage):
                            if msg.is_error:
                                yield sse_error_event(msg.result or "Upstream error")
                                return

                            turn_count = msg.num_turns
                            real_sdk_session_id = msg.session_id
                            logger.info(f"Received ResultMessage with session_id: {real_sdk_session_id}")
                            yield sse_done_event(msg.duration_ms)

                    # Save real SDK session ID (for next resume)
                    if real_sdk_session_id:
                        await session_manager.save_sdk_session_id(user_id, real_sdk_session_id)
                        logger.info(f"Saved SDK session ID for user {user_id}: {real_sdk_session_id}")

                    # Update session activity
                    if turn_count is not None:
                        await session_manager.update_session_activity(user_id, turn_count=turn_count)

                except Exception as e:
                    logger.error(f"User stream error: {e}", exc_info=True)
                    yield sse_error_event(str(e))

            return create_sse_response(event_generator())

        # session_id-based sessions (backward compatible, no resume)
        else:
            if session_id:
                session = session_manager.get_session(session_id)
                if not session:
                    raise HTTPException(status_code=404, detail="Session not found")
                session.update_activity()
            else:
                session = session_manager.create_session(user_id=None)

            logger.info(f"Processing user query for session {session.session_id} (legacy mode, no resume)")

            # Ensure User Service is initialized
            if not user_service.is_initialized:
                await user_service.initialize()

            # Define SSE generator
            async def event_generator():
                """SSE event generator (based on session_id, legacy mode without resume)"""
                try:
                    from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, ResultMessage

                    # Send session ID
                    yield sse_session_event(session.session_id)

                    # Stream User Agent responses (old mode: no sdk_session_id)
                    async for msg in user_service.query(message, sdk_session_id=None, user_id=None):
                        if isinstance(msg, AssistantMessage):
                            for block in msg.content:
                                if isinstance(block, TextBlock):
                                    # Filter metadata, don't show to frontend, but log it
                                    filtered_content, _metadata = filter_metadata_from_content(block.text)
                                    if _is_claude_code_login_required_error(filtered_content or block.text):
                                        yield sse_error_event(filtered_content or block.text)
                                        return
                                    if filtered_content:
                                        yield sse_message_event(filtered_content)
                                elif isinstance(block, ToolUseBlock):
                                    yield sse_tool_use_event(block.id, block.name, block.input)

                        elif isinstance(msg, ResultMessage):
                            if msg.is_error:
                                yield sse_error_event(msg.result or "Upstream error")
                                return
                            yield sse_done_event(msg.duration_ms)

                except Exception as e:
                    logger.error(f"User stream error: {e}", exc_info=True)
                    yield sse_error_event(str(e))

            return create_sse_response(event_generator())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User query stream error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
