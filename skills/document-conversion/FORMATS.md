# Document Format Processing Details

## DOCX/DOC

### Processing Method
- **DOCX**: Directly use Pandoc conversion
- **DOC**: First convert to DOCX using LibreOffice, then Pandoc processing

### Features
- Preserve formatting (headings, lists, tables)
- Automatically extract images to separate directory
- Preserve links and references

### Image Directory
```
original_filename_images/
├── image1.png
├── image2.jpg
└── ...
```

---

## PDF

### Automatic Type Detection

Script automatically detects PDF type:
- **Electronic**: High text density in first 3 pages (text can be directly extracted)
- **Scanned**: First 3 pages have almost no text but have images

### Electronic PDF
- Use PyMuPDF4LLM for fast conversion
- Second-level processing
- Preserve document structure

### Scanned PDF
- Use PaddleOCR-VL online service
- Requires `PADDLE_OCR_TOKEN` environment variable
- Processing time: tens of seconds to minutes
- Support table and chart recognition

### Force OCR Mode
```bash
python scripts/smart_convert.py input.pdf --force-ocr --json-output
```

---

## PPTX/PPT

### Processing Method
- **PPTX**: Use pptx2md professional conversion
- **PPT**: First convert to PPTX using LibreOffice, then pptx2md processing

### Features
- Preserve heading hierarchy
- Preserve list formatting
- Extract slide images
- Preserve notes (Speaker Notes)
- Add slide separators

### Output Structure
```markdown
# Slide Title

Slide content...

![](original_filename_images/slide1_image1.png)

---

# Next Slide Title
...
```

---

## Dependencies

| Library | Purpose |
|---------|---------|
| pypandoc | DOCX → Markdown |
| PyMuPDF (fitz) | PDF type detection |
| pymupdf4llm | Electronic PDF conversion |
| pptx2md | PPTX conversion |
| requests | PaddleOCR API calls |

---

## Error Handling

### LibreOffice Not Installed
```
LibreOffice (soffice) not found. Please install LibreOffice or add it to PATH.
```

### PaddleOCR Token Missing
```
Scanned PDF requires PADDLE_OCR_TOKEN environment variable.
```

### Unsupported Format
```
Unsupported file format: .xyz
```
