"""
Storage Base - Storage layer abstract interface
Defines unified interface for session storage, supporting multiple storage backends (Redis, PostgreSQL, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict


@dataclass
class SessionRecord:
    """
    Session record data structure

    Represents user_id → session mapping relationship

    Field descriptions:
    - internal_session_id: Internal tracking ID (UUID we generate)
    - sdk_session_id: Real session ID returned by SDK (for resume)
      - None: New session, SDK response not yet received
      - str: Real ID returned by SDK, can be used for resume
    """
    user_id: str                                      # User unique identifier
    internal_session_id: str                          # Internal tracking ID (UUID we generate)
    sdk_session_id: Optional[str] = None              # Real session ID returned by SDK
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    turn_count: int = 0                               # Conversation turn count
    metadata: Dict = field(default_factory=dict)      # Extension information

    # Compatibility alias (gradual migration)
    @property
    def claude_session_id(self) -> str:
        """Compatible with old code, returns internal_session_id"""
        return self.internal_session_id

    def is_expired(self, ttl_seconds: int = 7 * 86400) -> bool:
        """
        Check if session is expired

        Args:
            ttl_seconds: Timeout duration (seconds), default 7 days

        Returns:
            Whether expired
        """
        return (datetime.now() - self.last_active).total_seconds() > ttl_seconds

    def to_dict(self) -> dict:
        """
        Convert to dictionary (for serialization)

        Returns:
            Session information dictionary
        """
        return {
            "user_id": self.user_id,
            "internal_session_id": self.internal_session_id,
            "sdk_session_id": self.sdk_session_id,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "turn_count": self.turn_count,
            "metadata": self.metadata
        }


class SessionStorage(ABC):
    """
    Session storage abstract interface

    Defines unified storage interface, supporting multiple backend implementations:
    - RedisSessionStorage: Redis-based high-performance storage
    - PostgreSQLSessionStorage: PostgreSQL-based persistent storage
    - MemorySessionStorage: Memory-based temporary storage (fallback solution)
    """

    @abstractmethod
    async def get_active_session(self, user_id: str) -> Optional[SessionRecord]:
        """
        Get user's active session

        Args:
            user_id: User identifier

        Returns:
            Session record, or None if not exists
        """
        pass

    @abstractmethod
    async def save_active_session(self, session: SessionRecord) -> None:
        """
        Save active session

        Args:
            session: Session record
        """
        pass

    @abstractmethod
    async def delete_active_session(self, user_id: str) -> bool:
        """
        Delete active session

        Args:
            user_id: User identifier

        Returns:
            Whether deletion was successful
        """
        pass

    @abstractmethod
    async def get_all_active_sessions(self) -> Dict[str, SessionRecord]:
        """
        Get all active sessions

        Returns:
            Mapping of user_id -> SessionRecord
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Health check

        Returns:
            Whether storage backend is healthy
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        Close storage connection
        """
        pass
