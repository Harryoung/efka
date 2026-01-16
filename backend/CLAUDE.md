# Backend

FastAPI 后端服务，端口 8000。双 Agent 架构：Admin Agent + User Agent。

## Code Structure

```
agents/
├── kb_admin_agent.py      # Admin Agent 定义
├── kb_qa_agent.py         # User Agent 定义
└── prompts/               # Agent prompts

services/
├── kb_service_factory.py  # 主服务工厂
├── client_pool.py         # SDK 客户端池 (并发)
├── session_manager.py     # 会话管理 (Redis)
├── conversation_state_manager.py  # 多轮对话状态
├── domain_expert_router.py        # 专家路由
└── shared_kb_access.py           # 文件锁

api/
├── query.py              # /api/query (Admin)
├── user.py               # /api/user/query (User)
└── streaming_utils.py    # SSE 流式响应

channels/
├── base.py               # Channel 抽象基类
└── wework/               # 企业微信适配器

tools/
└── image_read.py         # 图像识别工具 (SDK MCP Tool)

utils/
└── logging_config.py     # 日志配置
```

## Key Design Patterns

1. **Env vars before SDK import**: `main.py` 先加载 dotenv，再导入 Agent SDK
2. **Singleton pattern**: 使用 `get_admin_service()`, `get_user_service()` 获取服务
3. **SSE streaming**: 知识问答使用 Server-Sent Events 实时响应
4. **File locks**: `SharedKBAccess` 防止并发写冲突 (FAQ.md, BADCASE.md)
5. **permission_mode="acceptEdits"**: Agent 可自动执行文件编辑

## Extending Channels

实现 `BaseChannelAdapter`:
1. 创建 `channels/<name>/`
2. 参考 WeWork 实现
3. 添加到 `channel_config.py`

## Manual Start

```bash
python3 -m backend.main  # :8000
```

## Dependencies

```bash
pip3 install -r backend/requirements.txt
```
