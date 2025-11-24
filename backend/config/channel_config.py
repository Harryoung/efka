"""
渠道配置管理

混合模式配置策略:
- auto: 自动检测(检查必要环境变量是否配置)
- enabled: 强制启用
- disabled: 强制禁用

使用方式:
    from backend.config.channel_config import get_channel_config

    config = get_channel_config()
    if config.is_channel_enabled("wework"):
        # 启动WeWork服务
        pass
"""

import os
import logging
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ChannelMode(str, Enum):
    """渠道启用模式"""
    AUTO = "auto"  # 自动检测
    ENABLED = "enabled"  # 强制启用
    DISABLED = "disabled"  # 强制禁用


class ChannelConfig:
    """渠道配置管理器"""

    # 各渠道所需的环境变量
    CHANNEL_ENV_VARS = {
        "wework": ["WEWORK_CORP_ID", "WEWORK_CORP_SECRET", "WEWORK_AGENT_ID", "WEWORK_TOKEN", "WEWORK_ENCODING_AES_KEY"],
        "feishu": ["FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_VERIFICATION_TOKEN", "FEISHU_ENCRYPT_KEY"],
        "dingtalk": ["DINGTALK_CORP_ID", "DINGTALK_APP_KEY", "DINGTALK_APP_SECRET"],
        "slack": ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "SLACK_APP_TOKEN"]
    }

    # 各渠道的默认端口
    CHANNEL_PORTS = {
        "wework": 8081,
        "feishu": 8082,
        "dingtalk": 8083,
        "slack": 8084
    }

    def __init__(self):
        """初始化配置"""
        # 读取各渠道的启用模式
        self.channel_modes: Dict[str, ChannelMode] = {}
        for channel in self.CHANNEL_ENV_VARS.keys():
            mode_str = os.getenv(f"ENABLE_{channel.upper()}", "auto").lower()
            try:
                self.channel_modes[channel] = ChannelMode(mode_str)
            except ValueError:
                logger.warning(f"Invalid mode '{mode_str}' for {channel}, defaulting to 'auto'")
                self.channel_modes[channel] = ChannelMode.AUTO

        logger.info(f"Channel modes: {self.channel_modes}")

    def is_channel_enabled(self, channel: str) -> bool:
        """
        判断渠道是否启用

        Args:
            channel: 渠道名称(wework/feishu/dingtalk/slack)

        Returns:
            bool: 是否启用
        """
        mode = self.channel_modes.get(channel, ChannelMode.AUTO)

        if mode == ChannelMode.DISABLED:
            return False
        elif mode == ChannelMode.ENABLED:
            return True
        else:  # AUTO
            return self._check_channel_configured(channel)

    def _check_channel_configured(self, channel: str) -> bool:
        """
        检查渠道是否已配置(所有必需环境变量都存在)

        Args:
            channel: 渠道名称

        Returns:
            bool: 是否已配置
        """
        required_vars = self.CHANNEL_ENV_VARS.get(channel, [])

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

    def get_enabled_channels(self) -> List[str]:
        """
        获取所有已启用的渠道列表

        Returns:
            List[str]: 渠道名称列表
        """
        enabled = []
        for channel in self.CHANNEL_ENV_VARS.keys():
            if self.is_channel_enabled(channel):
                enabled.append(channel)

        return enabled

    def get_channel_port(self, channel: str) -> int:
        """
        获取渠道的监听端口

        Args:
            channel: 渠道名称

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
        return self.CHANNEL_PORTS.get(channel, 8080 + len(channel))

    def get_channel_mode(self, channel: str) -> ChannelMode:
        """
        获取渠道的启用模式

        Args:
            channel: 渠道名称

        Returns:
            ChannelMode: 启用模式
        """
        return self.channel_modes.get(channel, ChannelMode.AUTO)

    def get_channel_status(self) -> Dict[str, Dict]:
        """
        获取所有渠道的状态信息

        Returns:
            Dict[str, Dict]: 渠道状态字典
        """
        status = {}

        for channel in self.CHANNEL_ENV_VARS.keys():
            mode = self.get_channel_mode(channel)
            enabled = self.is_channel_enabled(channel)
            configured = self._check_channel_configured(channel)
            port = self.get_channel_port(channel)

            status[channel] = {
                "mode": mode.value,
                "enabled": enabled,
                "configured": configured,
                "port": port,
                "required_env_vars": self.CHANNEL_ENV_VARS[channel]
            }

        return status

    def validate_enabled_channels(self) -> List[str]:
        """
        验证已启用的渠道配置

        Returns:
            List[str]: 配置错误的渠道列表
        """
        errors = []

        for channel in self.get_enabled_channels():
            mode = self.get_channel_mode(channel)

            # 强制启用但未配置
            if mode == ChannelMode.ENABLED and not self._check_channel_configured(channel):
                missing_vars = [
                    var for var in self.CHANNEL_ENV_VARS[channel]
                    if not os.getenv(var)
                ]
                error_msg = f"{channel} is set to 'enabled' but missing env vars: {missing_vars}"
                logger.error(f"❌ {error_msg}")
                errors.append(error_msg)

        return errors

    def get_required_env_vars(self, channel: str) -> List[str]:
        """
        获取渠道所需的环境变量列表

        Args:
            channel: 渠道名称

        Returns:
            List[str]: 环境变量列表
        """
        return self.CHANNEL_ENV_VARS.get(channel, [])


# 单例模式
_config_instance: Optional[ChannelConfig] = None


def get_channel_config() -> ChannelConfig:
    """
    获取渠道配置单例

    Returns:
        ChannelConfig
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = ChannelConfig()
    return _config_instance


# 便捷函数
def is_channel_enabled(channel: str) -> bool:
    """
    判断渠道是否启用(便捷函数)

    Args:
        channel: 渠道名称

    Returns:
        bool: 是否启用
    """
    return get_channel_config().is_channel_enabled(channel)


def get_enabled_channels() -> List[str]:
    """
    获取已启用的渠道列表(便捷函数)

    Returns:
        List[str]: 渠道名称列表
    """
    return get_channel_config().get_enabled_channels()


def validate_channel_config() -> List[str]:
    """
    验证渠道配置(便捷函数)

    Returns:
        List[str]: 配置错误列表
    """
    return get_channel_config().validate_enabled_channels()
