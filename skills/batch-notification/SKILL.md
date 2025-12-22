---
name: batch-notification
description: 批量向用户发送IM消息。用于通知特定用户群体、筛选表格数据后发送、全员通知等场景。当管理员请求批量通知、群发消息、表格筛选后通知时使用此 Skill。触发词：通知/发送/群发 + 用户/批量/表格。
---

# 批量用户通知

支持管理员批量向用户发送 IM 通知消息。

## 典型场景

1. **上传表格 + 筛选条件**：通知所有福利积分大于0的用户
2. **上传目标清单**：通知指定的用户列表
3. **全员通知**：通知所有人

## 快速开始

### 全员通知
```python
mcp__{channel}__send_markdown_message(
    touser="@all",
    content="## 通知标题\n\n通知内容..."
)
```

### 筛选后通知
```bash
python3 -c "
import pandas as pd
mapping = pd.read_excel('knowledge_base/企业管理/人力资源/user_mapping.xlsx')
business = pd.read_excel('/tmp/data.xlsx')
filtered = business[business['积分'] > 0]
result = pd.merge(filtered, mapping, on='工号', how='inner')
print('|'.join(result['企业微信用户ID'].tolist()))
"
```

## 详细流程

完整的5阶段工作流程，见 [WORKFLOW.md](WORKFLOW.md)

## pandas 查询模式

常用筛选、JOIN、日期处理模式，见 [PANDAS_PATTERNS.md](PANDAS_PATTERNS.md)

## 示例场景

完整的端到端示例，见 [EXAMPLES.md](EXAMPLES.md)

## 核心原则

1. **隐私保护**：通知为一对一私聊，消息不得包含其他人信息
2. **必须确认**：构建消息后必须等待管理员回复"确认发送"
3. **Python优先**：所有表格处理使用 pandas
4. **结果透明**：清晰报告发送结果（成功/失败人数）

## 可用工具

- **Bash**：执行 pandas 脚本
- **mcp__{channel}__send_markdown_message**：发送 Markdown 消息
- **mcp__{channel}__send_text_message**：发送纯文本消息
