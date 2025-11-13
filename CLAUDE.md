# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

智能资料库管理员 (Intelligent Knowledge Base Administrator) - An AI-powered knowledge base management system built with Claude Agent SDK. The system uses a **dual-agent architecture** to provide intelligent Q&A (Employee Agent via WeChat Work) and document management/KB administration (Admin Agent via Web UI).

## Key Architecture Principles

### Agent-First Design Philosophy
This project follows an **Agent Autonomous Decision-Making** architecture:

- **❌ AVOID**: Creating specialized tools for every business logic scenario
- **✅ CORRECT**: Provide minimal base tools (read, write, grep, glob, bash, markitdown-mcp) and let the Agent combine them intelligently
- **Core Principle**: Business logic resides in Agent prompts, not in code. The Agent makes autonomous decisions based on context.

### Dual-Agent Architecture (v2.0)
```
┌─────────────────────────────────────────────────────────┐
│         Intelligent KBA (Dual-Agent Architecture)       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  FastAPI Service (8000)      Flask Service (8081)      │
│  ┌─────────────────────┐    ┌──────────────────────┐  │
│  │   Admin Agent       │    │  Employee Agent      │  │
│  │   - Web UI          │    │  - WeChat Work       │  │
│  │   - Doc Mgmt        │    │  - Knowledge Q&A     │  │
│  │   - Batch Notify    │    │  - Expert Routing    │  │
│  └─────────────────────┘    └──────────────────────┘  │
│         │                            │                 │
│         └────────┬───────────────────┘                 │
│                  ▼                                     │
│     KBServiceFactory (Dual SDK Clients)               │
│     ConversationStateManager (Redis)                  │
│     DomainExpertRouter + SharedKBAccess               │
└─────────────────────────────────────────────────────────┘
```

**Key Benefits of Dual-Agent Architecture**:
- ✅ Channel-specific optimization (WeChat Work vs Web UI)
- ✅ Independent scaling (employee queries vs admin tasks)
- ✅ Tool isolation (Employee: wework only, Admin: wework + markitdown)
- ✅ Clear separation of concerns

## Development Commands

### Running the Application

**Quick Start (Recommended):**
```bash
# Start both backend and frontend
./scripts/start.sh

# Stop all services
./scripts/stop.sh
```

**Manual Start:**
```bash
# Terminal 1 - Backend (from project root)
python3 -m backend.main
# Runs on http://localhost:8000
# Health check: http://localhost:8000/health

# Terminal 2 - Frontend
cd frontend
npm run dev
# Runs on http://localhost:3000
```

### Testing

**Backend Tests:**
```bash
# Phase verification scripts
python scripts/verify_phase1.py  # Project structure
python scripts/verify_phase2.py  # Agent definitions
python scripts/verify_phase3.py  # API routes

# Test individual components
CLAUDE_API_KEY=test_key KB_ROOT_PATH=./knowledge_base python -c "from backend.services.kb_service import get_kb_service; print('✅ KnowledgeBaseService import success')"

CLAUDE_API_KEY=test_key KB_ROOT_PATH=./knowledge_base python -c "from backend.api.query import router; print('✅ Query API import success')"
```

**Frontend:**
```bash
cd frontend
npm run build         # Production build
npm run preview       # Preview production build
npm run lint          # Run ESLint
```

### Dependencies

**Backend:**
```bash
pip3 install -r backend/requirements.txt

# Important: markitdown-mcp is required for document conversion
# It should be installed automatically via requirements.txt
# Verify installation:
which markitdown-mcp
```

**Frontend:**
```bash
cd frontend
npm install
```

## Environment Configuration

Create `.env` file from `.env.example`:

```bash
cp .env.example .env
```

**Critical Environment Variables:**
- `CLAUDE_API_KEY` or `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_BASE_URL` (at least one required)
- `KB_ROOT_PATH`: Knowledge base root directory (default: ./knowledge_base)
- `SMALL_FILE_KB_THRESHOLD`: Small file threshold in KB (default: 30)
- `FAQ_MAX_ENTRIES`: Maximum FAQ entries (default: 50)
- `SESSION_TIMEOUT`: Session timeout in seconds (default: 1800)

**Important**: The startup script exports authentication environment variables to ensure sub-agents can access them.

## Code Architecture

### Backend Structure

**Agent Definition** (`backend/agents/`):
- `unified_agent.py`: Single unified agent handling all functions (intent recognition, knowledge QA, document management, KB administration)

**Services** (`backend/services/`):
- `kb_service.py`: Core knowledge base service, manages Agent SDK client lifecycle
- `session_manager.py`: Session management with automatic cleanup

**API Routes** (`backend/api/`):
- `query.py`: SSE streaming endpoint for Q&A (`/api/query`, `/api/query/stream`)
- `upload.py`: File upload endpoint (`/api/upload`)

**Key Design Patterns:**
1. **Agent Initialization**: Environment variables (especially auth tokens) MUST be loaded and exported before importing any Agent SDK modules (see `backend/main.py` lines 4-26)
2. **Singleton Pattern**: Use `get_kb_service()` and `get_session_manager()` instead of direct instantiation
3. **Async/Await**: All API endpoints and Agent interactions are async
4. **SSE Streaming**: Knowledge QA responses stream via Server-Sent Events for real-time UX
5. **MCP Integration**: MCP (Model Context Protocol) servers are configured programmatically via `ClaudeAgentOptions.mcp_servers`

### MCP (Model Context Protocol) Configuration

**What is MCP?**
MCP is a protocol that allows Claude to interact with external tools and services. In this project, we use the `markitdown-mcp` server to convert various file formats (PDF, DOCX, PPTX, XLSX, etc.) to Markdown.

**MCP Server Configuration** (`backend/services/kb_service.py:160-167`):
```python
mcp_servers = {
    "markitdown": {
        "type": "stdio",              # Communication method
        "command": "markitdown-mcp",  # MCP server command
        "args": []                    # Optional arguments
    }
}

options = ClaudeAgentOptions(
    mcp_servers=mcp_servers,
    allowed_tools=[
        "Read", "Write", "Grep", "Glob", "Bash",
        "mcp__markitdown__convert_to_markdown"  # MCP tool naming: mcp__{server}__{tool}
    ],
    ...
)
```

**Key Points:**
- ✅ **MCP servers MUST be configured in `ClaudeAgentOptions.mcp_servers`**
- ✅ MCP tools are referenced as `mcp__{server_name}__{tool_name}` in `allowed_tools`
- ✅ The `markitdown-mcp` command must be available in PATH (installed via `pip install markitdown-mcp`)
- ❌ Don't just add MCP tools to `allowed_tools` without configuring the server
- ❌ Don't use wildcards (`*`) in MCP tool names in `allowed_tools`

**Supported File Formats** (via markitdown):
PDF, DOCX, PPTX, XLSX, XLS, CSV, HTML, XML, JSON, images (with OCR), audio transcripts, and 29+ more formats.

### Frontend Structure

**React + Vite** setup with:
- `src/components/`: Reusable UI components
- `src/hooks/`: Custom React hooks
- `src/services/`: API service layer
- Uses `marked` library for Markdown rendering
- SSE client for streaming responses

## Agent SDK Usage Patterns

### Unified Agent Definition Template
```python
from claude_agent_sdk import AgentDefinition

unified_agent = AgentDefinition(
    description="Unified agent handling all KB operations",
    prompt="""
    Detailed instructions emphasizing:
    - Intent recognition (query/upload/management)
    - 7-stage retrieval for knowledge QA
    - 5-stage processing for document ingestion
    - Agent autonomy and decision-making freedom
    - Semantic understanding over pattern matching
    """,
    tools=["Read", "Write", "Grep", "Glob", "Bash", "mcp__markitdown__*"],
    model="sonnet"
)
```

### SDK Client Configuration
```python
options = ClaudeAgentOptions(
    system_prompt={
        "type": "preset",
        "preset": "claude_code",
        "append": unified_agent.prompt
    },
    agents=None,  # No sub-agents in single agent architecture
    allowed_tools=unified_agent.tools,
    permission_mode="acceptEdits",
    ...
)
```

### Permission Callback
The system uses a minimal permission callback (`kb_service.py`) that:
- Prevents dangerous bash commands
- Restricts file writes to knowledge base directory or /tmp
- Gives Agents maximum freedom within safety boundaries

## Knowledge Base Structure

Located at `./knowledge_base/`:
- `README.md`: Auto-maintained structure overview
- `FAQ.md`: Frequently asked questions with usage tracking
- Organized into topic-based subdirectories
- All documents converted to Markdown format

**Unified Agent maintains:**
- Semantic conflict detection (content-based, not string matching)
- Intelligent file placement (based on content themes)
- Directory capacity monitoring (suggests reorganization when >15 items)

**Unified Agent implements 7-stage retrieval:**
1. FAQ fast-track (semantic similarity)
2. Structured navigation (via README.md)
3. Intelligent keyword generation
4. Adaptive retrieval (full read for small files, grep for large)
5. Context expansion (semantic paragraphs, not fixed line counts)
6. Answer generation with source attribution
7. FAQ learning (user feedback loop)

## Batch Employee Notification

**Feature Overview**:
- Admins can batch notify employees via WeChat Work (企业微信)
- Supports 3 scenarios:
  1. Upload data file + filtering criteria (e.g., "notify employees with welfare points > 0")
  2. Upload target employee list directly
  3. Specify notification targets (e.g., @all, specific departments)

**Key Files**:
- `knowledge_base/企业管理/人力资源/employee_mapping.xlsx`: Employee-userid mapping table
- `backend/agents/prompts/batch_notification.md`: Detailed 5-stage process guide

**How It Works**:
1. Agent recognizes batch notification intent
2. Reads `batch_notification.md` (progressive disclosure)
3. Parses employee mapping table **using temporary Python scripts (pandas)**
4. Extracts target employee list with SQL-like queries (pandas filtering/joining)
5. Constructs message and waits for admin confirmation
6. Sends via wework-mcp (supports up to 1000 users per call)

**Table Processing Approach**:
- ❌ Does NOT use markitdown for XLSX processing
- ✅ Uses Bash tool to execute temporary Python scripts
- ✅ Leverages pandas for SQL-like queries (filter, join, aggregate)
- ✅ Supports complex filtering logic based on natural language conditions

**Architecture Alignment**:
- ✅ Agent-First: Business logic in prompt, not in code
- ✅ Uses existing tools: Read, Bash (Python), wework-mcp
- ✅ Single Agent architecture: No sub-agents needed
- ✅ Progressive disclosure: Detailed logic loaded only when needed

## Important Implementation Details

### Authentication Flow
1. `.env` file is loaded in `backend/main.py` (lines 10-26)
2. Auth tokens are explicitly exported to `os.environ` to ensure sub-processes inherit them
3. Both `ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_BASE_URL` and `CLAUDE_API_KEY` patterns are supported

### Session Management
- Sessions keyed by `session_id` (generated client-side)
- Automatic cleanup via background task
- Sessions persist across multiple requests for context continuity
- "Clear conversation" command creates new session while preserving session_id

### SSE Streaming Implementation
- Backend uses `async def` generators with `yield` for streaming
- Frontend EventSource API consumes SSE stream
- Real-time token-by-token rendering in chat interface

## Development Guidelines

### When Modifying Agents
1. **Prompt Engineering First**: Adjust prompts before changing code
2. **Test Autonomy**: Ensure Agents make decisions, not execute fixed rules
3. **Avoid Tool Proliferation**: Don't create specialized tools; use base tools
4. **Maintain Consistency**: Keep Agent behavior predictable but flexible

### When Adding Features
1. **Evaluate Agent Layer**: Can existing Agents handle this with prompt updates?
2. **Minimal Code Changes**: Prefer prompt modifications over code additions
3. **Document in Prompts**: New capabilities should be described in Agent prompts

### When Debugging
1. **Check Logs**: `logs/backend.log` and `logs/frontend.log`
2. **Verify Auth**: Ensure environment variables are loaded (check startup logs)
3. **Test Agents Individually**: Use verification scripts
4. **Monitor Sessions**: Check `/health` and `/info` endpoints

## Common Pitfalls to Avoid

1. **DON'T** create specialized tools like `semantic_conflict_checker` or `faq_manager` - let the Agent use base tools
2. **DON'T** import Agent SDK modules before setting environment variables
3. **DON'T** use direct instantiation of services - use singleton getters
4. **DON'T** forget to handle async/await in API routes
5. **DON'T** modify Agent business logic in code - modify prompts instead
6. **DON'T** try to create sub-agents - this is a single agent architecture

## Future Extension Patterns

### Multi-Channel Integration (WeChat Work, DingTalk, Slack)
Architecture supports easy channel integration via:
1. Message Gateway layer (format conversion)
2. Channel-specific adapters
3. Unified HTTP API (`/api/chat`) for external systems
4. Session management already supports channel prefixes

### Performance Optimization
- Agent decision caching
- Vector database for semantic search (complementary to Agent retrieval)
- Message queue for high concurrency

## Quick Reference

**Port Conflicts:**
```bash
lsof -i :8000  # Check FastAPI main service
lsof -i :8081  # Check Flask WeWork callback service (default, configurable via WEWORK_PORT)
lsof -i :3000  # Check frontend port
kill -9 <PID>  # Force stop process
```

**Health Checks:**
```bash
curl http://localhost:8000/health  # Admin API
curl http://localhost:8000/info
lsof -i:8081                        # WeWork callback (default port)
```

**View Real-time Logs:**
```bash
tail -f logs/backend.log  # FastAPI main service
tail -f logs/wework.log   # Flask WeWork callback service
tail -f logs/frontend.log # Frontend
```

**Restart Services:**
```bash
./scripts/stop.sh && ./scripts/start.sh
```

---

## Architecture Changes (2025-01 Update)

### Dual-Agent Architecture Details

The system has been split into two specialized agents:

**1. Employee Agent (`backend/agents/kb_qa_agent.py`)**
- **Responsibilities**: Knowledge Q&A, Satisfaction feedback, Expert routing
- **Interface**: WeChat Work (企业微信) via Flask service on configurable port (default 8081)
- **MCP Tools**: wework only (no markitdown for lightweight operation)
- **Characteristics**: Lightweight, high-frequency requests, async multi-turn conversations
- **Key Features**:
  - 6-stage retrieval workflow (FAQ → README → keyword search → adaptive retrieval → context expansion → answer generation)
  - Expert routing when KB search fails
  - Maintains conversation state for expert reply handling

**2. Admin Agent (`backend/agents/kb_admin_agent.py`)**
- **Responsibilities**: Document ingestion, KB management, Batch notifications
- **Interface**: Web Admin UI (React SPA) via FastAPI service on port 8000
- **MCP Tools**: markitdown + wework (full feature set)
- **Characteristics**: Feature-complete, low-frequency admin tasks
- **Key Features**:
  - 5-stage document ingestion
  - Semantic conflict detection
  - Batch employee notification with data filtering

### New Infrastructure Components

**KBServiceFactory** (`backend/services/kb_service_factory.py`):
- Manages two independent Claude SDK clients (one per agent)
- Singleton pattern: `get_employee_service()`, `get_admin_service()`
- Extensible to microservices (just change factory implementation)

**ConversationStateManager** (`backend/services/conversation_state_manager.py`):
- Manages asynchronous multi-turn conversations (Employee → Agent → Expert → Employee)
- State machine: IDLE → WAITING_FOR_EXPERT → COMPLETED
- Redis persistence with 24h TTL, memory fallback on Redis failure
- Key methods:
  - `get_conversation_context(user_id)`: Get current conversation state
  - `check_pending_expert_reply(expert_userid)`: Check if expert has pending reply
  - `update_state(...)`: Update conversation state

**DomainExpertRouter** (`backend/services/domain_expert_router.py`):
- Routes employee questions to domain experts based on semantic classification
- Queries `knowledge_base/企业管理/人力资源/domain_experts.xlsx` mapping table
- Falls back to default expert if domain not matched

**SharedKBAccess** (`backend/services/shared_kb_access.py`):
- File-level locking for concurrent writes (FAQ.md, BADCASE.md)
- Uses `fcntl` for cross-process safety
- Supports future microservices architecture
- Usage:
  ```python
  with kb_access.file_lock('FAQ.md', timeout=5):
      # Read, modify, write atomically
      pass
  ```

### API Routes

**WeWork Callback API** (`backend/api/wework_callback.py`):
- Endpoint: `POST /api/wework/callback`
- Handles WeChat Work message callbacks
- URL verification (GET), message reception (POST)
- Async message processing via global event loop
- Distinguishes employee queries from expert replies

### Deployment Architecture

**Dual-Process Mode:**
```
./scripts/start.sh
├── FastAPI Service (port 8000) - Admin Agent + Web API
├── Flask Service (port 8081, configurable) - Employee Agent + WeWork Callback
└── React Frontend (port 3000) - Admin UI
```

**Process Management:**
- PID files: `logs/backend.pid`, `logs/wework.pid`, `logs/frontend.pid`
- Log files: `logs/backend.log`, `logs/wework.log`, `logs/frontend.log`
- Stop all: `./scripts/stop.sh`

**Environment Variables:**
New WeChat Work configuration (see `.env.example`):
- `WEWORK_CORP_ID`, `WEWORK_CORP_SECRET`, `WEWORK_AGENT_ID`
- `WEWORK_TOKEN`, `WEWORK_ENCODING_AES_KEY`
- `WEWORK_PORT` (default: 8081) - WeWork callback service port
- `CONVERSATION_STATE_TTL`, `EXPERT_REPLY_TIMEOUT`, `FILE_LOCK_TIMEOUT`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`

### Expert Routing Workflow

When an employee question cannot be answered from the knowledge base:

1. **Domain Identification**: Agent semantically classifies the question
2. **Expert Lookup**: Query `domain_experts.xlsx` for responsible expert
3. **Contact Expert**: Send notification via WeChat Work MCP
4. **State Transition**: Update conversation state to WAITING_FOR_EXPERT
5. **Notify Employee**: Inform employee that expert has been contacted
6. **Wait for Reply**: Agent maintains session context (24h TTL)
7. **Expert Replies**: Agent detects expert's message, forwards to employee
8. **Auto FAQ**: Add Q&A to FAQ.md (with file lock)
9. **Suggest Documentation**: Remind expert to add detailed docs
10. **State Completion**: Mark conversation as COMPLETED

### File Lock Mechanism

To prevent concurrent write conflicts:

```python
from backend.services.shared_kb_access import get_shared_kb_access

kb_access = get_shared_kb_access('/path/to/knowledge_base')

with kb_access.file_lock('FAQ.md', timeout=5):
    # Read current content
    content = read_file('FAQ.md')
    # Modify
    content += new_entry
    # Write back atomically
    write_file('FAQ.md', content)
```

Uses `fcntl` for cross-process locking, compatible with future microservices deployment.

### Testing Commands

**Service Initialization:**
```bash
# Test Employee Service
python3 -c "
import asyncio
from backend.services.kb_service_factory import get_employee_service

async def test():
    service = get_employee_service()
    await service.initialize()
    print('✅ Employee service initialized')

asyncio.run(test())
"

# Test Admin Service
python3 -c "
import asyncio
from backend.services.kb_service_factory import get_admin_service

async def test():
    service = get_admin_service()
    await service.initialize()
    print('✅ Admin service initialized')

asyncio.run(test())
"
```

**Conversation State Manager:**
```bash
python3 -c "
import asyncio
from pathlib import Path
from backend.services.conversation_state_manager import get_conversation_state_manager
from backend.models.conversation_state import ConversationState
from datetime import datetime

async def test():
    mgr = get_conversation_state_manager(kb_root=Path('./knowledge_base'))

    # Test state update
    await mgr.update_state(
        user_id='test_user',
        state=ConversationState.WAITING_FOR_EXPERT,
        employee_question='测试问题',
        domain='薪酬福利',
        expert_userid='expert_001',
        contacted_at=datetime.now()
    )

    # Test retrieval
    context = await mgr.get_conversation_context('test_user')
    assert context.state == ConversationState.WAITING_FOR_EXPERT
    print('✅ Conversation state manager working')

asyncio.run(test())
"
```

### Migration Notes

**From Single Agent to Dual-Agent:**
- Old: `backend/agents/unified_agent.py` (deprecated)
- New: `backend/agents/kb_qa_agent.py` + `backend/agents/kb_admin_agent.py`
- Service factory manages both agents independently
- Web UI uses Admin Agent (no changes to frontend API)
- WeChat Work integration uses Employee Agent (new Flask service)

**Breaking Changes:**
- WeWork callback service now runs on configurable port (default 8081, set via WEWORK_PORT)
- New environment variables must be configured
- Redis recommended (but optional with memory fallback)

---

**Architecture Version**: v2.0 (Dual-Agent Architecture)
**Last Updated**: 2025-01-09
**Migration Status**: Phase 1-4 Complete, Ready for Production Testing
