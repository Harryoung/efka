# Intelligent KBA v3.0 - 部署指南

本文档提供 Intelligent KBA v3.0 统一多渠道架构的完整部署指南。

## 目录

1. [部署架构](#部署架构)
2. [环境要求](#环境要求)
3. [快速部署](#快速部署)
4. [详细配置](#详细配置)
5. [Docker 部署](#docker-部署)
6. [Kubernetes 部署](#kubernetes-部署)
7. [监控与运维](#监控与运维)
8. [故障排除](#故障排除)

---

## 部署架构

### 生产环境架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Internet                                    │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Nginx / Load Balancer                            │
│                    (SSL 终止, 反向代理)                              │
└─────────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Admin UI   │ │ Employee UI │ │ Backend API │ │ IM Callbacks│
│  (3000)     │ │   (3001)    │ │   (8000)    │ │ (8081-8084) │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
                                       │
                                       ▼
                            ┌─────────────────┐
                            │     Redis       │
                            │    (6379)       │
                            └─────────────────┘
```

### 服务端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| Admin UI | 3000 | 管理员 Web 界面 |
| Employee UI | 3001 | 员工 Web 界面 |
| Backend API | 8000 | FastAPI 后端服务 |
| WeWork Callback | 8081 | 企业微信回调服务 |
| Feishu Callback | 8082 | 飞书回调服务 (可选) |
| DingTalk Callback | 8083 | 钉钉回调服务 (可选) |
| Slack Callback | 8084 | Slack 回调服务 (可选) |
| Redis | 6379 | 会话状态存储 |

---

## 环境要求

### 硬件要求

| 环境 | CPU | 内存 | 存储 |
|------|-----|------|------|
| 开发 | 2 核 | 4 GB | 20 GB |
| 测试 | 4 核 | 8 GB | 50 GB |
| 生产 | 8 核 | 16 GB | 100 GB |

### 软件要求

- **操作系统**: Ubuntu 20.04+ / CentOS 7+ / macOS 12+
- **Python**: 3.10+
- **Node.js**: 18+
- **Docker**: 20.10+ (Docker 部署)
- **Docker Compose**: 2.0+ (Docker 部署)

### 网络要求

- **入站端口**: 80, 443 (HTTP/HTTPS), 8081-8084 (IM 回调)
- **出站访问**: Anthropic API, 企业微信 API, 飞书 API 等

---

## 快速部署

### 方式一: 本地开发部署

```bash
# 1. 克隆代码
git clone <repository-url>
cd intelligent_kba

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置必要的 API Key

# 3. 安装后端依赖
pip install -r backend/requirements.txt

# 4. 安装前端依赖
cd frontend && npm install && cd ..
cd frontend-employee && npm install && cd ..

# 5. 启动服务
./scripts/start_v3.sh

# 6. 访问服务
# Admin UI: http://localhost:3000
# Employee UI: http://localhost:3001
# API: http://localhost:8000
```

### 方式二: Docker 快速部署

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 2. 启动所有服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止服务
docker-compose down
```

---

## 详细配置

### 环境变量说明

创建 `.env` 文件并配置以下变量:

#### Claude API 配置 (必需)

```bash
# 方式一: 使用 Claude API Key
CLAUDE_API_KEY=your_claude_api_key

# 方式二: 使用 Anthropic Token (企业版)
ANTHROPIC_AUTH_TOKEN=your_auth_token
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

#### 知识库配置

```bash
# 知识库根目录
KB_ROOT_PATH=./knowledge_base

# 小文件阈值 (KB)
SMALL_FILE_KB_THRESHOLD=30

# FAQ 最大条目数
FAQ_MAX_ENTRIES=50

# 会话超时 (秒)
SESSION_TIMEOUT=1800
```

#### Redis 配置

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

#### 渠道配置

```bash
# 渠道启用模式: auto | enabled | disabled
ENABLE_WEWORK=auto
ENABLE_FEISHU=auto
ENABLE_DINGTALK=auto
ENABLE_SLACK=auto

# Employee UI
EMPLOYEE_UI_ENABLED=true
EMPLOYEE_UI_PORT=3001
```

#### 企业微信配置

```bash
WEWORK_CORP_ID=your_corp_id
WEWORK_CORP_SECRET=your_corp_secret
WEWORK_AGENT_ID=your_agent_id
WEWORK_TOKEN=your_token
WEWORK_ENCODING_AES_KEY=your_aes_key
WEWORK_PORT=8081
```

#### Vision 模型配置 (可选)

```bash
VISION_MODEL_PROVIDER=doubao
VISION_MODEL_API_KEY=your_api_key
VISION_MODEL_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
VISION_MODEL_NAME=ep-xxx
```

---

## Docker 部署

### 服务配置

`docker-compose.yml` 支持以下 profiles:

| Profile | 说明 | 命令 |
|---------|------|------|
| (默认) | Backend + Admin UI + Redis | `docker-compose up -d` |
| wework | 包含 WeWork 回调服务 | `docker-compose --profile wework up -d` |
| employee-ui | 包含 Employee UI | `docker-compose --profile employee-ui up -d` |
| production | 包含 Nginx 反向代理 | `docker-compose --profile production up -d` |

### 完整部署示例

```bash
# 启动所有服务 (包含 WeWork 和 Employee UI)
docker-compose \
  --profile wework \
  --profile employee-ui \
  up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend

# 重启单个服务
docker-compose restart backend

# 更新镜像并重启
docker-compose pull
docker-compose up -d
```

### 构建自定义镜像

```bash
# 构建所有镜像
docker-compose build

# 构建单个镜像
docker-compose build backend

# 带参数构建
docker-compose build --build-arg VITE_API_BASE_URL=https://api.example.com admin-ui
```

### 数据持久化

| 卷名 | 挂载点 | 说明 |
|------|--------|------|
| redis_data | /data | Redis 数据 |
| ./knowledge_base | /app/knowledge_base | 知识库文件 |
| ./logs | /app/logs | 日志文件 |

---

## Kubernetes 部署

### 部署清单示例

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ikba-backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ikba-backend
  template:
    metadata:
      labels:
        app: ikba-backend
    spec:
      containers:
      - name: backend
        image: ikba-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: CLAUDE_API_KEY
          valueFrom:
            secretKeyRef:
              name: ikba-secrets
              key: claude-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 40
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
```

### Helm Chart (推荐)

```bash
# 安装
helm install ikba ./charts/ikba \
  --set claude.apiKey=$CLAUDE_API_KEY \
  --set wework.enabled=true

# 升级
helm upgrade ikba ./charts/ikba -f values.yaml

# 卸载
helm uninstall ikba
```

---

## 监控与运维

### 健康检查端点

| 端点 | 说明 |
|------|------|
| GET /health | 服务健康状态 |
| GET /info | 服务版本信息 |
| GET /metrics | Prometheus 指标 (可选) |

### 日志管理

```bash
# 查看实时日志
tail -f logs/backend.log

# Docker 日志
docker-compose logs -f --tail=100 backend

# 日志轮转配置 (logrotate)
/app/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

### 性能监控

建议使用以下工具:

- **Prometheus**: 指标收集
- **Grafana**: 可视化仪表盘
- **ELK Stack**: 日志分析
- **Sentry**: 错误追踪

### 备份策略

```bash
# 知识库备份
tar -czvf kb_backup_$(date +%Y%m%d).tar.gz knowledge_base/

# Redis 数据备份
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb backup/

# 自动备份脚本
0 2 * * * /app/scripts/backup.sh >> /var/log/backup.log 2>&1
```

---

## 故障排除

### 常见问题

#### 1. 服务无法启动

```bash
# 检查端口占用
lsof -i :8000
lsof -i :3000

# 检查环境变量
printenv | grep CLAUDE

# 检查日志
tail -100 logs/backend.log
```

#### 2. Agent 响应超时

```bash
# 检查 Claude API 连接
curl -X POST https://api.anthropic.com/v1/messages \
  -H "x-api-key: $CLAUDE_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model": "claude-sonnet-4-20250514", "max_tokens": 10, "messages": [{"role": "user", "content": "Hi"}]}'

# 增加超时时间
export SESSION_TIMEOUT=3600
```

#### 3. WeWork 回调失败

```bash
# 检查回调服务状态
curl http://localhost:8081/health

# 验证签名配置
python -c "
from backend.channels.wework import WeWorkAdapter
adapter = WeWorkAdapter()
print('Configured:', adapter.is_configured())
"

# 查看回调日志
tail -f logs/wework.log
```

#### 4. Redis 连接失败

```bash
# 检查 Redis 状态
redis-cli ping

# 检查连接配置
redis-cli -h $REDIS_HOST -p $REDIS_PORT INFO

# Docker 环境检查
docker-compose exec redis redis-cli ping
```

### 性能优化

#### 1. 增加并发处理能力

```bash
# uvicorn 多进程
uvicorn backend.main:app --workers 4 --host 0.0.0.0 --port 8000
```

#### 2. 启用响应缓存

```python
# 在 backend/config/settings.py 中配置
CACHE_ENABLED = True
CACHE_TTL = 300  # 5 分钟
```

#### 3. 优化知识库检索

- 建立索引
- 使用向量数据库 (可选)
- 定期清理过期会话

### 安全加固

1. **启用 HTTPS**: 配置 SSL 证书
2. **API 认证**: 添加 API Key 验证
3. **请求限流**: 配置 Nginx rate limiting
4. **日志审计**: 记录所有操作日志
5. **定期更新**: 保持依赖包最新

---

## 联系支持

- **文档**: 查看 `docs/` 目录下的详细文档
- **问题反馈**: 提交 GitHub Issue
- **技术支持**: 联系项目维护者

---

**文档版本**: v3.0.0
**最后更新**: 2025-01-25
