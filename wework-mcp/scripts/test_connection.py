"""
测试企业微信连接和配置
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from wework_mcp.config import WeWorkConfig
from wework_mcp.weework_client import WeWorkClient


def main():
    # 加载环境变量
    load_dotenv()

    print("=" * 60)
    print("WeWork MCP Connection Test")
    print("=" * 60)

    try:
        # 加载配置
        print("\n1. Loading configuration...")
        config = WeWorkConfig.from_env()
        config.validate()
        print(f"   ✅ Corp ID: {config.corp_id}")
        print(f"   ✅ Agent ID: {config.agent_id}")
        print(f"   ✅ Secret: {'*' * 28}{config.corp_secret[-4:]}")

        # 初始化客户端
        print("\n2. Initializing WeWork client...")
        client = WeWorkClient(config)
        print("   ✅ Client initialized")

        # 获取 access token
        print("\n3. Fetching access token...")
        token = client.token_manager.get_token()
        print(f"   ✅ Token obtained: {token[:20]}...")

        # 发送测试消息（可选，取消注释以测试）
        # print("\n4. Sending test message...")
        # result = client.send_text(
        #     touser="@all",  # 或指定测试用户ID
        #     content="🤖 WeWork MCP 服务连接测试成功！\n\n这是一条测试消息。"
        # )
        # print(f"   ✅ Message sent, msgid: {result.get('msgid')}")

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
