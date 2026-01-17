"""
WeWork (企业微信) channel module

Provides complete WeWork integration features:
- WeWorkAdapter: Implements BaseChannelAdapter interface
- WeWorkClient: API client
- Flask callback server

Usage:
    from backend.channels.wework import WeWorkAdapter

    adapter = WeWorkAdapter()
    if adapter.is_configured():
        # Send message
        result = await adapter.send_message("userid", "Hello!")

        # Parse callback message
        msg = await adapter.parse_message(request_data)
"""

from backend.channels.wework.adapter import WeWorkAdapter
from backend.channels.wework.client import WeWorkClient, WeWorkAPIError

__all__ = [
    "WeWorkAdapter",
    "WeWorkClient",
    "WeWorkAPIError",
]
