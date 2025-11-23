"""
Conversation State Manager - 会话状态管理器

管理用户-专家异步多轮对话的状态持久化
支持 Redis 存储和内存降级
支持多平台（WeChat Work, Feishu, Slack等）
"""

import asyncio
import logging
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path

from backend.models.conversation_state import ConversationState, ConversationContext
from backend.storage.base import SessionStorage
from backend.config.messaging_platforms import MessagingPlatformType
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class ConversationStateManager:
    """
    会话状态管理器

    职责:
    1. 管理用户提问后等待专家回复的状态
    2. 检查某个专家是否有待回复的问题
    3. 更新会话状态(IDLE → WAITING_FOR_EXPERT → COMPLETED)
    4. 支持 Redis 持久化和内存降级
    5. 支持多平台（每个平台使用独立的Redis key前缀）

    架构说明:
    - 状态存储在 Redis key: {platform}:conv_state:{userid}
    - 24小时TTL自动清理已完成的会话
    - Redis 故障时降级到内存存储
    - 平台前缀通过 MessagingPlatformFactory 获取
    """

    def __init__(
        self,
        kb_root: Path,
        platform: MessagingPlatformType,
        storage: Optional[SessionStorage] = None
    ):
        """
        初始化会话状态管理器

        Args:
            kb_root: 知识库根目录
            platform: 消息平台类型
            storage: Session storage backend (Redis or memory)
        """
        self.kb_root = kb_root
        self.platform = platform
        self.storage = storage

        # 从平台配置获取 Redis key 前缀
        from backend.services.messaging_platform_factory import get_messaging_platform_factory
        factory = get_messaging_platform_factory()

        # 确保平台已注册
        if not factory.is_registered(platform):
            factory.register_platform(platform)

        self.redis_key_prefix = factory.get_redis_key_prefix(platform)

        # 内存降级存储 (userid -> ConversationContext)
        self._memory_state: Dict[str, ConversationContext] = {}
        self._using_fallback = False

        logger.info(f"ConversationStateManager initialized (platform={platform.value}, prefix={self.redis_key_prefix})")

    async def initialize_storage(self) -> None:
        """初始化存储后端"""
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

    def _make_redis_key(self, user_id: str) -> str:
        """
        构建平台特定的Redis key

        Args:
            user_id: Platform user ID

        Returns:
            Redis key: {platform}:conv_state:{user_id}
        """
        return f"{self.redis_key_prefix}:conv_state:{user_id}"

    async def get_conversation_context(
        self,
        user_id: str
    ) -> ConversationContext:
        """
        获取用户会话上下文

        Args:
            user_id: Platform user ID

        Returns:
            ConversationContext 对象

        如果不存在,返回新的 IDLE 状态上下文
        """
        redis_key = self._make_redis_key(user_id)

        # 尝试从 Redis 读取
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

        # 创建新的 IDLE 上下文
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
        更新会话状态

        Args:
            user_id: Platform user ID
            **kwargs: 要更新的字段 (state, user_question, domain, expert_userid, etc.)

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
        # 获取现有上下文
        context = await self.get_conversation_context(user_id)

        # 更新字段
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)

        context.updated_at = datetime.now()

        # 持久化到 Redis
        redis_key = self._make_redis_key(user_id)
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

        # 同时更新内存 (降级或缓存)
        self._memory_state[user_id] = context
        logger.debug(f"Updated context for {user_id} in memory")

    async def check_pending_expert_reply(
        self,
        expert_userid: str
    ) -> Optional[ConversationContext]:
        """
        检查某个专家是否有待回复的问题

        遍历所有 WAITING_FOR_EXPERT 状态的会话,
        匹配 expert_userid

        Args:
            expert_userid: Platform expert user ID

        Returns:
            如果有待回复的问题,返回对应的 ConversationContext,否则返回 None

        Example:
            pending = await state_mgr.check_pending_expert_reply('wangwu')
            if pending:
                # 专家 wangwu 有待回复的问题
                employee_id = pending.user_id
                question = pending.user_question
        """
        # 如果使用 Redis,扫描所有 {platform}:conv_state:* keys
        if not self._using_fallback and self.storage:
            try:
                pattern = f"{self.redis_key_prefix}:conv_state:*"
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
                                    f"employee={context.user_id}"
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
                    f"employee={context.user_id}"
                )
                return context

        logger.debug(f"No pending replies found for expert {expert_userid}")
        return None

    async def get_all_pending_expert_replies(self) -> List[ConversationContext]:
        """
        获取所有等待专家回复的会话

        Returns:
            所有 WAITING_FOR_EXPERT 状态的 ConversationContext 列表

        用途: 后台定时任务提醒超时未回复的专家
        """
        pending_contexts = []

        # 从 Redis 扫描
        if not self._using_fallback and self.storage:
            try:
                pattern = f"{self.redis_key_prefix}:conv_state:*"
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
        清除用户会话上下文 (重置为 IDLE)

        Args:
            user_id: Platform user ID
        """
        redis_key = self._make_redis_key(user_id)

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
        清理过期的会话上下文

        (Redis 使用 TTL 自动清理, 此方法主要清理内存降级数据)

        Returns:
            清理的会话数量
        """
        now = datetime.now()
        expired_count = 0

        # 清理内存中超过 48 小时的会话
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


# Singleton instance per platform
_conversation_state_managers: Dict[MessagingPlatformType, ConversationStateManager] = {}


def get_conversation_state_manager(
    platform: MessagingPlatformType,
    kb_root: Optional[Path] = None,
    storage: Optional[SessionStorage] = None
) -> ConversationStateManager:
    """
    获取会话状态管理器单例（每个平台一个实例）

    Args:
        platform: 消息平台类型
        kb_root: 知识库根目录
        storage: Session storage backend

    Returns:
        ConversationStateManager实例
    """
    global _conversation_state_managers

    if platform not in _conversation_state_managers:
        if kb_root is None:
            from backend.config.settings import get_settings
            settings = get_settings()
            kb_root = Path(settings.KB_ROOT_PATH)

        _conversation_state_managers[platform] = ConversationStateManager(
            kb_root=kb_root,
            platform=platform,
            storage=storage
        )

    return _conversation_state_managers[platform]


# 导出
__all__ = [
    "ConversationStateManager",
    "get_conversation_state_manager"
]
