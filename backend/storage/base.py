"""
Storage Base - 存储层抽象接口
定义会话存储的统一接口，支持多种存储后端（Redis、PostgreSQL 等）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict


@dataclass
class SessionRecord:
    """
    会话记录数据结构

    表示 user_id → claude_session_id 的映射关系
    """
    user_id: str                                      # 用户唯一标识
    claude_session_id: str                            # Claude SDK 的 session_id
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    turn_count: int = 0                               # 对话轮次
    metadata: Dict = field(default_factory=dict)      # 扩展信息

    def is_expired(self, ttl_seconds: int = 7 * 86400) -> bool:
        """
        检查会话是否过期

        Args:
            ttl_seconds: 超时时间（秒），默认 7 天

        Returns:
            是否过期
        """
        return (datetime.now() - self.last_active).total_seconds() > ttl_seconds

    def to_dict(self) -> dict:
        """
        转换为字典（用于序列化）

        Returns:
            会话信息字典
        """
        return {
            "user_id": self.user_id,
            "claude_session_id": self.claude_session_id,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "turn_count": self.turn_count,
            "metadata": self.metadata
        }


class SessionStorage(ABC):
    """
    会话存储抽象接口

    定义统一的存储接口，支持多种后端实现：
    - RedisSessionStorage: 基于 Redis 的高性能存储
    - PostgreSQLSessionStorage: 基于 PostgreSQL 的持久化存储
    - MemorySessionStorage: 基于内存的临时存储（降级方案）
    """

    @abstractmethod
    async def get_active_session(self, user_id: str) -> Optional[SessionRecord]:
        """
        获取用户的活跃会话

        Args:
            user_id: 用户标识

        Returns:
            会话记录，如果不存在返回 None
        """
        pass

    @abstractmethod
    async def save_active_session(self, session: SessionRecord) -> None:
        """
        保存活跃会话

        Args:
            session: 会话记录
        """
        pass

    @abstractmethod
    async def delete_active_session(self, user_id: str) -> bool:
        """
        删除活跃会话

        Args:
            user_id: 用户标识

        Returns:
            是否成功删除
        """
        pass

    @abstractmethod
    async def get_all_active_sessions(self) -> Dict[str, SessionRecord]:
        """
        获取所有活跃会话

        Returns:
            user_id -> SessionRecord 的映射
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        健康检查

        Returns:
            存储后端是否健康
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        关闭存储连接
        """
        pass
