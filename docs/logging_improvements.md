# 日志改进说明 (Logging Improvements)

## 问题描述

用户反馈:当大模型API欠费或无响应时,backend的log里没有任何错误信息,无法快速定位问题。

## 改进内容

### 1. SDK客户端初始化错误日志 (`backend/services/kb_service_factory.py`)

**改进位置**: `KBEmployeeService.initialize()` 和 `KBAdminService.initialize()`

**改进内容**:
- 在 `client.connect()` 调用处添加了 try-except 包装
- 记录详细的连接错误信息,包括:
  - 错误类型 (Error type)
  - 错误消息 (Error message)
  - 可能的原因提示:
    - Invalid API key (无效的API key)
    - API account insufficent balance (账户余额不足/欠费)
    - Network connectivity issues (网络连接问题)
    - API service unavailable (API服务不可用)

**示例日志输出**:
```
❌ Failed to connect to Claude API
   Error type: AuthenticationError
   Error message: Invalid API key
   This may indicate:
   - Invalid API key (CLAUDE_API_KEY or ANTHROPIC_AUTH_TOKEN)
   - API account insufficent balance (欠费)
   - Network connectivity issues
   - API service unavailable
```

### 2. API调用错误日志 (`backend/services/kb_service_factory.py`)

**改进位置**: `KBEmployeeService.query()` 和 `KBAdminService.query()`

**改进内容**:
- 添加消息计数器,检测是否收到响应
- 捕获 `asyncio.TimeoutError` 超时错误
- 捕获所有其他异常并记录详细信息
- 区分不同的错误场景:
  - **无响应场景** (message_count == 0):
    - API account insufficent balance (欠费)
    - API rate limit exceeded (超过速率限制)
    - Network timeout (网络超时)
  - **超时场景** (TimeoutError):
    - Network connectivity issues (网络连接问题)
    - API service overload (API服务过载)
  - **其他错误场景**:
    - Invalid API key or token (无效的API key)
    - API account insufficent balance (欠费)
    - Exceeded rate limits (超过速率限制)
    - API service unavailable (API服务不可用)

**示例日志输出**:
```
❌ No response from Claude API
   Session ID: abc123
   User ID: user001
   This may indicate:
   - API account insufficent balance (欠费)
   - API rate limit exceeded
   - Network timeout

✅ Received 5 messages from Claude API
```

### 3. WeChat Work回调错误日志 (`backend/api/wework_callback.py`)

**改进位置**: `process_wework_message()` 函数中的 Employee Agent 调用

**改进内容**:
- 添加消息计数器,检测是否收到响应
- 捕获 `asyncio.TimeoutError` 超时错误
- 捕获所有其他异常并记录详细信息
- 记录上下文信息:
  - User ID (用户ID)
  - Session ID (会话ID)
  - Message preview (消息预览,前100字符)

**示例日志输出**:
```
❌ No response from Employee Agent for user user001
   Session ID: abc123
   This may indicate:
   - API account insufficent balance (欠费)
   - API rate limit exceeded
   - Network timeout
   - API service unavailable

❌ Employee Agent call failed for user user001
   Error type: RateLimitError
   Error message: Rate limit exceeded
   Session ID: abc123
   Message: 请问如何申请年假?...
   This may indicate:
   - Invalid API key or token
   - API account insufficent balance (欠费)
   - Exceeded rate limits
   - API service unavailable
```

## 改进效果

### 改进前
- API调用失败或欠费时,日志中没有明确的错误信息
- 难以快速定位问题原因
- 需要手动检查API key、账户余额等

### 改进后
- **详细的错误类型识别**: 区分欠费、超时、无效key等不同场景
- **明确的原因提示**: 直接提示可能的原因(如"欠费")
- **完整的上下文信息**: 包含session ID、user ID、消息内容等
- **快速定位问题**: 运维人员可以立即识别是欠费、网络问题还是配置问题

## 测试建议

### 1. 测试API欠费场景
```bash
# 使用无效的API key
export CLAUDE_API_KEY="invalid_key"
./scripts/start.sh

# 检查日志
tail -f logs/backend.log

# 预期输出:
# ❌ Failed to connect to Claude API
#    Error type: AuthenticationError
#    ...
#    - API account insufficent balance (欠费)
```

### 2. 测试网络超时场景
```bash
# 模拟网络延迟
# (需要使用网络流量控制工具,如 tc 或 iptables)

# 检查日志
tail -f logs/backend.log

# 预期输出:
# ❌ Claude API call timeout
#    This may indicate:
#    - Network connectivity issues
```

### 3. 测试无响应场景
```bash
# 正常启动服务
./scripts/start.sh

# 发送查询请求
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"message": "测试消息"}'

# 如果API无响应,检查日志
tail -f logs/backend.log

# 预期输出:
# ❌ No response from Claude API
#    This may indicate:
#    - API account insufficent balance (欠费)
```

## 后续优化建议

1. **添加监控告警**:
   - 当检测到欠费或rate limit时,发送钉钉/企微告警
   - 集成到现有的audit_logger系统

2. **添加重试机制**:
   - 对于网络超时,可以自动重试
   - 对于rate limit,可以使用指数退避策略

3. **添加健康检查端点**:
   - `/health` 端点检测API连接状态
   - 定期检查账户余额(如果API支持)

4. **日志聚合**:
   - 考虑使用ELK或Grafana Loki进行日志聚合
   - 设置欠费关键字告警规则

## 相关文件

- `backend/services/kb_service_factory.py` - SDK客户端初始化和查询
- `backend/api/wework_callback.py` - WeChat Work回调处理

## 版本历史

- **2025-01-14**: 初始版本,添加欠费、超时、无响应场景的详细日志

---

**维护者**: System Administrator
**最后更新**: 2025-01-14
