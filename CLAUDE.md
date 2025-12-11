# CLAUDE.md

智能资料库管理员 (Intelligent Knowledge Base Administrator) - 基于 Claude Agent SDK 的 AI 知识库管理系统。

## 核心架构

### Agent-First 设计哲学
- **❌ 避免**: 为每个业务逻辑创建专用工具
- **✅ 正确**: 提供基础工具 (Read, Write, Grep, Glob, Bash)，让 Agent 智能组合
- **核心原则**: 业务逻辑在 Agent prompts 中，不在代码中

### 双 Agent 架构 (v3.0)
```
┌─────────────────────────────────────────────────────────┐
│  Frontend: Admin UI (3000) + Employee UI (3001)         │
│  + IM Platforms (WeWork/Feishu/DingTalk)               │
├─────────────────────────────────────────────────────────┤
│  Backend (FastAPI 8000)                                 │
│  ├─ Admin Agent: 文档管理、批量通知                      │
│  └─ Employee Agent: 知识问答、专家路由                   │
├─────────────────────────────────────────────────────────┤
│  Channel Layer: BaseChannelAdapter + ChannelRouter     │
│  WeWork (8081) / Feishu (8082) / DingTalk (8083)       │
├─────────────────────────────────────────────────────────┤
│  Infrastructure: Redis + ConversationStateManager      │
│  + DomainExpertRouter + SharedKBAccess (文件锁)         │
└─────────────────────────────────────────────────────────┘
```

## 开发命令

### ⚠️ 必须：激活虚拟环境
```bash
source venv/bin/activate  # 所有 Python 命令前必须执行
```

### 启动/停止
```bash
./scripts/start.sh   # 自动检测并启动所有配置的服务
./scripts/stop.sh    # 停止所有服务
```

### 手动启动
```bash
# Backend
python3 -m backend.main                                    # :8000

# Frontend
cd frontend && npm run dev                                 # Admin :3000
cd frontend && VITE_APP_MODE=employee npm run dev -- --port 3001  # Employee :3001

# IM Channel (可选)
python -m backend.channels.wework.server                   # :8081
```

### 依赖安装
```bash
pip3 install -r backend/requirements.txt  # Backend
cd frontend && npm install                 # Frontend
```

## 环境配置

从 `.env.example` 复制并配置 `.env`：

**必须**:
- `CLAUDE_API_KEY` 或 `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_BASE_URL`
- `KB_ROOT_PATH`: 知识库目录 (默认: ./knowledge_base)

**可选**:
- `WEWORK_*`: 企业微信配置
- `VISION_MODEL_*`: 图片识别模型配置
- `REDIS_*`: Redis 配置 (有内存 fallback)
- `*_CLIENT_POOL_SIZE`: 并发客户端池大小

## 代码结构

### Backend (`backend/`)
```
agents/
├── kb_admin_agent.py      # Admin Agent 定义
├── kb_qa_agent.py         # Employee Agent 定义
└── prompts/               # Agent 提示词

services/
├── kb_service_factory.py  # 主服务工厂 (get_admin_service, get_employee_service)
├── client_pool.py         # SDK 客户端池 (并发支持)
├── session_manager.py     # 会话管理 (Redis)
├── conversation_state_manager.py  # 多轮对话状态
├── domain_expert_router.py        # 专家路由
└── shared_kb_access.py           # 文件锁

api/
├── query.py              # /api/query (Admin)
├── employee.py           # /api/employee/query (Employee)
└── streaming_utils.py    # SSE 流式响应

channels/
├── base.py               # 渠道抽象基类
└── wework/               # 企业微信适配器

tools/
└── image_read.py         # 图片识别工具 (SDK MCP Tool)

utils/
└── smart_convert.py      # 文档转换工具
```

### Frontend (`frontend/src/`)
```
components/
├── ChatView.jsx          # Admin 界面
└── EmployeeChatView.jsx  # Employee 界面
```

## 关键设计模式

1. **环境变量先于 SDK 导入**: `backend/main.py` 先 load_dotenv，再 import Agent SDK
2. **单例模式**: 使用 `get_admin_service()`, `get_employee_service()` 获取服务
3. **SSE 流式**: 知识问答使用 Server-Sent Events 实时响应
4. **文件锁**: `SharedKBAccess` 防止并发写冲突 (FAQ.md, BADCASE.md)
5. **permission_mode="acceptEdits"**: Agent 可自动执行文件编辑

## 文档转换

使用 `smart_convert.py` 而非外部 MCP：
```bash
python backend/utils/smart_convert.py <input_file> --json-output
```

支持: DOCX, PDF (电子/扫描), PPTX, TXT

## 常见问题

**端口冲突**:
```bash
lsof -i :8000,:3000,:3001,:8081
kill -9 <PID>
```

**日志查看**:
```bash
tail -f logs/backend.log logs/wework.log logs/frontend.log
```

**健康检查**:
```bash
curl http://localhost:8000/health
```

## 禁止事项

1. ❌ 不激活 venv 就运行 Python
2. ❌ 创建专用工具 (如 `semantic_conflict_checker`) - 让 Agent 用基础工具
3. ❌ 在 SDK 导入前不设置环境变量
4. ❌ 直接实例化服务 - 用单例 getter
5. ❌ 在代码中修改 Agent 业务逻辑 - 修改 prompts

## 扩展渠道

实现 `BaseChannelAdapter`:
1. 创建 `backend/channels/<name>/`
2. 参考 WeWork 实现
3. 添加到 `channel_config.py`

---
**Version**: v3.0 | **Updated**: 2025-12-11 | **Docs**: `docs/CHANNELS.md`, `docs/DEPLOYMENT.md`
