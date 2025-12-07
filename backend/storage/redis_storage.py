"""
Redis Storage - 基于 Redis 的会话存储实现
支持高性能的会话数据持久化和自动过期
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
    基于 Redis 的会话存储

    特性：
    - 高性能内存存储
    - 自动过期（TTL）
    - 支持分布式部署
    - 连接池管理
    """

    def __init__(
        self,
        redis_url: str = "redis://127.0.0.1:6379/0",
        ttl_seconds: int = 7 * 86400,  # 7 天
        key_prefix: str = "kb_session:",
        max_connections: int = 10,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        初始化 Redis 存储

        Args:
            redis_url: Redis 连接 URL
            ttl_seconds: 会话过期时间（秒）
            key_prefix: Redis key 前缀
            max_connections: 最大连接数
            username: Redis ACL 用户名（可选）
            password: Redis 密码（可选）
        """
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix
        self.max_connections = max_connections
        self.username = username
        self.password = password
        self.redis: Optional[aioredis.Redis] = None
        self._connected = False

        auth_status = "启用" if password else "未启用"
        logger.info(
            "初始化 RedisSessionStorage: %s, TTL=%ss, 认证%s",
            redis_url,
            ttl_seconds,
            auth_status
        )

    async def connect(self) -> None:
        """建立 Redis 连接"""
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
            # 测试连接
            await self.redis.ping()
            self._connected = True
            logger.info("✅ Redis 连接成功")
        except RedisConnectionError as e:
            logger.error(f"❌ Redis 连接失败: {e}")
            self._connected = False
            raise
        except Exception as e:
            logger.error(f"❌ Redis 初始化失败: {e}")
            self._connected = False
            raise

    def _make_key(self, user_id: str) -> str:
        """
        生成 Redis key

        Args:
            user_id: 用户 ID

        Returns:
            完整的 Redis key
        """
        return f"{self.key_prefix}{user_id}"

    async def get_active_session(self, user_id: str) -> Optional[SessionRecord]:
        """
        获取用户的活跃会话

        Args:
            user_id: 用户标识

        Returns:
            会话记录，如果不存在返回 None
        """
        if not self._connected or not self.redis:
            raise RuntimeError("Redis 未连接")

        try:
            key = self._make_key(user_id)
            data = await self.redis.hgetall(key)

            if not data:
                logger.debug(f"用户 {user_id} 没有活跃会话")
                return None

            # 反序列化（兼容旧数据格式）
            # 新格式: internal_session_id + sdk_session_id
            # 旧格式: claude_session_id
            internal_id = data.get("internal_session_id") or data.get("claude_session_id")
            sdk_id = data.get("sdk_session_id")  # 可能为 None 或空字符串

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
                f"从 Redis 加载会话: {user_id} -> internal={session.internal_session_id}, "
                f"sdk={session.sdk_session_id or 'None'}"
            )
            return session

        except RedisError as e:
            logger.error(f"Redis 读取失败: {e}")
            raise
        except Exception as e:
            logger.error(f"会话反序列化失败: {e}")
            raise

    async def save_active_session(self, session: SessionRecord) -> None:
        """
        保存活跃会话

        Args:
            session: 会话记录
        """
        if not self._connected or not self.redis:
            raise RuntimeError("Redis 未连接")

        try:
            key = self._make_key(session.user_id)

            # 序列化（新格式）
            data = {
                "internal_session_id": session.internal_session_id,
                "sdk_session_id": session.sdk_session_id or "",  # Redis 不支持 None
                "created_at": session.created_at.isoformat(),
                "last_active": session.last_active.isoformat(),
                "turn_count": str(session.turn_count),
                "metadata": json.dumps(session.metadata, ensure_ascii=False)
            }

            # 使用 pipeline 优化性能
            async with self.redis.pipeline() as pipe:
                # 保存数据
                await pipe.hset(key, mapping=data)
                # 设置过期时间
                await pipe.expire(key, self.ttl_seconds)
                await pipe.execute()

            logger.debug(
                f"保存会话到 Redis: {session.user_id} -> internal={session.internal_session_id}, "
                f"sdk={session.sdk_session_id or 'None'}, TTL={self.ttl_seconds}s"
            )

        except RedisError as e:
            logger.error(f"Redis 写入失败: {e}")
            raise
        except Exception as e:
            logger.error(f"会话序列化失败: {e}")
            raise

    async def delete_active_session(self, user_id: str) -> bool:
        """
        删除活跃会话

        Args:
            user_id: 用户标识

        Returns:
            是否成功删除
        """
        if not self._connected or not self.redis:
            raise RuntimeError("Redis 未连接")

        try:
            key = self._make_key(user_id)
            result = await self.redis.delete(key)

            if result > 0:
                logger.debug(f"删除 Redis 会话: {user_id}")
                return True
            else:
                logger.debug(f"会话不存在: {user_id}")
                return False

        except RedisError as e:
            logger.error(f"Redis 删除失败: {e}")
            raise

    async def get_all_active_sessions(self) -> Dict[str, SessionRecord]:
        """
        获取所有活跃会话

        Returns:
            user_id -> SessionRecord 的映射
        """
        if not self._connected or not self.redis:
            raise RuntimeError("Redis 未连接")

        try:
            # 使用 SCAN 遍历所有 key（避免 KEYS 阻塞）
            sessions = {}
            pattern = f"{self.key_prefix}*"

            async for key in self.redis.scan_iter(match=pattern, count=100):
                # 提取 user_id
                user_id = key[len(self.key_prefix):]
                session = await self.get_active_session(user_id)
                if session:
                    sessions[user_id] = session

            logger.debug(f"加载了 {len(sessions)} 个活跃会话")
            return sessions

        except RedisError as e:
            logger.error(f"Redis 扫描失败: {e}")
            raise

    async def health_check(self) -> bool:
        """
        健康检查

        Returns:
            Redis 是否健康
        """
        try:
            if not self.redis:
                return False
            await self.redis.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis 健康检查失败: {e}")
            return False

    async def close(self) -> None:
        """关闭 Redis 连接"""
        if self.redis:
            await self.redis.close()
            self._connected = False
            logger.info("Redis 连接已关闭")

    async def __aenter__(self):
        """支持 async with 语法"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """支持 async with 语法"""
        await self.close()
