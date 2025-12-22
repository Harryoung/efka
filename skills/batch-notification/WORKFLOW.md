# 批量通知 5阶段工作流

## 阶段1：意图确认与信息收集

**目标**：准确理解管理员的通知需求

1. 识别通知对象类型：
   - 全员（@all）
   - 特定人员（需要筛选）
   - 已上传的清单文件

2. 提取关键信息：
   - 筛选条件（如"积分>0"、"部门=技术部"）
   - 通知内容的主题和要点
   - 是否需要链接、时间等元素

3. 如有歧义，主动询问确认

---

## 阶段2：用户映射表读取

**核心**：使用 pandas 处理表格

### 读取映射表

```bash
python3 -c "
import pandas as pd
import json

df = pd.read_excel('knowledge_base/企业管理/人力资源/user_mapping.xlsx')
result = df.to_dict('records')
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

### 构建映射关系

```python
{
  "姓名->userid": {"张三": "zhangsan", "李四": "lisi"},
  "工号->userid": {"E1001": "zhangsan", "E1002": "lisi"}
}
```

### 读取业务数据表（如有）

```bash
python3 -c "
import pandas as pd
import json

df = pd.read_excel('/tmp/uploaded_data.xlsx')
print(json.dumps(df.to_dict('records'), ensure_ascii=False, indent=2))
"
```

---

## 阶段3：目标用户清单提取

### 场景A：有筛选条件（JOIN + WHERE）

```bash
python3 -c "
import pandas as pd

mapping_df = pd.read_excel('knowledge_base/企业管理/人力资源/user_mapping.xlsx')
business_df = pd.read_excel('/tmp/data.xlsx')

# WHERE
filtered_df = business_df[business_df['福利积分'] > 0]

# JOIN
result = pd.merge(filtered_df, mapping_df, on='工号', how='inner')

# 输出
print('|'.join(result['企业微信用户ID'].tolist()))
"
```

### 场景B：直接清单

```bash
python3 -c "
import pandas as pd

mapping_df = pd.read_excel('knowledge_base/企业管理/人力资源/user_mapping.xlsx')
target_names = ['张三', '李四', '王五']
filtered = mapping_df[mapping_df['姓名'].isin(target_names)]
print('|'.join(filtered['企业微信用户ID'].tolist()))
"
```

### 场景C：全员

```python
touser = "@all"
```

---

## 阶段4：消息构建与确认

### 重要隐私原则

- 所有通知为私聊形式（一对一消息）
- 消息内容不得包含发送对象之外的其他人信息
- 使用"您"而非"你们"，避免透露批量发送事实

### 构建 Markdown 消息

```markdown
## 通知标题

**通知内容**：
[具体说明]

**相关信息**：
- 时间：[如有]
- 链接：[如有]

> 如有疑问，请联系 [联系人]
```

### 颜色字体语法

- `<font color="info">蓝色</font>`
- `<font color="warning">橙色</font>`
- `<font color="comment">灰色</font>`

### 生成预览

```
【批量通知预览】

目标人数：15人
目标用户：张三(zhangsan)、李四(lisi)... (共15人)

消息内容：
━━━━━━━━━━━━━━━━━━━━━━━━━━━
[消息内容]
━━━━━━━━━━━━━━━━━━━━━━━━━━━

请确认是否发送？（回复"确认发送"以继续）
```

### 等待确认

必须等待管理员回复以下关键词之一：
- "确认发送"
- "发送"
- "确认"
- "OK"

---

## 阶段5：批量发送与结果反馈

### 发送策略

**≤1000人**：单次发送
```python
mcp__{channel}__send_markdown_message(
    touser="user1|user2|user3|...",
    content="<消息内容>"
)
```

**>1000人**：分批发送（API限制）
```python
for i in range(0, len(userids), 1000):
    batch = userids[i:i+1000]
    touser = "|".join(batch)
    # 调用发送工具
```

### 结果反馈

**成功**：
```
✅ 消息发送成功！

发送人数：15人
消息ID：msg123456789
发送时间：2025-01-06 14:30:25
```

**部分失败**：
```
⚠️ 消息发送完成（部分失败）

成功发送：14人
失败人数：1人
失败用户：user999

建议：检查 user_mapping.xlsx 中该用户的 ID 是否正确。
```

**错误**：
```
❌ 消息发送失败

错误代码：40001
错误信息：invalid secret

建议：检查 .env 文件中的 IM 配置。
```
