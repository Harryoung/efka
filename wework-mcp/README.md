# WeWork MCP Server

企业微信 MCP 服务 - 让 Claude Agent 能够通过 MCP 协议向企业微信用户发送消息通知。

## 功能特性

- 发送文本消息
- 发送 Markdown 格式消息
- 发送图片消息
- 发送文件消息
- 上传临时素材
- Access Token 自动管理和缓存
- 错误重试机制

## 快速开始

### 1. 安装依赖

```bash
# 使用 Poetry 安装
cd wework-mcp
poetry install

# 或使用 pip 安装
pip install .
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并填入你的企业微信配置：

```bash
cp .env.example .env
vim .env
```

配置说明：
- `WEWORK_CORP_ID`: 企业ID（在企业微信管理后台 -> 我的企业 -> 企业信息中查看）
- `WEWORK_CORP_SECRET`: 应用凭证密钥（在应用详情页查看）
- `WEWORK_AGENT_ID`: 应用ID（在应用详情页查看）

### 3. 测试连接

```bash
poetry run python scripts/test_connection.py
```

### 4. 运行 MCP 服务

```bash
# 方式1：使用 Poetry
poetry run wework-mcp

# 方式2：直接运行
poetry run python -m wework_mcp.server
```

## 集成到 EFKA 知了

在 `backend/services/kb_service.py` 中添加 MCP 服务配置：

```python
mcp_servers = {
    "markitdown": {
        "type": "stdio",
        "command": "markitdown-mcp",
        "args": []
    },
    "wework": {
        "type": "stdio",
        "command": "wework-mcp",
        "args": [],
        "env": {
            "WEWORK_CORP_ID": os.getenv("WEWORK_CORP_ID"),
            "WEWORK_CORP_SECRET": os.getenv("WEWORK_CORP_SECRET"),
            "WEWORK_AGENT_ID": os.getenv("WEWORK_AGENT_ID"),
        }
    }
}

options = ClaudeAgentOptions(
    mcp_servers=mcp_servers,
    allowed_tools=[
        "Read", "Write", "Grep", "Glob", "Bash",
        "mcp__markitdown__convert_to_markdown",
        "mcp__wework__wework_send_text_message",
        "mcp__wework__wework_send_markdown_message",
        "mcp__wework__wework_send_image_message",
        "mcp__wework__wework_send_file_message",
        "mcp__wework__wework_upload_media",
    ],
    ...
)
```

## 可用工具

### 1. wework_send_text_message

发送纯文本消息。

参数：
- `touser` (string): 用户ID列表，用 '|' 分隔，或 '@all' 表示全员
- `content` (string): 消息内容，最长2048字节
- `safe` (integer, 可选): 是否保密消息，0=可分享（默认），1=不可分享

### 2. wework_send_markdown_message

发送 Markdown 格式消息。

参数：
- `touser` (string): 用户ID列表
- `content` (string): Markdown 内容，支持标题、加粗、链接、代码、引用、彩色字体等

### 3. wework_send_image_message

发送图片消息（需先上传获取 media_id）。

参数：
- `touser` (string): 用户ID列表
- `media_id` (string): 图片媒体文件ID
- `safe` (integer, 可选): 是否保密消息

### 4. wework_send_file_message

发送文件消息（需先上传获取 media_id）。

参数：
- `touser` (string): 用户ID列表
- `media_id` (string): 文件媒体ID
- `safe` (integer, 可选): 是否保密消息

### 5. wework_upload_media

上传临时素材，获取 media_id（有效期3天）。

参数：
- `media_type` (string): 媒体类型，可选 image/voice/video/file
- `file_path` (string): 文件绝对路径

## 企业微信配置获取步骤

1. **登录企业微信管理后台**
   - 访问：https://work.weixin.qq.com/
   - 使用管理员账号登录

2. **创建自建应用**
   - 进入「应用管理」→「应用」→「创建应用」
   - 填写应用名称、上传Logo
   - 选择可见范围

3. **获取配置参数**
   - 企业ID: 「我的企业」→「企业信息」→「企业ID」
   - Secret: 应用详情页 →「Secret」
   - AgentId: 应用详情页 →「AgentId」

4. **配置应用权限**
   - 确保开启「消息推送」权限
   - 在「可见范围」中添加需要接收消息的成员或部门

## 常见错误码

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| 40001 | 不合法的secret参数 | 检查 WEWORK_CORP_SECRET 是否正确 |
| 40013 | 不合法的corpid | 检查 WEWORK_CORP_ID 格式（需ww开头） |
| 40014 | 不合法的access_token | Token已过期，自动刷新后重试 |
| 42001 | access_token已过期 | 自动刷新token |
| 60011 | 不存在的userid | 检查用户ID是否正确 |
| 60020 | 不合法的agentid | 检查 WEWORK_AGENT_ID 配置 |
| 81013 | 所有接收者无权限 | 检查应用可见范围设置 |

## 开发测试

### 运行单元测试

```bash
poetry run pytest tests/ -v
```

### 运行集成测试

```bash
export WEWORK_INTEGRATION_TEST=1
export WEWORK_TEST_USER_ID=your_userid
poetry run pytest tests/test_integration.py -v
```

## 项目结构

```
wework-mcp/
├── pyproject.toml              # Poetry 项目配置
├── README.md                   # 本文档
├── .env.example                # 环境变量示例
├── src/
│   └── wework_mcp/
│       ├── __init__.py
│       ├── server.py           # MCP 服务器主程序
│       ├── weework_client.py   # 企业微信 API 客户端
│       ├── token_manager.py    # Access Token 管理
│       └── config.py           # 配置加载
├── tests/
│   ├── test_weework_client.py
│   ├── test_token_manager.py
│   └── test_integration.py
└── scripts/
    └── test_connection.py      # 连接测试脚本
```

## 许可证

MIT License

## 参考文档

- [企业微信API文档](https://developer.work.weixin.qq.com/document/)
- [发送应用消息](https://developer.work.weixin.qq.com/document/path/90236)
- [MCP协议规范](https://spec.modelcontextprotocol.io/)
