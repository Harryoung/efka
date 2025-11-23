"""
Configuration module
"""

from .messaging_platforms import (
    MessagingPlatformType,
    MCPServerConfig,
    MessagingPlatformConfig,
    get_platform_config,
    get_wework_config,
)

__all__ = [
    "MessagingPlatformType",
    "MCPServerConfig",
    "MessagingPlatformConfig",
    "get_platform_config",
    "get_wework_config",
]
