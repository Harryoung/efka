"""
Session Manager - Session Manager (refactored version)
Responsible for managing user sessions, timeout control, and permission association
Supports Redis persistence and memory fallback
"""
import asyncio
import logging
import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from ..config.settings import get_settings
from ..storage.base import SessionStorage, SessionRecord
from ..storage.redis_storage import RedisSessionStorage
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """
    Session data class (backward compatible)

    Attributes:
        session_id: Session unique identifier
        user_id: User ID (optional, for permission management)
        created_at: Creation timestamp
        last_active: Last active timestamp
        metadata: Session metadata (stores additional information)
    """
    session_id: str
    user_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)

    def is_expired(self, timeout: int) -> bool:
        """
        Check if session is expired

        Args:
            timeout: Timeout duration (seconds)

        Returns:
            Whether expired
        """
        return (time.time() - self.last_active) > timeout

    def update_activity(self):
        """Update last active time"""
        self.last_active = time.time()

    def get_age(self) -> float:
        """
        Get session age (seconds)

        Returns:
            Seconds from creation to now
        """
        return time.time() - self.created_at

    def to_dict(self) -> dict:
        """
        Convert to dictionary

        Returns:
            Session information dictionary
        """
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "last_active": datetime.fromtimestamp(self.last_active).isoformat(),
            "age_seconds": self.get_age(),
            "metadata": self.metadata
        }


class SessionManager:
    """
    Session Manager (refactored version)

    Responsibilities:
    1. Create and delete sessions (original functionality, backward compatible)
    2. Session timeout detection and cleanup
    3. Session information query
    4. User permission association (reserved interface)
    5. Session persistence based on user_id (new feature)
    6. Redis fallback logic (new feature)

    Note: Concurrency control has been moved to SDKClientPool layer (kb_service_factory.py)
    """

    def __init__(self, storage: Optional[SessionStorage] = None):
        """
        Initialize session manager

        Args:
            storage: Session storage backend (optional, defaults to memory)
        """
        self.settings = get_settings()
        self.storage = storage

        # Original memory session storage (session_id -> Session)
        self.sessions: Dict[str, Session] = {}

        # New: User session memory cache (user_id -> claude_session_id)
        # Used for Redis fallback scenario
        self._user_sessions_memory: Dict[str, SessionRecord] = {}

        # Fallback flag
        self._using_fallback = False

        self.cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_running = False

        logger.info("Session manager initialized (supports Redis persistence)")

    async def initialize_storage(self) -> None:
        """Initialize storage backend"""
        if self.storage:
            try:
                await self.storage.connect()
                logger.info("✅ 会话存储初始化成功")
                self._using_fallback = False
            except Exception as e:
                logger.error(f"❌ 会话存储初始化失败: {e}")
                logger.warning("⚠️  降级到内存存储")
                self._using_fallback = True

    async def start_cleanup_task(self):
        """Start session cleanup task (runs in background)"""
        if self._cleanup_running:
            logger.warning("清理任务已在运行")
            return

        self._cleanup_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("会话清理任务已启动")

    async def stop_cleanup_task(self):
        """Stop session cleanup task"""
        if self.cleanup_task:
            self._cleanup_running = False
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("会话清理任务已停止")

    async def _cleanup_loop(self):
        """Session cleanup loop (check every minute)"""
        while self._cleanup_running:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"会话清理失败: {e}")

    async def cleanup_expired_sessions(self) -> int:
        """
        Cleanup expired sessions

        Returns:
            Number of cleaned sessions
        """
        timeout = self.settings.SESSION_TIMEOUT
        expired_sessions = [
            session_id
            for session_id, session in self.sessions.items()
            if session.is_expired(timeout)
        ]

        for session_id in expired_sessions:
            await self.delete_session(session_id)
            logger.info(f"清理过期会话: {session_id}")

        if expired_sessions:
            logger.info(f"已清理 {len(expired_sessions)} 个过期会话")

        return len(expired_sessions)

    # ===== Original methods (backward compatible) =====

    def create_session(
        self,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Session:
        """
        Create new session

        Args:
            user_id: User ID (optional)
            metadata: Session metadata (optional)

        Returns:
            Newly created session object
        """
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            user_id=user_id,
            metadata=metadata or {}
        )

        self.sessions[session_id] = session
        logger.info(f"创建新会话: {session_id} (用户: {user_id or 'anonymous'})")

        return session

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete session

        Args:
            session_id: Session ID

        Returns:
            Whether successfully deleted
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"删除会话: {session_id}")
            return True
        else:
            logger.warning(f"会话不存在: {session_id}")
            return False

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session

        Args:
            session_id: Session ID

        Returns:
            Session object, None if not exists
        """
        session = self.sessions.get(session_id)

        if session:
            # Update active time
            session.update_activity()

        return session

    def get_all_sessions(self) -> Dict[str, Session]:
        """
        Get all sessions

        Returns:
            Session dictionary
        """
        return self.sessions.copy()

    def get_session_count(self) -> int:
        """
        Get current session count

        Returns:
            Total session count
        """
        return len(self.sessions)

    def get_user_sessions(self, user_id: str) -> Dict[str, Session]:
        """
        Get all sessions for specified user

        Args:
            user_id: User ID

        Returns:
            Session dictionary for this user
        """
        return {
            sid: session
            for sid, session in self.sessions.items()
            if session.user_id == user_id
        }

    def session_exists(self, session_id: str) -> bool:
        """
        Check if session exists

        Args:
            session_id: Session ID

        Returns:
            Whether exists
        """
        return session_id in self.sessions

    def update_session_metadata(
        self,
        session_id: str,
        metadata: Dict
    ) -> bool:
        """
        Update session metadata

        Args:
            session_id: Session ID
            metadata: New metadata (will merge into existing metadata)

        Returns:
            Whether successfully updated
        """
        session = self.get_session(session_id)
        if session:
            session.metadata.update(metadata)
            logger.info(f"更新会话元数据: {session_id}")
            return True
        return False

    def get_statistics(self) -> dict:
        """
        Get session statistics

        Returns:
            Statistics dictionary
        """
        total = len(self.sessions)
        with_user = sum(1 for s in self.sessions.values() if s.user_id)
        anonymous = total - with_user

        if total > 0:
            avg_age = sum(s.get_age() for s in self.sessions.values()) / total
        else:
            avg_age = 0

        user_session_count = len(self._user_sessions_memory) if self._using_fallback else 0

        return {
            "total_sessions": total,
            "authenticated_sessions": with_user,
            "anonymous_sessions": anonymous,
            "average_age_seconds": avg_age,
            "cleanup_running": self._cleanup_running,
            "user_sessions_count": user_session_count,
            "using_redis_fallback": self._using_fallback
        }

    # ===== New methods (user_id based persistence) =====

    async def get_or_create_user_session(self, user_id: str) -> Optional[str]:
        """
        Get or create user session, return SDK session ID (for resume)

        Core logic:
        - If new user or new session: return None (no resume, let SDK create new session)
        - If existing session with sdk_session_id: return that ID (for resume)

        Args:
            user_id: User identifier

        Returns:
            sdk_session_id: Real session ID returned by SDK, for resume
                           - None: New session, no need to resume
                           - str: Existing session, can resume
        """
        # Try to get from Redis/storage backend
        if self.storage and not self._using_fallback:
            try:
                session = await self.storage.get_active_session(user_id)

                if session is None:
                    # Create new session (sdk_session_id is None)
                    session = SessionRecord(
                        user_id=user_id,
                        internal_session_id=str(uuid.uuid4()),
                        sdk_session_id=None  # Wait for SDK to return
                    )
                    await self.storage.save_active_session(session)
                    logger.info(f"为用户 {user_id} 创建新会话: internal={session.internal_session_id}")
                    return None  # New session, no resume
                else:
                    # Reuse existing session
                    if session.sdk_session_id:
                        logger.info(
                            f"用户 {user_id} 复用已有会话: sdk={session.sdk_session_id}"
                        )
                        return session.sdk_session_id  # Return SDK session ID for resume
                    else:
                        logger.info(
                            f"用户 {user_id} 会话存在但无 SDK ID: internal={session.internal_session_id}"
                        )
                        return None  # No SDK session ID, cannot resume

            except (RedisError, RedisConnectionError, RuntimeError) as e:
                logger.error(f"Redis 操作失败: {e}，降级到内存存储")
                self._using_fallback = True

        # Fallback to memory storage
        if user_id in self._user_sessions_memory:
            session = self._user_sessions_memory[user_id]
            if session.sdk_session_id:
                logger.info(f"[内存] 用户 {user_id} 复用会话: sdk={session.sdk_session_id}")
                return session.sdk_session_id
            else:
                logger.info(f"[内存] 用户 {user_id} 会话无 SDK ID")
                return None
        else:
            session = SessionRecord(
                user_id=user_id,
                internal_session_id=str(uuid.uuid4()),
                sdk_session_id=None
            )
            self._user_sessions_memory[user_id] = session
            logger.info(f"[内存] 为用户 {user_id} 创建新会话: internal={session.internal_session_id}")
            return None  # 新会话不 resume

    async def update_session_activity(
        self,
        user_id: str,
        turn_count: Optional[int] = None
    ) -> None:
        """
        Update session activity

        Args:
            user_id: User identifier
            turn_count: Conversation turn count (optional)
        """
        if self.storage and not self._using_fallback:
            try:
                session = await self.storage.get_active_session(user_id)
                if session:
                    session.last_active = datetime.now()
                    if turn_count is not None:
                        session.turn_count = turn_count
                    await self.storage.save_active_session(session)
                    logger.debug(f"更新用户 {user_id} 会话活跃度")
                return
            except (RedisError, RedisConnectionError, RuntimeError) as e:
                logger.error(f"Redis 更新失败: {e}，降级到内存存储")
                self._using_fallback = True

        # Fallback to memory
        if user_id in self._user_sessions_memory:
            session = self._user_sessions_memory[user_id]
            session.last_active = datetime.now()
            if turn_count is not None:
                session.turn_count = turn_count
            logger.debug(f"[内存] 更新用户 {user_id} 会话活跃度")

    async def save_sdk_session_id(self, user_id: str, sdk_session_id: str) -> None:
        """
        Save real session ID returned by SDK

        When SDK returns ResultMessage, extract session_id and save it.
        Next time this user requests, can use this ID to resume session.

        Args:
            user_id: User identifier
            sdk_session_id: Real session ID returned by SDK
        """
        if self.storage and not self._using_fallback:
            try:
                session = await self.storage.get_active_session(user_id)
                if session:
                    session.sdk_session_id = sdk_session_id
                    session.last_active = datetime.now()
                    await self.storage.save_active_session(session)
                    logger.info(f"保存用户 {user_id} 的 SDK session ID: {sdk_session_id}")
                else:
                    logger.warning(f"用户 {user_id} 没有活跃会话，无法保存 SDK session ID")
                return
            except (RedisError, RedisConnectionError, RuntimeError) as e:
                logger.error(f"Redis 保存 SDK session ID 失败: {e}，降级到内存存储")
                self._using_fallback = True

        # Fallback to memory
        if user_id in self._user_sessions_memory:
            session = self._user_sessions_memory[user_id]
            session.sdk_session_id = sdk_session_id
            session.last_active = datetime.now()
            logger.info(f"[内存] 保存用户 {user_id} 的 SDK session ID: {sdk_session_id}")
        else:
            logger.warning(f"[内存] 用户 {user_id} 没有活跃会话，无法保存 SDK session ID")

    async def clear_user_context(self, user_id: str) -> None:
        """
        Clear user context (archive old session, create new session)

        Note: After clearing, sdk_session_id is None, next request will create new SDK session

        Args:
            user_id: User identifier
        """
        if self.storage and not self._using_fallback:
            try:
                # Archive old session (PostgreSQL archiving not implemented yet)
                old_session = await self.storage.get_active_session(user_id)
                if old_session:
                    await self.storage.delete_active_session(user_id)
                    logger.info(f"用户 {user_id} 归档旧会话: internal={old_session.internal_session_id}")

                # Create new session (sdk_session_id is None)
                new_session = SessionRecord(
                    user_id=user_id,
                    internal_session_id=str(uuid.uuid4()),
                    sdk_session_id=None
                )
                await self.storage.save_active_session(new_session)
                logger.info(f"用户 {user_id} 创建新会话: internal={new_session.internal_session_id}")
                return

            except (RedisError, RedisConnectionError, RuntimeError) as e:
                logger.error(f"Redis 操作失败: {e}，降级到内存存储")
                self._using_fallback = True

        # Fallback to memory
        old_session = self._user_sessions_memory.get(user_id)
        if old_session:
            logger.info(f"[内存] 用户 {user_id} 归档旧会话: internal={old_session.internal_session_id}")

        new_session = SessionRecord(
            user_id=user_id,
            internal_session_id=str(uuid.uuid4()),
            sdk_session_id=None
        )
        self._user_sessions_memory[user_id] = new_session
        logger.info(f"[内存] 用户 {user_id} 创建新会话: internal={new_session.internal_session_id}")

    async def __aenter__(self):
        """Support async with syntax"""
        await self.start_cleanup_task()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Support async with syntax"""
        await self.stop_cleanup_task()
        if self.storage:
            await self.storage.close()


# Singleton instance
_session_manager_instance: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """
    Get session manager singleton

    Returns:
        SessionManager instance
    """
    global _session_manager_instance
    if _session_manager_instance is None:
        _session_manager_instance = SessionManager()
    return _session_manager_instance


# Export
__all__ = [
    "Session",
    "SessionManager",
    "get_session_manager"
]
