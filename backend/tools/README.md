# Custom Tools for Intelligent KBA

## image_read Tool

### 概述

`image_read` 是一个自定义的 SDK MCP 工具，允许智能体使用多模态大模型读取和分析图像内容。

### 设计理念

遵循项目的 **Agent-First** 设计原则：
- ❌ **不是**：为每个业务场景创建专用工具
- ✅ **而是**：提供基础能力，让 Agent 自主决策如何使用

### 实现方式

使用 Claude Agent SDK 的 `@tool` 装饰器和 `create_sdk_mcp_server()` 创建：

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool(
    name="image_read",
    description="读取图像内容并根据指定的关注点返回分析结果",
    input_schema={
        "image_path": str,
        "question": str,
        "context": str
    }
)
async def image_read_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    # 实现逻辑...
    pass

# 创建 SDK MCP server
image_vision_server = create_sdk_mcp_server(
    name="image_vision",
    version="1.0.0",
    tools=[image_read_handler]
)
```

### 配置

#### 1. 环境变量（必需）

在 `.env` 文件中配置：

```bash
# 模型提供商：doubao, openai, anthropic
VISION_MODEL_PROVIDER=doubao

# API Key（必需）
VISION_MODEL_API_KEY=your_api_key_here

# API Base URL（可选，使用默认值）
VISION_MODEL_BASE_URL=

# 模型名称（可选，使用默认值）
VISION_MODEL_NAME=
```

#### 2. Agent 配置

已在 `backend/services/kb_service_factory.py` 中为两个 Agent 配置：

```python
# Employee Agent
mcp_servers = {
    "wework": {...},
    "image_vision": image_vision_server
}

allowed_tools = [
    "Read", "Grep", "Glob", "Write", "Bash",
    "mcp__image_vision__image_read",  # ← 图像读取工具
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
    "mcp__image_vision__image_read",  # ← 图像读取工具
    "mcp__markitdown__*",
    "mcp__wework__*",
]
```

### 工具参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `image_path` | `str` | ✅ | 图像文件路径（绝对路径或相对于 KB_ROOT_PATH） |
| `question` | `str` | ✅ | 需要从图像中获取的信息（关注点） |
| `context` | `str` | ❌ | 可选的上下文信息，帮助模型更好理解问题 |

### 使用示例

#### 示例 1：分析架构图

```
用户：知识库中有个系统架构图，请分析一下各组件的关系

Agent 自主决策流程：
1. 使用 Glob 工具搜索图像文件：*.png, *.jpg
2. 找到 "系统架构图.png"
3. 调用 image_read 工具：
   - image_path: "知识库/技术文档/系统架构图.png"
   - question: "描述图中的系统架构逻辑，包括各组件的功能和交互关系"
   - context: "这是一个微服务架构的系统设计图"
4. 获得分析结果，向用户解释
```

#### 示例 2：提取操作步骤

```
用户：这张截图里的操作步骤是什么？

Agent 自主决策流程：
1. 用户已提供图像路径或上传图像
2. 调用 image_read 工具：
   - image_path: "uploads/screenshot_123.png"
   - question: "按顺序提取图中的操作步骤"
   - context: ""
3. 将提取的步骤整理后返回用户
```

### 支持的提供商

#### 1. Doubao（火山引擎）- 默认

- **模型**：Doubao Seed 1.6 Vision
- **端点**：`https://ark.cn-beijing.volces.com/api/v3`
- **配置**：
  ```bash
  VISION_MODEL_PROVIDER=doubao
  VISION_MODEL_API_KEY=<火山引擎 API Key>
  VISION_MODEL_NAME=ep-20250122183949-wz66v
  ```

#### 2. OpenAI GPT-4V

- **模型**：GPT-4o (with vision)
- **端点**：`https://api.openai.com/v1`
- **配置**：
  ```bash
  VISION_MODEL_PROVIDER=openai
  VISION_MODEL_API_KEY=<OpenAI API Key>
  VISION_MODEL_NAME=gpt-4o
  ```

#### 3. Anthropic Claude 3

- **模型**：Claude 3.5 Sonnet
- **端点**：`https://api.anthropic.com`
- **配置**：
  ```bash
  VISION_MODEL_PROVIDER=anthropic
  VISION_MODEL_API_KEY=<Anthropic API Key>
  VISION_MODEL_NAME=claude-3-5-sonnet-20241022
  ```

### 错误处理

工具返回格式：

**成功**：
```json
{
    "content": [{
        "type": "text",
        "text": "图像分析结果..."
    }]
}
```

**失败**：
```json
{
    "content": [{
        "type": "text",
        "text": "图像读取失败: [错误信息]"
    }],
    "is_error": true
}
```

### 与 markitdown 的区别

| 特性 | markitdown (OCR) | image_read (Vision Model) |
|------|------------------|--------------------------|
| **用途** | 文档格式转换 | 智能图像分析 |
| **输入** | 各种文档格式 | 图像文件 |
| **输出** | Markdown 文本 | 基于问题的定向分析 |
| **灵活性** | 固定的 OCR 结果 | 根据 Agent 问题动态分析 |
| **典型场景** | PDF/Word 转 Markdown | 架构图分析、流程图解读、数据提取 |

### 架构对齐

✅ **Agent-First Philosophy**
- 工具只提供"读取图像"的能力
- Agent 决定何时使用、如何提问、如何利用结果
- 业务逻辑在 Agent prompt 中，不在工具代码中

✅ **Minimal Base Tools**
- 不为每种图像分析场景创建专用工具
- 一个通用的 image_read 工具 + Agent 智能决策

✅ **Tool Composition**
- Agent 可以组合使用：Glob → image_read → Write
- 例如：找图 → 分析 → 写入分析报告

### 开发指南

#### 添加新的视觉模型提供商

1. 在 `backend/tools/image_read.py` 中添加新的 `_call_xxx_vision()` 函数
2. 在 `image_read_handler()` 中添加对应的分支逻辑
3. 更新文档说明默认配置

#### 测试工具

```bash
# 测试工具导入
python3 -c "
from backend.tools.image_read import image_read_handler
print(f'✅ 工具名称: {image_read_handler.name}')
print(f'✅ 工具描述: {image_read_handler.description}')
print(f'✅ 输入参数: {list(image_read_handler.input_schema.keys())}')
"

# 测试 SDK MCP Server 创建
python3 -c "
from claude_agent_sdk import create_sdk_mcp_server
from backend.tools.image_read import image_read_handler

server = create_sdk_mcp_server(
    name='image_vision',
    version='1.0.0',
    tools=[image_read_handler]
)
print(f'✅ Server 类型: {server[\"type\"]}')
print(f'✅ Server 名称: {server[\"name\"]}')
"
```

### 常见问题

**Q: 为什么不直接用 markitdown 的图像 OCR？**

A: markitdown 的 OCR 是通用的文本提取，image_read 提供的是**定向分析**能力。Agent 可以根据具体需求提出不同的问题，获得更精准的答案。

**Q: 工具会自动识别图像类型吗？**

A: Agent 需要根据用户意图决定使用哪个工具。如果需要格式转换，用 markitdown；如果需要智能分析，用 image_read。

**Q: 支持哪些图像格式？**

A: JPG, JPEG, PNG, GIF, WEBP, BMP（取决于底层视觉模型的支持）

**Q: API 调用失败怎么办？**

A: 检查 `.env` 配置、API Key 是否正确、账户余额是否充足、网络连接是否正常。工具会返回详细的错误信息。

---

**Last Updated**: 2025-01-23
**Version**: 1.0.0
