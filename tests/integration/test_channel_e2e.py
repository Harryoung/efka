"""
渠道系统端到端集成测试

测试场景:
1. Web UI → User API → Agent → 响应
2. 渠道配置 → 路由器初始化 → 适配器注册
3. 多渠道消息路由流程
"""

import pytest
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.channels.base import (
    BaseChannelAdapter,
    ChannelType,
    ChannelUser,
    ChannelMessage,
    ChannelResponse,
    MessageType,
)
from backend.config.channel_config import (
    ChannelConfig,
    ChannelMode,
    get_channel_config,
)
from backend.services.channel_router import (
    ChannelMessageRouter,
    get_channel_router,
    initialize_channel_router,
)


# ==================== 测试 Fixtures ====================

@pytest.fixture
def reset_singletons():
    """重置所有单例"""
    import backend.config.channel_config as config_module
    import backend.services.channel_router as router_module

    config_module._config_instance = None
    router_module._router_instance = None

    yield

    config_module._config_instance = None
    router_module._router_instance = None


@pytest.fixture
def mock_wework_env():
    """模拟 WeWork 环境变量"""
    env_vars = {
        "ENABLE_WEWORK": "auto",
        "WEWORK_CORP_ID": "test_corp_id",
        "WEWORK_CORP_SECRET": "test_corp_secret",
        "WEWORK_AGENT_ID": "1000001",
        "WEWORK_TOKEN": "test_token",
        "WEWORK_ENCODING_AES_KEY": "test_aes_key_1234567890123456789012345678901"
    }
    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


@pytest.fixture
def mock_all_channels_disabled():
    """禁用所有渠道"""
    env_vars = {
        "ENABLE_WEWORK": "disabled",
        "ENABLE_FEISHU": "disabled",
        "ENABLE_DINGTALK": "disabled",
        "ENABLE_SLACK": "disabled"
    }
    with patch.dict(os.environ, env_vars, clear=False):
        yield


# ==================== 配置系统集成测试 ====================

class TestConfigIntegration:
    """配置系统集成测试"""

    def test_config_singleton_consistency(self, reset_singletons):
        """测试配置单例一致性"""
        config1 = get_channel_config()
        config2 = get_channel_config()

        assert config1 is config2
        assert config1.get_channel_status() == config2.get_channel_status()

    def test_config_reflects_env_changes(self, reset_singletons):
        """测试配置反映环境变量变化"""
        # 禁用所有渠道
        with patch.dict(os.environ, {"ENABLE_WEWORK": "disabled"}):
            config = ChannelConfig()
            assert config.get_channel_mode("wework") == ChannelMode.DISABLED
            assert config.is_channel_enabled("wework") is False

    def test_config_validation_flow(self, reset_singletons, mock_all_channels_disabled):
        """测试配置验证流程"""
        config = ChannelConfig()

        # 所有渠道禁用时，验证应该通过
        errors = config.validate_enabled_channels()
        assert errors == []

        # 获取状态
        status = config.get_channel_status()
        for channel_status in status.values():
            assert channel_status["enabled"] is False


# ==================== 路由器集成测试 ====================

class TestRouterIntegration:
    """路由器集成测试"""

    @pytest.mark.asyncio
    async def test_router_initialization_flow(self, reset_singletons, mock_all_channels_disabled):
        """测试路由器初始化流程"""
        router = await initialize_channel_router()

        assert router._initialized is True
        # 所有渠道禁用时，不应有活跃渠道
        # 注意：实际行为取决于适配器实现

    @pytest.mark.asyncio
    async def test_router_adapter_registration(self, reset_singletons):
        """测试适配器注册流程"""
        router = ChannelMessageRouter()

        # 手动注册 Mock 适配器
        class TestAdapter(BaseChannelAdapter):
            def __init__(self):
                super().__init__(ChannelType.WEB)

            async def send_message(self, user_id, content, msg_type=MessageType.TEXT, **kwargs):
                return ChannelResponse(success=True)

            async def parse_message(self, request_data):
                user = ChannelUser(user_id="test", channel=ChannelType.WEB)
                return ChannelMessage(message_id="1", user=user, content="")

            async def verify_signature(self, request_data):
                return True

            def is_configured(self):
                return True

            async def get_user_info(self, user_id):
                return ChannelUser(user_id=user_id, channel=ChannelType.WEB)

        adapter = TestAdapter()
        await adapter.initialize()
        router.adapters["web"] = adapter
        router._initialized = True

        # 验证注册成功
        assert "web" in router.get_active_channels()
        assert router.get_adapter("web") is adapter


# ==================== 消息流程集成测试 ====================

class TestMessageFlowIntegration:
    """消息流程集成测试"""

    @pytest.fixture
    def router_with_mock_service(self, reset_singletons):
        """创建带有 Mock 服务的路由器"""
        router = ChannelMessageRouter()

        # Mock 适配器
        class TestAdapter(BaseChannelAdapter):
            def __init__(self):
                super().__init__(ChannelType.WEB)
                self.messages_sent = []

            async def send_message(self, user_id, content, msg_type=MessageType.TEXT, **kwargs):
                self.messages_sent.append({
                    "user_id": user_id,
                    "content": content,
                    "msg_type": msg_type
                })
                return ChannelResponse(success=True, data={"msg_id": "test_msg"})

            async def parse_message(self, request_data):
                user = ChannelUser(user_id=request_data.get("user_id", "test"), channel=ChannelType.WEB)
                return ChannelMessage(
                    message_id=request_data.get("msg_id", "1"),
                    user=user,
                    content=request_data.get("content", "")
                )

            async def verify_signature(self, request_data):
                return True

            def is_configured(self):
                return True

            async def get_user_info(self, user_id):
                return ChannelUser(user_id=user_id, channel=ChannelType.WEB)

        adapter = TestAdapter()
        router.adapters["web"] = adapter
        router._initialized = True

        return router, adapter

    @pytest.mark.asyncio
    async def test_full_message_flow(self, router_with_mock_service):
        """测试完整消息流程: 接收 → 路由 → 响应"""
        router, adapter = router_with_mock_service

        # 创建消息
        user = ChannelUser(user_id="test_user_001", channel=ChannelType.WEB)
        message = ChannelMessage(
            message_id="msg_001",
            user=user,
            content="请问知识库在哪里？",
            session_id="session_001"
        )

        # Mock User Service
        mock_service = AsyncMock()
        mock_service.is_initialized = True

        async def mock_query(*args, **kwargs):
            class MockMsg:
                text = "知识库位于 ./knowledge_base 目录下。"
            yield MockMsg()

        mock_service.query = mock_query

        # 执行路由
        response = await router.route_message(
            channel="web",
            message=message,
            user_service=mock_service
        )

        # 验证响应
        assert "知识库" in response
        assert len(adapter.messages_sent) == 1
        assert adapter.messages_sent[0]["user_id"] == "test_user_001"

    @pytest.mark.asyncio
    async def test_batch_message_flow(self, router_with_mock_service):
        """测试批量消息流程"""
        router, adapter = router_with_mock_service

        user_ids = ["user_001", "user_002", "user_003"]
        content = "系统通知: 知识库已更新"

        await router.send_batch_response(
            channel="web",
            user_ids=user_ids,
            content=content
        )

        assert len(adapter.messages_sent) == 3
        for i, msg in enumerate(adapter.messages_sent):
            assert msg["user_id"] == user_ids[i]
            assert msg["content"] == content


# ==================== 错误处理集成测试 ====================

class TestErrorHandlingIntegration:
    """错误处理集成测试"""

    @pytest.mark.asyncio
    async def test_agent_error_handling(self, reset_singletons):
        """测试 Agent 错误处理"""
        router = ChannelMessageRouter()

        # Mock 适配器
        class TestAdapter(BaseChannelAdapter):
            def __init__(self):
                super().__init__(ChannelType.WEB)
                self.messages_sent = []

            async def send_message(self, user_id, content, msg_type=MessageType.TEXT, **kwargs):
                self.messages_sent.append({"content": content})
                return ChannelResponse(success=True)

            async def parse_message(self, request_data):
                user = ChannelUser(user_id="test", channel=ChannelType.WEB)
                return ChannelMessage(message_id="1", user=user, content="")

            async def verify_signature(self, request_data):
                return True

            def is_configured(self):
                return True

            async def get_user_info(self, user_id):
                return ChannelUser(user_id=user_id, channel=ChannelType.WEB)

        adapter = TestAdapter()
        router.adapters["web"] = adapter
        router._initialized = True

        # Mock 失败的 User Service
        mock_service = AsyncMock()
        mock_service.is_initialized = True

        async def mock_query(*args, **kwargs):
            raise Exception("Agent 处理失败")
            yield  # 使其成为生成器

        mock_service.query = mock_query

        # 创建消息
        user = ChannelUser(user_id="test_user", channel=ChannelType.WEB)
        message = ChannelMessage(message_id="1", user=user, content="test")

        # 执行路由
        response = await router.route_message(
            channel="web",
            message=message,
            user_service=mock_service
        )

        # 验证错误响应
        assert "错误" in response or "error" in response.lower()
        assert len(adapter.messages_sent) == 1

    @pytest.mark.asyncio
    async def test_channel_not_found_error(self, reset_singletons):
        """测试渠道不存在错误"""
        router = ChannelMessageRouter()
        router._initialized = True

        user = ChannelUser(user_id="test", channel=ChannelType.WEB)
        message = ChannelMessage(message_id="1", user=user, content="test")

        with pytest.raises(ValueError, match="Channel not configured"):
            await router.route_message(channel="unknown", message=message)


# ==================== 多渠道场景测试 ====================

class TestMultiChannelScenarios:
    """多渠道场景测试"""

    @pytest.fixture
    def multi_channel_router(self, reset_singletons):
        """创建多渠道路由器"""
        router = ChannelMessageRouter()

        # 创建多个适配器
        for channel_type, name in [
            (ChannelType.WEB, "web"),
            (ChannelType.WEWORK, "wework")
        ]:
            class DynamicAdapter(BaseChannelAdapter):
                def __init__(self, ct, n):
                    super().__init__(ct)
                    self._name = n
                    self.messages = []

                async def send_message(self, user_id, content, msg_type=MessageType.TEXT, **kwargs):
                    self.messages.append({"channel": self._name, "user_id": user_id, "content": content})
                    return ChannelResponse(success=True)

                async def parse_message(self, request_data):
                    user = ChannelUser(user_id="test", channel=self.channel_type)
                    return ChannelMessage(message_id="1", user=user, content="")

                async def verify_signature(self, request_data):
                    return True

                def is_configured(self):
                    return True

                async def get_user_info(self, user_id):
                    return ChannelUser(user_id=user_id, channel=self.channel_type)

            adapter = DynamicAdapter(channel_type, name)
            router.adapters[name] = adapter

        router._initialized = True
        return router

    @pytest.mark.asyncio
    async def test_route_to_different_channels(self, multi_channel_router):
        """测试路由到不同渠道"""
        # 发送到 web 渠道
        await multi_channel_router.send_response(
            channel="web",
            user_id="web_user",
            content="Web 消息"
        )

        # 发送到 wework 渠道
        await multi_channel_router.send_response(
            channel="wework",
            user_id="wework_user",
            content="WeWork 消息"
        )

        # 验证
        web_adapter = multi_channel_router.get_adapter("web")
        wework_adapter = multi_channel_router.get_adapter("wework")

        assert len(web_adapter.messages) == 1
        assert web_adapter.messages[0]["channel"] == "web"
        assert web_adapter.messages[0]["content"] == "Web 消息"

        assert len(wework_adapter.messages) == 1
        assert wework_adapter.messages[0]["channel"] == "wework"
        assert wework_adapter.messages[0]["content"] == "WeWork 消息"

    def test_channel_isolation(self, multi_channel_router):
        """测试渠道隔离"""
        # 验证不同渠道的适配器是独立的
        web_adapter = multi_channel_router.get_adapter("web")
        wework_adapter = multi_channel_router.get_adapter("wework")

        assert web_adapter is not wework_adapter
        assert web_adapter.channel_type != wework_adapter.channel_type


# ==================== 性能和并发测试 ====================

class TestPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_concurrent_message_routing(self, reset_singletons):
        """测试并发消息路由"""
        import asyncio

        router = ChannelMessageRouter()

        # Mock 适配器
        class ConcurrentAdapter(BaseChannelAdapter):
            def __init__(self):
                super().__init__(ChannelType.WEB)
                self.message_count = 0

            async def send_message(self, user_id, content, msg_type=MessageType.TEXT, **kwargs):
                self.message_count += 1
                await asyncio.sleep(0.01)  # 模拟网络延迟
                return ChannelResponse(success=True)

            async def parse_message(self, request_data):
                user = ChannelUser(user_id="test", channel=ChannelType.WEB)
                return ChannelMessage(message_id="1", user=user, content="")

            async def verify_signature(self, request_data):
                return True

            def is_configured(self):
                return True

            async def get_user_info(self, user_id):
                return ChannelUser(user_id=user_id, channel=ChannelType.WEB)

        adapter = ConcurrentAdapter()
        router.adapters["web"] = adapter
        router._initialized = True

        # 并发发送消息
        tasks = []
        for i in range(10):
            task = router.send_response(
                channel="web",
                user_id=f"user_{i}",
                content=f"消息 {i}"
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        # 验证所有消息都已发送
        assert adapter.message_count == 10


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
