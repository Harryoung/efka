# 文档格式处理详情

## DOCX/DOC

### 处理方式
- **DOCX**: 直接使用 Pandoc 转换
- **DOC**: 先用 LibreOffice 转为 DOCX，再 Pandoc 处理

### 特点
- 保留格式（标题、列表、表格）
- 自动提取图片到独立目录
- 保留链接和引用

### 图片目录
```
原始文件名_images/
├── image1.png
├── image2.jpg
└── ...
```

---

## PDF

### 自动类型检测

脚本自动检测 PDF 类型：
- **电子版**：前3页文本密度高（可直接提取文字）
- **扫描版**：前3页几乎无文字但有图片

### 电子版 PDF
- 使用 PyMuPDF4LLM 快速转换
- 秒级处理
- 保留文档结构

### 扫描版 PDF
- 使用 PaddleOCR-VL 在线服务
- 需要 `PADDLE_OCR_TOKEN` 环境变量
- 处理时间：几十秒到几分钟
- 支持表格和图表识别

### 强制 OCR 模式
```bash
python scripts/smart_convert.py input.pdf --force-ocr --json-output
```

---

## PPTX/PPT

### 处理方式
- **PPTX**: 使用 pptx2md 专业转换
- **PPT**: 先用 LibreOffice 转为 PPTX，再 pptx2md 处理

### 特点
- 保留标题层级
- 保留列表格式
- 提取幻灯片图片
- 保留备注（Speaker Notes）
- 添加幻灯片分隔符

### 输出结构
```markdown
# 幻灯片标题

幻灯片内容...

![](原始文件名_images/slide1_image1.png)

---

# 下一页标题
...
```

---

## 依赖库

| 库 | 用途 |
|---|-----|
| pypandoc | DOCX → Markdown |
| PyMuPDF (fitz) | PDF 类型检测 |
| pymupdf4llm | 电子版 PDF 转换 |
| pptx2md | PPTX 转换 |
| requests | PaddleOCR API 调用 |

---

## 错误处理

### LibreOffice 未安装
```
未找到 LibreOffice (soffice)。请安装 LibreOffice 或将其加入 PATH。
```

### PaddleOCR Token 缺失
```
扫描版 PDF 需要设置 PADDLE_OCR_TOKEN 环境变量。
```

### 不支持的格式
```
不支持的文件格式: .xyz
```
