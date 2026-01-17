"""
Routing Session Manager - Session Router session manager

Core responsibilities:
1. Manage Session lifecycle (create, query, update, expire)
2. Concurrent-safe Session summary updates (optimistic lock CAS mechanism)
3. Return user Sessions in reverse chronological order (supports Router semantic judgment)
4. State-based TTL management (ACTIVE 7 days, RESOLVED 24h)

Difference from existing session_manager.py:
- session_manager.py: Manages Claude SDK sessions (user_id → claude_session_id)
- routing_session_manager.py: Manages semantic session routing (supports concurrent sessions)
"""

import asyncio
import logging
import json
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from pathlib import Path
import uuid

from backend.models.session import (
    Session,
    SessionSummary,
    SessionRole,
    SessionStatus,
    SessionQueryResult,
    MessageSnapshot
)

logger = logging.getLogger(__name__)


class RoutingSessionManager:
    """
    Routing Session Manager (supports Redis optimistic lock and memory fallback)

    Redis Key design:
    - session:{session_id} -> Session JSON
    - user_sessions:{user_id} -> Set[session_id]
    - session_history:{session_id} -> List[Message JSON]

    Architecture notes:
    - Primary storage: Redis (persistent, distributed)
    - Fallback storage: Memory (when Redis fails)
    """

    def __init__(
        self,
        kb_root: Path,
        redis_client=None  # RedisSessionStorage client
    ):
        """
        Initialize Session manager

        Args:
            kb_root: Knowledge base root directory
            redis_client: Redis client (optional, uses memory when None)
        """
        self.kb_root = kb_root
        self.redis_client = redis_client
        self._using_fallback = redis_client is None

        # Memory fallback storage
        self._memory_sessions: Dict[str, Session] = {}  # session_id -> Session
        self._memory_user_sessions: Dict[str, List[str]] = {}  # user_id -> [session_ids]

        logger.info(f"RoutingSessionManager initialized (fallback={self._using_fallback})")

    async def initialize(self) -> None:
        """Initialize storage backend"""
        if self.redis_client:
            try:
                # Test Redis connection
                await self.redis_client.ping()
                logger.info("✅ RoutingSessionManager Redis storage ready")
                self._using_fallback = False
            except Exception as e:
                logger.error(f"❌ Redis connection failed: {e}")
                logger.warning("⚠️  Falling back to memory storage")
                self._using_fallback = True
        else:
            logger.info("Using memory storage for RoutingSessionManager")
            self._using_fallback = True

    async def create_session(
        self,
        user_id: str,
        role: SessionRole,
        original_question: str,
        session_id: Optional[str] = None,
        related_user_id: Optional[str] = None,
        domain: Optional[str] = None
    ) -> Session:
        """
        Create new Session

        Args:
            user_id: WeChat Work (企业微信) userid
            role: User role
            original_question: Original question
            session_id: Session ID (optional, generates UUID by default)
            related_user_id: Related user ID (only for role=EXPERT)
            domain: Expert domain (only for role=EXPERT)

        Returns:
            Created Session object
        """
        if session_id is None:
            session_id = f"sess_{uuid.uuid4().hex[:16]}"

        # Calculate expiration time (ACTIVE defaults to 7 days)
        expires_at = datetime.now() + timedelta(days=7)

        session = Session(
            session_id=session_id,
            user_id=user_id,
            role=role,
            status=SessionStatus.ACTIVE,
            summary=SessionSummary(
                original_question=original_question,
                latest_exchange=None,
                key_points=[],
                last_updated=datetime.now(),
                version=0
            ),
            full_context_key=f"session_history:{session_id}",
            related_user_id=related_user_id,
            domain=domain,
            created_at=datetime.now(),
            last_active_at=datetime.now(),
            expires_at=expires_at,
            message_count=0,
            tags=[]
        )

        # Persist
        await self._save_session(session, ttl_seconds=7 * 86400)

        # Add to user Session set
        await self._add_to_user_sessions(user_id, session_id)

        logger.info(f"Created session {session_id} for user {user_id} (role={role.value})")
        return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get Session

        Args:
            session_id: Session ID

        Returns:
            Session object, None if not found
        """
        if self._using_fallback:
            return self._memory_sessions.get(session_id)

        try:
            session_json = await self.redis_client.get(f"session:{session_id}")
            if session_json:
                return Session.parse_raw(session_json)
            return None
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return self._memory_sessions.get(session_id)

    async def query_user_sessions(
        self,
        user_id: str,
        include_expired: bool = False,
        max_per_role: int = 10
    ) -> SessionQueryResult:
        """
        Query all user Sessions (in reverse chronological order)

        Args:
            user_id: WeChat Work (企业微信) userid
            include_expired: Whether to include expired Sessions
            max_per_role: Maximum number to return per role

        Returns:
            SessionQueryResult (both as_user and as_expert in reverse chronological order)
        """
        # Get all user session_ids
        session_ids = await self._get_user_session_ids(user_id)

        if not session_ids:
            return SessionQueryResult(
                user_id=user_id,
                as_user=[],
                as_expert=[],
                total_count=0
            )

        # Batch get Session objects
        sessions = []
        for sid in session_ids:
            session = await self.get_session(sid)
            if session:
                # Filter expired Sessions
                if not include_expired and session.status == SessionStatus.EXPIRED:
                    continue
                sessions.append(session)

        # Classify by role
        as_user = [s for s in sessions if s.role in [SessionRole.USER, SessionRole.EXPERT_AS_USER]]
        as_expert = [s for s in sessions if s.role == SessionRole.EXPERT]

        # Key: Sort by last_active_at in descending order (newest first)
        as_user.sort(key=lambda s: s.last_active_at, reverse=True)
        as_expert.sort(key=lambda s: s.last_active_at, reverse=True)

        # Limit quantity
        as_user = as_user[:max_per_role]
        as_expert = as_expert[:max_per_role]

        return SessionQueryResult(
            user_id=user_id,
            as_user=as_user,
            as_expert=as_expert,
            total_count=len(as_user) + len(as_expert)
        )

    async def update_session_summary(
        self,
        session_id: str,
        new_message: Optional[MessageSnapshot] = None,
        key_points: Optional[List[str]] = None,
        session_status: Optional[SessionStatus] = None,
        max_retries: int = 3
    ) -> bool:
        """
        Update Session summary (optimistic lock mechanism)

        Args:
            session_id: Session ID
            new_message: New message snapshot
            key_points: Key points extracted by Agent
            session_status: New status (optional)
            max_retries: Maximum retry attempts

        Returns:
            Whether update was successful
        """
        for attempt in range(max_retries):
            try:
                # 1. Read current Session (with version)
                session = await self.get_session(session_id)
                if not session:
                    logger.error(f"Session {session_id} not found")
                    return False

                current_version = session.summary.version

                # 2. Update summary
                if new_message:
                    session.summary.latest_exchange = new_message

                session.summary.last_updated = datetime.now()
                session.summary.version += 1

                # 3. Append key points (deduplicate, max 10)
                if key_points:
                    existing_points = set(session.summary.key_points)
                    for point in key_points:
                        if point not in existing_points:
                            session.summary.key_points.append(point)
                            if len(session.summary.key_points) > 10:
                                session.summary.key_points.pop(0)  # Remove oldest

                # 4. Update other fields
                session.last_active_at = datetime.now()
                session.message_count += 1

                if session_status:
                    session.status = session_status
                    # When transitioning to RESOLVED, set 24h TTL
                    if session_status == SessionStatus.RESOLVED:
                        await self._transition_to_resolved(session)
                        logger.info(f"Session {session_id} marked as RESOLVED (24h TTL)")
                        return True

                # 5. CAS update (Compare-And-Swap)
                success = await self._cas_update_session(session, current_version)

                if success:
                    logger.info(f"Session {session_id} summary updated (v{current_version} -> v{session.summary.version})")
                    return True
                else:
                    # Version conflict, retry
                    logger.warning(f"Session {session_id} version conflict (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(0.05 * (2 ** attempt))  # Exponential backoff
                    continue

            except Exception as e:
                logger.error(f"Error updating session {session_id}: {e}")
                if attempt == max_retries - 1:
                    return False
                await asyncio.sleep(0.1 * (2 ** attempt))

        logger.error(f"Failed to update session {session_id} after {max_retries} retries")
        return False

    async def append_message_to_history(
        self,
        session_id: str,
        message: Dict
    ) -> None:
        """
        Append message to full history (no concurrency conflicts, uses LPUSH)

        Args:
            session_id: Session ID
            message: Message dict {role, content, timestamp}
        """
        history_key = f"session_history:{session_id}"

        if self._using_fallback:
            # Memory mode does not implement full history yet
            return

        try:
            await self.redis_client.lpush(history_key, json.dumps(message, default=str))
            await self.redis_client.expire(history_key, 7 * 86400)  # 7 days expiry
        except Exception as e:
            logger.error(f"Failed to append message to history {session_id}: {e}")

    async def get_session_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get Session full history

        Args:
            session_id: Session ID
            limit: Maximum number of messages to return

        Returns:
            Message list
        """
        history_key = f"session_history:{session_id}"

        if self._using_fallback:
            return []

        try:
            messages = await self.redis_client.lrange(history_key, -limit, -1)
            return [json.loads(msg) for msg in messages]
        except Exception as e:
            logger.error(f"Failed to get session history {session_id}: {e}")
            return []

    # ==================== Internal helper methods ====================

    async def _save_session(self, session: Session, ttl_seconds: int) -> None:
        """Save Session to storage"""
        session_key = f"session:{session.session_id}"

        if self._using_fallback:
            self._memory_sessions[session.session_id] = session
            return

        try:
            await self.redis_client.setex(
                session_key,
                ttl_seconds,
                session.json()
            )
        except Exception as e:
            logger.error(f"Failed to save session {session.session_id}: {e}")
            self._memory_sessions[session.session_id] = session

    async def _add_to_user_sessions(self, user_id: str, session_id: str) -> None:
        """Add Session to user Session set"""
        if self._using_fallback:
            if user_id not in self._memory_user_sessions:
                self._memory_user_sessions[user_id] = []
            self._memory_user_sessions[user_id].append(session_id)
            return

        try:
            user_sessions_key = f"user_sessions:{user_id}"
            await self.redis_client.sadd(user_sessions_key, session_id)
            await self.redis_client.expire(user_sessions_key, 30 * 86400)  # 30 days
        except Exception as e:
            logger.error(f"Failed to add session to user {user_id}: {e}")

    async def _get_user_session_ids(self, user_id: str) -> List[str]:
        """Get all user session_ids"""
        if self._using_fallback:
            return self._memory_user_sessions.get(user_id, [])

        try:
            user_sessions_key = f"user_sessions:{user_id}"
            session_ids = await self.redis_client.smembers(user_sessions_key)
            return list(session_ids) if session_ids else []
        except Exception as e:
            logger.error(f"Failed to get user sessions for {user_id}: {e}")
            return []

    async def _cas_update_session(
        self,
        session: Session,
        expected_version: int
    ) -> bool:
        """
        CAS update Session (Compare-And-Swap)

        Args:
            session: Updated Session object
            expected_version: Expected version number

        Returns:
            Whether update was successful
        """
        if self._using_fallback:
            # Memory mode: direct update
            self._memory_sessions[session.session_id] = session
            return True

        try:
            # Lua script for CAS
            lua_script = """
            local key = KEYS[1]
            local expected_version = tonumber(ARGV[1])
            local new_value = ARGV[2]
            local ttl_seconds = tonumber(ARGV[3])

            local current = redis.call('GET', key)
            if not current then
                return 0  -- Session was deleted
            end

            local current_data = cjson.decode(current)
            local current_version = current_data.summary.version

            if current_version == expected_version then
                redis.call('SETEX', key, ttl_seconds, new_value)
                return 1  -- Success
            else
                return -1  -- Version conflict
            end
            """

            # Calculate TTL
            if session.status == SessionStatus.RESOLVED:
                ttl_seconds = 24 * 3600  # 24 hours
            else:
                ttl_seconds = 7 * 86400  # 7 days

            session_key = f"session:{session.session_id}"
            result = await self.redis_client.eval(
                lua_script,
                keys=[session_key],
                args=[expected_version, session.json(), ttl_seconds]
            )

            return result == 1

        except Exception as e:
            logger.error(f"CAS update failed for session {session.session_id}: {e}")
            return False

    async def _transition_to_resolved(self, session: Session) -> None:
        """
        Mark Session as resolved (set 24h TTL)

        Args:
            session: Session object
        """
        session.status = SessionStatus.RESOLVED
        session.last_active_at = datetime.now()

        await self._save_session(session, ttl_seconds=24 * 3600)


# Global singleton
_routing_session_manager: Optional[RoutingSessionManager] = None


def get_routing_session_manager(
    kb_root: Optional[Path] = None,
    redis_client=None
) -> RoutingSessionManager:
    """
    Get RoutingSessionManager singleton

    Args:
        kb_root: Knowledge base root directory
        redis_client: Redis client

    Returns:
        RoutingSessionManager instance
    """
    global _routing_session_manager

    if _routing_session_manager is None:
        from backend.config.settings import settings

        if kb_root is None:
            kb_root = Path(settings.KB_ROOT_PATH)

        _routing_session_manager = RoutingSessionManager(
            kb_root=kb_root,
            redis_client=redis_client
        )

    return _routing_session_manager


# Export
__all__ = [
    "RoutingSessionManager",
    "get_routing_session_manager"
]
