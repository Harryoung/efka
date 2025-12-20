"""
RoutingSessionManager单元测试
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime
from backend.services.routing_session_manager import RoutingSessionManager
from backend.models.session import SessionRole, SessionStatus, MessageSnapshot


@pytest.mark.asyncio
async def test_create_session():
    """测试Session创建"""
    # 使用内存存储（redis_client=None）
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    session = await mgr.create_session(
        user_id="emp001",
        role=SessionRole.USER,
        original_question="测试问题"
    )

    assert session.user_id == "emp001"
    assert session.role == SessionRole.USER
    assert session.status == SessionStatus.ACTIVE
    assert session.summary.original_question == "测试问题"
    assert session.summary.version == 0


@pytest.mark.asyncio
async def test_get_session():
    """测试Session获取"""
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    # 创建Session
    created_session = await mgr.create_session(
        user_id="emp002",
        role=SessionRole.USER,
        original_question="测试获取"
    )

    # 获取Session
    retrieved_session = await mgr.get_session(created_session.session_id)

    assert retrieved_session is not None
    assert retrieved_session.session_id == created_session.session_id
    assert retrieved_session.user_id == "emp002"


@pytest.mark.asyncio
async def test_query_user_sessions_time_order():
    """测试Sessions按时间倒序返回"""
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    # 创建3个Session（间隔时间确保时间戳不同）
    s1 = await mgr.create_session(
        user_id="emp001",
        role=SessionRole.USER,
        original_question="Q1"
    )
    await asyncio.sleep(0.01)

    s2 = await mgr.create_session(
        user_id="emp001",
        role=SessionRole.USER,
        original_question="Q2"
    )
    await asyncio.sleep(0.01)

    s3 = await mgr.create_session(
        user_id="emp001",
        role=SessionRole.USER,
        original_question="Q3"
    )

    # 查询
    result = await mgr.query_user_sessions("emp001")

    # 验证倒序（最新的在前）
    assert len(result.as_user) == 3
    assert result.as_user[0].session_id == s3.session_id
    assert result.as_user[1].session_id == s2.session_id
    assert result.as_user[2].session_id == s1.session_id


@pytest.mark.asyncio
async def test_query_sessions_role_separation():
    """测试按角色分离查询"""
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    # 创建员工Session
    s1 = await mgr.create_session(
        user_id="expert001",
        role=SessionRole.EXPERT_AS_USER,
        original_question="专家作为员工咨询"
    )

    # 创建专家Session
    s2 = await mgr.create_session(
        user_id="expert001",
        role=SessionRole.EXPERT,
        original_question="专家被咨询",
        related_user_id="emp001"
    )

    # 查询
    result = await mgr.query_user_sessions("expert001")

    # 验证分离
    assert len(result.as_user) == 1
    assert len(result.as_expert) == 1
    assert result.as_user[0].session_id == s1.session_id
    assert result.as_expert[0].session_id == s2.session_id


@pytest.mark.asyncio
async def test_update_session_summary():
    """测试Session摘要更新"""
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    session = await mgr.create_session(
        user_id="emp003",
        role=SessionRole.USER,
        original_question="测试更新"
    )

    initial_version = session.summary.version

    # 更新摘要
    new_message = MessageSnapshot(
        content="新消息",
        timestamp=datetime.now(),
        role="user"
    )

    success = await mgr.update_session_summary(
        session_id=session.session_id,
        new_message=new_message,
        key_points=["新关键点1", "新关键点2"]
    )

    assert success

    # 验证更新
    updated_session = await mgr.get_session(session.session_id)
    assert updated_session.summary.version == initial_version + 1
    assert updated_session.summary.latest_exchange.content == "新消息"
    assert "新关键点1" in updated_session.summary.key_points
    assert "新关键点2" in updated_session.summary.key_points


@pytest.mark.asyncio
async def test_update_session_status():
    """测试Session状态更新"""
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    session = await mgr.create_session(
        user_id="emp004",
        role=SessionRole.USER,
        original_question="测试状态更新"
    )

    # 更新状态为RESOLVED
    success = await mgr.update_session_summary(
        session_id=session.session_id,
        new_message=MessageSnapshot(
            content="测试",
            timestamp=datetime.now(),
            role="agent"
        ),
        session_status=SessionStatus.RESOLVED
    )

    assert success

    # 验证状态
    updated_session = await mgr.get_session(session.session_id)
    assert updated_session.status == SessionStatus.RESOLVED


@pytest.mark.asyncio
async def test_query_sessions_with_limit():
    """测试查询Session数量限制"""
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    # 创建5个Session
    for i in range(5):
        await mgr.create_session(
            user_id="emp005",
            role=SessionRole.USER,
            original_question=f"Q{i+1}"
        )
        await asyncio.sleep(0.01)

    # 查询限制为3个
    result = await mgr.query_user_sessions("emp005", max_per_role=3)

    # 验证返回数量
    assert len(result.as_user) == 3


@pytest.mark.asyncio
async def test_session_not_found():
    """测试获取不存在的Session"""
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    session = await mgr.get_session("non-existent-id")
    assert session is None
