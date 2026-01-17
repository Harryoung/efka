# Table of Contents Overview File Template

## File Naming Rules

Original filename: `python_tutorial.md`
Overview filename: `python_tutorial_overview.md`
Storage location: `knowledge_base/contents_overview/`

## Template Format

```markdown
# [Filename] - Table of Contents Overview

> File path: knowledge_base/path/to/file.md
> File size: XXX KB
> Generation time: YYYY-MM-DD

## Chapter Directory

- [Chapter 1 Title](Starting line: 10)
- [Chapter 2 Title](Starting line: 150)
  - [2.1 Section Title](Starting line: 180)
  - [2.2 Section Title](Starting line: 250)
- [Chapter 3 Title](Starting line: 400)
  - [3.1 Section Title](Starting line: 420)
  - [3.2 Section Title](Starting line: 500)
```

## Generation Steps

### 1. Extract Headings and Line Numbers

```bash
# Use Grep tool
grep -n '^#+' knowledge_base/path/to/file.md
```

Output example:
```
10:# Chapter 1 Introduction
150:## 1.1 Background
180:## 1.2 Objectives
400:# Chapter 2 Methodology
420:## 2.1 Data Collection
500:## 2.2 Data Analysis
```

### 2. Parse Heading Hierarchy

- `#` → Level 1 heading (no indent)
- `##` → Level 2 heading (2 spaces indent)
- `###` → Level 3 heading (4 spaces indent)
- And so on

### 3. Generate Directory Structure

Determine hierarchy based on number of `#`, use line numbers as location anchors.

### 4. Get File Size

```bash
ls -lh knowledge_base/path/to/file.md | awk '{print $5}'
```

### 5. Get Current Time

```bash
date '+%Y-%m-%d'
```

## Example Output

```markdown
# Python Tutorial - Table of Contents Overview

> File path: knowledge_base/技术文档/编程语言/python_tutorial.md
> File size: 85 KB
> Generation time: 2025-01-06

## Chapter Directory

- [Chapter 1 Introduction to Python](Starting line: 10)
  - [1.1 What is Python](Starting line: 25)
  - [1.2 Installing Python](Starting line: 80)
  - [1.3 First Program](Starting line: 150)
- [Chapter 2 Basic Syntax](Starting line: 200)
  - [2.1 Variables and Data Types](Starting line: 220)
  - [2.2 Operators](Starting line: 350)
  - [2.3 Control Flow](Starting line: 450)
- [Chapter 3 Functions](Starting line: 600)
  - [3.1 Defining Functions](Starting line: 620)
  - [3.2 Parameters and Return Values](Starting line: 720)
- [Chapter 4 Object-Oriented](Starting line: 900)
  - [4.1 Classes and Objects](Starting line: 920)
  - [4.2 Inheritance](Starting line: 1100)
```

## Usage

When users query large files:
1. First read table of contents overview to understand overall structure
2. Precisely locate relevant chapters based on line number ranges
3. Use `Read` tool to read specified line ranges

```python
# For example, read Chapter 2 content (lines 200-599)
Read("knowledge_base/技术文档/编程语言/python_tutorial.md", offset=200, limit=400)
```
