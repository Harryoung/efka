# 智能资料库管理员 (Intelligent Knowledge Base Administrator)

*Intelligent Knowledge Base Administrator, without embedding based search. Maybe slower, but result is much more reliable!*

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/Harryoung/intelligent-kba)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

基于 Claude Agent SDK 开发的智能知识库管理系统（单一Agent架构），提供精准的资料查询和智能化的文档管理能力。

## 🌟 核心特性

- **🤖 智能问答**: 多阶段检索策略，精准回答，可溯源无捏造
- **⚡ FAQ机制**: 常见问题快速响应，持续学习优化
- **📁 智能入库**: 自动格式转换，语义冲突检测，智能文件归置
- **🗂️ 结构维护**: 自动维护知识库结构，保持组织有序
- **💬 Web界面**: 简洁直观的聊天式交互体验

## 🏗️ 技术栈

- **后端**: Python 3.10+ / FastAPI / Claude Agent SDK / WebSocket / Redis
- **前端**: React 18 / Vite / Marked (Markdown渲染)
- **部署**: Docker（规划中的容器化脚本）
- **AI**: Claude Sonnet 4.5 (通过Agent SDK)

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

### 方式一：使用启动脚本（推荐）

```bash
git clone https://github.com/Harryoung/intelligent-kba.git
cd intelligent-kba
cp .env.example .env              # 配置 Claude / Redis 环境变量
./scripts/start.sh                # 启动后端 + 前端，日志输出到 logs/
```

浏览器访问 http://localhost:3000，如需停止可运行 `./scripts/stop.sh`。

### 方式二：手动本地开发环境

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

### 方式三：Docker部署

容器化部署脚本正在完善中，当前 `scripts/deploy.sh` 为占位文件。后续版本将补充 docker-compose 与一键部署能力，欢迎关注仓库更新。

## 📖 项目结构

```
intelligent-kba/
├── backend/                    # 后端服务
│   ├── agents/                 # Agent 定义
│   ├── api/                    # FastAPI 路由
│   ├── config/                 # 配置（包含 redis_secure.conf）
│   ├── services/               # 业务服务层
│   ├── storage/                # Redis 等存储实现
│   ├── utils/                  # 工具函数
│   ├── main.py                 # 应用入口
│   └── requirements.txt
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── components/         # React 组件
│   │   ├── services/           # API Hooks
│   │   ├── utils/              # 工具方法
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
├── knowledge_base/             # 知识库存储（FAQ、文档等）
├── scripts/                    # 启动/部署脚本
├── docs/                       # 项目文档
├── logs/                       # 运行日志（启动脚本生成）
└── README.md
```

## 📚 文档

- [产品需求文档 (PRD)](过程文档/智能资料库管理员-PRD.md)
- [技术方案](过程文档/智能资料库管理员-技术方案.md)
- [Phase4 验收报告](过程文档/Phase4-验收报告.md)
- 更多资料请查看 `过程文档/` 目录

## 🔧 配置说明

主要配置项在 `.env` 文件中：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| CLAUDE_API_KEY | Claude API密钥 | 必填 |
| KB_ROOT_PATH | 知识库根目录路径 | ./knowledge_base |
| SMALL_FILE_KB_THRESHOLD | 小文件阈值(KB) | 30 |
| FAQ_MAX_ENTRIES | FAQ最大条目数 | 50 |
| SESSION_TIMEOUT | 会话超时时间(秒) | 1800 |
| MAX_UPLOAD_SIZE | 最大上传文件大小(字节) | 10485760 |
| PADDLE_OCR_TOKEN | PaddleOCR API Token（处理扫描版PDF） | 可选 |
| REDIS_URL | Redis 连接 URL | redis://127.0.0.1:6379/0 |
| REDIS_USERNAME | Redis ACL 用户名 | (可选) |
| REDIS_PASSWORD | Redis 密码 | 必填（启用认证时） |
| ALLOWED_ORIGINS | CORS 白名单（JSON 数组字符串） | ["http://localhost:3000","http://localhost"] |

> 提示：仓库内置的 `backend/config/redis_secure.conf` 会为 Docker 启动的 Redis 设置强口令并绑定到本机，请确保 `.env` 中的 `REDIS_PASSWORD` 与该文件保持一致，或同步修改后重新启动容器。

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

### Phase 1: 项目初始化 ✅ 已完成
- [x] 项目结构创建
- [x] 后端配置文件
- [x] 前端基础配置
- [x] 知识库初始化
- [x] 环境变量模板

### Phase 2: Agent 定义与实现 ✅ 已完成
- [x] 统一智能体实现（整合知识问答、文档管理、知识库维护）
- [x] 7阶段检索策略实现
- [x] 5阶段文档入库流程实现
- [x] 权限管理系统
- [x] 会话管理器

### 架构优化 ✅ 已完成
- [x] 重构为单一Agent架构（消除子Agent调用开销）
- [x] 简化代码结构（从3个Agent合并为1个）
- [x] 性能提升 20-30%

### Phase 3: 后端 API 路由 ✅ 已完成
- [x] 智能问答接口（/api/query）
- [x] SSE 流式响应（/api/query/stream）
- [x] 文件上传接口（/api/upload）
- [x] 会话管理接口
- [x] FastAPI 主应用配置

### Phase 4: 前端实现 ✅ 已完成
- [x] ChatView 主界面组件
- [x] Message 消息组件
- [x] FileUpload 文件上传组件
- [x] SSE 流式响应集成
- [x] Markdown 渲染
- [x] 响应式设计

### 待实施功能
- [ ] 集成测试和端到端测试
- [ ] Docker 容器化部署
- [ ] 性能优化和监控
- [ ] 多渠道接入（企业微信等）

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
