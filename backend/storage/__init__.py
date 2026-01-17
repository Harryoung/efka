"""
Storage Layer - Session Storage Layer
Responsible for persistent storage of session data (Redis/PostgreSQL)
"""

from .base import SessionStorage, SessionRecord
from .redis_storage import RedisSessionStorage

__all__ = [
    "SessionStorage",
    "SessionRecord",
    "RedisSessionStorage",
]
