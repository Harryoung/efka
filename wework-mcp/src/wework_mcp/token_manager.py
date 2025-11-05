"""
Access Token 管理模块
负责 token 的获取、缓存和自动刷新
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
import requests

from .config import WeWorkConfig


logger = logging.getLogger(__name__)


@dataclass
class TokenCache:
    """Token 缓存结构"""
    access_token: str
    expires_at: float  # Unix timestamp


class AccessTokenManager:
    """Access Token 管理器"""

    def __init__(self, config: WeWorkConfig):
        self.config = config
        self.cache_file = Path(config.token_cache_file)
        self._token_cache: Optional[TokenCache] = None
        self._load_cache()

    def _load_cache(self) -> None:
        """从文件加载缓存的 token"""
        if not self.cache_file.exists():
            return

        try:
            with open(self.cache_file, "r") as f:
                data = json.load(f)
                self._token_cache = TokenCache(**data)
                logger.info("Loaded access token from cache")
        except Exception as e:
            logger.warning(f"Failed to load token cache: {e}")
            self._token_cache = None

    def _save_cache(self) -> None:
        """保存 token 到文件"""
        if not self._token_cache:
            return

        try:
            with open(self.cache_file, "w") as f:
                json.dump(asdict(self._token_cache), f)
            logger.info("Saved access token to cache")
        except Exception as e:
            logger.warning(f"Failed to save token cache: {e}")

    def _is_token_valid(self) -> bool:
        """检查缓存的 token 是否有效"""
        if not self._token_cache:
            return False

        # 提前 5 分钟刷新，避免边界情况
        return time.time() < (self._token_cache.expires_at - 300)

    def _fetch_new_token(self) -> str:
        """从企业微信 API 获取新的 access token"""
        url = f"{self.config.api_base_url}/gettoken"
        params = {
            "corpid": self.config.corp_id,
            "corpsecret": self.config.corp_secret,
        }

        logger.info("Fetching new access token from WeWork API")

        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.config.request_timeout,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("errcode") != 0:
                error_msg = data.get("errmsg", "Unknown error")
                raise Exception(f"WeWork API error: {data.get('errcode')} - {error_msg}")

            access_token = data["access_token"]
            expires_in = data["expires_in"]  # 通常是 7200 秒

            # 缓存 token
            self._token_cache = TokenCache(
                access_token=access_token,
                expires_at=time.time() + expires_in,
            )
            self._save_cache()

            logger.info(f"Successfully fetched new access token (expires in {expires_in}s)")
            return access_token

        except requests.RequestException as e:
            logger.error(f"Failed to fetch access token: {e}")
            raise Exception(f"Failed to fetch access token: {e}")

    def get_token(self) -> str:
        """
        获取有效的 access token
        如果缓存有效则返回缓存，否则获取新 token
        """
        if self._is_token_valid():
            logger.debug("Using cached access token")
            return self._token_cache.access_token

        return self._fetch_new_token()

    def invalidate_token(self) -> None:
        """使当前 token 失效，强制下次刷新"""
        logger.info("Invalidating current access token")
        self._token_cache = None
        if self.cache_file.exists():
            self.cache_file.unlink()
