# 智能资料库管理员 (Intelligent Knowledge Base Administrator)

*Intelligent Knowledge Base Administrator, without embedding based search. Maybe slower, but result is much more reliable!*

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](https://github.com/Harryoung/intelligent-kba)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/architecture-v3.0_Multi--Channel-orange.svg)]()

基于 Claude Agent SDK 开发的智能知识库管理系统，采用**v3.0 统一多渠道架构**，支持Web UI和多种IM平台（企业微信、飞书、钉钉、Slack）的双Agent系统。

## 🌟 核心特性

### v3.0 新特性 (Latest)
- **🌐 多渠道支持**: Web UI + 企业微信/飞书/钉钉/Slack，统一的Channel Adapter架构
- **👥 双Agent系统**: Admin Agent (文档管理) + Employee Agent (知识问答)
- **⚙️ 混合配置**: 自动检测已配置渠道 (auto/enabled/disabled模式)
- **🎯 三端界面**: Admin Web UI (3000) + Employee Web UI (3001) + IM平台集成
- **🚀 智能启动**: 一键启动脚本，自动检测并启动配置的渠道服务

### 核心能力
- **🤖 智能问答**: 7阶段检索策略 + 专家路由，精准回答，可溯源无捏造
- **⚡ FAQ机制**: 常见问题快速响应，持续学习优化
- **📁 智能入库**: 自动格式转换，语义冲突检测，智能文件归置
- **🗂️ 结构维护**: 自动维护知识库结构，保持组织有序
- **💬 对话式UI**: Admin UI + Employee UI，简洁直观的聊天式交互体验
- **📱 IM集成**: 企业微信/飞书/钉钉/Slack无缝集成

## 🏗️ 技术栈

- **后端**: Python 3.10+ / FastAPI + Flask / Claude Agent SDK / SSE / Redis
- **前端**: React 18 / Vite / Tailwind CSS / Marked (Markdown渲染)
- **多渠道**: Channel Adapter模式 / 企业微信/飞书/钉钉/Slack API
- **部署**: Docker（规划中的容器化脚本）/ 智能启动脚本
- **AI**: Claude Sonnet 4.5 (通过Agent SDK)

## 🎯 架构演进

| 版本 | 架构 | 特性 |
|------|------|------|
| v1.0 | 单Agent | Web UI + 统一Agent |
| v2.0 | 双Agent | Web UI + 企业微信集成 |
| **v3.0** | **统一多渠道** | **Web UI (Admin + Employee) + 多IM平台** |

**v3.0 架构图**:
```
┌────────────────────────────────────────────────┐
│  Frontend Layer                                │
│  Admin UI | Employee UI | IM Platforms         │
│  (3000)   | (3001)      | (WeWork/Feishu)     │
├────────────────────────────────────────────────┤
│  Backend (FastAPI 8000)                        │
│  Admin Agent | Employee Agent                  │
├────────────────────────────────────────────────┤
│  Channel Layer                                 │
│  ChannelRouter + BaseChannelAdapter            │
│  WeWork | Feishu | DingTalk | Slack           │
└────────────────────────────────────────────────┘
```

## 📋 系统要求

- Python 3.10 或更高版本
- Node.js 18 或更高版本
- Docker（用于运行 Redis，或可选容器化部署）
- Redis 7+ 实例（推荐通过 Docker 启动）
- Claude API Key
- Pandoc（文档格式转换，处理 DOCX/DOC 文件）
  - Mac: `brew install pandoc`
  - Ubuntu: `apt-get install pandoc`
  - Windows: 从 [官网](https://pandoc.org/installing.html) 下载安装

## 🚀 快速开始

### 方式一：v3.0 智能启动脚本（推荐）

```bash
git clone https://github.com/Harryoung/intelligent-kba.git
cd intelligent-kba

# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，配置 Claude API Key 和其他选项

# 2. 赋予启动脚本执行权限
chmod +x scripts/start_v3.sh

# 3. 一键启动（自动检测并启动配置的服务）
./scripts/start_v3.sh
```

**启动后访问**:
- Admin UI: http://localhost:3000 (管理员界面)
- Employee UI: http://localhost:3001 (员工知识查询界面)
- Backend API: http://localhost:8000/health (健康检查)

**停止服务**: `./scripts/stop.sh`

**自动启动的服务**:
- ✅ Backend API (port 8000) - 总是启动
- ✅ Admin UI (port 3000) - 总是启动
- ✅ Employee UI (port 3001) - 如果 `EMPLOYEE_UI_ENABLED=true`
- ✅ IM渠道服务 - 自动检测并启动已配置的渠道:
  - WeWork callback (8081) - 如果配置了企业微信
  - Feishu callback (8082) - 如果配置了飞书
  - DingTalk callback (8083) - 如果配置了钉钉
  - Slack callback (8084) - 如果配置了Slack

### 方式二：使用传统启动脚本（v2.0兼容）

```bash
./scripts/start.sh  # 仅启动 Backend (8000) + Admin UI (3000)
```

浏览器访问 http://localhost:3000。

### 方式三：手动本地开发环境

#### 1. 克隆项目并配置环境变量

```bash
git clone https://github.com/Harryoung/intelligent-kba.git
cd intelligent-kba
cp .env.example .env
# 编辑 .env，填入 Claude/Redis 等配置
```

#### 2. 启动 Redis（Docker 示例）

```bash
docker run -d --name redis \
  --restart unless-stopped \
  -v $(pwd)/backend/config/redis_secure.conf:/usr/local/etc/redis/redis.conf:ro \
  -p 127.0.0.1:6379:6379 \
  redis:latest redis-server /usr/local/etc/redis/redis.conf
```

#### 3. 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ..
python -m backend.main
```

后端将在 http://localhost:8000 启动。

#### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端将在 http://localhost:3000 启动。

### 方式四：Docker部署

容器化部署脚本正在完善中(Phase 6)。后续版本将补充 docker-compose 与一键部署能力，欢迎关注仓库更新。

## 📖 项目结构

```
intelligent-kba/
├── backend/                        # 后端服务
│   ├── agents/                     # Agent 定义 (Admin + Employee)
│   ├── api/                        # FastAPI 路由
│   ├── channels/                   # 📱 v3.0: 渠道抽象层
│   │   ├── base.py                 # BaseChannelAdapter (443行)
│   │   └── wework/                 # 企业微信适配器示例
│   │       ├── client.py           # API客户端 (360行)
│   │       ├── adapter.py          # 适配器实现 (454行)
│   │       └── server.py           # 回调服务 (237行)
│   ├── config/                     # 配置（settings + channel_config）
│   ├── services/                   # 业务服务层
│   │   ├── channel_router.py      # 📱 v3.0: 渠道路由器 (332行)
│   │   ├── kb_service_factory.py  # 双Agent服务工厂
│   │   └── ...
│   ├── storage/                    # Redis 等存储实现
│   ├── tools/                      # 自定义工具 (image_read等)
│   ├── utils/                      # 工具函数 (smart_convert.py等)
│   ├── main.py                     # 应用入口
│   └── requirements.txt
├── frontend/                       # Admin UI (管理员界面)
│   ├── src/
│   │   ├── components/             # React 组件
│   │   └── ...
│   └── package.json
├── frontend-employee/              # 📱 v3.0: Employee UI (员工界面)
│   ├── src/
│   │   ├── components/             # ChatView, Message
│   │   ├── services/               # API客户端 (SSE)
│   │   └── utils/                  # userManager
│   └── package.json
├── knowledge_base/                 # 知识库存储（FAQ、文档等）
├── scripts/                        # 启动/部署脚本
│   ├── start_v3.sh                 # 📱 v3.0: 智能启动脚本 (382行)
│   ├── start.sh                    # v2.0: 传统启动脚本
│   └── stop.sh
├── docs/                           # 项目文档
│   ├── PROGRESS_V3.md              # 📱 v3.0: 进度跟踪
│   ├── TODO_V3.md                  # 📱 v3.0: 任务清单
│   ├── MIGRATION_V3.md             # 📱 v3.0: 迁移指南 (800+行)
│   └── CHANNELS.md                 # 📱 v3.0: 渠道开发指南 (700+行)
├── logs/                           # 运行日志
├── CLAUDE.md                       # Claude Code开发指南 (v3.0架构)
└── README.md
```

## 📚 文档

### v3.0 文档 (Latest)
- **[架构文档 (CLAUDE.md)](CLAUDE.md)** - v3.0统一多渠道架构完整说明
- **[迁移指南 (MIGRATION_V3.md)](docs/MIGRATION_V3.md)** - v2.0 → v3.0 迁移步骤(800+行)
- **[渠道开发指南 (CHANNELS.md)](docs/CHANNELS.md)** - 新增IM平台支持教程(700+行)
- **[进度跟踪 (PROGRESS_V3.md)](docs/PROGRESS_V3.md)** - Phase 1-3完成情况
- **[任务清单 (TODO_V3.md)](docs/TODO_V3.md)** - Phase 4-6待办事项

### 历史文档
- [产品需求文档 (PRD)](过程文档/智能资料库管理员-PRD.md)
- [技术方案](过程文档/智能资料库管理员-技术方案.md)
- [Phase4 验收报告](过程文档/Phase4-验收报告.md)
- 更多资料请查看 `过程文档/` 目录

## 🔧 配置说明

主要配置项在 `.env` 文件中 (详见 `.env.example`):

### 核心配置 (必需)
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| CLAUDE_API_KEY | Claude API密钥 | 必填 |
| KB_ROOT_PATH | 知识库根目录路径 | ./knowledge_base |
| SMALL_FILE_KB_THRESHOLD | 小文件阈值(KB) | 30 |
| FAQ_MAX_ENTRIES | FAQ最大条目数 | 50 |
| SESSION_TIMEOUT | 会话超时时间(秒) | 1800 |

### v3.0 多渠道配置 (可选)

**配置模式**:
- `auto` (推荐): 自动检测 - 配置了就启用，未配置就跳过
- `enabled`: 强制启用 - 未配置会报错
- `disabled`: 强制禁用 - 即使配置了也不启用

**企业微信 (WeChat Work)**:
```bash
ENABLE_WEWORK=auto              # auto | enabled | disabled
WEWORK_CORP_ID=ww...
WEWORK_CORP_SECRET=...
WEWORK_AGENT_ID=...
WEWORK_TOKEN=...
WEWORK_ENCODING_AES_KEY=...
WEWORK_PORT=8081               # 默认8081
```

**飞书 (Feishu)**:
```bash
ENABLE_FEISHU=auto
FEISHU_APP_ID=cli_...
FEISHU_APP_SECRET=...
FEISHU_VERIFICATION_TOKEN=...
FEISHU_ENCRYPT_KEY=...
FEISHU_PORT=8082
```

**其他平台**: DingTalk (8083), Slack (8084) - 参考 `.env.example`

### Employee Web UI (v3.0)
```bash
EMPLOYEE_UI_ENABLED=true        # true | false
EMPLOYEE_UI_PORT=3001           # 默认3001
```

### 其他配置
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| MAX_UPLOAD_SIZE | 最大上传文件大小(字节) | 10485760 |
| PADDLE_OCR_TOKEN | PaddleOCR API Token（处理扫描版PDF） | 可选 |
| REDIS_URL | Redis 连接 URL | redis://127.0.0.1:6379/0 |
| REDIS_PASSWORD | Redis 密码 | 必填（启用认证时） |

> 提示：仓库内置的 `backend/config/redis_secure.conf` 会为 Docker 启动的 Redis 设置强口令并绑定到本机，请确保 `.env` 中的 `REDIS_PASSWORD` 与该文件保持一致。

## 🎯 使用指南

### 1. 文档入库

- 通过Web界面上传文档（支持PDF、Word、TXT、Markdown等格式）
- 系统自动转换为Markdown格式
  - **DOCX/DOC**: 保留格式和图片
  - **PDF（电子版）**: 快速转换，保持布局
  - **PDF（扫描版）**: 自动识别并使用OCR处理
  - **图片提取**: 自动保存到独立目录
- 智能检测语义冲突
- 自动归置到合适的目录

### 2. 智能问答

- 在聊天界面输入问题
- 系统通过7阶段检索流程查找答案
- 答案附带可溯源的引用来源
- 对满意的回答可添加到FAQ

### 3. FAQ管理

- 点击"添加到FAQ"保存常见问答
- FAQ会自动管理使用次数
- 超过上限时自动清理低频条目

## 🧪 开发状态

### v1.0 (2025-10) ✅ 已完成
- [x] 单Agent架构 - 统一智能体
- [x] Web Admin UI - 文档管理和知识查询
- [x] 7阶段检索策略 + 5阶段文档入库
- [x] SSE流式响应 + Markdown渲染

### v2.0 (2025-01) ✅ 已完成
- [x] 双Agent架构 - Admin Agent + Employee Agent
- [x] 企业微信集成 - WeWork消息收发
- [x] 专家路由系统 - 自动转接领域专家
- [x] 会话状态管理 - Redis持久化 + 24h TTL
- [x] 批量员工通知 - 数据筛选 + 批量发送
- [x] 智能文档转换 - smart_convert.py (PyMuPDF + pypandoc)
- [x] 视觉工具集成 - image_read (多模态图片分析)

### v3.0 (2025-01, Current) - 71% 已完成

#### ✅ 已完成 (Phase 1-3)
- [x] **Phase 1: 渠道抽象层** (100%)
  - [x] BaseChannelAdapter 抽象基类 (443行)
  - [x] WeWork适配器重构 (client + adapter + server, 1051行)
  - [x] ChannelRouter 统一路由 (332行)

- [x] **Phase 2: Employee Web UI** (100%)
  - [x] 对话式UI界面 (ChatView + Message)
  - [x] SSE流式响应集成
  - [x] Markdown渲染 + 代码高亮
  - [x] Employee API endpoint (155行)
  - [x] 服务部署: http://localhost:3001

- [x] **Phase 3: 混合配置系统** (100%)
  - [x] ChannelConfig 配置管理器 (232行)
  - [x] 自动检测 (auto/enabled/disabled模式)
  - [x] 智能启动脚本 start_v3.sh (382行)
  - [x] 环境变量模板更新

- [x] **Phase 5: 文档与合并** (100%)
  - [x] 分支合并 (wework_integration → main)
  - [x] CLAUDE.md 更新为v3.0架构说明
  - [x] MIGRATION_V3.md 迁移指南 (800+行)
  - [x] CHANNELS.md 渠道开发指南 (700+行)
  - [x] README.md 更新

#### 🚧 进行中/待实施
- [ ] **Phase 4: 飞书适配器** (可选)
  - [ ] 创建 backend/channels/feishu/
  - [ ] 验证多渠道架构可扩展性

- [ ] **Phase 6: 测试与部署** (待开始)
  - [ ] 单元测试 (渠道适配器、配置系统)
  - [ ] 集成测试 (端到端、跨渠道)
  - [ ] Docker Compose 配置
  - [ ] Nginx反向代理
  - [ ] 性能优化和监控

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 👥 作者

- 开发者: [@Harryoung](https://github.com/Harryoung)
- 项目时间: 2025 年 10 月

## 📞 支持

如有问题，请提交 [Issue](https://github.com/Harryoung/intelligent-kba/issues)

---

**注意**: 本项目基于 Claude Agent SDK 开发，需要有效的 Claude API Key 才能运行。
