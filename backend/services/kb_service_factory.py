"""
KB Service Factory - 知识库服务工厂

管理User Agent和Admin Agent两个独立的Agent SDK客户端
支持未来拆分为微服务（仅需修改此文件的实现）

并发支持：使用 SDKClientPool 实现多用户真正并发
- 每个请求独占一个 Client
- 通过 resume 参数恢复用户 session
- 使用后归还到池中
"""

import logging
import os
import asyncio
from typing import AsyncIterator, Optional, Callable
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    Message,
    create_sdk_mcp_server
)

from backend.agents.kb_qa_agent import get_user_agent_definition
from backend.agents.kb_admin_agent import get_admin_agent_definition
from backend.config.settings import get_settings
from backend.config.run_mode import get_run_mode, get_im_channel, is_standalone
from backend.tools.image_read import image_read_handler
from backend.services.client_pool import SDKClientPool, get_pool_manager

logger = logging.getLogger(__name__)


class KBUserService:
    """
    用户端知识库服务

    职责:
    - 知识查询(6阶段检索)
    - 满意度反馈
    - 领域专家路由
    - 异步多轮对话管理

    特点:
    - 轻量级(无文档转换功能)
    - 企业微信MCP集成

    并发支持:
    - 使用 SDKClientPool 实现真正并发
    - 每个请求独占一个 Client
    - 通过 resume 参数恢复用户 session
    """

    def __init__(self):
        """初始化用户端服务"""
        self.settings = get_settings()
        self.client_pool: Optional[SDKClientPool] = None
        self.is_initialized = False

        # 缓存 MCP servers 配置（在 initialize 中设置）
        self._mcp_servers = None
        self._env_vars = None
        self._user_agent_def = None

        logger.info("KBUserService instance created")

    def _get_allowed_tools(self) -> list:
        """根据运行模式获取允许的工具列表"""
        tools = [
            "Read",
            "Grep",
            "Glob",
            "Write",
            "Bash",
            "Skill",  # Enable Claude Code Skills
            # Image Vision MCP tool
            "mcp__image_vision__image_read",
        ]

        # IM 模式下添加对应渠道的工具
        im_channel = get_im_channel()
        if im_channel:
            tools.extend([
                f"mcp__{im_channel}__send_text_message",
                f"mcp__{im_channel}__send_markdown_message",
                f"mcp__{im_channel}__send_image_message",
                f"mcp__{im_channel}__send_file_message",
                f"mcp__{im_channel}__upload_media",
            ])

        return tools

    def _get_im_mcp_command(self, channel: str) -> str:
        """获取 IM MCP 命令路径"""
        import sys
        import shutil

        mcp_name = f"{channel}-mcp"
        mcp_path = shutil.which(mcp_name)
        if not mcp_path:
            venv_path = Path(sys.executable).parent / mcp_name
            if venv_path.exists():
                mcp_path = str(venv_path)
            else:
                logger.warning(f"{mcp_name} not found in PATH or venv, using '{mcp_name}' (may fail)")
                mcp_path = mcp_name

        return mcp_path

    def _create_options(self, sdk_session_id: Optional[str] = None) -> ClaudeAgentOptions:
        """
        创建 ClaudeAgentOptions（Options Factory）

        Args:
            sdk_session_id: SDK 返回的真实 session ID（可选）
                           - None: 新会话，不设置 resume
                           - str: 已有会话，设置 resume 恢复会话

        Returns:
            配置好的 ClaudeAgentOptions
        """
        kb_path = Path(self.settings.KB_ROOT_PATH)

        options = ClaudeAgentOptions(
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": f"\n\n{self._user_agent_def.prompt}"
            },
            agents=None,  # 单一Agent架构
            mcp_servers=self._mcp_servers,
            allowed_tools=self._get_allowed_tools(),
            cwd=str(kb_path),  # 知识库目录作为 Agent 工作目录
            permission_mode="acceptEdits",
            env=self._env_vars,
            setting_sources=["project"],  # 启用项目级 Skills，从 .claude/skills/ 加载
            # 禁用 extended thinking（第三方 API 代理不兼容 thinking mode）
            max_thinking_tokens=0
        )

        # 如果提供了 SDK session ID，设置 resume 参数恢复会话
        if sdk_session_id:
            options.resume = sdk_session_id
            logger.debug(f"Setting resume to SDK session: {sdk_session_id}")

        return options

    async def initialize(self):
        """初始化User Agent连接池"""
        if self.is_initialized:
            logger.warning("User service already initialized")
            return

        try:
            # 检查认证
            if not self.settings.CLAUDE_API_KEY and not self.settings.ANTHROPIC_AUTH_TOKEN:
                raise ValueError("Missing authentication: CLAUDE_API_KEY or ANTHROPIC_AUTH_TOKEN")

            # 知识库路径
            kb_path = Path(self.settings.KB_ROOT_PATH)
            if not kb_path.exists():
                kb_path.mkdir(parents=True, exist_ok=True)

            # 准备环境变量（缓存供 _create_options 使用）
            self._env_vars = {
                "KB_ROOT_PATH": str(kb_path),
            }

            if self.settings.CLAUDE_API_KEY:
                self._env_vars["ANTHROPIC_API_KEY"] = self.settings.CLAUDE_API_KEY
            else:
                self._env_vars["ANTHROPIC_AUTH_TOKEN"] = self.settings.ANTHROPIC_AUTH_TOKEN
                if self.settings.ANTHROPIC_BASE_URL:
                    self._env_vars["ANTHROPIC_BASE_URL"] = self.settings.ANTHROPIC_BASE_URL

            # 获取User Agent定义（缓存供 _create_options 使用）
            run_mode = get_run_mode()
            self._user_agent_def = get_user_agent_definition(
                small_file_threshold_kb=self.settings.SMALL_FILE_KB_THRESHOLD,
                faq_max_entries=self.settings.FAQ_MAX_ENTRIES,
                run_mode=run_mode.value
            )
            logger.info(f"User Agent definition created with run_mode={run_mode.value}")

            # 配置MCP servers（缓存供 _create_options 使用）
            # 创建 SDK MCP server for image_read tool
            image_vision_server = create_sdk_mcp_server(
                name="image_vision",
                version="1.0.0",
                tools=[image_read_handler]
            )

            self._mcp_servers = {
                "image_vision": image_vision_server
            }

            # IM 模式下添加对应渠道的 MCP 服务器
            im_channel = get_im_channel()
            if im_channel:
                mcp_path = self._get_im_mcp_command(im_channel)
                logger.info(f"Using {im_channel}-mcp at: {mcp_path}")

                # 获取对应渠道的环境变量
                channel_upper = im_channel.upper()
                self._mcp_servers[im_channel] = {
                    "type": "stdio",
                    "command": mcp_path,
                    "args": [],
                    "env": {
                        f"{channel_upper}_CORP_ID": os.getenv(f"{channel_upper}_CORP_ID", ""),
                        f"{channel_upper}_CORP_SECRET": os.getenv(f"{channel_upper}_CORP_SECRET", ""),
                        f"{channel_upper}_AGENT_ID": os.getenv(f"{channel_upper}_AGENT_ID", ""),
                    }
                }
            else:
                logger.info("Standalone mode: No IM MCP server loaded")

            # 创建连接池
            pool_size = self.settings.USER_CLIENT_POOL_SIZE
            max_wait = self.settings.CLIENT_POOL_MAX_WAIT

            self.client_pool = SDKClientPool(
                pool_size=pool_size,
                options_factory=self._create_options,
                max_wait_time=float(max_wait)
            )

            # 初始化连接池
            logger.info(f"Initializing User client pool (size={pool_size})...")
            await self.client_pool.initialize()

            self.is_initialized = True
            logger.info("✅ User service initialized successfully")
            logger.info(f"   Pool size: {pool_size}")
            logger.info(f"   MCP Servers: {list(self._mcp_servers.keys())}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize user service: {e}")
            raise

    async def query(
        self,
        user_message: str,
        sdk_session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> AsyncIterator[Message]:
        """
        处理用户查询（使用连接池支持并发）

        Args:
            user_message: 用户消息
            sdk_session_id: SDK session ID（用于 resume 恢复会话）
                           - None: 新会话
                           - str: 已有会话，恢复上下文
            user_id: 用户WeChat Work UserID (可选)

        Yields:
            Message流（包含 ResultMessage，其中有真实的 session_id）
        """
        if not self.is_initialized:
            await self.initialize()

        logger.info(f"User query from {user_id or 'unknown'}: {user_message[:100]}...")

        try:
            message_count = 0

            # 从连接池获取客户端（支持 session 恢复）
            is_resume = sdk_session_id is not None
            logger.info(f"📤 Acquiring client from pool (resume={is_resume}, sdk_session={sdk_session_id or 'new'})...")
            async with self.client_pool.acquire(session_id=sdk_session_id) as client:
                logger.info(f"✅ Client acquired, sending query...")

                # 发送查询（不再传递 session_id，由 ClaudeAgentOptions.resume 控制）
                await client.query(user_message)
                logger.info(f"✅ Query sent successfully, waiting for response...")

                # 接收响应
                logger.info(f"🔄 Starting to receive response stream...")
                async for message in client.receive_response():
                    message_count += 1
                    logger.debug(f"📨 Received message {message_count}: type={type(message).__name__}")
                    yield message

            logger.info(f"✅ Response stream completed, total messages: {message_count}")
            logger.info(f"✅ Client released")

            # 检查是否收到响应
            if message_count == 0:
                logger.error("❌ No response from Claude API")
                logger.error(f"   SDK Session: {sdk_session_id or 'new'}")
                logger.error(f"   User ID: {user_id}")
                logger.error(f"   This may indicate:")
                logger.error(f"   - API account insufficent balance (欠费)")
                logger.error(f"   - API rate limit exceeded")
                logger.error(f"   - Network timeout")
            else:
                logger.info(f"✅ Received {message_count} messages from Claude API")

        except asyncio.TimeoutError:
            logger.error("❌ Claude API call timeout")
            logger.error(f"   SDK Session: {sdk_session_id or 'new'}")
            logger.error(f"   User ID: {user_id}")
            logger.error(f"   This may indicate:")
            logger.error(f"   - Network connectivity issues")
            logger.error(f"   - API service overload")
            logger.error(f"   - Pool exhausted (all clients busy)")
            raise
        except Exception as e:
            logger.error("❌ Claude API call failed")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Error message: {str(e)}")
            logger.error(f"   SDK Session: {sdk_session_id or 'new'}")
            logger.error(f"   User ID: {user_id}")
            logger.error(f"   This may indicate:")
            logger.error(f"   - Invalid API key or token")
            logger.error(f"   - API account insufficent balance (欠费)")
            logger.error(f"   - Exceeded rate limits")
            logger.error(f"   - API service unavailable")
            raise

    def get_pool_stats(self) -> dict:
        """获取连接池统计信息"""
        if self.client_pool:
            return self.client_pool.get_stats()
        return {"status": "not_initialized"}


class KBAdminService:
    """
    管理员端知识库服务

    职责:
    - 文档入库(5阶段处理)
    - 知识库管理
    - 批量员工通知

    特点:
    - 完整功能(smart_convert.py文档转换 + wework MCP)
    - SSE流式响应支持

    并发支持:
    - 使用 SDKClientPool 实现真正并发
    - 每个请求独占一个 Client
    - 通过 resume 参数恢复用户 session
    """

    def __init__(self):
        """初始化管理员端服务"""
        self.settings = get_settings()
        self.client_pool: Optional[SDKClientPool] = None
        self.is_initialized = False

        # 缓存配置（在 initialize 中设置）
        self._mcp_servers = None
        self._env_vars = None
        self._admin_agent_def = None

        logger.info("KBAdminService instance created")

    def _get_allowed_tools(self) -> list:
        """根据运行模式获取允许的工具列表"""
        tools = [
            "Read",
            "Write",
            "Grep",
            "Glob",
            "Bash",  # Document conversion via smart_convert.py
            "Skill",  # Enable Claude Code Skills
            # Image Vision MCP tool
            "mcp__image_vision__image_read",
        ]

        # IM 模式下添加对应渠道的工具
        im_channel = get_im_channel()
        if im_channel:
            tools.extend([
                f"mcp__{im_channel}__send_text_message",
                f"mcp__{im_channel}__send_markdown_message",
                f"mcp__{im_channel}__send_image_message",
                f"mcp__{im_channel}__send_file_message",
                f"mcp__{im_channel}__upload_media",
            ])

        return tools

    def _get_im_mcp_command(self, channel: str) -> str:
        """获取 IM MCP 命令路径"""
        import sys
        import shutil

        mcp_name = f"{channel}-mcp"
        mcp_path = shutil.which(mcp_name)
        if not mcp_path:
            venv_path = Path(sys.executable).parent / mcp_name
            if venv_path.exists():
                mcp_path = str(venv_path)
            else:
                logger.warning(f"{mcp_name} not found in PATH or venv, using '{mcp_name}' (may fail)")
                mcp_path = mcp_name

        return mcp_path

    def _create_options(self, sdk_session_id: Optional[str] = None) -> ClaudeAgentOptions:
        """
        创建 ClaudeAgentOptions（Options Factory）

        Args:
            sdk_session_id: SDK 返回的真实 session ID（可选）
                           - None: 新会话，不设置 resume
                           - str: 已有会话，设置 resume 恢复会话

        Returns:
            配置好的 ClaudeAgentOptions
        """
        kb_path = Path(self.settings.KB_ROOT_PATH)

        options = ClaudeAgentOptions(
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": f"\n\n{self._admin_agent_def.prompt}"
            },
            agents=None,  # 单一Agent架构
            mcp_servers=self._mcp_servers,
            allowed_tools=self._get_allowed_tools(),
            cwd=str(kb_path),  # 知识库目录作为 Agent 工作目录
            permission_mode="acceptEdits",
            env=self._env_vars,
            setting_sources=["project"],  # 启用项目级 Skills，从 .claude/skills/ 加载
            # 禁用 extended thinking（第三方 API 代理不兼容 thinking mode）
            max_thinking_tokens=0
        )

        # 如果提供了 SDK session ID，设置 resume 参数恢复会话
        if sdk_session_id:
            options.resume = sdk_session_id
            logger.debug(f"Setting resume to SDK session: {sdk_session_id}")

        return options

    async def initialize(self):
        """初始化Admin Agent连接池"""
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

            # 准备环境变量（缓存供 _create_options 使用）
            self._env_vars = {
                "KB_ROOT_PATH": str(kb_path),
            }

            if self.settings.CLAUDE_API_KEY:
                self._env_vars["ANTHROPIC_API_KEY"] = self.settings.CLAUDE_API_KEY
            else:
                self._env_vars["ANTHROPIC_AUTH_TOKEN"] = self.settings.ANTHROPIC_AUTH_TOKEN
                if self.settings.ANTHROPIC_BASE_URL:
                    self._env_vars["ANTHROPIC_BASE_URL"] = self.settings.ANTHROPIC_BASE_URL

            # 获取Admin Agent定义（缓存供 _create_options 使用）
            run_mode = get_run_mode()
            self._admin_agent_def = get_admin_agent_definition(
                small_file_threshold_kb=self.settings.SMALL_FILE_KB_THRESHOLD,
                faq_max_entries=self.settings.FAQ_MAX_ENTRIES,
                run_mode=run_mode.value
            )
            logger.info(f"Admin Agent definition created with run_mode={run_mode.value}")

            # 配置MCP servers（缓存供 _create_options 使用）
            # 创建 SDK MCP server for image_read tool
            image_vision_server = create_sdk_mcp_server(
                name="image_vision",
                version="1.0.0",
                tools=[image_read_handler]
            )

            self._mcp_servers = {
                "image_vision": image_vision_server
            }

            # IM 模式下添加对应渠道的 MCP 服务器
            im_channel = get_im_channel()
            if im_channel:
                mcp_path = self._get_im_mcp_command(im_channel)
                logger.info(f"Using {im_channel}-mcp at: {mcp_path}")

                # 获取对应渠道的环境变量
                channel_upper = im_channel.upper()
                self._mcp_servers[im_channel] = {
                    "type": "stdio",
                    "command": mcp_path,
                    "args": [],
                    "env": {
                        f"{channel_upper}_CORP_ID": os.getenv(f"{channel_upper}_CORP_ID", ""),
                        f"{channel_upper}_CORP_SECRET": os.getenv(f"{channel_upper}_CORP_SECRET", ""),
                        f"{channel_upper}_AGENT_ID": os.getenv(f"{channel_upper}_AGENT_ID", ""),
                    }
                }
            else:
                logger.info("Standalone mode: No IM MCP server loaded")

            # 创建连接池
            pool_size = self.settings.ADMIN_CLIENT_POOL_SIZE
            max_wait = self.settings.CLIENT_POOL_MAX_WAIT

            self.client_pool = SDKClientPool(
                pool_size=pool_size,
                options_factory=self._create_options,
                max_wait_time=float(max_wait)
            )

            # 初始化连接池
            logger.info(f"Initializing Admin client pool (size={pool_size})...")
            await self.client_pool.initialize()

            self.is_initialized = True
            logger.info("✅ Admin service initialized successfully")
            logger.info(f"   Pool size: {pool_size}")
            logger.info(f"   MCP Servers: {list(self._mcp_servers.keys())}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize admin service: {e}")
            raise

    async def query(
        self,
        user_message: str,
        sdk_session_id: Optional[str] = None
    ) -> AsyncIterator[Message]:
        """
        处理管理员查询（使用连接池支持并发）

        Args:
            user_message: 用户消息
            sdk_session_id: SDK session ID（用于 resume 恢复会话）
                           - None: 新会话
                           - str: 已有会话，恢复上下文

        Yields:
            Message流（包含 ResultMessage，其中有真实的 session_id）
        """
        if not self.is_initialized:
            await self.initialize()

        logger.info(f"Admin query: {user_message[:100]}...")

        try:
            message_count = 0

            # 从连接池获取客户端（支持 session 恢复）
            is_resume = sdk_session_id is not None
            logger.info(f"📤 Acquiring client from pool (resume={is_resume}, sdk_session={sdk_session_id or 'new'})...")
            async with self.client_pool.acquire(session_id=sdk_session_id) as client:
                logger.info(f"✅ Client acquired, sending query...")

                # 发送查询（不再传递 session_id，由 ClaudeAgentOptions.resume 控制）
                await client.query(user_message)

                # 接收响应
                async for message in client.receive_response():
                    message_count += 1
                    yield message

            logger.info(f"✅ Response completed, client released")

            # 检查是否收到响应
            if message_count == 0:
                logger.error("❌ No response from Claude API")
                logger.error(f"   SDK Session: {sdk_session_id or 'new'}")
                logger.error(f"   This may indicate:")
                logger.error(f"   - API account insufficent balance (欠费)")
                logger.error(f"   - API rate limit exceeded")
                logger.error(f"   - Network timeout")
            else:
                logger.info(f"✅ Received {message_count} messages from Claude API")

        except asyncio.TimeoutError:
            logger.error("❌ Claude API call timeout")
            logger.error(f"   SDK Session: {sdk_session_id or 'new'}")
            logger.error(f"   This may indicate:")
            logger.error(f"   - Network connectivity issues")
            logger.error(f"   - API service overload")
            logger.error(f"   - Pool exhausted (all clients busy)")
            raise
        except Exception as e:
            logger.error("❌ Claude API call failed")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Error message: {str(e)}")
            logger.error(f"   SDK Session: {sdk_session_id or 'new'}")
            logger.error(f"   This may indicate:")
            logger.error(f"   - Invalid API key or token")
            logger.error(f"   - API account insufficent balance (欠费)")
            logger.error(f"   - Exceeded rate limits")
            logger.error(f"   - API service unavailable")
            raise

    def get_pool_stats(self) -> dict:
        """获取连接池统计信息"""
        if self.client_pool:
            return self.client_pool.get_stats()
        return {"status": "not_initialized"}


class KBServiceFactory:
    """
    知识库服务工厂

    管理User和Admin两个独立的Agent服务
    采用单例模式,预留未来拆分为微服务的扩展点

    未来演进路径:
    - 当前: 单一进程,两个Agent客户端
    - 未来: 可改为HTTP客户端,调用独立的微服务
    """

    _user_service: Optional[KBUserService] = None
    _admin_service: Optional[KBAdminService] = None

    @classmethod
    def get_user_service(cls) -> KBUserService:
        """
        获取用户端服务单例

        Returns:
            KBUserService实例
        """
        if cls._user_service is None:
            cls._user_service = KBUserService()
            logger.info("Created new User service instance")

        return cls._user_service

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
        user = cls.get_user_service()
        admin = cls.get_admin_service()

        await user.initialize()
        await admin.initialize()

        logger.info("✅ All KB services initialized")


# 便捷函数(向后兼容)
def get_user_service() -> KBUserService:
    """获取用户端服务"""
    return KBServiceFactory.get_user_service()


def get_admin_service() -> KBAdminService:
    """获取管理员端服务"""
    return KBServiceFactory.get_admin_service()


__all__ = [
    'KBServiceFactory',
    'KBUserService',
    'KBAdminService',
    'get_user_service',
    'get_admin_service'
]
