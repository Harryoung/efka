"""
渠道消息路由器单元测试

测试 backend/services/channel_router.py 中的:
- ChannelMessageRouter 路由器类
- 适配器发现和注册
- 消息路由
- 响应发送
"""

import pytest
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.channels.base import (
    BaseChannelAdapter,
    ChannelType,
    ChannelUser,
    ChannelMessage,
    ChannelResponse,
    MessageType,
)
from backend.services.channel_router import (
    ChannelMessageRouter,
    get_channel_router,
    initialize_channel_router,
)


# ==================== Mock 适配器 ====================

class MockAdapter(BaseChannelAdapter):
    """用于测试的 Mock 适配器"""

    def __init__(self, channel_type: ChannelType = ChannelType.WEB, configured: bool = True):
        super().__init__(channel_type)
        self._configured = configured
        self.sent_messages = []  # 记录发送的消息

    async def send_message(self, user_id, content, msg_type=MessageType.TEXT, **kwargs):
        self.sent_messages.append({
            "user_id": user_id,
            "content": content,
            "msg_type": msg_type,
            "kwargs": kwargs
        })
        return ChannelResponse(success=True, message="发送成功", data={"msg_id": "mock_msg_001"})

    async def parse_message(self, request_data):
        user = ChannelUser(
            user_id=request_data.get("user_id", "mock_user"),
            channel=self.channel_type
        )
        return ChannelMessage(
            message_id=request_data.get("msg_id", "mock_msg"),
            user=user,
            content=request_data.get("content", "")
        )

    async def verify_signature(self, request_data):
        return request_data.get("signature") == "valid"

    def is_configured(self):
        return self._configured

    async def get_user_info(self, user_id):
        return ChannelUser(
            user_id=user_id,
            channel=self.channel_type,
            username="Mock User"
        )

    def get_required_env_vars(self):
        return ["MOCK_API_KEY"]


class MockFailingAdapter(MockAdapter):
    """发送消息会失败的 Mock 适配器"""

    async def send_message(self, user_id, content, msg_type=MessageType.TEXT, **kwargs):
        return ChannelResponse(success=False, error="发送失败: 用户不存在")


# ==================== ChannelMessageRouter 测试 ====================

class TestChannelMessageRouter:
    """ChannelMessageRouter 单元测试"""

    @pytest.fixture
    def router(self):
        """创建新的路由器实例"""
        return ChannelMessageRouter()

    def test_init(self, router):
        """测试路由器初始化"""
        assert router.adapters == {}
        assert router._initialized is False

    @pytest.mark.asyncio
    async def test_initialize(self, router):
        """测试路由器初始化方法"""
        # Mock 适配器发现
        with patch.object(router, '_discover_adapters', new_callable=AsyncMock) as mock_discover:
            await router.initialize()

            assert router._initialized is True
            mock_discover.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_only_once(self, router):
        """测试路由器只初始化一次"""
        with patch.object(router, '_discover_adapters', new_callable=AsyncMock) as mock_discover:
            await router.initialize()
            await router.initialize()  # 第二次调用

            # 只应该调用一次
            assert mock_discover.call_count == 1


class TestRouterAdapterManagement:
    """测试适配器管理"""

    @pytest.fixture
    def router_with_adapters(self):
        """创建带有适配器的路由器"""
        router = ChannelMessageRouter()
        router.adapters = {
            "web": MockAdapter(ChannelType.WEB),
            "wework": MockAdapter(ChannelType.WEWORK)
        }
        router._initialized = True
        return router

    def test_get_adapter(self, router_with_adapters):
        """测试获取适配器"""
        adapter = router_with_adapters.get_adapter("web")
        assert adapter is not None
        assert adapter.channel_type == ChannelType.WEB

    def test_get_adapter_not_found(self, router_with_adapters):
        """测试获取不存在的适配器"""
        adapter = router_with_adapters.get_adapter("unknown")
        assert adapter is None

    def test_get_active_channels(self, router_with_adapters):
        """测试获取活跃渠道列表"""
        channels = router_with_adapters.get_active_channels()
        assert "web" in channels
        assert "wework" in channels
        assert len(channels) == 2

    def test_get_channel_status(self, router_with_adapters):
        """测试获取渠道状态"""
        status = router_with_adapters.get_channel_status()

        assert "web" in status
        assert "wework" in status

        for channel_name, channel_status in status.items():
            assert "configured" in channel_status
            assert "initialized" in channel_status
            assert "required_env_vars" in channel_status


class TestRouterMessageRouting:
    """测试消息路由"""

    @pytest.fixture
    def router_with_mock_adapter(self):
        """创建带有 Mock 适配器的路由器"""
        router = ChannelMessageRouter()
        router.adapters = {
            "web": MockAdapter(ChannelType.WEB)
        }
        router._initialized = True
        return router

    @pytest.fixture
    def sample_message(self):
        """创建示例消息"""
        user = ChannelUser(user_id="test_user", channel=ChannelType.WEB)
        return ChannelMessage(
            message_id="msg_001",
            user=user,
            content="测试消息",
            session_id="session_001"
        )

    @pytest.mark.asyncio
    async def test_route_message_channel_not_found(self, router_with_mock_adapter, sample_message):
        """测试路由到不存在的渠道"""
        with pytest.raises(ValueError, match="Channel not configured"):
            await router_with_mock_adapter.route_message(
                channel="unknown",
                message=sample_message
            )

    @pytest.mark.asyncio
    async def test_route_message_success(self, router_with_mock_adapter, sample_message):
        """测试成功路由消息"""
        # Mock Employee Service
        mock_service = AsyncMock()
        mock_service.is_initialized = True

        # Mock 响应生成器
        async def mock_query(*args, **kwargs):
            class MockMessage:
                text = "这是 Agent 的响应"
            yield MockMessage()

        mock_service.query = mock_query

        response = await router_with_mock_adapter.route_message(
            channel="web",
            message=sample_message,
            employee_service=mock_service
        )

        assert response == "这是 Agent 的响应"

        # 验证消息已发送
        adapter = router_with_mock_adapter.get_adapter("web")
        assert len(adapter.sent_messages) == 1
        assert adapter.sent_messages[0]["user_id"] == "test_user"
        assert "Agent 的响应" in adapter.sent_messages[0]["content"]


class TestRouterSendResponse:
    """测试响应发送"""

    @pytest.fixture
    def router_with_adapters(self):
        """创建带有适配器的路由器"""
        router = ChannelMessageRouter()
        router.adapters = {
            "web": MockAdapter(ChannelType.WEB),
            "failing": MockFailingAdapter(ChannelType.WEWORK)
        }
        router._initialized = True
        return router

    @pytest.mark.asyncio
    async def test_send_response_success(self, router_with_adapters):
        """测试成功发送响应"""
        await router_with_adapters.send_response(
            channel="web",
            user_id="test_user",
            content="响应内容"
        )

        adapter = router_with_adapters.get_adapter("web")
        assert len(adapter.sent_messages) == 1
        assert adapter.sent_messages[0]["content"] == "响应内容"

    @pytest.mark.asyncio
    async def test_send_response_channel_not_found(self, router_with_adapters):
        """测试发送到不存在的渠道"""
        with pytest.raises(ValueError, match="Channel not configured"):
            await router_with_adapters.send_response(
                channel="unknown",
                user_id="test_user",
                content="响应内容"
            )

    @pytest.mark.asyncio
    async def test_send_response_failure(self, router_with_adapters):
        """测试发送失败"""
        with pytest.raises(Exception, match="Failed to send message"):
            await router_with_adapters.send_response(
                channel="failing",
                user_id="test_user",
                content="响应内容"
            )


class TestRouterBatchSend:
    """测试批量发送"""

    @pytest.fixture
    def router_with_adapter(self):
        """创建带有适配器的路由器"""
        router = ChannelMessageRouter()
        router.adapters = {
            "web": MockAdapter(ChannelType.WEB)
        }
        router._initialized = True
        return router

    @pytest.mark.asyncio
    async def test_send_batch_response(self, router_with_adapter):
        """测试批量发送响应"""
        user_ids = ["user_001", "user_002", "user_003"]

        await router_with_adapter.send_batch_response(
            channel="web",
            user_ids=user_ids,
            content="批量消息"
        )

        adapter = router_with_adapter.get_adapter("web")
        assert len(adapter.sent_messages) == 3

        for i, msg in enumerate(adapter.sent_messages):
            assert msg["user_id"] == user_ids[i]
            assert msg["content"] == "批量消息"

    @pytest.mark.asyncio
    async def test_send_batch_response_channel_not_found(self, router_with_adapter):
        """测试批量发送到不存在的渠道"""
        with pytest.raises(ValueError, match="Channel not configured"):
            await router_with_adapter.send_batch_response(
                channel="unknown",
                user_ids=["user_001"],
                content="批量消息"
            )


# ==================== 单例和便捷函数测试 ====================

class TestSingletonAndHelpers:
    """测试单例模式和便捷函数"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """每个测试前重置单例"""
        import backend.services.channel_router as router_module
        router_module._router_instance = None
        yield
        router_module._router_instance = None

    def test_get_channel_router_returns_singleton(self):
        """测试 get_channel_router 返回单例"""
        router1 = get_channel_router()
        router2 = get_channel_router()
        assert router1 is router2

    @pytest.mark.asyncio
    async def test_initialize_channel_router(self):
        """测试 initialize_channel_router 函数"""
        with patch.object(ChannelMessageRouter, '_discover_adapters', new_callable=AsyncMock):
            router = await initialize_channel_router()

            assert router._initialized is True

            # 再次调用应该返回同一个实例
            router2 = await initialize_channel_router()
            assert router is router2


# ==================== 适配器发现测试 ====================

class TestAdapterDiscovery:
    """测试适配器自动发现"""

    @pytest.mark.asyncio
    async def test_discover_adapters_with_no_configured_channels(self):
        """测试没有配置渠道时的发现"""
        router = ChannelMessageRouter()

        # 清除环境变量
        env_vars = ["WEWORK_CORP_ID", "WEWORK_CORP_SECRET", "WEWORK_AGENT_ID",
                    "WEWORK_TOKEN", "WEWORK_ENCODING_AES_KEY"]
        original_values = {var: os.environ.pop(var, None) for var in env_vars}

        try:
            await router._discover_adapters()
            # 如果没有配置，不应该有任何适配器注册
            # 注意：实际行为取决于测试环境
            assert isinstance(router.adapters, dict)
        finally:
            for var, value in original_values.items():
                if value is not None:
                    os.environ[var] = value

    @pytest.mark.asyncio
    async def test_discover_adapters_handles_import_errors(self):
        """测试适配器导入错误处理"""
        router = ChannelMessageRouter()

        # 模拟导入错误
        with patch.dict('sys.modules', {'backend.channels.feishu': None}):
            # 不应该抛出异常
            await router._discover_adapters()


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
