# pandas Query Patterns

## Natural Language → pandas Conversion

| Natural Language | pandas Code |
|-----------------|-------------|
| "Points greater than 100" | `df['积分'] > 100` |
| "Points not zero" | `df['积分'] > 0` |
| "Tech department" | `df['部门'] == '技术部'` |
| "Tech-related departments" | `df['部门'].str.contains('技术')` |
| "Joined over 1 year" | `df['入职日期'] < (pd.Timestamp.now() - pd.DateOffset(years=1))` |
| "Joined this year" | `df['入职日期'].dt.year == 2025` |
| "Top 10 points" | `df.nlargest(10, '积分')` |
| "Level P7 and above" | `df['职级'] >= 'P7'` |

## Single Condition Filtering

```python
# Numeric comparison
df[df['积分'] > 100]

# Exact match
df[df['部门'] == '技术部']

# List match
df[df['姓名'].isin(['张三', '李四'])]

# Fuzzy match
df[df['部门'].str.contains('技术')]
```

## Multiple Condition Filtering

```python
# AND
df[(df['积分'] > 0) & (df['部门'] == '技术部')]

# OR
df[(df['入职日期'] < '2024-01-01') | (df['职级'] >= 'P7')]

# Complex combination
df[
    (df['积分'] > 100) &
    (df['部门'].isin(['技术部', '产品部'])) &
    (df['入职日期'] >= '2023-01-01')
]
```

## JOIN Query

```python
# INNER JOIN
result = pd.merge(
    business_df,
    mapping_df,
    on='工号',
    how='inner'
)

# LEFT JOIN (different field names)
result = pd.merge(
    business_df,
    mapping_df,
    left_on='用户姓名',
    right_on='姓名',
    how='left'
)
```

## Aggregation Statistics

```python
# Group statistics
df.groupby('部门')['积分'].sum()      # Total points per department
df.groupby('部门').size()            # Count per department
df.groupby('部门')['积分'].mean()    # Average per department

# Sorting
df.sort_values('积分', ascending=False)
df.nlargest(10, '积分')              # Top 10
df.nsmallest(5, '入职日期')          # Earliest 5
```

## Date Processing

```python
from datetime import datetime, timedelta

# Parse date column
df['入职日期'] = pd.to_datetime(df['入职日期'])

# Joined over 1 year ago
one_year_ago = datetime.now() - timedelta(days=365)
df[df['入职日期'] < one_year_ago]

# Joined this month
current_month = datetime.now().replace(day=1)
df[df['入职日期'] >= current_month]
```

## Complete Script Template

```bash
python3 -c "
import pandas as pd
import sys

try:
    # Read mapping table
    mapping_df = pd.read_excel('knowledge_base/企业管理/人力资源/user_mapping.xlsx')

    # Read business table
    business_df = pd.read_excel('/tmp/data.xlsx')

    # Filter
    filtered = business_df[business_df['福利积分'] > 0]

    # JOIN
    result = pd.merge(filtered, mapping_df, on='工号', how='inner')

    # Output
    print('|'.join(result['企业微信用户ID'].tolist()))

except Exception as e:
    print(f'ERROR: {str(e)}', file=sys.stderr)
"
```
