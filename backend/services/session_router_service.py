"""
Session Router Service - Session routing service

Encapsulates Session Router Agent invocation logic
Provides route_to_session method for wework_callback usage
"""

import logging
import json
import os
from typing import Optional, Dict
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock
)

from backend.agents.session_router_agent import get_session_router_agent_definition
from backend.services.routing_session_manager import get_routing_session_manager
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)


class SessionRouterService:
    """
    Session routing service

    Responsibilities:
    - Call Session Router Agent to determine message attribution
    - Scaffold layer directly passes structured JSON (candidate sessions already queried)
    - Return routing decision (session_id or NEW_SESSION)

    Note: No longer uses embedded tools, all data passed to Agent via JSON
    """

    def __init__(self):
        """Initialize Session Router service"""
        self.settings = get_settings()
        self.client: Optional[ClaudeSDKClient] = None
        self.is_initialized = False
        self.routing_session_manager = None

        logger.info("SessionRouterService instance created")

    async def initialize(self, redis_client=None):
        """
        Initialize Session Router Agent SDK client

        Args:
            redis_client: Redis client (optional)
        """
        if self.is_initialized:
            logger.warning("Session Router service already initialized")
            return

        try:
            # Check authentication
            if not self.settings.CLAUDE_API_KEY and not self.settings.ANTHROPIC_AUTH_TOKEN:
                raise ValueError("Missing authentication: CLAUDE_API_KEY or ANTHROPIC_AUTH_TOKEN")

            # Initialize RoutingSessionManager
            kb_path = Path(self.settings.KB_ROOT_PATH)
            self.routing_session_manager = get_routing_session_manager(
                kb_root=kb_path,
                redis_client=redis_client
            )
            await self.routing_session_manager.initialize()

            # Prepare environment variables
            env_vars = {
                "KB_ROOT_PATH": str(kb_path),
            }

            if self.settings.CLAUDE_API_KEY:
                env_vars["ANTHROPIC_API_KEY"] = self.settings.CLAUDE_API_KEY
            else:
                env_vars["ANTHROPIC_AUTH_TOKEN"] = self.settings.ANTHROPIC_AUTH_TOKEN
                if self.settings.ANTHROPIC_BASE_URL:
                    env_vars["ANTHROPIC_BASE_URL"] = self.settings.ANTHROPIC_BASE_URL

            # Get Session Router Agent definition
            router_agent_def = get_session_router_agent_definition()

            # Configure embedded tools (deprecated: scaffold layer passes structured JSON directly, no tools needed)
            # custom_tools = self._configure_custom_tools()

            # Create Claude Agent Options
            options = ClaudeAgentOptions(
                system_prompt={
                    "type": "preset",
                    "preset": "claude_code",
                    "append": f"\n\n{router_agent_def.prompt}"
                },
                agents=None,  # Single Agent architecture
                mcp_servers={},  # No MCP servers
                allowed_tools=[],  # No tools needed: all data passed via JSON by scaffold layer
                # Deprecated tools (code retained but not registered):
                #   - query_user_sessions: scaffold layer already queries in route_to_session
                #   - get_session_history: Agent only needs summary, not full history
                # custom_tools is not a valid ClaudeAgentOptions parameter, removed
                cwd=str(kb_path.parent),  # Project root directory
                permission_mode="acceptEdits",
                env=env_vars,
                setting_sources=None
            )

            # Create client
            self.client = ClaudeSDKClient(options=options)
            await self.client.connect()

            self.is_initialized = True
            logger.info("✅ Session Router service initialized successfully")
            logger.info("   Mode: JSON-only (no custom tools, data passed via structured JSON)")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Session Router service: {e}")
            raise

    def _configure_custom_tools(self) -> Dict:
        """
        Configure embedded tools

        ⚠️ Deprecated (code retained but no longer used)
        Reason: Scaffold layer (route_to_session) already queries candidate sessions and passes via JSON to Agent
        Agent no longer needs these tools to query data

        Returns:
            Tool dictionary {tool_name: async_function}
        """
        async def query_user_sessions(
            user_id: str,
            include_expired: bool = False
        ) -> Dict:
            """
            Query all user Sessions (embedded tool)

            Args:
                user_id: WeChat Work (企业微信) userid
                include_expired: Whether to include expired Sessions

            Returns:
                SessionQueryResult dict
            """
            result = await self.routing_session_manager.query_user_sessions(
                user_id=user_id,
                include_expired=include_expired,
                max_per_role=10  # Limit quantity
            )

            # Convert to dict (Session objects need serialization)
            return {
                "user_id": result.user_id,
                "as_user": [s.dict() for s in result.as_user],
                "as_expert": [s.dict() for s in result.as_expert],
                "total_count": result.total_count
            }

        async def get_session_history(
            session_id: str,
            limit: int = 50
        ) -> Dict:
            """
            Get Session full history (embedded tool)

            Args:
                session_id: Session ID
                limit: Maximum number of messages to return

            Returns:
                Historical message dict
            """
            messages = await self.routing_session_manager.get_session_history(
                session_id=session_id,
                limit=limit
            )

            return {
                "session_id": session_id,
                "messages": messages,
                "count": len(messages)
            }

        return {
            "query_user_sessions": query_user_sessions,
            "get_session_history": get_session_history
        }

    async def route_to_session(
        self,
        user_id: str,
        new_message: str,
        user_info: Dict
    ) -> Dict:
        """
        Call Session Router Agent to determine message attribution

        Args:
            user_id: WeChat Work (企业微信) userid
            new_message: New message content
            user_info: User info {"is_expert": bool, "expert_domains": []}

        Returns:
            Routing decision {
                "decision": str,  # session_id or "NEW_SESSION"
                "confidence": float,
                "reasoning": str,
                "matched_role": Optional[str]
            }
        """
        if not self.is_initialized:
            await self.initialize()

        # Query candidate Sessions
        sessions = await self.routing_session_manager.query_user_sessions(
            user_id=user_id,
            include_expired=False,
            max_per_role=10
        )

        # Fast path: if no candidate sessions, create new session directly
        if sessions.total_count == 0:
            logger.info(f"  No candidate sessions found, creating new session directly (fast path)")
            return {
                "decision": "NEW_SESSION",
                "confidence": 1.0,
                "reasoning": "New user, no historical Sessions",
                "matched_role": None
            }

        # Construct Router input
        from datetime import datetime
        router_input = {
            "user_id": user_id,
            "new_message": new_message,
            "current_time": datetime.now().isoformat(),  # Current timestamp for time window judgment
            "user_info": user_info,
            "candidate_sessions": {
                "as_user": [s.dict() for s in sessions.as_user],
                "as_expert": [s.dict() for s in sessions.as_expert]
            }
        }

        logger.info(f"Routing message for user {user_id}: {new_message[:50]}...")
        logger.info(f"  Candidate sessions: {sessions.total_count} ({len(sessions.as_user)} user, {len(sessions.as_expert)} expert)")

        try:
            # Call Router Agent
            # Send input as JSON string
            prompt = f"""Please determine which Session the new message should belong to based on the following information:

{json.dumps(router_input, ensure_ascii=False, indent=2)}

Please return your decision in strict JSON format."""

            response_text = ""
            async for message in self.client.send_message(
                message=prompt,
                session_id=f"router_{user_id}"  # Router's own session
            ):
                # Handle AssistantMessage - contains actual response content
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_text += block.text

            # Parse result
            try:
                # Extract JSON (may be mixed with other text)
                import re
                json_match = re.search(r'\{[^\}]*"decision"[^\}]*\}', response_text, re.DOTALL)
                if json_match:
                    decision = json.loads(json_match.group(0))
                else:
                    # Try to parse directly
                    decision = json.loads(response_text)

                # Validate required fields
                assert 'decision' in decision
                assert 'confidence' in decision
                assert decision['decision'] == 'NEW_SESSION' or decision['decision'].startswith('sess')

                logger.info(f"  Router decision: {decision['decision']} (confidence: {decision['confidence']})")
                return decision

            except Exception as e:
                logger.error(f"Failed to parse router decision: {e}")
                logger.error(f"Response text: {response_text}")
                # Fallback: create new Session
                return {
                    "decision": "NEW_SESSION",
                    "confidence": 0.0,
                    "reasoning": f"Router error: {str(e)}",
                    "matched_role": None
                }

        except Exception as e:
            logger.error(f"Session Router failed: {e}")
            # Fallback: create new Session
            return {
                "decision": "NEW_SESSION",
                "confidence": 0.0,
                "reasoning": f"Router error: {str(e)}",
                "matched_role": None
            }


# Global singleton
_session_router_service: Optional[SessionRouterService] = None


def get_session_router_service(redis_client=None) -> SessionRouterService:
    """
    Get SessionRouterService singleton

    Args:
        redis_client: Redis client

    Returns:
        SessionRouterService instance
    """
    global _session_router_service

    if _session_router_service is None:
        _session_router_service = SessionRouterService()

    return _session_router_service


# Export
__all__ = [
    "SessionRouterService",
    "get_session_router_service"
]
