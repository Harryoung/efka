"""
Channel configuration management

v3.0 Refactor: Simplified to port configuration management
Run mode is now managed through run_mode.py

Usage:
    from backend.config.channel_config import get_channel_port, CHANNEL_PORTS
"""

import os
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


# Environment variables required for each channel (for configuration validation)
CHANNEL_ENV_VARS: Dict[str, List[str]] = {
    "wework": ["WEWORK_CORP_ID", "WEWORK_CORP_SECRET", "WEWORK_AGENT_ID", "WEWORK_TOKEN", "WEWORK_ENCODING_AES_KEY"],
    "feishu": ["FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_VERIFICATION_TOKEN", "FEISHU_ENCRYPT_KEY"],
    "dingtalk": ["DINGTALK_CORP_ID", "DINGTALK_APP_KEY", "DINGTALK_APP_SECRET"],
    "slack": ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "SLACK_APP_TOKEN"]
}

# Default ports for each channel
CHANNEL_PORTS: Dict[str, int] = {
    "wework": 8081,
    "feishu": 8082,
    "dingtalk": 8083,
    "slack": 8084
}


def get_channel_port(channel: str) -> int:
    """
    Get the listening port for a channel

    Args:
        channel: Channel name (wework/feishu/dingtalk/slack)

    Returns:
        int: Port number
    """
    # Read from environment variable first
    env_var = f"{channel.upper()}_PORT"
    port_str = os.getenv(env_var)

    if port_str:
        try:
            return int(port_str)
        except ValueError:
            logger.warning(f"Invalid port value for {env_var}: {port_str}, using default")

    # Use default port
    return CHANNEL_PORTS.get(channel, 8080)


def get_channel_env_vars(channel: str) -> List[str]:
    """
    Get the list of environment variables required for a channel

    Args:
        channel: Channel name

    Returns:
        List[str]: Environment variable list
    """
    return CHANNEL_ENV_VARS.get(channel, [])


def is_channel_configured(channel: str) -> bool:
    """
    Check if a channel is configured (all required environment variables exist)

    Args:
        channel: Channel name

    Returns:
        bool: Whether the channel is configured
    """
    required_vars = CHANNEL_ENV_VARS.get(channel, [])

    if not required_vars:
        logger.warning(f"Unknown channel: {channel}")
        return False

    configured = all(os.getenv(var) for var in required_vars)

    if configured:
        logger.debug(f"✅ Channel {channel} is configured")
    else:
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        logger.debug(f"⏭️  Channel {channel} not configured (missing: {missing_vars})")

    return configured


__all__ = [
    "CHANNEL_ENV_VARS",
    "CHANNEL_PORTS",
    "get_channel_port",
    "get_channel_env_vars",
    "is_channel_configured",
]
