"""
WeChat Work (企业微信) Channel Adapter

Implements BaseChannelAdapter interface, providing:
1. Message parsing (XML decryption → ChannelMessage)
2. Message sending (ChannelMessage → WeChat Work API)
3. Signature verification
4. Configuration detection
5. User information query
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
    """WeChat Work channel adapter"""

    def __init__(self):
        """Initialize adapter"""
        super().__init__(ChannelType.WEWORK)

        # Load configuration from environment variables
        self.corp_id = os.getenv("WEWORK_CORP_ID", "")
        self.corp_secret = os.getenv("WEWORK_CORP_SECRET", "")
        self.agent_id = int(os.getenv("WEWORK_AGENT_ID", "0"))
        self.token = os.getenv("WEWORK_TOKEN", "")
        self.encoding_aes_key = os.getenv("WEWORK_ENCODING_AES_KEY", "")

        # Initialize API client (lazy loading)
        self._client: Optional[WeWorkClient] = None

    @property
    def client(self) -> WeWorkClient:
        """Get API client (lazy loading)"""
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
        """Check if configured"""
        return bool(
            self.corp_id and
            self.corp_secret and
            self.agent_id > 0 and
            self.token and
            self.encoding_aes_key
        )

    def get_required_env_vars(self) -> List[str]:
        """Get list of required environment variables"""
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
        Send message to WeChat Work

        Args:
            user_id: WeChat Work userid
            content: Message content
            msg_type: Message type (TEXT/MARKDOWN/IMAGE/FILE)
            **kwargs: Platform-specific parameters (e.g., safe, media_id, etc.)

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
        Parse WeChat Work callback message

        Args:
            request_data: Contains the following fields:
                - xml_content: XML string
                - msg_signature: Signature (optional, for verification)
                - timestamp: Timestamp (optional)
                - nonce: Random number (optional)

        Returns:
            ChannelMessage

        Raises:
            ChannelMessageError: Message parsing failed
        """
        try:
            xml_content = request_data.get("xml_content")
            if not xml_content:
                raise ValueError("xml_content is required")

            # Parse XML to get encrypted content
            root = ET.fromstring(xml_content)
            encrypt_element = root.find('Encrypt')
            if encrypt_element is None:
                raise ValueError("Missing <Encrypt> element in XML")
            encrypt_str = encrypt_element.text

            # Decrypt message
            decrypted_xml = decrypt_message(
                encrypt_str,
                self.encoding_aes_key,
                self.corp_id
            )

            # Parse to dictionary
            message_dict = parse_message(decrypted_xml)

            # Convert to ChannelMessage
            return self._dict_to_channel_message(message_dict)

        except Exception as e:
            logger.error(f"Failed to parse WeWork message: {e}", exc_info=True)
            raise ChannelMessageError(f"Failed to parse message: {e}")

    def _dict_to_channel_message(self, message_dict: Dict[str, Any]) -> ChannelMessage:
        """
        Convert WeChat Work message dictionary to ChannelMessage

        Args:
            message_dict: Decrypted message dictionary

        Returns:
            ChannelMessage
        """
        sender_userid = message_dict.get("FromUserName", "")
        msg_type_str = message_dict.get("MsgType", "text")
        content = message_dict.get("Content", "")
        message_id = message_dict.get("MsgId", "")
        timestamp = int(message_dict.get("CreateTime", 0))

        # Map message type
        msg_type_map = {
            "text": MessageType.TEXT,
            "image": MessageType.IMAGE,
            "file": MessageType.FILE,
            "event": MessageType.EVENT
        }
        msg_type = msg_type_map.get(msg_type_str, MessageType.TEXT)

        # Create user object (contains only userid, detailed info via get_user_info)
        user = ChannelUser(
            user_id=sender_userid,
            channel=ChannelType.WEWORK,
            raw_data={}
        )

        # Construct ChannelMessage
        channel_msg = ChannelMessage(
            message_id=str(message_id),
            user=user,
            content=content,
            msg_type=msg_type,
            timestamp=timestamp,
            raw_data=message_dict
        )

        # Handle attachments (images/files)
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
        Verify callback signature

        Args:
            request_data: Contains the following fields:
                - msg_signature: Signature
                - timestamp: Timestamp
                - nonce: Random number
                - echo_str: Echo string (for URL verification)
                - encrypt_msg: Encrypted message (for message callback)

        Returns:
            bool: Whether the signature is valid
        """
        try:
            from backend.utils.wework_crypto import verify_signature

            msg_signature = request_data.get("msg_signature", "")
            timestamp = request_data.get("timestamp", "")
            nonce = request_data.get("nonce", "")

            # URL verification (GET request)
            if "echo_str" in request_data:
                echo_str = request_data["echo_str"]
                return verify_signature(
                    msg_signature,
                    timestamp,
                    nonce,
                    echo_str,
                    self.token
                )

            # Message callback (POST request)
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
        Get detailed user information

        Args:
            user_id: WeChat Work userid

        Returns:
            ChannelUser
        """
        try:
            user_data = self.client.get_user_info(user_id)

            return ChannelUser(
                user_id=user_id,
                username=user_data.get("name"),
                email=user_data.get("email"),
                department=user_data.get("department"),  # May need further processing
                channel=ChannelType.WEWORK,
                raw_data=user_data
            )

        except WeWorkAPIError as e:
            logger.error(f"Failed to get user info: {e}")
            # Return basic user object
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
        Send batch messages (WeChat Work supports sending to multiple users at once)

        Args:
            user_ids: List of user IDs
            content: Message content
            msg_type: Message type
            **kwargs: Platform-specific parameters

        Returns:
            List[ChannelResponse]: List of sending results (WeChat Work API returns single result)
        """
        # WeChat Work supports touser parameter with '|' separating multiple users
        touser_str = "|".join(user_ids)

        result = await self.send_message(touser_str, content, msg_type, **kwargs)

        # Return same result to all users (WeChat Work API doesn't distinguish individual user status)
        return [result] * len(user_ids)

    async def upload_media(self, file_path: str, media_type: str) -> str:
        """
        Upload media file

        Args:
            file_path: File path
            media_type: Media type (image/voice/video/file)

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
        Handle WeChat Work events (e.g., join group, mentions, etc.)

        Args:
            event_data: Event data

        Returns:
            Optional[ChannelResponse]: Event handling result
        """
        event_type = event_data.get("Event")
        logger.info(f"Received WeWork event: {event_type}")

        # Currently not handling events, only logging
        # Can be extended in the future to handle specific events (e.g., subscribe/unsubscribe)

        return None
