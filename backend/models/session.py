"""
Session数据模型 - 支持Session Router智能会话管理

数据结构设计：
- Session: 完整会话数据
- SessionSummary: 动态摘要（原始问题 + 最新交互 + 关键点）
- SessionRole: 用户角色（员工/专家/专家作为员工）
- SessionStatus: 会话状态（活跃/等待专家/已解决/已过期）
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class SessionRole(str, Enum):
    """用户在Session中的角色"""
    USER = "user"  # 作为用户咨询
    EXPERT = "expert"  # 作为专家被咨询
    EXPERT_AS_USER = "expert_as_user"  # 专家自己咨询


class SessionStatus(str, Enum):
    """Session状态"""
    ACTIVE = "active"  # 活跃中
    WAITING_EXPERT = "waiting_expert"  # 等待专家回复
    RESOLVED = "resolved"  # 已解决
    EXPIRED = "expired"  # 已过期


class MessageSnapshot(BaseModel):
    """消息快照（用于摘要）"""
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(..., description="消息时间")
    role: str = Field(..., description="消息角色: user/agent/expert")


class SessionSummary(BaseModel):
    """
    Session摘要结构

    设计原则：
    - original_question: 永远不变，标识Session主题
    - latest_exchange: 最新一轮对话（动态更新）
    - key_points: 关键信息点（Agent提取，最多10个）
    - version: 乐观锁版本号（支持并发更新）
    """
    original_question: str = Field(..., description="原始问题（不变）")
    latest_exchange: Optional[MessageSnapshot] = Field(None, description="最新一轮对话")
    key_points: List[str] = Field(default_factory=list, description="关键信息点")
    last_updated: datetime = Field(default_factory=datetime.now, description="摘要最后更新时间")
    version: int = Field(default=0, description="乐观锁版本号")


class Session(BaseModel):
    """
    Session完整数据结构

    Redis存储：
    - session:{session_id} -> Session JSON
    - user_sessions:{user_id} -> Set[session_id]
    - session_history:{session_id} -> List[Message JSON]

    TTL策略：
    - ACTIVE: 7天（基本不过期）
    - RESOLVED: 24小时（标记时刻起）
    - WAITING_EXPERT: 7天
    - EXPIRED: 立即删除
    """
    session_id: str = Field(..., description="Session UUID")
    user_id: str = Field(..., description="Platform user ID")
    role: SessionRole = Field(..., description="用户角色")
    status: SessionStatus = Field(..., description="Session状态")

    # 核心内容
    summary: SessionSummary = Field(..., description="动态摘要")
    full_context_key: str = Field(..., description="Redis key指向完整历史")

    # 专家相关（仅role=EXPERT时有效）
    related_user_id: Optional[str] = Field(None, description="关联的用户ID")
    domain: Optional[str] = Field(None, description="专业领域")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    last_active_at: datetime = Field(default_factory=datetime.now, description="最后活跃时间")
    expires_at: datetime = Field(..., description="过期时间")

    # 元数据
    message_count: int = Field(default=0, description="消息数量")
    tags: List[str] = Field(default_factory=list, description="标签（Agent动态添加）")


class SessionQueryResult(BaseModel):
    """
    MCP工具返回结构

    区分用户的两种身份：
    - as_user: 用户作为咨询者的sessions
    - as_expert: 用户作为专家的sessions（被咨询）

    重要：列表按 last_active_at 倒序排列
    """
    user_id: str = Field(..., description="Platform user ID")
    as_user: List[Session] = Field(default_factory=list, description="作为咨询者的sessions")
    as_expert: List[Session] = Field(default_factory=list, description="作为专家的sessions")
    total_count: int = Field(..., description="总Session数量")


# 导出
__all__ = [
    "SessionRole",
    "SessionStatus",
    "MessageSnapshot",
    "SessionSummary",
    "Session",
    "SessionQueryResult"
]
