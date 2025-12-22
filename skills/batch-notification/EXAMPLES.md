# 批量通知示例

## 示例1：筛选条件通知

**用户输入**：
> 我上传了福利积分表，请通知所有积分大于0的用户，提醒他们在月底前使用积分。

**执行流程**：

1. **意图确认**：通知对象=积分>0的用户，内容=提醒月底前使用

2. **读取映射表**并获取 姓名/工号 → userid 映射

3. **筛选目标用户**：
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

4. **构建消息**（隐私保护，不包含其他人信息）：
```markdown
## 福利积分使用提醒

**温馨提示**：
您还有福利积分余额，将于本月底（1月31日）清零，请尽快使用。

**查看积分**：[点击进入福利平台](http://welfare.example.com)

> 如有疑问，请联系人力资源部（内线：1234）
```

5. **展示预览并等待确认**

6. **执行发送**：
```python
mcp__{channel}__send_markdown_message(
    touser="zhangsan|lisi|wangwu|...",
    content="<消息内容>"
)
```

7. **反馈结果**

---

## 示例2：全员通知

**用户输入**：
> 通知所有人，知识库新增了《2025年度规划》文档，请大家及时学习。

**执行流程**：

1. **意图确认**：全员通知（@all）

2. **构建消息**（使用"您"而非"各位"）：
```markdown
## 知识库更新通知

**新增文档**：《2025年度规划》

请您及时查看学习，了解公司新一年的战略方向。

**查看文档**：[点击进入知识库](http://kb.example.com)

> 如有疑问，请联系行政部
```

3. **展示预览**

4. **等待确认并发送**：
```python
mcp__{channel}__send_markdown_message(
    touser="@all",
    content="<消息内容>"
)
```

---

## 示例3：指定人员通知

**用户输入**：
> 通知张三、李四、王五参加下周一的培训

**执行流程**：

1. **意图确认**：指定人员通知

2. **查询 userid**：
```bash
python3 -c "
import pandas as pd
mapping_df = pd.read_excel('knowledge_base/企业管理/人力资源/user_mapping.xlsx')
target = mapping_df[mapping_df['姓名'].isin(['张三', '李四', '王五'])]
print('|'.join(target['企业微信用户ID'].tolist()))
"
```

3. **构建消息并发送**

---

## 错误处理示例

### user_mapping.xlsx 不存在

```
user_mapping.xlsx 文件不存在，请先创建用户映射表。

映射表需包含以下字段：
- 姓名
- 工号
- 企业微信用户ID

位置：knowledge_base/企业管理/人力资源/user_mapping.xlsx
```

### 筛选无结果

```
根据筛选条件"福利积分>0"，未找到符合条件的用户。

请检查：
1. 筛选条件是否正确
2. 业务数据表是否包含相关数据
```

### 列名不匹配

```
表格中不存在"福利积分"列。

实际列名：['姓名', '工号', '积分余额', '部门']

请确认正确的列名后重试。
```
