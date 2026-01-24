"""
Claude SDK Client Connection Pool

Design principles:
1. Use semaphore to control concurrency (not pre-create clients)
2. Connect/disconnect in the same task for each request
3. Support resume user session via resume parameter
4. Support true concurrency, each request gets exclusive use of a Client

Important: ClaudeSDKClient uses anyio TaskGroup, must complete
          connect/disconnect in the same asyncio task. Therefore cannot pre-create client pool.

Usage:
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
    Claude SDK Client Connection Pool

    Key features:
    - Use semaphore to control concurrency
    - Create new client for each request (avoid cross-task issues)
    - Dynamically resume user session via resume parameter
    - Support concurrency, each request gets exclusive use of a Client
    """

    def __init__(
        self,
        pool_size: int,
        options_factory: Callable[[Optional[str]], ClaudeAgentOptions],
        max_wait_time: float = 30.0
    ):
        """
        Initialize connection pool

        Args:
            pool_size: Maximum concurrent client count
            options_factory: Factory function to create ClaudeAgentOptions
                            (parameter: session_id or None)
            max_wait_time: Maximum wait time to acquire client (seconds)
        """
        self.pool_size = pool_size
        self.options_factory = options_factory
        self.max_wait_time = max_wait_time

        # Use semaphore to control concurrency
        self._semaphore = asyncio.Semaphore(pool_size)

        # Statistics
        self._active_count = 0
        self._total_requests = 0
        self._lock = asyncio.Lock()

        # Is pool initialized
        self.is_initialized = True  # Using semaphore, no initialization needed

        logger.info(f"SDKClientPool created (max_concurrency={pool_size})")

    async def initialize(self):
        """Initialize connection pool (using semaphore approach, no need to pre-create clients)"""
        logger.info(f"SDKClientPool ready (max_concurrency={self.pool_size})")
        self.is_initialized = True

    async def shutdown(self):
        """Shutdown connection pool"""
        logger.info("SDKClientPool shutdown complete")
        self.is_initialized = False

    @asynccontextmanager
    async def acquire(self, session_id: Optional[str] = None):
        """
        Acquire client (context manager)

        Complete connect and disconnect in the same task,
        avoiding anyio TaskGroup cross-task issues.

        Args:
            session_id: Session ID to resume (optional)
        """
        # Wait for semaphore (with timeout)
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
        disconnected = False
        try:
            # Create and connect client in current task
            options = self.options_factory(session_id)
            client = ClaudeSDKClient(options=options)
            try:
                await client.connect()
            except Exception as e:
                if session_id is None:
                    raise

                logger.warning(
                    "Client connect failed when resuming session %s; retrying without resume. Error: %s",
                    session_id,
                    str(e)
                )
                try:
                    await client.disconnect()
                    disconnected = True
                except Exception:
                    pass

                options = self.options_factory(None)
                client = ClaudeSDKClient(options=options)
                await client.connect()

            logger.debug(f"Client connected (session={session_id or 'new'}, active={self._active_count})")

            yield client

        except asyncio.CancelledError:
            # Explicitly catch cancellation, ensure cleanup before re-raising
            logger.warning(f"Client operation cancelled (session={session_id or 'new'})")
            if client:
                try:
                    await client.disconnect()
                    disconnected = True
                except Exception as e:
                    logger.warning("Error disconnecting client after cancellation: %s", e)
            raise
        finally:
            # Disconnect in the same task
            if client and not disconnected:
                try:
                    await client.disconnect()
                    logger.debug(f"Client disconnected (session={session_id or 'new'})")
                except Exception as e:
                    logger.warning("Error disconnecting client: %s", e)

            # Release semaphore (must execute)
            self._semaphore.release()
            logger.debug(f"Semaphore released (session={session_id or 'new'})")

            async with self._lock:
                self._active_count -= 1

    def get_stats(self) -> dict:
        """Get connection pool statistics"""
        return {
            "max_concurrency": self.pool_size,
            "active_clients": self._active_count,
            "available_slots": self.pool_size - self._active_count,
            "total_requests": self._total_requests,
            "is_initialized": self.is_initialized
        }


# Singleton manager
class PoolManager:
    """Connection pool manager (singleton)"""

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
        """Register a connection pool"""
        if name in cls._pools:
            logger.warning(f"Pool '{name}' already registered")
            return cls._pools[name]

        pool = SDKClientPool(pool_size, options_factory, max_wait_time)
        cls._pools[name] = pool
        logger.info(f"Registered pool '{name}' (max_concurrency={pool_size})")
        return pool

    @classmethod
    def get_pool(cls, name: str) -> Optional[SDKClientPool]:
        """Get connection pool"""
        return cls._pools.get(name)

    @classmethod
    async def initialize_all(cls):
        """Initialize all connection pools"""
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
        """Shutdown all connection pools"""
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
        """Get all connection pool statistics"""
        return {name: pool.get_stats() for name, pool in cls._pools.items()}


# Convenience function
def get_pool_manager() -> PoolManager:
    """Get connection pool manager singleton"""
    return PoolManager()
