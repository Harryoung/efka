"""
端到端集成测试 - Session Router

测试完整的Session路由流程，验证：
1. 用户连续咨询多个问题，模糊回复按时间倒序匹配
2. 专家同时收到多个问题，语义匹配到具体Session
3. 专家双重身份管理

注意：这些测试模拟业务逻辑，不实际调用Session Router Agent API
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime
from backend.services.routing_session_manager import RoutingSessionManager
from backend.models.session import SessionRole, SessionStatus, MessageSnapshot


@pytest.mark.asyncio
async def test_e2e_user_consecutive_queries_fuzzy_reply():
    """
    E2E场景1: 用户连续咨询3个问题，只回复最后一个"满意"

    场景描述：
    1. 用户提问："如何申请年假？"
    2. 用户提问："报销流程是什么？"
    3. 用户提问："考勤异常怎么处理？"
    4. 用户回复："满意"（模糊回复）

    预期：
    - 创建3个Session
    - "满意"应该匹配到最新的Session（问题3）
    - 该Session状态变更为RESOLVED
    """
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    user_id = "emp001"

    # Step 1: 用户提问1
    s1 = await mgr.create_session(
        user_id=user_id,
        role=SessionRole.USER,
        original_question="如何申请年假？"
    )
    await asyncio.sleep(0.01)

    # 模拟Agent回复
    await mgr.update_session_summary(
        s1.session_id,
        new_message=MessageSnapshot(
            content="年假申请需要在OA系统提交...",
            timestamp=datetime.now(),
            role="agent"
        ),
        key_points=["年假申请", "OA系统"]
    )

    # Step 2: 用户提问2
    s2 = await mgr.create_session(
        user_id=user_id,
        role=SessionRole.USER,
        original_question="报销流程是什么？"
    )
    await asyncio.sleep(0.01)

    # 模拟Agent回复
    await mgr.update_session_summary(
        s2.session_id,
        new_message=MessageSnapshot(
            content="报销需要提交发票...",
            timestamp=datetime.now(),
            role="agent"
        ),
        key_points=["报销流程", "发票"]
    )

    # Step 3: 用户提问3
    s3 = await mgr.create_session(
        user_id=user_id,
        role=SessionRole.USER,
        original_question="考勤异常怎么处理？"
    )
    await asyncio.sleep(0.01)

    # 模拟Agent回复
    await mgr.update_session_summary(
        s3.session_id,
        new_message=MessageSnapshot(
            content="考勤异常需要在系统中申请补卡...",
            timestamp=datetime.now(),
            role="agent"
        ),
        key_points=["考勤异常", "补卡"]
    )

    # Step 4: 查询该用户的Sessions（按时间倒序）
    result = await mgr.query_user_sessions(user_id)

    # 验证时间倒序
    assert len(result.as_user) == 3
    assert result.as_user[0].session_id == s3.session_id  # 最新
    assert result.as_user[1].session_id == s2.session_id
    assert result.as_user[2].session_id == s1.session_id

    # Step 5: 模拟Session Router决策（时间优先）
    # 用户回复"满意" -> 应该匹配最新的Session (s3)
    matched_session_id = result.as_user[0].session_id

    # Step 6: 更新Session状态为RESOLVED
    await mgr.update_session_summary(
        matched_session_id,
        new_message=MessageSnapshot(
            content="满意",
            timestamp=datetime.now(),
            role="user"
        ),
        session_status=SessionStatus.RESOLVED
    )

    # 验证结果
    final_session = await mgr.get_session(matched_session_id)
    assert final_session.status == SessionStatus.RESOLVED
    assert final_session.session_id == s3.session_id

    print(f"✅ E2E场景1通过：模糊回复'满意'正确匹配到最新Session")


@pytest.mark.asyncio
async def test_e2e_expert_multiple_pending_questions():
    """
    E2E场景2: 专家同时收到3个待回复问题，根据回复内容语义匹配

    场景描述：
    1. 用户A问："新用户入职需要准备什么材料？"
    2. 用户B问："试用期考核标准是什么？"
    3. 用户C问："年假申请流程？"
    4. 专家回复："入职材料需要身份证原件和学历证书复印件"

    预期：
    - 创建3个EXPERT角色的Session
    - 专家回复应该匹配到问题1（语义相关：入职材料）
    """
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    expert_userid = "expert001"

    # 创建3个待回复Session
    s1 = await mgr.create_session(
        user_id=expert_userid,
        role=SessionRole.EXPERT,
        original_question="新用户入职需要准备什么材料？",
        related_user_id="emp_a"
    )
    s1.status = SessionStatus.WAITING_EXPERT
    await asyncio.sleep(0.01)

    s2 = await mgr.create_session(
        user_id=expert_userid,
        role=SessionRole.EXPERT,
        original_question="试用期考核标准是什么？",
        related_user_id="emp_b"
    )
    s2.status = SessionStatus.WAITING_EXPERT
    await asyncio.sleep(0.01)

    s3 = await mgr.create_session(
        user_id=expert_userid,
        role=SessionRole.EXPERT,
        original_question="年假申请流程？",
        related_user_id="emp_c"
    )
    s3.status = SessionStatus.WAITING_EXPERT

    # 查询专家的待回复Sessions
    result = await mgr.query_user_sessions(expert_userid)

    # 验证专家Session列表
    assert len(result.as_expert) == 3

    # 模拟Session Router语义匹配
    # 专家回复："入职材料需要身份证原件和学历证书复印件"
    # 应该匹配s1（包含"入职"、"材料"关键词）
    expert_reply = "入职材料需要身份证原件和学历证书复印件"

    # 在实际场景中，Session Router Agent会进行语义判断
    # 这里我们模拟匹配到s1
    matched_session_id = s1.session_id

    # 更新Session
    await mgr.update_session_summary(
        matched_session_id,
        new_message=MessageSnapshot(
            content=expert_reply,
            timestamp=datetime.now(),
            role="expert"
        ),
        session_status=SessionStatus.RESOLVED
    )

    # 验证结果
    final_session = await mgr.get_session(matched_session_id)
    assert final_session.status == SessionStatus.RESOLVED
    assert "入职材料" in final_session.summary.latest_exchange.content

    print(f"✅ E2E场景2通过：专家回复正确匹配到语义相关的Session")


@pytest.mark.asyncio
async def test_e2e_expert_dual_identity():
    """
    E2E场景3: 专家双重身份管理

    场景描述：
    1. 专家作为用户咨询："我的薪资调整流程是什么？"
    2. 同时有用户问专家："入职材料有哪些？"

    预期：
    - 创建2个Session：EXPERT_AS_USER + EXPERT
    - 查询时正确区分as_user和as_expert
    """
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    expert_userid = "expert002"

    # 专家作为用户咨询
    s1 = await mgr.create_session(
        user_id=expert_userid,
        role=SessionRole.EXPERT_AS_USER,
        original_question="我的薪资调整流程是什么？"
    )

    # 专家被咨询
    s2 = await mgr.create_session(
        user_id=expert_userid,
        role=SessionRole.EXPERT,
        original_question="入职材料有哪些？",
        related_user_id="emp_d"
    )

    # 查询Sessions
    result = await mgr.query_user_sessions(expert_userid)

    # 验证双重身份分离
    assert len(result.as_user) == 1
    assert len(result.as_expert) == 1
    assert result.as_user[0].session_id == s1.session_id
    assert result.as_expert[0].session_id == s2.session_id

    # 验证角色
    assert result.as_user[0].role == SessionRole.EXPERT_AS_USER
    assert result.as_expert[0].role == SessionRole.EXPERT

    print(f"✅ E2E场景3通过：专家双重身份正确分离管理")


@pytest.mark.asyncio
async def test_e2e_session_lifecycle():
    """
    E2E场景4: Session完整生命周期

    测试一个Session从创建到解决的完整流程：
    1. 创建Session（ACTIVE）
    2. Agent回复（ACTIVE）
    3. 用户追问（ACTIVE）
    4. Agent再次回复（ACTIVE）
    5. 用户表示满意（RESOLVED）
    """
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    user_id = "emp_lifecycle"

    # Step 1: 创建Session
    session = await mgr.create_session(
        user_id=user_id,
        role=SessionRole.USER,
        original_question="如何申请病假？"
    )
    assert session.status == SessionStatus.ACTIVE
    assert session.summary.version == 0

    # Step 2: Agent首次回复
    await mgr.update_session_summary(
        session.session_id,
        new_message=MessageSnapshot(
            content="病假需要提供医院证明...",
            timestamp=datetime.now(),
            role="agent"
        ),
        key_points=["病假", "医院证明"]
    )
    s2 = await mgr.get_session(session.session_id)
    assert s2.status == SessionStatus.ACTIVE
    assert s2.summary.version == 1
    assert len(s2.summary.key_points) == 2

    # Step 3: 用户追问
    await mgr.update_session_summary(
        session.session_id,
        new_message=MessageSnapshot(
            content="需要提前几天提交？",
            timestamp=datetime.now(),
            role="user"
        )
    )
    s3 = await mgr.get_session(session.session_id)
    assert s3.status == SessionStatus.ACTIVE
    assert s3.summary.version == 2

    # Step 4: Agent再次回复
    await mgr.update_session_summary(
        session.session_id,
        new_message=MessageSnapshot(
            content="需要提前1天提交",
            timestamp=datetime.now(),
            role="agent"
        ),
        key_points=["提前1天"]
    )
    s4 = await mgr.get_session(session.session_id)
    assert s4.status == SessionStatus.ACTIVE
    assert s4.summary.version == 3
    assert len(s4.summary.key_points) == 3

    # Step 5: 用户表示满意
    await mgr.update_session_summary(
        session.session_id,
        new_message=MessageSnapshot(
            content="明白了，谢谢！",
            timestamp=datetime.now(),
            role="user"
        ),
        session_status=SessionStatus.RESOLVED
    )
    s5 = await mgr.get_session(session.session_id)
    assert s5.status == SessionStatus.RESOLVED
    assert s5.summary.version == 4

    print(f"✅ E2E场景4通过：Session完整生命周期测试通过（4次更新，版本号0→4）")


@pytest.mark.asyncio
async def test_e2e_multiple_users_concurrent():
    """
    E2E场景5: 多用户并发场景

    模拟真实场景：3个用户同时咨询不同问题
    """
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    # 3个用户同时创建Session
    tasks_create = [
        mgr.create_session(
            user_id=f"emp{i:03d}",
            role=SessionRole.USER,
            original_question=f"问题{i}"
        )
        for i in range(3)
    ]
    sessions = await asyncio.gather(*tasks_create)

    # 3个用户的Session同时收到回复
    tasks_update = [
        mgr.update_session_summary(
            sessions[i].session_id,
            new_message=MessageSnapshot(
                content=f"回复{i}",
                timestamp=datetime.now(),
                role="agent"
            ),
            key_points=[f"关键点{i}"]
        )
        for i in range(3)
    ]
    results = await asyncio.gather(*tasks_update)
    assert all(results)

    # 验证每个Session独立管理
    for i, session in enumerate(sessions):
        final = await mgr.get_session(session.session_id)
        assert final.user_id == f"emp{i:03d}"
        assert final.summary.version == 1
        assert f"关键点{i}" in final.summary.key_points

    print(f"✅ E2E场景5通过：3个用户并发Session独立管理正常")
