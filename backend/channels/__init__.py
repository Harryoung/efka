"""
渠道适配器模块

提供统一的消息接口,支持多种IM平台:
- 企业微信 (WeWork)
- 飞书 (Feishu/Lark)
- 钉钉 (DingTalk)
- Slack

使用方式:
    from backend.channels import BaseChannelAdapter, ChannelMessage
    from backend.channels.wework import WeWorkAdapter

    # 创建适配器
    adapter = WeWorkAdapter()

    # 检查是否配置
    if adapter.is_configured():
        # 解析消息
        message = await adapter.parse_message(request_data)

        # 发送响应
        await adapter.send_message(user_id, "您好!")
"""

from backend.channels.base import (
    # 抽象基类
    BaseChannelAdapter,

    # 数据模型
    ChannelMessage,
    ChannelUser,
    ChannelResponse,

    # 枚举类型
    MessageType,
    ChannelType,

    # 异常类
    ChannelAdapterError,
    ChannelNotConfiguredError,
    ChannelMessageError,
    ChannelAuthError,
)

__all__ = [
    # 抽象基类
    "BaseChannelAdapter",

    # 数据模型
    "ChannelMessage",
    "ChannelUser",
    "ChannelResponse",

    # 枚举类型
    "MessageType",
    "ChannelType",

    # 异常类
    "ChannelAdapterError",
    "ChannelNotConfiguredError",
    "ChannelMessageError",
    "ChannelAuthError",
]
