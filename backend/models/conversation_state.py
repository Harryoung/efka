"""
Conversation state management data structures

This module defines the state machine for asynchronous multi-turn conversations
between employees, the Agent, and domain experts via WeChat Work.

State Transitions:
    IDLE → WAITING_FOR_EXPERT → COMPLETED → (auto-cleanup after 24h) → IDLE
"""

from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime
import json


class ConversationState(Enum):
    """
    Conversation state enumeration

    States:
        IDLE: Employee is not in an active conversation, or conversation completed
        WAITING_FOR_EXPERT: Agent has contacted a domain expert, waiting for reply
        COMPLETED: Expert replied, Agent forwarded to employee, FAQ updated
    """
    IDLE = "idle"
    WAITING_FOR_EXPERT = "waiting_expert"
    COMPLETED = "completed"


@dataclass
class ConversationContext:
    """
    Conversation context data structure

    This stores all information needed to manage an asynchronous conversation
    where an employee asks a question, Agent contacts an expert, and waits
    for the expert's reply before responding to the employee.

    Attributes:
        session_id: Claude Agent SDK session ID for continuity
        state: Current conversation state
        employee_userid: Employee's WeChat Work UserID
        employee_question: Original question from employee (None if IDLE)
        domain: Identified work domain (e.g., "薪酬福利", "考勤管理")
        expert_userid: Domain expert's WeChat Work UserID
        expert_name: Domain expert's display name (for user-friendly messages)
        contacted_at: Timestamp when expert was contacted
        expert_reply: Expert's reply content (None until received)
        created_at: Context creation timestamp
        updated_at: Last update timestamp
    """
    session_id: str
    state: ConversationState
    employee_userid: str
    employee_question: Optional[str] = None
    domain: Optional[str] = None
    expert_userid: Optional[str] = None
    expert_name: Optional[str] = None
    contacted_at: Optional[datetime] = None
    expert_reply: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        """Initialize timestamps if not provided"""
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        """
        Convert to dictionary for Redis storage

        Handles datetime and Enum serialization
        """
        data = asdict(self)
        # Convert Enum to string
        data['state'] = self.state.value
        # Convert datetime to ISO format
        for key in ['contacted_at', 'created_at', 'updated_at']:
            if data[key]:
                data[key] = data[key].isoformat()
        return data

    def to_json(self) -> str:
        """Serialize to JSON string for Redis storage"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> 'ConversationContext':
        """
        Create instance from dictionary (Redis retrieval)

        Handles datetime and Enum deserialization
        """
        # Convert state string back to Enum
        data['state'] = ConversationState(data['state'])
        # Convert ISO format strings back to datetime
        for key in ['contacted_at', 'created_at', 'updated_at']:
            if data.get(key):
                data[key] = datetime.fromisoformat(data[key])
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'ConversationContext':
        """Deserialize from JSON string (Redis retrieval)"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def is_waiting_for_expert(self) -> bool:
        """Check if conversation is waiting for expert reply"""
        return self.state == ConversationState.WAITING_FOR_EXPERT

    def is_completed(self) -> bool:
        """Check if conversation is completed"""
        return self.state == ConversationState.COMPLETED

    def is_idle(self) -> bool:
        """Check if conversation is idle"""
        return self.state == ConversationState.IDLE

    def time_since_contacted(self) -> Optional[float]:
        """
        Get seconds since expert was contacted

        Returns None if expert hasn't been contacted yet
        """
        if self.contacted_at:
            return (datetime.now() - self.contacted_at).total_seconds()
        return None

    def has_expert_reply_timeout(self, timeout_seconds: int = 86400) -> bool:
        """
        Check if expert reply has timed out (default 24h)

        Args:
            timeout_seconds: Timeout threshold in seconds (default: 86400 = 24h)

        Returns:
            True if waiting for expert and timeout exceeded
        """
        if not self.is_waiting_for_expert():
            return False

        time_elapsed = self.time_since_contacted()
        if time_elapsed is None:
            return False

        return time_elapsed > timeout_seconds
