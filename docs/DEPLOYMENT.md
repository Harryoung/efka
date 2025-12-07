# Deployment Guide

This document provides deployment instructions for the Intelligent Knowledge Base Administrator.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Requirements](#requirements)
3. [Quick Deployment](#quick-deployment)
4. [Configuration](#configuration)
5. [Docker Deployment](#docker-deployment)
6. [Production Setup](#production-setup)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Production Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Internet                                    │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Nginx / Load Balancer                            │
│                    (SSL termination, reverse proxy)                 │
└─────────────────────────────────────────────────────────────────────┘
         │                            │                    │
         ▼                            ▼                    ▼
┌─────────────────┐        ┌─────────────────┐   ┌─────────────────┐
│    Web UI       │        │  Backend API    │   │  IM Callbacks   │
│    (3000)       │        │    (8000)       │   │  (8081-8084)    │
└─────────────────┘        └─────────────────┘   └─────────────────┘
                                    │
                                    ▼
                          ┌─────────────────┐
                          │     Redis       │
                          │    (6379)       │
                          └─────────────────┘
```

### Service Ports

| Service | Port | Description |
|---------|------|-------------|
| Web UI | 3000 | React frontend |
| Backend API | 8000 | FastAPI service |
| WeWork Callback | 8081 | WeChat Work integration |
| Feishu Callback | 8082 | Feishu integration (optional) |
| DingTalk Callback | 8083 | DingTalk integration (optional) |
| Slack Callback | 8084 | Slack integration (optional) |
| Redis | 6379 | Session storage |

---

## Requirements

### Hardware

| Environment | CPU | Memory | Storage |
|-------------|-----|--------|---------|
| Development | 2 cores | 4 GB | 20 GB |
| Testing | 4 cores | 8 GB | 50 GB |
| Production | 8 cores | 16 GB | 100 GB |

### Software

- **OS**: Ubuntu 20.04+ / CentOS 7+ / macOS 12+
- **Python**: 3.10+
- **Node.js**: 18+
- **Docker**: 20.10+ (for Docker deployment)
- **Docker Compose**: 2.0+ (for Docker deployment)

### Network

- **Inbound**: 80, 443 (HTTP/HTTPS), 8081-8084 (IM callbacks)
- **Outbound**: Anthropic API, WeChat Work API, Feishu API, etc.

---

## Quick Deployment

### Local Development

```bash
# 1. Clone the repository
git clone <repository-url>
cd intelligent-kba

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Set up Python environment
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# 4. Install frontend dependencies
cd frontend && npm install && cd ..

# 5. Start services
./scripts/start.sh

# 6. Access the application
# Web UI: http://localhost:3000
# API: http://localhost:8000
```

### Docker Quick Start

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your configuration

# 2. Start all services
docker-compose up -d

# 3. View logs
docker-compose logs -f

# 4. Stop services
docker-compose down
```

---

## Configuration

### Required Environment Variables

```bash
# Claude API (required - choose one)
CLAUDE_API_KEY=your_claude_api_key

# Or use Anthropic Token (enterprise)
ANTHROPIC_AUTH_TOKEN=your_auth_token
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

### Knowledge Base Configuration

```bash
KB_ROOT_PATH=./knowledge_base
SMALL_FILE_KB_THRESHOLD=30
FAQ_MAX_ENTRIES=50
SESSION_TIMEOUT=1800
```

### Redis Configuration

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password  # If authentication enabled
```

### Channel Configuration

```bash
# Channel enable mode: auto | enabled | disabled
ENABLE_WEWORK=auto
ENABLE_FEISHU=auto

# WeChat Work
WEWORK_CORP_ID=your_corp_id
WEWORK_CORP_SECRET=your_corp_secret
WEWORK_AGENT_ID=your_agent_id
WEWORK_TOKEN=your_token
WEWORK_ENCODING_AES_KEY=your_aes_key
WEWORK_PORT=8081
```

### Vision Model (Optional)

```bash
VISION_MODEL_PROVIDER=doubao
VISION_MODEL_API_KEY=your_api_key
VISION_MODEL_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
VISION_MODEL_NAME=ep-xxx
```

---

## Docker Deployment

### Docker Compose Profiles

| Profile | Description | Command |
|---------|-------------|---------|
| (default) | Backend + Web UI + Redis | `docker-compose up -d` |
| wework | Include WeWork callback | `docker-compose --profile wework up -d` |
| production | Include Nginx reverse proxy | `docker-compose --profile production up -d` |

### Full Deployment Example

```bash
# Start all services with WeWork
docker-compose --profile wework up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f backend

# Restart a service
docker-compose restart backend

# Update and restart
docker-compose pull
docker-compose up -d
```

### Build Custom Images

```bash
# Build all images
docker-compose build

# Build single image
docker-compose build backend

# Build with arguments
docker-compose build --build-arg VITE_API_BASE_URL=https://api.example.com frontend
```

### Data Persistence

| Volume | Mount Point | Description |
|--------|-------------|-------------|
| redis_data | /data | Redis data |
| ./knowledge_base | /app/knowledge_base | Knowledge base files |
| ./logs | /app/logs | Log files |

---

## Production Setup

### Nginx Reverse Proxy

```nginx
upstream backend {
    server 127.0.0.1:8000;
}

upstream frontend {
    server 127.0.0.1:3000;
}

server {
    listen 80;
    server_name example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /etc/ssl/certs/example.com.crt;
    ssl_certificate_key /etc/ssl/private/example.com.key;

    location /api {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
```

### Systemd Services

```ini
# /etc/systemd/system/ikba-backend.service
[Unit]
Description=IKBA Backend Service
After=network.target redis.service

[Service]
User=www-data
WorkingDirectory=/opt/intelligent-kba
Environment="PATH=/opt/intelligent-kba/venv/bin"
EnvironmentFile=/opt/intelligent-kba/.env
ExecStart=/opt/intelligent-kba/venv/bin/python -m backend.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Monitoring

### Health Check Endpoints

| Endpoint | Description |
|----------|-------------|
| GET /health | Service health status |
| GET /info | Service version info |

### Log Management

```bash
# View real-time logs
tail -f logs/backend.log

# Docker logs
docker-compose logs -f --tail=100 backend

# Log rotation (logrotate)
/app/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

### Recommended Tools

- **Prometheus**: Metrics collection
- **Grafana**: Visualization
- **ELK Stack**: Log analysis
- **Sentry**: Error tracking

### Backup Strategy

```bash
# Knowledge base backup
tar -czvf kb_backup_$(date +%Y%m%d).tar.gz knowledge_base/

# Redis backup
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb backup/

# Automated backup (cron)
0 2 * * * /opt/intelligent-kba/scripts/backup.sh >> /var/log/backup.log 2>&1
```

---

## Troubleshooting

### Common Issues

#### Service Won't Start

```bash
# Check port conflicts
lsof -i :8000
lsof -i :3000

# Check environment variables
printenv | grep CLAUDE

# Check logs
tail -100 logs/backend.log
```

#### Agent Response Timeout

```bash
# Test Claude API connection
curl -X POST https://api.anthropic.com/v1/messages \
  -H "x-api-key: $CLAUDE_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model": "claude-sonnet-4-20250514", "max_tokens": 10, "messages": [{"role": "user", "content": "Hi"}]}'

# Increase timeout
export SESSION_TIMEOUT=3600
```

#### WeWork Callback Failed

```bash
# Check callback service
curl http://localhost:8081/health

# Verify configuration
python -c "
from backend.channels.wework import WeWorkAdapter
adapter = WeWorkAdapter()
print('Configured:', adapter.is_configured())
"

# View logs
tail -f logs/wework.log
```

#### Redis Connection Failed

```bash
# Check Redis status
redis-cli ping

# Check connection
redis-cli -h $REDIS_HOST -p $REDIS_PORT INFO

# Docker environment
docker-compose exec redis redis-cli ping
```

### Performance Optimization

```bash
# Run with multiple workers
uvicorn backend.main:app --workers 4 --host 0.0.0.0 --port 8000
```

### Security Hardening

1. **Enable HTTPS**: Configure SSL certificates
2. **API Authentication**: Add API key verification
3. **Rate Limiting**: Configure Nginx rate limiting
4. **Audit Logging**: Record all operations
5. **Regular Updates**: Keep dependencies updated

---

## Support

- **Documentation**: See `docs/` directory
- **Issues**: Submit GitHub Issues
- **Channels Guide**: See [CHANNELS.md](CHANNELS.md) for IM integration
