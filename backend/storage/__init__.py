"""
Storage Layer - 会话存储层
负责会话数据的持久化存储（Redis/PostgreSQL）
"""

from .base import SessionStorage, SessionRecord
from .redis_storage import RedisSessionStorage

__all__ = [
    "SessionStorage",
    "SessionRecord",
    "RedisSessionStorage",
]
