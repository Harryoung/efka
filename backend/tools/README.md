# Custom Tools for EFKA (知了)

## image_read Tool

### Overview

`image_read` is a custom SDK MCP tool that allows agents to read and analyze image content using multimodal large models.

### Design Philosophy

Follows the project's **Agent-First** design principle:
- ❌ **Not**: Create dedicated tools for each business scenario
- ✅ **Instead**: Provide basic capabilities, let the Agent decide how to use them

### Implementation

Created using Claude Agent SDK's `@tool` decorator and `create_sdk_mcp_server()`:

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool(
    name="image_read",
    description="Read image content and return analysis results based on specified focus points",
    input_schema={
        "image_path": str,
        "question": str,
        "context": str
    }
)
async def image_read_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    # Implementation logic...
    pass

# Create SDK MCP server
image_vision_server = create_sdk_mcp_server(
    name="image_vision",
    version="1.0.0",
    tools=[image_read_handler]
)
```

### Configuration

#### 1. Environment Variables (Required)

Configure in `.env` file:

```bash
# Model provider: doubao, openai, anthropic
VISION_MODEL_PROVIDER=doubao

# API Key (required)
VISION_MODEL_API_KEY=your_api_key_here

# API Base URL (optional, uses default)
VISION_MODEL_BASE_URL=

# Model name (optional, uses default)
VISION_MODEL_NAME=
```

#### 2. Agent Configuration

Already configured for both Agents in `backend/services/kb_service_factory.py`:

```python
# User Agent
mcp_servers = {
    "wework": {...},
    "image_vision": image_vision_server
}

allowed_tools = [
    "Read", "Grep", "Glob", "Write", "Bash",
    "mcp__image_vision__image_read",  # ← Image read tool
    "mcp__wework__*",
]

# Admin Agent
mcp_servers = {
    "markitdown": {...},
    "wework": {...},
    "image_vision": image_vision_server
}

allowed_tools = [
    "Read", "Write", "Grep", "Glob", "Bash",
    "mcp__image_vision__image_read",  # ← Image read tool
    "mcp__markitdown__*",
    "mcp__wework__*",
]
```

### Tool Parameters

| Parameter | Type | Required | Description |
|------|------|------|------|
| `image_path` | `str` | ✅ | Image file path (absolute path or relative to KB_ROOT_PATH) |
| `question` | `str` | ✅ | Information to extract from image (focus point) |
| `context` | `str` | ❌ | Optional context information to help model better understand the question |

### Usage Examples

#### Example 1: Analyze Architecture Diagram

```
User: There's a system architecture diagram in the knowledge base, please analyze the relationship between components

Agent autonomous decision flow:
1. Use Glob tool to search for image files: *.png, *.jpg
2. Find "System Architecture Diagram.png"
3. Call image_read tool:
   - image_path: "Knowledge Base/Technical Docs/System Architecture Diagram.png"
   - question: "Describe the system architecture logic in the diagram, including component functions and interaction relationships"
   - context: "This is a microservices architecture system design diagram"
4. Get analysis results, explain to user
```

#### Example 2: Extract Operation Steps

```
User: What are the operation steps in this screenshot?

Agent autonomous decision flow:
1. User has provided image path or uploaded image
2. Call image_read tool:
   - image_path: "uploads/screenshot_123.png"
   - question: "Extract operation steps in the image in order"
   - context: ""
3. Organize extracted steps and return to user
```

### Supported Providers

#### 1. Doubao (火山引擎) - Default

- **Model**: Doubao Seed 1.6 Vision
- **Endpoint**: `https://ark.cn-beijing.volces.com/api/v3`
- **Configuration**:
  ```bash
  VISION_MODEL_PROVIDER=doubao
  VISION_MODEL_API_KEY=<Volcengine API Key>
  VISION_MODEL_NAME=ep-20250122183949-wz66v
  ```

#### 2. OpenAI GPT-4V

- **Model**: GPT-4o (with vision)
- **Endpoint**: `https://api.openai.com/v1`
- **Configuration**:
  ```bash
  VISION_MODEL_PROVIDER=openai
  VISION_MODEL_API_KEY=<OpenAI API Key>
  VISION_MODEL_NAME=gpt-4o
  ```

#### 3. Anthropic Claude 3

- **Model**: Claude 3.5 Sonnet
- **Endpoint**: `https://api.anthropic.com`
- **Configuration**:
  ```bash
  VISION_MODEL_PROVIDER=anthropic
  VISION_MODEL_API_KEY=<Anthropic API Key>
  VISION_MODEL_NAME=claude-3-5-sonnet-20241022
  ```

### Error Handling

Tool return format:

**Success**:
```json
{
    "content": [{
        "type": "text",
        "text": "Image analysis results..."
    }]
}
```

**Failure**:
```json
{
    "content": [{
        "type": "text",
        "text": "Image read failed: [Error message]"
    }],
    "is_error": true
}
```

### Difference from markitdown

| Feature | markitdown (OCR) | image_read (Vision Model) |
|------|------------------|--------------------------|
| **Purpose** | Document format conversion | Intelligent image analysis |
| **Input** | Various document formats | Image files |
| **Output** | Markdown text | Targeted analysis based on questions |
| **Flexibility** | Fixed OCR results | Dynamic analysis based on Agent questions |
| **Typical Scenarios** | PDF/Word to Markdown | Architecture diagram analysis, flowchart interpretation, data extraction |

### Architecture Alignment

✅ **Agent-First Philosophy**
- Tool only provides "read image" capability
- Agent decides when to use, how to ask, how to utilize results
- Business logic in Agent prompt, not in tool code

✅ **Minimal Base Tools**
- Don't create dedicated tools for each image analysis scenario
- One generic image_read tool + Agent intelligent decision-making

✅ **Tool Composition**
- Agent can compose tools: Glob → image_read → Write
- Example: Find image → Analyze → Write analysis report

### Development Guide

#### Add New Vision Model Provider

1. Add new `_call_xxx_vision()` function in `backend/tools/image_read.py`
2. Add corresponding branch logic in `image_read_handler()`
3. Update documentation with default configuration

#### Test Tool

```bash
# Test tool import
python3 -c "
from backend.tools.image_read import image_read_handler
print(f'✅ Tool name: {image_read_handler.name}')
print(f'✅ Tool description: {image_read_handler.description}')
print(f'✅ Input parameters: {list(image_read_handler.input_schema.keys())}')
"

# Test SDK MCP Server creation
python3 -c "
from claude_agent_sdk import create_sdk_mcp_server
from backend.tools.image_read import image_read_handler

server = create_sdk_mcp_server(
    name='image_vision',
    version='1.0.0',
    tools=[image_read_handler]
)
print(f'✅ Server type: {server[\"type\"]}')
print(f'✅ Server name: {server[\"name\"]}')
"
```

### FAQ

**Q: Why not just use markitdown's image OCR?**

A: markitdown's OCR is generic text extraction, image_read provides **targeted analysis** capability. Agent can ask different questions based on specific needs to get more precise answers.

**Q: Does the tool automatically recognize image type?**

A: Agent needs to decide which tool to use based on user intent. If format conversion is needed, use markitdown; if intelligent analysis is needed, use image_read.

**Q: Which image formats are supported?**

A: JPG, JPEG, PNG, GIF, WEBP, BMP (depends on underlying vision model support)

**Q: What if API call fails?**

A: Check `.env` configuration, whether API Key is correct, account balance is sufficient, network connection is normal. Tool will return detailed error messages.

---

**Last Updated**: 2025-01-23
**Version**: 1.0.0
