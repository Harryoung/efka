"""
Application settings and configuration management.
"""
from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import model_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Claude API配置
    # 支持三种方式：CLAUDE_API_KEY 或 ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL
    CLAUDE_API_KEY: Optional[str] = None
    ANTHROPIC_AUTH_TOKEN: Optional[str] = None
    ANTHROPIC_BASE_URL: Optional[str] = None

    # 知识库配置
    KB_ROOT_PATH: str = "./knowledge_base"
    SMALL_FILE_KB_THRESHOLD: int = 30  # KB
    FAQ_MAX_ENTRIES: int = 50

    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False  # 调试模式

    # 会话配置
    SESSION_TIMEOUT: int = 1800  # 30分钟
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB

    # Redis 配置
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_USERNAME: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None

    # 企业微信配置（可选）
    WEWORK_CORP_ID: Optional[str] = None
    WEWORK_CORP_SECRET: Optional[str] = None
    WEWORK_AGENT_ID: Optional[str] = None
    WEWORK_TOKEN: Optional[str] = None
    WEWORK_ENCODING_AES_KEY: Optional[str] = None

    # 会话状态配置
    CONVERSATION_STATE_TTL: int = 86400  # 24小时
    EXPERT_REPLY_TIMEOUT: int = 86400  # 24小时
    FILE_LOCK_TIMEOUT: int = 5  # 5秒

    # CORS配置
    ALLOWED_ORIGINS: list = ["http://localhost:3000", "http://localhost"]

    @model_validator(mode='after')
    def validate_api_key(self):
        """验证至少配置了一种认证方式"""
        if not self.CLAUDE_API_KEY and not self.ANTHROPIC_AUTH_TOKEN:
            raise ValueError(
                "必须配置 CLAUDE_API_KEY 或 ANTHROPIC_AUTH_TOKEN 之一"
            )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局settings实例
settings = Settings()


def get_settings() -> Settings:
    """
    获取设置实例

    Returns:
        Settings 实例
    """
    return settings
