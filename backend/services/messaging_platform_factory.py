"""
Messaging Platform Factory

Manages multi-platform messaging configurations dynamically.
Supports runtime registration and switching between platforms.

Design Pattern: Factory + Registry
- Centralized platform configuration management
- Easy to add new platforms (WeChat Work, Feishu, Slack, etc.)
- Supports multi-tenancy with platform-specific Redis prefixes
"""

import logging
from typing import Dict, List, Optional
from backend.config.messaging_platforms import (
    MessagingPlatformType,
    MessagingPlatformConfig,
    get_platform_config,
)

logger = logging.getLogger(__name__)


class MessagingPlatformFactory:
    """
    Factory for managing messaging platform configurations

    Supports:
    - Dynamic platform registration
    - MCP server configuration retrieval
    - Tool list retrieval
    - Redis key prefix management for multi-tenancy

    Example:
        factory = MessagingPlatformFactory()
        factory.register_platform(MessagingPlatformType.WEWORK)

        # Get MCP servers config for KB service
        mcp_servers = factory.get_mcp_servers_config([MessagingPlatformType.WEWORK])

        # Get tools list for agent
        tools = factory.get_tools([MessagingPlatformType.WEWORK])

        # Get Redis key prefix for conversation state
        prefix = factory.get_redis_key_prefix(MessagingPlatformType.WEWORK)
    """

    def __init__(self):
        """Initialize factory with empty registry"""
        self._registered_platforms: Dict[MessagingPlatformType, MessagingPlatformConfig] = {}
        logger.info("MessagingPlatformFactory initialized")

    def register_platform(self, platform: MessagingPlatformType) -> None:
        """
        Register a messaging platform

        Args:
            platform: Platform type to register

        Raises:
            ValueError: If platform not supported or already registered
        """
        if platform in self._registered_platforms:
            logger.warning(f"Platform {platform.value} already registered, skipping")
            return

        try:
            config = get_platform_config(platform)
            self._registered_platforms[platform] = config
            logger.info(f"Registered platform: {platform.value} (MCP: {config.mcp_server_name})")
        except Exception as e:
            logger.error(f"Failed to register platform {platform.value}: {e}")
            raise

    def unregister_platform(self, platform: MessagingPlatformType) -> None:
        """
        Unregister a messaging platform

        Args:
            platform: Platform type to unregister
        """
        if platform in self._registered_platforms:
            del self._registered_platforms[platform]
            logger.info(f"Unregistered platform: {platform.value}")

    def is_registered(self, platform: MessagingPlatformType) -> bool:
        """
        Check if a platform is registered

        Args:
            platform: Platform type to check

        Returns:
            True if platform is registered
        """
        return platform in self._registered_platforms

    def get_config(self, platform: MessagingPlatformType) -> MessagingPlatformConfig:
        """
        Get configuration for a registered platform

        Args:
            platform: Platform type

        Returns:
            Platform configuration

        Raises:
            ValueError: If platform not registered
        """
        if platform not in self._registered_platforms:
            raise ValueError(f"Platform {platform.value} not registered")

        return self._registered_platforms[platform]

    def get_mcp_servers_config(
        self,
        platforms: Optional[List[MessagingPlatformType]] = None
    ) -> Dict[str, Dict]:
        """
        Get MCP servers configuration for Claude Agent SDK

        Args:
            platforms: List of platforms to include. If None, include all registered.

        Returns:
            MCP servers config dict for ClaudeAgentOptions.mcp_servers

        Example:
            {
                "wework": {
                    "type": "stdio",
                    "command": "/path/to/wework-mcp",
                    "args": [],
                    "env": {...}
                },
                "feishu": {
                    "type": "stdio",
                    "command": "/path/to/feishu-mcp",
                    ...
                }
            }
        """
        if platforms is None:
            platforms = list(self._registered_platforms.keys())

        mcp_servers = {}
        for platform in platforms:
            if platform not in self._registered_platforms:
                logger.warning(f"Platform {platform.value} not registered, skipping")
                continue

            config = self._registered_platforms[platform]
            mcp_config = config.mcp_config

            mcp_servers[config.mcp_server_name] = {
                "type": mcp_config.type,
                "command": mcp_config.command,
                "args": mcp_config.args,
                "env": mcp_config.env,
            }

        return mcp_servers

    def get_tools(
        self,
        platforms: Optional[List[MessagingPlatformType]] = None,
        include_base_tools: bool = True
    ) -> List[str]:
        """
        Get tool list for agent's allowed_tools

        Args:
            platforms: List of platforms to include. If None, include all registered.
            include_base_tools: Whether to include base tools (Read, Write, etc.)

        Returns:
            List of tool names for ClaudeAgentOptions.allowed_tools

        Example:
            [
                "Read", "Write", "Grep", "Glob", "Bash",
                "mcp__wework__wework_send_text_message",
                "mcp__wework__wework_send_markdown_message",
                ...
            ]
        """
        tools = []

        # Base tools
        if include_base_tools:
            tools.extend([
                "Read",
                "Write",
                "Grep",
                "Glob",
                "Bash",
            ])

        # Platform-specific MCP tools
        if platforms is None:
            platforms = list(self._registered_platforms.keys())

        for platform in platforms:
            if platform not in self._registered_platforms:
                logger.warning(f"Platform {platform.value} not registered, skipping")
                continue

            config = self._registered_platforms[platform]
            tools.extend(config.tools)

        return tools

    def get_redis_key_prefix(self, platform: MessagingPlatformType) -> str:
        """
        Get Redis key prefix for a platform

        Args:
            platform: Platform type

        Returns:
            Redis key prefix (e.g., "wework", "feishu")

        Example:
            prefix = factory.get_redis_key_prefix(MessagingPlatformType.WEWORK)
            # Use as: f"{prefix}:conv_state:{user_id}"
        """
        if platform not in self._registered_platforms:
            raise ValueError(f"Platform {platform.value} not registered")

        return self._registered_platforms[platform].redis_key_prefix

    def get_all_registered_platforms(self) -> List[MessagingPlatformType]:
        """
        Get list of all registered platforms

        Returns:
            List of registered platform types
        """
        return list(self._registered_platforms.keys())


# Singleton instance
_messaging_platform_factory: Optional[MessagingPlatformFactory] = None


def get_messaging_platform_factory() -> MessagingPlatformFactory:
    """
    Get singleton instance of MessagingPlatformFactory

    Returns:
        MessagingPlatformFactory instance
    """
    global _messaging_platform_factory

    if _messaging_platform_factory is None:
        _messaging_platform_factory = MessagingPlatformFactory()

    return _messaging_platform_factory


__all__ = [
    "MessagingPlatformFactory",
    "get_messaging_platform_factory",
]
