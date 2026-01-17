# FAQ Operations Details

## File Lock Usage

All FAQ and BADCASE operations must use file locks:

```python
from backend.services.shared_kb_access import SharedKBAccess

kb = SharedKBAccess('knowledge_base')
with kb.file_lock('FAQ.md', timeout=5):
    # Read, modify, write operations
    pass
```

---

## Scenario 1: Answer from FAQ

### Satisfied Feedback → Increment Usage Count

```bash
python3 -c "
from backend.services.shared_kb_access import SharedKBAccess

kb = SharedKBAccess('knowledge_base')
with kb.file_lock('FAQ.md', timeout=5):
    # 1. Read FAQ.md
    with open('knowledge_base/FAQ.md', 'r') as f:
        content = f.read()

    # 2. Find matching entry, increment count
    # FAQ format: | Question | Answer | Usage Count |
    # Change | 3 | to | 4 |

    # 3. Write back to FAQ.md
    with open('knowledge_base/FAQ.md', 'w') as f:
        f.write(updated_content)
"
```

**Reply**: "Glad I could help! FAQ usage statistics updated."
**Metadata**: `session_status: "resolved"`

### Unsatisfied Feedback (with improvement suggestion) → Update Content

```bash
python3 -c "
from backend.services.shared_kb_access import SharedKBAccess

kb = SharedKBAccess('knowledge_base')
with kb.file_lock('FAQ.md', timeout=5):
    # 1. Read FAQ.md
    # 2. Find matching entry, update answer content
    # 3. Write back to FAQ.md
    pass
"
```

**Reply**: "Thank you for your feedback! FAQ content has been updated based on your suggestion."

### Unsatisfied Feedback (no reason) → Remove Entry

```bash
python3 -c "
from backend.services.shared_kb_access import SharedKBAccess

kb = SharedKBAccess('knowledge_base')

# 1. Remove from FAQ
with kb.file_lock('FAQ.md', timeout=5):
    # Read, delete entry, write back
    pass

# 2. Record to BADCASE
with kb.file_lock('BADCASE.md', timeout=5):
    # Append record
    pass
"
```

**Reply**: "Thank you for the feedback! This FAQ entry has been removed and recorded as an improvement item. Administrators will supplement accurate information soon."

---

## Scenario 2: Answer from Knowledge Base File

### Satisfied Feedback → Add to FAQ

```bash
python3 -c "
from backend.services.shared_kb_access import SharedKBAccess

kb = SharedKBAccess('knowledge_base')
with kb.file_lock('FAQ.md', timeout=5):
    # 1. Read FAQ.md
    with open('knowledge_base/FAQ.md', 'r') as f:
        content = f.read()

    # 2. Count current entries
    entry_count = content.count('| ')  # Simplified count

    # 3. If exceeding max entries, remove least used one
    if entry_count > 50:  # FAQ_MAX_ENTRIES
        # Find and delete entry with lowest usage count
        pass

    # 4. Append new entry: | Question | Answer | 1 |
    new_entry = f'| {question} | {answer} | 1 |\\n'
    content += new_entry

    # 5. Write back to FAQ.md
    with open('knowledge_base/FAQ.md', 'w') as f:
        f.write(content)
"
```

**Reply**: "Glad I could help! This Q&A has been added to FAQ for easy access by other colleagues."
**Metadata**: `session_status: "resolved"`

### Unsatisfied Feedback → Record BADCASE

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

**Question**: {question}
**Given answer**: {answer}
**User feedback**: Unsatisfied
**Source file**: {source_file}

---
'''
        f.write(entry)
"
```

**Reply**: "Sorry we couldn't provide a satisfactory answer. This case has been recorded and administrators will supplement relevant information. Would you like me to contact a domain expert?"
**Metadata**: `session_status: "active"` (possible follow-up)

---

## FAQ.md Format

```markdown
# FAQ - Frequently Asked Questions

| Question | Answer | Usage Count |
|---------|--------|-------------|
| How to apply for annual leave? | Log into OA system, submit application 3 days in advance. | 15 |
| What is the company WiFi password? | guest2024 | 8 |
| ... | ... | ... |
```

## BADCASE.md Format

```markdown
# BADCASE - Issues to Improve

## 2025-01-06 14:30

**Question**: How to apply for salary adjustment?
**Given answer**: No relevant information in knowledge base
**User feedback**: Unsatisfied
**Source file**: None

---
```
