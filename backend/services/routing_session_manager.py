"""
Routing Session Manager - Session Router会话管理器

核心职责：
1. 管理Session生命周期（创建、查询、更新、过期）
2. Session摘要并发安全更新（乐观锁CAS机制）
3. 按时间倒序返回用户Sessions（支持Router语义判断）
4. 分状态TTL管理（ACTIVE 7天，RESOLVED 24h）

与现有session_manager.py的区别：
- session_manager.py：管理Claude SDK session（user_id → claude_session_id）
- routing_session_manager.py：管理语义会话路由（支持并发会话）
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
    路由Session管理器（支持Redis乐观锁和内存降级）

    Redis Key设计：
    - session:{session_id} -> Session JSON
    - user_sessions:{user_id} -> Set[session_id]
    - session_history:{session_id} -> List[Message JSON]

    架构说明：
    - 主存储：Redis（持久化、分布式）
    - 降级存储：内存（Redis故障时）
    """

    def __init__(
        self,
        kb_root: Path,
        redis_client=None  # RedisSessionStorage client
    ):
        """
        初始化Session管理器

        Args:
            kb_root: 知识库根目录
            redis_client: Redis客户端（可选，None时使用内存）
        """
        self.kb_root = kb_root
        self.redis_client = redis_client
        self._using_fallback = redis_client is None

        # 内存降级存储
        self._memory_sessions: Dict[str, Session] = {}  # session_id -> Session
        self._memory_user_sessions: Dict[str, List[str]] = {}  # user_id -> [session_ids]

        logger.info(f"RoutingSessionManager initialized (fallback={self._using_fallback})")

    async def initialize(self) -> None:
        """初始化存储后端"""
        if self.redis_client:
            try:
                # 测试Redis连接
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
        创建新Session

        Args:
            user_id: 企业微信userid
            role: 用户角色
            original_question: 原始问题
            session_id: Session ID（可选，默认生成UUID）
            related_user_id: 关联用户ID（仅role=EXPERT时）
            domain: 专业领域（仅role=EXPERT时）

        Returns:
            创建的Session对象
        """
        if session_id is None:
            session_id = f"sess_{uuid.uuid4().hex[:16]}"

        # 计算过期时间（ACTIVE默认7天）
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

        # 持久化
        await self._save_session(session, ttl_seconds=7 * 86400)

        # 添加到用户Session集合
        await self._add_to_user_sessions(user_id, session_id)

        logger.info(f"Created session {session_id} for user {user_id} (role={role.value})")
        return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        获取Session

        Args:
            session_id: Session ID

        Returns:
            Session对象，不存在返回None
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
        查询用户的所有Sessions（按时间倒序）

        Args:
            user_id: 企业微信userid
            include_expired: 是否包含过期Session
            max_per_role: 每种角色最多返回数量

        Returns:
            SessionQueryResult（as_user和as_expert都按时间倒序）
        """
        # 获取用户所有session_ids
        session_ids = await self._get_user_session_ids(user_id)

        if not session_ids:
            return SessionQueryResult(
                user_id=user_id,
                as_user=[],
                as_expert=[],
                total_count=0
            )

        # 批量获取Session对象
        sessions = []
        for sid in session_ids:
            session = await self.get_session(sid)
            if session:
                # 过滤过期Session
                if not include_expired and session.status == SessionStatus.EXPIRED:
                    continue
                sessions.append(session)

        # 按角色分类
        as_user = [s for s in sessions if s.role in [SessionRole.USER, SessionRole.EXPERT_AS_USER]]
        as_expert = [s for s in sessions if s.role == SessionRole.EXPERT]

        # 关键：按 last_active_at 倒序排序（最新的在前）
        as_user.sort(key=lambda s: s.last_active_at, reverse=True)
        as_expert.sort(key=lambda s: s.last_active_at, reverse=True)

        # 限制数量
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
        更新Session摘要（乐观锁机制）

        Args:
            session_id: Session ID
            new_message: 新消息快照
            key_points: Agent提取的关键点
            session_status: 新状态（可选）
            max_retries: 最大重试次数

        Returns:
            是否更新成功
        """
        for attempt in range(max_retries):
            try:
                # 1. 读取当前Session（带版本号）
                session = await self.get_session(session_id)
                if not session:
                    logger.error(f"Session {session_id} not found")
                    return False

                current_version = session.summary.version

                # 2. 更新摘要
                if new_message:
                    session.summary.latest_exchange = new_message

                session.summary.last_updated = datetime.now()
                session.summary.version += 1

                # 3. 追加关键点（去重，最多10个）
                if key_points:
                    existing_points = set(session.summary.key_points)
                    for point in key_points:
                        if point not in existing_points:
                            session.summary.key_points.append(point)
                            if len(session.summary.key_points) > 10:
                                session.summary.key_points.pop(0)  # 移除最旧的

                # 4. 更新其他字段
                session.last_active_at = datetime.now()
                session.message_count += 1

                if session_status:
                    session.status = session_status
                    # 状态变更到RESOLVED时，设置24小时TTL
                    if session_status == SessionStatus.RESOLVED:
                        await self._transition_to_resolved(session)
                        logger.info(f"Session {session_id} marked as RESOLVED (24h TTL)")
                        return True

                # 5. CAS更新（Compare-And-Swap）
                success = await self._cas_update_session(session, current_version)

                if success:
                    logger.info(f"Session {session_id} summary updated (v{current_version} -> v{session.summary.version})")
                    return True
                else:
                    # 版本冲突，重试
                    logger.warning(f"Session {session_id} version conflict (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(0.05 * (2 ** attempt))  # 指数退避
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
        追加消息到完整历史（无并发冲突，使用LPUSH）

        Args:
            session_id: Session ID
            message: 消息字典 {role, content, timestamp}
        """
        history_key = f"session_history:{session_id}"

        if self._using_fallback:
            # 内存模式暂不实现完整历史
            return

        try:
            await self.redis_client.lpush(history_key, json.dumps(message, default=str))
            await self.redis_client.expire(history_key, 7 * 86400)  # 7天过期
        except Exception as e:
            logger.error(f"Failed to append message to history {session_id}: {e}")

    async def get_session_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        获取Session完整历史

        Args:
            session_id: Session ID
            limit: 最多返回消息数

        Returns:
            消息列表
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

    # ==================== 内部辅助方法 ====================

    async def _save_session(self, session: Session, ttl_seconds: int) -> None:
        """保存Session到存储"""
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
        """添加Session到用户Session集合"""
        if self._using_fallback:
            if user_id not in self._memory_user_sessions:
                self._memory_user_sessions[user_id] = []
            self._memory_user_sessions[user_id].append(session_id)
            return

        try:
            user_sessions_key = f"user_sessions:{user_id}"
            await self.redis_client.sadd(user_sessions_key, session_id)
            await self.redis_client.expire(user_sessions_key, 30 * 86400)  # 30天
        except Exception as e:
            logger.error(f"Failed to add session to user {user_id}: {e}")

    async def _get_user_session_ids(self, user_id: str) -> List[str]:
        """获取用户所有session_ids"""
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
        CAS更新Session（Compare-And-Swap）

        Args:
            session: 更新后的Session对象
            expected_version: 期望的版本号

        Returns:
            是否更新成功
        """
        if self._using_fallback:
            # 内存模式：直接更新
            self._memory_sessions[session.session_id] = session
            return True

        try:
            # Lua脚本实现CAS
            lua_script = """
            local key = KEYS[1]
            local expected_version = tonumber(ARGV[1])
            local new_value = ARGV[2]
            local ttl_seconds = tonumber(ARGV[3])

            local current = redis.call('GET', key)
            if not current then
                return 0  -- Session已被删除
            end

            local current_data = cjson.decode(current)
            local current_version = current_data.summary.version

            if current_version == expected_version then
                redis.call('SETEX', key, ttl_seconds, new_value)
                return 1  -- 成功
            else
                return -1  -- 版本冲突
            end
            """

            # 计算TTL
            if session.status == SessionStatus.RESOLVED:
                ttl_seconds = 24 * 3600  # 24小时
            else:
                ttl_seconds = 7 * 86400  # 7天

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
        标记Session为已解决（设置24小时TTL）

        Args:
            session: Session对象
        """
        session.status = SessionStatus.RESOLVED
        session.last_active_at = datetime.now()

        await self._save_session(session, ttl_seconds=24 * 3600)


# 全局单例
_routing_session_manager: Optional[RoutingSessionManager] = None


def get_routing_session_manager(
    kb_root: Optional[Path] = None,
    redis_client=None
) -> RoutingSessionManager:
    """
    获取RoutingSessionManager单例

    Args:
        kb_root: 知识库根目录
        redis_client: Redis客户端

    Returns:
        RoutingSessionManager实例
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


# 导出
__all__ = [
    "RoutingSessionManager",
    "get_routing_session_manager"
]
