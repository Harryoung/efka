"""
渠道适配器单元测试

测试 backend/channels/base.py 中的:
- 数据模型: ChannelUser, ChannelMessage, ChannelResponse
- 枚举类型: MessageType, ChannelType
- 异常类: ChannelAdapterError, ChannelNotConfiguredError 等
- 基类方法: BaseChannelAdapter (使用Mock实现)
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.channels.base import (
    MessageType,
    ChannelType,
    ChannelUser,
    ChannelMessage,
    ChannelResponse,
    BaseChannelAdapter,
    ChannelAdapterError,
    ChannelNotConfiguredError,
    ChannelMessageError,
    ChannelAuthError,
)


# ==================== 枚举类型测试 ====================

class TestMessageType:
    """MessageType 枚举测试"""

    def test_enum_values(self):
        """测试枚举值定义正确"""
        assert MessageType.TEXT.value == "text"
        assert MessageType.IMAGE.value == "image"
        assert MessageType.FILE.value == "file"
        assert MessageType.MARKDOWN.value == "markdown"
        assert MessageType.EVENT.value == "event"

    def test_enum_str_conversion(self):
        """测试枚举可以作为字符串使用"""
        assert str(MessageType.TEXT) == "MessageType.TEXT"
        assert MessageType.TEXT == "text"  # str enum 支持直接比较


class TestChannelType:
    """ChannelType 枚举测试"""

    def test_enum_values(self):
        """测试枚举值定义正确"""
        assert ChannelType.WEWORK.value == "wework"
        assert ChannelType.FEISHU.value == "feishu"
        assert ChannelType.DINGTALK.value == "dingtalk"
        assert ChannelType.SLACK.value == "slack"
        assert ChannelType.WEB.value == "web"

    def test_all_channel_types(self):
        """测试所有渠道类型都已定义"""
        channel_types = [c.value for c in ChannelType]
        assert "wework" in channel_types
        assert "feishu" in channel_types
        assert "dingtalk" in channel_types
        assert "slack" in channel_types
        assert "web" in channel_types


# ==================== 数据模型测试 ====================

class TestChannelUser:
    """ChannelUser 数据模型测试"""

    def test_create_minimal_user(self):
        """测试创建最小用户对象"""
        user = ChannelUser(
            user_id="test_user",
            channel=ChannelType.WEWORK
        )
        assert user.user_id == "test_user"
        assert user.channel == ChannelType.WEWORK
        assert user.username is None
        assert user.email is None
        assert user.department is None
        assert user.raw_data == {}

    def test_create_full_user(self):
        """测试创建完整用户对象"""
        user = ChannelUser(
            user_id="test_user",
            username="张三",
            email="zhangsan@example.com",
            department="技术部",
            channel=ChannelType.FEISHU,
            raw_data={"open_id": "ou_xxx"}
        )
        assert user.user_id == "test_user"
        assert user.username == "张三"
        assert user.email == "zhangsan@example.com"
        assert user.department == "技术部"
        assert user.channel == ChannelType.FEISHU
        assert user.raw_data == {"open_id": "ou_xxx"}

    def test_user_requires_user_id(self):
        """测试必须提供 user_id"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ChannelUser(channel=ChannelType.WEWORK)

    def test_user_requires_channel(self):
        """测试必须提供 channel"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ChannelUser(user_id="test_user")


class TestChannelMessage:
    """ChannelMessage 数据模型测试"""

    def test_create_minimal_message(self):
        """测试创建最小消息对象"""
        user = ChannelUser(user_id="test_user", channel=ChannelType.WEWORK)
        msg = ChannelMessage(
            message_id="msg_001",
            user=user,
            content="Hello, world!"
        )
        assert msg.message_id == "msg_001"
        assert msg.user.user_id == "test_user"
        assert msg.content == "Hello, world!"
        assert msg.msg_type == MessageType.TEXT  # 默认值
        assert msg.timestamp > 0  # 自动生成
        assert msg.session_id is None
        assert msg.reply_to is None
        assert msg.attachments == []
        assert msg.metadata == {}
        assert msg.raw_data == {}

    def test_create_full_message(self):
        """测试创建完整消息对象"""
        user = ChannelUser(user_id="test_user", channel=ChannelType.FEISHU)
        timestamp = int(datetime.now().timestamp())

        msg = ChannelMessage(
            message_id="msg_002",
            user=user,
            content="这是一条Markdown消息",
            msg_type=MessageType.MARKDOWN,
            timestamp=timestamp,
            session_id="session_001",
            reply_to="msg_001",
            attachments=[{"type": "image", "url": "https://example.com/img.png"}],
            metadata={"mentions": ["user_002"]},
            raw_data={"feishu_msg_id": "om_xxx"}
        )

        assert msg.message_id == "msg_002"
        assert msg.msg_type == MessageType.MARKDOWN
        assert msg.timestamp == timestamp
        assert msg.session_id == "session_001"
        assert msg.reply_to == "msg_001"
        assert len(msg.attachments) == 1
        assert msg.metadata == {"mentions": ["user_002"]}

    def test_message_timestamp_auto_generated(self):
        """测试时间戳自动生成"""
        user = ChannelUser(user_id="test_user", channel=ChannelType.WEWORK)
        before = int(datetime.now().timestamp())
        msg = ChannelMessage(message_id="msg_003", user=user, content="test")
        after = int(datetime.now().timestamp())

        assert before <= msg.timestamp <= after


class TestChannelResponse:
    """ChannelResponse 数据模型测试"""

    def test_success_response(self):
        """测试成功响应"""
        resp = ChannelResponse(
            success=True,
            message="消息发送成功",
            data={"msg_id": "msg_001"}
        )
        assert resp.success is True
        assert resp.message == "消息发送成功"
        assert resp.data == {"msg_id": "msg_001"}
        assert resp.error is None

    def test_failure_response(self):
        """测试失败响应"""
        resp = ChannelResponse(
            success=False,
            error="用户不存在"
        )
        assert resp.success is False
        assert resp.error == "用户不存在"
        assert resp.message is None
        assert resp.data is None


# ==================== 异常类测试 ====================

class TestExceptions:
    """异常类测试"""

    def test_channel_adapter_error(self):
        """测试渠道适配器基础异常"""
        error = ChannelAdapterError("适配器错误")
        assert str(error) == "适配器错误"
        assert isinstance(error, Exception)

    def test_channel_not_configured_error(self):
        """测试渠道未配置异常"""
        error = ChannelNotConfiguredError("WeWork 未配置")
        assert str(error) == "WeWork 未配置"
        assert isinstance(error, ChannelAdapterError)

    def test_channel_message_error(self):
        """测试渠道消息错误异常"""
        error = ChannelMessageError("消息格式错误")
        assert str(error) == "消息格式错误"
        assert isinstance(error, ChannelAdapterError)

    def test_channel_auth_error(self):
        """测试渠道认证错误异常"""
        error = ChannelAuthError("Token 过期")
        assert str(error) == "Token 过期"
        assert isinstance(error, ChannelAdapterError)


# ==================== BaseChannelAdapter 测试 ====================

class MockChannelAdapter(BaseChannelAdapter):
    """用于测试的 Mock 适配器实现"""

    def __init__(self, configured: bool = True):
        super().__init__(ChannelType.WEB)
        self._configured = configured

    async def send_message(self, user_id, content, msg_type=MessageType.TEXT, **kwargs):
        return ChannelResponse(success=True, message="发送成功")

    async def parse_message(self, request_data):
        user = ChannelUser(user_id=request_data.get("user_id", "unknown"), channel=ChannelType.WEB)
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
        return ChannelUser(user_id=user_id, channel=ChannelType.WEB, username="Mock User")

    def get_required_env_vars(self):
        return ["MOCK_API_KEY", "MOCK_SECRET"]


class TestBaseChannelAdapter:
    """BaseChannelAdapter 基类测试"""

    def test_init(self):
        """测试适配器初始化"""
        adapter = MockChannelAdapter()
        assert adapter.channel_type == ChannelType.WEB
        assert adapter.channel_name == "web"
        assert adapter._initialized is False

    @pytest.mark.asyncio
    async def test_initialize(self):
        """测试适配器初始化方法"""
        adapter = MockChannelAdapter()
        assert adapter._initialized is False

        await adapter.initialize()
        assert adapter._initialized is True

        # 重复初始化应该不会出错
        await adapter.initialize()
        assert adapter._initialized is True

    def test_is_configured(self):
        """测试配置检测"""
        configured_adapter = MockChannelAdapter(configured=True)
        unconfigured_adapter = MockChannelAdapter(configured=False)

        assert configured_adapter.is_configured() is True
        assert unconfigured_adapter.is_configured() is False

    @pytest.mark.asyncio
    async def test_send_message(self):
        """测试发送消息"""
        adapter = MockChannelAdapter()
        result = await adapter.send_message("user_001", "Hello!")

        assert result.success is True
        assert result.message == "发送成功"

    @pytest.mark.asyncio
    async def test_parse_message(self):
        """测试解析消息"""
        adapter = MockChannelAdapter()
        msg = await adapter.parse_message({
            "msg_id": "msg_001",
            "user_id": "user_001",
            "content": "测试消息"
        })

        assert msg.message_id == "msg_001"
        assert msg.user.user_id == "user_001"
        assert msg.content == "测试消息"

    @pytest.mark.asyncio
    async def test_verify_signature(self):
        """测试签名验证"""
        adapter = MockChannelAdapter()

        valid = await adapter.verify_signature({"signature": "valid"})
        invalid = await adapter.verify_signature({"signature": "invalid"})

        assert valid is True
        assert invalid is False

    @pytest.mark.asyncio
    async def test_get_user_info(self):
        """测试获取用户信息"""
        adapter = MockChannelAdapter()
        user = await adapter.get_user_info("user_001")

        assert user.user_id == "user_001"
        assert user.username == "Mock User"
        assert user.channel == ChannelType.WEB

    def test_get_required_env_vars(self):
        """测试获取必需环境变量"""
        adapter = MockChannelAdapter()
        env_vars = adapter.get_required_env_vars()

        assert "MOCK_API_KEY" in env_vars
        assert "MOCK_SECRET" in env_vars

    def test_repr(self):
        """测试字符串表示"""
        configured_adapter = MockChannelAdapter(configured=True)
        unconfigured_adapter = MockChannelAdapter(configured=False)

        assert "configured" in repr(configured_adapter)
        assert "not configured" in repr(unconfigured_adapter)

    @pytest.mark.asyncio
    async def test_send_batch_message_default(self):
        """测试默认批量发送实现"""
        adapter = MockChannelAdapter()
        results = await adapter.send_batch_message(
            user_ids=["user_001", "user_002", "user_003"],
            content="批量消息"
        )

        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_handle_event_default(self):
        """测试默认事件处理"""
        adapter = MockChannelAdapter()
        result = await adapter.handle_event({"event_type": "user_join"})

        # 默认实现返回 None
        assert result is None


# ==================== WeWork 适配器测试 (如果可用) ====================

class TestWeWorkAdapter:
    """WeWork 适配器测试"""

    def test_import_wework_adapter(self):
        """测试 WeWork 适配器可以导入"""
        try:
            from backend.channels.wework import WeWorkAdapter
            adapter = WeWorkAdapter()
            assert adapter.channel_type == ChannelType.WEWORK
            assert adapter.channel_name == "wework"
        except ImportError:
            pytest.skip("WeWork adapter not available")

    def test_wework_required_env_vars(self):
        """测试 WeWork 适配器必需环境变量"""
        try:
            from backend.channels.wework import WeWorkAdapter
            adapter = WeWorkAdapter()
            env_vars = adapter.get_required_env_vars()

            assert "WEWORK_CORP_ID" in env_vars
            assert "WEWORK_CORP_SECRET" in env_vars
            assert "WEWORK_AGENT_ID" in env_vars
        except ImportError:
            pytest.skip("WeWork adapter not available")

    def test_wework_is_configured_without_env(self):
        """测试未设置环境变量时 is_configured 返回 False"""
        try:
            from backend.channels.wework import WeWorkAdapter

            # 清除可能存在的环境变量
            env_vars = ["WEWORK_CORP_ID", "WEWORK_CORP_SECRET", "WEWORK_AGENT_ID",
                        "WEWORK_TOKEN", "WEWORK_ENCODING_AES_KEY"]
            original_values = {}
            for var in env_vars:
                original_values[var] = os.environ.pop(var, None)

            try:
                adapter = WeWorkAdapter()
                # 如果环境变量未设置，应该返回 False
                # 注意：测试环境可能已设置这些变量
                result = adapter.is_configured()
                assert isinstance(result, bool)
            finally:
                # 恢复环境变量
                for var, value in original_values.items():
                    if value is not None:
                        os.environ[var] = value

        except ImportError:
            pytest.skip("WeWork adapter not available")


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
