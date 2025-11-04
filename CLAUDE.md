# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

智能资料库管理员 (Intelligent Knowledge Base Administrator) - An AI-powered knowledge base management system built with Claude Agent SDK. The system uses a **single unified agent architecture** to provide intelligent Q&A, document management, and knowledge base administration capabilities.

## Key Architecture Principles

### Agent-First Design Philosophy
This project follows an **Agent Autonomous Decision-Making** architecture:

- **❌ AVOID**: Creating specialized tools for every business logic scenario
- **✅ CORRECT**: Provide minimal base tools (read, write, grep, glob, bash, markitdown-mcp) and let the Agent combine them intelligently
- **Core Principle**: Business logic resides in Agent prompts, not in code. The Agent makes autonomous decisions based on context.

### Single Agent Architecture
```
Web Frontend (React + SSE)
    ↓
Unified Intelligent KB Agent
(Intent recognition + Knowledge QA + Document Management + KB Administration)
    ↓
Base Tools: Read, Write, Grep, Glob, Bash, markitdown-mcp
```

**Key Benefits of Single Agent Architecture**:
- ✅ Eliminated sub-agent call overhead (20-30% performance improvement)
- ✅ Simplified codebase (reduced from 3 agents to 1)
- ✅ Unified context management across all tasks
- ✅ Easier maintenance and prompt optimization

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
lsof -i :8000  # Check backend port
lsof -i :3000  # Check frontend port
kill -9 <PID>  # Force stop process
```

**Health Checks:**
```bash
curl http://localhost:8000/health
curl http://localhost:8000/info
```

**View Real-time Logs:**
```bash
tail -f logs/backend.log
tail -f logs/frontend.log
```

**Restart Services:**
```bash
./scripts/stop.sh && ./scripts/start.sh
```
