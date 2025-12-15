# EFKA 部署测试报告 - 文档问题汇总

**测试日期**: 2025-12-15
**测试人员**: 自动化部署测试

---

## 测试环境

| 项目 | 版本 | 状态 |
|------|------|------|
| macOS | Darwin 25.1.0 | - |
| Python | 3.12.9 | ✅ 满足要求 |
| Node.js | v23.10.0 | ✅ 满足要求 |
| Pandoc | 3.7.0.2 | ✅ 满足要求 |
| Redis | 未安装 | ❌ |

---

## 🔴 严重问题（阻止部署）

### 1. `.env.example` 与 `settings.py` 不同步

**文件位置**:
- `.env.example`
- `backend/config/settings.py`

**问题描述**:

`.env.example` 中定义了多个环境变量，但这些变量在 `backend/config/settings.py` 的 `Settings` 类中没有对应的字段定义。由于 `Settings` 类没有设置 `extra = "ignore"`，pydantic 会对未定义的环境变量抛出验证错误，导致后端服务无法启动。

**缺失的字段**:

```python
# 渠道启用配置
ENABLE_WEWORK: str = "auto"
ENABLE_FEISHU: str = "auto"
ENABLE_DINGTALK: str = "auto"
ENABLE_SLACK: str = "auto"

# 飞书配置
FEISHU_APP_ID: Optional[str] = None
FEISHU_APP_SECRET: Optional[str] = None
FEISHU_VERIFICATION_TOKEN: Optional[str] = None
FEISHU_ENCRYPT_KEY: Optional[str] = None
FEISHU_PORT: int = 8082

# 钉钉配置
DINGTALK_CORP_ID: Optional[str] = None
DINGTALK_APP_KEY: Optional[str] = None
DINGTALK_APP_SECRET: Optional[str] = None
DINGTALK_PORT: int = 8083

# Slack 配置
SLACK_BOT_TOKEN: Optional[str] = None
SLACK_SIGNING_SECRET: Optional[str] = None
SLACK_APP_TOKEN: Optional[str] = None
SLACK_PORT: int = 8084

# Employee UI 配置
EMPLOYEE_UI_ENABLED: bool = True
EMPLOYEE_UI_PORT: int = 3001
```

**错误信息**:

```
pydantic_core._pydantic_core.ValidationError: 9 validation errors for Settings
ENABLE_WEWORK
  Extra inputs are not permitted [type=extra_forbidden, input_value='auto', input_type=str]
ENABLE_FEISHU
  Extra inputs are not permitted [type=extra_forbidden, input_value='auto', input_type=str]
FEISHU_PORT
  Extra inputs are not permitted [type=extra_forbidden, input_value='8082', input_type=str]
ENABLE_DINGTALK
  Extra inputs are not permitted [type=extra_forbidden, input_value='auto', input_type=str]
DINGTALK_PORT
  Extra inputs are not permitted [type=extra_forbidden, input_value='8083', input_type=str]
ENABLE_SLACK
  Extra inputs are not permitted [type=extra_forbidden, input_value='auto', input_type=str]
SLACK_PORT
  Extra inputs are not permitted [type=extra_forbidden, input_value='8084', input_type=str]
EMPLOYEE_UI_ENABLED
  Extra inputs are not permitted [type=extra_forbidden, input_value='true', input_type=str]
EMPLOYEE_UI_PORT
  Extra inputs are not permitted [type=extra_forbidden, input_value='3001', input_type=str]
```

**解决方案**:

方案 A: 在 `Settings` 类中添加所有缺失的字段定义

方案 B: 在 `Settings` 类的 `Config` 中添加 `extra = "ignore"` 来忽略未定义的环境变量

---

### 2. `docker-compose.yml` 引用不存在的目录

**文件位置**: `docker-compose.yml:165-168`

**问题描述**:

`employee-ui` 服务的构建配置引用了 `./frontend-employee` 目录，但该目录在项目中不存在。

**问题代码**:

```yaml
employee-ui:
  build:
    context: ./frontend-employee  # 此目录不存在
    dockerfile: ../deploy/Dockerfile.frontend
```

**解决方案**:

根据项目实际架构，`employee-ui` 应该与 `admin-ui` 共用同一个前端代码库，通过环境变量 `VITE_APP_MODE=employee` 来区分模式。建议修改为：

```yaml
employee-ui:
  build:
    context: ./frontend
    dockerfile: ../deploy/Dockerfile.frontend
    args:
      - VITE_APP_MODE=employee
      - VITE_API_BASE_URL=${VITE_API_BASE_URL:-http://localhost:8000}
```

---

## 🟡 中等问题（文档引用错误）

### 3. 引用的文件不存在

**文件位置**: `frontend/README.md:222-224`

**问题描述**:

前端 README 中的"相关文档"部分引用了不存在的文件：

```markdown
## 相关文档

- [技术方案](../docs/DEPLOYMENT.md)           # 存在 ✅
- [Phase 3 验收报告](../docs/Phase3-验收报告.md)  # 不存在 ❌
- [后端 API 文档](../backend/README.md)        # 不存在 ❌
```

**解决方案**:

- 创建缺失的文档文件，或
- 移除对不存在文件的引用

---

### 4. README 中的配置变量名称描述不一致

**文件位置**: `README.md:265`

**问题描述**:

文档的配置表格中显示 `CLAUDE_API_KEY` 为必填项，但 `.env.example` 中推荐使用 `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_BASE_URL` 方式（方式二，标注为推荐）。

**当前文档**:

| Variable | Description | Required |
|----------|-------------|----------|
| `CLAUDE_API_KEY` | Claude API key | Yes |

**建议修改为**:

| Variable | Description | Required |
|----------|-------------|----------|
| `CLAUDE_API_KEY` 或 `ANTHROPIC_AUTH_TOKEN` | Claude API 认证（二选一） | Yes |
| `ANTHROPIC_BASE_URL` | API Base URL（使用 AUTH_TOKEN 时需要） | 条件必填 |

---

## 🟢 轻微问题（建议改进）

### 5. Redis 依赖说明不明确

**文件位置**:
- `README.md:213-219`
- `docs/DEPLOYMENT.md:74`

**问题描述**:

文档将 "Redis 7+" 列为前置条件，给人的印象是必须安装。但根据 `CLAUDE.md` 中的说明：

> `REDIS_*`: Redis configuration (has memory fallback)

Redis 实际上应该是可选的，系统有内存回退机制。

**建议修改**:

```markdown
### Prerequisites

- Python 3.10+
- Node.js 18+
- Redis 7+ (可选，未安装时使用内存存储)
- Claude API Key
- Pandoc (for document conversion)
```

---

### 6. `knowledge_base` 目录初始化步骤不明确

**文件位置**: Quick Start 部分

**问题描述**:

文档说明了手动复制 skills 的方法：

```bash
cp -r skills/ knowledge_base/skills/
```

但没有说明需要先创建 `knowledge_base` 目录。如果该目录不存在，此命令会失败。

**建议修改**:

```bash
# 手动复制 skills 到知识库
mkdir -p knowledge_base
cp -r skills/ knowledge_base/skills/
```

---

### 7. Git clone 地址需要确认

**文件位置**:
- `README.md:225`
- `docs/DEPLOYMENT.md:91`

**问题描述**:

```bash
git clone https://github.com/anthropics/efka.git
```

需要确认该仓库地址是否正确，或者是否应该是其他地址。

---

### 8. 前端依赖存在安全警告

**问题描述**:

执行 `npm install` 时显示以下警告：

```
2 moderate severity vulnerabilities

npm warn deprecated inflight@1.0.6: This module is not supported, and leaks memory.
npm warn deprecated @humanwhocodes/config-array@0.13.0: Use @eslint/config-array instead
npm warn deprecated rimraf@3.0.2: Rimraf versions prior to v4 are no longer supported
npm warn deprecated glob@7.2.3: Glob versions prior to v9 are no longer supported
npm warn deprecated @humanwhocodes/object-schema@2.0.3: Use @eslint/object-schema instead
npm warn deprecated eslint@8.57.1: This version is no longer supported.
```

**建议**: 更新 `package.json` 中的依赖版本以解决安全问题。

---

## 测试结果总结

| 阶段 | 状态 | 备注 |
|------|------|------|
| 环境检查 | ⚠️ 部分通过 | Redis 未安装（应为可选） |
| 配置文件复制 | ✅ 通过 | `.env.example` → `.env` |
| 后端依赖安装 | ✅ 通过 | pip install 成功 |
| 前端依赖安装 | ✅ 通过 | npm install 成功（有安全警告） |
| Skills 复制 | ✅ 通过 | 需手动创建目录 |
| **后端启动** | ❌ **失败** | Settings 类缺少字段定义 |
| 前端启动 | ⏸️ 未测试 | 后端失败导致阻塞 |

---

## 修复优先级

1. **P0 (立即修复)**: 问题 #1 - Settings 类与 .env.example 不同步
2. **P0 (立即修复)**: 问题 #2 - docker-compose.yml 引用不存在的目录
3. **P1 (尽快修复)**: 问题 #3 - 移除或创建缺失的文档引用
4. **P2 (计划修复)**: 问题 #4-8 - 文档改进和依赖更新
