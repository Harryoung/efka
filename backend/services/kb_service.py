"""
Knowledge Base Service - 知识库核心服务
负责管理 Claude SDK Client 和 Agent 配置
"""
import logging
import os
from typing import AsyncIterator, Optional, Any
from pathlib import Path

# Claude Agent SDK 导入
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    Message,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ResultMessage
)

# 导入 Agent 定义
from ..agents.unified_agent import get_unified_agent_definition
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """
    知识库核心服务类

    职责：
    1. 管理 Claude SDK Client（单一Agent架构）
    2. 配置统一智能体
    3. 提供统一的查询接口
    4. 处理会话管理
    """

    def __init__(self):
        """初始化知识库服务"""
        self.settings = get_settings()
        self.client: Optional[ClaudeSDKClient] = None
        self.is_initialized = False

        # 提前设置环境变量到进程级别（在任何 SDK 调用之前）
        self._set_process_env_vars()

        # 配置日志
        self._setup_logging()

    def _set_process_env_vars(self):
        """在进程级别设置环境变量，确保所有 Agent 都能访问"""
        logger.info("=" * 80)
        logger.info("🔍 DEBUG: 设置进程环境变量")
        logger.info("=" * 80)

        # 设置认证环境变量
        if self.settings.CLAUDE_API_KEY:
            os.environ["ANTHROPIC_API_KEY"] = self.settings.CLAUDE_API_KEY
            logger.info(f"✅ 设置 ANTHROPIC_API_KEY = ...{self.settings.CLAUDE_API_KEY[-4:]}")
        else:
            os.environ["ANTHROPIC_AUTH_TOKEN"] = self.settings.ANTHROPIC_AUTH_TOKEN
            logger.info(f"✅ 设置 ANTHROPIC_AUTH_TOKEN = ...{self.settings.ANTHROPIC_AUTH_TOKEN[-4:]}")

            if self.settings.ANTHROPIC_BASE_URL:
                os.environ["ANTHROPIC_BASE_URL"] = self.settings.ANTHROPIC_BASE_URL
                logger.info(f"✅ 设置 ANTHROPIC_BASE_URL = {self.settings.ANTHROPIC_BASE_URL}")

        # 验证环境变量已设置
        logger.info("\n🔍 验证 os.environ 中的环境变量:")
        if "ANTHROPIC_API_KEY" in os.environ:
            logger.info(f"  ✅ os.environ['ANTHROPIC_API_KEY'] = ...{os.environ['ANTHROPIC_API_KEY'][-4:]}")
        if "ANTHROPIC_AUTH_TOKEN" in os.environ:
            logger.info(f"  ✅ os.environ['ANTHROPIC_AUTH_TOKEN'] = ...{os.environ['ANTHROPIC_AUTH_TOKEN'][-4:]}")
        if "ANTHROPIC_BASE_URL" in os.environ:
            logger.info(f"  ✅ os.environ['ANTHROPIC_BASE_URL'] = {os.environ['ANTHROPIC_BASE_URL']}")

        logger.info("=" * 80)

    def _setup_logging(self):
        """配置日志系统"""
        log_level = logging.DEBUG if self.settings.DEBUG else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(
                    Path(self.settings.KB_ROOT_PATH).parent / "backend" / "logs" / "kb_service.log"
                ),
                logging.StreamHandler()
            ]
        )
        logger.info("知识库服务日志系统已初始化")

    async def initialize(self):
        """
        初始化 Claude SDK Client
        """
        if self.is_initialized:
            logger.warning("知识库服务已经初始化，跳过重复初始化")
            return

        try:
            # 检查 API Key（支持 CLAUDE_API_KEY 或 ANTHROPIC_AUTH_TOKEN）
            if not self.settings.CLAUDE_API_KEY and not self.settings.ANTHROPIC_AUTH_TOKEN:
                raise ValueError(
                    "未配置认证信息，请在 .env 文件中配置 CLAUDE_API_KEY 或 ANTHROPIC_AUTH_TOKEN"
                )

            # 检查知识库路径
            kb_path = Path(self.settings.KB_ROOT_PATH)
            if not kb_path.exists():
                logger.warning(f"知识库路径不存在，将创建: {kb_path}")
                kb_path.mkdir(parents=True, exist_ok=True)

            logger.info(f"知识库路径: {kb_path}")

            # 在进程环境变量中设置知识库路径
            os.environ["KB_ROOT_PATH"] = str(kb_path)

            # 日志显示认证方式（环境变量已在 __init__ 中设置）
            if self.settings.CLAUDE_API_KEY:
                logger.info(f"认证方式: CLAUDE_API_KEY ({'*' * 20}{self.settings.CLAUDE_API_KEY[-4:]})")
            else:
                logger.info(f"认证方式: ANTHROPIC_AUTH_TOKEN ({'*' * 20}{self.settings.ANTHROPIC_AUTH_TOKEN[-4:]})")
                logger.info(f"Base URL: {self.settings.ANTHROPIC_BASE_URL}")

            logger.info("✅ 认证环境变量已在进程启动时设置")

            # 准备传递给 SDK 的环境变量
            env_vars = {
                "KB_ROOT_PATH": str(kb_path),
            }

            # 设置认证环境变量
            if self.settings.CLAUDE_API_KEY:
                env_vars["ANTHROPIC_API_KEY"] = self.settings.CLAUDE_API_KEY
            else:
                env_vars["ANTHROPIC_AUTH_TOKEN"] = self.settings.ANTHROPIC_AUTH_TOKEN
                if self.settings.ANTHROPIC_BASE_URL:
                    env_vars["ANTHROPIC_BASE_URL"] = self.settings.ANTHROPIC_BASE_URL

            # 获取统一 Agent 的 prompt（注入配置参数）
            unified_agent_def = get_unified_agent_definition(
                small_file_threshold_kb=self.settings.SMALL_FILE_KB_THRESHOLD,
                faq_max_entries=self.settings.FAQ_MAX_ENTRIES
            )

            logger.info("\n" + "=" * 80)
            logger.info("🔍 DEBUG: 创建 ClaudeAgentOptions（单一Agent架构）")
            logger.info("=" * 80)
            logger.info(f"传递给 SDK 的 env 参数:")
            for key, value in env_vars.items():
                if key in ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_API_KEY"]:
                    logger.info(f"  {key} = ...{value[-4:]}")
                else:
                    logger.info(f"  {key} = {value}")
            logger.info("=" * 80)

            # 配置 MCP servers（markitdown 文档转换服务）
            mcp_servers = {
                "markitdown": {
                    "type": "stdio",
                    "command": "markitdown-mcp",
                    "args": []
                }
            }

            # 创建 Claude Agent Options（单一Agent架构）
            options = ClaudeAgentOptions(
                # 使用 claude_code preset 并添加统一 Agent 的指令
                system_prompt={
                    "type": "preset",
                    "preset": "claude_code",
                    "append": f"\n\n{unified_agent_def.prompt}"
                },

                # 不注册子 Agents（单一Agent架构）
                agents=None,

                # 配置 MCP servers
                mcp_servers=mcp_servers,

                # 完全整合的工具集（移除Task，添加所有功能工具）
                allowed_tools=[
                    "Read",   # 读取文件
                    "Write",  # 写入文件
                    "Grep",   # 搜索内容
                    "Glob",   # 查找文件
                    "Bash",   # 执行命令
                    "mcp__markitdown__convert_to_markdown"  # markitdown MCP 工具
                ],

                # 工作目录（设置为项目根目录，这样可以访问 knowledge_base/）
                cwd=str(kb_path.parent),

                # 权限模式：自动接受编辑
                permission_mode="acceptEdits",

                # 环境变量
                env=env_vars,

                # 不加载文件系统配置（完全编程式配置）
                setting_sources=None
            )

            logger.info("\n✅ ClaudeAgentOptions 创建完成（单一Agent架构）")
            logger.info(f"✅ MCP Servers: {list(mcp_servers.keys())}")

            # 创建 Client
            self.client = ClaudeSDKClient(options=options)

            # 连接（不传入初始 prompt，等待用户查询）
            await self.client.connect()

            self.is_initialized = True
            logger.info("✅ 知识库服务初始化成功")
            logger.info(f"✅ 工作目录: {options.cwd}")
            logger.info(f"✅ 单一 Agent 架构：Unified Intelligent KB Agent")
            logger.info(f"✅ 可用工具: {', '.join(options.allowed_tools)}")
            logger.info(f"✅ MCP Servers 已加载: {', '.join(mcp_servers.keys())}")

        except Exception as e:
            logger.error(f"❌ 知识库服务初始化失败: {e}")
            raise

    async def query(
        self,
        user_message: str,
        session_id: str = "default"
    ) -> AsyncIterator[Message]:
        """
        查询知识库

        Args:
            user_message: 用户消息
            session_id: 会话ID（用于多会话管理）

        Yields:
            消息流

        Example:
            async for message in kb_service.query("如何配置CORS?"):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(block.text)
        """
        if not self.is_initialized:
            raise RuntimeError("服务未初始化，请先调用 initialize()")

        try:
            # 记录完整的用户输入
            logger.info(f"📝 收到查询 [会话: {session_id}]")
            logger.info(f"{'='*80}")
            logger.info(f"用户输入:\n{user_message}")
            logger.info(f"{'='*80}")

            # 发送查询到 Claude（带会话ID）
            await self.client.query(user_message, session_id=session_id)

            # 接收响应
            turn_number = 0
            async for message in self.client.receive_response():
                # 详细记录每条消息
                if isinstance(message, AssistantMessage):
                    turn_number += 1
                    logger.info(f"\n{'─'*80}")
                    logger.info(f"🤖 Agent 响应 - Turn {turn_number} [会话: {session_id}]")
                    logger.info(f"{'─'*80}")

                    for block in message.content:
                        if isinstance(block, TextBlock):
                            logger.info(f"📄 文本输出:\n{block.text}")
                        elif isinstance(block, ToolUseBlock):
                            logger.info(f"🔧 工具调用: {block.name}")
                            logger.info(f"   参数: {block.input}")

                    logger.info(f"{'─'*80}\n")

                else:
                    # 记录其他类型的消息（可能包含工具结果）
                    message_type = type(message).__name__
                    logger.info(f"\n{'┄'*80}")
                    logger.info(f"📦 消息类型: {message_type} [会话: {session_id}]")

                    # 尝试提取工具结果
                    if hasattr(message, 'content'):
                        logger.info(f"📋 消息内容:")
                        if isinstance(message.content, list):
                            for idx, block in enumerate(message.content):
                                block_type = type(block).__name__
                                logger.info(f"   Block {idx} 类型: {block_type}")

                                # 打印 block 的所有属性
                                if hasattr(block, '__dict__'):
                                    for key, value in block.__dict__.items():
                                        if not key.startswith('_'):
                                            # 如果值太长，截断显示
                                            value_str = str(value)
                                            if len(value_str) > 500:
                                                value_str = value_str[:500] + f"... (truncated, total {len(value_str)} chars)"
                                            logger.info(f"      {key}: {value_str}")
                        else:
                            content_str = str(message.content)
                            if len(content_str) > 1000:
                                content_str = content_str[:1000] + f"... (truncated, total {len(content_str)} chars)"
                            logger.info(f"   {content_str}")

                    # 打印消息对象的所有属性
                    if hasattr(message, '__dict__'):
                        logger.info(f"📊 消息属性:")
                        for key, value in message.__dict__.items():
                            if not key.startswith('_') and key != 'content':
                                logger.info(f"   {key}: {value}")

                    logger.info(f"{'┄'*80}\n")

                yield message

                # 记录最终结果
                if isinstance(message, ResultMessage):
                    logger.info(f"\n{'='*80}")
                    logger.info(
                        f"✅ 查询完成 [会话: {session_id}] "
                        f"耗时: {message.duration_ms}ms "
                        f"轮次: {message.num_turns}"
                    )
                    logger.info(f"{'='*80}\n")

        except Exception as e:
            logger.error(f"❌ 查询失败: {e}")
            raise

    async def close(self):
        """关闭服务，释放资源"""
        if self.client:
            try:
                await self.client.disconnect()
                logger.info("✅ 知识库服务已关闭")
            except Exception as e:
                logger.error(f"❌ 关闭服务失败: {e}")
        self.is_initialized = False

    async def __aenter__(self):
        """支持 async with 语法"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """支持 async with 语法"""
        await self.close()

    def get_agent_info(self) -> dict:
        """
        获取 Agent 信息

        Returns:
            Agent 配置信息
        """
        unified_agent_def = get_unified_agent_definition(
            small_file_threshold_kb=self.settings.SMALL_FILE_KB_THRESHOLD,
            faq_max_entries=self.settings.FAQ_MAX_ENTRIES
        )
        return {
            "architecture": "single_agent",
            "agent": {
                "name": "Unified Intelligent KB Agent",
                "description": unified_agent_def.description,
                "tools": unified_agent_def.tools,
                "model": unified_agent_def.model
            },
            "config": {
                "small_file_threshold_kb": self.settings.SMALL_FILE_KB_THRESHOLD,
                "faq_max_entries": self.settings.FAQ_MAX_ENTRIES
            }
        }

    def get_service_status(self) -> dict:
        """
        获取服务状态

        Returns:
            服务状态信息
        """
        return {
            "initialized": self.is_initialized,
            "architecture": "single_agent",
            "kb_path": str(self.settings.KB_ROOT_PATH),
            "api_key_configured": bool(self.settings.CLAUDE_API_KEY)
        }


# 单例实例
_kb_service_instance: Optional[KnowledgeBaseService] = None


def get_kb_service() -> KnowledgeBaseService:
    """
    获取知识库服务单例

    Returns:
        KnowledgeBaseService 实例
    """
    global _kb_service_instance
    if _kb_service_instance is None:
        _kb_service_instance = KnowledgeBaseService()
    return _kb_service_instance


# 导出
__all__ = [
    "KnowledgeBaseService",
    "get_kb_service"
]
