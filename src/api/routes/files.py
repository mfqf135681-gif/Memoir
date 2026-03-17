"""File upload and management API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ...core.memory_store import MemoryStore
from ...utils.file_extractor import extract_file_content
from ..dependencies import get_current_user_id, get_memory_store

router = APIRouter(prefix="/v1/files", tags=["files"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    extract_content: bool = True,
    store: MemoryStore = Depends(get_memory_store),
):
    """Upload a file.

    Args:
        file: Uploaded file
        extract_content: Whether to extract text content
        store: Memory store

    Returns:
        File ID and optional extracted content
    """
    try:
        # Read file content
        content = await file.read()

        # Save file
        file_id = await store.save_file(
            filename=file.filename,
            content=content,
            content_type=file.content_type,
        )

        result = {
            "file_id": file_id,
            "filename": file.filename,
            "size": len(content),
            "content_type": file.content_type,
        }

        # Extract content if requested
        if extract_content:
            try:
                extracted = await extract_file_content(
                    content,
                    file.filename,
                    file.content_type,
                )
                result["extracted_content"] = extracted
            except Exception as e:
                result["extraction_error"] = str(e)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{file_id}")
async def get_file_info(
    file_id: str,
    store: MemoryStore = Depends(get_memory_store),
):
    """Get file metadata.

    Args:
        file_id: File ID
        store: Memory store

    Returns:
        File metadata
    """
    try:
        file_info = await store.get_file(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")
        return file_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    store: MemoryStore = Depends(get_memory_store),
):
    """Download a file.

    Args:
        file_id: File ID
        store: Memory store

    Returns:
        File response
    """
    try:
        file_info = await store.get_file(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")

        file_path = file_info.get("path")
        if not file_path:
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            path=file_path,
            filename=file_info.get("original_filename", file_id),
            media_type=file_info.get("content_type", "application/octet-stream"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract")
async def extract_file_text(
    file: UploadFile = File(...),
):
    """Extract text from uploaded file.

    Args:
        file: Uploaded file

    Returns:
        Extracted text
    """
    try:
        content = await file.read()
        extracted = await extract_file_content(
            content,
            file.filename,
            file.content_type,
        )
        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "extracted_text": extracted,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
