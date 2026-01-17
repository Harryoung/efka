"""
Session data models - Support Session Router intelligent conversation management

Data structure design:
- Session: Complete session data
- SessionSummary: Dynamic summary (original question + latest interaction + key points)
- SessionRole: User role (employee/expert/expert as employee)
- SessionStatus: Session status (active/waiting expert/resolved/expired)
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class SessionRole(str, Enum):
    """User's role in Session"""
    USER = "user"  # As user consulting
    EXPERT = "expert"  # As expert being consulted
    EXPERT_AS_USER = "expert_as_user"  # Expert consulting for themselves


class SessionStatus(str, Enum):
    """Session status"""
    ACTIVE = "active"  # Active
    WAITING_EXPERT = "waiting_expert"  # Waiting for expert reply
    RESOLVED = "resolved"  # Resolved
    EXPIRED = "expired"  # Expired


class MessageSnapshot(BaseModel):
    """Message snapshot (for summary)"""
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message time")
    role: str = Field(..., description="Message role: user/agent/expert")


class SessionSummary(BaseModel):
    """
    Session summary structure

    Design principles:
    - original_question: Never changes, identifies Session topic
    - latest_exchange: Latest round of conversation (dynamically updated)
    - key_points: Key information points (Agent extracted, max 10)
    - version: Optimistic lock version number (supports concurrent updates)
    """
    original_question: str = Field(..., description="Original question (immutable)")
    latest_exchange: Optional[MessageSnapshot] = Field(None, description="Latest round of conversation")
    key_points: List[str] = Field(default_factory=list, description="Key information points")
    last_updated: datetime = Field(default_factory=datetime.now, description="Summary last updated time")
    version: int = Field(default=0, description="Optimistic lock version number")


class Session(BaseModel):
    """
    Session complete data structure

    Redis storage:
    - session:{session_id} -> Session JSON
    - user_sessions:{user_id} -> Set[session_id]
    - session_history:{session_id} -> List[Message JSON]

    TTL strategy:
    - ACTIVE: 7 days (basically doesn't expire)
    - RESOLVED: 24 hours (from marking time)
    - WAITING_EXPERT: 7 days
    - EXPIRED: Delete immediately
    """
    session_id: str = Field(..., description="Session UUID")
    user_id: str = Field(..., description="Platform user ID")
    role: SessionRole = Field(..., description="User role")
    status: SessionStatus = Field(..., description="Session status")

    # Core content
    summary: SessionSummary = Field(..., description="Dynamic summary")
    full_context_key: str = Field(..., description="Redis key pointing to full history")

    # Expert related (only valid when role=EXPERT)
    related_user_id: Optional[str] = Field(None, description="Associated user ID")
    domain: Optional[str] = Field(None, description="Professional domain")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now, description="Creation time")
    last_active_at: datetime = Field(default_factory=datetime.now, description="Last active time")
    expires_at: datetime = Field(..., description="Expiration time")

    # Metadata
    message_count: int = Field(default=0, description="Message count")
    tags: List[str] = Field(default_factory=list, description="Tags (Agent dynamically added)")


class SessionQueryResult(BaseModel):
    """
    MCP tool return structure

    Distinguishes user's two identities:
    - as_user: User's sessions as consultant
    - as_expert: User's sessions as expert (being consulted)

    Important: Lists are sorted by last_active_at in descending order
    """
    user_id: str = Field(..., description="Platform user ID")
    as_user: List[Session] = Field(default_factory=list, description="Sessions as consultant")
    as_expert: List[Session] = Field(default_factory=list, description="Sessions as expert")
    total_count: int = Field(..., description="Total Session count")


# Export
__all__ = [
    "SessionRole",
    "SessionStatus",
    "MessageSnapshot",
    "SessionSummary",
    "Session",
    "SessionQueryResult"
]
