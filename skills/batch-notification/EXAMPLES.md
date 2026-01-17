# Batch Notification Examples

## Example 1: Filtered Notification

**User input**:
> I uploaded the benefits points table. Please notify all users with points greater than 0 to remind them to use points before the end of the month.

**Execution process**:

1. **Intent confirmation**: Target=users with points>0, content=reminder to use before month end

2. **Read mapping table** and get name/employee_id → userid mapping

3. **Filter target users**:
```bash
python3 -c "
import pandas as pd
mapping_df = pd.read_excel('knowledge_base/企业管理/人力资源/user_mapping.xlsx')
business_df = pd.read_excel('/tmp/welfare_points.xlsx')
filtered = business_df[business_df['福利积分'] > 0]
result = pd.merge(filtered, mapping_df, on='工号', how='inner')
print('|'.join(result['企业微信用户ID'].tolist()))
"
```

4. **Construct message** (privacy protection, no other people's information):
```markdown
## Benefits Points Usage Reminder

**Friendly reminder**:
You still have benefits points balance, which will expire at the end of this month (January 31). Please use them as soon as possible.

**Check points**: [Click to enter benefits platform](http://welfare.example.com)

> If you have any questions, please contact HR department (ext: 1234)
```

5. **Show preview and wait for confirmation**

6. **Execute sending**:
```python
mcp__{channel}__send_markdown_message(
    touser="zhangsan|lisi|wangwu|...",
    content="<Message content>"
)
```

7. **Feedback results**

---

## Example 2: All-staff Notification

**User input**:
> Notify everyone that the knowledge base has added the "2025 Annual Plan" document. Please study it in time.

**Execution process**:

1. **Intent confirmation**: All-staff notification (@all)

2. **Construct message** (use "you" instead of "everyone"):
```markdown
## Knowledge Base Update Notification

**New document**: "2025 Annual Plan"

Please review and study it in time to understand the company's strategic direction for the new year.

**View document**: [Click to enter knowledge base](http://kb.example.com)

> If you have any questions, please contact the administration department
```

3. **Show preview**

4. **Wait for confirmation and send**:
```python
mcp__{channel}__send_markdown_message(
    touser="@all",
    content="<Message content>"
)
```

---

## Example 3: Specified Personnel Notification

**User input**:
> Notify Zhang San, Li Si, Wang Wu to attend training next Monday

**Execution process**:

1. **Intent confirmation**: Specified personnel notification

2. **Query userid**:
```bash
python3 -c "
import pandas as pd
mapping_df = pd.read_excel('knowledge_base/企业管理/人力资源/user_mapping.xlsx')
target = mapping_df[mapping_df['姓名'].isin(['张三', '李四', '王五'])]
print('|'.join(target['企业微信用户ID'].tolist()))
"
```

3. **Construct message and send**

---

## Error Handling Examples

### user_mapping.xlsx Does Not Exist

```
user_mapping.xlsx file does not exist. Please create user mapping table first.

Mapping table should contain the following fields:
- 姓名
- 工号
- 企业微信用户ID

Location: knowledge_base/企业管理/人力资源/user_mapping.xlsx
```

### No Filter Results

```
No users found matching filter condition "福利积分>0".

Please check:
1. Filter condition is correct
2. Business data table contains relevant data
```

### Column Name Mismatch

```
Column "福利积分" does not exist in table.

Actual column names: ['姓名', '工号', '积分余额', '部门']

Please confirm the correct column name and try again.
```
