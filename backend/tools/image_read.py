"""
Image Read Tool - Image content reading tool

Uses multimodal LLM to read image content, agents can specify focus points or questions,
allowing the model to return targeted information from the image.

Design principles:
- Keep it generic, support multiple multimodal model providers (Volcengine Doubao, OpenAI GPT-4V, Anthropic Claude 3, etc.)
- Configure model endpoints and authentication via environment variables
- Return clear, structured text descriptions for agent use
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
    """Image read tool exception"""
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
    Call Volcengine Doubao Vision API (OpenAI-compatible format).

    API docs: https://www.volcengine.com/docs/82379/1298454
    """
    # Construct prompt
    prompt = question
    if context:
        prompt = f"Context information: {context}\n\nQuestion: {question}"

    # Construct request
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
    Call OpenAI GPT-4V API.

    API docs: https://platform.openai.com/docs/guides/vision
    """
    # Construct prompt
    prompt = question
    if context:
        prompt = f"Context: {context}\n\nQuestion: {question}"

    # Construct request
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
    Call Anthropic Claude 3 Vision API.

    API docs: https://docs.anthropic.com/claude/docs/vision
    """
    # Construct prompt
    prompt = question
    if context:
        prompt = f"Context: {context}\n\nQuestion: {question}"

    # Construct request
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
    description="Read image content and return analysis results based on specified focus points",
    input_schema={
        "image_path": str,
        "question": str,
        "context": str
    }
)
async def image_read_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Read image content and return analysis results based on specified focus points.

    Args:
        args: Dictionary containing the following fields
            - image_path: Image file path (supports absolute path or path relative to KB_ROOT_PATH)
            - question: Information to extract from the image, for example:
                       - "Describe the architecture diagram logic"
                       - "Extract operation steps from the image"
                       - "Recognize text content in the image"
                       - "Analyze data table in the image"
            - context: Optional context information to help model better understand the question

    Returns:
        Dictionary containing analysis results, format:
        {
            "content": [{"type": "text", "text": "analysis result"}],
            "is_error": False  # Optional, only returns True on error
        }
    """
    try:
        image_path = args.get("image_path")
        question = args.get("question")
        context = args.get("context")

        if not image_path:
            raise ImageReadError("Missing required parameter: image_path")
        if not question:
            raise ImageReadError("Missing required parameter: question")

        # 1. Parse image path
        image_file = Path(image_path)
        if not image_file.is_absolute():
            kb_root = os.getenv("KB_ROOT_PATH", "./knowledge_base")
            image_file = Path(kb_root) / image_path

        if not image_file.exists():
            raise ImageReadError(f"Image file does not exist: {image_file}")

        # 2. Read and encode image
        with open(image_file, "rb") as f:
            image_data = f.read()

        # Get image format
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

        # Base64 encode
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # 3. Get multimodal model configuration
        provider = os.getenv("VISION_MODEL_PROVIDER", "doubao").lower()
        api_key = os.getenv("VISION_MODEL_API_KEY")
        base_url = os.getenv("VISION_MODEL_BASE_URL")
        model_name = os.getenv("VISION_MODEL_NAME")

        if not api_key:
            raise ImageReadError(
                "VISION_MODEL_API_KEY environment variable not configured. "
                "Please configure multimodal model authentication in .env file."
            )

        # 4. Call API based on provider
        if provider == "doubao":
            # Volcengine Doubao Vision (OpenAI-compatible format)
            result = await _call_doubao_vision(
                api_key=api_key,
                base_url=base_url or "https://ark.cn-beijing.volces.com/api/v3",
                model=model_name or "ep-20250122183949-wz66v",  # Default endpoint
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
            raise ImageReadError(f"Unsupported VISION_MODEL_PROVIDER: {provider}")

        logger.info(f"Successfully read image {image_path}, question: {question}")

        return {
            "content": [{
                "type": "text",
                "text": result
            }]
        }

    except Exception as e:
        logger.error(f"Image read failed: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Image read failed: {str(e)}"
            }],
            "is_error": True
        }
