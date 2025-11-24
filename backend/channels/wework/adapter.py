"""
企业微信渠道适配器

实现BaseChannelAdapter接口,提供:
1. 消息解析(XML解密 → ChannelMessage)
2. 消息发送(ChannelMessage → 企微API)
3. 签名验证
4. 配置检测
5. 用户信息查询
"""

import os
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List

from backend.channels.base import (
    BaseChannelAdapter,
    ChannelMessage,
    ChannelUser,
    ChannelResponse,
    MessageType,
    ChannelType,
    ChannelNotConfiguredError,
    ChannelMessageError,
    ChannelAuthError,
)
from backend.channels.wework.client import WeWorkClient, WeWorkAPIError
from backend.utils.wework_crypto import decrypt_message, parse_message

logger = logging.getLogger(__name__)


class WeWorkAdapter(BaseChannelAdapter):
    """企业微信渠道适配器"""

    def __init__(self):
        """初始化适配器"""
        super().__init__(ChannelType.WEWORK)

        # 从环境变量加载配置
        self.corp_id = os.getenv("WEWORK_CORP_ID", "")
        self.corp_secret = os.getenv("WEWORK_CORP_SECRET", "")
        self.agent_id = int(os.getenv("WEWORK_AGENT_ID", "0"))
        self.token = os.getenv("WEWORK_TOKEN", "")
        self.encoding_aes_key = os.getenv("WEWORK_ENCODING_AES_KEY", "")

        # 初始化API客户端(延迟到真正需要时)
        self._client: Optional[WeWorkClient] = None

    @property
    def client(self) -> WeWorkClient:
        """获取API客户端(懒加载)"""
        if self._client is None:
            if not self.is_configured():
                raise ChannelNotConfiguredError(
                    f"{self.channel_name} is not configured. "
                    "Please set WEWORK_CORP_ID, WEWORK_CORP_SECRET, and WEWORK_AGENT_ID"
                )

            self._client = WeWorkClient(
                corp_id=self.corp_id,
                corp_secret=self.corp_secret,
                agent_id=self.agent_id
            )
            logger.info(f"WeWork API client initialized for agent {self.agent_id}")

        return self._client

    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(
            self.corp_id and
            self.corp_secret and
            self.agent_id > 0 and
            self.token and
            self.encoding_aes_key
        )

    def get_required_env_vars(self) -> List[str]:
        """获取必需的环境变量列表"""
        return [
            "WEWORK_CORP_ID",
            "WEWORK_CORP_SECRET",
            "WEWORK_AGENT_ID",
            "WEWORK_TOKEN",
            "WEWORK_ENCODING_AES_KEY"
        ]

    async def send_message(
        self,
        user_id: str,
        content: str,
        msg_type: MessageType = MessageType.TEXT,
        **kwargs
    ) -> ChannelResponse:
        """
        发送消息到企微

        Args:
            user_id: 企微userid
            content: 消息内容
            msg_type: 消息类型(TEXT/MARKDOWN/IMAGE/FILE)
            **kwargs: 平台特定参数(如safe, media_id等)

        Returns:
            ChannelResponse
        """
        try:
            if msg_type == MessageType.TEXT:
                result = self.client.send_text(
                    touser=user_id,
                    content=content,
                    safe=kwargs.get("safe", 0),
                    enable_duplicate_check=kwargs.get("enable_duplicate_check", 0)
                )
            elif msg_type == MessageType.MARKDOWN:
                result = self.client.send_markdown(
                    touser=user_id,
                    content=content,
                    enable_duplicate_check=kwargs.get("enable_duplicate_check", 0)
                )
            elif msg_type == MessageType.IMAGE:
                media_id = kwargs.get("media_id")
                if not media_id:
                    raise ValueError("media_id is required for IMAGE message")
                result = self.client.send_image(
                    touser=user_id,
                    media_id=media_id,
                    safe=kwargs.get("safe", 0)
                )
            elif msg_type == MessageType.FILE:
                media_id = kwargs.get("media_id")
                if not media_id:
                    raise ValueError("media_id is required for FILE message")
                result = self.client.send_file(
                    touser=user_id,
                    media_id=media_id,
                    safe=kwargs.get("safe", 0)
                )
            else:
                return ChannelResponse(
                    success=False,
                    error=f"Unsupported message type: {msg_type}"
                )

            return ChannelResponse(
                success=True,
                message="Message sent successfully",
                data=result
            )

        except WeWorkAPIError as e:
            logger.error(f"WeWork API error: {e}")
            return ChannelResponse(
                success=False,
                error=f"WeWork API error {e.errcode}: {e.errmsg}"
            )
        except Exception as e:
            logger.error(f"Failed to send message: {e}", exc_info=True)
            return ChannelResponse(
                success=False,
                error=str(e)
            )

    async def parse_message(self, request_data: Dict[str, Any]) -> ChannelMessage:
        """
        解析企微回调消息

        Args:
            request_data: 包含以下字段:
                - xml_content: XML字符串
                - msg_signature: 签名(可选,用于验证)
                - timestamp: 时间戳(可选)
                - nonce: 随机数(可选)

        Returns:
            ChannelMessage

        Raises:
            ChannelMessageError: 消息解析失败
        """
        try:
            xml_content = request_data.get("xml_content")
            if not xml_content:
                raise ValueError("xml_content is required")

            # 解析XML获取加密内容
            root = ET.fromstring(xml_content)
            encrypt_element = root.find('Encrypt')
            if encrypt_element is None:
                raise ValueError("Missing <Encrypt> element in XML")
            encrypt_str = encrypt_element.text

            # 解密消息
            decrypted_xml = decrypt_message(
                encrypt_str,
                self.encoding_aes_key,
                self.corp_id
            )

            # 解析为字典
            message_dict = parse_message(decrypted_xml)

            # 转换为ChannelMessage
            return self._dict_to_channel_message(message_dict)

        except Exception as e:
            logger.error(f"Failed to parse WeWork message: {e}", exc_info=True)
            raise ChannelMessageError(f"Failed to parse message: {e}")

    def _dict_to_channel_message(self, message_dict: Dict[str, Any]) -> ChannelMessage:
        """
        将企微消息字典转换为ChannelMessage

        Args:
            message_dict: 解密后的消息字典

        Returns:
            ChannelMessage
        """
        sender_userid = message_dict.get("FromUserName", "")
        msg_type_str = message_dict.get("MsgType", "text")
        content = message_dict.get("Content", "")
        message_id = message_dict.get("MsgId", "")
        timestamp = int(message_dict.get("CreateTime", 0))

        # 映射消息类型
        msg_type_map = {
            "text": MessageType.TEXT,
            "image": MessageType.IMAGE,
            "file": MessageType.FILE,
            "event": MessageType.EVENT
        }
        msg_type = msg_type_map.get(msg_type_str, MessageType.TEXT)

        # 创建用户对象(仅包含userid,详细信息通过get_user_info获取)
        user = ChannelUser(
            user_id=sender_userid,
            channel=ChannelType.WEWORK,
            raw_data={}
        )

        # 构造ChannelMessage
        channel_msg = ChannelMessage(
            message_id=str(message_id),
            user=user,
            content=content,
            msg_type=msg_type,
            timestamp=timestamp,
            raw_data=message_dict
        )

        # 处理附件(图片/文件)
        if msg_type == MessageType.IMAGE:
            pic_url = message_dict.get("PicUrl")
            media_id = message_dict.get("MediaId")
            if pic_url or media_id:
                channel_msg.attachments = [{
                    "type": "image",
                    "pic_url": pic_url,
                    "media_id": media_id
                }]

        elif msg_type == MessageType.FILE:
            media_id = message_dict.get("MediaId")
            if media_id:
                channel_msg.attachments = [{
                    "type": "file",
                    "media_id": media_id
                }]

        return channel_msg

    async def verify_signature(self, request_data: Dict[str, Any]) -> bool:
        """
        验证回调签名

        Args:
            request_data: 包含以下字段:
                - msg_signature: 签名
                - timestamp: 时间戳
                - nonce: 随机数
                - echo_str: 回显字符串(URL验证时)
                - encrypt_msg: 加密消息(消息回调时)

        Returns:
            bool: 签名是否有效
        """
        try:
            from backend.utils.wework_crypto import verify_signature

            msg_signature = request_data.get("msg_signature", "")
            timestamp = request_data.get("timestamp", "")
            nonce = request_data.get("nonce", "")

            # URL验证(GET请求)
            if "echo_str" in request_data:
                echo_str = request_data["echo_str"]
                return verify_signature(
                    msg_signature,
                    timestamp,
                    nonce,
                    echo_str,
                    self.token
                )

            # 消息回调(POST请求)
            elif "encrypt_msg" in request_data:
                encrypt_msg = request_data["encrypt_msg"]
                return verify_signature(
                    msg_signature,
                    timestamp,
                    nonce,
                    encrypt_msg,
                    self.token
                )

            else:
                logger.warning("Missing echo_str or encrypt_msg in request_data")
                return False

        except Exception as e:
            logger.error(f"Signature verification failed: {e}", exc_info=True)
            return False

    async def get_user_info(self, user_id: str) -> ChannelUser:
        """
        获取用户详细信息

        Args:
            user_id: 企微userid

        Returns:
            ChannelUser
        """
        try:
            user_data = self.client.get_user_info(user_id)

            return ChannelUser(
                user_id=user_id,
                username=user_data.get("name"),
                email=user_data.get("email"),
                department=user_data.get("department"),  # 可能需要进一步处理
                channel=ChannelType.WEWORK,
                raw_data=user_data
            )

        except WeWorkAPIError as e:
            logger.error(f"Failed to get user info: {e}")
            # 返回基本用户对象
            return ChannelUser(
                user_id=user_id,
                channel=ChannelType.WEWORK,
                raw_data={}
            )

    async def send_batch_message(
        self,
        user_ids: List[str],
        content: str,
        msg_type: MessageType = MessageType.TEXT,
        **kwargs
    ) -> List[ChannelResponse]:
        """
        批量发送消息(企微支持一次发送给多个用户)

        Args:
            user_ids: 用户ID列表
            content: 消息内容
            msg_type: 消息类型
            **kwargs: 平台特定参数

        Returns:
            List[ChannelResponse]: 发送结果列表(企微API返回单个结果)
        """
        # 企微支持touser参数用'|'分隔多个用户
        touser_str = "|".join(user_ids)

        result = await self.send_message(touser_str, content, msg_type, **kwargs)

        # 返回相同结果给所有用户(企微API不区分单个用户的发送状态)
        return [result] * len(user_ids)

    async def upload_media(self, file_path: str, media_type: str) -> str:
        """
        上传媒体文件

        Args:
            file_path: 文件路径
            media_type: 媒体类型(image/voice/video/file)

        Returns:
            media_id
        """
        try:
            media_id = self.client.upload_media(media_type, file_path)
            logger.info(f"Uploaded media: {file_path} → {media_id}")
            return media_id
        except Exception as e:
            logger.error(f"Failed to upload media: {e}", exc_info=True)
            raise ChannelMessageError(f"Failed to upload media: {e}")

    async def handle_event(self, event_data: Dict[str, Any]) -> Optional[ChannelResponse]:
        """
        处理企微事件(如加入群聊、@提及等)

        Args:
            event_data: 事件数据

        Returns:
            Optional[ChannelResponse]: 事件处理结果
        """
        event_type = event_data.get("Event")
        logger.info(f"Received WeWork event: {event_type}")

        # 目前不处理事件,仅记录日志
        # 未来可以扩展处理特定事件(如subscribe/unsubscribe)

        return None
