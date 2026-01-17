# Expert Routing Workflow

## Step 1: Domain Identification

Identify the domain based on question semantics:

```python
# Domain keyword mapping (example)
domain_keywords = {
    "Compensation & Benefits": ["salary", "wage", "adjustment", "bonus", "benefits", "social security", "housing fund"],
    "Attendance Management": ["leave", "attendance", "clock-in", "overtime", "compensatory leave", "annual leave"],
    "Recruitment & Training": ["onboarding", "new employee", "training", "interview", "recruitment", "probation"],
    "Employee Relations": ["contract", "labor", "resignation", "quit", "arbitration", "dispute"],
    "IT Support": ["system", "account", "password", "computer", "network", "permission"],
}
```

**Judgment Principle**:
- Based on semantic understanding, not keyword matching
- If domain cannot be determined, use "Default Contact"

---

## Step 2: Query Domain Contact

Use pandas to query domain_experts.xlsx:

```bash
python3 -c "
import pandas as pd
import json

domain = 'Compensation & Benefits'  # Replace with identified domain

df = pd.read_excel('knowledge_base/企业管理/人力资源/domain_experts.xlsx')
result = df[df['工作领域'] == domain]

if result.empty:
    # Use default contact
    result = df[df['工作领域'] == '默认负责人']

print(json.dumps(result[['姓名', 'userid', '工作领域']].to_dict('records'), ensure_ascii=False))
"
```

**Output example**:
```json
[{"姓名": "李明", "userid": "liming", "工作领域": "Compensation & Benefits"}]
```

---

## Step 3: Notify Expert

Send message to expert using IM MCP:

```python
mcp__{channel}__send_markdown_message(
    touser="{expert_userid}",
    content="""## 【User Inquiry】

User **{user_name}**({user_id}) asked:

> {question}

<font color="warning">This question has no answer in the knowledge base</font>. Please respond. I will forward your reply to the user.

> It is recommended that you supplement relevant documents to the knowledge base in a timely manner."""
)
```

---

## Step 4: Notify User to Wait

Send waiting message to user:

```python
mcp__{channel}__send_markdown_message(
    touser="{user_id}",
    content="""**{user_name}**, Hello!

We have contacted the <font color="info">{domain}</font> contact **{expert_name}** for you. Please wait, they will reply to you soon."""
)
```

---

## Step 5: Output Metadata

Output metadata containing expert routing information:

```metadata
{
  "key_points": ["Question cannot be answered", "Domain expert contacted"],
  "answer_source": "expert",
  "session_status": "active",
  "confidence": 0.0,
  "expert_routed": true,
  "expert_userid": "liming",
  "expert_name": "李明",
  "domain": "Compensation & Benefits",
  "original_question": "How to apply for salary adjustment?"
}
```

---

## domain_experts.xlsx Format

| 姓名 | userid | 工作领域 |
|-----|--------|---------|
| 李明 | liming | Compensation & Benefits |
| 王芳 | wangfang | Attendance Management |
| 张伟 | zhangwei | Recruitment & Training |
| 赵六 | zhaoliu | Employee Relations |
| 陈默 | chenmo | Default Contact |

**Location**: `knowledge_base/企业管理/人力资源/domain_experts.xlsx`
