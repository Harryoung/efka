"""
WeWork (企业微信) API Client

Encapsulates WeWork API calls, responsible for:
1. Access Token management
2. Message sending (text/Markdown/image/file)
3. Media file upload
4. User information query
"""

import logging
import time
import os
from typing import Any, Dict, List, Optional
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class WeWorkAPIError(Exception):
    """WeWork (企业微信) API Error"""

    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"WeWork API Error {errcode}: {errmsg}")


class AccessTokenManager:
    """Access Token Manager"""

    def __init__(
        self,
        corp_id: str,
        corp_secret: str,
        api_base_url: str = "https://qyapi.weixin.qq.com/cgi-bin"
    ):
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self.api_base_url = api_base_url
        self._token: Optional[str] = None
        self._expires_at: Optional[datetime] = None

    def get_token(self) -> str:
        """Get valid access_token (auto-refresh)"""
        if self._token and self._expires_at and datetime.now() < self._expires_at:
            return self._token

        # Token expired or doesn't exist, fetch new one
        return self._fetch_token()

    def _fetch_token(self) -> str:
        """Fetch access_token from WeWork API"""
        url = f"{self.api_base_url}/gettoken"
        params = {
            "corpid": self.corp_id,
            "corpsecret": self.corp_secret
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            errcode = data.get("errcode", 0)
            if errcode != 0:
                errmsg = data.get("errmsg", "Unknown error")
                raise WeWorkAPIError(errcode, errmsg)

            self._token = data["access_token"]
            expires_in = data["expires_in"]
            # Expire 5 minutes early to avoid edge cases
            self._expires_at = datetime.now() + timedelta(seconds=expires_in - 300)

            logger.info(f"Access token refreshed, expires in {expires_in}s")
            return self._token

        except requests.RequestException as e:
            logger.error(f"Failed to fetch access token: {e}")
            raise Exception(f"Failed to fetch access token: {e}")

    def invalidate_token(self):
        """Invalidate token, force re-fetch on next use"""
        self._token = None
        self._expires_at = None
        logger.info("Access token invalidated")


class WeWorkClient:
    """WeWork (企业微信) API Client"""

    def __init__(
        self,
        corp_id: str,
        corp_secret: str,
        agent_id: int,
        api_base_url: str = "https://qyapi.weixin.qq.com/cgi-bin",
        max_retries: int = 3,
        request_timeout: int = 30
    ):
        """
        Initialize WeWork client

        Args:
            corp_id: Corporate ID
            corp_secret: Application Secret
            agent_id: Application AgentID
            api_base_url: API base URL
            max_retries: Maximum retry attempts
            request_timeout: Request timeout (seconds)
        """
        self.corp_id = corp_id
        self.agent_id = agent_id
        self.api_base_url = api_base_url
        self.max_retries = max_retries
        self.request_timeout = request_timeout

        self.token_manager = AccessTokenManager(corp_id, corp_secret, api_base_url)

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        HTTP request with retry

        Handles token expiration and other errors, auto-retry
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method,
                    url,
                    timeout=self.request_timeout,
                    **kwargs
                )
                response.raise_for_status()
                data = response.json()

                errcode = data.get("errcode", 0)

                # Success
                if errcode == 0:
                    return data

                # access_token expired or invalid, refresh and retry
                if errcode in [40014, 42001]:
                    logger.warning(f"Access token expired (errcode={errcode}), refreshing...")
                    self.token_manager.invalidate_token()
                    # Update token in URL
                    if "params" in kwargs:
                        kwargs["params"]["access_token"] = self.token_manager.get_token()
                    continue

                # Other errors, raise exception
                raise WeWorkAPIError(errcode, data.get("errmsg", "Unknown error"))

            except requests.RequestException as e:
                last_exception = e
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue

        # All retries failed
        raise Exception(f"Request failed after {self.max_retries} attempts: {last_exception}")

    def send_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic message sending interface

        Args:
            message_data: Message data (conforming to WeWork API format)

        Returns:
            API response data

        Raises:
            WeWorkAPIError: API returned error
        """
        # Auto-add agentid
        if "agentid" not in message_data:
            message_data["agentid"] = self.agent_id

        access_token = self.token_manager.get_token()
        url = f"{self.api_base_url}/message/send"

        logger.info(f"Sending message: type={message_data.get('msgtype')}, to={message_data.get('touser', 'N/A')[:20]}")

        response = self._request_with_retry(
            "POST",
            url,
            params={"access_token": access_token},
            json=message_data,
        )

        logger.info(f"Message sent successfully, msgid: {response.get('msgid')}")
        return response

    def send_text(
        self,
        touser: str,
        content: str,
        safe: int = 0,
        enable_duplicate_check: int = 0,
    ) -> Dict[str, Any]:
        """Send text message"""
        message_data = {
            "touser": touser,
            "msgtype": "text",
            "text": {"content": content},
            "safe": safe,
            "enable_duplicate_check": enable_duplicate_check,
        }
        return self.send_message(message_data)

    def send_markdown(
        self,
        touser: str,
        content: str,
        enable_duplicate_check: int = 0,
    ) -> Dict[str, Any]:
        """Send Markdown message"""
        message_data = {
            "touser": touser,
            "msgtype": "markdown",
            "markdown": {"content": content},
            "enable_duplicate_check": enable_duplicate_check,
        }
        return self.send_message(message_data)

    def send_image(
        self,
        touser: str,
        media_id: str,
        safe: int = 0,
    ) -> Dict[str, Any]:
        """Send image message"""
        message_data = {
            "touser": touser,
            "msgtype": "image",
            "image": {"media_id": media_id},
            "safe": safe,
        }
        return self.send_message(message_data)

    def send_file(
        self,
        touser: str,
        media_id: str,
        safe: int = 0,
    ) -> Dict[str, Any]:
        """Send file message"""
        message_data = {
            "touser": touser,
            "msgtype": "file",
            "file": {"media_id": media_id},
            "safe": safe,
        }
        return self.send_message(message_data)

    def upload_media(
        self,
        media_type: str,
        file_path: str,
    ) -> str:
        """
        Upload temporary media

        Args:
            media_type: Media file type (image/voice/video/file)
            file_path: File path

        Returns:
            media_id
        """
        access_token = self.token_manager.get_token()
        url = f"{self.api_base_url}/media/upload"

        with open(file_path, "rb") as f:
            files = {"media": f}
            params = {
                "access_token": access_token,
                "type": media_type,
            }

            response = self._request_with_retry(
                "POST",
                url,
                params=params,
                files=files,
            )

        media_id = response.get("media_id")
        logger.info(f"Uploaded media: {file_path}, media_id: {media_id}")
        return media_id

    def get_user_info(self, userid: str) -> Dict[str, Any]:
        """
        Get user detailed information

        Args:
            userid: User ID

        Returns:
            User information dictionary
        """
        access_token = self.token_manager.get_token()
        url = f"{self.api_base_url}/user/get"

        response = self._request_with_retry(
            "GET",
            url,
            params={
                "access_token": access_token,
                "userid": userid
            }
        )

        logger.info(f"Retrieved user info for {userid}")
        return response
