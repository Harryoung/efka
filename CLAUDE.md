# CLAUDE.md

**EFKA 知了** (Embed-Free Knowledge Agent) - 无需向量数据库，让 Agent 直接阅读你的文件。基于 Claude Agent SDK 构建。

## Core Architecture

### Agent-First Design Philosophy
- **No Embeddings**: Direct file system access via Grep/Glob/Read
- **Agent Driven**: Let Claude intelligently search and combine information
- **Business Logic in Prompts**: Not in code

### Dual Agent Architecture (v3.0)
```
┌─────────────────────────────────────────────────────────┐
│  Frontend: Admin UI (3000) + Employee UI (3001)         │
│  + IM Platforms (WeWork/Feishu/DingTalk)               │
├─────────────────────────────────────────────────────────┤
│  Backend (FastAPI 8000)                                 │
│  ├─ Admin Agent: Doc management, batch notifications   │
│  └─ Employee Agent: Q&A, expert routing                │
├─────────────────────────────────────────────────────────┤
│  Channel Layer: BaseChannelAdapter + ChannelRouter     │
│  WeWork (8081) / Feishu (8082) / DingTalk (8083)       │
├─────────────────────────────────────────────────────────┤
│  Infrastructure: Redis + ConversationStateManager      │
│  + DomainExpertRouter + SharedKBAccess (file locks)    │
└─────────────────────────────────────────────────────────┘
```

## Development Commands

### Required: Activate Virtual Environment
```bash
source venv/bin/activate  # Must run before any Python commands
```

### Start/Stop
```bash
./scripts/start.sh   # Auto-detect and start all configured services
./scripts/stop.sh    # Stop all services
```

### Manual Start
```bash
# Backend
python3 -m backend.main                                    # :8000

# Frontend
cd frontend && npm run dev                                 # Admin :3000
cd frontend && VITE_APP_MODE=employee npm run dev -- --port 3001  # Employee :3001

# IM Channel (optional)
python -m backend.channels.wework.server                   # :8081
```

### Install Dependencies
```bash
pip3 install -r backend/requirements.txt  # Backend
cd frontend && npm install                 # Frontend
```

## Environment Configuration

Copy and configure `.env` from `.env.example`:

**Required**:
- `CLAUDE_API_KEY` or `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_BASE_URL`
- `KB_ROOT_PATH`: Knowledge base directory (default: ./knowledge_base)

**Optional**:
- `WEWORK_*`: WeChat Work configuration
- `VISION_MODEL_*`: Image recognition model
- `REDIS_*`: Redis configuration (has memory fallback)
- `*_CLIENT_POOL_SIZE`: Concurrent client pool size

## Code Structure

### Backend (`backend/`)
```
agents/
├── kb_admin_agent.py      # Admin Agent definition
├── kb_qa_agent.py         # Employee Agent definition
└── prompts/               # Agent prompts

services/
├── kb_service_factory.py  # Main service factory
├── client_pool.py         # SDK client pool (concurrency)
├── session_manager.py     # Session management (Redis)
├── conversation_state_manager.py  # Multi-turn conversation state
├── domain_expert_router.py        # Expert routing
└── shared_kb_access.py           # File locks

api/
├── query.py              # /api/query (Admin)
├── employee.py           # /api/employee/query (Employee)
└── streaming_utils.py    # SSE streaming response

channels/
├── base.py               # Channel abstract base class
└── wework/               # WeChat Work adapter

tools/
└── image_read.py         # Image recognition tool (SDK MCP Tool)

utils/
└── smart_convert.py      # Document conversion tool
```

### Frontend (`frontend/src/`)
```
components/
├── ChatView.jsx          # Admin interface
└── EmployeeChatView.jsx  # Employee interface
```

## Key Design Patterns

1. **Env vars before SDK import**: `backend/main.py` loads dotenv first, then imports Agent SDK
2. **Singleton pattern**: Use `get_admin_service()`, `get_employee_service()` to get services
3. **SSE streaming**: Knowledge Q&A uses Server-Sent Events for real-time response
4. **File locks**: `SharedKBAccess` prevents concurrent write conflicts (FAQ.md, BADCASE.md)
5. **permission_mode="acceptEdits"**: Agent can auto-execute file edits

## Document Conversion

Use `smart_convert.py` instead of external MCP:
```bash
python backend/utils/smart_convert.py <input_file> --json-output
```

Supports: DOCX, PDF (electronic/scanned), PPTX, TXT

## Troubleshooting

**Port conflict**:
```bash
lsof -i :8000,:3000,:3001,:8081
kill -9 <PID>
```

**View logs**:
```bash
tail -f logs/backend.log logs/wework.log logs/frontend.log
```

**Health check**:
```bash
curl http://localhost:8000/health
```

## Don'ts

1. Don't run Python without activating venv
2. Don't create specialized tools - let Agent use basic tools
3. Don't import SDK before setting env vars
4. Don't instantiate services directly - use singleton getters
5. Don't modify Agent business logic in code - modify prompts

## Extending Channels

Implement `BaseChannelAdapter`:
1. Create `backend/channels/<name>/`
2. Reference WeWork implementation
3. Add to `channel_config.py`

---
**Version**: v3.0 | **Updated**: 2025-12-11 | **Docs**: `docs/CHANNELS.md`, `docs/DEPLOYMENT.md`
