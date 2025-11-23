"""
Messaging Platform Configuration

Provides abstraction for multi-platform messaging integration.
Supports WeChat Work (企业微信), Feishu (飞书), Slack, and other platforms.

Design:
- Platform-specific MCP server configurations
- Platform-specific tool lists
- Redis key prefixes for multi-tenancy
- Environment variable mapping
"""

import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MessagingPlatformType(str, Enum):
    """Supported messaging platforms"""
    WEWORK = "wework"  # WeChat Work (企业微信)
    FEISHU = "feishu"  # Feishu (飞书)
    SLACK = "slack"  # Slack
    DINGTALK = "dingtalk"  # DingTalk (钉钉)


@dataclass
class MCPServerConfig:
    """MCP Server configuration for a platform"""
    type: str  # "stdio" or "sse"
    command: str  # Command to execute (e.g., "wework-mcp")
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)


@dataclass
class MessagingPlatformConfig:
    """
    Configuration for a messaging platform

    Attributes:
        platform_type: Platform identifier
        mcp_server_name: MCP server name (e.g., "wework", "feishu")
        mcp_config: MCP server configuration
        tools: List of MCP tool names (e.g., ["mcp__wework__send_text_message"])
        redis_key_prefix: Redis key prefix for this platform (e.g., "wework")
        env_vars: Environment variable names for this platform
    """
    platform_type: MessagingPlatformType
    mcp_server_name: str
    mcp_config: MCPServerConfig
    tools: List[str]
    redis_key_prefix: str
    env_vars: Dict[str, str] = field(default_factory=dict)


def get_wework_config() -> MessagingPlatformConfig:
    """
    Get WeChat Work (企业微信) platform configuration

    Returns:
        MessagingPlatformConfig for WeChat Work
    """
    import sys
    import shutil

    # Find wework-mcp command path (supports virtual environments)
    wework_mcp_path = shutil.which("wework-mcp")
    if not wework_mcp_path:
        # Try to find in virtual environment
        venv_path = Path(sys.executable).parent / "wework-mcp"
        if venv_path.exists():
            wework_mcp_path = str(venv_path)
        else:
            logger.warning("wework-mcp not found in PATH or venv, using 'wework-mcp' (may fail)")
            wework_mcp_path = "wework-mcp"

    logger.info(f"Using wework-mcp at: {wework_mcp_path}")

    mcp_config = MCPServerConfig(
        type="stdio",
        command=wework_mcp_path,
        args=[],
        env={
            "WEWORK_CORP_ID": os.getenv("WEWORK_CORP_ID", ""),
            "WEWORK_CORP_SECRET": os.getenv("WEWORK_CORP_SECRET", ""),
            "WEWORK_AGENT_ID": os.getenv("WEWORK_AGENT_ID", ""),
        }
    )

    tools = [
        "mcp__wework__wework_send_text_message",
        "mcp__wework__wework_send_markdown_message",
        "mcp__wework__wework_send_image_message",
        "mcp__wework__wework_send_file_message",
        "mcp__wework__wework_upload_media",
    ]

    return MessagingPlatformConfig(
        platform_type=MessagingPlatformType.WEWORK,
        mcp_server_name="wework",
        mcp_config=mcp_config,
        tools=tools,
        redis_key_prefix="wework",
        env_vars={
            "corp_id": "WEWORK_CORP_ID",
            "corp_secret": "WEWORK_CORP_SECRET",
            "agent_id": "WEWORK_AGENT_ID",
        }
    )


def get_feishu_config() -> MessagingPlatformConfig:
    """
    Get Feishu (飞书) platform configuration (placeholder)

    Returns:
        MessagingPlatformConfig for Feishu
    """
    # TODO: Implement Feishu configuration when integrating
    raise NotImplementedError("Feishu integration not yet implemented")


def get_slack_config() -> MessagingPlatformConfig:
    """
    Get Slack platform configuration (placeholder)

    Returns:
        MessagingPlatformConfig for Slack
    """
    # TODO: Implement Slack configuration when integrating
    raise NotImplementedError("Slack integration not yet implemented")


def get_dingtalk_config() -> MessagingPlatformConfig:
    """
    Get DingTalk (钉钉) platform configuration (placeholder)

    Returns:
        MessagingPlatformConfig for DingTalk
    """
    # TODO: Implement DingTalk configuration when integrating
    raise NotImplementedError("DingTalk integration not yet implemented")


# Platform configuration registry
PLATFORM_CONFIG_REGISTRY = {
    MessagingPlatformType.WEWORK: get_wework_config,
    MessagingPlatformType.FEISHU: get_feishu_config,
    MessagingPlatformType.SLACK: get_slack_config,
    MessagingPlatformType.DINGTALK: get_dingtalk_config,
}


def get_platform_config(platform: MessagingPlatformType) -> MessagingPlatformConfig:
    """
    Get configuration for a specific platform

    Args:
        platform: Platform type

    Returns:
        Platform configuration

    Raises:
        ValueError: If platform not supported or not configured
    """
    if platform not in PLATFORM_CONFIG_REGISTRY:
        raise ValueError(f"Unsupported platform: {platform}")

    config_func = PLATFORM_CONFIG_REGISTRY[platform]
    return config_func()


__all__ = [
    "MessagingPlatformType",
    "MCPServerConfig",
    "MessagingPlatformConfig",
    "get_platform_config",
    "get_wework_config",
    "PLATFORM_CONFIG_REGISTRY",
]
