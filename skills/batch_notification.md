# 批量员工通知操作指南

## 核心能力说明

支持管理员批量向员工发送企业微信通知消息。

## 典型使用场景

1. **上传表格 + 说明筛选条件**
   - 管理员上传业务数据表格（如福利积分表）
   - 说明筛选条件："通知所有福利积分大于0的员工，提醒尽快使用"

2. **直接上传目标员工清单**
   - 管理员上传包含姓名/工号的XLSX文件
   - 说明："通知这些员工参加培训"

3. **直接指定通知对象**
   - 全员通知："通知所有人，知识库新增了XXX文档"
   - 特定条件："通知技术部所有员工"

## 5阶段处理流程

### 阶段1：意图确认与信息收集

**目标**：准确理解管理员的通知需求

**步骤**：
1. 识别通知对象类型：
   - 全员（@all）
   - 特定人员（需要筛选）
   - 已上传的清单文件

2. 提取关键信息：
   - 如有筛选条件，提取完整的筛选逻辑（如"积分>0"、"部门=技术部"）
   - 确认通知内容的主题和要点
   - 确认是否需要包含链接、时间等元素

3. 如有歧义，主动询问确认：
   - "您是希望通知所有员工，还是满足特定条件的员工？"
   - "筛选条件是积分大于0，还是积分未清零（即积分>0）？"

---

### 阶段2：员工映射表读取与解析

**核心原则**：使用Python脚本处理表格，不使用markitdown

**步骤2.1：读取员工映射表**

使用Bash工具执行Python代码：

```python
python3 -c "
import pandas as pd
import json

try:
    # 读取员工映射表
    df = pd.read_excel('knowledge_base/企业管理/人力资源/employee_mapping.xlsx')

    # 输出JSON格式，便于后续处理
    result = df.to_dict('records')
    print(json.dumps(result, ensure_ascii=False, indent=2))

except FileNotFoundError:
    print('ERROR: employee_mapping.xlsx 文件不存在')
except Exception as e:
    print(f'ERROR: {str(e)}')
"
```

**步骤2.2：解析映射表数据**

从输出中提取关键字段：
- 姓名（用于匹配）
- 工号（用于匹配）
- 企业微信用户ID（最终发送目标）

构建映射关系：
```python
{
  "姓名->userid": {"张三": "zhangsan", "李四": "lisi", ...},
  "工号->userid": {"E1001": "zhangsan", "E1002": "lisi", ...}
}
```

**步骤2.3：读取业务数据表（如有）**

如果管理员上传了业务数据表（如福利积分表），同样使用Python读取：

```python
python3 -c "
import pandas as pd
import json

df = pd.read_excel('/tmp/uploaded_welfare_points.xlsx')
print(json.dumps(df.to_dict('records'), ensure_ascii=False, indent=2))
"
```

---

### 阶段3：目标员工清单提取

**核心原则**：使用pandas执行类似SQL的查询

**场景A：有筛选条件（需要JOIN和WHERE）**

示例：通知所有福利积分大于0的员工

```python
python3 -c "
import pandas as pd

# 读取员工映射表
mapping_df = pd.read_excel('knowledge_base/企业管理/人力资源/employee_mapping.xlsx')

# 读取业务数据表
business_df = pd.read_excel('/tmp/welfare_points.xlsx')

# 执行筛选（WHERE子句）
filtered_df = business_df[business_df['福利积分'] > 0]

# 与员工映射表关联（JOIN）
result = pd.merge(
    filtered_df,
    mapping_df,
    left_on='工号',  # 或'姓名'，根据实际表格字段
    right_on='工号',
    how='inner'
)

# 提取企业微信用户ID列表
userids = result['企业微信用户ID'].tolist()

# 输出格式：user1|user2|user3（企业微信API格式）
print('|'.join(userids))
"
```

**智能转换：自然语言 → pandas查询**

根据管理员的筛选条件，智能生成pandas代码：

| 自然语言 | pandas代码 |
|---------|-----------|
| "福利积分大于0" | `df['福利积分'] > 0` |
| "福利积分未清零" | `df['福利积分'] > 0` |
| "入职超过1年" | `df['入职日期'] < (pd.Timestamp.now() - pd.DateOffset(years=1))` |
| "技术部门" | `df['部门'].str.contains('技术')` |
| "积分前10名" | `df.nlargest(10, '积分')` |
| "职级>=P7" | `df['职级'] >= 'P7'` |
| "技术部且积分>100" | `(df['部门']=='技术部') & (df['积分']>100)` |

**场景B：直接清单（只需要匹配）**

示例：管理员上传了包含姓名的清单，或直接说"通知张三、李四、王五"

```python
python3 -c "
import pandas as pd

# 读取员工映射表
mapping_df = pd.read_excel('knowledge_base/企业管理/人力资源/employee_mapping.xlsx')

# 从用户输入或清单文件中提取的目标姓名列表
target_names = ['张三', '李四', '王五']

# 筛选目标员工
filtered = mapping_df[mapping_df['姓名'].isin(target_names)]

# 提取用户ID
userids = filtered['企业微信用户ID'].tolist()
print('|'.join(userids))
"
```

**场景C：全员通知**

无需查询，直接使用特殊值：
```python
touser = "@all"
```

**步骤输出**：
- 场景A/B：企业微信用户ID列表，格式 `"user1|user2|user3"`
- 场景C：字符串 `"@all"`
- 同时记录目标人数

---

### 阶段4：消息构建与确认

**核心原则**：必须等待管理员明确确认后才能发送

**重要隐私原则**：
- ⚠️ **所有通知均为私聊形式**（一对一消息）
- ⚠️ **消息内容不得包含发送对象之外的其他人的信息**
- ✅ 正确示例："您的福利积分为580分，请尽快使用"
- ❌ 错误示例："您和张三、李四的福利积分分别为580、320、150分"（泄露了其他人的信息）
- ❌ 错误示例："本次通知对象有15人，包括..."（透露了通知对象范围）

**步骤4.1：构建Markdown格式消息**

根据管理员的通知内容，构建结构化消息（推荐Markdown格式）：

```markdown
## 📢 [通知标题]

**通知内容**：
[具体说明，注意：不得包含其他接收者的信息]

**相关信息**：
- 时间：[如有]
- 链接：[如有]
- 其他说明

> 如有疑问，请联系 [联系人]
```

**消息格式最佳实践**：
- 使用标题（`##`）突出通知主题
- 使用粗体（`**...**`）强调关键信息
- 使用列表（`-`）组织多个要点
- 使用引用（`>`）添加补充说明或联系方式
- 支持的颜色字体：`<font color="info">蓝色</font>`、`<font color="warning">橙色</font>`、`<font color="comment">灰色</font>`
- **隐私保护**：消息内容应该使用"您"而非"你们"，避免透露批量发送的事实

**步骤4.2：生成预览信息**

向管理员展示即将发送的内容：

```
【批量通知预览】

目标人数：15人
目标用户：张三(zhangsan)、李四(lisi)、王五(wangwu)、赵六(zhaoliu)... (共15人)

消息内容：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 📢 福利积分清零提醒

**温馨提示**：
您还有福利积分余额，将于本月底清零，请尽快使用。

**查看积分**：[点击进入福利平台](http://welfare.example.com)

> 如有疑问，请联系人力资源部（内线：1234）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 隐私提示：以上消息为通用内容，每个接收者将收到相同的消息。消息中不包含其他接收者的任何信息。

请确认是否发送？（回复"确认发送"或"发送"以继续）
```

**步骤4.3：等待管理员确认**

**重要**：必须等待管理员明确回复以下关键词之一：
- "确认发送"
- "发送"
- "确认"
- "OK"
- "可以发送"

如果管理员回复其他内容（如"修改一下"、"不对"），则回到步骤4.1重新构建消息。

**步骤4.4：处理个性化数据需求**

如果管理员要求在消息中包含每个人的个人数据（如"告诉每个人他们各自的积分余额"），需要明确告知限制：

```
⚠️ 企业微信API不支持发送个性化消息内容。

**当前方案**：所有接收者将收到相同的通用消息。

**替代方案**：
1. 发送通用提醒（如"您还有福利积分，请及时查看"），并引导员工自行登录系统查看个人数据
2. 在消息中提供查询链接或系统入口

是否采用通用消息方案？
```

---

### 阶段5：批量发送与结果反馈

**步骤5.1：批量发送策略**

根据目标人数选择发送策略：

**情况A：≤1000人（单次发送）**
```python
# 直接调用工具
mcp__wework__wework_send_markdown_message(
    touser="user1|user2|user3|...",
    content="<消息内容>"
)
```

**情况B：>1000人（分批发送）**

企业微信API限制单次最多1000人，需要分批：

```python
# 伪代码示例
userids_list = ["user1", "user2", ..., "user2500"]  # 假设2500人
batch_size = 1000

for i in range(0, len(userids_list), batch_size):
    batch = userids_list[i:i+batch_size]
    touser = "|".join(batch)

    # 调用发送工具
    mcp__wework__wework_send_markdown_message(
        touser=touser,
        content="<消息内容>"
    )
```

**步骤5.2：调用企业微信工具**

推荐使用Markdown格式（更美观）：

```
工具：mcp__wework__wework_send_markdown_message

参数：
- touser: "zhangsan|lisi|wangwu"  (或 "@all")
- content: "<Markdown格式的消息内容>"
```

备选：文本格式

```
工具：mcp__wework__wework_send_text_message

参数：
- touser: "zhangsan|lisi|wangwu"
- content: "<纯文本消息>"
```

**步骤5.3：结果处理与反馈**

解析企业微信API返回结果：

成功响应示例：
```json
{
  "errcode": 0,
  "errmsg": "ok",
  "msgid": "msg123456789",
  "invaliduser": "user999"  // 发送失败的用户（如果有）
}
```

**向管理员反馈**：

成功情况（无失败用户）：
```
✅ 消息发送成功！

发送人数：15人
消息ID：msg123456789
发送时间：2025-01-06 14:30:25
```

部分失败情况：
```
⚠️ 消息发送完成（部分失败）

成功发送：14人
失败人数：1人
失败用户：user999 (可能原因：用户ID不存在或不在应用可见范围内)

消息ID：msg123456789
发送时间：2025-01-06 14:30:25

建议：请检查employee_mapping.xlsx中user999的用户ID是否正确。
```

错误情况：
```
❌ 消息发送失败

错误代码：40001
错误信息：invalid secret

建议：请检查.env文件中的企业微信配置（WEWORK_CORP_SECRET）。
```

---

## Python脚本编写指南

### 核心库依赖

- **pandas**：表格读取和数据处理（支持XLSX、CSV、XLS等）
- **openpyxl**：pandas读取XLSX时的底层引擎
- **json**：输出结构化数据

这些库应已在backend/requirements.txt中定义。

### 脚本编写原则

1. **临时执行**：使用Bash工具执行一次性Python代码，无需创建.py文件
2. **结构化输出**：使用JSON或按特定格式输出，便于Agent解析
3. **错误处理**：包含try-except，优雅处理异常
4. **输出格式**：
   - 正常结果：print到stdout
   - 错误信息：以"ERROR:"开头

### 常用查询模式

**模式1：简单筛选**

```python
# 单条件
df[df['积分'] > 100]
df[df['部门'] == '技术部']
df[df['姓名'].isin(['张三', '李四'])]
df[df['部门'].str.contains('技术')]  # 模糊匹配
```

**模式2：多条件筛选**

```python
# AND 条件
df[(df['积分'] > 0) & (df['部门'] == '技术部')]

# OR 条件
df[(df['入职日期'] < '2024-01-01') | (df['职级'] >= 'P7')]

# 复杂条件
df[
    (df['积分'] > 100) &
    (df['部门'].isin(['技术部', '产品部'])) &
    (df['入职日期'] >= '2023-01-01')
]
```

**模式3：关联查询（JOIN）**

```python
# INNER JOIN（只保留匹配的）
result = pd.merge(
    business_df,      # 业务表
    mapping_df,       # 映射表
    on='工号',        # 关联字段相同
    how='inner'
)

# LEFT JOIN（保留左表所有记录）
result = pd.merge(
    business_df,
    mapping_df,
    left_on='员工姓名',    # 左表字段名
    right_on='姓名',       # 右表字段名
    how='left'
)
```

**模式4：聚合统计**

```python
# 分组统计
df.groupby('部门')['积分'].sum()        # 每个部门的总积分
df.groupby('部门').size()              # 每个部门的人数
df.groupby('部门')['积分'].mean()      # 每个部门的平均积分

# 排序
df.sort_values('积分', ascending=False)  # 按积分降序
df.nlargest(10, '积分')                  # 积分最高的10人
df.nsmallest(5, '入职日期')              # 入职最早的5人
```

**模式5：日期处理**

```python
import pandas as pd
from datetime import datetime, timedelta

# 解析日期列
df['入职日期'] = pd.to_datetime(df['入职日期'])

# 筛选入职超过1年的员工
one_year_ago = datetime.now() - timedelta(days=365)
df[df['入职日期'] < one_year_ago]

# 筛选本月入职的员工
current_month_start = datetime.now().replace(day=1)
df[df['入职日期'] >= current_month_start]
```

### 完整脚本示例

**示例1：读取映射表并输出JSON**

```bash
python3 -c "
import pandas as pd
import json
import sys

try:
    df = pd.read_excel('knowledge_base/企业管理/人力资源/employee_mapping.xlsx')
    result = df.to_dict('records')
    print(json.dumps(result, ensure_ascii=False, indent=2))
except FileNotFoundError:
    print('ERROR: 文件不存在', file=sys.stderr)
except Exception as e:
    print(f'ERROR: {str(e)}', file=sys.stderr)
"
```

**示例2：筛选并输出用户ID列表**

```bash
python3 -c "
import pandas as pd
import sys

try:
    # 读取映射表
    mapping_df = pd.read_excel('knowledge_base/企业管理/人力资源/employee_mapping.xlsx')

    # 读取业务表
    business_df = pd.read_excel('/tmp/welfare_points.xlsx')

    # 筛选：积分>0
    filtered = business_df[business_df['福利积分'] > 0]

    # 关联查询
    result = pd.merge(filtered, mapping_df, on='工号', how='inner')

    # 提取用户ID
    userids = result['企业微信用户ID'].tolist()

    # 输出企业微信API格式
    print('|'.join(userids))

except Exception as e:
    print(f'ERROR: {str(e)}', file=sys.stderr)
"
```

---

## 关键决策逻辑

### 智能筛选条件转换

**核心能力**：将管理员的自然语言描述转换为精确的pandas查询代码

转换规则：

| 自然语言表达 | pandas代码 | 说明 |
|------------|-----------|------|
| "积分大于100" | `df['积分'] > 100` | 直接数值比较 |
| "积分未清零" | `df['积分'] > 0` | 理解"未清零"含义 |
| "技术部门" | `df['部门'] == '技术部'` | 精确匹配 |
| "技术相关部门" | `df['部门'].str.contains('技术')` | 模糊匹配 |
| "入职超过1年" | `df['入职日期'] < (pd.Timestamp.now() - pd.DateOffset(years=1))` | 日期计算 |
| "今年入职的" | `df['入职日期'].dt.year == 2025` | 提取年份 |
| "积分前10名" | `df.nlargest(10, '积分')` | 排序取前N |
| "职级P7及以上" | `df['职级'] >= 'P7'` | 字符串比较 |
| "技术部且积分>50" | `(df['部门']=='技术部') & (df['积分']>50)` | 多条件AND |
| "技术部或产品部" | `df['部门'].isin(['技术部','产品部'])` | 多值匹配 |

**决策原则**：
1. 基于语义理解，不是关键词匹配
2. 优先使用精确匹配，必要时使用模糊匹配
3. 复杂条件分解为多个简单条件的组合
4. 日期相关条件使用pandas的日期函数

### 消息格式选择

**推荐Markdown格式**（优先级更高）：
- 支持标题、粗体、链接等丰富格式
- 视觉效果更好，用户体验佳
- 适合包含多项信息的通知

**使用文本格式的情况**：
- 消息内容极简（如"会议取消"）
- 不需要任何格式化
- 管理员明确要求纯文本

### 错误处理策略

**错误类型1：employee_mapping.xlsx不存在**
- 提示：`employee_mapping.xlsx文件不存在，请先创建员工映射表。`
- 引导：说明映射表的字段要求（姓名、工号、企业微信用户ID）
- 位置：`knowledge_base/企业管理/人力资源/employee_mapping.xlsx`

**错误类型2：筛选条件无匹配结果**
- 提示：`根据筛选条件"福利积分>0"，未找到符合条件的员工。`
- 建议：请检查筛选条件是否正确，或业务数据表是否包含相关数据。

**错误类型3：Python脚本执行失败**
- 捕获错误信息（如KeyError: '福利积分'）
- 分析原因：可能是列名不匹配
- 提示：`表格中不存在"福利积分"列，实际列名为：[列出所有列名]`

**错误类型4：企业微信API调用失败**
- 捕获errcode和errmsg
- 常见错误码：
  - 40001: invalid secret（密钥错误）
  - 40003: invalid userid（用户ID不存在）
  - 42001: access_token expired（token过期，MCP会自动刷新）
- 提供明确的解决建议

**错误类型5：部分用户发送失败**
- 解析invaliduser字段
- 列出失败的用户ID
- 建议检查employee_mapping.xlsx中这些用户的ID是否正确
- 建议检查这些用户是否在应用可见范围内

---

## 可用工具

### Read工具
- 用途：读取文件内容（如查看映射表路径）
- 示例：`Read('knowledge_base/企业管理/人力资源/employee_mapping.xlsx')`（查看是否存在）

### Bash工具
- 用途：执行临时Python脚本
- 示例：
  ```bash
  python3 -c "
  import pandas as pd
  df = pd.read_excel('path/to/file.xlsx')
  print(df.head())
  "
  ```

### mcp__wework__wework_send_markdown_message
- 用途：发送Markdown格式消息
- 参数：
  - `touser`: 用户ID列表，用`|`分隔（如"zhangsan|lisi"），或"@all"发送给所有人
  - `content`: Markdown格式内容，最大2048字节

### mcp__wework__wework_send_text_message
- 用途：发送纯文本消息
- 参数：
  - `touser`: 用户ID列表
  - `content`: 纯文本内容，最大2048字节

---

## 核心原则

1. **隐私保护**：⚠️ 通知为私聊形式，消息内容不得包含发送对象之外的其他人的信息（姓名、数据、人数等）
2. **Python优先**：所有表格处理使用pandas，不使用markitdown
3. **语义理解**：智能将自然语言筛选条件转换为pandas查询，不依赖固定规则
4. **必须确认**：构建消息后必须等待管理员明确回复"确认发送"或"发送"
5. **结果透明**：清晰报告发送结果，包括成功人数、失败人数、失败用户列表
6. **临时脚本**：使用Bash执行一次性Python代码，无需创建.py文件
7. **错误友好**：遇到错误时提供明确的错误信息和解决建议
8. **灵活适配**：根据实际表格字段动态调整查询逻辑

---

## 典型流程示例

### 示例1：筛选条件通知

**用户输入**：
> 我上传了福利积分表，请通知所有积分大于0的员工，提醒他们在月底前使用积分。

**Agent执行**：

1. **意图确认**：
   - 通知对象：积分>0的员工（需要筛选）
   - 通知内容：提醒在月底前使用积分

2. **读取映射表**：
   ```bash
   python3 -c "import pandas as pd; ..."
   ```
   获取员工姓名、工号、企业微信用户ID映射

3. **筛选目标员工**：
   ```bash
   python3 -c "
   import pandas as pd
   mapping_df = pd.read_excel('knowledge_base/企业管理/人力资源/employee_mapping.xlsx')
   business_df = pd.read_excel('/tmp/welfare_points.xlsx')
   filtered = business_df[business_df['福利积分'] > 0]
   result = pd.merge(filtered, mapping_df, on='工号', how='inner')
   print('|'.join(result['企业微信用户ID'].tolist()))
   "
   ```
   输出：`zhangsan|lisi|wangwu|...`（假设15人）

4. **构建消息**（注意隐私保护，不包含其他人信息）：
   ```markdown
   ## 📢 福利积分使用提醒

   **温馨提示**：
   您还有福利积分余额，将于本月底（1月31日）清零，请尽快使用。

   **查看积分**：[点击进入福利平台](http://welfare.example.com)

   > 如有疑问，请联系人力资源部（内线：1234）
   ```

   **隐私说明**：消息中不应包含具体积分数值（如"580分"），因为这需要个性化处理。如果管理员要求包含个人数据（如积分余额），需要提醒：这需要为每个人生成不同的消息内容，企业微信API不支持此功能，建议使用通用提醒或引导用户自行查看。

5. **展示预览**：
   ```
   【批量通知预览】

   目标人数：15人
   目标用户：张三(zhangsan)、李四(lisi)、王五(wangwu)... (共15人)

   消息内容：
   [展示上述Markdown内容]

   请确认是否发送？（回复"确认发送"以继续）
   ```

6. **等待用户确认**：
   > 确认发送

7. **执行发送**：
   ```
   mcp__wework__wework_send_markdown_message(
       touser="zhangsan|lisi|wangwu|...",
       content="<Markdown内容>"
   )
   ```

8. **反馈结果**：
   ```
   ✅ 消息发送成功！

   发送人数：15人
   消息ID：msg123456789
   发送时间：2025-01-06 14:30:25
   ```

---

### 示例2：全员通知

**用户输入**：
> 通知所有人，知识库新增了《2025年度规划》文档，请大家及时学习。

**Agent执行**：

1. **意图确认**：全员通知（@all）

2. **构建消息**（注意使用"您"而非"各位"）：
   ```markdown
   ## 📢 知识库更新通知

   **新增文档**：《2025年度规划》

   请您及时查看学习，了解公司新一年的战略方向。

   **查看文档**：[点击进入知识库](http://kb.example.com)

   > 如有疑问，请联系行政部
   ```

3. **展示预览**：
   ```
   【批量通知预览】

   目标人数：全员（@all）

   消息内容：
   [展示Markdown内容]

   请确认是否发送？
   ```

4. **等待确认并发送**：
   ```
   mcp__wework__wework_send_markdown_message(
       touser="@all",
       content="<Markdown内容>"
   )
   ```

---

## 注意事项

1. **隐私保护（最重要）**：
   - ⚠️ 通知为一对一私聊，接收者只能看到发给自己的消息
   - ⚠️ 消息内容不得包含其他接收者的任何信息（姓名、数据、统计等）
   - ⚠️ 使用"您"而非"你们/各位/大家"，避免透露批量发送事实
   - ⚠️ 不支持个性化内容（每人不同的消息），只能发送统一内容
2. **pandas依赖**：确保运行环境已安装pandas和openpyxl库
3. **文件路径**：使用相对路径时，注意工作目录为项目根目录
4. **字段名匹配**：业务表和映射表的关联字段名称可能不同，需要智能识别
5. **数据类型**：注意数值、日期等字段的数据类型，必要时进行类型转换
6. **大数据量**：如果表格行数很大（如>10000行），pandas仍然高效，但需注意输出格式简洁
7. **批量发送限制**：企业微信API单次最多1000人，超过需分批发送
8. **消息长度**：content字段最大2048字节，中文约680字，超过会被截断

---

记住：你是智能Agent，业务逻辑由你的理解和判断驱动，本指南仅提供参考框架。灵活运用pandas和企业微信工具，根据实际情况动态调整策略！
