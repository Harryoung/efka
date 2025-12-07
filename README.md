# Intelligent Knowledge Base Administrator

> AI-powered knowledge base management without embedding-based search. Maybe slower, but results are much more reliable!

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Claude](https://img.shields.io/badge/Claude-Agent%20SDK-orange.svg)](https://github.com/anthropics/claude-code)

An intelligent knowledge base management system built with Claude Agent SDK. Features a dual-agent architecture for document management (Admin) and knowledge Q&A (Employee), with multi-channel support including Web UI and enterprise IM platforms.

## Features

- **Intelligent Q&A**: 7-stage retrieval strategy with expert routing - accurate answers with source attribution
- **Smart Document Ingestion**: Automatic format conversion, semantic conflict detection, intelligent file placement
- **FAQ System**: Automatic learning from interactions, usage tracking, and optimization
- **Multi-Channel Support**: Web UI + Enterprise IM platforms (WeChat Work, Feishu, DingTalk, Slack)
- **Dual-Agent Architecture**: Separate agents optimized for admin tasks and employee queries
- **Streaming Responses**: Real-time SSE streaming with Markdown rendering

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Frontend Layer                                       │
│  ┌─────────────┐  ┌──────────────────────────────┐  │
│  │  Web UI     │  │  IM Platforms                │  │
│  │  (3000)     │  │  WeWork / Feishu / DingTalk  │  │
│  └──────┬──────┘  └──────────────┬───────────────┘  │
│         └────────────┬───────────┘                   │
├──────────────────────┼───────────────────────────────┤
│  Backend (FastAPI)   │                               │
│  ┌─────────────┐  ┌──┴──────────┐                   │
│  │ Admin Agent │  │ Employee    │                   │
│  │ - Doc Mgmt  │  │ Agent       │                   │
│  │ - KB Admin  │  │ - Q&A       │                   │
│  │ - Notify    │  │ - Routing   │                   │
│  └─────────────┘  └─────────────┘                   │
├──────────────────────────────────────────────────────┤
│  Infrastructure: Redis | Knowledge Base | Channels   │
└──────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Redis 7+
- Claude API Key
- Pandoc (for document conversion)
  - macOS: `brew install pandoc`
  - Ubuntu: `apt-get install pandoc`

### Installation

```bash
# Clone the repository
git clone https://github.com/anthropics/intelligent-kba.git
cd intelligent-kba

# Configure environment
cp .env.example .env
# Edit .env with your Claude API Key and other settings

# Install backend dependencies
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# Start services
./scripts/start.sh
```

Access the application:
- **Web UI**: http://localhost:3000
- **API**: http://localhost:8000/health

Stop services: `./scripts/stop.sh`

### Docker Deployment

```bash
cp .env.example .env
# Edit .env with your configuration

docker-compose up -d
```

## Configuration

Key environment variables (see `.env.example` for full list):

| Variable | Description | Required |
|----------|-------------|----------|
| `CLAUDE_API_KEY` | Claude API key | Yes |
| `KB_ROOT_PATH` | Knowledge base directory | No (default: ./knowledge_base) |
| `REDIS_HOST` | Redis host | No (default: localhost) |
| `WEWORK_CORP_ID` | WeChat Work Corp ID | For WeWork integration |

### IM Platform Integration

The system supports multiple IM platforms through a pluggable Channel Adapter architecture:

```bash
# WeChat Work
ENABLE_WEWORK=auto
WEWORK_CORP_ID=your_corp_id
WEWORK_CORP_SECRET=your_secret
WEWORK_AGENT_ID=your_agent_id
```

See [Channel Development Guide](docs/CHANNELS.md) for adding new platforms.

## Project Structure

```
intelligent-kba/
├── backend/
│   ├── agents/          # Agent definitions (Admin + Employee)
│   ├── api/             # FastAPI routes
│   ├── channels/        # IM platform adapters
│   ├── services/        # Business logic
│   ├── tools/           # Custom tools (image_read, etc.)
│   └── utils/           # Utilities (smart_convert.py)
├── frontend/            # React Web UI
├── knowledge_base/      # Document storage
├── scripts/             # Deployment scripts
├── docs/                # Documentation
└── wework-mcp/          # WeChat Work MCP server (submodule)
```

## Documentation

- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions
- [Channel Development Guide](docs/CHANNELS.md) - Adding new IM platform support

## Tech Stack

- **Backend**: Python / FastAPI / Claude Agent SDK / Redis
- **Frontend**: React 18 / Vite / Tailwind CSS
- **AI**: Claude (via Agent SDK)
- **Document Processing**: PyMuPDF / pypandoc / PaddleOCR

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Built with [Claude Agent SDK](https://github.com/anthropics/claude-code) by Anthropic.
