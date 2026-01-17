"""
Channel adapter module

Provides unified messaging interface, supports multiple IM platforms:
- 企业微信 (WeWork)
- 飞书 (Feishu/Lark)
- 钉钉 (DingTalk)
- Slack

Usage:
    from backend.channels import BaseChannelAdapter, ChannelMessage
    from backend.channels.wework import WeWorkAdapter

    # Create adapter
    adapter = WeWorkAdapter()

    # Check if configured
    if adapter.is_configured():
        # Parse message
        message = await adapter.parse_message(request_data)

        # Send response
        await adapter.send_message(user_id, "Hello!")
"""

from backend.channels.base import (
    # Abstract base class
    BaseChannelAdapter,

    # Data models
    ChannelMessage,
    ChannelUser,
    ChannelResponse,

    # Enum types
    MessageType,
    ChannelType,

    # Exception classes
    ChannelAdapterError,
    ChannelNotConfiguredError,
    ChannelMessageError,
    ChannelAuthError,
)

__all__ = [
    # Abstract base class
    "BaseChannelAdapter",

    # Data models
    "ChannelMessage",
    "ChannelUser",
    "ChannelResponse",

    # Enum types
    "MessageType",
    "ChannelType",

    # Exception classes
    "ChannelAdapterError",
    "ChannelNotConfiguredError",
    "ChannelMessageError",
    "ChannelAuthError",
]
