"""
重点测试：不同的 Client 是否能通过相同的 session id 来继续会话

验证场景：
1. Client A 创建会话，获取 session_id
2. Client B 使用 resume=session_id 恢复会话
3. 验证 Client B 是否能继续 Client A 的上下文
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage


async def test_resume_across_clients():
    """测试跨 Client 的 session 恢复"""
    print("=" * 60)
    print("测试：跨 Client 的 session 恢复")
    print("=" * 60)

    # Step 1: Client A 创建会话
    print("\n[Step 1] Client A 创建会话...")

    options_a = ClaudeAgentOptions(
        allowed_tools=["Read"],
        permission_mode="acceptEdits"
    )

    client_a = ClaudeSDKClient(options=options_a)
    await client_a.connect()

    # 发送第一条消息
    await client_a.query("我的名字是小明，我的年龄是25岁。请记住这些信息。")

    session_id = None
    async for msg in client_a.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(f"  Client A 响应: {block.text[:100]}")
        elif isinstance(msg, ResultMessage):
            session_id = msg.session_id
            print(f"  Session ID: {session_id}")

    await client_a.disconnect()
    print("  Client A 已断开")

    if not session_id:
        print("❌ 错误：未获取到 session_id")
        return False

    # Step 2: Client B 使用 resume 恢复会话
    print(f"\n[Step 2] Client B 使用 resume={session_id} 恢复会话...")

    options_b = ClaudeAgentOptions(
        allowed_tools=["Read"],
        permission_mode="acceptEdits",
        resume=session_id  # 关键：使用 resume 参数
    )

    client_b = ClaudeSDKClient(options=options_b)
    await client_b.connect()

    # 发送后续消息
    await client_b.query("我的名字和年龄是什么？")

    response_text = ""
    async for msg in client_b.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response_text += block.text
                    print(f"  Client B 响应: {block.text[:100]}")

    await client_b.disconnect()

    # 验证结果
    print("\n[验证结果]")
    if "小明" in response_text and "25" in response_text:
        print("✅ 成功：Client B 通过 resume 参数恢复了 Client A 的上下文")
        print("   -> 不同 Client 可以共享 session")
        return True
    else:
        print("❌ 失败：Client B 无法恢复 Client A 的上下文")
        print(f"   响应内容: {response_text}")
        return False


async def test_concurrent_resume():
    """测试并发场景下的 session 恢复"""
    print("\n" + "=" * 60)
    print("测试：并发场景下的 session 恢复")
    print("=" * 60)

    # 创建基础会话
    print("\n[创建基础会话...]")

    base_options = ClaudeAgentOptions(
        allowed_tools=["Read"],
        permission_mode="acceptEdits"
    )

    base_client = ClaudeSDKClient(options=base_options)
    await base_client.connect()

    await base_client.query("基础信息：项目名称是'智能资料库'，版本是v3.0。")

    base_session_id = None
    async for msg in base_client.receive_response():
        if isinstance(msg, ResultMessage):
            base_session_id = msg.session_id
            print(f"  基础 Session ID: {base_session_id}")

    await base_client.disconnect()

    if not base_session_id:
        print("❌ 错误：未获取到基础 session_id")
        return False

    # 并发恢复会话
    print("\n[并发恢复会话（3个Client同时恢复）...]")

    results = []
    errors = []

    async def concurrent_user(user_id: int):
        """并发用户恢复会话"""
        try:
            options = ClaudeAgentOptions(
                allowed_tools=["Read"],
                permission_mode="acceptEdits",
                resume=base_session_id
            )

            client = ClaudeSDKClient(options=options)
            await client.connect()

            await client.query(f"用户{user_id}：项目名称和版本是什么？")

            response_text = ""
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            response_text += block.text

            await client.disconnect()

            # 验证响应
            correct = "智能资料库" in response_text and "v3.0" in response_text
            results.append((user_id, response_text, correct))
            print(f"  用户{user_id}: {'✅' if correct else '❌'}")

        except Exception as e:
            errors.append((user_id, str(e)))
            print(f"  用户{user_id} 错误: {e}")

    # 并发执行
    tasks = [
        concurrent_user(1),
        concurrent_user(2),
        concurrent_user(3)
    ]

    await asyncio.gather(*tasks, return_exceptions=True)

    # 分析结果
    print("\n[结果分析]")
    success_count = sum(1 for _, _, correct in results if correct)
    total_count = len(results)

    print(f"  成功恢复: {success_count}/{total_count}")
    print(f"  错误数: {len(errors)}")

    if success_count == total_count and len(errors) == 0:
        print("✅ 成功：多个 Client 可以并发恢复同一个 session")
        return True
    else:
        print("❌ 失败：并发恢复有问题")
        return False


async def test_session_isolation():
    """测试不同 session 的隔离性"""
    print("\n" + "=" * 60)
    print("测试：不同 session 的隔离性")
    print("=" * 60)

    # 创建两个独立的会话
    print("\n[创建两个独立会话...]")

    # 会话 A
    client_a = ClaudeSDKClient(ClaudeAgentOptions(
        allowed_tools=["Read"],
        permission_mode="acceptEdits"
    ))
    await client_a.connect()
    await client_a.query("会话A：我的颜色是红色。")
    session_a_id = None
    async for msg in client_a.receive_response():
        if isinstance(msg, ResultMessage):
            session_a_id = msg.session_id
            print(f"  会话A ID: {session_a_id}")
    await client_a.disconnect()

    # 会话 B
    client_b = ClaudeSDKClient(ClaudeAgentOptions(
        allowed_tools=["Read"],
        permission_mode="acceptEdits"
    ))
    await client_b.connect()
    await client_b.query("会话B：我的颜色是蓝色。")
    session_b_id = None
    async for msg in client_b.receive_response():
        if isinstance(msg, ResultMessage):
            session_b_id = msg.session_id
            print(f"  会话B ID: {session_b_id}")
    await client_b.disconnect()

    # 恢复并验证隔离性
    print("\n[验证隔离性...]")

    # 恢复会话 A
    client_a2 = ClaudeSDKClient(ClaudeAgentOptions(
        allowed_tools=["Read"],
        permission_mode="acceptEdits",
        resume=session_a_id
    ))
    await client_a2.connect()
    await client_a2.query("我的颜色是什么？")

    response_a = ""
    async for msg in client_a2.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response_a += block.text
    await client_a2.disconnect()

    # 恢复会话 B
    client_b2 = ClaudeSDKClient(ClaudeAgentOptions(
        allowed_tools=["Read"],
        permission_mode="acceptEdits",
        resume=session_b_id
    ))
    await client_b2.connect()
    await client_b2.query("我的颜色是什么？")

    response_b = ""
    async for msg in client_b2.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    response_b += block.text
    await client_b2.disconnect()

    # 验证
    print(f"\n[验证结果]")
    print(f"  会话A 响应: {response_a[:50]}...")
    print(f"  会话B 响应: {response_b[:50]}...")

    a_correct = "红色" in response_a and "蓝色" not in response_a
    b_correct = "蓝色" in response_b and "红色" not in response_b

    if a_correct and b_correct:
        print("✅ 成功：不同 session 完全隔离")
        return True
    else:
        print("❌ 失败：session 隔离有问题")
        if not a_correct:
            print("   会话A 未获得正确答案'红色'")
        if not b_correct:
            print("   会话B 未获得正确答案'蓝色'")
        return False


async def main():
    print("Session Resume 关键测试")
    print("=" * 60)
    print("\n测试目标：")
    print("1. 验证不同 Client 能否通过 resume 共享 session")
    print("2. 验证并发恢复 session 的可行性")
    print("3. 验证不同 session 的隔离性")

    results = []

    try:
        result1 = await test_resume_across_clients()
        results.append(("跨 Client session 恢复", result1))
    except Exception as e:
        print(f"❌ 测试 1 异常: {e}")
        results.append(("跨 Client session 恢复", False))

    try:
        result2 = await test_concurrent_resume()
        results.append(("并发 session 恢复", result2))
    except Exception as e:
        print(f"❌ 测试 2 异常: {e}")
        results.append(("并发 session 恢复", False))

    try:
        result3 = await test_session_isolation()
        results.append(("session 隔离性", result3))
    except Exception as e:
        print(f"❌ 测试 3 异常: {e}")
        results.append(("session 隔离性", False))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")

    all_passed = all(r[1] for r in results)

    print("\n" + "=" * 60)
    print("技术方案结论")
    print("=" * 60)

    if all_passed:
        print("✅ 所有测试通过！")
        print("\n结论：")
        print("1. 不同 Client 可以通过 resume 参数共享 session")
        print("2. 多个 Client 可以并发恢复同一个 session")
        print("3. 不同 session 完全隔离")
        print("\n✅ 推荐方案：Client Pool + resume 参数")
        print("   - 维护 Client 实例池")
        print("   - 每个请求从池中获取 Client")
        print("   - 使用 resume=session_id 恢复用户会话")
        print("   - 支持真正并发，保持 session 连续性")
    else:
        print("⚠️ 部分测试失败")
        print("\n备选方案：")
        print("1. 全局锁方案（简单但无并发）")
        print("2. 每请求创建 Client（完全隔离但开销大）")


if __name__ == "__main__":
    asyncio.run(main())
