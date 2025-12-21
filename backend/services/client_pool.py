"""
Claude SDK 客户端连接池

设计原则：
1. 使用信号量控制并发数量（而非预创建客户端）
2. 每次请求时在同一个 task 中 connect/disconnect
3. 支持通过 resume 参数恢复用户 session
4. 支持真正并发，每个请求独占一个 Client

重要：ClaudeSDKClient 使用 anyio TaskGroup，必须在同一个 asyncio task 中
     完成 connect/disconnect。因此不能预先创建客户端池。

使用方式：
    async with pool.acquire(session_id=user_session_id) as client:
        await client.query(...)
"""

import asyncio
import logging
from typing import Optional, Callable
from contextlib import asynccontextmanager

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

logger = logging.getLogger(__name__)


class SDKClientPool:
    """
    Claude SDK 客户端连接池

    关键特性：
    - 使用信号量控制并发数量
    - 每次请求时创建新客户端（避免跨 task 问题）
    - 通过 resume 参数动态恢复用户 session
    - 支持并发，每个请求独占一个 Client
    """

    def __init__(
        self,
        pool_size: int,
        options_factory: Callable[[Optional[str]], ClaudeAgentOptions],
        max_wait_time: float = 30.0
    ):
        """
        初始化连接池

        Args:
            pool_size: 最大并发客户端数量
            options_factory: 创建 ClaudeAgentOptions 的工厂函数
                            (参数: session_id 或 None)
            max_wait_time: 获取客户端最大等待时间（秒）
        """
        self.pool_size = pool_size
        self.options_factory = options_factory
        self.max_wait_time = max_wait_time

        # 使用信号量控制并发
        self._semaphore = asyncio.Semaphore(pool_size)

        # 统计信息
        self._active_count = 0
        self._total_requests = 0
        self._lock = asyncio.Lock()

        # 池是否已初始化
        self.is_initialized = True  # 使用信号量，无需初始化

        logger.info(f"SDKClientPool created (max_concurrency={pool_size})")

    async def initialize(self):
        """初始化连接池（使用信号量方案，无需预创建客户端）"""
        logger.info(f"SDKClientPool ready (max_concurrency={self.pool_size})")
        self.is_initialized = True

    async def shutdown(self):
        """关闭连接池"""
        logger.info("SDKClientPool shutdown complete")
        self.is_initialized = False

    @asynccontextmanager
    async def acquire(self, session_id: Optional[str] = None):
        """
        获取客户端（上下文管理器）

        在同一个 task 中完成 connect 和 disconnect，
        避免 anyio TaskGroup 跨 task 问题。

        Args:
            session_id: 要恢复的 session ID（可选）
        """
        # 等待信号量（带超时）
        try:
            acquired = await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.max_wait_time
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for available client slot (waited {self.max_wait_time}s)")
            raise

        async with self._lock:
            self._active_count += 1
            self._total_requests += 1

        client = None
        try:
            # 在当前 task 中创建并连接客户端
            options = self.options_factory(session_id)
            client = ClaudeSDKClient(options=options)
            await client.connect()

            logger.debug(f"Client connected (session={session_id or 'new'}, active={self._active_count})")

            yield client

        except asyncio.CancelledError:
            # 显式捕获取消，确保清理后重新抛出
            logger.warning(f"Client operation cancelled (session={session_id or 'new'})")
            raise
        finally:
            # 在同一个 task 中断开连接
            if client:
                try:
                    # 使用 shield 保护 disconnect 不被取消
                    await asyncio.shield(client.disconnect())
                    logger.debug(f"Client disconnected (session={session_id or 'new'})")
                except asyncio.CancelledError:
                    # shield 中的取消会变成 CancelledError，忽略它
                    logger.warning(f"Client disconnect interrupted but resources released (session={session_id or 'new'})")
                except Exception as e:
                    logger.warning(f"Error disconnecting client: {e}")

            # 释放信号量（必须执行）
            self._semaphore.release()
            logger.debug(f"Semaphore released (session={session_id or 'new'})")

            async with self._lock:
                self._active_count -= 1

    def get_stats(self) -> dict:
        """获取连接池统计信息"""
        return {
            "max_concurrency": self.pool_size,
            "active_clients": self._active_count,
            "available_slots": self.pool_size - self._active_count,
            "total_requests": self._total_requests,
            "is_initialized": self.is_initialized
        }


# 单例管理器
class PoolManager:
    """连接池管理器（单例）"""

    _instance = None
    _pools = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register_pool(
        cls,
        name: str,
        pool_size: int,
        options_factory: Callable[[Optional[str]], ClaudeAgentOptions],
        max_wait_time: float = 30.0
    ) -> SDKClientPool:
        """注册一个连接池"""
        if name in cls._pools:
            logger.warning(f"Pool '{name}' already registered")
            return cls._pools[name]

        pool = SDKClientPool(pool_size, options_factory, max_wait_time)
        cls._pools[name] = pool
        logger.info(f"Registered pool '{name}' (max_concurrency={pool_size})")
        return pool

    @classmethod
    def get_pool(cls, name: str) -> Optional[SDKClientPool]:
        """获取连接池"""
        return cls._pools.get(name)

    @classmethod
    async def initialize_all(cls):
        """初始化所有连接池"""
        logger.info(f"Initializing {len(cls._pools)} pools...")
        for name, pool in cls._pools.items():
            try:
                await pool.initialize()
                logger.info(f"✅ Pool '{name}' initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize pool '{name}': {e}")
                raise

    @classmethod
    async def shutdown_all(cls):
        """关闭所有连接池"""
        logger.info(f"Shutting down {len(cls._pools)} pools...")
        for name, pool in cls._pools.items():
            try:
                await pool.shutdown()
                logger.info(f"✅ Pool '{name}' shutdown")
            except Exception as e:
                logger.warning(f"Error shutting down pool '{name}': {e}")

        cls._pools.clear()

    @classmethod
    def get_all_stats(cls) -> dict:
        """获取所有连接池统计信息"""
        return {name: pool.get_stats() for name, pool in cls._pools.items()}


# 便捷函数
def get_pool_manager() -> PoolManager:
    """获取连接池管理器单例"""
    return PoolManager()
