# 专家路由工作流

## Step 1: 领域识别

基于问题语义识别所属领域：

```python
# 领域关键词映射（示例）
domain_keywords = {
    "薪酬福利": ["薪资", "工资", "调薪", "奖金", "福利", "社保", "公积金"],
    "考勤管理": ["请假", "考勤", "打卡", "加班", "调休", "年假"],
    "招聘培训": ["入职", "新员工", "培训", "面试", "招聘", "转正"],
    "员工关系": ["合同", "劳动", "离职", "辞职", "仲裁", "纠纷"],
    "IT支持": ["系统", "账号", "密码", "电脑", "网络", "权限"],
}
```

**判断原则**：
- 基于语义理解，不是关键词匹配
- 如果无法确定领域，使用"默认负责人"

---

## Step 2: 查询领域负责人

使用 pandas 查询 domain_experts.xlsx：

```bash
python3 -c "
import pandas as pd
import json

domain = '薪酬福利'  # 替换为识别出的领域

df = pd.read_excel('knowledge_base/企业管理/人力资源/domain_experts.xlsx')
result = df[df['工作领域'] == domain]

if result.empty:
    # 使用默认负责人
    result = df[df['工作领域'] == '默认负责人']

print(json.dumps(result[['姓名', 'userid', '工作领域']].to_dict('records'), ensure_ascii=False))
"
```

**输出示例**：
```json
[{"姓名": "李明", "userid": "liming", "工作领域": "薪酬福利"}]
```

---

## Step 3: 通知专家

使用 IM MCP 发送消息给专家：

```python
mcp__{channel}__send_markdown_message(
    touser="{expert_userid}",
    content="""## 【用户咨询】

用户 **{user_name}**({user_id}) 提问：

> {question}

<font color="warning">该问题在知识库中暂无答案</font>，请您回复。我会将您的回复转发给该用户。

> 建议您及时补充相关文档到知识库。"""
)
```

---

## Step 4: 通知用户等待

发送等待消息给用户：

```python
mcp__{channel}__send_markdown_message(
    touser="{user_id}",
    content="""**{user_name}**您好！

已为您联系<font color="info">{domain}</font>负责人 **{expert_name}**，请稍等，会尽快回复您。"""
)
```

---

## Step 5: 输出元数据

输出包含专家路由信息的元数据：

```metadata
{
  "key_points": ["问题无法解答", "已联系领域专家"],
  "answer_source": "expert",
  "session_status": "active",
  "confidence": 0.0,
  "expert_routed": true,
  "expert_userid": "liming",
  "expert_name": "李明",
  "domain": "薪酬福利",
  "original_question": "如何申请调薪？"
}
```

---

## domain_experts.xlsx 格式

| 姓名 | userid | 工作领域 |
|-----|--------|---------|
| 李明 | liming | 薪酬福利 |
| 王芳 | wangfang | 考勤管理 |
| 张伟 | zhangwei | 招聘培训 |
| 赵六 | zhaoliu | 员工关系 |
| 陈默 | chenmo | 默认负责人 |

**位置**：`knowledge_base/企业管理/人力资源/domain_experts.xlsx`
