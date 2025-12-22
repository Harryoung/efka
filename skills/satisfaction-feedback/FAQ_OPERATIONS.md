# FAQ 操作详情

## 文件锁使用

所有 FAQ 和 BADCASE 操作必须使用文件锁：

```python
from backend.services.shared_kb_access import SharedKBAccess

kb = SharedKBAccess('knowledge_base')
with kb.file_lock('FAQ.md', timeout=5):
    # 读取、修改、写入操作
    pass
```

---

## 场景1：答案来自 FAQ

### 满意反馈 → 增加使用计数

```bash
python3 -c "
from backend.services.shared_kb_access import SharedKBAccess

kb = SharedKBAccess('knowledge_base')
with kb.file_lock('FAQ.md', timeout=5):
    # 1. 读取 FAQ.md
    with open('knowledge_base/FAQ.md', 'r') as f:
        content = f.read()

    # 2. 找到匹配条目，增加计数
    # FAQ 格式: | 问题 | 答案 | 使用次数 |
    # 将 | 3 | 改为 | 4 |

    # 3. 写回 FAQ.md
    with open('knowledge_base/FAQ.md', 'w') as f:
        f.write(updated_content)
"
```

**回复**："很高兴能帮到您！已更新FAQ使用统计。"
**元数据**：`session_status: "resolved"`

### 不满意反馈（有改进意见）→ 更新内容

```bash
python3 -c "
from backend.services.shared_kb_access import SharedKBAccess

kb = SharedKBAccess('knowledge_base')
with kb.file_lock('FAQ.md', timeout=5):
    # 1. 读取 FAQ.md
    # 2. 找到匹配条目，更新答案内容
    # 3. 写回 FAQ.md
    pass
"
```

**回复**："感谢您的反馈！已根据您的建议更新FAQ内容。"

### 不满意反馈（无理由）→ 移除条目

```bash
python3 -c "
from backend.services.shared_kb_access import SharedKBAccess

kb = SharedKBAccess('knowledge_base')

# 1. 从 FAQ 移除
with kb.file_lock('FAQ.md', timeout=5):
    # 读取、删除条目、写回
    pass

# 2. 记录到 BADCASE
with kb.file_lock('BADCASE.md', timeout=5):
    # 追加记录
    pass
"
```

**回复**："感谢反馈！该FAQ条目已移除并记录为待改进项，管理员将尽快补充准确资料。"

---

## 场景2：答案来自知识库文件

### 满意反馈 → 添加到 FAQ

```bash
python3 -c "
from backend.services.shared_kb_access import SharedKBAccess

kb = SharedKBAccess('knowledge_base')
with kb.file_lock('FAQ.md', timeout=5):
    # 1. 读取 FAQ.md
    with open('knowledge_base/FAQ.md', 'r') as f:
        content = f.read()

    # 2. 统计当前条目数
    entry_count = content.count('| ')  # 简化计数

    # 3. 如果超过最大条目数，移除使用次数最少的
    if entry_count > 50:  # FAQ_MAX_ENTRIES
        # 找到使用次数最少的条目并删除
        pass

    # 4. 追加新条目: | 问题 | 答案 | 1 |
    new_entry = f'| {question} | {answer} | 1 |\\n'
    content += new_entry

    # 5. 写回 FAQ.md
    with open('knowledge_base/FAQ.md', 'w') as f:
        f.write(content)
"
```

**回复**："很高兴能帮到您！已将此问答添加到FAQ，方便其他同事查询。"
**元数据**：`session_status: "resolved"`

### 不满意反馈 → 记录 BADCASE

```bash
python3 -c "
from backend.services.shared_kb_access import SharedKBAccess
from datetime import datetime

kb = SharedKBAccess('knowledge_base')
with kb.file_lock('BADCASE.md', timeout=5):
    with open('knowledge_base/BADCASE.md', 'a') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        entry = f'''
## {timestamp}

**问题**: {question}
**给出的答案**: {answer}
**用户反馈**: 不满意
**来源文件**: {source_file}

---
'''
        f.write(entry)
"
```

**回复**："很抱歉未能提供满意答案，该case已被记录，管理员后续将补充相关资料。是否需要为您联系领域专家？"
**元数据**：`session_status: "active"`（可能有追问）

---

## FAQ.md 格式

```markdown
# FAQ - 常见问题

| 问题 | 答案 | 使用次数 |
|-----|-----|---------|
| 如何申请年假？ | 登录OA系统，提前3天提交申请。 | 15 |
| 公司WIFI密码是多少？ | guest2024 | 8 |
| ... | ... | ... |
```

## BADCASE.md 格式

```markdown
# BADCASE - 待改进问题

## 2025-01-06 14:30

**问题**: 如何申请调薪？
**给出的答案**: 知识库中暂无相关信息
**用户反馈**: 不满意
**来源文件**: 无

---
```
