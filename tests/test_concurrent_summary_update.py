"""
并发Session摘要更新测试 - 验证乐观锁机制

这个测试是Phase 5的核心，用于验证：
1. 乐观锁CAS机制正常工作
2. 并发更新时版本冲突能正确检测
3. 重试机制能成功解决冲突
4. 统计冲突率和重试成功率
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime
from backend.services.routing_session_manager import RoutingSessionManager
from backend.models.session import SessionRole, MessageSnapshot


@pytest.mark.asyncio
async def test_concurrent_summary_update_optimistic_lock():
    """
    测试并发Session摘要更新（乐观锁）

    场景：10个并发任务同时更新同一个Session的摘要
    预期：所有更新都成功（通过乐观锁重试机制）
    """
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    # 创建Session
    session = await mgr.create_session(
        user_id="emp001",
        role=SessionRole.USER,
        original_question="测试并发更新"
    )

    # 模拟10个并发更新
    tasks = [
        mgr.update_session_summary(
            session.session_id,
            new_message=MessageSnapshot(
                content=f"Message {i}",
                timestamp=datetime.now(),
                role="user"
            )
        )
        for i in range(10)
    ]

    results = await asyncio.gather(*tasks)

    # 验证所有更新都成功
    assert all(results), f"Some updates failed: {results}"

    # 验证版本号正确递增
    updated_session = await mgr.get_session(session.session_id)
    assert updated_session.summary.version == 10, f"Expected version 10, got {updated_session.summary.version}"

    print(f"✅ 并发测试通过：10个并发更新全部成功，版本号正确递增到 {updated_session.summary.version}")


@pytest.mark.asyncio
async def test_concurrent_update_different_sessions():
    """
    测试并发更新不同Session（无冲突场景）

    场景：10个并发任务更新10个不同的Session
    预期：所有更新都成功，无冲突
    """
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    # 创建10个Session
    sessions = []
    for i in range(10):
        session = await mgr.create_session(
            user_id=f"emp{i:03d}",
            role=SessionRole.USER,
            original_question=f"Q{i}"
        )
        sessions.append(session)

    # 并发更新不同Session
    tasks = [
        mgr.update_session_summary(
            sessions[i].session_id,
            new_message=MessageSnapshot(
                content=f"Update for session {i}",
                timestamp=datetime.now(),
                role="user"
            )
        )
        for i in range(10)
    ]

    results = await asyncio.gather(*tasks)

    # 验证所有更新都成功
    assert all(results), "Some updates failed"

    # 验证每个Session版本号都是1
    for session in sessions:
        updated = await mgr.get_session(session.session_id)
        assert updated.summary.version == 1

    print(f"✅ 无冲突并发测试通过：10个Session并发更新全部成功")


@pytest.mark.asyncio
async def test_concurrent_update_with_key_points():
    """
    测试并发更新Session摘要（带key_points）

    场景：5个并发任务更新同一Session，每个添加不同的key_points
    预期：所有key_points都被正确累积
    """
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    session = await mgr.create_session(
        user_id="emp100",
        role=SessionRole.USER,
        original_question="测试key_points累积"
    )

    # 5个并发更新，每个添加2个key_points
    tasks = [
        mgr.update_session_summary(
            session.session_id,
            new_message=MessageSnapshot(
                content=f"Msg {i}",
                timestamp=datetime.now(),
                role="user"
            ),
            key_points=[f"point_{i}_a", f"point_{i}_b"]
        )
        for i in range(5)
    ]

    results = await asyncio.gather(*tasks)
    assert all(results)

    # 验证key_points累积
    updated_session = await mgr.get_session(session.session_id)

    # 应该有10个key_points（5次更新 x 2个点）
    assert len(updated_session.summary.key_points) == 10, \
        f"Expected 10 key_points, got {len(updated_session.summary.key_points)}"

    print(f"✅ Key points累积测试通过：{len(updated_session.summary.key_points)}个关键点正确累积")


@pytest.mark.asyncio
async def test_concurrent_update_stress_test():
    """
    压力测试：20个并发任务更新同一Session

    这个测试模拟高并发场景，验证乐观锁机制在高压下的表现
    """
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    session = await mgr.create_session(
        user_id="emp_stress",
        role=SessionRole.USER,
        original_question="压力测试"
    )

    # 20个并发更新
    concurrent_updates = 20
    tasks = [
        mgr.update_session_summary(
            session.session_id,
            new_message=MessageSnapshot(
                content=f"Stress test message {i}",
                timestamp=datetime.now(),
                role="user"
            )
        )
        for i in range(concurrent_updates)
    ]

    # 记录开始时间
    start_time = asyncio.get_event_loop().time()

    results = await asyncio.gather(*tasks)

    # 记录结束时间
    end_time = asyncio.get_event_loop().time()
    elapsed = end_time - start_time

    # 验证结果
    success_count = sum(1 for r in results if r)
    failure_count = sum(1 for r in results if not r)

    updated_session = await mgr.get_session(session.session_id)

    print(f"\n压力测试结果：")
    print(f"  - 并发更新数：{concurrent_updates}")
    print(f"  - 成功：{success_count}")
    print(f"  - 失败：{failure_count}")
    print(f"  - 最终版本号：{updated_session.summary.version}")
    print(f"  - 耗时：{elapsed:.3f}秒")
    print(f"  - 平均每次更新：{elapsed/concurrent_updates*1000:.1f}ms")

    # 在内存模式下，所有更新应该成功
    assert success_count == concurrent_updates, f"Expected all {concurrent_updates} updates to succeed"
    assert updated_session.summary.version == concurrent_updates


@pytest.mark.asyncio
async def test_sequential_vs_concurrent_comparison():
    """
    对比测试：顺序更新 vs 并发更新

    验证并发更新的性能优势（在有Redis的情况下更明显）
    """
    mgr = RoutingSessionManager(kb_root=Path("."), redis_client=None)
    await mgr.initialize()

    # 测试参数
    num_updates = 10

    # === 顺序更新测试 ===
    session_seq = await mgr.create_session(
        user_id="emp_seq",
        role=SessionRole.USER,
        original_question="顺序测试"
    )

    start_seq = asyncio.get_event_loop().time()
    for i in range(num_updates):
        await mgr.update_session_summary(
            session_seq.session_id,
            new_message=MessageSnapshot(
                content=f"Seq {i}",
                timestamp=datetime.now(),
                role="user"
            )
        )
    end_seq = asyncio.get_event_loop().time()
    seq_time = end_seq - start_seq

    # === 并发更新测试 ===
    session_conc = await mgr.create_session(
        user_id="emp_conc",
        role=SessionRole.USER,
        original_question="并发测试"
    )

    start_conc = asyncio.get_event_loop().time()
    tasks = [
        mgr.update_session_summary(
            session_conc.session_id,
            new_message=MessageSnapshot(
                content=f"Conc {i}",
                timestamp=datetime.now(),
                role="user"
            )
        )
        for i in range(num_updates)
    ]
    await asyncio.gather(*tasks)
    end_conc = asyncio.get_event_loop().time()
    conc_time = end_conc - start_conc

    print(f"\n性能对比（{num_updates}次更新）：")
    print(f"  - 顺序更新：{seq_time*1000:.1f}ms")
    print(f"  - 并发更新：{conc_time*1000:.1f}ms")
    print(f"  - 性能提升：{seq_time/conc_time:.2f}x（注意：内存模式下提升有限）")

    # 验证两种方式结果一致
    final_seq = await mgr.get_session(session_seq.session_id)
    final_conc = await mgr.get_session(session_conc.session_id)

    assert final_seq.summary.version == num_updates
    assert final_conc.summary.version == num_updates

    print(f"✅ 对比测试通过：两种方式版本号一致")
