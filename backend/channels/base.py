"""
渠道抽象层基类

定义统一的消息接口,屏蔽不同IM平台的API差异。
所有IM平台适配器(企微、飞书、钉钉、Slack等)都应继承BaseChannelAdapter。

设计原则:
1. 统一消息模型: ChannelMessage封装跨平台消息
2. 抽象接口: 子类实现平台特定逻辑
3. 配置检测: 自动判断平台是否已配置
4. 错误处理: 统一异常处理机制
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """消息类型枚举"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    MARKDOWN = "markdown"
    EVENT = "event"  # 系统事件(如群聊@、加好友等)


class ChannelType(str, Enum):
    """渠道类型枚举"""
    WEWORK = "wework"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    SLACK = "slack"
    WEB = "web"  # Web UI


class ChannelUser(BaseModel):
    """渠道用户模型"""
    user_id: str = Field(..., description="用户在渠道内的唯一标识(如企微userid、飞书open_id)")
    username: Optional[str] = Field(None, description="用户昵称")
    email: Optional[str] = Field(None, description="用户邮箱")
    department: Optional[str] = Field(None, description="用户部门")
    channel: ChannelType = Field(..., description="用户所属渠道")
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="原始用户数据")

    class Config:
        use_enum_values = True


class ChannelMessage(BaseModel):
    """渠道消息模型 - 统一的跨平台消息格式"""
    message_id: str = Field(..., description="消息唯一标识")
    user: ChannelUser = Field(..., description="发送消息的用户")
    content: str = Field(..., description="消息文本内容")
    msg_type: MessageType = Field(MessageType.TEXT, description="消息类型")
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp()), description="消息时间戳(秒)")

    # 可选字段
    session_id: Optional[str] = Field(None, description="会话ID(用于会话管理)")
    reply_to: Optional[str] = Field(None, description="回复的消息ID")
    attachments: List[Dict[str, Any]] = Field(default_factory=list, description="附件列表(图片/文件等)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据(如@列表、表情等)")
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="原始消息数据(保留平台特定信息)")

    class Config:
        use_enum_values = True


class ChannelResponse(BaseModel):
    """渠道响应模型"""
    success: bool = Field(..., description="操作是否成功")
    message: Optional[str] = Field(None, description="响应消息")
    data: Optional[Dict[str, Any]] = Field(None, description="响应数据")
    error: Optional[str] = Field(None, description="错误信息")


class BaseChannelAdapter(ABC):
    """
    渠道适配器抽象基类

    所有IM平台适配器必须继承此类并实现所有抽象方法。
    适配器负责:
    1. 消息收发: 解析平台回调消息,发送响应消息
    2. 签名验证: 验证回调请求的合法性
    3. 配置检测: 检查平台所需环境变量是否配置
    4. 用户身份: 获取和管理用户信息
    """

    def __init__(self, channel_type: ChannelType):
        """
        初始化适配器

        Args:
            channel_type: 渠道类型枚举
        """
        self.channel_type = channel_type
        self.channel_name = channel_type.value
        self._initialized = False

    @abstractmethod
    async def send_message(
        self,
        user_id: str,
        content: str,
        msg_type: MessageType = MessageType.TEXT,
        **kwargs
    ) -> ChannelResponse:
        """
        发送消息到IM平台

        Args:
            user_id: 目标用户ID(平台特定ID)
            content: 消息内容
            msg_type: 消息类型
            **kwargs: 平台特定参数(如图片media_id、文件路径等)

        Returns:
            ChannelResponse: 发送结果
        """
        pass

    @abstractmethod
    async def parse_message(self, request_data: Dict[str, Any]) -> ChannelMessage:
        """
        解析IM平台回调消息

        Args:
            request_data: 平台回调的原始数据(通常是HTTP POST body)

        Returns:
            ChannelMessage: 统一格式的消息对象

        Raises:
            ValueError: 消息格式错误
        """
        pass

    @abstractmethod
    async def verify_signature(self, request_data: Dict[str, Any]) -> bool:
        """
        验证回调请求的签名/合法性

        Args:
            request_data: 包含签名参数的请求数据

        Returns:
            bool: 签名是否有效
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """
        检查渠道是否已配置必要的环境变量

        Returns:
            bool: 是否已配置
        """
        pass

    @abstractmethod
    async def get_user_info(self, user_id: str) -> ChannelUser:
        """
        获取用户信息

        Args:
            user_id: 用户ID

        Returns:
            ChannelUser: 用户信息对象
        """
        pass

    # 可选方法(子类可选择性实现)

    async def initialize(self) -> None:
        """
        初始化适配器(可选)

        用于执行一次性初始化操作:
        - 获取access_token
        - 建立连接池
        - 验证配置有效性
        """
        if self._initialized:
            logger.warning(f"{self.channel_name} adapter already initialized")
            return

        logger.info(f"Initializing {self.channel_name} adapter...")
        self._initialized = True

    async def handle_event(self, event_data: Dict[str, Any]) -> Optional[ChannelResponse]:
        """
        处理平台事件(如用户加入、群聊@等)

        Args:
            event_data: 事件数据

        Returns:
            Optional[ChannelResponse]: 事件处理结果(如果需要响应)
        """
        logger.debug(f"{self.channel_name} received event: {event_data.get('event_type', 'unknown')}")
        return None

    async def send_batch_message(
        self,
        user_ids: List[str],
        content: str,
        msg_type: MessageType = MessageType.TEXT,
        **kwargs
    ) -> List[ChannelResponse]:
        """
        批量发送消息(默认实现:逐个发送)

        子类可以重写此方法以使用平台的批量发送API提高效率。

        Args:
            user_ids: 目标用户ID列表
            content: 消息内容
            msg_type: 消息类型
            **kwargs: 平台特定参数

        Returns:
            List[ChannelResponse]: 每个用户的发送结果
        """
        results = []
        for user_id in user_ids:
            try:
                result = await self.send_message(user_id, content, msg_type, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to send message to {user_id}: {e}")
                results.append(ChannelResponse(
                    success=False,
                    error=str(e)
                ))
        return results

    def get_required_env_vars(self) -> List[str]:
        """
        获取渠道所需的环境变量列表(用于配置检查)

        Returns:
            List[str]: 必需的环境变量名称列表
        """
        return []

    def __repr__(self) -> str:
        configured = "configured" if self.is_configured() else "not configured"
        return f"<{self.__class__.__name__} channel={self.channel_name} status={configured}>"


class ChannelAdapterError(Exception):
    """渠道适配器异常基类"""
    pass


class ChannelNotConfiguredError(ChannelAdapterError):
    """渠道未配置异常"""
    pass


class ChannelMessageError(ChannelAdapterError):
    """渠道消息错误异常"""
    pass


class ChannelAuthError(ChannelAdapterError):
    """渠道认证错误异常"""
    pass
