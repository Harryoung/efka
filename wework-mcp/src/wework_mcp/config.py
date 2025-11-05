"""
配置管理模块
从环境变量加载企业微信配置
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class WeWorkConfig:
    """企业微信配置"""
    corp_id: str  # 企业ID
    corp_secret: str  # 应用凭证密钥
    agent_id: int  # 应用ID
    api_base_url: str = "https://qyapi.weixin.qq.com/cgi-bin"
    token_cache_file: str = ".wework_token_cache"  # token 缓存文件路径
    request_timeout: int = 30  # 请求超时时间（秒）
    max_retries: int = 3  # 最大重试次数

    @classmethod
    def from_env(cls) -> "WeWorkConfig":
        """从环境变量加载配置"""
        corp_id = os.getenv("WEWORK_CORP_ID")
        corp_secret = os.getenv("WEWORK_CORP_SECRET")
        agent_id = os.getenv("WEWORK_AGENT_ID")

        if not corp_id or not corp_secret or not agent_id:
            raise ValueError(
                "Missing required environment variables: "
                "WEWORK_CORP_ID, WEWORK_CORP_SECRET, WEWORK_AGENT_ID"
            )

        return cls(
            corp_id=corp_id,
            corp_secret=corp_secret,
            agent_id=int(agent_id),
            api_base_url=os.getenv("WEWORK_API_BASE_URL", cls.__dataclass_fields__['api_base_url'].default),
            token_cache_file=os.getenv("WEWORK_TOKEN_CACHE_FILE", cls.__dataclass_fields__['token_cache_file'].default),
            request_timeout=int(os.getenv("WEWORK_REQUEST_TIMEOUT", str(cls.__dataclass_fields__['request_timeout'].default))),
            max_retries=int(os.getenv("WEWORK_MAX_RETRIES", str(cls.__dataclass_fields__['max_retries'].default))),
        )

    def validate(self) -> None:
        """验证配置有效性"""
        if not self.corp_id.startswith("ww"):
            raise ValueError(f"Invalid corp_id format: {self.corp_id}")
        if len(self.corp_secret) != 32:
            raise ValueError("corp_secret must be 32 characters")
        if self.agent_id <= 0:
            raise ValueError(f"Invalid agent_id: {self.agent_id}")
