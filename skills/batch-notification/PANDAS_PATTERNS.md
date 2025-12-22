# pandas 查询模式

## 自然语言 → pandas 转换

| 自然语言 | pandas 代码 |
|---------|------------|
| "积分大于100" | `df['积分'] > 100` |
| "积分未清零" | `df['积分'] > 0` |
| "技术部门" | `df['部门'] == '技术部'` |
| "技术相关部门" | `df['部门'].str.contains('技术')` |
| "入职超过1年" | `df['入职日期'] < (pd.Timestamp.now() - pd.DateOffset(years=1))` |
| "今年入职的" | `df['入职日期'].dt.year == 2025` |
| "积分前10名" | `df.nlargest(10, '积分')` |
| "职级P7及以上" | `df['职级'] >= 'P7'` |

## 单条件筛选

```python
# 数值比较
df[df['积分'] > 100]

# 精确匹配
df[df['部门'] == '技术部']

# 列表匹配
df[df['姓名'].isin(['张三', '李四'])]

# 模糊匹配
df[df['部门'].str.contains('技术')]
```

## 多条件筛选

```python
# AND
df[(df['积分'] > 0) & (df['部门'] == '技术部')]

# OR
df[(df['入职日期'] < '2024-01-01') | (df['职级'] >= 'P7')]

# 复杂组合
df[
    (df['积分'] > 100) &
    (df['部门'].isin(['技术部', '产品部'])) &
    (df['入职日期'] >= '2023-01-01')
]
```

## JOIN 查询

```python
# INNER JOIN
result = pd.merge(
    business_df,
    mapping_df,
    on='工号',
    how='inner'
)

# LEFT JOIN（字段名不同）
result = pd.merge(
    business_df,
    mapping_df,
    left_on='用户姓名',
    right_on='姓名',
    how='left'
)
```

## 聚合统计

```python
# 分组统计
df.groupby('部门')['积分'].sum()      # 每部门总积分
df.groupby('部门').size()            # 每部门人数
df.groupby('部门')['积分'].mean()    # 每部门平均

# 排序
df.sort_values('积分', ascending=False)
df.nlargest(10, '积分')              # 前10
df.nsmallest(5, '入职日期')          # 最早5人
```

## 日期处理

```python
from datetime import datetime, timedelta

# 解析日期列
df['入职日期'] = pd.to_datetime(df['入职日期'])

# 入职超过1年
one_year_ago = datetime.now() - timedelta(days=365)
df[df['入职日期'] < one_year_ago]

# 本月入职
current_month = datetime.now().replace(day=1)
df[df['入职日期'] >= current_month]
```

## 完整脚本模板

```bash
python3 -c "
import pandas as pd
import sys

try:
    # 读取映射表
    mapping_df = pd.read_excel('knowledge_base/企业管理/人力资源/user_mapping.xlsx')

    # 读取业务表
    business_df = pd.read_excel('/tmp/data.xlsx')

    # 筛选
    filtered = business_df[business_df['福利积分'] > 0]

    # JOIN
    result = pd.merge(filtered, mapping_df, on='工号', how='inner')

    # 输出
    print('|'.join(result['企业微信用户ID'].tolist()))

except Exception as e:
    print(f'ERROR: {str(e)}', file=sys.stderr)
"
```
