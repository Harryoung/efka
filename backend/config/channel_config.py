"""
渠道配置管理

v3.0 重构: 简化为端口配置管理
运行模式现在通过 run_mode.py 管理

使用方式:
    from backend.config.channel_config import get_channel_port, CHANNEL_PORTS
"""

import os
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


# 各渠道所需的环境变量（用于配置验证）
CHANNEL_ENV_VARS: Dict[str, List[str]] = {
    "wework": ["WEWORK_CORP_ID", "WEWORK_CORP_SECRET", "WEWORK_AGENT_ID", "WEWORK_TOKEN", "WEWORK_ENCODING_AES_KEY"],
    "feishu": ["FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_VERIFICATION_TOKEN", "FEISHU_ENCRYPT_KEY"],
    "dingtalk": ["DINGTALK_CORP_ID", "DINGTALK_APP_KEY", "DINGTALK_APP_SECRET"],
    "slack": ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "SLACK_APP_TOKEN"]
}

# 各渠道的默认端口
CHANNEL_PORTS: Dict[str, int] = {
    "wework": 8081,
    "feishu": 8082,
    "dingtalk": 8083,
    "slack": 8084
}


def get_channel_port(channel: str) -> int:
    """
    获取渠道的监听端口

    Args:
        channel: 渠道名称 (wework/feishu/dingtalk/slack)

    Returns:
        int: 端口号
    """
    # 优先从环境变量读取
    env_var = f"{channel.upper()}_PORT"
    port_str = os.getenv(env_var)

    if port_str:
        try:
            return int(port_str)
        except ValueError:
            logger.warning(f"Invalid port value for {env_var}: {port_str}, using default")

    # 使用默认端口
    return CHANNEL_PORTS.get(channel, 8080)


def get_channel_env_vars(channel: str) -> List[str]:
    """
    获取渠道所需的环境变量列表

    Args:
        channel: 渠道名称

    Returns:
        List[str]: 环境变量列表
    """
    return CHANNEL_ENV_VARS.get(channel, [])


def is_channel_configured(channel: str) -> bool:
    """
    检查渠道是否已配置(所有必需环境变量都存在)

    Args:
        channel: 渠道名称

    Returns:
        bool: 是否已配置
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
