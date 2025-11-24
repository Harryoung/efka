"""
WeWork MCP - Enterprise WeChat messaging integration for Model Context Protocol
"""

__version__ = "1.0.0"

from .config import WeWorkConfig
from .weework_client import WeWorkClient, WeWorkAPIError
from .token_manager import AccessTokenManager

__all__ = [
    "WeWorkConfig",
    "WeWorkClient",
    "WeWorkAPIError",
    "AccessTokenManager",
]
