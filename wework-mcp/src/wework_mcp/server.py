"""
WeWork MCP 服务器主程序
实现 MCP 协议，暴露企业微信消息发送工具
"""
import asyncio
import logging
from typing import Any, Dict, List
from mcp.server import Server
from mcp.types import Tool, TextContent

from .config import WeWorkConfig
from .weework_client import WeWorkClient, WeWorkAPIError


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class WeWorkMCPServer:
    """WeWork MCP 服务器"""

    def __init__(self):
        self.config = WeWorkConfig.from_env()
        self.config.validate()
        self.client = WeWorkClient(self.config)
        self.server = Server("wework-mcp")
        self._register_handlers()

    def _register_handlers(self):
        """注册 MCP 协议处理器"""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """列出所有可用工具"""
            return [
                Tool(
                    name="wework_send_text_message",
                    description=(
                        "Send a text message to WeWork (Enterprise WeChat) users. "
                        "Use this tool to notify employees about knowledge base updates, "
                        "document processing results, or system alerts."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "touser": {
                                "type": "string",
                                "description": (
                                    "User ID list, separated by '|'. Max 1000 users. "
                                    "Use '@all' to send to all application members. "
                                    "Example: 'zhangsan|lisi' or '@all'"
                                ),
                            },
                            "content": {
                                "type": "string",
                                "description": (
                                    "Message content, max 2048 bytes. "
                                    "Supports line breaks (\\n) and <a> tags for links."
                                ),
                            },
                            "safe": {
                                "type": "integer",
                                "description": (
                                    "Whether this is a confidential message. "
                                    "0 = can share externally (default), 1 = cannot share (with watermark)"
                                ),
                                "default": 0,
                                "enum": [0, 1],
                            },
                        },
                        "required": ["touser", "content"],
                    },
                ),
                Tool(
                    name="wework_send_markdown_message",
                    description=(
                        "Send a Markdown formatted message to WeWork users. "
                        "Supports rich text formatting including headers, bold, links, "
                        "inline code, quotes, and colored fonts."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "touser": {
                                "type": "string",
                                "description": (
                                    "User ID list, separated by '|'. Max 1000 users. "
                                    "Use '@all' for all members."
                                ),
                            },
                            "content": {
                                "type": "string",
                                "description": (
                                    "Markdown content, max 2048 bytes. "
                                    "Supports subset of Markdown: headers (# to ######), "
                                    "**bold**, [links](url), `code`, > quotes, "
                                    "<font color='info|comment|warning'>text</font>"
                                ),
                            },
                        },
                        "required": ["touser", "content"],
                    },
                ),
                Tool(
                    name="wework_send_image_message",
                    description=(
                        "Send an image message to WeWork users. "
                        "Requires uploading the image first to get a media_id."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "touser": {
                                "type": "string",
                                "description": "User ID list, separated by '|'",
                            },
                            "media_id": {
                                "type": "string",
                                "description": (
                                    "Image media file ID obtained from upload_media API. "
                                    "Valid for 3 days."
                                ),
                            },
                            "safe": {
                                "type": "integer",
                                "description": "Confidential message flag (0 or 1)",
                                "default": 0,
                                "enum": [0, 1],
                            },
                        },
                        "required": ["touser", "media_id"],
                    },
                ),
                Tool(
                    name="wework_send_file_message",
                    description=(
                        "Send a file message to WeWork users. "
                        "Requires uploading the file first to get a media_id."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "touser": {
                                "type": "string",
                                "description": "User ID list, separated by '|'",
                            },
                            "media_id": {
                                "type": "string",
                                "description": (
                                    "File media ID obtained from upload_media API. "
                                    "Valid for 3 days."
                                ),
                            },
                            "safe": {
                                "type": "integer",
                                "description": "Confidential message flag (0 or 1)",
                                "default": 0,
                                "enum": [0, 1],
                            },
                        },
                        "required": ["touser", "media_id"],
                    },
                ),
                Tool(
                    name="wework_upload_media",
                    description=(
                        "Upload a temporary media file (image/voice/video/file) "
                        "to WeWork and get a media_id. The media_id is valid for 3 days."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "media_type": {
                                "type": "string",
                                "description": "Media file type",
                                "enum": ["image", "voice", "video", "file"],
                            },
                            "file_path": {
                                "type": "string",
                                "description": "Absolute path to the file to upload",
                            },
                        },
                        "required": ["media_type", "file_path"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """调用工具"""
            try:
                logger.info(f"Tool called: {name} with arguments: {arguments}")

                if name == "wework_send_text_message":
                    result = self.client.send_text(
                        touser=arguments["touser"],
                        content=arguments["content"],
                        safe=arguments.get("safe", 0),
                    )

                elif name == "wework_send_markdown_message":
                    result = self.client.send_markdown(
                        touser=arguments["touser"],
                        content=arguments["content"],
                    )

                elif name == "wework_send_image_message":
                    result = self.client.send_image(
                        touser=arguments["touser"],
                        media_id=arguments["media_id"],
                        safe=arguments.get("safe", 0),
                    )

                elif name == "wework_send_file_message":
                    result = self.client.send_file(
                        touser=arguments["touser"],
                        media_id=arguments["media_id"],
                        safe=arguments.get("safe", 0),
                    )

                elif name == "wework_upload_media":
                    media_id = self.client.upload_media(
                        media_type=arguments["media_type"],
                        file_path=arguments["file_path"],
                    )
                    result = {"media_id": media_id}

                else:
                    raise ValueError(f"Unknown tool: {name}")

                # 格式化响应
                return [
                    TextContent(
                        type="text",
                        text=self._format_success_response(name, result),
                    )
                ]

            except WeWorkAPIError as e:
                logger.error(f"WeWork API error: {e}")
                return [
                    TextContent(
                        type="text",
                        text=self._format_error_response(name, e.errcode, e.errmsg),
                    )
                ]

            except Exception as e:
                logger.error(f"Tool execution error: {e}", exc_info=True)
                return [
                    TextContent(
                        type="text",
                        text=self._format_error_response(name, -1, str(e)),
                    )
                ]

    def _format_success_response(self, tool_name: str, result: Dict[str, Any]) -> str:
        """格式化成功响应"""
        msgid = result.get("msgid", "N/A")
        invalid_user = result.get("invaliduser", "")

        response = f"✅ Message sent successfully via {tool_name}\n"
        response += f"Message ID: {msgid}\n"

        if invalid_user:
            response += f"⚠️ Invalid users (not sent): {invalid_user}\n"

        if "media_id" in result:
            response += f"Media ID: {result['media_id']}\n"

        return response

    def _format_error_response(self, tool_name: str, errcode: int, errmsg: str) -> str:
        """格式化错误响应"""
        return (
            f"❌ Failed to execute {tool_name}\n"
            f"Error Code: {errcode}\n"
            f"Error Message: {errmsg}\n"
        )

    async def run(self):
        """运行 MCP 服务器"""
        logger.info("Starting WeWork MCP Server...")
        logger.info(f"Corp ID: {self.config.corp_id}")
        logger.info(f"Agent ID: {self.config.agent_id}")

        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


def main():
    """主函数"""
    try:
        server = WeWorkMCPServer()
        asyncio.run(server.run())
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
