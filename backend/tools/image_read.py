"""
Image Read Tool - 图像内容读取工具

使用多模态大模型读取图像内容，智能体可以指定关注点或问题，
让模型有针对性地返回图像中的信息。

设计原则：
- 保持通用性，支持多种多模态模型提供商（火山引擎 Doubao、OpenAI GPT-4V、Anthropic Claude 3 等）
- 通过环境变量配置模型端点和认证信息
- 返回清晰、结构化的文本描述供智能体使用
"""

import os
import base64
import logging
from pathlib import Path
from typing import Any, Dict

import httpx
from claude_agent_sdk import tool

logger = logging.getLogger(__name__)


class ImageReadError(Exception):
    """图像读取工具异常"""
    pass


async def _call_doubao_vision(
    api_key: str,
    base_url: str,
    model: str,
    image_base64: str,
    mime_type: str,
    question: str,
    context: str | None = None
) -> str:
    """
    调用火山引擎 Doubao Vision API (兼容 OpenAI 格式)。

    API 文档: https://www.volcengine.com/docs/82379/1298454
    """
    # 构造 prompt
    prompt = question
    if context:
        prompt = f"上下文信息：{context}\n\n问题：{question}"

    # 构造请求
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]


async def _call_openai_vision(
    api_key: str,
    base_url: str,
    model: str,
    image_base64: str,
    mime_type: str,
    question: str,
    context: str | None = None
) -> str:
    """
    调用 OpenAI GPT-4V API。

    API 文档: https://platform.openai.com/docs/guides/vision
    """
    # 构造 prompt
    prompt = question
    if context:
        prompt = f"Context: {context}\n\nQuestion: {question}"

    # 构造请求
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        "max_tokens": 4096
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]


async def _call_anthropic_vision(
    api_key: str,
    base_url: str,
    model: str,
    image_base64: str,
    mime_type: str,
    question: str,
    context: str | None = None
) -> str:
    """
    调用 Anthropic Claude 3 Vision API。

    API 文档: https://docs.anthropic.com/claude/docs/vision
    """
    # 构造 prompt
    prompt = question
    if context:
        prompt = f"Context: {context}\n\nQuestion: {question}"

    # 构造请求
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base_url}/v1/messages",
            headers=headers,
            json=payload
        )
        response.raise_for_status()

        data = response.json()
        return data["content"][0]["text"]


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
    """
    读取图像内容并根据指定的关注点返回分析结果。

    Args:
        args: 包含以下字段的字典
            - image_path: 图像文件路径（支持绝对路径或相对于 KB_ROOT_PATH 的路径）
            - question: 需要从图像中获取的信息，例如：
                       - "描述图中的架构图逻辑"
                       - "提取图中的操作步骤"
                       - "识别图中的文字内容"
                       - "分析图中的数据表格"
            - context: 可选的上下文信息，帮助模型更好地理解问题

    Returns:
        包含分析结果的字典，格式：
        {
            "content": [{"type": "text", "text": "分析结果"}],
            "is_error": False  # 可选，仅在错误时返回 True
        }
    """
    try:
        image_path = args.get("image_path")
        question = args.get("question")
        context = args.get("context")

        if not image_path:
            raise ImageReadError("缺少必需参数: image_path")
        if not question:
            raise ImageReadError("缺少必需参数: question")

        # 1. 解析图像路径
        image_file = Path(image_path)
        if not image_file.is_absolute():
            kb_root = os.getenv("KB_ROOT_PATH", "./knowledge_base")
            image_file = Path(kb_root) / image_path

        if not image_file.exists():
            raise ImageReadError(f"图像文件不存在: {image_file}")

        # 2. 读取并编码图像
        with open(image_file, "rb") as f:
            image_data = f.read()

        # 获取图像格式
        suffix = image_file.suffix.lower()
        mime_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        mime_type = mime_type_map.get(suffix, "image/jpeg")

        # Base64 编码
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # 3. 获取多模态模型配置
        provider = os.getenv("VISION_MODEL_PROVIDER", "doubao").lower()
        api_key = os.getenv("VISION_MODEL_API_KEY")
        base_url = os.getenv("VISION_MODEL_BASE_URL")
        model_name = os.getenv("VISION_MODEL_NAME")

        if not api_key:
            raise ImageReadError(
                "未配置 VISION_MODEL_API_KEY 环境变量。"
                "请在 .env 文件中配置多模态模型的认证信息。"
            )

        # 4. 根据不同提供商调用 API
        if provider == "doubao":
            # 火山引擎 Doubao Vision (兼容 OpenAI 格式)
            result = await _call_doubao_vision(
                api_key=api_key,
                base_url=base_url or "https://ark.cn-beijing.volces.com/api/v3",
                model=model_name or "ep-20250122183949-wz66v",  # 默认 endpoint
                image_base64=image_base64,
                mime_type=mime_type,
                question=question,
                context=context
            )
        elif provider == "openai":
            # OpenAI GPT-4V
            result = await _call_openai_vision(
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1",
                model=model_name or "gpt-4o",
                image_base64=image_base64,
                mime_type=mime_type,
                question=question,
                context=context
            )
        elif provider == "anthropic":
            # Anthropic Claude 3
            result = await _call_anthropic_vision(
                api_key=api_key,
                base_url=base_url or "https://api.anthropic.com",
                model=model_name or "claude-3-5-sonnet-20241022",
                image_base64=image_base64,
                mime_type=mime_type,
                question=question,
                context=context
            )
        else:
            raise ImageReadError(f"不支持的 VISION_MODEL_PROVIDER: {provider}")

        logger.info(f"成功读取图像 {image_path}，问题: {question}")

        return {
            "content": [{
                "type": "text",
                "text": result
            }]
        }

    except Exception as e:
        logger.error(f"图像读取失败: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"图像读取失败: {str(e)}"
            }],
            "is_error": True
        }
