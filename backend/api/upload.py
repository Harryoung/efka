"""
Upload API routes - 纯文件接收服务
核心原则：此端点只负责接收文件和保存到临时目录，不做任何业务逻辑！
所有业务处理（格式转换、入库、冲突检测）由 Agent 通过 /api/query 自主完成。
"""
import logging
import os
import tempfile
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    纯文件接收服务

    职责：
    1. 接收文件
    2. 验证文件大小
    3. 保存到临时目录
    4. 返回文件路径信息

    不做任何业务逻辑！

    使用方式：
    1. 前端调用此端点上传文件，获取文件路径
    2. 前端通过 /api/query 发送消息告诉 Coordinator Agent 处理这些文件
    3. Agent 自主决定如何处理（格式转换、入库、冲突检测等）

    示例：
    ```python
    # 1. 上传文件
    result = await upload_files(files)

    # 2. 告诉 Agent 处理
    await query({
        "message": f"请将以下文件添加到知识库：\\n{result['files'][0]['temp_path']}"
    })
    ```
    """
    try:
        # 验证文件数量
        if len(files) > 10:
            raise HTTPException(status_code=400, detail="一次最多上传10个文件")

        uploaded_files = []
        temp_paths = []

        for file in files:
            # 读取文件内容
            content = await file.read()
            file_size = len(content)

            # 验证文件大小
            if file_size > settings.MAX_UPLOAD_SIZE:
                # 清理已上传的临时文件
                for temp_path in temp_paths:
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

                raise HTTPException(
                    status_code=413,
                    detail=f"文件 {file.filename} 大小 {file_size / 1024 / 1024:.2f}MB 超过限制 {settings.MAX_UPLOAD_SIZE / 1024 / 1024:.0f}MB"
                )

            # 保存到临时目录
            suffix = os.path.splitext(file.filename)[1] if file.filename else ""
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix,
                prefix="kb_upload_"
            )

            try:
                temp_file.write(content)
                temp_file.flush()
                temp_path = temp_file.name
            finally:
                temp_file.close()

            temp_paths.append(temp_path)
            uploaded_files.append({
                "original_name": file.filename,
                "temp_path": temp_path,
                "size": file_size,
                "content_type": file.content_type
            })

            logger.info(f"Saved file {file.filename} to {temp_path} ({file_size} bytes)")

        return {
            "status": "success",
            "files": uploaded_files,
            "message": f"成功接收 {len(uploaded_files)} 个文件",
            "note": "请通过 /api/query 告诉 Agent 如何处理这些文件"
        }

    except HTTPException:
        raise
    except Exception as e:
        # 清理临时文件
        for temp_path in temp_paths:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
