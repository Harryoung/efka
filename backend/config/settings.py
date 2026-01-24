"""
Application settings and configuration management.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pydantic import model_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Claude API configuration
    # Supports:
    # - CLAUDE_API_KEY (project-level naming)
    # - ANTHROPIC_API_KEY (upstream/Claude Code naming)
    # - ANTHROPIC_AUTH_TOKEN (+ optional ANTHROPIC_BASE_URL)
    CLAUDE_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_AUTH_TOKEN: Optional[str] = None
    ANTHROPIC_BASE_URL: Optional[str] = None

    # Knowledge base configuration
    KB_ROOT_PATH: str = "./knowledge_base"
    SMALL_FILE_KB_THRESHOLD: int = 30  # KB
    FAQ_MAX_ENTRIES: int = 50

    # Service configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False  # Debug mode

    # Session configuration
    SESSION_TIMEOUT: int = 1800  # 30 minutes
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB

    # Redis configuration
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_USERNAME: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None

    # WeChat Work (企业微信) configuration (optional)
    WEWORK_CORP_ID: Optional[str] = None
    WEWORK_CORP_SECRET: Optional[str] = None
    WEWORK_AGENT_ID: Optional[str] = None
    WEWORK_TOKEN: Optional[str] = None
    WEWORK_ENCODING_AES_KEY: Optional[str] = None
    WEWORK_PORT: int = 8081  # WeWork callback service port

    # Conversation state configuration
    CONVERSATION_STATE_TTL: int = 86400  # 24 hours
    EXPERT_REPLY_TIMEOUT: int = 86400  # 24 hours
    FILE_LOCK_TIMEOUT: int = 5  # 5 seconds

    # CORS configuration
    ALLOWED_ORIGINS: list = ["http://localhost:3000", "http://localhost:3001", "http://localhost"]

    # Vision Model configuration (for image_read tool)
    VISION_MODEL_PROVIDER: Optional[str] = None  # doubao, openai, anthropic
    VISION_MODEL_API_KEY: Optional[str] = None
    VISION_MODEL_BASE_URL: Optional[str] = None
    VISION_MODEL_NAME: Optional[str] = None

    # PaddleOCR configuration (for smart_convert.py)
    PADDLE_OCR_TOKEN: Optional[str] = None

    # Client connection pool configuration
    USER_CLIENT_POOL_SIZE: int = 3  # User service pool size (high-frequency queries)
    ADMIN_CLIENT_POOL_SIZE: int = 2     # Admin service pool size (low-frequency operations)
    CLIENT_POOL_MAX_WAIT: int = 30      # Maximum wait time to acquire client (seconds)

    # Feishu (飞书) configuration
    FEISHU_APP_ID: Optional[str] = None
    FEISHU_APP_SECRET: Optional[str] = None
    FEISHU_VERIFICATION_TOKEN: Optional[str] = None
    FEISHU_ENCRYPT_KEY: Optional[str] = None
    FEISHU_PORT: int = 8082

    # DingTalk (钉钉) configuration
    DINGTALK_CORP_ID: Optional[str] = None
    DINGTALK_APP_KEY: Optional[str] = None
    DINGTALK_APP_SECRET: Optional[str] = None
    DINGTALK_PORT: int = 8083

    # Slack configuration
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_SIGNING_SECRET: Optional[str] = None
    SLACK_APP_TOKEN: Optional[str] = None
    SLACK_PORT: int = 8084

    # User UI 配置
    USER_UI_ENABLED: bool = True
    USER_UI_PORT: int = 3001

    @model_validator(mode='after')
    def validate_api_key(self):
        """Validate that at least one authentication method is configured"""
        if not self.CLAUDE_API_KEY and self.ANTHROPIC_API_KEY:
            self.CLAUDE_API_KEY = self.ANTHROPIC_API_KEY
        if not self.CLAUDE_API_KEY and not self.ANTHROPIC_AUTH_TOKEN:
            raise ValueError(
                "Either CLAUDE_API_KEY or ANTHROPIC_AUTH_TOKEN must be configured"
            )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


# Create global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get the settings instance

    Returns:
        Settings instance
    """
    return settings
