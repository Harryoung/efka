"""
Redis Storage - Redis-based session storage implementation
Supports high-performance session data persistence and automatic expiration
"""

import logging
import json
from datetime import datetime
from typing import Optional, Dict

import redis.asyncio as aioredis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from .base import SessionStorage, SessionRecord

logger = logging.getLogger(__name__)


class RedisSessionStorage(SessionStorage):
    """
    Redis-based session storage

    Features:
    - High-performance in-memory storage
    - Automatic expiration (TTL)
    - Supports distributed deployment
    - Connection pool management
    """

    def __init__(
        self,
        redis_url: str = "redis://127.0.0.1:6379/0",
        ttl_seconds: int = 7 * 86400,  # 7 days
        key_prefix: str = "kb_session:",
        max_connections: int = 10,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize Redis storage

        Args:
            redis_url: Redis connection URL
            ttl_seconds: Session expiration time (seconds)
            key_prefix: Redis key prefix
            max_connections: Maximum number of connections
            username: Redis ACL username (optional)
            password: Redis password (optional)
        """
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix
        self.max_connections = max_connections
        self.username = username
        self.password = password
        self.redis: Optional[aioredis.Redis] = None
        self._connected = False

        auth_status = "enabled" if password else "disabled"
        logger.info(
            "Initializing RedisSessionStorage: %s, TTL=%ss, authentication %s",
            redis_url,
            ttl_seconds,
            auth_status
        )

    async def connect(self) -> None:
        """Establish Redis connection"""
        if self._connected and self.redis:
            return

        try:
            connection_kwargs = {
                "encoding": "utf-8",
                "decode_responses": True,
                "max_connections": self.max_connections
            }
            if self.username:
                connection_kwargs["username"] = self.username
            if self.password:
                connection_kwargs["password"] = self.password

            self.redis = await aioredis.from_url(
                self.redis_url,
                **connection_kwargs
            )
            # Test connection
            await self.redis.ping()
            self._connected = True
            logger.info("✅ Redis connection successful")
        except RedisConnectionError as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self._connected = False
            raise
        except Exception as e:
            logger.error(f"❌ Redis initialization failed: {e}")
            self._connected = False
            raise

    def _make_key(self, user_id: str) -> str:
        """
        Generate Redis key

        Args:
            user_id: User ID

        Returns:
            Complete Redis key
        """
        return f"{self.key_prefix}{user_id}"

    async def get_active_session(self, user_id: str) -> Optional[SessionRecord]:
        """
        Get user's active session

        Args:
            user_id: User identifier

        Returns:
            Session record, or None if not exists
        """
        if not self._connected or not self.redis:
            raise RuntimeError("Redis not connected")

        try:
            key = self._make_key(user_id)
            data = await self.redis.hgetall(key)

            if not data:
                logger.debug(f"User {user_id} has no active session")
                return None

            # Deserialize (compatible with old data format)
            # New format: internal_session_id + sdk_session_id
            # Old format: claude_session_id
            internal_id = data.get("internal_session_id") or data.get("claude_session_id")
            sdk_id = data.get("sdk_session_id")  # May be None or empty string

            session = SessionRecord(
                user_id=user_id,
                internal_session_id=internal_id,
                sdk_session_id=sdk_id if sdk_id else None,
                created_at=datetime.fromisoformat(data["created_at"]),
                last_active=datetime.fromisoformat(data["last_active"]),
                turn_count=int(data.get("turn_count", 0)),
                metadata=json.loads(data.get("metadata", "{}"))
            )

            logger.debug(
                f"Loaded session from Redis: {user_id} -> internal={session.internal_session_id}, "
                f"sdk={session.sdk_session_id or 'None'}"
            )
            return session

        except RedisError as e:
            logger.error(f"Redis read failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Session deserialization failed: {e}")
            raise

    async def save_active_session(self, session: SessionRecord) -> None:
        """
        Save active session

        Args:
            session: Session record
        """
        if not self._connected or not self.redis:
            raise RuntimeError("Redis not connected")

        try:
            key = self._make_key(session.user_id)

            # Serialize (new format)
            data = {
                "internal_session_id": session.internal_session_id,
                "sdk_session_id": session.sdk_session_id or "",  # Redis doesn't support None
                "created_at": session.created_at.isoformat(),
                "last_active": session.last_active.isoformat(),
                "turn_count": str(session.turn_count),
                "metadata": json.dumps(session.metadata, ensure_ascii=False)
            }

            # Use pipeline for performance optimization
            async with self.redis.pipeline() as pipe:
                # Save data
                await pipe.hset(key, mapping=data)
                # Set expiration time
                await pipe.expire(key, self.ttl_seconds)
                await pipe.execute()

            logger.debug(
                f"Saved session to Redis: {session.user_id} -> internal={session.internal_session_id}, "
                f"sdk={session.sdk_session_id or 'None'}, TTL={self.ttl_seconds}s"
            )

        except RedisError as e:
            logger.error(f"Redis write failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Session serialization failed: {e}")
            raise

    async def delete_active_session(self, user_id: str) -> bool:
        """
        Delete active session

        Args:
            user_id: User identifier

        Returns:
            Whether deletion was successful
        """
        if not self._connected or not self.redis:
            raise RuntimeError("Redis not connected")

        try:
            key = self._make_key(user_id)
            result = await self.redis.delete(key)

            if result > 0:
                logger.debug(f"Deleted Redis session: {user_id}")
                return True
            else:
                logger.debug(f"Session does not exist: {user_id}")
                return False

        except RedisError as e:
            logger.error(f"Redis delete failed: {e}")
            raise

    async def get_all_active_sessions(self) -> Dict[str, SessionRecord]:
        """
        Get all active sessions

        Returns:
            Mapping of user_id -> SessionRecord
        """
        if not self._connected or not self.redis:
            raise RuntimeError("Redis not connected")

        try:
            # Use SCAN to iterate all keys (avoid KEYS blocking)
            sessions = {}
            pattern = f"{self.key_prefix}*"

            async for key in self.redis.scan_iter(match=pattern, count=100):
                # Extract user_id
                user_id = key[len(self.key_prefix):]
                session = await self.get_active_session(user_id)
                if session:
                    sessions[user_id] = session

            logger.debug(f"Loaded {len(sessions)} active session(s)")
            return sessions

        except RedisError as e:
            logger.error(f"Redis scan failed: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Health check

        Returns:
            Whether Redis is healthy
        """
        try:
            if not self.redis:
                return False
            await self.redis.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            self._connected = False
            logger.info("Redis connection closed")

    async def __aenter__(self):
        """Support async with syntax"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Support async with syntax"""
        await self.close()
