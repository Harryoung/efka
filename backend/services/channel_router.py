"""
渠道消息路由器

统一管理所有IM渠道适配器,负责:
1. 自动发现并注册已配置的渠道
2. 路由IM消息到Employee Agent
3. 将Agent响应发送回用户(通过适配器)
4. 提供渠道状态查询
"""

import logging
from typing import Dict, List, Optional
from pathlib import Path

from backend.channels.base import (
    BaseChannelAdapter,
    ChannelMessage,
    ChannelType,
    MessageType,
    ChannelNotConfiguredError
)

logger = logging.getLogger(__name__)


class ChannelMessageRouter:
    """渠道消息路由器"""

    def __init__(self):
        """初始化路由器"""
        self.adapters: Dict[str, BaseChannelAdapter] = {}
        self._initialized = False

    async def initialize(self):
        """初始化路由器:发现并注册已配置的渠道"""
        if self._initialized:
            logger.warning("ChannelMessageRouter already initialized")
            return

        logger.info("Initializing ChannelMessageRouter...")

        # 自动发现并注册适配器
        await self._discover_adapters()

        self._initialized = True
        logger.info(f"✅ ChannelMessageRouter initialized with {len(self.adapters)} channels: {list(self.adapters.keys())}")

    async def _discover_adapters(self):
        """自动发现并注册已配置的适配器"""

        # 尝试导入并注册各个渠道适配器
        adapter_classes = []

        # WeWork
        try:
            from backend.channels.wework import WeWorkAdapter
            adapter_classes.append(WeWorkAdapter)
        except ImportError as e:
            logger.warning(f"WeWork adapter not available: {e}")

        # Feishu(未来实现)
        try:
            from backend.channels.feishu import FeishuAdapter
            adapter_classes.append(FeishuAdapter)
        except ImportError:
            pass  # Feishu尚未实现

        # DingTalk(未来实现)
        try:
            from backend.channels.dingtalk import DingTalkAdapter
            adapter_classes.append(DingTalkAdapter)
        except ImportError:
            pass

        # Slack(未来实现)
        try:
            from backend.channels.slack import SlackAdapter
            adapter_classes.append(SlackAdapter)
        except ImportError:
            pass

        # 注册已配置的适配器
        for AdapterClass in adapter_classes:
            try:
                adapter = AdapterClass()

                # 检查是否已配置
                if adapter.is_configured():
                    await adapter.initialize()
                    self.adapters[adapter.channel_name] = adapter
                    logger.info(f"✅ Registered channel: {adapter.channel_name}")
                else:
                    logger.info(f"⏭️  Skipped channel: {adapter.channel_name} (not configured)")
                    logger.debug(f"   Required env vars: {adapter.get_required_env_vars()}")

            except Exception as e:
                logger.error(f"Failed to initialize adapter {AdapterClass.__name__}: {e}", exc_info=True)

    def get_adapter(self, channel: str) -> Optional[BaseChannelAdapter]:
        """
        获取指定渠道的适配器

        Args:
            channel: 渠道名称(wework/feishu/dingtalk/slack)

        Returns:
            BaseChannelAdapter或None
        """
        return self.adapters.get(channel)

    def get_active_channels(self) -> List[str]:
        """
        获取已激活的渠道列表

        Returns:
            List[str]: 渠道名称列表
        """
        return list(self.adapters.keys())

    async def route_message(
        self,
        channel: str,
        message: ChannelMessage,
        employee_service = None
    ) -> str:
        """
        路由IM消息到Employee Agent并返回响应

        流程:
        1. 验证渠道是否存在
        2. 调用Employee Service处理消息
        3. 收集Agent响应
        4. 通过适配器发送回用户

        Args:
            channel: 渠道名称
            message: ChannelMessage对象
            employee_service: Employee Service实例(可选,用于依赖注入)

        Returns:
            str: Agent响应文本

        Raises:
            ValueError: 渠道未配置或消息路由失败
        """
        # 验证渠道
        adapter = self.get_adapter(channel)
        if not adapter:
            raise ValueError(f"Channel not configured: {channel}")

        logger.info(f"Routing message from {channel}:{message.user.user_id} → Employee Agent")

        # 获取Employee Service
        if employee_service is None:
            from backend.services.kb_service_factory import get_employee_service
            employee_service = get_employee_service()

        # 确保service已初始化
        if not employee_service.is_initialized:
            await employee_service.initialize()
            logger.info("Employee service initialized")

        # 构造消息(包含用户信息)
        formatted_message = f"""[用户信息]
user_id: {message.user.user_id}
channel: {channel}

[用户消息]
{message.content}"""

        # 调用Employee Agent
        agent_response_text = ""
        message_count = 0

        try:
            logger.info(f"Calling Employee Agent with session {message.session_id or 'new'}")

            async for msg in employee_service.query(
                user_message=formatted_message,
                session_id=message.session_id,
                user_id=message.user.user_id
            ):
                message_count += 1
                agent_response_text += msg.text
                logger.debug(f"Received message {message_count} from Employee Agent (len={len(msg.text)})")

            logger.info(f"✅ Received {message_count} messages from Employee Agent (total length={len(agent_response_text)})")

            if message_count == 0:
                logger.error(f"No response from Employee Agent for {message.user.user_id}")
                agent_response_text = "抱歉,服务暂时不可用,请稍后重试。"

        except Exception as e:
            logger.error(f"Employee Agent call failed: {type(e).__name__}: {str(e)}", exc_info=True)
            agent_response_text = f"抱歉,处理消息时出现错误: {str(e)}"

        # 发送响应(通过适配器)
        await self.send_response(
            channel=channel,
            user_id=message.user.user_id,
            content=agent_response_text
        )

        return agent_response_text

    async def send_response(
        self,
        channel: str,
        user_id: str,
        content: str,
        msg_type: MessageType = MessageType.TEXT,
        **kwargs
    ):
        """
        通过指定渠道发送响应消息

        Args:
            channel: 渠道名称
            user_id: 目标用户ID
            content: 消息内容
            msg_type: 消息类型
            **kwargs: 平台特定参数
        """
        adapter = self.get_adapter(channel)
        if not adapter:
            raise ValueError(f"Channel not configured: {channel}")

        result = await adapter.send_message(user_id, content, msg_type, **kwargs)

        if not result.success:
            logger.error(f"Failed to send message via {channel}: {result.error}")
            raise Exception(f"Failed to send message: {result.error}")

        logger.info(f"✅ Message sent to {channel}:{user_id}")

    async def send_batch_response(
        self,
        channel: str,
        user_ids: List[str],
        content: str,
        msg_type: MessageType = MessageType.TEXT,
        **kwargs
    ):
        """
        批量发送消息

        Args:
            channel: 渠道名称
            user_ids: 目标用户ID列表
            content: 消息内容
            msg_type: 消息类型
            **kwargs: 平台特定参数
        """
        adapter = self.get_adapter(channel)
        if not adapter:
            raise ValueError(f"Channel not configured: {channel}")

        results = await adapter.send_batch_message(user_ids, content, msg_type, **kwargs)

        success_count = sum(1 for r in results if r.success)
        logger.info(f"✅ Batch send completed: {success_count}/{len(user_ids)} successful")

        if success_count < len(user_ids):
            failed_count = len(user_ids) - success_count
            logger.warning(f"⚠️  {failed_count} messages failed to send")

    def get_channel_status(self) -> Dict[str, Dict]:
        """
        获取所有渠道的状态

        Returns:
            Dict[str, Dict]: 渠道状态字典
        """
        status = {}
        for channel_name, adapter in self.adapters.items():
            status[channel_name] = {
                "configured": adapter.is_configured(),
                "initialized": adapter._initialized,
                "required_env_vars": adapter.get_required_env_vars()
            }
        return status


# 单例模式
_router_instance: Optional[ChannelMessageRouter] = None


def get_channel_router() -> ChannelMessageRouter:
    """
    获取渠道路由器单例

    Returns:
        ChannelMessageRouter
    """
    global _router_instance
    if _router_instance is None:
        _router_instance = ChannelMessageRouter()
    return _router_instance


async def initialize_channel_router() -> ChannelMessageRouter:
    """
    初始化渠道路由器(确保已初始化)

    Returns:
        ChannelMessageRouter
    """
    router = get_channel_router()
    if not router._initialized:
        await router.initialize()
    return router
