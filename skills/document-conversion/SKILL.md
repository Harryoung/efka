---
name: document-conversion
description: 将 DOC/DOCX/PDF/PPT/PPTX 文档转换为 Markdown 格式。自动检测 PDF 类型（电子版/扫描版），提取图片到独立目录。当管理员入库非 Markdown 文档时使用此 Skill。触发条件：入库 DOC/DOCX/PDF/PPT/PPTX 格式文件。
---

# 文档格式转换

将各种文档格式转换为 Markdown，用于知识库入库。

## 支持格式

| 格式 | 处理方式 |
|-----|---------|
| DOCX | Pandoc 转换，保留格式和图片 |
| DOC | LibreOffice → DOCX → Pandoc |
| PDF 电子版 | PyMuPDF4LLM 快速转换 |
| PDF 扫描版 | PaddleOCR-VL 在线 OCR |
| PPTX | pptx2md 专业转换 |
| PPT | LibreOffice → PPTX → pptx2md |

## 调用方式

```bash
python .claude/skills/document-conversion/scripts/smart_convert.py \
    <temp_path> \
    --original-name "<原始文件名>" \
    --json-output
```

**参数说明**：
- `<temp_path>`: 临时文件路径（如 `/tmp/kb_upload_xxx.pptx`）
- `--original-name`: **必须传入原始文件名**，用于生成正确的图片目录名
- `--json-output`: 输出 JSON 格式结果

## 输出格式

```json
{
  "success": true,
  "markdown_file": "/path/to/output.md",
  "images_dir": "原始文件名_images",
  "image_count": 5,
  "input_file": "/path/to/input.pptx"
}
```

## 处理流程

1. 执行转换命令（必须使用 `--original-name` 和 `--json-output`）
2. 解析 JSON 输出，检查 `success` 字段
3. 如果 `success: false`，报告错误并结束
4. 如果 `success: true`，记录生成的文件路径和图片目录

## 重要提示

- 图片目录使用原始文件名命名（如 `培训资料_images/`）
- 不传 `--original-name` 会导致图片引用路径错误
- PDF 类型自动检测，扫描版处理较慢（几十秒到几分钟）

## 格式详情

各格式的详细处理说明，见 [FORMATS.md](FORMATS.md)
