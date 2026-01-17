"""
Run mode configuration module

Supports explicit distinction between standalone mode (pure Web) and IM integration mode (WeWork/Feishu/DingTalk/Slack).
Single channel mutual exclusion: only one channel can be selected in IM mode.

Configuration priority: CLI --mode > ENV RUN_MODE > default standalone

Usage:
    from backend.config.run_mode import get_run_mode, is_standalone, get_im_channel

    mode = get_run_mode()
    if is_standalone():
        # Pure Web mode
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
    """Run mode enumeration"""
    STANDALONE = "standalone"
    WEWORK = "wework"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    SLACK = "slack"


class RunModeConfig:
    """
    Run mode configuration manager

    Supports three-level priority:
    1. CLI parameter (set via set_cli_mode)
    2. Environment variable RUN_MODE
    3. Default value standalone
    """
    _mode: Optional[RunMode] = None
    _cli_override: Optional[str] = None

    @classmethod
    def set_cli_mode(cls, mode: str) -> None:
        """
        Set the run mode passed from CLI (highest priority)

        Args:
            mode: Run mode string (standalone/wework/feishu/dingtalk/slack)

        Raises:
            ValueError: If mode is not a valid run mode
        """
        mode_lower = mode.lower()
        valid_modes = [m.value for m in RunMode]
        if mode_lower not in valid_modes:
            raise ValueError(
                f"Invalid run mode: '{mode}'. "
                f"Valid modes: {', '.join(valid_modes)}"
            )
        cls._cli_override = mode_lower
        cls._mode = None  # Clear cache, recalculate on next get_mode call
        logger.info(f"CLI run mode set to: {mode_lower}")

    @classmethod
    def get_mode(cls) -> RunMode:
        """
        Get the current run mode

        Priority: CLI > ENV > default standalone

        Returns:
            RunMode enum value
        """
        if cls._mode is not None:
            return cls._mode

        # Priority 1: CLI parameter
        if cls._cli_override:
            cls._mode = RunMode(cls._cli_override)
            logger.debug(f"Using CLI run mode: {cls._mode.value}")
            return cls._mode

        # Priority 2: Environment variable
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

        # Priority 3: Default value
        cls._mode = RunMode.STANDALONE
        logger.debug(f"Using default run mode: {cls._mode.value}")
        return cls._mode

    @classmethod
    def is_standalone(cls) -> bool:
        """
        Check if it is standalone mode

        Returns:
            True if it is standalone mode
        """
        return cls.get_mode() == RunMode.STANDALONE

    @classmethod
    def get_im_channel(cls) -> Optional[str]:
        """
        Get the current IM channel name

        Returns:
            Channel name string (wework/feishu/dingtalk/slack),
            or None if in standalone mode
        """
        mode = cls.get_mode()
        if mode == RunMode.STANDALONE:
            return None
        return mode.value

    @classmethod
    def reset(cls) -> None:
        """
        Reset configuration state (mainly for testing)
        """
        cls._mode = None
        cls._cli_override = None


# Convenience functions
def get_run_mode() -> RunMode:
    """Get the current run mode"""
    return RunModeConfig.get_mode()


def is_standalone() -> bool:
    """Check if it is standalone mode"""
    return RunModeConfig.is_standalone()


def get_im_channel() -> Optional[str]:
    """Get the current IM channel name (returns None in standalone mode)"""
    return RunModeConfig.get_im_channel()


def set_cli_mode(mode: str) -> None:
    """Set the run mode passed from CLI"""
    RunModeConfig.set_cli_mode(mode)


__all__ = [
    "RunMode",
    "RunModeConfig",
    "get_run_mode",
    "is_standalone",
    "get_im_channel",
    "set_cli_mode",
]
