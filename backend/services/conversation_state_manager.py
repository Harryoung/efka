"""
Conversation State Manager - Conversation State Manager

Manages state persistence for employee-expert asynchronous multi-turn conversations
Supports Redis storage and memory fallback
"""

import asyncio
import logging
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path

from backend.models.conversation_state import ConversationState, ConversationContext
from backend.storage.base import SessionStorage
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class ConversationStateManager:
    """
    Conversation State Manager

    Responsibilities:
    1. Manage state while waiting for expert reply after employee question
    2. Check if an expert has pending questions to reply
    3. Update conversation state(IDLE → WAITING_FOR_EXPERT → COMPLETED)
    4. 支持 Redis 持久化和内存降级

    Architecture notes:
    - 状态存储在 Redis key: wework:conv_state:{userid}
    - 24小时TTL自动清理已完成的会话
    - Redis 故障时降级到内存存储
    """

    def __init__(
        self,
        kb_root: Path,
        storage: Optional[SessionStorage] = None
    ):
        """
        初始化Conversation State Manager

        Args:
            kb_root: Knowledge base root directory
            storage: Session storage backend (Redis or memory)
        """
        self.kb_root = kb_root
        self.storage = storage

        # Memory fallback storage (userid -> ConversationContext)
        self._memory_state: Dict[str, ConversationContext] = {}
        self._using_fallback = False

        logger.info("ConversationStateManager initialized")

    async def initialize_storage(self) -> None:
        """Initialize storage backend"""
        if self.storage:
            try:
                await self.storage.connect()
                logger.info("✅ Conversation state storage initialized (Redis)")
                self._using_fallback = False
            except Exception as e:
                logger.error(f"❌ Failed to initialize conversation state storage: {e}")
                logger.warning("⚠️  Falling back to memory storage")
                self._using_fallback = True
        else:
            logger.info("Using memory storage for conversation state")
            self._using_fallback = True

    async def get_conversation_context(
        self,
        user_id: str
    ) -> ConversationContext:
        """
        Get user conversation context

        Args:
            user_id: User WeChat Work UserID

        Returns:
            ConversationContext 对象

        If not exists, return new IDLE state context
        """
        redis_key = f"wework:conv_state:{user_id}"

        # Try to read from Redis
        if not self._using_fallback and self.storage:
            try:
                data = await self.storage.client.get(redis_key)
                if data:
                    context = ConversationContext.from_json(data)
                    logger.debug(f"Loaded context for {user_id} from Redis: {context.state.value}")
                    return context
            except RedisError as e:
                logger.warning(f"Redis error loading context for {user_id}: {e}, using fallback")
                self._using_fallback = True

        # Redis 失败或不存在,检查内存
        if user_id in self._memory_state:
            logger.debug(f"Loaded context for {user_id} from memory")
            return self._memory_state[user_id]

        # Create new IDLE context
        new_context = ConversationContext(
            session_id="",
            state=ConversationState.IDLE,
            user_id=user_id,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        logger.info(f"Created new IDLE context for {user_id}")
        return new_context

    async def update_state(
        self,
        user_id: str,
        **kwargs
    ) -> None:
        """
        Update conversation state

        Args:
            user_id: 用户 UserID
            **kwargs: Fields to update (state, user_question, domain, expert_userid, etc.)

        Example:
            await state_mgr.update_state(
                user_id='zhangsan',
                state=ConversationState.WAITING_FOR_EXPERT,
                user_question='如何调整薪资?',
                domain='薪酬福利',
                expert_userid='wangwu',
                expert_name='王五',
                contacted_at=datetime.now()
            )
        """
        # Get existing context
        context = await self.get_conversation_context(user_id)

        # Update fields
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)

        context.updated_at = datetime.now()

        # Persist to Redis
        redis_key = f"wework:conv_state:{user_id}"
        ttl = 86400  # 24 hours

        if not self._using_fallback and self.storage:
            try:
                await self.storage.client.setex(
                    redis_key,
                    ttl,
                    context.to_json()
                )
                logger.info(
                    f"Updated context for {user_id} in Redis: "
                    f"state={context.state.value}"
                )
            except RedisError as e:
                logger.warning(f"Redis error updating context for {user_id}: {e}")
                self._using_fallback = True

        # Update memory simultaneously (降级或缓存)
        self._memory_state[user_id] = context
        logger.debug(f"Updated context for {user_id} in memory")

    async def check_pending_expert_reply(
        self,
        expert_userid: str
    ) -> Optional[ConversationContext]:
        """
        Check if an expert has pending questions to reply

        Traverse all .* state sessions,
        匹配 expert_userid

        Args:
            expert_userid: 专家 UserID

        Returns:
            If there are pending replies,返回对应的 ConversationContext,否则返回 None

        Example:
            pending = await state_mgr.check_pending_expert_reply('wangwu')
            if pending:
                # 专家 wangwu 有待回复的问题
                inquirer_id = pending.user_id
                question = pending.user_question
        """
        # 如果使用 Redis,扫描所有 wework:conv_state:* keys
        if not self._using_fallback and self.storage:
            try:
                pattern = "wework:conv_state:*"
                cursor = "0"

                while True:
                    cursor, keys = await self.storage.client.scan(
                        cursor=int(cursor),
                        match=pattern,
                        count=100
                    )

                    for key in keys:
                        data = await self.storage.client.get(key)
                        if data:
                            context = ConversationContext.from_json(data)

                            # 检查是否匹配
                            if (context.state == ConversationState.WAITING_FOR_EXPERT and
                                context.expert_userid == expert_userid):
                                logger.info(
                                    f"Found pending reply for expert {expert_userid}: "
                                    f"user={context.user_id}"
                                )
                                return context

                    # 游标为 0 表示扫描完成
                    if cursor == 0 or cursor == "0":
                        break

            except RedisError as e:
                logger.warning(f"Redis error scanning for pending replies: {e}")
                self._using_fallback = True

        # 降级到内存搜索
        for context in self._memory_state.values():
            if (context.state == ConversationState.WAITING_FOR_EXPERT and
                context.expert_userid == expert_userid):
                logger.info(
                    f"Found pending reply in memory for expert {expert_userid}: "
                    f"user={context.user_id}"
                )
                return context

        logger.debug(f"No pending replies found for expert {expert_userid}")
        return None

    async def get_all_pending_expert_replies(self) -> List[ConversationContext]:
        """
        Get all sessions waiting for expert reply

        Returns:
            所有 WAITING_FOR_EXPERT 状态的 ConversationContext 列表

        Purpose: Background scheduled task to remind experts who haven't replied
        """
        pending_contexts = []

        # 从 Redis 扫描
        if not self._using_fallback and self.storage:
            try:
                pattern = "wework:conv_state:*"
                cursor = "0"

                while True:
                    cursor, keys = await self.storage.client.scan(
                        cursor=int(cursor),
                        match=pattern,
                        count=100
                    )

                    for key in keys:
                        data = await self.storage.client.get(key)
                        if data:
                            context = ConversationContext.from_json(data)
                            if context.state == ConversationState.WAITING_FOR_EXPERT:
                                pending_contexts.append(context)

                    if cursor == 0 or cursor == "0":
                        break

            except RedisError as e:
                logger.warning(f"Redis error getting all pending replies: {e}")
                self._using_fallback = True

        # 降级到内存
        if self._using_fallback:
            for context in self._memory_state.values():
                if context.state == ConversationState.WAITING_FOR_EXPERT:
                    pending_contexts.append(context)

        logger.info(f"Found {len(pending_contexts)} pending expert replies")
        return pending_contexts

    async def clear_conversation_context(self, user_id: str) -> None:
        """
        Clear user conversation context (Reset to IDLE)

        Args:
            user_id: 用户 UserID
        """
        redis_key = f"wework:conv_state:{user_id}"

        # 从 Redis 删除
        if not self._using_fallback and self.storage:
            try:
                await self.storage.client.delete(redis_key)
                logger.info(f"Cleared context for {user_id} from Redis")
            except RedisError as e:
                logger.warning(f"Redis error clearing context for {user_id}: {e}")

        # 从内存删除
        if user_id in self._memory_state:
            del self._memory_state[user_id]
            logger.info(f"Cleared context for {user_id} from memory")

    async def cleanup_expired_contexts(self) -> int:
        """
        Cleanup expired conversation contexts

        (Redis Uses TTL for auto cleanup, This method mainly cleans memory fallback data)

        Returns:
            Number of cleaned sessions
        """
        now = datetime.now()
        expired_count = 0

        # Clean sessions older than .* hours in memory
        expired_users = []
        for user_id, context in self._memory_state.items():
            age_hours = (now - context.created_at).total_seconds() / 3600
            if age_hours > 48:
                expired_users.append(user_id)

        for user_id in expired_users:
            del self._memory_state[user_id]
            expired_count += 1

        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired conversation contexts")

        return expired_count


# Singleton instance
_conversation_state_manager_instance: Optional[ConversationStateManager] = None


def get_conversation_state_manager(
    kb_root: Optional[Path] = None,
    storage: Optional[SessionStorage] = None
) -> ConversationStateManager:
    """
    Get .* singleton

    Args:
        kb_root: Knowledge base root directory (Required on first call)
        storage: Session storage backend (Optional on first call)

    Returns:
        ConversationStateManager 实例
    """
    global _conversation_state_manager_instance

    if _conversation_state_manager_instance is None:
        if kb_root is None:
            raise ValueError("kb_root must be provided on first call")
        _conversation_state_manager_instance = ConversationStateManager(
            kb_root=kb_root,
            storage=storage
        )

    return _conversation_state_manager_instance


__all__ = [
    'ConversationStateManager',
    'get_conversation_state_manager'
]
