"""
Channel Message Router

Unified management of all IM channel adapters, responsible for:
1. Auto-discovery and registration of configured channels
2. Routing IM messages to User Agent
3. Sending Agent responses back to users (via adapters)
4. Providing channel status queries
"""

import logging
from typing import Dict, List, Optional
from pathlib import Path

from backend.channels.base import (
    BaseChannelAdapter,
    ChannelMessage,
    ChannelType,
    MessageType,
    ChannelNotConfiguredError
)

logger = logging.getLogger(__name__)


class ChannelMessageRouter:
    """Channel Message Router"""

    def __init__(self):
        """Initialize router"""
        self.adapters: Dict[str, BaseChannelAdapter] = {}
        self._initialized = False

    async def initialize(self):
        """Initialize router: discover and register configured channels"""
        if self._initialized:
            logger.warning("ChannelMessageRouter already initialized")
            return

        logger.info("Initializing ChannelMessageRouter...")

        # Auto-discover and register adapters
        await self._discover_adapters()

        self._initialized = True
        logger.info(f"✅ ChannelMessageRouter initialized with {len(self.adapters)} channels: {list(self.adapters.keys())}")

    async def _discover_adapters(self):
        """Auto-discover and register configured adapters"""

        # Try to import and register channel adapters
        adapter_classes = []

        # WeWork
        try:
            from backend.channels.wework import WeWorkAdapter
            adapter_classes.append(WeWorkAdapter)
        except ImportError as e:
            logger.warning(f"WeWork adapter not available: {e}")

        # Feishu (Lark) - to be implemented
        try:
            from backend.channels.feishu import FeishuAdapter
            adapter_classes.append(FeishuAdapter)
        except ImportError:
            pass  # Feishu not yet implemented

        # DingTalk - to be implemented
        try:
            from backend.channels.dingtalk import DingTalkAdapter
            adapter_classes.append(DingTalkAdapter)
        except ImportError:
            pass

        # Slack - to be implemented
        try:
            from backend.channels.slack import SlackAdapter
            adapter_classes.append(SlackAdapter)
        except ImportError:
            pass

        # Register configured adapters
        for AdapterClass in adapter_classes:
            try:
                adapter = AdapterClass()

                # Check if configured
                if adapter.is_configured():
                    await adapter.initialize()
                    self.adapters[adapter.channel_name] = adapter
                    logger.info(f"✅ Registered channel: {adapter.channel_name}")
                else:
                    logger.info(f"⏭️  Skipped channel: {adapter.channel_name} (not configured)")
                    logger.debug(f"   Required env vars: {adapter.get_required_env_vars()}")

            except Exception as e:
                logger.error(f"Failed to initialize adapter {AdapterClass.__name__}: {e}", exc_info=True)

    def get_adapter(self, channel: str) -> Optional[BaseChannelAdapter]:
        """
        Get adapter for specified channel

        Args:
            channel: Channel name (wework/feishu/dingtalk/slack)

        Returns:
            BaseChannelAdapter or None
        """
        return self.adapters.get(channel)

    def get_active_channels(self) -> List[str]:
        """
        Get list of active channels

        Returns:
            List[str]: Channel name list
        """
        return list(self.adapters.keys())

    async def route_message(
        self,
        channel: str,
        message: ChannelMessage,
        user_service = None
    ) -> str:
        """
        Route IM message to User Agent and return response

        Flow:
        1. Verify channel exists
        2. Call User Service to process message
        3. Collect Agent response
        4. Send back to user via adapter

        Args:
            channel: Channel name
            message: ChannelMessage object
            user_service: User Service instance (optional, for dependency injection)

        Returns:
            str: Agent response text

        Raises:
            ValueError: Channel not configured or message routing failed
        """
        # Verify channel
        adapter = self.get_adapter(channel)
        if not adapter:
            raise ValueError(f"Channel not configured: {channel}")

        logger.info(f"Routing message from {channel}:{message.user.user_id} → User Agent")

        # Get User Service
        if user_service is None:
            from backend.services.kb_service_factory import get_user_service
            user_service = get_user_service()

        # Ensure service is initialized
        if not user_service.is_initialized:
            await user_service.initialize()
            logger.info("User service initialized")

        # Construct message (including user info)
        formatted_message = f"""[User Info]
user_id: {message.user.user_id}
channel: {channel}

[User Message]
{message.content}"""

        # Call User Agent
        agent_response_text = ""
        message_count = 0

        try:
            logger.info(f"Calling User Agent with session {message.session_id or 'new'}")

            async for msg in user_service.query(
                user_message=formatted_message,
                session_id=message.session_id,
                user_id=message.user.user_id
            ):
                message_count += 1
                agent_response_text += msg.text
                logger.debug(f"Received message {message_count} from User Agent (len={len(msg.text)})")

            logger.info(f"✅ Received {message_count} messages from User Agent (total length={len(agent_response_text)})")

            if message_count == 0:
                logger.error(f"No response from User Agent for {message.user.user_id}")
                agent_response_text = "Sorry, the service is temporarily unavailable. Please try again later."

        except Exception as e:
            logger.error(f"User Agent call failed: {type(e).__name__}: {str(e)}", exc_info=True)
            agent_response_text = f"Sorry, an error occurred while processing the message: {str(e)}"

        # Send response (via adapter)
        await self.send_response(
            channel=channel,
            user_id=message.user.user_id,
            content=agent_response_text
        )

        return agent_response_text

    async def send_response(
        self,
        channel: str,
        user_id: str,
        content: str,
        msg_type: MessageType = MessageType.TEXT,
        **kwargs
    ):
        """
        Send response message via specified channel

        Args:
            channel: Channel name
            user_id: Target user ID
            content: Message content
            msg_type: Message type
            **kwargs: Platform-specific parameters
        """
        adapter = self.get_adapter(channel)
        if not adapter:
            raise ValueError(f"Channel not configured: {channel}")

        result = await adapter.send_message(user_id, content, msg_type, **kwargs)

        if not result.success:
            logger.error(f"Failed to send message via {channel}: {result.error}")
            raise Exception(f"Failed to send message: {result.error}")

        logger.info(f"✅ Message sent to {channel}:{user_id}")

    async def send_batch_response(
        self,
        channel: str,
        user_ids: List[str],
        content: str,
        msg_type: MessageType = MessageType.TEXT,
        **kwargs
    ):
        """
        Send messages in batch

        Args:
            channel: Channel name
            user_ids: Target user ID list
            content: Message content
            msg_type: Message type
            **kwargs: Platform-specific parameters
        """
        adapter = self.get_adapter(channel)
        if not adapter:
            raise ValueError(f"Channel not configured: {channel}")

        results = await adapter.send_batch_message(user_ids, content, msg_type, **kwargs)

        success_count = sum(1 for r in results if r.success)
        logger.info(f"✅ Batch send completed: {success_count}/{len(user_ids)} successful")

        if success_count < len(user_ids):
            failed_count = len(user_ids) - success_count
            logger.warning(f"⚠️  {failed_count} messages failed to send")

    def get_channel_status(self) -> Dict[str, Dict]:
        """
        Get status of all channels

        Returns:
            Dict[str, Dict]: Channel status dictionary
        """
        status = {}
        for channel_name, adapter in self.adapters.items():
            status[channel_name] = {
                "configured": adapter.is_configured(),
                "initialized": adapter._initialized,
                "required_env_vars": adapter.get_required_env_vars()
            }
        return status


# Singleton pattern
_router_instance: Optional[ChannelMessageRouter] = None


def get_channel_router() -> ChannelMessageRouter:
    """
    Get channel router singleton

    Returns:
        ChannelMessageRouter
    """
    global _router_instance
    if _router_instance is None:
        _router_instance = ChannelMessageRouter()
    return _router_instance


async def initialize_channel_router() -> ChannelMessageRouter:
    """
    Initialize channel router (ensure initialized)

    Returns:
        ChannelMessageRouter
    """
    router = get_channel_router()
    if not router._initialized:
        await router.initialize()
    return router
