"""
Session Router Service - Session路由服务

封装Session Router Agent的调用逻辑
提供route_to_session方法供wework_callback使用
"""

import logging
import json
import os
from typing import Optional, Dict
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions
)

from backend.agents.session_router_agent import get_session_router_agent_definition
from backend.services.routing_session_manager import get_routing_session_manager
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)


class SessionRouterService:
    """
    Session路由服务

    职责：
    - 调用Session Router Agent判断消息归属
    - 脚手架层直接传入结构化JSON（候选sessions已查询）
    - 返回路由决策（session_id或NEW_SESSION）

    注：不再使用内嵌工具，所有数据通过JSON传入Agent
    """

    def __init__(self):
        """初始化Session Router服务"""
        self.settings = get_settings()
        self.client: Optional[ClaudeSDKClient] = None
        self.is_initialized = False
        self.routing_session_manager = None

        logger.info("SessionRouterService instance created")

    async def initialize(self, redis_client=None):
        """
        初始化Session Router Agent SDK客户端

        Args:
            redis_client: Redis客户端（可选）
        """
        if self.is_initialized:
            logger.warning("Session Router service already initialized")
            return

        try:
            # 检查认证
            if not self.settings.CLAUDE_API_KEY and not self.settings.ANTHROPIC_AUTH_TOKEN:
                raise ValueError("Missing authentication: CLAUDE_API_KEY or ANTHROPIC_AUTH_TOKEN")

            # 初始化RoutingSessionManager
            kb_path = Path(self.settings.KB_ROOT_PATH)
            self.routing_session_manager = get_routing_session_manager(
                kb_root=kb_path,
                redis_client=redis_client
            )
            await self.routing_session_manager.initialize()

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

            # 获取Session Router Agent定义
            router_agent_def = get_session_router_agent_definition()

            # 配置内嵌工具（已废弃：脚手架层直接传入结构化JSON，无需工具）
            # custom_tools = self._configure_custom_tools()

            # 创建Claude Agent Options
            options = ClaudeAgentOptions(
                system_prompt={
                    "type": "preset",
                    "preset": "claude_code",
                    "append": f"\n\n{router_agent_def.prompt}"
                },
                agents=None,  # 单一Agent架构
                mcp_servers={},  # 不使用MCP服务器
                allowed_tools=[],  # 不需要工具：所有数据由脚手架层通过JSON传入
                # 已废弃的工具（保留代码但不注册）：
                #   - query_user_sessions: 脚手架层已在route_to_session中查询
                #   - get_session_history: Agent只需要summary，不需要完整历史
                custom_tools={},  # 不注册工具
                cwd=str(kb_path.parent),  # 项目根目录
                permission_mode="acceptEdits",
                env=env_vars,
                setting_sources=None
            )

            # 创建客户端
            self.client = ClaudeSDKClient(options=options)
            await self.client.connect()

            self.is_initialized = True
            logger.info("✅ Session Router service initialized successfully")
            logger.info("   Mode: JSON-only (no custom tools, data passed via structured JSON)")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Session Router service: {e}")
            raise

    def _configure_custom_tools(self) -> Dict:
        """
        配置内嵌工具

        ⚠️ 已废弃（保留代码但不再使用）
        原因：脚手架层（route_to_session）已直接查询候选sessions并通过JSON传入Agent
        Agent不再需要这些工具来查询数据

        Returns:
            工具字典 {tool_name: async_function}
        """
        async def query_user_sessions(
            user_id: str,
            include_expired: bool = False
        ) -> Dict:
            """
            查询用户的所有Sessions（内嵌工具）

            Args:
                user_id: 企业微信userid
                include_expired: 是否包含过期Session

            Returns:
                SessionQueryResult字典
            """
            result = await self.routing_session_manager.query_user_sessions(
                user_id=user_id,
                include_expired=include_expired,
                max_per_role=10  # 限制数量
            )

            # 转换为dict（Session对象需要序列化）
            return {
                "user_id": result.user_id,
                "as_employee": [s.dict() for s in result.as_employee],
                "as_expert": [s.dict() for s in result.as_expert],
                "total_count": result.total_count
            }

        async def get_session_history(
            session_id: str,
            limit: int = 50
        ) -> Dict:
            """
            获取Session完整历史（内嵌工具）

            Args:
                session_id: Session ID
                limit: 最多返回消息数

            Returns:
                历史消息字典
            """
            messages = await self.routing_session_manager.get_session_history(
                session_id=session_id,
                limit=limit
            )

            return {
                "session_id": session_id,
                "messages": messages,
                "count": len(messages)
            }

        return {
            "query_user_sessions": query_user_sessions,
            "get_session_history": get_session_history
        }

    async def route_to_session(
        self,
        user_id: str,
        new_message: str,
        user_info: Dict
    ) -> Dict:
        """
        调用Session Router Agent判断消息归属

        Args:
            user_id: 企业微信userid
            new_message: 新消息内容
            user_info: 用户信息 {"is_expert": bool, "expert_domains": []}

        Returns:
            路由决策 {
                "decision": str,  # session_id or "NEW_SESSION"
                "confidence": float,
                "reasoning": str,
                "matched_role": Optional[str]
            }
        """
        if not self.is_initialized:
            await self.initialize()

        # 查询候选Sessions
        sessions = await self.routing_session_manager.query_user_sessions(
            user_id=user_id,
            include_expired=False,
            max_per_role=10
        )

        # 快捷路径：如果没有候选sessions，直接创建新session
        if sessions.total_count == 0:
            logger.info(f"  No candidate sessions found, creating new session directly (fast path)")
            return {
                "decision": "NEW_SESSION",
                "confidence": 1.0,
                "reasoning": "新用户，无历史Session",
                "matched_role": None
            }

        # 构造Router输入
        from datetime import datetime
        router_input = {
            "user_id": user_id,
            "new_message": new_message,
            "current_time": datetime.now().isoformat(),  # 当前时间戳，用于时间窗口判断
            "user_info": user_info,
            "candidate_sessions": {
                "as_employee": [s.dict() for s in sessions.as_employee],
                "as_expert": [s.dict() for s in sessions.as_expert]
            }
        }

        logger.info(f"Routing message for user {user_id}: {new_message[:50]}...")
        logger.info(f"  Candidate sessions: {sessions.total_count} ({len(sessions.as_employee)} employee, {len(sessions.as_expert)} expert)")

        try:
            # 调用Router Agent
            # 将输入作为JSON字符串发送
            prompt = f"""请根据以下信息判断新消息应该归属到哪个Session：

{json.dumps(router_input, ensure_ascii=False, indent=2)}

请严格按照JSON格式返回你的决策。"""

            response_text = ""
            async for message in self.client.send_message(
                message=prompt,
                session_id=f"router_{user_id}"  # Router自己的session
            ):
                response_text += message.text

            # 解析结果
            try:
                # 提取JSON（可能夹杂在其他文本中）
                import re
                json_match = re.search(r'\{[^\}]*"decision"[^\}]*\}', response_text, re.DOTALL)
                if json_match:
                    decision = json.loads(json_match.group(0))
                else:
                    # 尝试直接解析
                    decision = json.loads(response_text)

                # 验证必需字段
                assert 'decision' in decision
                assert 'confidence' in decision
                assert decision['decision'] == 'NEW_SESSION' or decision['decision'].startswith('sess')

                logger.info(f"  Router decision: {decision['decision']} (confidence: {decision['confidence']})")
                return decision

            except Exception as e:
                logger.error(f"Failed to parse router decision: {e}")
                logger.error(f"Response text: {response_text}")
                # 降级：创建新Session
                return {
                    "decision": "NEW_SESSION",
                    "confidence": 0.0,
                    "reasoning": f"Router error: {str(e)}",
                    "matched_role": None
                }

        except Exception as e:
            logger.error(f"Session Router failed: {e}")
            # 降级：创建新Session
            return {
                "decision": "NEW_SESSION",
                "confidence": 0.0,
                "reasoning": f"Router error: {str(e)}",
                "matched_role": None
            }


# 全局单例
_session_router_service: Optional[SessionRouterService] = None


def get_session_router_service(redis_client=None) -> SessionRouterService:
    """
    获取SessionRouterService单例

    Args:
        redis_client: Redis客户端

    Returns:
        SessionRouterService实例
    """
    global _session_router_service

    if _session_router_service is None:
        _session_router_service = SessionRouterService()

    return _session_router_service


# 导出
__all__ = [
    "SessionRouterService",
    "get_session_router_service"
]
