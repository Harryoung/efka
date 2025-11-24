# Channel Development Guide

**目标**: 指导开发者为智能资料库管理员添加新的IM平台支持

**适用版本**: v3.0+

**难度**: 中级 (需要熟悉Python异步编程和目标IM平台API)

**预计时间**: 1-2天/平台

---

## 目录

1. [Channel Adapter架构概述](#channel-adapter架构概述)
2. [开发前准备](#开发前准备)
3. [步骤1: 创建Channel Client](#步骤1-创建channel-client)
4. [步骤2: 实现Channel Adapter](#步骤2-实现channel-adapter)
5. [步骤3: 创建Callback Server](#步骤3-创建callback-server)
6. [步骤4: 注册配置](#步骤4-注册配置)
7. [步骤5: 测试与调试](#步骤5-测试与调试)
8. [最佳实践](#最佳实践)
9. [参考: WeWork适配器](#参考-wework适配器)

---

## Channel Adapter架构概述

### 核心组件

```
┌────────────────────────────────────────────────┐
│         Channel Adapter Architecture          │
├────────────────────────────────────────────────┤
│                                                │
│  BaseChannelAdapter (Abstract Base Class)     │
│  ├─ send_message()                             │
│  ├─ parse_message()                            │
│  ├─ verify_signature()                         │
│  ├─ is_configured()                            │
│  └─ get_required_env_vars()                    │
│                                                │
│  Concrete Adapters (Implementations)           │
│  ┌──────────────┐  ┌──────────────┐           │
│  │ WeWork       │  │ Feishu       │           │
│  │ Adapter      │  │ Adapter      │   ...     │
│  └──────────────┘  └──────────────┘           │
│                                                │
│  ChannelRouter (Message Routing)               │
│  └─ route_message() → Employee Agent          │
│                                                │
└────────────────────────────────────────────────┘
```

### 数据流

```
IM平台回调
    ↓
Callback Server (Flask/FastAPI)
    ↓
Adapter.parse_message() → ChannelMessage (统一格式)
    ↓
ChannelRouter.route_message()
    ↓
Employee Agent (知识问答处理)
    ↓
Adapter.send_message() → ChannelResponse
    ↓
IM平台
```

### 三个核心文件

每个Channel Adapter包含3个核心文件:

1. **`client.py`** - API客户端
   - Token管理
   - API调用封装
   - 错误处理和重试

2. **`adapter.py`** - 适配器实现
   - 实现`BaseChannelAdapter`
   - 消息格式转换
   - 签名验证

3. **`server.py`** - 回调服务器
   - Flask/FastAPI服务器
   - URL验证
   - 消息接收和异步处理

---

## 开发前准备

### 1. 了解目标IM平台

**必需了解**:
- 消息回调机制 (Webhook/Callback)
- 消息发送API
- 身份验证方式 (Token, Signature)
- 消息格式 (JSON, XML, etc.)

**推荐阅读**:
- WeChat Work: https://developer.work.weixin.qq.com/document/
- Feishu: https://open.feishu.cn/document/
- DingTalk: https://open.dingtalk.com/document/
- Slack: https://api.slack.com/

### 2. 注册应用并获取凭证

**通用步骤**:
1. 在IM平台开发者后台注册应用
2. 获取必需凭证 (App ID, Secret, Token, etc.)
3. 配置回调URL (需要公网可访问)
4. 测试回调连通性

### 3. 设置开发环境

```bash
# 创建目录结构
mkdir -p backend/channels/<platform_name>
cd backend/channels/<platform_name>

# 创建文件
touch __init__.py
touch client.py
touch adapter.py
touch server.py
```

---

## 步骤1: 创建Channel Client

### 目标
封装IM平台的API调用，提供统一的接口给Adapter使用。

### 1.1 Token Manager (可选但推荐)

大部分IM平台使用Access Token机制，建议实现Token自动管理:

```python
# client.py
import time
import logging
from typing import Optional
import requests

logger = logging.getLogger(__name__)


class AccessTokenManager:
    """
    Access Token自动管理器

    特性:
    - 自动获取和刷新Token
    - Token缓存 (内存)
    - 过期前自动刷新
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        token_url: str
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token_url = token_url

        self._token: Optional[str] = None
        self._expires_at: float = 0

    def get_token(self) -> str:
        """获取有效的Access Token (自动刷新)"""
        if self._is_token_valid():
            return self._token

        return self._refresh_token()

    def _is_token_valid(self) -> bool:
        """检查Token是否有效 (提前5分钟刷新)"""
        if not self._token:
            return False

        buffer_time = 300  # 5分钟缓冲
        return time.time() < (self._expires_at - buffer_time)

    def _refresh_token(self) -> str:
        """刷新Access Token"""
        try:
            # 根据IM平台API调整请求方式
            response = requests.post(
                self.token_url,
                json={
                    'appid': self.app_id,
                    'secret': self.app_secret
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            # 根据IM平台响应格式调整
            self._token = data['access_token']
            expires_in = data['expires_in']
            self._expires_at = time.time() + expires_in

            logger.info(f"Access token refreshed, expires in {expires_in}s")
            return self._token

        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise
```

### 1.2 API Client

```python
# client.py (续)
from typing import Dict, Any, Optional


class PlatformClient:
    """
    IM平台API客户端

    封装所有API调用:
    - 发送文本消息
    - 发送Markdown消息
    - 上传媒体文件
    - 获取用户信息
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        agent_id: Optional[str] = None  # 部分平台需要
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.agent_id = agent_id

        # 初始化Token管理器
        self.token_manager = AccessTokenManager(
            app_id=app_id,
            app_secret=app_secret,
            token_url="https://api.platform.com/gettoken"  # 替换为实际URL
        )

        self.base_url = "https://api.platform.com"  # 替换为实际API base URL

    def send_text(
        self,
        user_id: str,
        content: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送文本消息

        Args:
            user_id: 用户ID
            content: 文本内容
            **kwargs: 平台特定参数

        Returns:
            API响应字典
        """
        token = self.token_manager.get_token()

        # 根据平台API调整请求格式
        payload = {
            'touser': user_id,
            'msgtype': 'text',
            'text': {
                'content': content
            }
        }

        # 添加平台特定字段
        if self.agent_id:
            payload['agentid'] = self.agent_id

        response = requests.post(
            f"{self.base_url}/message/send",
            params={'access_token': token},
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return response.json()

    def send_markdown(
        self,
        user_id: str,
        content: str,
        **kwargs
    ) -> Dict[str, Any]:
        """发送Markdown消息 (如果平台支持)"""
        token = self.token_manager.get_token()

        payload = {
            'touser': user_id,
            'msgtype': 'markdown',
            'markdown': {
                'content': content
            }
        }

        if self.agent_id:
            payload['agentid'] = self.agent_id

        response = requests.post(
            f"{self.base_url}/message/send",
            params={'access_token': token},
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return response.json()

    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """获取用户信息"""
        token = self.token_manager.get_token()

        response = requests.get(
            f"{self.base_url}/user/get",
            params={
                'access_token': token,
                'userid': user_id
            },
            timeout=10
        )
        response.raise_for_status()
        return response.json()

    # 根据需要添加更多API方法:
    # - upload_media()
    # - send_image()
    # - send_file()
    # - create_group()
    # ...
```

---

## 步骤2: 实现Channel Adapter

### 目标
实现`BaseChannelAdapter`,提供统一的消息处理接口。

### 2.1 导入必需的基类和模型

```python
# adapter.py
import logging
from typing import Dict, Any, Optional, List
from backend.channels.base import (
    BaseChannelAdapter,
    ChannelMessage,
    ChannelResponse,
    ChannelUser,
    ChannelType,
    MessageType,
    ChannelAuthError,
    ChannelMessageError
)
from .client import PlatformClient

logger = logging.getLogger(__name__)
```

### 2.2 实现Adapter类

```python
# adapter.py (续)
class PlatformAdapter(BaseChannelAdapter):
    """
    Platform Channel Adapter

    实现BaseChannelAdapter的所有抽象方法
    """

    def __init__(self):
        """
        初始化适配器

        从环境变量读取配置 (通过settings.py)
        """
        from backend.config.settings import settings

        self.app_id = settings.PLATFORM_APP_ID
        self.app_secret = settings.PLATFORM_APP_SECRET
        self.agent_id = settings.PLATFORM_AGENT_ID  # 如果需要
        self.verification_token = settings.PLATFORM_VERIFICATION_TOKEN
        self.encrypt_key = settings.PLATFORM_ENCRYPT_KEY  # 如果需要

        # 初始化client
        if self.is_configured():
            self.client = PlatformClient(
                app_id=self.app_id,
                app_secret=self.app_secret,
                agent_id=self.agent_id
            )
        else:
            self.client = None
            logger.warning("Platform adapter not configured")

    @property
    def channel_type(self) -> ChannelType:
        """返回渠道类型"""
        # 根据实际平台调整 (WEWORK, FEISHU, DINGTALK, SLACK)
        return ChannelType.FEISHU  # 示例: 飞书

    def is_configured(self) -> bool:
        """检查是否已配置"""
        required = self.get_required_env_vars()
        from backend.config.settings import settings

        for var in required:
            value = getattr(settings, var, None)
            if not value:
                logger.debug(f"Missing required env var: {var}")
                return False

        return True

    def get_required_env_vars(self) -> List[str]:
        """返回必需的环境变量列表"""
        return [
            "PLATFORM_APP_ID",
            "PLATFORM_APP_SECRET",
            "PLATFORM_VERIFICATION_TOKEN",
            # 根据实际需要添加
        ]

    async def send_message(
        self,
        message: ChannelMessage
    ) -> ChannelResponse:
        """
        发送消息

        Args:
            message: 统一格式的ChannelMessage

        Returns:
            ChannelResponse
        """
        if not self.client:
            raise ChannelMessageError("Platform client not initialized")

        try:
            # 根据消息类型调用不同API
            if message.message_type == MessageType.TEXT:
                result = self.client.send_text(
                    user_id=message.user_id,
                    content=message.content
                )

            elif message.message_type == MessageType.MARKDOWN:
                result = self.client.send_markdown(
                    user_id=message.user_id,
                    content=message.content
                )

            else:
                raise ChannelMessageError(
                    f"Unsupported message type: {message.message_type}"
                )

            # 根据平台API响应判断成功/失败
            success = result.get('errcode') == 0  # 根据实际API调整
            error_msg = result.get('errmsg') if not success else None

            return ChannelResponse(
                success=success,
                message_id=result.get('msgid'),  # 如果平台返回
                error_message=error_msg,
                raw_response=result
            )

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return ChannelResponse(
                success=False,
                error_message=str(e)
            )

    async def send_batch_message(
        self,
        user_ids: List[str],
        content: str,
        message_type: MessageType = MessageType.TEXT
    ) -> ChannelResponse:
        """
        批量发送消息

        **优化建议**: 如果平台支持批量发送API,直接调用;
        否则,使用默认实现 (循环发送)
        """
        # 如果平台支持批量发送,实现如下:
        if not self.client:
            raise ChannelMessageError("Platform client not initialized")

        try:
            # 示例: 平台支持touser用'|'分隔多个用户
            user_list = '|'.join(user_ids)

            if message_type == MessageType.TEXT:
                result = self.client.send_text(
                    user_id=user_list,
                    content=content
                )
            else:
                result = self.client.send_markdown(
                    user_id=user_list,
                    content=content
                )

            success = result.get('errcode') == 0
            return ChannelResponse(
                success=success,
                error_message=result.get('errmsg') if not success else None,
                raw_response=result
            )

        except Exception as e:
            logger.error(f"Batch send failed: {e}")
            return ChannelResponse(
                success=False,
                error_message=str(e)
            )

    async def parse_message(
        self,
        raw_data: Dict[str, Any]
    ) -> Optional[ChannelMessage]:
        """
        解析原始回调消息为ChannelMessage

        Args:
            raw_data: 平台回调的原始数据 (已解析为dict)

        Returns:
            ChannelMessage 或 None (如果无需处理)
        """
        try:
            # 根据平台消息格式解析
            # 示例: 飞书格式
            event_type = raw_data.get('type')

            # 跳过非消息事件
            if event_type != 'message':
                logger.debug(f"Skipping non-message event: {event_type}")
                return None

            message_data = raw_data.get('message', {})

            # 提取关键字段
            user_id = message_data.get('user_id')
            content = message_data.get('text') or message_data.get('content')
            message_id = message_data.get('message_id')

            if not user_id or not content:
                logger.warning("Missing user_id or content in message")
                return None

            # 创建ChannelMessage
            return ChannelMessage(
                channel_type=self.channel_type,
                message_type=MessageType.TEXT,
                user_id=user_id,
                content=content,
                message_id=message_id,
                timestamp=message_data.get('timestamp'),
                raw_data=raw_data
            )

        except Exception as e:
            logger.error(f"Failed to parse message: {e}")
            raise ChannelMessageError(f"Parse failed: {e}")

    async def verify_signature(
        self,
        signature: str,
        data: str
    ) -> bool:
        """
        验证回调签名

        Args:
            signature: 平台提供的签名
            data: 待验证的数据

        Returns:
            验证通过返回True
        """
        import hashlib
        import hmac

        try:
            # 根据平台签名算法实现
            # 示例: HMAC-SHA256
            expected_signature = hmac.new(
                self.verification_token.encode('utf-8'),
                data.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            # 对比签名
            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    async def get_user_info(
        self,
        user_id: str
    ) -> Optional[ChannelUser]:
        """
        获取用户信息

        Args:
            user_id: 用户ID

        Returns:
            ChannelUser 或 None
        """
        if not self.client:
            return None

        try:
            user_data = self.client.get_user_info(user_id)

            # 根据平台响应格式解析
            return ChannelUser(
                user_id=user_id,
                name=user_data.get('name'),
                email=user_data.get('email'),
                department=user_data.get('department'),
                raw_data=user_data
            )

        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return None
```

---

## 步骤3: 创建Callback Server

### 目标
创建Flask/FastAPI服务器接收IM平台回调消息。

### 3.1 Flask实现 (推荐,轻量级)

```python
# server.py
import os
import logging
import asyncio
from flask import Flask, request, jsonify
from .adapter import PlatformAdapter

logger = logging.getLogger(__name__)

# 创建Flask app
app = Flask(__name__)
adapter = PlatformAdapter()

# 获取event loop (异步处理)
loop = None


def get_event_loop():
    """获取或创建event loop"""
    global loop
    if loop is None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


@app.route('/callback', methods=['GET', 'POST'])
async def callback():
    """
    Platform回调endpoint

    GET: URL验证 (初始配置时)
    POST: 接收消息
    """

    if request.method == 'GET':
        # URL验证逻辑 (根据平台要求实现)
        # 示例: 飞书的challenge验证
        challenge = request.args.get('challenge')
        if challenge:
            logger.info("URL verification successful")
            return jsonify({'challenge': challenge})

        return jsonify({'error': 'Missing challenge'}), 400

    elif request.method == 'POST':
        try:
            # 获取原始数据
            raw_data = request.get_json()

            # 验证签名 (如果平台要求)
            signature = request.headers.get('X-Signature')  # 根据平台调整header名称
            if signature:
                is_valid = await adapter.verify_signature(
                    signature=signature,
                    data=request.get_data(as_text=True)
                )
                if not is_valid:
                    logger.warning("Invalid signature")
                    return jsonify({'error': 'Invalid signature'}), 401

            # 解析消息
            message = await adapter.parse_message(raw_data)

            if message is None:
                # 非消息事件,直接返回成功
                return jsonify({'code': 0, 'msg': 'ok'})

            # 异步处理消息 (不阻塞回调)
            loop = get_event_loop()
            loop.create_task(process_message(message))

            # 立即返回200 (IM平台要求快速响应)
            return jsonify({'code': 0, 'msg': 'ok'})

        except Exception as e:
            logger.error(f"Callback processing failed: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500


async def process_message(message):
    """
    异步处理消息

    调用ChannelRouter路由到Employee Agent
    """
    try:
        from backend.services.channel_router import get_channel_router

        router = get_channel_router()
        response = await router.route_message(message)

        logger.info(f"Message processed: {response.success}")

    except Exception as e:
        logger.error(f"Message processing failed: {e}", exc_info=True)


def run_server(host='0.0.0.0', port=8082):
    """
    启动Flask服务器

    Args:
        host: 监听地址
        port: 监听端口 (从环境变量PLATFORM_PORT读取)
    """
    from backend.config.settings import settings

    port = getattr(settings, 'PLATFORM_PORT', port)

    logger.info(f"Starting Platform callback server on {host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    run_server()
```

---

## 步骤4: 注册配置

### 4.1 添加环境变量

在`backend/config/settings.py`中添加平台配置:

```python
# settings.py (新增)
class Settings(BaseSettings):
    # ... 现有配置 ...

    # Platform Configuration (新增)
    PLATFORM_APP_ID: Optional[str] = None
    PLATFORM_APP_SECRET: Optional[str] = None
    PLATFORM_AGENT_ID: Optional[str] = None
    PLATFORM_VERIFICATION_TOKEN: Optional[str] = None
    PLATFORM_ENCRYPT_KEY: Optional[str] = None
    PLATFORM_PORT: int = 8082  # 默认端口
```

### 4.2 注册到Channel Config

在`backend/config/channel_config.py`中注册新平台:

```python
# channel_config.py (修改)
CHANNEL_ENV_VARS = {
    "wework": ["WEWORK_CORP_ID", "WEWORK_CORP_SECRET", ...],
    "feishu": ["FEISHU_APP_ID", "FEISHU_APP_SECRET", ...],

    # 新增
    "platform": [
        "PLATFORM_APP_ID",
        "PLATFORM_APP_SECRET",
        "PLATFORM_VERIFICATION_TOKEN"
    ]
}

CHANNEL_PORTS = {
    "wework": 8081,
    "feishu": 8082,
    "platform": 8083,  # 新增
    ...
}
```

### 4.3 更新.env.example

在`.env.example`中添加配置模板:

```bash
# Platform Configuration (新增)
ENABLE_PLATFORM=auto              # auto | enabled | disabled
PLATFORM_APP_ID=
PLATFORM_APP_SECRET=
PLATFORM_AGENT_ID=
PLATFORM_VERIFICATION_TOKEN=
PLATFORM_ENCRYPT_KEY=
PLATFORM_PORT=8083
```

### 4.4 创建__init__.py

```python
# backend/channels/platform/__init__.py
"""
Platform Channel Adapter

提供Platform消息平台集成支持
"""
from .client import PlatformClient
from .adapter import PlatformAdapter

__all__ = [
    'PlatformClient',
    'PlatformAdapter'
]
```

---

## 步骤5: 测试与调试

### 5.1 单元测试

创建`tests/test_platform_adapter.py`:

```python
import pytest
from backend.channels.platform import PlatformAdapter, PlatformClient
from backend.channels.base import ChannelMessage, MessageType, ChannelType


@pytest.fixture
def adapter():
    """创建测试adapter"""
    return PlatformAdapter()


@pytest.mark.asyncio
async def test_is_configured(adapter):
    """测试配置检测"""
    # 根据实际环境变量判断
    is_configured = adapter.is_configured()
    assert isinstance(is_configured, bool)


@pytest.mark.asyncio
async def test_send_message(adapter):
    """测试发送消息"""
    if not adapter.is_configured():
        pytest.skip("Platform not configured")

    message = ChannelMessage(
        channel_type=ChannelType.FEISHU,  # 根据实际平台调整
        message_type=MessageType.TEXT,
        user_id='test_user_id',
        content='测试消息'
    )

    response = await adapter.send_message(message)
    assert response.success is True


@pytest.mark.asyncio
async def test_parse_message(adapter):
    """测试消息解析"""
    raw_data = {
        'type': 'message',
        'message': {
            'user_id': 'test_user',
            'text': '测试问题',
            'message_id': 'msg123',
            'timestamp': 1234567890
        }
    }

    message = await adapter.parse_message(raw_data)
    assert message is not None
    assert message.user_id == 'test_user'
    assert message.content == '测试问题'
```

运行测试:
```bash
pytest tests/test_platform_adapter.py -v
```

### 5.2 集成测试

**测试Callback Server**:
```bash
# 启动callback server
python -m backend.channels.platform.server

# 在另一个终端使用curl测试
curl -X POST http://localhost:8083/callback \
  -H "Content-Type: application/json" \
  -d '{
    "type": "message",
    "message": {
      "user_id": "test_user",
      "text": "测试消息",
      "message_id": "msg123"
    }
  }'
```

**测试完整流程**:
```bash
# 1. 配置.env
ENABLE_PLATFORM=auto
PLATFORM_APP_ID=your_app_id
PLATFORM_APP_SECRET=your_app_secret
PLATFORM_VERIFICATION_TOKEN=your_token

# 2. 启动完整服务
./scripts/start_v3.sh

# 3. 检查Platform服务是否启动
lsof -i :8083

# 4. 在IM平台发送消息,检查日志
tail -f logs/backend.log
```

### 5.3 调试技巧

**启用详细日志**:
```python
# 在server.py开头添加
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

**打印原始数据**:
```python
# 在callback endpoint添加
logger.debug(f"Raw callback data: {request.get_data(as_text=True)}")
logger.debug(f"Parsed JSON: {request.get_json()}")
```

**使用Python调试器**:
```python
# 在关键位置添加断点
import pdb; pdb.set_trace()
```

---

## 最佳实践

### 1. 错误处理

**Client层**:
- 所有API调用都应try-except
- 网络错误重试 (指数退避)
- Token过期自动刷新
- 记录详细错误日志

**Adapter层**:
- 捕获并转换异常为ChannelResponse
- 不要让异常传播到Router层
- 返回明确的error_message

**Server层**:
- 快速响应 (< 3秒)
- 异步处理耗时操作
- 始终返回200状态码 (IM平台要求)

### 2. 日志记录

**分级记录**:
```python
logger.debug("Detailed debug info")  # 开发时
logger.info("Important milestones")   # 正常流程
logger.warning("Recoverable issues")  # 警告
logger.error("Critical failures")     # 错误
```

**包含上下文**:
```python
logger.info(f"Processing message from {user_id}: {content[:50]}...")
logger.error(f"Failed to send to {user_id}: {error}", exc_info=True)
```

### 3. 安全性

**Token安全**:
- 不要在日志中输出完整Token
- 使用环境变量,不要硬编码
- Token自动刷新,避免过期

**签名验证**:
- 始终验证回调签名
- 使用constant-time比较 (`hmac.compare_digest`)
- 拒绝无效签名的请求

**输入验证**:
- 验证必需字段存在
- 检查数据类型和范围
- 防止注入攻击

### 4. 性能优化

**Token缓存**:
- 缓存Access Token,避免频繁获取
- 提前刷新 (过期前5分钟)

**批量发送**:
- 优先使用平台的批量API
- 避免循环发送 (如果平台支持批量)

**异步处理**:
- 消息处理异步化
- 不阻塞回调响应
- 使用线程池/进程池处理耗时任务

### 5. 测试策略

**单元测试**:
- 测试每个方法的基本功能
- Mock外部API调用
- 覆盖边界条件

**集成测试**:
- 测试完整消息流程
- 使用真实配置 (测试环境)
- 验证与其他组件集成

**回归测试**:
- 每次修改后运行全部测试
- CI/CD自动化测试

---

## 参考: WeWork适配器

WeWork适配器是一个完整的参考实现,展示了所有最佳实践。

**目录结构**:
```
backend/channels/wework/
├── __init__.py           # 16行 - 导出
├── client.py             # 360行 - API客户端
├── adapter.py            # 454行 - 适配器实现
└── server.py             # 237行 - Flask回调服务
```

**学习重点**:

1. **Token管理** (`client.py:20-80`):
   - AccessTokenManager实现
   - 自动刷新逻辑
   - 缓存策略

2. **消息解析** (`adapter.py:150-250`):
   - XML解密和解析
   - 转换为ChannelMessage
   - 错误处理

3. **回调处理** (`server.py:50-120`):
   - URL验证
   - 签名验证
   - 异步消息处理

4. **批量发送** (`adapter.py:100-130`):
   - 企微原生批量API
   - 用户列表格式化

**阅读建议**:
```bash
# 按顺序阅读
1. backend/channels/base.py      # 理解抽象接口
2. backend/channels/wework/client.py  # API封装
3. backend/channels/wework/adapter.py # 适配器实现
4. backend/channels/wework/server.py  # 回调服务
```

---

## 总结

### 开发检查清单

- [ ] 了解目标IM平台API文档
- [ ] 注册应用并获取凭证
- [ ] 创建目录结构 (`backend/channels/<platform>/`)
- [ ] 实现Client (`client.py`)
  - [ ] Token Manager
  - [ ] API封装
  - [ ] 错误处理
- [ ] 实现Adapter (`adapter.py`)
  - [ ] 继承BaseChannelAdapter
  - [ ] 实现所有抽象方法
  - [ ] 消息格式转换
  - [ ] 签名验证
- [ ] 实现Server (`server.py`)
  - [ ] URL验证endpoint
  - [ ] 消息接收endpoint
  - [ ] 异步处理
- [ ] 注册配置
  - [ ] 添加环境变量 (`settings.py`)
  - [ ] 注册到Channel Config
  - [ ] 更新`.env.example`
- [ ] 编写测试
  - [ ] 单元测试
  - [ ] 集成测试
- [ ] 文档更新
  - [ ] README.md
  - [ ] API文档

### 下一步

恭喜!你已经为智能资料库管理员添加了新的IM平台支持!

**进一步优化**:
1. 添加更多消息类型支持 (图片、文件、语音)
2. 实现群聊功能
3. 添加主动消息推送
4. 性能监控和告警
5. 分布式部署支持

**分享你的成果**:
- 提交Pull Request到主仓库
- 编写使用文档
- 分享集成经验

---

**Happy Coding!** 🚀

如有问题,请参考:
- 架构文档: `CLAUDE.md`
- 迁移指南: `docs/MIGRATION_V3.md`
- WeWork参考: `backend/channels/wework/`
- 问题反馈: GitHub Issues
