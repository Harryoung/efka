---
name: excel-parser
description: Smart Excel/CSV file parsing with intelligent routing based on file complexity analysis. Analyzes file structure (merged cells, row count, table layout) using lightweight metadata scanning, then recommends optimal processing strategy - either high-speed Pandas mode for standard tables or semantic HTML mode for complex reports. Use when processing Excel/CSV files with unknown or varying structure where optimization between speed and accuracy is needed.
---

# Excel Parser

## Overview

Provide intelligent routing strategies for parsing Excel/CSV files by analyzing complexity and choosing the optimal processing path. The skill implements a "Scout Pattern" that scans file metadata before processing to balance speed (Pandas) with accuracy (semantic extraction).

## Core Philosophy: Scout Pattern

Before processing data, deploy a lightweight "scout" to analyze file metadata and make intelligent routing decisions:

1. **Metadata Scanning** - Use `openpyxl` to scan file structure without loading data
2. **Complexity Scoring** - Calculate score based on merged cells, row count, and layout
3. **Path Selection** - Choose between Pandas (fast) or HTML (accurate) processing
4. **Optimized Execution** - Execute with the most appropriate tool for the file type

**Key Principle**: "LLM handles metadata decisions, Pandas/HTML processes bulk data"

## When to Use This Skill

Use excel-parser when:
- Processing Excel/CSV files with unknown structure or varying complexity
- Handling files ranging from simple data tables to complex financial reports
- Need to optimize between processing speed and extraction accuracy
- Working with files that may contain merged cells, multi-level headers, or irregular layouts

**Skip this skill when:**
- File structure is already known and documented
- Processing simple, well-structured tables with confirmed format
- Using predefined scripts for specific file formats

## Processing Workflow

### Step 1: Analyze File Complexity

Use the `scripts/complexity_analyzer.py` to scan file metadata:

```bash
python scripts/complexity_analyzer.py <file_path> [sheet_name]
```

**What it analyzes** (without loading data):
- Merged cell distribution (shallow vs deep in the table)
- Row count and data continuity
- Empty row interruptions (indicates multi-table layouts)

**Output** (JSON format):
```json
{
  "is_complex": false,
  "recommended_strategy": "pandas",
  "reasons": ["No deep merges detected", "行数过多 (>1000), 强制使用 Pandas 模式"],
  "stats": {
    "total_rows": 5000,
    "deep_merges": 0,
    "empty_interruptions": 0
  }
}
```

### Step 2: Route to Optimal Strategy

Based on complexity analysis:

- **is_complex = false** → Use **Path A (Pandas Standard Mode)**
- **is_complex = true** → Use **Path B (HTML Semantic Mode)**

### Step 3: Execute Processing

Follow the selected path's workflow to extract data.

## Complexity Scoring Rules

### Rule 1: Deep Merged Cells
- **Condition**: Merged cells appearing beyond row 5
- **Interpretation**: Complex table structure (not just header formatting)
- **Decision**: Mark as complex if >2 deep merges detected
- **Example**: Financial reports with merged category labels in data region

### Rule 2: Empty Row Interruptions
- **Condition**: Multiple empty rows within the table
- **Interpretation**: Multiple sub-tables in single sheet
- **Decision**: Mark as complex if >2 empty row interruptions found
- **Example**: Summary table + detail table in one sheet

### Rule 3: Row Count Override
- **Condition**: Total rows >1000
- **Interpretation**: Too large for HTML processing (token explosion)
- **Decision**: Force Pandas mode regardless of complexity
- **Rationale**: HTML conversion would exceed token limits

### Rule 4: Default (Standard Table)
- **Condition**: No deep merges, continuous data, moderate size
- **Interpretation**: Standard data table
- **Decision**: Use Pandas for optimal speed

## Path A: Pandas Standard Mode

**When**: Simple/large tables (most common case)

**Strategy**: Let LLM analyze ONLY the first 20 rows to determine header position, then use Pandas to read full data at native speed.

**Workflow**:

1. **Sample First 20 Rows**
   ```python
   import pandas as pd

   df_sample = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=20)
   csv_sample = df_sample.to_csv(index=False)
   ```

2. **LLM Analyzes Header Position**

   Prompt template:
   ```
   You are a Pandas expert. Analyze the following first 20 rows of an Excel file (in CSV format):

   {csv_sample}

   Task: Identify the true header row index (0-based). If row 0 is the header, return 0.
   If the first two rows are titles and row 2 is the header, return 2.

   Return JSON format:
   {
       "header_row": <int>,
       "explanation": "<reasoning>"
   }
   ```

3. **Parse LLM Response**
   ```python
   import json, re

   json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
   config = json.loads(json_match.group())
   header_idx = config.get("header_row", 0)
   ```

4. **Read Full Data with Correct Parameters**
   ```python
   full_df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_idx)
   print(f"Successfully loaded DataFrame: {full_df.shape}")
   ```

**Token Cost**: ~500 tokens (only 20 rows analyzed by LLM)
**Processing Speed**: Very fast (Pandas native speed)

## Path B: HTML Semantic Mode

**When**: Complex/irregular tables (merged cells, multi-level headers)

**Strategy**: Convert to semantic HTML preserving structure (rowspan/colspan), then let LLM extract data understanding the visual layout.

**Workflow**:

1. **Convert to Semantic HTML**
   ```python
   import openpyxl
   from openpyxl.utils import get_column_letter

   wb = openpyxl.load_workbook(file_path, data_only=True)
   sheet = wb[sheet_name]

   html_parts = ['<table border="1">']

   # Track merged cell spans
   merge_map = {}
   for merge in sheet.merged_cells.ranges:
       min_col, min_row, max_col, max_row = merge.bounds
       merge_map[(min_row, min_col)] = {
           'rowspan': max_row - min_row + 1,
           'colspan': max_col - min_col + 1
       }

   # Build HTML with rowspan/colspan
   for row_idx, row in enumerate(sheet.iter_rows(), start=1):
       html_parts.append('<tr>')
       for col_idx, cell in enumerate(row, start=1):
           # Skip cells that are part of a merge (not the top-left)
           if any((row_idx, col_idx) in range(...) for merge in sheet.merged_cells.ranges):
               if (row_idx, col_idx) not in merge_map:
                   continue

           # Get cell value
           value = cell.value or ''

           # Add rowspan/colspan if this is a merged cell origin
           attrs = ''
           if (row_idx, col_idx) in merge_map:
               span = merge_map[(row_idx, col_idx)]
               if span['rowspan'] > 1:
                   attrs += f' rowspan="{span["rowspan"]}"'
               if span['colspan'] > 1:
                   attrs += f' colspan="{span["colspan"]}"'

           html_parts.append(f'<td{attrs}>{value}</td>')
       html_parts.append('</tr>')

   html_parts.append('</table>')
   html_content = '\n'.join(html_parts)
   ```

2. **LLM Extracts Structured Data**

   Prompt template:
   ```
   Analyze the following HTML table and extract key data as JSON.
   Pay attention to merged cells (rowspan/colspan) which indicate hierarchical headers or grouped data.

   HTML (first 2000 chars):
   {html_content[:2000]}

   Task: Extract the data preserving the semantic structure. Return JSON format suitable for the data type.
   ```

3. **Parse and Return**
   ```python
   import json, re

   json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
   extracted_data = json.loads(json_match.group())
   ```

**Token Cost**: Higher (full HTML structure analyzed)
**Processing Speed**: Slower (LLM semantic extraction)
**Use Case**: Only for small, complex files where Pandas would fail

## Implementation Code Template

Complete executable example combining both paths:

```python
import openpyxl
from openpyxl.utils import range_boundaries
import pandas as pd
import json
import sys

class SmartExcelRouter:
    def __init__(self, file_path):
        self.file_path = file_path
        self.wb = openpyxl.load_workbook(file_path, read_only=False, data_only=True)

    def analyze_sheet_complexity(self, sheet_name):
        """Scout function: Calculate complexity score without loading data."""
        sheet = self.wb[sheet_name]

        max_row = sheet.max_row
        merged_ranges = sheet.merged_cells.ranges

        # Analyze merge distribution
        deep_merges = 0
        for merge in merged_ranges:
            min_col, min_row, max_col, max_row_merge = range_boundaries(str(merge))
            if min_row > 5:  # Beyond header region
                deep_merges += 1

        # Check empty row interruptions
        empty_interruptions = 0
        if max_row < 200:  # Only check short tables
            for row in sheet.iter_rows(min_row=1, max_row=max_row):
                if all(cell.value is None for cell in row):
                    empty_interruptions += 1

        # Apply scoring rules
        is_complex = False
        reasons = []

        if deep_merges > 2:
            is_complex = True
            reasons.append(f"检测到数据区域有 {deep_merges} 处合并单元格")

        if max_row < 300 and empty_interruptions > 2:
            is_complex = True
            reasons.append("检测到多处空行,疑为多子表布局")

        if max_row > 1000:
            is_complex = False
            reasons = ["行数过多 (>1000), 强制使用 Pandas 模式"]

        if not is_complex and not reasons:
            reasons.append("结构规则,未检测到复杂布局")

        return {
            "is_complex": is_complex,
            "recommended_strategy": "html" if is_complex else "pandas",
            "reasons": reasons,
            "stats": {
                "total_rows": max_row,
                "deep_merges": deep_merges,
                "empty_interruptions": empty_interruptions
            }
        }

    def process_pandas_mode(self, sheet_name):
        """Path A: Read first 20 rows, LLM determines header, Pandas loads full data."""
        print(f"[Pandas Mode] Processing {sheet_name}...")

        # Step 1: Sample
        df_sample = pd.read_excel(self.file_path, sheet_name=sheet_name, header=None, nrows=20)
        csv_sample = df_sample.to_csv(index=False)

        # Step 2: LLM analyzes (you need to implement call_llm function)
        # For now, assume header is at row 0
        header_idx = 0  # Replace with LLM analysis

        # Step 3: Full read
        full_df = pd.read_excel(self.file_path, sheet_name=sheet_name, header=header_idx)
        print(f"   Loaded DataFrame: {full_df.shape}")

        return full_df

    def process_html_mode(self, sheet_name):
        """Path B: Convert to HTML, LLM extracts semantically."""
        print(f"[HTML Mode] Processing {sheet_name}...")

        # Implementation would include HTML conversion as shown above
        # For brevity, returning placeholder
        return {"message": "Use HTML conversion code from Path B section"}

# Usage
if __name__ == "__main__":
    router = SmartExcelRouter("example.xlsx")

    for sheet_name in router.wb.sheetnames:
        analysis = router.analyze_sheet_complexity(sheet_name)
        print(f"\nSheet: {sheet_name}")
        print(f"Strategy: {analysis['recommended_strategy']}")
        print(f"Reasons: {analysis['reasons']}")

        if analysis['is_complex']:
            router.process_html_mode(sheet_name)
        else:
            router.process_pandas_mode(sheet_name)
```

## Best Practices

### 1. Trust the Scout
Always run complexity analysis before processing. The metadata scan is fast (<1 second) and prevents wasted effort on wrong approach.

### 2. Respect the Row Count Rule
Never attempt HTML mode on files >1000 rows. Token limits will cause failures.

### 3. Pandas First for Unknown Files
When in doubt, try Pandas mode first. It fails fast and clearly when structure is incompatible.

### 4. Cache Analysis Results
If processing multiple sheets from same file, run analysis once and cache results.

### 5. Preserve Original Files
Never modify the original Excel file during analysis or processing.

## Dependencies

Required Python packages:
- `openpyxl` - Metadata scanning and Excel file manipulation
- `pandas` - High-speed data reading and manipulation
- Access to Bash tool for executing Python scripts

## Resources

This skill includes:
- `scripts/complexity_analyzer.py` - Standalone executable for complexity analysis
- Implementation code templates in this document for both processing paths
