# CLAUDE.md

**EFKA Cicada** (Embed-Free Knowledge Agent) - No vector database needed, let Agent read your files directly. Built with Claude Agent SDK.

## Core Architecture

### Agent-First Design Philosophy
- **No Embeddings**: Direct file system access via Grep/Glob/Read
- **Agent Driven**: Let Claude intelligently search and combine information
- **Business Logic in Prompts**: Not in code

### Run Mode Configuration (v3.0)
Single-channel mutual exclusivity model:
- **standalone** (default): Pure Web, no IM integration
- **wework/feishu/dingtalk/slack**: Enable specific IM channel

```bash
./scripts/start.sh              # standalone mode (default)
./scripts/start.sh --mode wework  # WeChat Work mode
RUN_MODE=wework ./scripts/start.sh  # via env var
```

### Dual Agent Architecture (v3.0)
```
┌─────────────────────────────────────────────────────────┐
│  Frontend: Admin UI (3000) + User UI (3001)             │
│  + IM Platforms (WeWork/Feishu/DingTalk)                │
├─────────────────────────────────────────────────────────┤
│  Backend (FastAPI 8000)                                 │
│  ├─ Admin Agent: Doc management, batch notifications   │
│  └─ User Agent: Q&A, expert routing                    │
├─────────────────────────────────────────────────────────┤
│  Channel Layer: BaseChannelAdapter + ChannelRouter     │
│  WeWork (8081) / Feishu (8082) / DingTalk (8083)       │
├─────────────────────────────────────────────────────────┤
│  Infrastructure: Redis + ConversationStateManager      │
│  + DomainExpertRouter + SharedKBAccess (file locks)    │
└─────────────────────────────────────────────────────────┘
```

## Modules

See CLAUDE.md in each directory for module details:
- [`backend/CLAUDE.md`](backend/CLAUDE.md) - Backend services, API, design patterns
- [`frontend/CLAUDE.md`](frontend/CLAUDE.md) - Frontend components
- [`skills/CLAUDE.md`](skills/CLAUDE.md) - Agent Skills

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

---
**Version**: v3.0 | **Updated**: 2025-12-23 | **Docs**: `docs/CHANNELS.md`, `docs/DEPLOYMENT.md`
