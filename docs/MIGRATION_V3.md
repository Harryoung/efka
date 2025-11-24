# Migration Guide: v2.0 → v3.0

**目标**: 从 v2.0 双Agent架构 迁移到 v3.0 统一多渠道架构

**迁移时间**: 30-60分钟（取决于现有配置复杂度）

**向后兼容性**: ✅ **100% 向后兼容** - v2.0代码完全保留，v3.0为增量升级

---

## 目录

1. [架构变化概述](#架构变化概述)
2. [迁移前准备](#迁移前准备)
3. [步骤1: 更新代码库](#步骤1-更新代码库)
4. [步骤2: 配置环境变量](#步骤2-配置环境变量)
5. [步骤3: 更新启动脚本](#步骤3-更新启动脚本)
6. [步骤4: 验证部署](#步骤4-验证部署)
7. [可选: 启用新功能](#可选-启用新功能)
8. [回滚计划](#回滚计划)
9. [常见问题](#常见问题)

---

## 架构变化概述

### v2.0 架构 (Current)
```
┌─────────────────────────────────┐
│  FastAPI (8000)  Flask (8081)   │
│  ┌──────────┐  ┌──────────────┐ │
│  │  Admin   │  │  Employee    │ │
│  │  Agent   │  │  Agent       │ │
│  │  (Web)   │  │  (WeWork)    │ │
│  └──────────┘  └──────────────┘ │
└─────────────────────────────────┘
```

### v3.0 架构 (Target)
```
┌───────────────────────────────────────────────┐
│  Frontend Layer                               │
│  Admin UI | Employee UI | IM Platforms        │
│  (3000)   | (3001)      | (WeWork/Feishu)    │
├───────────────────────────────────────────────┤
│  Backend Layer (FastAPI 8000)                 │
│  Admin Agent | Employee Agent                 │
├───────────────────────────────────────────────┤
│  Channel Layer                                │
│  ChannelRouter + BaseChannelAdapter           │
│  WeWork (8081) | Feishu (8082) | ...         │
└───────────────────────────────────────────────┘
```

### 关键差异

| 特性 | v2.0 | v3.0 | 影响 |
|------|------|------|------|
| **Admin接口** | Web UI (3000) | Web UI (3000) | 无变化 |
| **Employee接口** | WeWork only | Web UI (3001) + 多IM平台 | **新增** |
| **IM平台支持** | WeWork (hardcoded) | WeWork/Feishu/DingTalk/Slack (pluggable) | **扩展** |
| **配置方式** | 手动配置 | 自动检测 (auto/enabled/disabled) | **简化** |
| **启动脚本** | `start.sh` | `start_v3.sh` (自动检测渠道) | **增强** |
| **代码结构** | 无渠道抽象 | Channel Adapter模式 | **新增** |

---

## 迁移前准备

### 1. 备份

```bash
# 备份当前配置
cp .env .env.backup.$(date +%Y%m%d)

# 备份数据库 (如果使用Redis持久化)
# 注意: Redis默认使用内存，无需备份
```

### 2. 检查当前版本

```bash
# 查看当前分支
git branch --show-current
# 应显示: main 或 wework_integration

# 查看最新提交
git log --oneline -5

# 查看CLAUDE.md版本信息
tail -10 CLAUDE.md
```

### 3. 确认依赖版本

```bash
# Python版本 (需要 >= 3.9)
python3 --version

# Node版本 (需要 >= 16)
node --version

# Redis版本 (可选，推荐 >= 7.0)
redis-cli --version
```

---

## 步骤1: 更新代码库

### 1.1 拉取最新代码

```bash
# 如果在wework_integration分支
git checkout main
git pull origin main

# 或者直接克隆最新main分支
git clone <repository_url>
cd intelligent_kba
```

### 1.2 安装新依赖

**Backend依赖更新**:
```bash
pip3 install -r backend/requirements.txt
```

**关键依赖变化**:
- ❌ **移除**: `markitdown-mcp==0.0.1a4` (外部MCP服务器)
- ✅ **新增**: `PyMuPDF>=1.24.2`, `pymupdf4llm>=0.0.5`, `pypandoc>=1.13` (smart_convert.py需要)

**Frontend依赖** (如果要启用Employee UI):
```bash
cd frontend-employee
npm install
cd ..
```

### 1.3 验证代码结构

```bash
# 检查新增的v3.0文件
ls -lh backend/channels/
ls -lh backend/config/channel_config.py
ls -lh backend/api/employee.py
ls -lh scripts/start_v3.sh
ls -lh frontend-employee/
```

---

## 步骤2: 配置环境变量

### 2.1 更新.env文件

**复制模板**:
```bash
# 如果没有.env文件
cp .env.example .env
```

**v3.0新增配置项**:
```bash
# ============================================
# Multi-Channel Configuration (v3.0)
# ============================================

# WeChat Work (企业微信)
ENABLE_WEWORK=auto                    # auto | enabled | disabled
WEWORK_CORP_ID=your_corp_id
WEWORK_CORP_SECRET=your_corp_secret
WEWORK_AGENT_ID=your_agent_id
WEWORK_TOKEN=your_token
WEWORK_ENCODING_AES_KEY=your_aes_key
WEWORK_PORT=8081                      # 可选，默认8081

# Feishu (飞书) - 可选
ENABLE_FEISHU=auto                    # auto | enabled | disabled
# FEISHU_APP_ID=
# FEISHU_APP_SECRET=
# FEISHU_VERIFICATION_TOKEN=
# FEISHU_ENCRYPT_KEY=
# FEISHU_PORT=8082

# DingTalk (钉钉) - 可选
ENABLE_DINGTALK=auto
# DINGTALK_CORP_ID=
# DINGTALK_APP_KEY=
# DINGTALK_APP_SECRET=
# DINGTALK_PORT=8083

# Slack - 可选
ENABLE_SLACK=auto
# SLACK_BOT_TOKEN=
# SLACK_SIGNING_SECRET=
# SLACK_APP_TOKEN=
# SLACK_PORT=8084

# ============================================
# Employee Web UI (v3.0)
# ============================================
EMPLOYEE_UI_ENABLED=true              # true | false
EMPLOYEE_UI_PORT=3001                 # 默认3001
```

### 2.2 配置模式说明

**`auto` 模式 (推荐)**:
- 如果环境变量已配置 → 自动启用该渠道
- 如果环境变量未配置 → 自动跳过该渠道
- **零配置开销**: 配置了就启用，没配置就不启用

**`enabled` 模式**:
- 强制启用该渠道
- 如果环境变量未配置 → **启动失败并报错**
- **适用场景**: 关键渠道必须启用

**`disabled` 模式**:
- 强制禁用该渠道
- 即使环境变量已配置也不启用
- **适用场景**: 临时关闭某个渠道

**示例配置**:
```bash
# 场景1: 仅使用Web UI (不使用任何IM平台)
ENABLE_WEWORK=disabled
ENABLE_FEISHU=disabled
ENABLE_DINGTALK=disabled
ENABLE_SLACK=disabled

# 场景2: 仅使用企微 (auto模式，配置了就启用)
ENABLE_WEWORK=auto
WEWORK_CORP_ID=ww123...
WEWORK_CORP_SECRET=xxx...
# 其他渠道不配置，自动跳过

# 场景3: 同时使用企微和飞书
ENABLE_WEWORK=auto
WEWORK_CORP_ID=ww123...
# ... (其他企微配置)

ENABLE_FEISHU=auto
FEISHU_APP_ID=cli_xxx...
# ... (其他飞书配置)
```

### 2.3 检查配置

```bash
# 检查配置的渠道
python -c "
from backend.config.channel_config import get_channel_config
config = get_channel_config()
print('已启用渠道:', config.get_enabled_channels())
print('渠道状态:')
for channel, status in config.get_channel_status().items():
    print(f'  {channel}: {status}')
"
```

---

## 步骤3: 更新启动脚本

### 3.1 使用v3.0启动脚本

**赋予执行权限**:
```bash
chmod +x scripts/start_v3.sh
```

**启动服务**:
```bash
./scripts/start_v3.sh
```

**启动过程说明**:
```
1. 环境检查 (Python, Node, npm, .env)
2. 渠道检测 (调用channel_config.py)
   ✅ 检测到: wework
   ⏭️  跳过: feishu, dingtalk, slack (未配置)
3. 端口检查 (8000, 3000, 3001, 8081)
4. 启动Backend API (8000)
   - 初始化Admin Agent
   - 初始化Employee Agent
5. 启动IM渠道服务 (按需)
   - 启动WeWork callback (8081)
6. 启动前端服务
   - 启动Admin UI (3000)
   - 启动Employee UI (3001) - 如果EMPLOYEE_UI_ENABLED=true
```

### 3.2 验证服务启动

```bash
# 检查所有服务状态
lsof -i :8000,:3000,:3001,:8081
```

**预期输出**:
```
COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
python3  1234 user   5u  IPv4  ...      0t0  TCP *:8000 (LISTEN)
node     5678 user  23u  IPv4  ...      0t0  TCP *:3000 (LISTEN)
node     9101 user  23u  IPv4  ...      0t0  TCP *:3001 (LISTEN)
python3  1112 user   6u  IPv4  ...      0t0  TCP *:8081 (LISTEN)
```

---

## 步骤4: 验证部署

### 4.1 健康检查

```bash
# Backend API
curl http://localhost:8000/health
# 预期: {"status":"healthy","timestamp":"..."}

# Admin UI
curl http://localhost:3000
# 预期: HTML内容

# Employee UI (如果启用)
curl http://localhost:3001
# 预期: HTML内容

# WeWork callback (如果配置)
curl http://localhost:8081/health || echo "No health endpoint"
```

### 4.2 功能测试

**测试Admin UI** (Web浏览器):
```
1. 访问 http://localhost:3000
2. 尝试上传文档
3. 尝试知识查询
4. 检查是否能正常使用
```

**测试Employee UI** (Web浏览器):
```
1. 访问 http://localhost:3001
2. 输入知识查询问题
3. 检查SSE流式响应
4. 验证Markdown渲染
```

**测试WeWork集成** (企业微信):
```
1. 在企业微信中向应用发送消息
2. 检查是否收到回复
3. 查看日志: tail -f logs/wework.log
```

### 4.3 检查日志

```bash
# Backend主服务日志
tail -50 logs/backend.log

# WeWork回调服务日志
tail -50 logs/wework.log

# Frontend日志
tail -50 logs/frontend.log
```

---

## 可选: 启用新功能

### 1. 启用Employee Web UI

**步骤**:
1. 在`.env`中设置:
   ```bash
   EMPLOYEE_UI_ENABLED=true
   EMPLOYEE_UI_PORT=3001
   ```

2. 重启服务:
   ```bash
   ./scripts/stop.sh
   ./scripts/start_v3.sh
   ```

3. 访问: http://localhost:3001

**功能**:
- 💬 对话式知识查询界面
- 🚀 SSE流式响应
- 📝 Markdown渲染
- 🎨 现代化设计

### 2. 添加新的IM平台 (飞书示例)

**步骤**:
1. 在`.env`中配置飞书:
   ```bash
   ENABLE_FEISHU=auto
   FEISHU_APP_ID=cli_xxx...
   FEISHU_APP_SECRET=xxx...
   FEISHU_VERIFICATION_TOKEN=xxx...
   FEISHU_ENCRYPT_KEY=xxx...
   FEISHU_PORT=8082
   ```

2. 开发飞书适配器:
   ```bash
   # 创建目录
   mkdir -p backend/channels/feishu

   # 参考WeWork适配器实现
   # 需要实现: client.py, adapter.py, server.py
   ```

3. 重启服务:
   ```bash
   ./scripts/stop.sh
   ./scripts/start_v3.sh
   ```

**参考文档**: `docs/CHANNELS.md`

---

## 回滚计划

### 如果需要回滚到v2.0

**步骤1: 切换启动脚本**
```bash
# 停止v3.0服务
./scripts/stop.sh

# 使用v2.0启动脚本 (仍然保留)
./scripts/start.sh
```

**步骤2: 还原配置**
```bash
# 还原.env文件
cp .env.backup.YYYYMMDD .env

# 或者手动删除v3.0配置项
# 只保留v2.0需要的配置
```

**步骤3: 重启服务**
```bash
./scripts/start.sh
```

**注意**:
- ✅ v2.0代码完全保留，回滚无风险
- ✅ `scripts/start.sh` 未被修改，可直接使用
- ✅ 不需要代码回滚，只需切换启动脚本

---

## 常见问题

### Q1: 启动时提示"端口已被占用"

**问题**: `Port 8000 already in use`

**解决方案**:
```bash
# 查找占用端口的进程
lsof -i :8000

# 杀死进程
kill -9 <PID>

# 或者使用stop脚本
./scripts/stop.sh
```

### Q2: Employee UI无法访问

**问题**: 访问http://localhost:3001 无响应

**排查步骤**:
```bash
# 1. 检查EMPLOYEE_UI_ENABLED配置
grep EMPLOYEE_UI_ENABLED .env
# 应显示: EMPLOYEE_UI_ENABLED=true

# 2. 检查端口监听
lsof -i :3001

# 3. 检查日志
tail -50 logs/frontend.log

# 4. 手动启动Employee UI
cd frontend-employee
npm run dev
```

### Q3: WeWork回调无响应

**问题**: 企微消息发送后无回复

**排查步骤**:
```bash
# 1. 检查配置
grep WEWORK_ .env

# 2. 检查WeWork服务是否启动
lsof -i :8081

# 3. 检查日志
tail -100 logs/wework.log

# 4. 测试WeWork适配器
python -c "
from backend.channels.wework import WeWorkAdapter
adapter = WeWorkAdapter()
print('Configured:', adapter.is_configured())
print('Required vars:', adapter.get_required_env_vars())
"
```

### Q4: 启动脚本检测不到已配置的渠道

**问题**: `start_v3.sh`显示"未检测到任何已配置的渠道"

**排查步骤**:
```bash
# 1. 检查环境变量是否正确加载
source .env
echo $WEWORK_CORP_ID

# 2. 手动测试配置检测
python -c "
from backend.config.channel_config import get_channel_config
config = get_channel_config()
print('Enabled:', config.get_enabled_channels())
print('Status:', config.get_channel_status())
"

# 3. 检查ENABLE_*配置
grep ENABLE_ .env
# 确保不是disabled
```

### Q5: 依赖安装失败

**问题**: `pip install -r backend/requirements.txt`失败

**解决方案**:
```bash
# 问题: PyMuPDF安装失败
# 原因: 缺少系统依赖
# macOS解决:
brew install mupdf

# Ubuntu/Debian解决:
sudo apt-get install libmupdf-dev

# 问题: pypandoc安装失败
# 原因: 缺少pandoc
# macOS:
brew install pandoc

# Ubuntu/Debian:
sudo apt-get install pandoc

# 重新安装
pip3 install -r backend/requirements.txt
```

### Q6: 如何保留v2.0的WeWork功能但不启用v3.0的其他功能?

**答**: 完全可以! v3.0 100%向后兼容v2.0。

**配置方式**:
```bash
# .env文件
ENABLE_WEWORK=auto      # 保留企微功能
WEWORK_CORP_ID=...
# ... (其他企微配置)

ENABLE_FEISHU=disabled  # 不启用飞书
ENABLE_DINGTALK=disabled
ENABLE_SLACK=disabled

EMPLOYEE_UI_ENABLED=false  # 不启用Employee UI
```

**启动方式**:
```bash
# 选项1: 使用v2.0启动脚本
./scripts/start.sh

# 选项2: 使用v3.0启动脚本(会自动跳过未配置的渠道)
./scripts/start_v3.sh
```

---

## 总结

### 迁移检查清单

- [ ] 备份当前配置 (`.env`)
- [ ] 拉取最新代码 (`git pull` 或 `git checkout main`)
- [ ] 安装新依赖 (`pip3 install -r backend/requirements.txt`)
- [ ] 更新`.env`文件 (添加v3.0配置项)
- [ ] 赋予启动脚本执行权限 (`chmod +x scripts/start_v3.sh`)
- [ ] 启动v3.0服务 (`./scripts/start_v3.sh`)
- [ ] 验证所有服务健康 (健康检查 + 功能测试)
- [ ] 检查日志无错误 (`logs/backend.log`, `logs/wework.log`)
- [ ] (可选) 启用Employee UI
- [ ] (可选) 添加新的IM平台

### 支持渠道

- **技术文档**: `docs/PROGRESS_V3.md`, `docs/TODO_V3.md`
- **架构文档**: `CLAUDE.md`
- **渠道开发**: `docs/CHANNELS.md`
- **Issues**: GitHub Issues (如果适用)

---

**迁移完成!** 🎉

现在你已成功迁移到v3.0统一多渠道架构,享受以下新特性:
- ✅ Employee Web UI - 员工端Web知识查询界面
- ✅ 多IM平台支持 - 企微/飞书/钉钉/Slack可插拔
- ✅ 混合配置系统 - 自动检测已配置渠道
- ✅ 智能启动脚本 - 一键启动所有服务
- ✅ Channel Adapter - 统一的IM平台抽象层

**Next Steps**: 浏览 `docs/CHANNELS.md` 学习如何开发新的IM平台适配器!
