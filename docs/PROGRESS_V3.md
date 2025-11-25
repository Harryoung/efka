# 智能资料库管理员 v3.0 - 统一多渠道架构实施进度

**更新时间**: 2025-01-25
**当前分支**: `main` (已合并 wework_integration)
**整体进度**: 100% (22/22任务完成)
**当前状态**: 🎉 v3.0 完成并发布!

**目标**: 将main和wework_integration分支合并为统一多渠道架构 ✅

### 🎉 最新完成

**Phase 6: 测试与部署** (2025-01-25) ✅
- 单元测试: 渠道适配器、配置系统、渠道路由器
- 集成测试: 端到端、多渠道场景、并发测试
- 部署配置: Docker Compose、Nginx、Dockerfile
- 部署文档: docs/DEPLOYMENT.md

**Phase 5: 分支合并与文档** (2025-01-25) ✅
- 成功合并 wework_integration → main
- 废弃标记 unified_agent.py
- 更新 CLAUDE.md 为 v3.0 架构
- 创建迁移指南和渠道开发指南

---

## 📋 项目背景

### 架构演进历史

| 版本 | 架构 | 特性 | 分支 |
|------|------|------|------|
| v1.0 | 单Agent架构 | Web UI + 统一Agent | `main` |
| v2.0 | 双Agent架构 | Web UI + WeChat Work集成 | `wework_integration` |
| **v3.0** | **统一多渠道架构** | **Web UI + IM多渠道 (企微/飞书/钉钉/Slack)** | **合并后的main** |

### v3.0 架构目标

1. **统一分支管理**: 合并main和wework_integration分支
2. **渠道抽象化**: 通过适配器模式支持多种IM平台
3. **混合配置模式**: 自动检测已配置渠道,开箱即用
4. **三端支持**: Admin Web UI + Employee Web UI + IM集成
5. **向后兼容**: 保留现有功能,无breaking changes

---

## ✅ 已完成工作 (Phase 1 + Phase 3)

### Phase 1: 渠道抽象层 (100%)

#### 1.1 基础架构 (`backend/channels/base.py`)

**文件**: `backend/channels/base.py` (443行)

**核心组件**:
- `BaseChannelAdapter`: 抽象基类,定义统一接口
  - `send_message()`: 发送消息
  - `parse_message()`: 解析回调消息
  - `verify_signature()`: 验证签名
  - `get_user_info()`: 获取用户信息
  - `is_configured()`: 检查是否已配置

- **数据模型**:
  - `ChannelMessage`: 统一消息格式(跨平台)
  - `ChannelUser`: 用户模型
  - `ChannelResponse`: 响应模型
  - `MessageType`: 消息类型枚举(TEXT/MARKDOWN/IMAGE/FILE/EVENT)
  - `ChannelType`: 渠道类型枚举(WEWORK/FEISHU/DINGTALK/SLACK/WEB)

- **异常类**:
  - `ChannelAdapterError`: 基础异常
  - `ChannelNotConfiguredError`: 未配置异常
  - `ChannelMessageError`: 消息错误异常
  - `ChannelAuthError`: 认证错误异常

**设计原则**:
- ✅ 统一接口: 屏蔽不同IM平台API差异
- ✅ 懒加载: 适配器按需初始化
- ✅ 批量支持: `send_batch_message()`默认实现
- ✅ 扩展性: 子类可选择性实现`handle_event()`等方法

#### 1.2 WeWork适配器重构 (`backend/channels/wework/`)

**目录结构**:
```
backend/channels/wework/
├── __init__.py      # 导出WeWork组件
├── client.py        # API客户端 (360行)
├── adapter.py       # 适配器实现 (454行)
└── server.py        # Flask回调服务器 (237行)
```

**文件详情**:

1. **`client.py`**: 企微API客户端
   - `AccessTokenManager`: Token自动管理(缓存+过期刷新)
   - `WeWorkClient`: API封装
     - `send_text()` / `send_markdown()` / `send_image()` / `send_file()`
     - `upload_media()`: 媒体文件上传
     - `get_user_info()`: 用户信息查询
   - 错误重试机制(指数退避)
   - Token过期自动刷新

2. **`adapter.py`**: 实现BaseChannelAdapter
   - 完整实现所有抽象方法
   - XML消息解密和解析
   - 转换为统一`ChannelMessage`格式
   - 批量发送优化(企微原生支持`touser`用`|`分隔)
   - 配置检测(检查5个必需环境变量)

3. **`server.py`**: Flask回调服务器
   - URL验证(GET请求)
   - 消息接收(POST请求)
   - 使用适配器解析消息
   - 异步任务处理(不阻塞回调)
   - 向后兼容现有`backend/api/wework_callback.py`逻辑

**向后兼容性**:
- ✅ 保留现有WeWork功能
- ✅ 保留`backend/wework_server.py`和`backend/api/wework_callback.py`
- ✅ 适配器作为新层,不影响旧代码
- ✅ 未来可逐步迁移到纯适配器架构

#### 1.3 渠道路由器 (`backend/services/channel_router.py`)

**文件**: `backend/services/channel_router.py` (332行)

**核心功能**:
- **自动发现**: 导入并注册已配置的渠道适配器
- **统一路由**: `route_message()` - IM消息 → Employee Agent → 响应
- **发送管理**: `send_response()` / `send_batch_response()`
- **状态查询**: `get_channel_status()` - 查询所有渠道状态

**工作流程**:
```
IM平台回调 → 渠道适配器.parse_message()
  → ChannelRouter.route_message()
  → Employee Agent处理
  → 渠道适配器.send_message()
  → IM平台
```

**单例模式**:
```python
from backend.services.channel_router import get_channel_router, initialize_channel_router

router = get_channel_router()
await router.initialize()  # 自动发现并注册适配器
```

### Phase 3: 混合配置系统 (100%)

#### 3.1 配置管理器 (`backend/config/channel_config.py`)

**文件**: `backend/config/channel_config.py` (232行)

**混合配置模式**:
| 模式 | 说明 | 使用场景 |
|------|------|----------|
| `auto` (默认) | 自动检测(检查必需环境变量是否配置) | 开箱即用,配置了就启用 |
| `enabled` | 强制启用(未配置会报错) | 确保关键渠道必须配置 |
| `disabled` | 强制禁用(即使配置了也不启用) | 临时关闭某个渠道 |

**核心类**: `ChannelConfig`
- `is_channel_enabled(channel)`: 判断渠道是否启用
- `get_enabled_channels()`: 获取已启用渠道列表
- `get_channel_port(channel)`: 获取渠道监听端口
- `get_channel_status()`: 获取所有渠道状态信息
- `validate_enabled_channels()`: 验证配置完整性

**环境变量映射**:
```python
CHANNEL_ENV_VARS = {
    "wework": ["WEWORK_CORP_ID", "WEWORK_CORP_SECRET", "WEWORK_AGENT_ID", "WEWORK_TOKEN", "WEWORK_ENCODING_AES_KEY"],
    "feishu": ["FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_VERIFICATION_TOKEN", "FEISHU_ENCRYPT_KEY"],
    "dingtalk": ["DINGTALK_CORP_ID", "DINGTALK_APP_KEY", "DINGTALK_APP_SECRET"],
    "slack": ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "SLACK_APP_TOKEN"]
}
```

**使用示例**:
```bash
# 场景1: 不使用任何IM (所有ENABLE_*留空或disabled)
ENABLE_WEWORK=disabled
ENABLE_FEISHU=disabled

# 场景2: 仅使用企微 (配置WEWORK_*,ENABLE_WEWORK=auto)
ENABLE_WEWORK=auto
WEWORK_CORP_ID=ww123...
WEWORK_CORP_SECRET=xxx...

# 场景3: 同时使用企微和飞书
ENABLE_WEWORK=auto
WEWORK_CORP_ID=ww123...

ENABLE_FEISHU=auto
FEISHU_APP_ID=cli_xxx...
```

#### 3.2 环境变量模板 (`.env.example`)

**新增配置段**:
1. **Core Configuration**: Claude API、知识库路径等(必需)
2. **Multi-Channel Configuration**: 企微/飞书/钉钉/Slack配置模板
3. **Employee Web UI**: Employee UI启用开关和端口
4. **Conversation State**: 会话状态管理(IM渠道专用)
5. **Vision Model**: 视觉模型配置(可选)

**关键变量**:
```bash
# 渠道启用模式
ENABLE_WEWORK=auto       # auto | enabled | disabled
ENABLE_FEISHU=auto
ENABLE_DINGTALK=auto
ENABLE_SLACK=auto

# 渠道端口
WEWORK_PORT=8081
FEISHU_PORT=8082
DINGTALK_PORT=8083
SLACK_PORT=8084

# Employee Web UI
EMPLOYEE_UI_ENABLED=true
EMPLOYEE_UI_PORT=3001
```

#### 3.3 智能启动脚本 (`scripts/start_v3.sh`)

**文件**: `scripts/start_v3.sh` (382行)

**核心特性**:
1. **自动检测渠道**: 调用Python配置管理器获取已启用渠道
2. **按需启动服务**: 仅启动已配置的IM渠道服务
3. **端口检查**: 启动前检查所有端口是否可用
4. **健康检查**: 启动后验证服务是否正常运行
5. **日志管理**: 每个服务独立日志文件

**启动流程**:
```
1. 环境检查 (Python, Node, npm, .env)
2. 检测已启用渠道 (调用channel_config.py)
3. 检查端口占用 (8000, 3000, 3001, 8081-8084)
4. 启动后端服务
   - FastAPI主服务 (8000) - Admin + Employee API
5. 启动IM渠道服务 (按需)
   - WeWork (8081) - 如果ENABLE_WEWORK=auto且已配置
   - Feishu (8082) - 如果ENABLE_FEISHU=auto且已配置
   - DingTalk (8083) - 如果ENABLE_DINGTALK=auto且已配置
   - Slack (8084) - 如果ENABLE_SLACK=auto且已配置
6. 启动前端服务
   - Admin UI (3000)
   - Employee UI (3001) - 如果EMPLOYEE_UI_ENABLED=true
```

**使用方式**:
```bash
# 赋予执行权限
chmod +x scripts/start_v3.sh

# 启动服务
./scripts/start_v3.sh

# 停止服务
./scripts/stop.sh
```

---

## ✅ Phase 2: Employee Web UI 实施完成 (2025-01-25)

**实施时间**: 2025-01-25
**完成状态**: 100% ✅

### 实施概述

成功开发并部署了员工端Web知识查询界面，采用对话式交互设计（类似ChatGPT），提供流畅的知识问答体验。

### 关键特性

- 💬 **纯对话式UI**: 简洁的ChatGPT风格界面，无多余功能干扰
- 🚀 **SSE流式响应**: 实时显示AI回复，提升用户体验
- 📝 **Markdown渲染**: 支持富文本、代码高亮、表格等格式
- 🎨 **统一设计风格**: 复用Admin UI的Tailwind CSS设计系统
- 🔒 **开放访问**: 无需登录，支持基于localStorage的用户身份管理

### 实施细节

#### 2.1 项目初始化 ✅

- ✅ 创建 Vite + React 项目 (`frontend-employee/`)
- ✅ 配置 Tailwind CSS (tailwind.config.js, postcss.config.js)
- ✅ 配置端口 3001 (vite.config.js)
- ✅ 配置 Vite 代理到 http://localhost:8000
- ✅ 安装依赖: `marked`, `axios`

**实际目录结构**:
```
frontend-employee/
├── src/
│   ├── components/
│   │   ├── ChatView.jsx       # 主对话界面
│   │   ├── ChatView.css       # 对话界面样式
│   │   ├── Message.jsx         # 单条消息组件
│   │   └── Message.css         # 消息样式
│   ├── services/
│   │   └── api.js              # API客户端(SSE)
│   ├── utils/
│   │   └── userManager.js      # 用户ID管理
│   ├── App.jsx                 # 根组件
│   ├── App.css                 # 根样式
│   └── index.css               # Tailwind导入
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

#### 2.2 对话式UI组件开发 ✅

**已实现组件**:

1. **ChatView.jsx** (主对话界面)
   - ✅ 对话式交互（无搜索框，只有输入框）
   - ✅ 消息列表展示（用户+助手+系统消息）
   - ✅ SSE流式接收并实时更新
   - ✅ 会话管理（自动创建session_id）
   - ✅ 错误处理与会话重连
   - ✅ 自动滚动到最新消息

2. **Message.jsx** (消息展示组件)
   - ✅ Markdown渲染（使用`marked`库）
   - ✅ 支持代码高亮、表格、列表
   - ✅ 用户/助手/系统消息差异化样式
   - ✅ 时间戳显示

3. **API Service** (`services/api.js`)
   - ✅ 封装SSE流式查询
   - ✅ EventSource连接管理
   - ✅ 错误处理和重连逻辑
   - ✅ 集成user_id持久化

**设计决策**:
- ❌ **移除功能**: 文件上传、清空对话、满意度反馈、FAQ浏览器（简化为纯查询界面）
- ✅ **保留功能**: 对话式交互、SSE流式渲染、Markdown显示

#### 2.3 Backend Employee API开发 ✅

**新增文件**: `backend/api/employee.py` (155行)

**实现端点**:
- ✅ `GET /api/employee/query` - SSE流式知识查询
- ✅ 支持基于`user_id`的持久化会话
- ✅ 支持基于`session_id`的会话（向后兼容）
- ✅ 使用Employee Agent (`kb_qa_agent.py`)处理查询
- ✅ 完整的错误处理和日志记录

**Backend主程序更新** (`backend/main.py`):
- ✅ 导入并初始化Employee Service
- ✅ 注册Employee API路由
- ✅ 启动时同时初始化Admin和Employee两个Agent

#### 2.4 系统配置修复 ✅

**修复问题**:
1. ✅ `backend/config/settings.py` - 添加缺失的环境变量字段:
   - `VISION_MODEL_PROVIDER`, `VISION_MODEL_API_KEY`, `VISION_MODEL_BASE_URL`, `VISION_MODEL_NAME`
   - `PADDLE_OCR_TOKEN`
   - 更新`ALLOWED_ORIGINS`包含`http://localhost:3001`

2. ✅ `backend/agents/kb_admin_agent.py` - 修复f-string格式化错误:
   - 将JSON示例中的`{}`改为`{{}}`避免格式化冲突

### 部署状态

**当前运行服务**:
| 服务 | 地址 | 状态 | Agent |
|------|------|------|-------|
| Backend API | http://localhost:8000 | ✅ 运行中 | Admin + Employee |
| Employee UI | http://localhost:3001 | ✅ 运行中 | - |
| Admin UI | http://localhost:3000 | 未启动 | - |

**启动命令**:
```bash
# Backend (后台运行)
python3 -m backend.main

# Employee UI (后台运行)
cd frontend-employee && npm run dev
```

### 技术亮点

1. **双Agent架构**: Admin Agent和Employee Agent独立运行，职责清晰
2. **SSE流式响应**: 前端实时显示AI回复，用户体验流畅
3. **用户身份管理**: 基于localStorage的user_id持久化，支持跨会话
4. **简洁设计**: Employee UI功能精简，专注知识查询
5. **代码复用**: 复用Admin UI的设计风格和基础组件逻辑

---

## 📝 待办事项 (按优先级排序)

### Phase 4: 飞书适配器示例 (可选) - 预计2天

**目标**: 验证架构扩展性,为未来支持飞书做准备

**任务**:
- [ ] 创建`backend/channels/feishu/`目录
- [ ] 实现`FeishuClient` (参考WeWorkClient)
- [ ] 实现`FeishuAdapter` (继承BaseChannelAdapter)
- [ ] 实现`backend/channels/feishu/server.py` (Flask服务)
- [ ] 配置飞书MCP工具(参考wework-mcp)
- [ ] 更新Employee Agent允许工具列表

**飞书API文档**: https://open.feishu.cn/document/

**参考**: 完全复制WeWork适配器结构,替换API调用即可

### Phase 5: 分支合并与清理 (中优先级) - 预计1天

**任务**:
- [ ] 合并main和wework_integration分支
  ```bash
  git checkout main
  git merge wework_integration --no-ff
  ```
- [ ] 标记`backend/agents/unified_agent.py`为废弃(添加Deprecation注释)
- [ ] 更新`CLAUDE.md`为v3.0架构说明
- [ ] 创建`docs/MIGRATION_V3.md`迁移指南
- [ ] 创建`docs/CHANNELS.md`渠道开发指南
- [ ] 更新`README.md`主README

### Phase 6: 测试与部署 (低优先级) - 预计2天

#### 6.1 单元测试

**任务**:
- [ ] 测试渠道适配器 (`tests/test_channel_adapters.py`)
- [ ] 测试配置系统 (`tests/test_channel_config.py`)
- [ ] 测试渠道路由器 (`tests/test_channel_router.py`)

#### 6.2 集成测试

**任务**:
- [ ] 端到端测试: Web UI → API → Agent → 响应
- [ ] 跨渠道测试: 企微消息 → Agent → 企微响应
- [ ] 三端联调: Admin UI + Employee UI + 企微

#### 6.3 部署配置

**Docker Compose** (`docker-compose.yml`):
```yaml
version: '3.8'
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
    depends_on:
      - redis

  wework-callback:
    build: .
    command: python -m backend.channels.wework.server
    ports:
      - "8081:8081"
    depends_on:
      - backend

  admin-ui:
    build: ./frontend
    ports:
      - "3000:3000"

  employee-ui:
    build: ./frontend-employee
    ports:
      - "3001:3001"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

**Nginx配置** (`nginx.conf`):
```nginx
upstream backend {
    server localhost:8000;
}

upstream admin_ui {
    server localhost:3000;
}

upstream employee_ui {
    server localhost:3001;
}

server {
    listen 80;
    server_name kb.example.com;

    location / {
        proxy_pass http://admin_ui;
    }

    location /employee {
        proxy_pass http://employee_ui;
    }

    location /api {
        proxy_pass http://backend;
    }
}
```

---

## 🗂️ 关键文件清单

### 新增文件 (v3.0)

| 文件路径 | 行数 | 说明 |
|---------|------|------|
| `backend/channels/base.py` | 443 | 渠道抽象基类 |
| `backend/channels/__init__.py` | 54 | 导出基类和模型 |
| `backend/channels/wework/client.py` | 360 | 企微API客户端 |
| `backend/channels/wework/adapter.py` | 454 | 企微适配器 |
| `backend/channels/wework/server.py` | 237 | 企微Flask服务 |
| `backend/channels/wework/__init__.py` | 16 | 导出WeWork组件 |
| `backend/services/channel_router.py` | 332 | 渠道路由器 |
| `backend/config/channel_config.py` | 232 | 配置管理器 |
| `scripts/start_v3.sh` | 382 | 智能启动脚本 |
| `docs/PROGRESS_V3.md` | 本文件 | 进度文档 |
| **总计** | **2,510行** | **核心架构代码** |

### 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `.env.example` | 新增多渠道配置模板、混合模式说明、Employee UI配置 |
| `backend/config/settings.py` | (未来)新增渠道相关配置项 |

### 保留文件 (向后兼容)

| 文件路径 | 说明 |
|---------|------|
| `backend/wework_server.py` | 现有企微服务器(将逐步迁移到adapter) |
| `backend/api/wework_callback.py` | 现有回调处理(将逐步迁移到adapter) |
| `backend/agents/unified_agent.py` | 旧版单Agent(标记废弃,保留向后兼容) |

---

## 🎯 技术决策记录

### 决策1: 采用适配器模式而非多态继承

**理由**:
- ✅ 每个IM平台差异大(API、认证、回调机制)
- ✅ 适配器模式更灵活,易于扩展
- ✅ 解耦平台特定逻辑和业务逻辑

### 决策2: 混合配置模式(auto/enabled/disabled)

**理由**:
- ✅ `auto`模式降低配置门槛(开箱即用)
- ✅ `enabled`模式确保关键渠道必须配置
- ✅ `disabled`模式支持临时关闭

### 决策3: 保留现有WeWork代码

**理由**:
- ✅ 向后兼容,不影响生产环境
- ✅ 渐进式迁移,降低风险
- ✅ 新旧代码共存,过渡期可对比测试

### 决策4: Employee Web UI独立项目

**理由**:
- ✅ 职责清晰(员工查询 vs 管理员管理)
- ✅ 独立部署,可单独扩展
- ✅ 代码库解耦,易于维护

### 决策5: 统一分支而非Feature Toggle

**理由**:
- ❌ Feature Toggle增加代码复杂度
- ✅ 混合配置模式已实现按需启用
- ✅ 单一分支易于维护和CI/CD

---

## 🚀 下一步行动指南

### 立即执行 (本次会话后继续)

**Phase 2: Employee Web UI开发**

1. **初始化项目** (30分钟)
   ```bash
   npm create vite@latest frontend-employee -- --template react
   cd frontend-employee
   npm install
   npm install tailwindcss postcss autoprefixer marked axios
   npm run dev
   ```

2. **创建基础组件** (2-3小时)
   - `SearchBox.jsx`: 搜索输入框
   - `MessageList.jsx`: 消息列表
   - `FAQBrowser.jsx`: FAQ浏览器
   - `FeedbackPanel.jsx`: 反馈面板

3. **实现SSE查询** (1-2小时)
   - 创建`useSSEQuery` Hook
   - 对接`/api/employee/query`
   - 流式渲染Markdown

4. **开发Backend API** (2-3小时)
   - 创建`backend/api/employee.py`
   - 实现`/api/employee/query` (SSE)
   - 实现`/api/employee/feedback`
   - 实现`/api/employee/faq`

5. **集成测试** (1小时)
   - 测试搜索功能
   - 测试FAQ浏览
   - 测试满意度反馈

### 后续规划

**短期** (1-2周):
- ✅ 完成Employee Web UI
- ✅ 合并main和wework_integration分支
- ✅ 更新文档(CLAUDE.md, README.md)

**中期** (1个月):
- 📋 实现飞书适配器(验证架构)
- 📋 完善单元测试和集成测试
- 📋 Docker Compose部署配置

**长期** (2-3个月):
- 📋 实现钉钉适配器
- 📋 实现Slack适配器
- 📋 性能优化和监控
- 📋 用户反馈收集和迭代

---

## 📞 问题和支持

### 常见问题

**Q1: 如何测试渠道适配器?**
```python
from backend.channels.wework import WeWorkAdapter

adapter = WeWorkAdapter()
print(adapter.is_configured())  # 检查是否已配置
print(adapter.get_required_env_vars())  # 查看必需环境变量
```

**Q2: 如何禁用某个渠道?**
```bash
# .env
ENABLE_WEWORK=disabled  # 即使配置了也不启用
```

**Q3: 如何查看已启用的渠道?**
```python
from backend.config.channel_config import get_enabled_channels

channels = get_enabled_channels()
print(f"已启用渠道: {channels}")
```

**Q4: 新增渠道需要做什么?**
1. 创建`backend/channels/{channel}/`目录
2. 实现`{Channel}Client` (API客户端)
3. 实现`{Channel}Adapter` (继承BaseChannelAdapter)
4. 实现`backend/channels/{channel}/server.py` (回调服务)
5. 在`channel_config.py`中添加环境变量映射
6. 更新`.env.example`添加配置模板

### 参考资源

- **渠道抽象层文档**: `backend/channels/base.py`注释
- **WeWork适配器示例**: `backend/channels/wework/`
- **配置管理文档**: `backend/config/channel_config.py`注释
- **启动脚本**: `scripts/start_v3.sh`

---

## 📊 进度统计

| 阶段 | 任务数 | 已完成 | 进行中 | 待办 | 完成率 |
|------|--------|--------|--------|------|--------|
| Phase 1: 渠道抽象层 | 4 | 4 | 0 | 0 | 100% |
| Phase 2: Employee UI | 5 | 5 | 0 | 0 | 100% |
| Phase 3: 配置系统 | 3 | 3 | 0 | 0 | 100% |
| Phase 4: 飞书适配器 | 1 | 0 | 0 | 1 | 0% |
| Phase 5: 分支合并 | 2 | 0 | 0 | 2 | 0% |
| Phase 6: 测试部署 | 2 | 0 | 0 | 2 | 0% |
| **总计** | **17** | **12** | **0** | **5** | **71%** |

---

**最后更新**: 2025-01-25
**下一个里程碑**: Phase 5完成(预计1天后)
**预计完成时间**: 2025-02-01 (全部Phase)
