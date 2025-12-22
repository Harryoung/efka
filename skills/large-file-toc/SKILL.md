---
name: large-file-toc
description: 为大文件生成目录概要。当入库的 Markdown 文件超过阈值（默认30KB）时，提取标题结构创建导航文件。触发条件：Markdown 文件大小 >= 30KB。
---

# 大文件目录概要生成

为大型 Markdown 文件生成目录概要，便于用户快速导航。

## 适用条件

- Markdown 文件大小 >= 30KB
- 入库阶段5（写入和更新）自动触发

## 快速流程

1. **提取标题**：使用 Grep 搜索 `^#+\s+.*$`
2. **生成概要**：创建 `contents_overview/{文件名}_overview.md`
3. **更新 README**：记录概要文件路径

## Grep 提取标题

```bash
grep -n '^#' knowledge_base/path/to/file.md
```

输出示例：
```
10:# 第1章 介绍
150:## 1.1 背景
180:## 1.2 目标
400:# 第2章 方法
```

## 目录概要格式

见 [TOC_TEMPLATE.md](TOC_TEMPLATE.md)

## README 更新格式

```markdown
- [文件名.md](path/to/file.md) (XXX KB) - 简短描述 [目录概要](contents_overview/文件名_overview.md)
```
