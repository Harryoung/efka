"""
KB Service Factory - 知识库服务工厂

管理Employee Agent和Admin Agent两个独立的Agent SDK客户端
支持未来拆分为微服务（仅需修改此文件的实现）
"""

import logging
import os
import asyncio
from typing import AsyncIterator, Optional
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    Message
)

from backend.agents.kb_qa_agent import get_employee_agent_definition
from backend.agents.kb_admin_agent import get_admin_agent_definition
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)


class KBEmployeeService:
    """
    员工端知识库服务

    职责:
    - 知识查询(6阶段检索)
    - 满意度反馈
    - 领域专家路由
    - 异步多轮对话管理

    特点:
    - 轻量级(无markitdown MCP)
    - 企业微信MCP集成
    """

    def __init__(self):
        """初始化员工端服务"""
        self.settings = get_settings()
        self.client: Optional[ClaudeSDKClient] = None
        self.is_initialized = False

        logger.info("KBEmployeeService instance created")

    async def initialize(self):
        """初始化Employee Agent SDK客户端"""
        if self.is_initialized:
            logger.warning("Employee service already initialized")
            return

        try:
            # 检查认证
            if not self.settings.CLAUDE_API_KEY and not self.settings.ANTHROPIC_AUTH_TOKEN:
                raise ValueError("Missing authentication: CLAUDE_API_KEY or ANTHROPIC_AUTH_TOKEN")

            # 知识库路径
            kb_path = Path(self.settings.KB_ROOT_PATH)
            if not kb_path.exists():
                kb_path.mkdir(parents=True, exist_ok=True)

            # 准备环境变量
            env_vars = {
                "KB_ROOT_PATH": str(kb_path),
            }

            if self.settings.CLAUDE_API_KEY:
                env_vars["ANTHROPIC_API_KEY"] = self.settings.CLAUDE_API_KEY
            else:
                env_vars["ANTHROPIC_AUTH_TOKEN"] = self.settings.ANTHROPIC_AUTH_TOKEN
                if self.settings.ANTHROPIC_BASE_URL:
                    env_vars["ANTHROPIC_BASE_URL"] = self.settings.ANTHROPIC_BASE_URL

            # 获取Employee Agent定义
            employee_agent_def = get_employee_agent_definition(
                small_file_threshold_kb=self.settings.SMALL_FILE_KB_THRESHOLD,
                faq_max_entries=self.settings.FAQ_MAX_ENTRIES
            )

            # 配置MCP servers (仅wework)
            mcp_servers = {
                "wework": {
                    "type": "stdio",
                    "command": "wework-mcp",
                    "args": [],
                    "env": {
                        "WEWORK_CORP_ID": os.getenv("WEWORK_CORP_ID", ""),
                        "WEWORK_CORP_SECRET": os.getenv("WEWORK_CORP_SECRET", ""),
                        "WEWORK_AGENT_ID": os.getenv("WEWORK_AGENT_ID", ""),
                    }
                }
            }

            # 创建Claude Agent Options
            options = ClaudeAgentOptions(
                system_prompt={
                    "type": "preset",
                    "preset": "claude_code",
                    "append": f"\n\n{employee_agent_def.prompt}"
                },
                agents=None,  # 单一Agent架构
                mcp_servers=mcp_servers,
                allowed_tools=[
                    "Read",
                    "Grep",
                    "Glob",
                    "Write",
                    "Bash",
                    # WeWork MCP tools
                    "mcp__wework__wework_send_text_message",
                    "mcp__wework__wework_send_markdown_message",
                    "mcp__wework__wework_send_image_message",
                    "mcp__wework__wework_send_file_message",
                    "mcp__wework__wework_upload_media",
                ],
                cwd=str(kb_path.parent),  # 项目根目录
                permission_mode="acceptEdits",
                env=env_vars,
                setting_sources=None
            )

            # 创建客户端
            self.client = ClaudeSDKClient(options=options)

            # 连接到Claude API（可能因欠费/无效API key失败）
            try:
                logger.info("Connecting to Claude API...")
                await self.client.connect()
                logger.info("✅ Claude API connection successful")
            except Exception as conn_error:
                logger.error("❌ Failed to connect to Claude API")
                logger.error(f"   Error type: {type(conn_error).__name__}")
                logger.error(f"   Error message: {str(conn_error)}")
                logger.error(f"   This may indicate:")
                logger.error(f"   - Invalid API key (CLAUDE_API_KEY or ANTHROPIC_AUTH_TOKEN)")
                logger.error(f"   - API account insufficent balance (欠费)")
                logger.error(f"   - Network connectivity issues")
                logger.error(f"   - API service unavailable")
                raise

            self.is_initialized = True
            logger.info("✅ Employee service initialized successfully")
            logger.info(f"   MCP Servers: {list(mcp_servers.keys())}")
            logger.info(f"   Tools: {len(options.allowed_tools)}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize employee service: {e}")
            raise

    async def query(
        self,
        user_message: str,
        session_id: str = "default",
        user_id: Optional[str] = None
    ) -> AsyncIterator[Message]:
        """
        处理员工查询

        Args:
            user_message: 用户消息
            session_id: Claude session ID
            user_id: 用户WeChat Work UserID (可选)

        Yields:
            Message流
        """
        if not self.is_initialized:
            await self.initialize()

        logger.info(f"Employee query from {user_id or 'unknown'}: {user_message[:100]}...")

        try:
            message_count = 0
            # 使用正确的 Claude SDK API
            await self.client.query(user_message, session_id=session_id)
            async for message in self.client.receive_response():
                message_count += 1
                yield message

            # 检查是否收到响应
            if message_count == 0:
                logger.error("❌ No response from Claude API")
                logger.error(f"   Session ID: {session_id}")
                logger.error(f"   User ID: {user_id}")
                logger.error(f"   This may indicate:")
                logger.error(f"   - API account insufficent balance (欠费)")
                logger.error(f"   - API rate limit exceeded")
                logger.error(f"   - Network timeout")
            else:
                logger.info(f"✅ Received {message_count} messages from Claude API")

        except asyncio.TimeoutError:
            logger.error("❌ Claude API call timeout")
            logger.error(f"   Session ID: {session_id}")
            logger.error(f"   User ID: {user_id}")
            logger.error(f"   This may indicate:")
            logger.error(f"   - Network connectivity issues")
            logger.error(f"   - API service overload")
            raise
        except Exception as e:
            logger.error("❌ Claude API call failed")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Error message: {str(e)}")
            logger.error(f"   Session ID: {session_id}")
            logger.error(f"   User ID: {user_id}")
            logger.error(f"   This may indicate:")
            logger.error(f"   - Invalid API key or token")
            logger.error(f"   - API account insufficent balance (欠费)")
            logger.error(f"   - Exceeded rate limits")
            logger.error(f"   - API service unavailable")
            raise


class KBAdminService:
    """
    管理员端知识库服务

    职责:
    - 文档入库(5阶段处理)
    - 知识库管理
    - 批量员工通知

    特点:
    - 完整功能(markitdown + wework MCP)
    - SSE流式响应支持
    """

    def __init__(self):
        """初始化管理员端服务"""
        self.settings = get_settings()
        self.client: Optional[ClaudeSDKClient] = None
        self.is_initialized = False

        logger.info("KBAdminService instance created")

    async def initialize(self):
        """初始化Admin Agent SDK客户端"""
        if self.is_initialized:
            logger.warning("Admin service already initialized")
            return

        try:
            # 检查认证
            if not self.settings.CLAUDE_API_KEY and not self.settings.ANTHROPIC_AUTH_TOKEN:
                raise ValueError("Missing authentication: CLAUDE_API_KEY or ANTHROPIC_AUTH_TOKEN")

            # 知识库路径
            kb_path = Path(self.settings.KB_ROOT_PATH)
            if not kb_path.exists():
                kb_path.mkdir(parents=True, exist_ok=True)

            # 准备环境变量
            env_vars = {
                "KB_ROOT_PATH": str(kb_path),
            }

            if self.settings.CLAUDE_API_KEY:
                env_vars["ANTHROPIC_API_KEY"] = self.settings.CLAUDE_API_KEY
            else:
                env_vars["ANTHROPIC_AUTH_TOKEN"] = self.settings.ANTHROPIC_AUTH_TOKEN
                if self.settings.ANTHROPIC_BASE_URL:
                    env_vars["ANTHROPIC_BASE_URL"] = self.settings.ANTHROPIC_BASE_URL

            # 获取Admin Agent定义
            admin_agent_def = get_admin_agent_definition(
                small_file_threshold_kb=self.settings.SMALL_FILE_KB_THRESHOLD,
                faq_max_entries=self.settings.FAQ_MAX_ENTRIES
            )

            # 配置MCP servers (markitdown + wework)
            mcp_servers = {
                "markitdown": {
                    "type": "stdio",
                    "command": "markitdown-mcp",
                    "args": []
                },
                "wework": {
                    "type": "stdio",
                    "command": "wework-mcp",
                    "args": [],
                    "env": {
                        "WEWORK_CORP_ID": os.getenv("WEWORK_CORP_ID", ""),
                        "WEWORK_CORP_SECRET": os.getenv("WEWORK_CORP_SECRET", ""),
                        "WEWORK_AGENT_ID": os.getenv("WEWORK_AGENT_ID", ""),
                    }
                }
            }

            # 创建Claude Agent Options
            options = ClaudeAgentOptions(
                system_prompt={
                    "type": "preset",
                    "preset": "claude_code",
                    "append": f"\n\n{admin_agent_def.prompt}"
                },
                agents=None,  # 单一Agent架构
                mcp_servers=mcp_servers,
                allowed_tools=[
                    "Read",
                    "Write",
                    "Grep",
                    "Glob",
                    "Bash",
                    # Markitdown MCP
                    "mcp__markitdown__convert_to_markdown",
                    # WeWork MCP tools
                    "mcp__wework__wework_send_text_message",
                    "mcp__wework__wework_send_markdown_message",
                    "mcp__wework__wework_send_image_message",
                    "mcp__wework__wework_send_file_message",
                    "mcp__wework__wework_upload_media",
                ],
                cwd=str(kb_path.parent),  # 项目根目录
                permission_mode="acceptEdits",
                env=env_vars,
                setting_sources=None
            )

            # 创建客户端
            self.client = ClaudeSDKClient(options=options)

            # 连接到Claude API（可能因欠费/无效API key失败）
            try:
                logger.info("Connecting to Claude API...")
                await self.client.connect()
                logger.info("✅ Claude API connection successful")
            except Exception as conn_error:
                logger.error("❌ Failed to connect to Claude API")
                logger.error(f"   Error type: {type(conn_error).__name__}")
                logger.error(f"   Error message: {str(conn_error)}")
                logger.error(f"   This may indicate:")
                logger.error(f"   - Invalid API key (CLAUDE_API_KEY or ANTHROPIC_AUTH_TOKEN)")
                logger.error(f"   - API account insufficent balance (欠费)")
                logger.error(f"   - Network connectivity issues")
                logger.error(f"   - API service unavailable")
                raise

            self.is_initialized = True
            logger.info("✅ Admin service initialized successfully")
            logger.info(f"   MCP Servers: {list(mcp_servers.keys())}")
            logger.info(f"   Tools: {len(options.allowed_tools)}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize admin service: {e}")
            raise

    async def query(
        self,
        user_message: str,
        session_id: str = "default"
    ) -> AsyncIterator[Message]:
        """
        处理管理员查询

        Args:
            user_message: 用户消息
            session_id: Claude session ID

        Yields:
            Message流 (支持SSE流式响应)
        """
        if not self.is_initialized:
            await self.initialize()

        logger.info(f"Admin query: {user_message[:100]}...")

        try:
            message_count = 0
            # 使用正确的 Claude SDK API
            await self.client.query(user_message, session_id=session_id)
            async for message in self.client.receive_response():
                message_count += 1
                yield message

            # 检查是否收到响应
            if message_count == 0:
                logger.error("❌ No response from Claude API")
                logger.error(f"   Session ID: {session_id}")
                logger.error(f"   This may indicate:")
                logger.error(f"   - API account insufficent balance (欠费)")
                logger.error(f"   - API rate limit exceeded")
                logger.error(f"   - Network timeout")
            else:
                logger.info(f"✅ Received {message_count} messages from Claude API")

        except asyncio.TimeoutError:
            logger.error("❌ Claude API call timeout")
            logger.error(f"   Session ID: {session_id}")
            logger.error(f"   This may indicate:")
            logger.error(f"   - Network connectivity issues")
            logger.error(f"   - API service overload")
            raise
        except Exception as e:
            logger.error("❌ Claude API call failed")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Error message: {str(e)}")
            logger.error(f"   Session ID: {session_id}")
            logger.error(f"   This may indicate:")
            logger.error(f"   - Invalid API key or token")
            logger.error(f"   - API account insufficent balance (欠费)")
            logger.error(f"   - Exceeded rate limits")
            logger.error(f"   - API service unavailable")
            raise


class KBServiceFactory:
    """
    知识库服务工厂

    管理Employee和Admin两个独立的Agent服务
    采用单例模式,预留未来拆分为微服务的扩展点

    未来演进路径:
    - 当前: 单一进程,两个Agent客户端
    - 未来: 可改为HTTP客户端,调用独立的微服务
    """

    _employee_service: Optional[KBEmployeeService] = None
    _admin_service: Optional[KBAdminService] = None

    @classmethod
    def get_employee_service(cls) -> KBEmployeeService:
        """
        获取员工端服务单例

        Returns:
            KBEmployeeService实例
        """
        if cls._employee_service is None:
            cls._employee_service = KBEmployeeService()
            logger.info("Created new Employee service instance")

        return cls._employee_service

    @classmethod
    def get_admin_service(cls) -> KBAdminService:
        """
        获取管理员端服务单例

        Returns:
            KBAdminService实例
        """
        if cls._admin_service is None:
            cls._admin_service = KBAdminService()
            logger.info("Created new Admin service instance")

        return cls._admin_service

    @classmethod
    async def initialize_all(cls):
        """初始化所有服务"""
        employee = cls.get_employee_service()
        admin = cls.get_admin_service()

        await employee.initialize()
        await admin.initialize()

        logger.info("✅ All KB services initialized")


# 便捷函数(向后兼容)
def get_employee_service() -> KBEmployeeService:
    """获取员工端服务"""
    return KBServiceFactory.get_employee_service()


def get_admin_service() -> KBAdminService:
    """获取管理员端服务"""
    return KBServiceFactory.get_admin_service()


__all__ = [
    'KBServiceFactory',
    'KBEmployeeService',
    'KBAdminService',
    'get_employee_service',
    'get_admin_service'
]
