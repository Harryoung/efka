# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

智能资料库管理员 (Intelligent Knowledge Base Administrator) - An AI-powered knowledge base management system built with Claude Agent SDK. The system uses a **unified multi-channel architecture (v3.0)** to provide:
- **Dual-Agent System**: Admin Agent (document management, batch notifications) + Employee Agent (knowledge Q&A, expert routing)
- **Multi-Channel Support**: Web UI (Admin + Employee) + IM platforms (WeChat Work, Feishu, DingTalk, Slack)
- **Channel Abstraction**: Unified interface for multi-platform messaging via Channel Adapter pattern

**Architecture Evolution**: v1.0 (Single Agent) → v2.0 (Dual-Agent + WeWork) → v3.0 (Unified Multi-Channel)

## Key Architecture Principles

### Agent-First Design Philosophy
This project follows an **Agent Autonomous Decision-Making** architecture:

- **❌ AVOID**: Creating specialized tools for every business logic scenario
- **✅ CORRECT**: Provide minimal base tools (read, write, grep, glob, bash) and let the Agent combine them intelligently
- **Core Principle**: Business logic resides in Agent prompts, not in code. The Agent makes autonomous decisions based on context.
- **Document Conversion**: Use Bash tool to invoke `smart_convert.py` script, not external MCP servers

### v3.0 Unified Multi-Channel Architecture (Current)
```
┌──────────────────────────────────────────────────────────────────────┐
│       Intelligent KBA (v3.0 Unified Multi-Channel)                   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Frontend Layer                                                      │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────────┐ │
│  │  Admin UI    │  │  Employee UI  │  │  IM Platforms            │ │
│  │  (port 3000) │  │  (port 3001)  │  │  WeWork/Feishu/DingTalk  │ │
│  └──────┬───────┘  └───────┬───────┘  └──────────┬───────────────┘ │
│         │                  │                      │                 │
│         └──────────────────┴──────────────────────┘                 │
│                            │                                        │
│  Backend Layer (FastAPI 8000)                                       │
│  ┌──────────────────────────┴────────────────────────┐             │
│  │                                                    │             │
│  │  ┌──────────────┐         ┌──────────────────┐   │             │
│  │  │ Admin Agent  │         │ Employee Agent   │   │             │
│  │  │ - Doc Mgmt   │         │ - Knowledge Q&A  │   │             │
│  │  │ - Batch      │         │ - Expert Routing │   │             │
│  │  │   Notify     │         │                  │   │             │
│  │  └──────────────┘         └──────────────────┘   │             │
│  │                                                    │             │
│  │  KBServiceFactory (Dual SDK Clients)              │             │
│  └────────────────────────────────────────────────────┘             │
│                            │                                        │
│  Channel Layer                                                      │
│  ┌──────────────────────────┴────────────────────────┐             │
│  │         ChannelRouter (Message Routing)           │             │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────┐  │             │
│  │  │ WeWork      │  │ Feishu       │  │ Web     │  │             │
│  │  │ Adapter     │  │ Adapter      │  │ Adapter │  │             │
│  │  │ (port 8081) │  │ (port 8082)  │  │         │  │             │
│  │  └─────────────┘  └──────────────┘  └─────────┘  │             │
│  │           (BaseChannelAdapter)                    │             │
│  └───────────────────────────────────────────────────┘             │
│                            │                                        │
│  Infrastructure Layer                                               │
│  ┌──────────────────────────┴────────────────────────┐             │
│  │  Redis  │  ConversationStateManager               │             │
│  │         │  DomainExpertRouter                     │             │
│  │         │  SharedKBAccess (File Locking)          │             │
│  └─────────────────────────────────────────────────────┘             │
└──────────────────────────────────────────────────────────────────────┘
```

**v3.0 Key Features**:
- ✅ **Channel Abstraction Layer**: `BaseChannelAdapter` for multi-IM platform support
- ✅ **Three Interfaces**: Admin UI + Employee Web UI + IM Platforms
- ✅ **Hybrid Configuration**: Auto-detect configured channels (auto/enabled/disabled modes)
- ✅ **Dual-Agent System**: Preserved from v2.0, enhanced with multi-channel support
- ✅ **Scalability**: Independent scaling per channel, platform-agnostic design
- ✅ **Developer Experience**: Smart startup script (`start_v3.sh`) with automatic channel detection

**v3.0 vs v2.0 Comparison**:
| Feature | v2.0 | v3.0 |
|---------|------|------|
| Admin Interface | Web UI only | Web UI only |
| Employee Interface | WeChat Work only | Web UI + Multi-IM platforms |
| Channel Support | WeChat Work (hardcoded) | WeWork/Feishu/DingTalk/Slack (pluggable) |
| Configuration | Manual setup | Auto-detection (hybrid mode) |
| Architecture | Dual-Agent | Dual-Agent + Channel Adapter |

### v2.0 Dual-Agent Architecture (Legacy)
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

**Key Benefits of Dual-Agent Architecture** (v2.0):
- ✅ Channel-specific optimization (WeChat Work vs Web UI)
- ✅ Independent scaling (employee queries vs admin tasks)
- ✅ Tool isolation (Employee: wework only, Admin: wework + smart_convert via Bash)
- ✅ Clear separation of concerns

## Development Commands

### Running the Application (v3.0)

**Quick Start (Recommended):**
```bash
# v3.0: Smart startup script with automatic channel detection
./scripts/start_v3.sh

# Stop all services
./scripts/stop.sh
```

**What starts automatically?**:
- ✅ Backend API (port 8000) - Always starts
- ✅ Admin UI (port 3000) - Always starts
- ✅ Employee UI (port 3001) - If `EMPLOYEE_UI_ENABLED=true` in .env
- ✅ IM Channel Services - Auto-detected based on configuration:
  - WeWork callback (port 8081) - If WEWORK env vars configured
  - Feishu callback (port 8082) - If FEISHU env vars configured
  - DingTalk callback (port 8083) - If DINGTALK env vars configured
  - Slack callback (port 8084) - If SLACK env vars configured

**Manual Start (v3.0):**
```bash
# Terminal 1 - Backend (FastAPI with both Admin and Employee agents)
python3 -m backend.main
# Runs on http://localhost:8000
# Health check: http://localhost:8000/health

# Terminal 2 - Admin UI
cd frontend && npm run dev
# Runs on http://localhost:3000

# Terminal 3 - Employee UI (optional)
cd frontend-employee && npm run dev
# Runs on http://localhost:3001

# Terminal 4 - IM Channel Services (optional, if configured)
# WeWork callback service (if WEWORK env vars configured)
python -m backend.channels.wework.server
# Runs on port 8081 (or WEWORK_PORT from .env)
```

**Legacy Start (v2.0):**
```bash
# For backward compatibility only
./scripts/start.sh

# Starts: Backend (8000) + Admin UI (3000)
# Does NOT start: Employee UI, Channel services
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

# Important dependencies for document conversion (smart_convert.py):
# - PyMuPDF, pymupdf4llm (PDF processing)
# - pypandoc (DOCX processing, requires pandoc installed)
# - requests (PaddleOCR API for scanned PDFs)
# All should be installed automatically via requirements.txt

# Verify smart_convert.py is accessible:
python backend/utils/smart_convert.py --help
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

### Document Conversion: smart_convert.py

**What is smart_convert?**
A standalone Python utility (`backend/utils/smart_convert.py`) that intelligently converts documents to Markdown with automatic format detection and optimized processing pipelines.

**Conversion Approach** (replaced markitdown-mcp):
- ❌ **Removed**: External MCP server dependency (`markitdown-mcp`)
- ✅ **Current**: Direct Python script invocation via Bash tool
- ✅ **Benefits**: Faster, more control, no MCP overhead, better error handling

**Conversion Command**:
```bash
python backend/utils/smart_convert.py <input_file> --json-output
```

**Supported Formats & Processing Pipelines**:
1. **DOCX/DOC**: Pandoc (format preservation, image extraction)
2. **PDF (Electronic)**: PyMuPDF4LLM (fast, local processing)
3. **PDF (Scanned)**: PaddleOCR-VL API (automatic detection, OCR processing)

**JSON Output Format**:
```json
{
  "success": true,
  "markdown_file": "/absolute/path/to/output.md",
  "images_dir": "filename_images",
  "image_count": 5,
  "input_file": "/absolute/path/to/input.pdf"
}
```

**Key Features:**
- ✅ **Automatic PDF type detection** (electronic vs. scanned)
- ✅ **Image extraction** to `<filename>_images/` directory
- ✅ **JSON output** for programmatic parsing
- ✅ **Error handling** with detailed error messages
- ✅ **Force OCR mode** via `--force-ocr` flag

**Dependencies** (in `requirements.txt`):
- `PyMuPDF` (PDF rendering)
- `pymupdf4llm` (PDF to Markdown)
- `pypandoc` (DOCX to Markdown)
- `requests` (PaddleOCR API calls)

**Environment Variables**:
- `PADDLE_OCR_TOKEN`: PaddleOCR API token (for scanned PDFs)

### Custom Tool: image_read (SDK MCP Tool)

**What is image_read?**
A custom vision tool that allows agents to read and analyze image content using multimodal AI models. This tool provides targeted analysis based on agent-specified questions, enabling context-aware image understanding.

**Implementation Approach:**
- ✅ **SDK MCP Tool**: Created using `@tool` decorator and `create_sdk_mcp_server()`
- ✅ **In-process execution**: Runs within the Python application (no external MCP server needed)
- ✅ **Multi-provider support**: Doubao (Volcano Engine), OpenAI GPT-4V, Anthropic Claude 3

**Configuration** (`backend/services/kb_service_factory.py`):
```python
from backend.tools.image_read import image_read_handler
from claude_agent_sdk import create_sdk_mcp_server

# Create SDK MCP server
image_vision_server = create_sdk_mcp_server(
    name="image_vision",
    version="1.0.0",
    tools=[image_read_handler]
)

# Add to ClaudeAgentOptions
options = ClaudeAgentOptions(
    mcp_servers={
        "image_vision": image_vision_server,
        # ... other MCP servers
    },
    allowed_tools=[
        "mcp__image_vision__image_read",
        # ... other tools
    ]
)
```

**Tool Parameters:**
- `image_path`: Path to image file (absolute or relative to KB_ROOT_PATH)
- `question`: Specific question about the image (e.g., "描述图中的架构图逻辑", "提取图中的操作步骤")
- `context`: Optional context to help the model understand the question better

**Supported Providers** (configured via environment variables):
1. **Doubao (火山引擎)** - Default
   - `VISION_MODEL_PROVIDER=doubao`
   - `VISION_MODEL_API_KEY=<your_api_key>`
   - `VISION_MODEL_BASE_URL=https://ark.cn-beijing.volces.com/api/v3`
   - `VISION_MODEL_NAME=ep-20250122183949-wz66v` (Doubao Seed 1.6 Vision)

2. **OpenAI GPT-4V**
   - `VISION_MODEL_PROVIDER=openai`
   - `VISION_MODEL_API_KEY=<your_api_key>`
   - `VISION_MODEL_BASE_URL=https://api.openai.com/v1`
   - `VISION_MODEL_NAME=gpt-4o`

3. **Anthropic Claude 3**
   - `VISION_MODEL_PROVIDER=anthropic`
   - `VISION_MODEL_API_KEY=<your_api_key>`
   - `VISION_MODEL_BASE_URL=https://api.anthropic.com`
   - `VISION_MODEL_NAME=claude-3-5-sonnet-20241022`

**Key Benefits:**
- ✅ **Targeted analysis**: Agent can specify what to look for in the image
- ✅ **Context-aware**: Supports additional context for better understanding
- ✅ **Architecture alignment**: Follows Agent-First philosophy (provides capability, agent decides how to use it)
- ✅ **Multi-provider**: Easy to switch between vision model providers

**Usage Example:**
Agent autonomously decides when and how to use the tool:
```
User: "知识库中有个架构图，请分析一下"
Agent: [Uses Glob to find image] → [Uses image_read with question="描述图中的架构图逻辑和组件关系"] → [Provides analysis to user]
```

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
    - Document conversion via smart_convert.py (Bash tool)
    """,
    tools=["Read", "Write", "Grep", "Glob", "Bash"],
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

### Skills Integration

**What are Skills?**
Skills are specialized capabilities that extend Claude's abilities with domain knowledge, workflows, or tool integrations. They are enabled by adding `"Skill"` to `allowed_tools` in `ClaudeAgentOptions`.

**Official Documentation:**
```python
# Enable Skills in your agent
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Skill"],  # Add "Skill" to enable
    ...
)
```

**When to Use Skills:**
- ✅ **Complex multi-step workflows** (e.g., code review process, security audit flow)
- ✅ **Domain knowledge guidance** (e.g., brand design guidelines, internal communication templates)
- ✅ **Cross-project reusable capabilities** (e.g., algorithmic art generation, MCP server builder)

**When NOT to Use Skills:**
- ❌ **Simple script invocations** - Just document in Agent prompt instead
  - Example: Converting docs with `python backend/utils/smart_convert.py` doesn't need a Skill
  - Reason: Skill prompt would be trivial ("call this script"), adding unnecessary abstraction
- ❌ **Project-specific one-off tasks** - Use Agent prompt + base tools
- ❌ **Basic tool combinations** - Let Agent autonomously combine base tools

**Design Principle:**
If the Skill prompt would be extremely simple (e.g., "call script X with args Y"), it's a signal that you should just document the approach directly in the Agent's system prompt instead of creating a Skill wrapper.

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
- ❌ Does NOT use external conversion tools for XLSX processing
- ✅ Uses Bash tool to execute temporary Python scripts
- ✅ Leverages pandas for SQL-like queries (filter, join, aggregate)
- ✅ Supports complex filtering logic based on natural language conditions
- ✅ excel-parser Skill available for analyzing complex Excel structures

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
- **MCP Tools**: wework only (lightweight operation, no document conversion needed)
- **Characteristics**: Lightweight, high-frequency requests, async multi-turn conversations
- **Key Features**:
  - 6-stage retrieval workflow (FAQ → README → keyword search → adaptive retrieval → context expansion → answer generation)
  - Expert routing when KB search fails
  - Maintains conversation state for expert reply handling

**2. Admin Agent (`backend/agents/kb_admin_agent.py`)**
- **Responsibilities**: Document ingestion, KB management, Batch notifications
- **Interface**: Web Admin UI (React SPA) via FastAPI service on port 8000
- **Tools**: Bash (smart_convert.py for document conversion) + wework (full feature set)
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

## v3.0 Unified Multi-Channel Architecture (Latest)

**Status**: Phase 1-3 Complete (71%), Phase 4-6 Pending
**Last Updated**: 2025-01-25

### New Architecture Components

#### 1. Channel Abstraction Layer (`backend/channels/`)

**Core Files**:
- `backend/channels/base.py` (443 lines) - Abstract base classes and data models
- `backend/channels/wework/` - WeChat Work adapter implementation (1051 lines)
- `backend/services/channel_router.py` (332 lines) - Unified message routing

**Key Classes**:
```python
# Base adapter for all IM platforms
class BaseChannelAdapter:
    def send_message(msg: ChannelMessage) -> ChannelResponse
    def parse_message(raw_data) -> ChannelMessage
    def verify_signature(signature, data) -> bool
    def is_configured() -> bool

# Unified data models
@dataclass
class ChannelMessage:
    channel_type: ChannelType  # WEWORK/FEISHU/DINGTALK/SLACK/WEB
    message_type: MessageType  # TEXT/MARKDOWN/IMAGE/FILE/EVENT
    user_id: str
    content: str
    ...

# Channel router
class ChannelRouter:
    async def route_message(channel_msg) -> ChannelResponse
    async def send_batch_response(channel, users, content)
```

**Design Principles**:
- ✅ Platform-agnostic: Same interface for all IM platforms
- ✅ Lazy loading: Adapters initialize only when configured
- ✅ Extensible: Add new channels by implementing BaseChannelAdapter
- ✅ Type-safe: Pydantic models for all data structures

#### 2. Hybrid Configuration System (`backend/config/channel_config.py`)

**Configuration Modes**:
```bash
# .env file
ENABLE_WEWORK=auto      # Auto-detect (default) - enables if env vars configured
ENABLE_FEISHU=enabled   # Force enable - fails if not configured
ENABLE_DINGTALK=disabled  # Force disable - ignores even if configured
```

**Auto-Detection Logic**:
```python
from backend.config.channel_config import get_channel_config

config = get_channel_config()
enabled_channels = config.get_enabled_channels()
# Returns: ['wework'] if only WEWORK_* env vars configured
# Returns: ['wework', 'feishu'] if both configured
# Returns: [] if none configured
```

**Benefits**:
- ✅ Zero configuration overhead (works out-of-the-box if env vars set)
- ✅ Flexible deployment scenarios (single channel, multi-channel, or no channels)
- ✅ Clear error messages when required env vars missing

#### 3. Employee Web UI (`frontend-employee/`)

**Features**:
- 💬 Chat-style interface (similar to ChatGPT)
- 🚀 SSE streaming for real-time responses
- 📝 Markdown rendering with code highlighting
- 🎨 Tailwind CSS for consistent design
- 🔒 No authentication (localStorage-based user ID)

**API Endpoint**:
```python
# backend/api/employee.py
@router.get("/api/employee/query")
async def employee_query(
    question: str,
    user_id: str,
    session_id: Optional[str] = None
):
    # Uses Employee Agent (kb_qa_agent.py)
    # Returns SSE stream
```

**Access**:
- URL: http://localhost:3001
- Ports: Configurable via `EMPLOYEE_UI_PORT` in .env

#### 4. Smart Startup Script (`scripts/start_v3.sh`)

**Automatic Channel Detection**:
```bash
#!/bin/bash
# Auto-detects configured channels and starts only those services

# Example output:
# ✅ Detected channels: wework, feishu
# 🚀 Starting Backend API (port 8000)...
# 🚀 Starting WeWork callback (port 8081)...
# 🚀 Starting Feishu callback (port 8082)...
# 🚀 Starting Admin UI (port 3000)...
# 🚀 Starting Employee UI (port 3001)...
```

**Port Management**:
- Checks port availability before starting
- Configurable ports for each channel
- Health checks after startup

### Migration Path: v2.0 → v3.0

**Backward Compatibility**:
- ✅ v2.0 code fully preserved (no breaking changes)
- ✅ `scripts/start.sh` still works (legacy mode)
- ✅ WeWork integration unchanged from user perspective

**New Files (v3.0)**:
| File | Lines | Purpose |
|------|-------|---------|
| `backend/channels/base.py` | 443 | Channel abstraction |
| `backend/channels/wework/*.py` | 1051 | WeWork adapter |
| `backend/services/channel_router.py` | 332 | Message routing |
| `backend/config/channel_config.py` | 232 | Hybrid config |
| `backend/api/employee.py` | 155 | Employee API |
| `frontend-employee/` | ~2000 | Employee Web UI |
| `scripts/start_v3.sh` | 382 | Smart startup |
| **Total** | **~4600** | **v3.0 core** |

**Modified Files**:
- `.env.example` - Added multi-channel configuration templates
- `backend/config/settings.py` - Added CORS for port 3001
- `backend/main.py` - Initialize both Admin and Employee agents
- `backend/requirements.txt` - Removed markitdown-mcp, added PyMuPDF/pypandoc

**Deprecated Files**:
- `backend/agents/unified_agent.py` - Use kb_admin_agent.py + kb_qa_agent.py instead

### Future Roadmap

**Phase 4: Feishu Adapter** (Optional - 2 days)
- Create `backend/channels/feishu/` following WeWork pattern
- Test multi-channel routing

**Phase 5: Documentation** (1 day) - Current Phase
- ✅ Update CLAUDE.md to v3.0
- Create MIGRATION_V3.md
- Create CHANNELS.md (channel development guide)

**Phase 6: Testing & Deployment** (2 days)
- Unit tests for channel adapters
- Integration tests for multi-channel routing
- Docker Compose configuration

### Quick Reference (v3.0)

**Check Configured Channels**:
```bash
python -c "
from backend.config.channel_config import get_channel_config
config = get_channel_config()
print('Enabled channels:', config.get_enabled_channels())
print('Status:', config.get_channel_status())
"
```

**Test WeWork Adapter**:
```bash
python -c "
from backend.channels.wework import WeWorkAdapter
adapter = WeWorkAdapter()
print('Configured:', adapter.is_configured())
print('Required env vars:', adapter.get_required_env_vars())
"
```

**Startup Troubleshooting**:
```bash
# If services don't start, check:
1. Port availability: lsof -i :8000,:3000,:3001,:8081-8084
2. Configuration: cat .env | grep ENABLE_
3. Logs: tail -f logs/backend.log logs/wework.log logs/frontend.log
```

---

**Architecture Version**: v3.0 (Unified Multi-Channel Architecture)
**Last Updated**: 2025-01-25
**Implementation Status**: Phase 1-3 Complete (71%), Phase 4-6 Pending
**Branch**: main (merged from wework_integration)

**Further Reading**:
- Migration Guide: `docs/MIGRATION_V3.md` (to be created)
- Channel Development: `docs/CHANNELS.md` (to be created)
- Progress Tracking: `docs/PROGRESS_V3.md`
- Task List: `docs/TODO_V3.md`
