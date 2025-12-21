"""
运行模式配置模块

支持 standalone 模式（纯 Web）和 IM 集成模式（企微/飞书/钉钉/Slack）的显式区分。
单渠道互斥：IM 模式下只能选择一个渠道。

配置优先级：CLI --mode > ENV RUN_MODE > 默认 standalone

使用方式:
    from backend.config.run_mode import get_run_mode, is_standalone, get_im_channel

    mode = get_run_mode()
    if is_standalone():
        # 纯 Web 模式
        pass
    else:
        channel = get_im_channel()  # wework/feishu/dingtalk/slack
"""

from enum import Enum
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)


class RunMode(str, Enum):
    """运行模式枚举"""
    STANDALONE = "standalone"
    WEWORK = "wework"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    SLACK = "slack"


class RunModeConfig:
    """
    运行模式配置管理器

    支持三级优先级：
    1. CLI 参数（通过 set_cli_mode 设置）
    2. 环境变量 RUN_MODE
    3. 默认值 standalone
    """
    _mode: Optional[RunMode] = None
    _cli_override: Optional[str] = None

    @classmethod
    def set_cli_mode(cls, mode: str) -> None:
        """
        设置 CLI 传入的运行模式（最高优先级）

        Args:
            mode: 运行模式字符串 (standalone/wework/feishu/dingtalk/slack)

        Raises:
            ValueError: 如果 mode 不是有效的运行模式
        """
        mode_lower = mode.lower()
        valid_modes = [m.value for m in RunMode]
        if mode_lower not in valid_modes:
            raise ValueError(
                f"Invalid run mode: '{mode}'. "
                f"Valid modes: {', '.join(valid_modes)}"
            )
        cls._cli_override = mode_lower
        cls._mode = None  # 清除缓存，下次调用 get_mode 时重新计算
        logger.info(f"CLI run mode set to: {mode_lower}")

    @classmethod
    def get_mode(cls) -> RunMode:
        """
        获取当前运行模式

        优先级：CLI > ENV > 默认 standalone

        Returns:
            RunMode 枚举值
        """
        if cls._mode is not None:
            return cls._mode

        # Priority 1: CLI 参数
        if cls._cli_override:
            cls._mode = RunMode(cls._cli_override)
            logger.debug(f"Using CLI run mode: {cls._mode.value}")
            return cls._mode

        # Priority 2: 环境变量
        env_mode = os.getenv("RUN_MODE", "").lower().strip()
        if env_mode:
            valid_modes = [m.value for m in RunMode]
            if env_mode in valid_modes:
                cls._mode = RunMode(env_mode)
                logger.debug(f"Using ENV run mode: {cls._mode.value}")
                return cls._mode
            else:
                logger.warning(
                    f"Invalid RUN_MODE env value: '{env_mode}', "
                    f"falling back to 'standalone'. "
                    f"Valid modes: {', '.join(valid_modes)}"
                )

        # Priority 3: 默认值
        cls._mode = RunMode.STANDALONE
        logger.debug(f"Using default run mode: {cls._mode.value}")
        return cls._mode

    @classmethod
    def is_standalone(cls) -> bool:
        """
        判断是否为 standalone 模式

        Returns:
            True 如果是 standalone 模式
        """
        return cls.get_mode() == RunMode.STANDALONE

    @classmethod
    def get_im_channel(cls) -> Optional[str]:
        """
        获取当前 IM 渠道名称

        Returns:
            渠道名称字符串 (wework/feishu/dingtalk/slack)，
            如果是 standalone 模式则返回 None
        """
        mode = cls.get_mode()
        if mode == RunMode.STANDALONE:
            return None
        return mode.value

    @classmethod
    def reset(cls) -> None:
        """
        重置配置状态（主要用于测试）
        """
        cls._mode = None
        cls._cli_override = None


# 便捷函数
def get_run_mode() -> RunMode:
    """获取当前运行模式"""
    return RunModeConfig.get_mode()


def is_standalone() -> bool:
    """判断是否为 standalone 模式"""
    return RunModeConfig.is_standalone()


def get_im_channel() -> Optional[str]:
    """获取当前 IM 渠道名称（standalone 模式返回 None）"""
    return RunModeConfig.get_im_channel()


def set_cli_mode(mode: str) -> None:
    """设置 CLI 传入的运行模式"""
    RunModeConfig.set_cli_mode(mode)


__all__ = [
    "RunMode",
    "RunModeConfig",
    "get_run_mode",
    "is_standalone",
    "get_im_channel",
    "set_cli_mode",
]
