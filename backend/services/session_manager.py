"""
Session Manager - 会话管理器（改造版）
负责管理用户会话、超时控制和权限关联
支持 Redis 持久化和内存降级
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
    会话数据类（向后兼容）

    Attributes:
        session_id: 会话唯一标识
        user_id: 用户ID（可选，用于权限管理）
        created_at: 创建时间戳
        last_active: 最后活跃时间戳
        metadata: 会话元数据（存储额外信息）
    """
    session_id: str
    user_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)

    def is_expired(self, timeout: int) -> bool:
        """
        检查会话是否过期

        Args:
            timeout: 超时时间（秒）

        Returns:
            是否过期
        """
        return (time.time() - self.last_active) > timeout

    def update_activity(self):
        """更新最后活跃时间"""
        self.last_active = time.time()

    def get_age(self) -> float:
        """
        获取会话年龄（秒）

        Returns:
            从创建到现在的秒数
        """
        return time.time() - self.created_at

    def to_dict(self) -> dict:
        """
        转换为字典

        Returns:
            会话信息字典
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
    会话管理器（改造版）

    职责：
    1. 创建和删除会话（原有功能，向后兼容）
    2. 会话超时检测和清理
    3. 会话信息查询
    4. 用户权限关联（预留接口）
    5. 基于 user_id 的会话持久化（新功能）
    6. Redis 降级逻辑（新功能）
    """

    def __init__(self, storage: Optional[SessionStorage] = None):
        """
        初始化会话管理器

        Args:
            storage: 会话存储后端（可选，默认使用内存）
        """
        self.settings = get_settings()
        self.storage = storage

        # 原有的内存会话存储（session_id -> Session）
        self.sessions: Dict[str, Session] = {}

        # 新增：用户会话内存缓存（user_id -> claude_session_id）
        # 用于 Redis 降级场景
        self._user_sessions_memory: Dict[str, SessionRecord] = {}

        # 降级标志
        self._using_fallback = False

        self.cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_running = False

        logger.info("会话管理器已初始化（支持 Redis 持久化）")

    async def initialize_storage(self) -> None:
        """初始化存储后端"""
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
        """启动会话清理任务（后台运行）"""
        if self._cleanup_running:
            logger.warning("清理任务已在运行")
            return

        self._cleanup_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("会话清理任务已启动")

    async def stop_cleanup_task(self):
        """停止会话清理任务"""
        if self.cleanup_task:
            self._cleanup_running = False
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("会话清理任务已停止")

    async def _cleanup_loop(self):
        """会话清理循环（每分钟检查一次）"""
        while self._cleanup_running:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"会话清理失败: {e}")

    async def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话

        Returns:
            清理的会话数量
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

    # ===== 原有方法（向后兼容）=====

    def create_session(
        self,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Session:
        """
        创建新会话

        Args:
            user_id: 用户ID（可选）
            metadata: 会话元数据（可选）

        Returns:
            新创建的会话对象
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
        删除会话

        Args:
            session_id: 会话ID

        Returns:
            是否成功删除
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
        获取会话

        Args:
            session_id: 会话ID

        Returns:
            会话对象，如果不存在返回 None
        """
        session = self.sessions.get(session_id)

        if session:
            # 更新活跃时间
            session.update_activity()

        return session

    def get_all_sessions(self) -> Dict[str, Session]:
        """
        获取所有会话

        Returns:
            会话字典
        """
        return self.sessions.copy()

    def get_session_count(self) -> int:
        """
        获取当前会话数量

        Returns:
            会话总数
        """
        return len(self.sessions)

    def get_user_sessions(self, user_id: str) -> Dict[str, Session]:
        """
        获取指定用户的所有会话

        Args:
            user_id: 用户ID

        Returns:
            该用户的会话字典
        """
        return {
            sid: session
            for sid, session in self.sessions.items()
            if session.user_id == user_id
        }

    def session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在

        Args:
            session_id: 会话ID

        Returns:
            是否存在
        """
        return session_id in self.sessions

    def update_session_metadata(
        self,
        session_id: str,
        metadata: Dict
    ) -> bool:
        """
        更新会话元数据

        Args:
            session_id: 会话ID
            metadata: 新的元数据（会合并到现有元数据）

        Returns:
            是否成功更新
        """
        session = self.get_session(session_id)
        if session:
            session.metadata.update(metadata)
            logger.info(f"更新会话元数据: {session_id}")
            return True
        return False

    def get_statistics(self) -> dict:
        """
        获取会话统计信息

        Returns:
            统计信息字典
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

    # ===== 新方法（基于 user_id 的持久化）=====

    async def get_or_create_user_session(self, user_id: str) -> str:
        """
        获取或创建用户的 Claude session ID

        Args:
            user_id: 用户标识

        Returns:
            claude_session_id: 传递给 Claude SDK 的 session_id
        """
        # 尝试从 Redis/存储后端获取
        if self.storage and not self._using_fallback:
            try:
                session = await self.storage.get_active_session(user_id)

                if session is None:
                    # 创建新会话
                    session = SessionRecord(
                        user_id=user_id,
                        claude_session_id=str(uuid.uuid4())
                    )
                    await self.storage.save_active_session(session)
                    logger.info(f"为用户 {user_id} 创建新会话: {session.claude_session_id}")
                else:
                    logger.info(f"用户 {user_id} 复用已有会话: {session.claude_session_id}")

                return session.claude_session_id

            except (RedisError, RedisConnectionError, RuntimeError) as e:
                logger.error(f"Redis 操作失败: {e}，降级到内存存储")
                self._using_fallback = True

        # 降级到内存存储
        if user_id in self._user_sessions_memory:
            session = self._user_sessions_memory[user_id]
            logger.info(f"[内存] 用户 {user_id} 复用会话: {session.claude_session_id}")
        else:
            session = SessionRecord(
                user_id=user_id,
                claude_session_id=str(uuid.uuid4())
            )
            self._user_sessions_memory[user_id] = session
            logger.info(f"[内存] 为用户 {user_id} 创建新会话: {session.claude_session_id}")

        return session.claude_session_id

    async def update_session_activity(
        self,
        user_id: str,
        turn_count: Optional[int] = None
    ) -> None:
        """
        更新会话活跃度

        Args:
            user_id: 用户标识
            turn_count: 对话轮次（可选）
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

        # 降级到内存
        if user_id in self._user_sessions_memory:
            session = self._user_sessions_memory[user_id]
            session.last_active = datetime.now()
            if turn_count is not None:
                session.turn_count = turn_count
            logger.debug(f"[内存] 更新用户 {user_id} 会话活跃度")

    async def clear_user_context(self, user_id: str) -> str:
        """
        清空用户上下文（归档旧会话，创建新会话）

        Args:
            user_id: 用户标识

        Returns:
            新的 claude_session_id
        """
        if self.storage and not self._using_fallback:
            try:
                # 归档旧会话（暂不实现 PostgreSQL 归档）
                old_session = await self.storage.get_active_session(user_id)
                if old_session:
                    await self.storage.delete_active_session(user_id)
                    logger.info(f"用户 {user_id} 归档旧会话: {old_session.claude_session_id}")

                # 创建新会话
                new_session = SessionRecord(
                    user_id=user_id,
                    claude_session_id=str(uuid.uuid4())
                )
                await self.storage.save_active_session(new_session)
                logger.info(f"用户 {user_id} 创建新会话: {new_session.claude_session_id}")

                return new_session.claude_session_id

            except (RedisError, RedisConnectionError, RuntimeError) as e:
                logger.error(f"Redis 操作失败: {e}，降级到内存存储")
                self._using_fallback = True

        # 降级到内存
        old_session = self._user_sessions_memory.get(user_id)
        if old_session:
            logger.info(f"[内存] 用户 {user_id} 归档旧会话: {old_session.claude_session_id}")

        new_session = SessionRecord(
            user_id=user_id,
            claude_session_id=str(uuid.uuid4())
        )
        self._user_sessions_memory[user_id] = new_session
        logger.info(f"[内存] 用户 {user_id} 创建新会话: {new_session.claude_session_id}")

        return new_session.claude_session_id

    async def __aenter__(self):
        """支持 async with 语法"""
        await self.start_cleanup_task()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """支持 async with 语法"""
        await self.stop_cleanup_task()
        if self.storage:
            await self.storage.close()


# 单例实例
_session_manager_instance: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """
    获取会话管理器单例

    Returns:
        SessionManager 实例
    """
    global _session_manager_instance
    if _session_manager_instance is None:
        _session_manager_instance = SessionManager()
    return _session_manager_instance


# 导出
__all__ = [
    "Session",
    "SessionManager",
    "get_session_manager"
]
