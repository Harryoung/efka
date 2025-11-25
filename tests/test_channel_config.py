"""
渠道配置系统单元测试

测试 backend/config/channel_config.py 中的:
- ChannelMode 枚举
- ChannelConfig 配置管理器
- 混合配置模式 (auto/enabled/disabled)
- 便捷函数
"""

import pytest
import os
import sys
from unittest.mock import patch

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config.channel_config import (
    ChannelMode,
    ChannelConfig,
    get_channel_config,
    is_channel_enabled,
    get_enabled_channels,
    validate_channel_config,
)


# ==================== ChannelMode 枚举测试 ====================

class TestChannelMode:
    """ChannelMode 枚举测试"""

    def test_enum_values(self):
        """测试枚举值定义正确"""
        assert ChannelMode.AUTO.value == "auto"
        assert ChannelMode.ENABLED.value == "enabled"
        assert ChannelMode.DISABLED.value == "disabled"

    def test_enum_str_conversion(self):
        """测试枚举字符串转换"""
        assert ChannelMode("auto") == ChannelMode.AUTO
        assert ChannelMode("enabled") == ChannelMode.ENABLED
        assert ChannelMode("disabled") == ChannelMode.DISABLED


# ==================== ChannelConfig 测试 ====================

class TestChannelConfig:
    """ChannelConfig 配置管理器测试"""

    def test_channel_env_vars_defined(self):
        """测试所有渠道的必需环境变量都已定义"""
        assert "wework" in ChannelConfig.CHANNEL_ENV_VARS
        assert "feishu" in ChannelConfig.CHANNEL_ENV_VARS
        assert "dingtalk" in ChannelConfig.CHANNEL_ENV_VARS
        assert "slack" in ChannelConfig.CHANNEL_ENV_VARS

    def test_channel_ports_defined(self):
        """测试所有渠道的默认端口都已定义"""
        assert ChannelConfig.CHANNEL_PORTS["wework"] == 8081
        assert ChannelConfig.CHANNEL_PORTS["feishu"] == 8082
        assert ChannelConfig.CHANNEL_PORTS["dingtalk"] == 8083
        assert ChannelConfig.CHANNEL_PORTS["slack"] == 8084

    def test_wework_required_env_vars(self):
        """测试 WeWork 必需环境变量列表正确"""
        wework_vars = ChannelConfig.CHANNEL_ENV_VARS["wework"]
        assert "WEWORK_CORP_ID" in wework_vars
        assert "WEWORK_CORP_SECRET" in wework_vars
        assert "WEWORK_AGENT_ID" in wework_vars
        assert "WEWORK_TOKEN" in wework_vars
        assert "WEWORK_ENCODING_AES_KEY" in wework_vars

    def test_feishu_required_env_vars(self):
        """测试飞书必需环境变量列表正确"""
        feishu_vars = ChannelConfig.CHANNEL_ENV_VARS["feishu"]
        assert "FEISHU_APP_ID" in feishu_vars
        assert "FEISHU_APP_SECRET" in feishu_vars


class TestChannelConfigModes:
    """测试渠道配置模式"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """每个测试前重置单例"""
        import backend.config.channel_config as config_module
        config_module._config_instance = None
        yield
        config_module._config_instance = None

    def test_default_mode_is_auto(self):
        """测试默认模式是 auto"""
        # 清除环境变量
        env_vars_to_clear = ["ENABLE_WEWORK", "ENABLE_FEISHU", "ENABLE_DINGTALK", "ENABLE_SLACK"]
        original_values = {var: os.environ.pop(var, None) for var in env_vars_to_clear}

        try:
            config = ChannelConfig()
            assert config.get_channel_mode("wework") == ChannelMode.AUTO
            assert config.get_channel_mode("feishu") == ChannelMode.AUTO
            assert config.get_channel_mode("dingtalk") == ChannelMode.AUTO
            assert config.get_channel_mode("slack") == ChannelMode.AUTO
        finally:
            # 恢复环境变量
            for var, value in original_values.items():
                if value is not None:
                    os.environ[var] = value

    def test_enabled_mode(self):
        """测试强制启用模式"""
        with patch.dict(os.environ, {"ENABLE_WEWORK": "enabled"}):
            config = ChannelConfig()
            assert config.get_channel_mode("wework") == ChannelMode.ENABLED

    def test_disabled_mode(self):
        """测试强制禁用模式"""
        with patch.dict(os.environ, {"ENABLE_WEWORK": "disabled"}):
            config = ChannelConfig()
            assert config.get_channel_mode("wework") == ChannelMode.DISABLED

    def test_invalid_mode_defaults_to_auto(self):
        """测试无效模式默认为 auto"""
        with patch.dict(os.environ, {"ENABLE_WEWORK": "invalid_value"}):
            config = ChannelConfig()
            assert config.get_channel_mode("wework") == ChannelMode.AUTO


class TestChannelConfigEnabled:
    """测试渠道启用检测"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """每个测试前重置单例"""
        import backend.config.channel_config as config_module
        config_module._config_instance = None
        yield
        config_module._config_instance = None

    def test_disabled_channel_returns_false(self):
        """测试禁用的渠道返回 False"""
        with patch.dict(os.environ, {"ENABLE_WEWORK": "disabled"}, clear=False):
            config = ChannelConfig()
            assert config.is_channel_enabled("wework") is False

    def test_enabled_channel_returns_true(self):
        """测试强制启用的渠道返回 True"""
        with patch.dict(os.environ, {"ENABLE_FEISHU": "enabled"}, clear=False):
            config = ChannelConfig()
            assert config.is_channel_enabled("feishu") is True

    def test_auto_mode_checks_env_vars(self):
        """测试 auto 模式会检查环境变量"""
        # 清除所有相关环境变量
        env_to_clear = ["ENABLE_WEWORK", "WEWORK_CORP_ID", "WEWORK_CORP_SECRET",
                        "WEWORK_AGENT_ID", "WEWORK_TOKEN", "WEWORK_ENCODING_AES_KEY"]
        original_values = {var: os.environ.pop(var, None) for var in env_to_clear}

        try:
            config = ChannelConfig()
            # 没有环境变量，应该返回 False
            assert config.is_channel_enabled("wework") is False
        finally:
            for var, value in original_values.items():
                if value is not None:
                    os.environ[var] = value

    def test_auto_mode_enabled_when_configured(self):
        """测试 auto 模式在配置完整时启用"""
        wework_env = {
            "ENABLE_WEWORK": "auto",
            "WEWORK_CORP_ID": "test_corp",
            "WEWORK_CORP_SECRET": "test_secret",
            "WEWORK_AGENT_ID": "1000001",
            "WEWORK_TOKEN": "test_token",
            "WEWORK_ENCODING_AES_KEY": "test_aes_key"
        }

        with patch.dict(os.environ, wework_env, clear=False):
            config = ChannelConfig()
            assert config.is_channel_enabled("wework") is True


class TestChannelConfigPorts:
    """测试渠道端口配置"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """每个测试前重置单例"""
        import backend.config.channel_config as config_module
        config_module._config_instance = None
        yield
        config_module._config_instance = None

    def test_default_ports(self):
        """测试默认端口"""
        # 清除可能存在的端口环境变量
        port_vars = ["WEWORK_PORT", "FEISHU_PORT", "DINGTALK_PORT", "SLACK_PORT"]
        original_values = {var: os.environ.pop(var, None) for var in port_vars}

        try:
            config = ChannelConfig()
            assert config.get_channel_port("wework") == 8081
            assert config.get_channel_port("feishu") == 8082
            assert config.get_channel_port("dingtalk") == 8083
            assert config.get_channel_port("slack") == 8084
        finally:
            # 恢复环境变量
            for var, value in original_values.items():
                if value is not None:
                    os.environ[var] = value

    def test_custom_port_from_env(self):
        """测试从环境变量读取自定义端口"""
        with patch.dict(os.environ, {"WEWORK_PORT": "9081"}):
            config = ChannelConfig()
            assert config.get_channel_port("wework") == 9081

    def test_invalid_port_falls_back_to_default(self):
        """测试无效端口回退到默认值"""
        with patch.dict(os.environ, {"WEWORK_PORT": "not_a_number"}):
            config = ChannelConfig()
            assert config.get_channel_port("wework") == 8081


class TestChannelConfigStatus:
    """测试渠道状态查询"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """每个测试前重置单例"""
        import backend.config.channel_config as config_module
        config_module._config_instance = None
        yield
        config_module._config_instance = None

    def test_get_channel_status(self):
        """测试获取渠道状态"""
        config = ChannelConfig()
        status = config.get_channel_status()

        # 验证所有渠道都有状态
        assert "wework" in status
        assert "feishu" in status
        assert "dingtalk" in status
        assert "slack" in status

        # 验证状态结构
        for channel_status in status.values():
            assert "mode" in channel_status
            assert "enabled" in channel_status
            assert "configured" in channel_status
            assert "port" in channel_status
            assert "required_env_vars" in channel_status

    def test_get_enabled_channels(self):
        """测试获取已启用渠道列表"""
        # 清除环境变量并禁用所有渠道
        with patch.dict(os.environ, {
            "ENABLE_WEWORK": "disabled",
            "ENABLE_FEISHU": "disabled",
            "ENABLE_DINGTALK": "disabled",
            "ENABLE_SLACK": "disabled"
        }):
            config = ChannelConfig()
            enabled = config.get_enabled_channels()
            assert enabled == []


class TestChannelConfigValidation:
    """测试配置验证"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """每个测试前重置单例"""
        import backend.config.channel_config as config_module
        config_module._config_instance = None
        yield
        config_module._config_instance = None

    def test_validate_returns_errors_for_enabled_but_unconfigured(self):
        """测试强制启用但未配置的渠道返回错误"""
        # 清除 WeWork 环境变量
        env_to_clear = ["WEWORK_CORP_ID", "WEWORK_CORP_SECRET", "WEWORK_AGENT_ID",
                        "WEWORK_TOKEN", "WEWORK_ENCODING_AES_KEY"]
        original_values = {var: os.environ.pop(var, None) for var in env_to_clear}

        try:
            with patch.dict(os.environ, {"ENABLE_WEWORK": "enabled"}):
                config = ChannelConfig()
                errors = config.validate_enabled_channels()

                # 应该有错误
                assert len(errors) > 0
                assert any("wework" in e.lower() for e in errors)
        finally:
            for var, value in original_values.items():
                if value is not None:
                    os.environ[var] = value

    def test_validate_returns_empty_for_properly_configured(self):
        """测试正确配置的渠道返回空错误列表"""
        # 禁用所有渠道
        with patch.dict(os.environ, {
            "ENABLE_WEWORK": "disabled",
            "ENABLE_FEISHU": "disabled",
            "ENABLE_DINGTALK": "disabled",
            "ENABLE_SLACK": "disabled"
        }):
            config = ChannelConfig()
            errors = config.validate_enabled_channels()
            assert errors == []


class TestChannelConfigRequiredEnvVars:
    """测试获取必需环境变量"""

    def test_get_required_env_vars_for_wework(self):
        """测试获取 WeWork 必需环境变量"""
        config = ChannelConfig()
        vars = config.get_required_env_vars("wework")

        assert "WEWORK_CORP_ID" in vars
        assert "WEWORK_CORP_SECRET" in vars

    def test_get_required_env_vars_for_unknown_channel(self):
        """测试获取未知渠道的环境变量返回空列表"""
        config = ChannelConfig()
        vars = config.get_required_env_vars("unknown_channel")
        assert vars == []


# ==================== 便捷函数测试 ====================

class TestConvenienceFunctions:
    """测试便捷函数"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """每个测试前重置单例"""
        import backend.config.channel_config as config_module
        config_module._config_instance = None
        yield
        config_module._config_instance = None

    def test_get_channel_config_returns_singleton(self):
        """测试 get_channel_config 返回单例"""
        config1 = get_channel_config()
        config2 = get_channel_config()
        assert config1 is config2

    def test_is_channel_enabled_function(self):
        """测试 is_channel_enabled 便捷函数"""
        with patch.dict(os.environ, {"ENABLE_WEWORK": "disabled"}):
            # 重置单例
            import backend.config.channel_config as config_module
            config_module._config_instance = None

            result = is_channel_enabled("wework")
            assert result is False

    def test_get_enabled_channels_function(self):
        """测试 get_enabled_channels 便捷函数"""
        with patch.dict(os.environ, {
            "ENABLE_WEWORK": "disabled",
            "ENABLE_FEISHU": "disabled",
            "ENABLE_DINGTALK": "disabled",
            "ENABLE_SLACK": "disabled"
        }):
            # 重置单例
            import backend.config.channel_config as config_module
            config_module._config_instance = None

            result = get_enabled_channels()
            assert result == []

    def test_validate_channel_config_function(self):
        """测试 validate_channel_config 便捷函数"""
        with patch.dict(os.environ, {
            "ENABLE_WEWORK": "disabled",
            "ENABLE_FEISHU": "disabled",
            "ENABLE_DINGTALK": "disabled",
            "ENABLE_SLACK": "disabled"
        }):
            # 重置单例
            import backend.config.channel_config as config_module
            config_module._config_instance = None

            result = validate_channel_config()
            assert result == []


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
