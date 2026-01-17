# Batch Notification 5-Stage Workflow

## Stage 1: Intent Confirmation and Information Collection

**Goal**: Accurately understand administrator's notification needs

1. Identify notification target type:
   - All-staff (@all)
   - Specific people (need filtering)
   - Uploaded list file

2. Extract key information:
   - Filter conditions (e.g. "points>0", "department=Tech")
   - Notification content theme and key points
   - Whether links, time, etc. are needed

3. Proactively ask for confirmation if ambiguous

---

## Stage 2: User Mapping Table Reading

**Core**: Use pandas to process tables

### Read Mapping Table

```bash
python3 -c "
import pandas as pd
import json

df = pd.read_excel('knowledge_base/企业管理/人力资源/user_mapping.xlsx')
result = df.to_dict('records')
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

### Build Mapping Relations

```python
{
  "name->userid": {"张三": "zhangsan", "李四": "lisi"},
  "employee_id->userid": {"E1001": "zhangsan", "E1002": "lisi"}
}
```

### Read Business Data Table (if any)

```bash
python3 -c "
import pandas as pd
import json

df = pd.read_excel('/tmp/uploaded_data.xlsx')
print(json.dumps(df.to_dict('records'), ensure_ascii=False, indent=2))
"
```

---

## Stage 3: Target User List Extraction

### Scenario A: With Filter Conditions (JOIN + WHERE)

```bash
python3 -c "
import pandas as pd

mapping_df = pd.read_excel('knowledge_base/企业管理/人力资源/user_mapping.xlsx')
business_df = pd.read_excel('/tmp/data.xlsx')

# WHERE
filtered_df = business_df[business_df['福利积分'] > 0]

# JOIN
result = pd.merge(filtered_df, mapping_df, on='工号', how='inner')

# Output
print('|'.join(result['企业微信用户ID'].tolist()))
"
```

### Scenario B: Direct List

```bash
python3 -c "
import pandas as pd

mapping_df = pd.read_excel('knowledge_base/企业管理/人力资源/user_mapping.xlsx')
target_names = ['张三', '李四', '王五']
filtered = mapping_df[mapping_df['姓名'].isin(target_names)]
print('|'.join(filtered['企业微信用户ID'].tolist()))
"
```

### Scenario C: All-staff

```python
touser = "@all"
```

---

## Stage 4: Message Construction and Confirmation

### Important Privacy Principles

- All notifications are in private chat format (one-on-one messages)
- Message content must not contain information about people other than the recipient
- Use "you" instead of "you all" to avoid revealing batch sending fact

### Construct Markdown Message

```markdown
## Notification Title

**Notification content**:
[Specific description]

**Related information**:
- Time: [if any]
- Link: [if any]

> If you have any questions, please contact [contact person]
```

### Color Font Syntax

- `<font color="info">Blue</font>`
- `<font color="warning">Orange</font>`
- `<font color="comment">Gray</font>`

### Generate Preview

```
【Batch Notification Preview】

Target count: 15 people
Target users: 张三(zhangsan), 李四(lisi)... (15 people total)

Message content:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Message content]
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Please confirm sending? (Reply "confirm send" to continue)
```

### Wait for Confirmation

Must wait for administrator to reply with one of these keywords:
- "confirm send"
- "send"
- "confirm"
- "OK"

---

## Stage 5: Batch Sending and Result Feedback

### Sending Strategy

**≤1000 people**: Single send
```python
mcp__{channel}__send_markdown_message(
    touser="user1|user2|user3|...",
    content="<Message content>"
)
```

**>1000 people**: Batch send (API limit)
```python
for i in range(0, len(userids), 1000):
    batch = userids[i:i+1000]
    touser = "|".join(batch)
    # Call send tool
```

### Result Feedback

**Success**:
```
✅ Message sent successfully!

Sent to: 15 people
Message ID: msg123456789
Send time: 2025-01-06 14:30:25
```

**Partial Failure**:
```
⚠️ Message sending completed (partial failure)

Successfully sent: 14 people
Failed: 1 person
Failed user: user999

Suggestion: Check if the user ID in user_mapping.xlsx is correct.
```

**Error**:
```
❌ Message sending failed

Error code: 40001
Error message: invalid secret

Suggestion: Check IM configuration in .env file.
```
