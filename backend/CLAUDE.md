# Backend

FastAPI backend service on port 8000. Dual Agent architecture: Admin Agent + User Agent.

## Code Structure

```
agents/
├── kb_admin_agent.py      # Admin Agent definition
├── kb_qa_agent.py         # User Agent definition
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
├── user.py               # /api/user/query (User)
└── streaming_utils.py    # SSE streaming response

channels/
├── base.py               # Channel abstract base class
└── wework/               # WeChat Work adapter

tools/
└── image_read.py         # Image recognition tool (SDK MCP Tool)

utils/
└── logging_config.py     # Logging configuration
```

## Key Design Patterns

1. **Env vars before SDK import**: `main.py` loads dotenv first, then imports Agent SDK
2. **Singleton pattern**: Use `get_admin_service()`, `get_user_service()` to get services
3. **SSE streaming**: Knowledge Q&A uses Server-Sent Events for real-time response
4. **File locks**: `SharedKBAccess` prevents concurrent write conflicts (FAQ.md, BADCASE.md)
5. **permission_mode="acceptEdits"**: Agent can auto-execute file edits

## Extending Channels

Implement `BaseChannelAdapter`:
1. Create `channels/<name>/`
2. Reference WeWork implementation
3. Add to `channel_config.py`

## Manual Start

```bash
python3 -m backend.main  # :8000
```

## Dependencies

```bash
pip3 install -r backend/requirements.txt
```
