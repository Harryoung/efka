# Skills

Agent skills use Claude Agent SDK native loading mechanism `setting_sources=["project"]`.

## Location

- Source code: `skills/`
- Runtime: `knowledge_base/.claude/skills/` (automatically copied at startup)

Skills are referenced by name in Agent prompts and automatically loaded by SDK.

## Available Skills

| Skill | Function |
|-------|----------|
| batch-notification | Batch user notification workflow |
| document-conversion | DOC/PDF/PPT → Markdown conversion |
| excel-parser | Smart Excel/CSV parsing |
| expert-routing | Domain expert routing |
| large-file-toc | Large file table of contents generation |
| satisfaction-feedback | User satisfaction feedback |

## Document Conversion

Direct call:
```bash
python skills/document-conversion/scripts/smart_convert.py <input_file> --json-output
```

Supported formats: DOCX, PDF (electronic/scanned), PPTX, TXT
