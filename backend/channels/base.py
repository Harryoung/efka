"""
Channel abstraction layer base class

Defines a unified message interface to abstract away API differences between IM platforms.
All IM platform adapters (WeChat Work, Feishu, DingTalk, Slack, etc.) should inherit from BaseChannelAdapter.

Design principles:
1. Unified message model: ChannelMessage encapsulates cross-platform messages
2. Abstract interface: Subclasses implement platform-specific logic
3. Configuration detection: Automatically determines if platform is configured
4. Error handling: Unified exception handling mechanism
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
    """Message type enumeration"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    MARKDOWN = "markdown"
    EVENT = "event"  # System events (e.g., group mentions, friend requests, etc.)


class ChannelType(str, Enum):
    """Channel type enumeration"""
    WEWORK = "wework"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    SLACK = "slack"
    WEB = "web"  # Web UI


class ChannelUser(BaseModel):
    """Channel user model"""
    user_id: str = Field(..., description="Unique user identifier within the channel (e.g., WeChat Work userid, Feishu open_id)")
    username: Optional[str] = Field(None, description="User nickname")
    email: Optional[str] = Field(None, description="User email")
    department: Optional[str] = Field(None, description="User department")
    channel: ChannelType = Field(..., description="Channel the user belongs to")
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Raw user data")

    class Config:
        use_enum_values = True


class ChannelMessage(BaseModel):
    """Channel message model - Unified cross-platform message format"""
    message_id: str = Field(..., description="Unique message identifier")
    user: ChannelUser = Field(..., description="User who sent the message")
    content: str = Field(..., description="Message text content")
    msg_type: MessageType = Field(MessageType.TEXT, description="Message type")
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp()), description="Message timestamp (seconds)")

    # Optional fields
    session_id: Optional[str] = Field(None, description="Session ID (for session management)")
    reply_to: Optional[str] = Field(None, description="ID of the message being replied to")
    attachments: List[Dict[str, Any]] = Field(default_factory=list, description="List of attachments (images/files, etc.)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata (e.g., mention list, emojis, etc.)")
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Raw message data (preserves platform-specific information)")

    class Config:
        use_enum_values = True


class ChannelResponse(BaseModel):
    """Channel response model"""
    success: bool = Field(..., description="Whether the operation was successful")
    message: Optional[str] = Field(None, description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message")


class BaseChannelAdapter(ABC):
    """
    Channel adapter abstract base class

    All IM platform adapters must inherit from this class and implement all abstract methods.
    Adapter responsibilities:
    1. Message sending/receiving: Parse platform callback messages, send response messages
    2. Signature verification: Verify the legitimacy of callback requests
    3. Configuration detection: Check if required environment variables are configured
    4. User identity: Retrieve and manage user information
    """

    def __init__(self, channel_type: ChannelType):
        """
        Initialize the adapter

        Args:
            channel_type: Channel type enumeration
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
        Send message to IM platform

        Args:
            user_id: Target user ID (platform-specific ID)
            content: Message content
            msg_type: Message type
            **kwargs: Platform-specific parameters (e.g., image media_id, file path, etc.)

        Returns:
            ChannelResponse: Sending result
        """
        pass

    @abstractmethod
    async def parse_message(self, request_data: Dict[str, Any]) -> ChannelMessage:
        """
        Parse IM platform callback message

        Args:
            request_data: Raw data from platform callback (typically HTTP POST body)

        Returns:
            ChannelMessage: Message object in unified format

        Raises:
            ValueError: Invalid message format
        """
        pass

    @abstractmethod
    async def verify_signature(self, request_data: Dict[str, Any]) -> bool:
        """
        Verify callback request signature/legitimacy

        Args:
            request_data: Request data containing signature parameters

        Returns:
            bool: Whether the signature is valid
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if the channel has the necessary environment variables configured

        Returns:
            bool: Whether it is configured
        """
        pass

    @abstractmethod
    async def get_user_info(self, user_id: str) -> ChannelUser:
        """
        Get user information

        Args:
            user_id: User ID

        Returns:
            ChannelUser: User information object
        """
        pass

    # Optional methods (subclasses can optionally implement)

    async def initialize(self) -> None:
        """
        Initialize the adapter (optional)

        Used to perform one-time initialization operations:
        - Obtain access_token
        - Establish connection pool
        - Verify configuration validity
        """
        if self._initialized:
            logger.warning(f"{self.channel_name} adapter already initialized")
            return

        logger.info(f"Initializing {self.channel_name} adapter...")
        self._initialized = True

    async def handle_event(self, event_data: Dict[str, Any]) -> Optional[ChannelResponse]:
        """
        Handle platform events (e.g., user joins, group mentions, etc.)

        Args:
            event_data: Event data

        Returns:
            Optional[ChannelResponse]: Event handling result (if a response is needed)
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
        Send batch messages (default implementation: send one by one)

        Subclasses can override this method to use the platform's batch send API for improved efficiency.

        Args:
            user_ids: List of target user IDs
            content: Message content
            msg_type: Message type
            **kwargs: Platform-specific parameters

        Returns:
            List[ChannelResponse]: Sending result for each user
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
        Get the list of environment variables required by the channel (for configuration checking)

        Returns:
            List[str]: List of required environment variable names
        """
        return []

    def __repr__(self) -> str:
        configured = "configured" if self.is_configured() else "not configured"
        return f"<{self.__class__.__name__} channel={self.channel_name} status={configured}>"


class ChannelAdapterError(Exception):
    """Channel adapter exception base class"""
    pass


class ChannelNotConfiguredError(ChannelAdapterError):
    """Channel not configured exception"""
    pass


class ChannelMessageError(ChannelAdapterError):
    """Channel message error exception"""
    pass


class ChannelAuthError(ChannelAdapterError):
    """Channel authentication error exception"""
    pass
