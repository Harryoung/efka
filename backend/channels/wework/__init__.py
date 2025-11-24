"""
企业微信渠道模块

提供企微集成的完整功能:
- WeWorkAdapter: 实现BaseChannelAdapter接口
- WeWorkClient: API客户端
- Flask回调服务器

使用方式:
    from backend.channels.wework import WeWorkAdapter

    adapter = WeWorkAdapter()
    if adapter.is_configured():
        # 发送消息
        result = await adapter.send_message("userid", "Hello!")

        # 解析回调消息
        msg = await adapter.parse_message(request_data)
"""

from backend.channels.wework.adapter import WeWorkAdapter
from backend.channels.wework.client import WeWorkClient, WeWorkAPIError

__all__ = [
    "WeWorkAdapter",
    "WeWorkClient",
    "WeWorkAPIError",
]
