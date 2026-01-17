"""
Upload API routes - Pure file receiving service
Core principle: This endpoint only handles receiving files and saving to temp directory, no business logic!
All business processing (format conversion, storage, conflict detection) is autonomously handled by Agent via /api/query.
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
    Pure file receiving service

    Responsibilities:
    1. Receive files
    2. Validate file size
    3. Save to temporary directory
    4. Return file path information

    No business logic!

    Usage:
    1. Frontend calls this endpoint to upload files and get file paths
    2. Frontend sends message via /api/query to tell Coordinator Agent to process these files
    3. Agent autonomously decides how to process (format conversion, storage, conflict detection, etc.)

    Example:
    ```python
    # 1. Upload files
    result = await upload_files(files)

    # 2. Tell Agent to process
    await query({
        "message": f"Please add the following files to knowledge base:\\n{result['files'][0]['temp_path']}"
    })
    ```
    """
    try:
        # Validate file count
        if len(files) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 files can be uploaded at once")

        uploaded_files = []
        temp_paths = []

        for file in files:
            # Read file content
            content = await file.read()
            file_size = len(content)

            # Validate file size
            if file_size > settings.MAX_UPLOAD_SIZE:
                # Clean up already uploaded temp files
                for temp_path in temp_paths:
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

                raise HTTPException(
                    status_code=413,
                    detail=f"File {file.filename} size {file_size / 1024 / 1024:.2f}MB exceeds limit {settings.MAX_UPLOAD_SIZE / 1024 / 1024:.0f}MB"
                )

            # Save to temporary directory
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
            "message": f"Successfully received {len(uploaded_files)} file(s)",
            "note": "Please tell Agent how to process these files via /api/query"
        }

    except HTTPException:
        raise
    except Exception as e:
        # Clean up temporary files
        for temp_path in temp_paths:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
