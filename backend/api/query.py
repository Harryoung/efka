"""
Query API routes - Intelligent Q&A Interface
Core principle: No hardcoded business logic, let Admin Agent autonomously judge and handle
Supports user_id-based persistent sessions (Redis + memory fallback)
Dual Agent architecture: This interface uses Admin Agent (kb_admin_agent.py)
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

def _is_claude_code_login_required_error(text: str) -> bool:
    return "Please run /login" in text


class QueryRequest(BaseModel):
    """Query request"""
    session_id: Optional[str] = None
    message: str
    user_id: Optional[str] = None


class QueryResponse(BaseModel):
    """Query response"""
    session_id: str
    response: str
    status: str


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """
    Intelligent Q&A interface (non-streaming)

    Core logic:
    1. Get or create session (supports user_id-based persistence)
    2. Pass user message to Admin Agent (kb_admin_agent.py)
    3. Admin Agent autonomously judges intent and handles directly (document ingestion, knowledge base management, batch notification)
    4. Wait for Agent to complete processing and return result

    No intent judgment or business logic here!
    """
    try:
        admin_service = get_admin_service()
        session_manager = get_session_manager()

        # New logic: user_id-based persistent sessions
        if req.user_id:
            # Get SDK session ID (for resume, None if new session)
            sdk_session_id = await session_manager.get_or_create_user_session(req.user_id)
            is_new_session = sdk_session_id is None
            logger.info(
                f"Processing query for user {req.user_id} "
                f"(sdk_session: {sdk_session_id or 'new'}, is_new: {is_new_session})"
            )

            # Ensure Admin Service is initialized
            if not admin_service.is_initialized:
                await admin_service.initialize()

            # Send user message directly to Admin Agent
            response_parts = []
            turn_count = None
            real_sdk_session_id = None

            from claude_agent_sdk import AssistantMessage, TextBlock, ResultMessage

            # Stream Admin Agent responses (connection pool handles concurrency at service layer)
            async for message in admin_service.query(req.message, sdk_session_id=sdk_session_id):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_parts.append(block.text)
                elif isinstance(message, ResultMessage):
                    turn_count = message.num_turns
                    real_sdk_session_id = message.session_id  # Extract real SDK session ID

            # Save real SDK session ID (for next resume)
            if real_sdk_session_id:
                await session_manager.save_sdk_session_id(req.user_id, real_sdk_session_id)
                logger.info(f"Saved SDK session ID for user {req.user_id}: {real_sdk_session_id}")

            # Update session activity
            if turn_count is not None:
                await session_manager.update_session_activity(req.user_id, turn_count=turn_count)

            response_text = "".join(response_parts) if response_parts else "No response received"

            return QueryResponse(
                session_id=real_sdk_session_id or "new",
                response=response_text,
                status="success"
            )

        # Legacy logic: session_id-based session (backward compatible, no resume)
        else:
            if req.session_id:
                session = session_manager.get_session(req.session_id)
                if not session:
                    raise HTTPException(status_code=404, detail="Session not found")
                session.update_activity()
            else:
                session = session_manager.create_session(user_id=None)

            logger.info(f"Processing query for session {session.session_id}: {req.message[:50]}... (legacy mode)")

            # Ensure Admin Service is initialized
            if not admin_service.is_initialized:
                await admin_service.initialize()

            # Send user message directly to Admin Agent (old mode: no resume)
            response_parts = []
            from claude_agent_sdk import AssistantMessage, TextBlock

            async for message in admin_service.query(req.message, sdk_session_id=None):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_parts.append(block.text)

            response_text = "".join(response_parts) if response_parts else "No response received"

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
    Intelligent Q&A interface (SSE streaming)

    Core logic:
    1. Same flow as /query (supports user_id-based persistence)
    2. Use Server-Sent Events (SSE) to stream Admin Agent responses
    3. Admin Agent output is pushed to frontend in real-time

    No business logic judgment here!

    Note: SSE can only use GET requests, so parameters are passed via query string
    """
    try:
        admin_service = get_admin_service()
        session_manager = get_session_manager()

        # New logic: user_id-based persistent sessions
        if user_id:
            # Get SDK session ID (for resume, None if new session)
            sdk_session_id = await session_manager.get_or_create_user_session(user_id)
            is_new_session = sdk_session_id is None
            logger.info(
                f"Processing streaming query for user {user_id} "
                f"(sdk_session: {sdk_session_id or 'new'}, is_new: {is_new_session})"
            )

            # Ensure Admin Service is initialized
            if not admin_service.is_initialized:
                await admin_service.initialize()

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

                    # Stream Admin Agent responses (connection pool handles concurrency at service layer)
                    async for msg in admin_service.query(message, sdk_session_id=sdk_session_id):
                        logger.info(f"[DEBUG] Received message type: {type(msg).__name__}")
                        if isinstance(msg, AssistantMessage):
                            for block in msg.content:
                                block_type = type(block).__name__
                                logger.info(f"[DEBUG] Processing block type: {block_type}")
                                if isinstance(block, TextBlock):
                                    if _is_claude_code_login_required_error(block.text):
                                        yield sse_error_event(block.text)
                                        return
                                    yield sse_message_event(block.text)
                                elif isinstance(block, ToolUseBlock):
                                    logger.info(f"Tool use detected: {block.name}, input: {block.input}")
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
                    logger.error(f"Stream error: {e}", exc_info=True)
                    yield sse_error_event(str(e))

            return create_sse_response(event_generator())

        # Old logic: session_id-based sessions (backward compatible, no resume)
        else:
            if session_id:
                session = session_manager.get_session(session_id)
                if not session:
                    raise HTTPException(status_code=404, detail="Session not found")
                session.update_activity()
            else:
                session = session_manager.create_session(user_id=None)

            logger.info(f"Processing streaming query for session {session.session_id} (legacy mode, no resume)")

            # Ensure Admin Service is initialized
            if not admin_service.is_initialized:
                await admin_service.initialize()

            # Define SSE generator
            async def event_generator():
                """SSE event generator (based on session_id, legacy mode without resume)"""
                try:
                    from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, ResultMessage

                    # Send session ID
                    yield sse_session_event(session.session_id)

                    # Stream Admin Agent responses (old mode: no sdk_session_id, new session each time)
                    async for msg in admin_service.query(message, sdk_session_id=None):
                        if isinstance(msg, AssistantMessage):
                            for block in msg.content:
                                if isinstance(block, TextBlock):
                                    if _is_claude_code_login_required_error(block.text):
                                        yield sse_error_event(block.text)
                                        return
                                    yield sse_message_event(block.text)
                                elif isinstance(block, ToolUseBlock):
                                    logger.info(f"Tool use detected: {block.name}, input: {block.input}")
                                    yield sse_tool_use_event(block.id, block.name, block.input)

                        elif isinstance(msg, ResultMessage):
                            if msg.is_error:
                                yield sse_error_event(msg.result or "Upstream error")
                                return
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
    Clear user context (new interface)

    Archive old session, create new session (sdk_session_id will be cleared)
    """
    try:
        user_id = request.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="Missing user_id parameter")

        session_manager = get_session_manager()

        # Clear user context (next query will create new SDK session)
        await session_manager.clear_user_context(user_id)

        return {
            "success": True,
            "message": f"Context cleared for user {user_id}, next query will create new session"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clear context error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/create")
async def create_session(user_id: Optional[str] = None):
    """
    Create new session (original interface, backward compatible)
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
    Delete session (original interface, backward compatible)
    """
    try:
        session_manager = get_session_manager()
        success = await session_manager.delete_session(session_id)

        if not success:
            raise HTTPException(status_code=404, detail="Session not found")

        return {"status": "deleted", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete session error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
