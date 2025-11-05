"""
企业微信 API 客户端
封装企业微信消息发送接口
"""
import logging
import time
from typing import Any, Dict, List, Optional
import requests

from .config import WeWorkConfig
from .token_manager import AccessTokenManager


logger = logging.getLogger(__name__)


class WeWorkAPIError(Exception):
    """企业微信 API 错误"""

    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"WeWork API Error {errcode}: {errmsg}")


class WeWorkClient:
    """企业微信 API 客户端"""

    def __init__(self, config: WeWorkConfig):
        self.config = config
        self.token_manager = AccessTokenManager(config)

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        带重试的 HTTP 请求
        处理 access_token 过期等错误
        """
        last_exception = None

        for attempt in range(self.config.max_retries):
            try:
                response = requests.request(
                    method,
                    url,
                    timeout=self.config.request_timeout,
                    **kwargs
                )
                response.raise_for_status()
                data = response.json()

                errcode = data.get("errcode", 0)

                # 成功
                if errcode == 0:
                    return data

                # access_token 过期或无效，刷新后重试
                if errcode in [40014, 42001]:
                    logger.warning(f"Access token expired (errcode={errcode}), refreshing...")
                    self.token_manager.invalidate_token()
                    # 更新 URL 中的 token
                    if "params" in kwargs:
                        kwargs["params"]["access_token"] = self.token_manager.get_token()
                    continue

                # 其他错误，抛出异常
                raise WeWorkAPIError(errcode, data.get("errmsg", "Unknown error"))

            except requests.RequestException as e:
                last_exception = e
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                continue

        # 所有重试都失败
        raise Exception(f"Request failed after {self.config.max_retries} attempts: {last_exception}")

    def send_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送消息通用接口

        Args:
            message_data: 消息数据（符合企业微信 API 格式）

        Returns:
            API 响应数据

        Raises:
            WeWorkAPIError: API 返回错误
            Exception: 网络或其他错误
        """
        # 自动添加 agentid
        if "agentid" not in message_data:
            message_data["agentid"] = self.config.agent_id

        access_token = self.token_manager.get_token()
        url = f"{self.config.api_base_url}/message/send"

        logger.info(f"Sending message to WeWork API: {message_data.get('msgtype')}")

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
        """
        发送文本消息

        Args:
            touser: 成员ID列表，多个用'|'分隔，最多1000个。特殊值"@all"表示全员
            content: 消息内容，最长2048字节
            safe: 是否保密消息，0=可分享，1=不可分享
            enable_duplicate_check: 是否开启重复消息检查

        Returns:
            API 响应
        """
        message_data = {
            "touser": touser,
            "msgtype": "text",
            "text": {
                "content": content
            },
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
        """
        发送 Markdown 消息

        Args:
            touser: 成员ID列表
            content: Markdown 内容，最长2048字节
            enable_duplicate_check: 是否开启重复消息检查

        Returns:
            API 响应
        """
        message_data = {
            "touser": touser,
            "msgtype": "markdown",
            "markdown": {
                "content": content
            },
            "enable_duplicate_check": enable_duplicate_check,
        }
        return self.send_message(message_data)

    def send_image(
        self,
        touser: str,
        media_id: str,
        safe: int = 0,
    ) -> Dict[str, Any]:
        """
        发送图片消息

        Args:
            touser: 成员ID列表
            media_id: 图片媒体文件ID（需先上传）
            safe: 是否保密消息

        Returns:
            API 响应
        """
        message_data = {
            "touser": touser,
            "msgtype": "image",
            "image": {
                "media_id": media_id
            },
            "safe": safe,
        }
        return self.send_message(message_data)

    def send_file(
        self,
        touser: str,
        media_id: str,
        safe: int = 0,
    ) -> Dict[str, Any]:
        """
        发送文件消息

        Args:
            touser: 成员ID列表
            media_id: 文件媒体文件ID（需先上传）
            safe: 是否保密消息

        Returns:
            API 响应
        """
        message_data = {
            "touser": touser,
            "msgtype": "file",
            "file": {
                "media_id": media_id
            },
            "safe": safe,
        }
        return self.send_message(message_data)

    def upload_media(
        self,
        media_type: str,
        file_path: str,
    ) -> str:
        """
        上传临时素材

        Args:
            media_type: 媒体文件类型，image/voice/video/file
            file_path: 文件路径

        Returns:
            media_id
        """
        access_token = self.token_manager.get_token()
        url = f"{self.config.api_base_url}/media/upload"

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
        logger.info(f"Uploaded media file: {file_path}, media_id: {media_id}")
        return media_id
