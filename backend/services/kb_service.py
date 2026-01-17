"""
Knowledge Base Service - Core knowledge base service
Manages Claude SDK Client and Agent configuration
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
    Knowledge base core service class

    Responsibilities:
    1. Manage Claude SDK Client (single Agent architecture)
    2. Configure unified intelligent agent
    3. Provide unified query interface
    4. Handle session management
    """

    def __init__(self):
        """Initialize knowledge base service"""
        self.settings = get_settings()
        self.client: Optional[ClaudeSDKClient] = None
        self.is_initialized = False

        # Set environment variables at process level early (before any SDK calls)
        self._set_process_env_vars()

        # Configure logging
        self._setup_logging()

    def _set_process_env_vars(self):
        """Set environment variables at process level to ensure all Agents can access them"""
        logger.info("=" * 80)
        logger.info("🔍 DEBUG: Setting process environment variables")
        logger.info("=" * 80)

        # Set authentication environment variables
        if self.settings.CLAUDE_API_KEY:
            os.environ["ANTHROPIC_API_KEY"] = self.settings.CLAUDE_API_KEY
            logger.info(f"✅ Set ANTHROPIC_API_KEY = ...{self.settings.CLAUDE_API_KEY[-4:]}")
        else:
            os.environ["ANTHROPIC_AUTH_TOKEN"] = self.settings.ANTHROPIC_AUTH_TOKEN
            logger.info(f"✅ Set ANTHROPIC_AUTH_TOKEN = ...{self.settings.ANTHROPIC_AUTH_TOKEN[-4:]}")

            if self.settings.ANTHROPIC_BASE_URL:
                os.environ["ANTHROPIC_BASE_URL"] = self.settings.ANTHROPIC_BASE_URL
                logger.info(f"✅ Set ANTHROPIC_BASE_URL = {self.settings.ANTHROPIC_BASE_URL}")

        # Verify environment variables are set
        logger.info("\n🔍 Verifying environment variables in os.environ:")
        if "ANTHROPIC_API_KEY" in os.environ:
            logger.info(f"  ✅ os.environ['ANTHROPIC_API_KEY'] = ...{os.environ['ANTHROPIC_API_KEY'][-4:]}")
        if "ANTHROPIC_AUTH_TOKEN" in os.environ:
            logger.info(f"  ✅ os.environ['ANTHROPIC_AUTH_TOKEN'] = ...{os.environ['ANTHROPIC_AUTH_TOKEN'][-4:]}")
        if "ANTHROPIC_BASE_URL" in os.environ:
            logger.info(f"  ✅ os.environ['ANTHROPIC_BASE_URL'] = {os.environ['ANTHROPIC_BASE_URL']}")

        logger.info("=" * 80)

    def _setup_logging(self):
        """Configure logging system"""
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
        logger.info("Knowledge base service logging system initialized")

    async def initialize(self):
        """
        Initialize Claude SDK Client
        """
        if self.is_initialized:
            logger.warning("Knowledge base service already initialized, skipping duplicate initialization")
            return

        try:
            # Check API Key (supports CLAUDE_API_KEY or ANTHROPIC_AUTH_TOKEN)
            if not self.settings.CLAUDE_API_KEY and not self.settings.ANTHROPIC_AUTH_TOKEN:
                raise ValueError(
                    "Authentication not configured, please configure CLAUDE_API_KEY or ANTHROPIC_AUTH_TOKEN in .env file"
                )

            # Check knowledge base path
            kb_path = Path(self.settings.KB_ROOT_PATH)
            if not kb_path.exists():
                logger.warning(f"Knowledge base path does not exist, will create: {kb_path}")
                kb_path.mkdir(parents=True, exist_ok=True)

            logger.info(f"Knowledge base path: {kb_path}")

            # Set knowledge base path in process environment variables
            os.environ["KB_ROOT_PATH"] = str(kb_path)

            # Log authentication method (environment variables set in __init__)
            if self.settings.CLAUDE_API_KEY:
                logger.info(f"Authentication method: CLAUDE_API_KEY ({'*' * 20}{self.settings.CLAUDE_API_KEY[-4:]})")
            else:
                logger.info(f"Authentication method: ANTHROPIC_AUTH_TOKEN ({'*' * 20}{self.settings.ANTHROPIC_AUTH_TOKEN[-4:]})")
                logger.info(f"Base URL: {self.settings.ANTHROPIC_BASE_URL}")

            logger.info("✅ Authentication environment variables set at process startup")

            # Prepare environment variables for SDK
            env_vars = {
                "KB_ROOT_PATH": str(kb_path),
            }

            # Set authentication environment variables
            if self.settings.CLAUDE_API_KEY:
                env_vars["ANTHROPIC_API_KEY"] = self.settings.CLAUDE_API_KEY
            else:
                env_vars["ANTHROPIC_AUTH_TOKEN"] = self.settings.ANTHROPIC_AUTH_TOKEN
                if self.settings.ANTHROPIC_BASE_URL:
                    env_vars["ANTHROPIC_BASE_URL"] = self.settings.ANTHROPIC_BASE_URL

            # Get unified Agent prompt (inject config parameters)
            unified_agent_def = get_unified_agent_definition(
                small_file_threshold_kb=self.settings.SMALL_FILE_KB_THRESHOLD,
                faq_max_entries=self.settings.FAQ_MAX_ENTRIES
            )

            logger.info("\n" + "=" * 80)
            logger.info("🔍 DEBUG: Creating ClaudeAgentOptions (single Agent architecture)")
            logger.info("=" * 80)
            logger.info(f"Env parameters passed to SDK:")
            for key, value in env_vars.items():
                if key in ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_API_KEY"]:
                    logger.info(f"  {key} = ...{value[-4:]}")
                else:
                    logger.info(f"  {key} = {value}")
            logger.info("=" * 80)

            # Configure MCP servers (markitdown document conversion service + wework message notification service)
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
                        # Pass config from environment variables
                        "WEWORK_CORP_ID": os.getenv("WEWORK_CORP_ID", ""),
                        "WEWORK_CORP_SECRET": os.getenv("WEWORK_CORP_SECRET", ""),
                        "WEWORK_AGENT_ID": os.getenv("WEWORK_AGENT_ID", ""),
                    }
                }
            }

            # Create Claude Agent Options (single Agent architecture)
            options = ClaudeAgentOptions(
                # Use claude_code preset and add unified Agent instructions
                system_prompt={
                    "type": "preset",
                    "preset": "claude_code",
                    "append": f"\n\n{unified_agent_def.prompt}"
                },

                # No sub-Agents (single Agent architecture)
                agents=None,

                # Configure MCP servers
                mcp_servers=mcp_servers,

                # Fully integrated toolset (remove Task, add all functional tools)
                allowed_tools=[
                    "Read",   # Read files
                    "Write",  # Write files
                    "Grep",   # Search content
                    "Glob",   # Find files
                    "Bash",   # Execute commands
                    "mcp__markitdown__convert_to_markdown",  # markitdown MCP tool
                    # WeWork (企业微信) message notification tools
                    "mcp__wework__wework_send_text_message",
                    "mcp__wework__wework_send_markdown_message",
                    "mcp__wework__wework_send_image_message",
                    "mcp__wework__wework_send_file_message",
                    "mcp__wework__wework_upload_media",
                ],

                # Working directory (set to project root to access knowledge_base/)
                cwd=str(kb_path.parent),

                # Permission mode: auto-accept edits
                permission_mode="acceptEdits",

                # Environment variables
                env=env_vars,

                # Don't load filesystem config (fully programmatic config)
                setting_sources=None
            )

            logger.info("\n✅ ClaudeAgentOptions creation complete (single Agent architecture)")
            logger.info(f"✅ MCP Servers: {list(mcp_servers.keys())}")

            # Create Client
            self.client = ClaudeSDKClient(options=options)

            # Connect (don't pass initial prompt, wait for user query)
            await self.client.connect()

            self.is_initialized = True
            logger.info("✅ Knowledge base service initialized successfully")
            logger.info(f"✅ Working directory: {options.cwd}")
            logger.info(f"✅ Single Agent architecture: Unified Intelligent KB Agent")
            logger.info(f"✅ Available tools: {', '.join(options.allowed_tools)}")
            logger.info(f"✅ MCP Servers loaded: {', '.join(mcp_servers.keys())}")

        except Exception as e:
            logger.error(f"❌ Knowledge base service initialization failed: {e}")
            raise

    async def query(
        self,
        user_message: str,
        session_id: str = "default"
    ) -> AsyncIterator[Message]:
        """
        Query knowledge base

        Args:
            user_message: User message
            session_id: Session ID (for multi-session management)

        Yields:
            Message stream

        Example:
            async for message in kb_service.query("How to configure CORS?"):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(block.text)
        """
        if not self.is_initialized:
            raise RuntimeError("Service not initialized, please call initialize() first")

        try:
            # Log complete user input
            logger.info(f"📝 Received query [session: {session_id}]")
            logger.info(f"{'='*80}")
            logger.info(f"User input:\n{user_message}")
            logger.info(f"{'='*80}")

            # Send query to Claude (with session ID)
            await self.client.query(user_message, session_id=session_id)

            # Receive response
            turn_number = 0
            async for message in self.client.receive_response():
                # Log each message in detail
                if isinstance(message, AssistantMessage):
                    turn_number += 1
                    logger.info(f"\n{'─'*80}")
                    logger.info(f"🤖 Agent response - Turn {turn_number} [session: {session_id}]")
                    logger.info(f"{'─'*80}")

                    for block in message.content:
                        if isinstance(block, TextBlock):
                            logger.info(f"📄 Text output:\n{block.text}")
                        elif isinstance(block, ToolUseBlock):
                            logger.info(f"🔧 Tool call: {block.name}")
                            logger.info(f"   Parameters: {block.input}")

                    logger.info(f"{'─'*80}\n")

                else:
                    # Log other message types (may include tool results)
                    message_type = type(message).__name__
                    logger.info(f"\n{'┄'*80}")
                    logger.info(f"📦 Message type: {message_type} [session: {session_id}]")

                    # Try to extract tool results
                    if hasattr(message, 'content'):
                        logger.info(f"📋 Message content:")
                        if isinstance(message.content, list):
                            for idx, block in enumerate(message.content):
                                block_type = type(block).__name__
                                logger.info(f"   Block {idx} type: {block_type}")

                                # Print all block attributes
                                if hasattr(block, '__dict__'):
                                    for key, value in block.__dict__.items():
                                        if not key.startswith('_'):
                                            # Truncate if value is too long
                                            value_str = str(value)
                                            if len(value_str) > 500:
                                                value_str = value_str[:500] + f"... (truncated, total {len(value_str)} chars)"
                                            logger.info(f"      {key}: {value_str}")
                        else:
                            content_str = str(message.content)
                            if len(content_str) > 1000:
                                content_str = content_str[:1000] + f"... (truncated, total {len(content_str)} chars)"
                            logger.info(f"   {content_str}")

                    # Print all message object attributes
                    if hasattr(message, '__dict__'):
                        logger.info(f"📊 Message attributes:")
                        for key, value in message.__dict__.items():
                            if not key.startswith('_') and key != 'content':
                                logger.info(f"   {key}: {value}")

                    logger.info(f"{'┄'*80}\n")

                yield message

                # Log final result
                if isinstance(message, ResultMessage):
                    logger.info(f"\n{'='*80}")
                    logger.info(
                        f"✅ Query completed [session: {session_id}] "
                        f"Duration: {message.duration_ms}ms "
                        f"Turns: {message.num_turns}"
                    )
                    logger.info(f"{'='*80}\n")

        except Exception as e:
            logger.error(f"❌ Query failed: {e}")
            raise

    async def close(self):
        """Close service and release resources"""
        if self.client:
            try:
                await self.client.disconnect()
                logger.info("✅ Knowledge base service closed")
            except Exception as e:
                logger.error(f"❌ Failed to close service: {e}")
        self.is_initialized = False

    async def __aenter__(self):
        """Support async with syntax"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Support async with syntax"""
        await self.close()

    def get_agent_info(self) -> dict:
        """
        Get Agent information

        Returns:
            Agent configuration info
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
        Get service status

        Returns:
            Service status information
        """
        return {
            "initialized": self.is_initialized,
            "architecture": "single_agent",
            "kb_path": str(self.settings.KB_ROOT_PATH),
            "api_key_configured": bool(self.settings.CLAUDE_API_KEY)
        }


# Singleton instance
_kb_service_instance: Optional[KnowledgeBaseService] = None


def get_kb_service() -> KnowledgeBaseService:
    """
    Get knowledge base service singleton

    Returns:
        KnowledgeBaseService instance
    """
    global _kb_service_instance
    if _kb_service_instance is None:
        _kb_service_instance = KnowledgeBaseService()
    return _kb_service_instance


# Export
__all__ = [
    "KnowledgeBaseService",
    "get_kb_service"
]
