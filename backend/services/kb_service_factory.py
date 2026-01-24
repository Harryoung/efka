"""
KB Service Factory - Knowledge Base Service Factory

Manages two independent Agent SDK clients for User Agent and Admin Agent
Supports future microservices split (only need to modify this file's implementation)

Concurrency support: Use SDKClientPool to achieve true multi-user concurrency
- Each request gets exclusive use of a Client
- Resume user session via resume parameter
- Return to pool after use
"""

import logging
import os
import asyncio
import json
from typing import AsyncIterator, Optional, Callable
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    Message,
    AssistantMessage,
    TextBlock,
    ResultMessage,
    create_sdk_mcp_server
)

from backend.agents.kb_qa_agent import get_user_agent_definition
from backend.agents.kb_admin_agent import get_admin_agent_definition
from backend.config.settings import get_settings
from backend.config.run_mode import get_run_mode, get_im_channel, is_standalone
from backend.tools.image_read import image_read_handler
from backend.services.client_pool import SDKClientPool, get_pool_manager

logger = logging.getLogger(__name__)

def _should_use_claude_print_json(base_url: Optional[str]) -> bool:
    """
    Claude Code streaming mode (SDK control protocol) is brittle with some third-party
    Anthropic-compatible proxies and can surface 'Please run /login' 403 errors.
    Use non-interactive JSON output mode as a pragmatic fallback.
    """
    if not base_url:
        return False
    return "api.anthropic.com" not in base_url


async def _run_claude_print_json(
    *,
    prompt: str,
    cwd: str,
    env: dict[str, str],
    allowed_tools: list[str],
    append_system_prompt: str,
    resume: Optional[str],
) -> tuple[AssistantMessage, ResultMessage]:
    allowed_tools = [t for t in allowed_tools if not t.startswith("mcp__")]

    cmd = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--permission-mode",
        "acceptEdits",
    ]
    if allowed_tools:
        cmd.extend(["--allowedTools", ",".join(allowed_tools)])
    if resume:
        cmd.extend(["--resume", resume])
    if append_system_prompt:
        cmd.extend(["--append-system-prompt", append_system_prompt])
    cmd.extend(["--", prompt])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        env={**os.environ, **env},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await proc.communicate()

    stdout = (stdout_b or b"").decode("utf-8", errors="replace").strip()
    stderr = (stderr_b or b"").decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        msg = stderr or stdout or f"claude exited with code {proc.returncode}"
        assistant = AssistantMessage(content=[TextBlock(text=msg)], model="unknown")
        result = ResultMessage(
            subtype="error",
            duration_ms=0,
            duration_api_ms=0,
            is_error=True,
            num_turns=0,
            session_id="",
            result=msg,
        )
        return assistant, result

    try:
        # Claude Code typically prints one JSON object. Be defensive:
        # - stderr/stdout may include extra lines
        # - some versions/proxies may return a JSON array
        last_line = next((line for line in reversed(stdout.splitlines()) if line.strip()), "")
        parsed = json.loads(last_line) if last_line else json.loads(stdout or "{}")
    except json.JSONDecodeError:
        msg = stderr or stdout or "Failed to parse claude JSON output"
        assistant = AssistantMessage(content=[TextBlock(text=msg)], model="unknown")
        result = ResultMessage(
            subtype="error",
            duration_ms=0,
            duration_api_ms=0,
            is_error=True,
            num_turns=0,
            session_id="",
            result=msg,
        )
        return assistant, result

    data: dict = {}
    if isinstance(parsed, dict):
        data = parsed
    elif isinstance(parsed, list):
        for item in reversed(parsed):
            if isinstance(item, dict) and (
                "result" in item or "subtype" in item or item.get("type") == "result"
            ):
                data = item
                break
        if not data:
            for item in reversed(parsed):
                if isinstance(item, dict):
                    data = item
                    break

    if not data:
        msg = stderr or stdout or "Unexpected claude JSON output"
        assistant = AssistantMessage(content=[TextBlock(text=msg)], model="unknown")
        result = ResultMessage(
            subtype="error",
            duration_ms=0,
            duration_api_ms=0,
            is_error=True,
            num_turns=0,
            session_id="",
            result=msg,
        )
        return assistant, result

    result_text = data.get("result") or ""
    if not result_text and "content" in data:
        content = data.get("content")
        if isinstance(content, str):
            result_text = content
        elif isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
            result_text = "".join(parts)

    assistant = AssistantMessage(content=[TextBlock(text=result_text)], model="unknown")
    result = ResultMessage(
        subtype=str(data.get("subtype") or "success"),
        duration_ms=int(data.get("duration_ms") or 0),
        duration_api_ms=int(data.get("duration_api_ms") or 0),
        is_error=bool(data.get("is_error") or False),
        num_turns=int(data.get("num_turns") or 0),
        session_id=str(data.get("session_id") or ""),
        total_cost_usd=data.get("total_cost_usd"),
        usage=data.get("usage"),
        result=result_text,
    )
    return assistant, result


def _is_transient_upstream_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    transient_markers = [
        "connection error",
        "connect",
        "econnreset",
        "enotfound",
        "timed out",
        "timeout",
        "tls",
        "temporary",
        "temporarily unavailable",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
        "rate limit",
        "429",
        "502",
        "503",
        "504",
    ]
    return any(marker in msg for marker in transient_markers)


class KBUserService:
    """
    User-side Knowledge Base Service

    Responsibilities:
    - Knowledge query (6-stage retrieval)
    - Satisfaction feedback
    - Domain expert routing
    - Asynchronous multi-turn conversation management

    Features:
    - Lightweight (no document conversion)
    - WeChat Work MCP integration

    Concurrency support:
    - Use SDKClientPool for true concurrency
    - Each request gets exclusive use of a Client
    - Resume user session via resume parameter
    """

    def __init__(self):
        """Initialize user-side service"""
        self.settings = get_settings()
        self.client_pool: Optional[SDKClientPool] = None
        self.is_initialized = False
        self._use_print_json = _should_use_claude_print_json(self.settings.ANTHROPIC_BASE_URL)

        # Cache MCP servers configuration (set in initialize)
        self._mcp_servers = None
        self._env_vars = None
        self._user_agent_def = None

        logger.info("KBUserService instance created")

    def _get_allowed_tools(self) -> list:
        """Get allowed tools list based on run mode"""
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

        # Add channel-specific tools in IM mode
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
        """Get IM MCP command path"""
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
        Create ClaudeAgentOptions (Options Factory)

        Args:
            sdk_session_id: Real session ID returned by SDK (optional)
                           - None: New session, don't set resume
                           - str: Existing session, set resume to restore session

        Returns:
            Configured ClaudeAgentOptions
        """
        kb_path = Path(self.settings.KB_ROOT_PATH)

        options = ClaudeAgentOptions(
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": f"\n\n{self._user_agent_def.prompt}"
            },
            agents=None,  # Single Agent architecture
            mcp_servers=self._mcp_servers,
            allowed_tools=self._get_allowed_tools(),
            cwd=str(kb_path),  # Knowledge base directory as Agent working directory
            permission_mode="acceptEdits",
            env=self._env_vars,
            setting_sources=["project"],  # Enable project-level Skills, load from .claude/skills/
            # Disable extended thinking (third-party API proxy incompatible with thinking mode)
            max_thinking_tokens=0
        )

        # If SDK session ID provided, set resume parameter to restore session
        if sdk_session_id:
            options.resume = sdk_session_id
            logger.debug(f"Setting resume to SDK session: {sdk_session_id}")

        return options

    async def initialize(self):
        """Initialize User Agent connection pool"""
        if self.is_initialized:
            logger.warning("User service already initialized")
            return

        try:
            # Check authentication
            if not self.settings.CLAUDE_API_KEY and not self.settings.ANTHROPIC_AUTH_TOKEN:
                raise ValueError("Missing authentication: CLAUDE_API_KEY or ANTHROPIC_AUTH_TOKEN")

            # Knowledge base path
            kb_path = Path(self.settings.KB_ROOT_PATH)
            if not kb_path.exists():
                kb_path.mkdir(parents=True, exist_ok=True)

            # Prepare environment variables (cached for _create_options)
            self._env_vars = {
                "KB_ROOT_PATH": str(kb_path),
            }

            if self.settings.CLAUDE_API_KEY:
                self._env_vars["ANTHROPIC_API_KEY"] = self.settings.CLAUDE_API_KEY
            else:
                self._env_vars["ANTHROPIC_AUTH_TOKEN"] = self.settings.ANTHROPIC_AUTH_TOKEN
                if self.settings.ANTHROPIC_BASE_URL:
                    self._env_vars["ANTHROPIC_BASE_URL"] = self.settings.ANTHROPIC_BASE_URL

            # Get User Agent definition (cached for _create_options)
            run_mode = get_run_mode()
            self._user_agent_def = get_user_agent_definition(
                small_file_threshold_kb=self.settings.SMALL_FILE_KB_THRESHOLD,
                faq_max_entries=self.settings.FAQ_MAX_ENTRIES,
                run_mode=run_mode.value
            )
            logger.info(f"User Agent definition created with run_mode={run_mode.value}")

            # Configure MCP servers (cached for _create_options)
            # Create SDK MCP server for image_read tool
            image_vision_server = create_sdk_mcp_server(
                name="image_vision",
                version="1.0.0",
                tools=[image_read_handler]
            )

            self._mcp_servers = {
                "image_vision": image_vision_server
            }

            if self._use_print_json:
                # Avoid initializing streaming SDK clients; use `claude -p --output-format json` per request.
                self.is_initialized = True
                logger.warning(
                    "User service running in non-interactive Claude Code mode (print+json). "
                    "Streaming and SDK MCP servers are disabled in this mode."
                )
                return

            # Add corresponding channel's MCP server in IM mode
            im_channel = get_im_channel()
            if im_channel:
                mcp_path = self._get_im_mcp_command(im_channel)
                logger.info(f"Using {im_channel}-mcp at: {mcp_path}")

                # Get environment variables for the corresponding channel
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

            # Create connection pool
            pool_size = self.settings.USER_CLIENT_POOL_SIZE
            max_wait = self.settings.CLIENT_POOL_MAX_WAIT

            self.client_pool = SDKClientPool(
                pool_size=pool_size,
                options_factory=self._create_options,
                max_wait_time=float(max_wait)
            )

            # Initialize connection pool
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
        Process user query (using connection pool to support concurrency)

        Args:
            user_message: User message
            sdk_session_id: SDK session ID (for resume to restore session)
                           - None: New session
                           - str: Existing session, restore context
            user_id: User WeChat Work UserID (optional)

        Yields:
            Message stream (includes ResultMessage with real session_id)
        """
        if not self.is_initialized:
            await self.initialize()

        logger.info(f"User query from {user_id or 'unknown'}: {user_message[:100]}...")

        if self._use_print_json:
            kb_path = Path(self.settings.KB_ROOT_PATH)
            assistant, result = await _run_claude_print_json(
                prompt=user_message,
                cwd=str(kb_path),
                env=self._env_vars or {},
                allowed_tools=self._get_allowed_tools(),
                append_system_prompt=f"\n\n{self._user_agent_def.prompt}",
                resume=sdk_session_id,
            )
            yield assistant
            yield result
            return

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            message_count = 0
            try:
                # Acquire client from pool (supports session resume)
                is_resume = sdk_session_id is not None
                logger.info(
                    f"📤 Acquiring client from pool (resume={is_resume}, sdk_session={sdk_session_id or 'new'})..."
                )
                async with self.client_pool.acquire(session_id=sdk_session_id) as client:
                    logger.info("✅ Client acquired, sending query...")

                    # Send query (no longer pass session_id, controlled by ClaudeAgentOptions.resume)
                    await client.query(user_message)
                    logger.info("✅ Query sent successfully, waiting for response...")

                    # Receive response
                    logger.info("🔄 Starting to receive response stream...")
                    async for message in client.receive_response():
                        message_count += 1
                        logger.debug(f"📨 Received message {message_count}: type={type(message).__name__}")
                        yield message

                logger.info(f"✅ Response stream completed, total messages: {message_count}")
                logger.info("✅ Client released")

                if message_count == 0:
                    logger.error("❌ No response from Claude API")
                    logger.error(f"   SDK Session: {sdk_session_id or 'new'}")
                    logger.error(f"   User ID: {user_id}")
                    logger.error("   This may indicate:")
                    logger.error("   - API account insufficient balance")
                    logger.error("   - API rate limit exceeded")
                    logger.error("   - Network timeout")
                else:
                    logger.info(f"✅ Received {message_count} messages from Claude API")

                return

            except asyncio.CancelledError:
                raise
            except Exception as e:
                is_last = attempt >= max_attempts
                should_retry = (not is_last) and (message_count == 0) and _is_transient_upstream_error(e)

                logger.error("❌ Claude API call failed")
                logger.error(f"   Error type: {type(e).__name__}")
                logger.error(f"   Error message: {str(e)}")
                logger.error(f"   SDK Session: {sdk_session_id or 'new'}")
                logger.error(f"   User ID: {user_id}")
                logger.error(f"   Attempt: {attempt}/{max_attempts}")
                logger.error("   This may indicate:")
                logger.error("   - Invalid API key or token")
                logger.error("   - API account insufficent balance (欠费)")
                logger.error("   - Exceeded rate limits")
                logger.error("   - API service unavailable")
                logger.error("   - Transient network issues")
                logger.error("   Stack:", exc_info=True)

                if should_retry:
                    backoff_seconds = 0.5 * (2 ** (attempt - 1))
                    logger.warning(
                        "⚠️  Transient upstream error before any response; retrying in %.1fs (attempt %d/%d)",
                        backoff_seconds,
                        attempt + 1,
                        max_attempts
                    )
                    await asyncio.sleep(backoff_seconds)
                    continue
                raise

    def get_pool_stats(self) -> dict:
        """Get connection pool statistics"""
        if self.client_pool:
            return self.client_pool.get_stats()
        return {"status": "not_initialized"}


class KBAdminService:
    """
    Admin-side Knowledge Base Service

    Responsibilities:
    - Document ingestion (5-stage processing)
    - Knowledge base management
    - Batch employee notifications

    Features:
    - Full functionality (smart_convert.py document conversion + wework MCP)
    - SSE streaming response support

    Concurrency support:
    - Use SDKClientPool for true concurrency
    - Each request gets exclusive use of a Client
    - Resume user session via resume parameter
    """

    def __init__(self):
        """Initialize admin-side service"""
        self.settings = get_settings()
        self.client_pool: Optional[SDKClientPool] = None
        self.is_initialized = False
        self._use_print_json = _should_use_claude_print_json(self.settings.ANTHROPIC_BASE_URL)

        # Cache configuration (set in initialize)
        self._mcp_servers = None
        self._env_vars = None
        self._admin_agent_def = None

        logger.info("KBAdminService instance created")

    def _get_allowed_tools(self) -> list:
        """Get allowed tools list based on run mode"""
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

        # Add channel-specific tools in IM mode
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
        """Get IM MCP command path"""
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
        Create ClaudeAgentOptions (Options Factory)

        Args:
            sdk_session_id: Real session ID returned by SDK (optional)
                           - None: New session, don't set resume
                           - str: Existing session, set resume to restore session

        Returns:
            Configured ClaudeAgentOptions
        """
        kb_path = Path(self.settings.KB_ROOT_PATH)

        options = ClaudeAgentOptions(
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": f"\n\n{self._admin_agent_def.prompt}"
            },
            agents=None,  # Single Agent architecture
            mcp_servers=self._mcp_servers,
            allowed_tools=self._get_allowed_tools(),
            cwd=str(kb_path),  # Knowledge base directory as Agent working directory
            permission_mode="acceptEdits",
            env=self._env_vars,
            setting_sources=["project"],  # Enable project-level Skills, load from .claude/skills/
            # Disable extended thinking (third-party API proxy incompatible with thinking mode)
            max_thinking_tokens=0
        )

        # If SDK session ID provided, set resume parameter to restore session
        if sdk_session_id:
            options.resume = sdk_session_id
            logger.debug(f"Setting resume to SDK session: {sdk_session_id}")

        return options

    async def initialize(self):
        """Initialize Admin Agent connection pool"""
        if self.is_initialized:
            logger.warning("Admin service already initialized")
            return

        try:
            # Check authentication
            if not self.settings.CLAUDE_API_KEY and not self.settings.ANTHROPIC_AUTH_TOKEN:
                raise ValueError("Missing authentication: CLAUDE_API_KEY or ANTHROPIC_AUTH_TOKEN")

            # Knowledge base path
            kb_path = Path(self.settings.KB_ROOT_PATH)
            if not kb_path.exists():
                kb_path.mkdir(parents=True, exist_ok=True)

            # Prepare environment variables (cached for _create_options)
            self._env_vars = {
                "KB_ROOT_PATH": str(kb_path),
            }

            if self.settings.CLAUDE_API_KEY:
                self._env_vars["ANTHROPIC_API_KEY"] = self.settings.CLAUDE_API_KEY
            else:
                self._env_vars["ANTHROPIC_AUTH_TOKEN"] = self.settings.ANTHROPIC_AUTH_TOKEN
                if self.settings.ANTHROPIC_BASE_URL:
                    self._env_vars["ANTHROPIC_BASE_URL"] = self.settings.ANTHROPIC_BASE_URL

            # Get Admin Agent definition (cached for _create_options)
            run_mode = get_run_mode()
            self._admin_agent_def = get_admin_agent_definition(
                small_file_threshold_kb=self.settings.SMALL_FILE_KB_THRESHOLD,
                faq_max_entries=self.settings.FAQ_MAX_ENTRIES,
                run_mode=run_mode.value
            )
            logger.info(f"Admin Agent definition created with run_mode={run_mode.value}")

            # Configure MCP servers (cached for _create_options)
            # Create SDK MCP server for image_read tool
            image_vision_server = create_sdk_mcp_server(
                name="image_vision",
                version="1.0.0",
                tools=[image_read_handler]
            )

            self._mcp_servers = {
                "image_vision": image_vision_server
            }

            if self._use_print_json:
                # Avoid initializing streaming SDK clients; use `claude -p --output-format json` per request.
                self.is_initialized = True
                logger.warning(
                    "Admin service running in non-interactive Claude Code mode (print+json). "
                    "Streaming and SDK MCP servers are disabled in this mode."
                )
                return

            # Add corresponding channel's MCP server in IM mode
            im_channel = get_im_channel()
            if im_channel:
                mcp_path = self._get_im_mcp_command(im_channel)
                logger.info(f"Using {im_channel}-mcp at: {mcp_path}")

                # Get environment variables for the corresponding channel
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

            # Create connection pool
            pool_size = self.settings.ADMIN_CLIENT_POOL_SIZE
            max_wait = self.settings.CLIENT_POOL_MAX_WAIT

            self.client_pool = SDKClientPool(
                pool_size=pool_size,
                options_factory=self._create_options,
                max_wait_time=float(max_wait)
            )

            # Initialize connection pool
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
        Process admin query (using connection pool to support concurrency)

        Args:
            user_message: User message
            sdk_session_id: SDK session ID (for resume to restore session)
                           - None: New session
                           - str: Existing session, restore context

        Yields:
            Message stream (includes ResultMessage with real session_id)
        """
        if not self.is_initialized:
            await self.initialize()

        logger.info(f"Admin query: {user_message[:100]}...")

        if self._use_print_json:
            kb_path = Path(self.settings.KB_ROOT_PATH)
            assistant, result = await _run_claude_print_json(
                prompt=user_message,
                cwd=str(kb_path),
                env=self._env_vars or {},
                allowed_tools=self._get_allowed_tools(),
                append_system_prompt=f"\n\n{self._admin_agent_def.prompt}",
                resume=sdk_session_id,
            )
            yield assistant
            yield result
            return

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            message_count = 0
            try:
                # Acquire client from pool (supports session resume)
                is_resume = sdk_session_id is not None
                logger.info(
                    f"📤 Acquiring client from pool (resume={is_resume}, sdk_session={sdk_session_id or 'new'})..."
                )
                async with self.client_pool.acquire(session_id=sdk_session_id) as client:
                    logger.info("✅ Client acquired, sending query...")

                    # Send query (no longer pass session_id, controlled by ClaudeAgentOptions.resume)
                    await client.query(user_message)

                    # Receive response
                    async for message in client.receive_response():
                        message_count += 1
                        yield message

                logger.info("✅ Response completed, client released")

                if message_count == 0:
                    logger.error("❌ No response from Claude API")
                    logger.error(f"   SDK Session: {sdk_session_id or 'new'}")
                    logger.error("   This may indicate:")
                    logger.error("   - API account insufficient balance")
                    logger.error("   - API rate limit exceeded")
                    logger.error("   - Network timeout")
                else:
                    logger.info(f"✅ Received {message_count} messages from Claude API")

                return

            except asyncio.CancelledError:
                raise
            except Exception as e:
                is_last = attempt >= max_attempts
                should_retry = (not is_last) and (message_count == 0) and _is_transient_upstream_error(e)

                logger.error("❌ Claude API call failed")
                logger.error(f"   Error type: {type(e).__name__}")
                logger.error(f"   Error message: {str(e)}")
                logger.error(f"   SDK Session: {sdk_session_id or 'new'}")
                logger.error(f"   Attempt: {attempt}/{max_attempts}")
                logger.error("   This may indicate:")
                logger.error("   - Invalid API key or token")
                logger.error("   - API account insufficent balance (欠费)")
                logger.error("   - Exceeded rate limits")
                logger.error("   - API service unavailable")
                logger.error("   - Transient network issues")
                logger.error("   Stack:", exc_info=True)

                if should_retry:
                    backoff_seconds = 0.5 * (2 ** (attempt - 1))
                    logger.warning(
                        "⚠️  Transient upstream error before any response; retrying in %.1fs (attempt %d/%d)",
                        backoff_seconds,
                        attempt + 1,
                        max_attempts
                    )
                    await asyncio.sleep(backoff_seconds)
                    continue
                raise

    def get_pool_stats(self) -> dict:
        """Get connection pool statistics"""
        if self.client_pool:
            return self.client_pool.get_stats()
        return {"status": "not_initialized"}


class KBServiceFactory:
    """
    Knowledge Base Service Factory

    Manages two independent Agent services: User and Admin
    Uses singleton pattern, reserved extension point for future microservices split

    Future evolution path:
    - Current: Single process, two Agent clients
    - Future: Can be changed to HTTP client, calling independent microservices
    """

    _user_service: Optional[KBUserService] = None
    _admin_service: Optional[KBAdminService] = None

    @classmethod
    def get_user_service(cls) -> KBUserService:
        """
        Get user-side service singleton

        Returns:
            KBUserService instance
        """
        if cls._user_service is None:
            cls._user_service = KBUserService()
            logger.info("Created new User service instance")

        return cls._user_service

    @classmethod
    def get_admin_service(cls) -> KBAdminService:
        """
        Get admin-side service singleton

        Returns:
            KBAdminService instance
        """
        if cls._admin_service is None:
            cls._admin_service = KBAdminService()
            logger.info("Created new Admin service instance")

        return cls._admin_service

    @classmethod
    async def initialize_all(cls):
        """Initialize all services"""
        user = cls.get_user_service()
        admin = cls.get_admin_service()

        await user.initialize()
        await admin.initialize()

        logger.info("✅ All KB services initialized")


# Convenience functions (backward compatibility)
def get_user_service() -> KBUserService:
    """Get user-side service"""
    return KBServiceFactory.get_user_service()


def get_admin_service() -> KBAdminService:
    """Get admin-side service"""
    return KBServiceFactory.get_admin_service()


__all__ = [
    'KBServiceFactory',
    'KBUserService',
    'KBAdminService',
    'get_user_service',
    'get_admin_service'
]
