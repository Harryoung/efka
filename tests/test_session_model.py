"""
Session数据模型单元测试
"""

import pytest
from datetime import datetime
from backend.models.session import (
    Session,
    SessionSummary,
    SessionRole,
    SessionStatus,
    MessageSnapshot
)


def test_session_creation():
    """测试Session创建"""
    now = datetime.now()
    summary = SessionSummary(
        original_question="测试问题",
        latest_exchange=MessageSnapshot(
            content="测试消息",
            timestamp=now,
            role="user"
        ),
        key_points=["关键点1", "关键点2"],
        last_updated=now,
        version=0
    )

    session = Session(
        session_id="test-123",
        user_id="emp001",
        role=SessionRole.EMPLOYEE,
        status=SessionStatus.ACTIVE,
        summary=summary,
        full_context_key="session_history:test-123",
        last_active_at=now,
        created_at=now,
        expires_at=datetime(2025, 12, 31)
    )

    assert session.session_id == "test-123"
    assert session.user_id == "emp001"
    assert session.role == SessionRole.EMPLOYEE
    assert session.status == SessionStatus.ACTIVE
    assert session.summary.version == 0


def test_session_summary_versioning():
    """测试摘要版本控制"""
    summary = SessionSummary(
        original_question="测试",
        latest_exchange=MessageSnapshot(
            content="测试",
            timestamp=datetime.now(),
            role="user"
        ),
        key_points=[],
        last_updated=datetime.now(),
        version=0
    )

    assert summary.version == 0

    # 模拟版本递增
    summary.version += 1
    assert summary.version == 1


def test_session_role_enum():
    """测试SessionRole枚举"""
    assert SessionRole.EMPLOYEE.value == "employee"
    assert SessionRole.EXPERT.value == "expert"
    assert SessionRole.EXPERT_AS_EMPLOYEE.value == "expert_as_employee"


def test_session_status_enum():
    """测试SessionStatus枚举"""
    assert SessionStatus.ACTIVE.value == "active"
    assert SessionStatus.WAITING_EXPERT.value == "waiting_expert"
    assert SessionStatus.RESOLVED.value == "resolved"
    assert SessionStatus.EXPIRED.value == "expired"


def test_message_snapshot():
    """测试MessageSnapshot"""
    now = datetime.now()
    snapshot = MessageSnapshot(
        content="测试消息内容",
        timestamp=now,
        role="user"
    )

    assert snapshot.content == "测试消息内容"
    assert snapshot.timestamp == now
    assert snapshot.role == "user"


def test_session_serialization():
    """测试Session序列化"""
    now = datetime.now()
    summary = SessionSummary(
        original_question="测试问题",
        latest_exchange=MessageSnapshot(
            content="测试消息",
            timestamp=now,
            role="user"
        ),
        key_points=["关键点1"],
        last_updated=now,
        version=0
    )

    session = Session(
        session_id="test-456",
        user_id="emp002",
        role=SessionRole.EXPERT,
        status=SessionStatus.WAITING_EXPERT,
        summary=summary,
        full_context_key="session_history:test-456",
        last_active_at=now,
        created_at=now,
        expires_at=datetime(2025, 12, 31)
    )

    # 测试model_dump
    session_dict = session.model_dump()
    assert session_dict['session_id'] == "test-456"
    assert session_dict['user_id'] == "emp002"
    assert session_dict['role'] == "expert"
    assert session_dict['status'] == "waiting_expert"

    # 测试model_dump_json
    session_json = session.model_dump_json()
    assert isinstance(session_json, str)
    assert "test-456" in session_json


def test_session_key_points_limit():
    """测试key_points列表"""
    summary = SessionSummary(
        original_question="测试",
        latest_exchange=MessageSnapshot(
            content="测试",
            timestamp=datetime.now(),
            role="user"
        ),
        key_points=["点1", "点2", "点3", "点4", "点5"],
        last_updated=datetime.now(),
        version=0
    )

    assert len(summary.key_points) == 5

    # 添加更多关键点（业务逻辑应限制最多10个）
    summary.key_points.extend(["点6", "点7", "点8", "点9", "点10"])
    assert len(summary.key_points) == 10
