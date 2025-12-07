"""
测试：不同 ClaudeSDKClient 实例是否能共享同一个 session_id 恢复上下文

验证场景：
1. Client A 发送消息，记录 session_id
2. 断开 Client A
3. 创建 Client B，使用相同 session_id 发送后续消息
4. 验证 Client B 是否能访问 Client A 的上下文

运行方式：
    source venv/bin/activate
    python scripts/test_session_sharing.py
"""

import asyncio
import os
import sys

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage


async def test_resume_parameter():
    """测试通过 resume 参数恢复会话（跨 Client）"""

    print("=" * 60)
    print("测试 1：通过 resume 参数恢复会话")
    print("=" * 60)

    options = ClaudeAgentOptions(
        allowed_tools=["Read"],
        permission_mode="acceptEdits"
    )

    session_id = None

    # Step 1: Client A 发送消息
    print("\n[Step 1] Client A 发送消息...")

    client_a = ClaudeSDKClient(options=options)
    await client_a.connect()

    await client_a.query("我的名字是小明，请记住这个信息。只需要回复：好的，我记住了。")

    async for msg in client_a.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(f"  Client A 响应: {block.text[:100]}")
        elif isinstance(msg, ResultMessage):
            session_id = msg.session_id
            print(f"  Session ID: {session_id}")

    await client_a.disconnect()
    print("  Client A 已断开\n")

    if not session_id:
        print("❌ 错误：未获取到 session_id")
        return False

    # Step 2: Client B 使用 resume 参数恢复会话
    print(f"[Step 2] Client B 使用 resume={session_id} 恢复会话...")

    options_b = ClaudeAgentOptions(
        allowed_tools=["Read"],
        permission_mode="acceptEdits",
        resume=session_id
    )

    client_b = ClaudeSDKClient(options=options_b)
    await client_b.connect()

    await client_b.query("请问我的名字是什么？只需要回复名字。")

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
    if "小明" in response_text:
        print("✅ 成功：通过 resume 参数，Client B 能够访问 Client A 的上下文")
        return True
    else:
        print("❌ 失败：Client B 无法访问 Client A 的上下文")
        print(f"   响应内容: {response_text}")
        return False


async def test_session_id_parameter():
    """测试通过 query 的 session_id 参数实现会话共享"""

    print("\n" + "=" * 60)
    print("测试 2：通过 query(session_id) 参数共享会话")
    print("=" * 60)

    options = ClaudeAgentOptions(
        allowed_tools=["Read"],
        permission_mode="acceptEdits"
    )

    custom_session_id = f"test-session-{os.urandom(4).hex()}"

    # Step 1: Client A 发送消息
    print(f"\n[Step 1] Client A 使用 session_id={custom_session_id}...")

    client_a = ClaudeSDKClient(options=options)
    await client_a.connect()

    await client_a.query(
        "我的宠物是一只名叫旺财的狗。只需要回复：好的，我记住了。",
        session_id=custom_session_id
    )

    async for msg in client_a.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(f"  Client A 响应: {block.text[:100]}")

    await client_a.disconnect()
    print("  Client A 已断开\n")

    # Step 2: Client B 使用相同 session_id
    print(f"[Step 2] Client B 使用相同 session_id={custom_session_id}...")

    client_b = ClaudeSDKClient(options=options)
    await client_b.connect()

    await client_b.query(
        "我的宠物叫什么名字？只需要回复名字。",
        session_id=custom_session_id
    )

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
    if "旺财" in response_text:
        print("✅ 成功：通过 session_id 参数，不同 Client 可以共享会话上下文")
        return True
    else:
        print("❌ 失败：session_id 参数无法实现跨 Client 会话共享")
        print(f"   响应内容: {response_text}")
        return False


async def test_concurrent_clients():
    """测试并发场景下不同 Client 的隔离性"""

    print("\n" + "=" * 60)
    print("测试 3：并发场景下不同 Client 的隔离性")
    print("=" * 60)

    options = ClaudeAgentOptions(
        allowed_tools=["Read"],
        permission_mode="acceptEdits"
    )

    session_a = f"session-a-{os.urandom(4).hex()}"
    session_b = f"session-b-{os.urandom(4).hex()}"

    results = {}

    async def user_a_conversation():
        """用户 A 的对话"""
        client = ClaudeSDKClient(options=options)
        await client.connect()

        # 第一轮
        await client.query("我是用户A，我的幸运数字是888。只回复：好的。", session_id=session_a)
        async for msg in client.receive_response():
            pass

        # 第二轮
        await client.query("我的幸运数字是多少？只回复数字。", session_id=session_a)
        response = ""
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response += block.text

        await client.disconnect()
        results["user_a"] = response

    async def user_b_conversation():
        """用户 B 的对话"""
        client = ClaudeSDKClient(options=options)
        await client.connect()

        # 第一轮
        await client.query("我是用户B，我的幸运数字是666。只回复：好的。", session_id=session_b)
        async for msg in client.receive_response():
            pass

        # 第二轮
        await client.query("我的幸运数字是多少？只回复数字。", session_id=session_b)
        response = ""
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response += block.text

        await client.disconnect()
        results["user_b"] = response

    print("\n[并发执行两个用户的对话...]")

    # 并发执行
    await asyncio.gather(
        user_a_conversation(),
        user_b_conversation()
    )

    print(f"\n[结果]")
    print(f"  用户 A 响应: {results.get('user_a', 'N/A')}")
    print(f"  用户 B 响应: {results.get('user_b', 'N/A')}")

    # 验证
    a_correct = "888" in results.get("user_a", "")
    b_correct = "666" in results.get("user_b", "")

    print("\n[验证结果]")
    if a_correct and b_correct:
        print("✅ 成功：并发场景下，不同 session 完全隔离")
        return True
    else:
        print("❌ 失败：会话可能发生混淆")
        if not a_correct:
            print("   用户 A 未获得正确答案 888")
        if not b_correct:
            print("   用户 B 未获得正确答案 666")
        return False


async def main():
    print("=" * 60)
    print("Claude SDK Session 共享测试")
    print("=" * 60)
    print("\n此测试验证 Client Pool 方案的关键假设：")
    print("- 不同 ClaudeSDKClient 实例能否共享 session_id")
    print("- 并发场景下不同 session 是否完全隔离")
    print()

    results = []

    # 测试 1：resume 参数
    try:
        result1 = await test_resume_parameter()
        results.append(("resume 参数", result1))
    except Exception as e:
        print(f"❌ 测试 1 异常: {e}")
        results.append(("resume 参数", False))

    # 测试 2：session_id 参数
    try:
        result2 = await test_session_id_parameter()
        results.append(("session_id 参数", result2))
    except Exception as e:
        print(f"❌ 测试 2 异常: {e}")
        results.append(("session_id 参数", False))

    # 测试 3：并发隔离性
    try:
        result3 = await test_concurrent_clients()
        results.append(("并发隔离性", result3))
    except Exception as e:
        print(f"❌ 测试 3 异常: {e}")
        results.append(("并发隔离性", False))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")

    all_passed = all(r[1] for r in results)
    print()
    if all_passed:
        print("🎉 所有测试通过！Client Pool 方案可行。")
    else:
        print("⚠️ 部分测试失败，需要重新评估方案。")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
