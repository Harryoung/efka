"""
企业微信 API 客户端

封装企业微信API调用,负责:
1. Access Token管理
2. 消息发送(文本/Markdown/图片/文件)
3. 媒体文件上传
4. 用户信息查询
"""

import logging
import time
import os
from typing import Any, Dict, List, Optional
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class WeWorkAPIError(Exception):
    """企业微信 API 错误"""

    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"WeWork API Error {errcode}: {errmsg}")


class AccessTokenManager:
    """Access Token管理器"""

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
        """获取有效的access_token(自动刷新)"""
        if self._token and self._expires_at and datetime.now() < self._expires_at:
            return self._token

        # Token过期或不存在,重新获取
        return self._fetch_token()

    def _fetch_token(self) -> str:
        """从企微API获取access_token"""
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
            # 提前5分钟过期,避免临界情况
            self._expires_at = datetime.now() + timedelta(seconds=expires_in - 300)

            logger.info(f"Access token refreshed, expires in {expires_in}s")
            return self._token

        except requests.RequestException as e:
            logger.error(f"Failed to fetch access token: {e}")
            raise Exception(f"Failed to fetch access token: {e}")

    def invalidate_token(self):
        """使token失效,强制下次重新获取"""
        self._token = None
        self._expires_at = None
        logger.info("Access token invalidated")


class WeWorkClient:
    """企业微信 API 客户端"""

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
        初始化企微客户端

        Args:
            corp_id: 企业ID
            corp_secret: 应用Secret
            agent_id: 应用AgentID
            api_base_url: API基础URL
            max_retries: 最大重试次数
            request_timeout: 请求超时时间(秒)
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
        带重试的HTTP请求

        处理token过期等错误,自动重试
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

                # 成功
                if errcode == 0:
                    return data

                # access_token过期或无效,刷新后重试
                if errcode in [40014, 42001]:
                    logger.warning(f"Access token expired (errcode={errcode}), refreshing...")
                    self.token_manager.invalidate_token()
                    # 更新URL中的token
                    if "params" in kwargs:
                        kwargs["params"]["access_token"] = self.token_manager.get_token()
                    continue

                # 其他错误,抛出异常
                raise WeWorkAPIError(errcode, data.get("errmsg", "Unknown error"))

            except requests.RequestException as e:
                last_exception = e
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                continue

        # 所有重试都失败
        raise Exception(f"Request failed after {self.max_retries} attempts: {last_exception}")

    def send_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送消息通用接口

        Args:
            message_data: 消息数据(符合企微API格式)

        Returns:
            API响应数据

        Raises:
            WeWorkAPIError: API返回错误
        """
        # 自动添加agentid
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
        """发送文本消息"""
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
        """发送Markdown消息"""
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
        """发送图片消息"""
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
        """发送文件消息"""
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
        上传临时素材

        Args:
            media_type: 媒体文件类型(image/voice/video/file)
            file_path: 文件路径

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
        获取用户详细信息

        Args:
            userid: 用户ID

        Returns:
            用户信息字典
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
