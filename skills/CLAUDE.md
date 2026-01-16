# Skills

Agent skills 使用 Claude Agent SDK 原生加载机制 `setting_sources=["project"]`。

## Location

- 源码: `skills/`
- 运行时: `knowledge_base/.claude/skills/` (启动时自动复制)

Skills 在 Agent prompts 中按名称引用，由 SDK 自动加载。

## Available Skills

| Skill | 功能 |
|-------|------|
| batch-notification | 批量用户通知工作流 |
| document-conversion | DOC/PDF/PPT → Markdown 转换 |
| excel-parser | 智能 Excel/CSV 解析 |
| expert-routing | 领域专家路由 |
| large-file-toc | 大文件目录生成 |
| satisfaction-feedback | 用户满意度反馈 |

## Document Conversion

直接调用:
```bash
python skills/document-conversion/scripts/smart_convert.py <input_file> --json-output
```

支持格式: DOCX, PDF (电子/扫描), PPTX, TXT
