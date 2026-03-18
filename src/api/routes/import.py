"""Import API routes."""

import json
import tempfile
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from ..core.config import Settings, get_settings
from ..core.llm_client import LLMClientBase, create_dynamic_client, get_llm_client
from ..core.memory_index import MemoryIndex
from ..core.memory_store import MemoryStore
from ..core.user_config import get_user_config
from ..utils.logger import get_logger
from .dependencies import (
    get_current_user_id,
    get_llm_client_dep,
    get_memory_index,
    get_memory_store,
    get_settings_dep,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/import", tags=["import"])


# Request/Response models
class ConfirmRequest(BaseModel):
    """Request model for confirming memories."""

    memory_ids: List[str]


class RejectRequest(BaseModel):
    """Request model for rejecting memories."""

    memory_ids: List[str]


class ImportJobResponse(BaseModel):
    """Response model for import job."""

    job_id: str
    status: str
    candidates_count: int = 0
    filename: Optional[str] = None
    error: Optional[str] = None


class PendingResponse(BaseModel):
    """Response model for pending memories."""

    items: List[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


class ConfirmResponse(BaseModel):
    """Response model for confirm/reject operations."""

    success: bool
    confirmed_count: int = 0
    rejected_count: int = 0
    error: Optional[str] = None


async def get_import_manager(
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
):
    """Get import manager instance.

    Args:
        user_id: User ID
        settings: Application settings

    Returns:
        ImportManager instance
    """
    from ..importers.extractor import ImportManager

    return ImportManager(user_id, settings.storage.base_dir)


async def get_user_llm_client(
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
) -> LLMClientBase:
    """Get user-specific LLM client.

    Args:
        user_id: User identifier
        settings: Application settings

    Returns:
        LLM client instance
    """
    try:
        config = await get_user_config(user_id, settings.storage.base_dir)
        llm_config = await config.get_llm_config()

        if llm_config.get("api_key"):
            return create_dynamic_client(
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"],
                model=llm_config.get("model", "gpt-3.5-turbo"),
            )
    except Exception as e:
        logger.warning(f"Could not get user LLM config: {e}")

    # Fall back to default client
    return get_llm_client(settings=settings)


@router.post("", response_model=ImportJobResponse)
async def upload_and_import(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
    memory_store: MemoryStore = Depends(get_memory_store),
    llm_client: LLMClientBase = Depends(get_user_llm_client),
):
    """Upload a file and start import process.

    Args:
        file: Uploaded file
        user_id: User ID
        settings: Application settings
        memory_store: Memory store instance
        llm_client: LLM client

    Returns:
        Import job info
    """
    from ..importers.extractor import ImportManager

    logger.info(f"Starting import job for user {user_id}, file: {file.filename}")

    # Save uploaded file to temp location
    suffix = Path(file.filename).suffix if file.filename else ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Create import manager and process file
        import_manager = ImportManager(user_id, settings.storage.base_dir)
        result = await import_manager.create_import_job(
            file_path=tmp_path,
            original_filename=file.filename or "unknown",
            llm_client=llm_client,
        )

        return ImportJobResponse(**result)

    except Exception as e:
        logger.error(f"Import job failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}",
        )
    finally:
        # Clean up temp file
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


@router.get("/{job_id}", response_model=ImportJobResponse)
async def get_import_job(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
):
    """Get import job status.

    Args:
        job_id: Job ID
        user_id: User ID
        settings: Application settings

    Returns:
        Job status info
    """
    from ..importers.extractor import ImportManager

    import_manager = ImportManager(user_id, settings.storage.base_dir)
    job = await import_manager.get_job_status(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return ImportJobResponse(**job)


@router.get("/{job_id}/candidates", response_model=PendingResponse)
async def get_job_candidates(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
    page: int = 1,
    page_size: int = 20,
):
    """Get candidates from a specific import job.

    Args:
        job_id: Job ID
        user_id: User ID
        settings: Application settings
        page: Page number
        page_size: Items per page

    Returns:
        List of candidate memories
    """
    from ..importers.extractor import ImportManager

    import_manager = ImportManager(user_id, settings.storage.base_dir)
    result = await import_manager.get_pending_memories(
        job_id=job_id,
        page=page,
        page_size=page_size,
    )

    return PendingResponse(**result)


@router.get("/pending", response_model=PendingResponse)
async def get_all_pending(
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
    page: int = 1,
    page_size: int = 20,
):
    """Get all pending memories (across all jobs).

    Args:
        user_id: User ID
        settings: Application settings
        page: Page number
        page_size: Items per page

    Returns:
        List of pending memories
    """
    from ..importers.extractor import ImportManager

    import_manager = ImportManager(user_id, settings.storage.base_dir)
    result = await import_manager.get_pending_memories(
        page=page,
        page_size=page_size,
    )

    return PendingResponse(**result)


@router.get("/pending/count")
async def get_pending_count(
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
):
    """Get count of pending memories.

    Args:
        user_id: User ID
        settings: Application settings

    Returns:
        Count of pending memories
    """
    from ..importers.extractor import ImportManager

    import_manager = ImportManager(user_id, settings.storage.base_dir)
    count = await import_manager.get_all_pending_count()

    return {"count": count}


@router.post("/{job_id}/confirm", response_model=ConfirmResponse)
async def confirm_memories(
    job_id: str,
    request: ConfirmRequest,
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
    memory_store: MemoryStore = Depends(get_memory_store),
    memory_index: MemoryIndex = Depends(get_memory_index),
):
    """Confirm and save selected memories.

    Args:
        job_id: Job ID
        request: Confirm request with memory IDs
        user_id: User ID
        settings: Application settings
        memory_store: Memory store instance
        memory_index: Memory index instance

    Returns:
        Confirmation result
    """
    from ..importers.extractor import ImportManager

    import_manager = ImportManager(user_id, settings.storage.base_dir)

    try:
        result = await import_manager.confirm_memories(
            memory_ids=request.memory_ids,
            memory_store=memory_store,
            memory_index=memory_index,
        )

        return ConfirmResponse(**result)

    except Exception as e:
        logger.error(f"Confirm memories failed: {e}")
        return ConfirmResponse(
            success=False,
            error=str(e),
        )


@router.post("/{job_id}/reject", response_model=ConfirmResponse)
async def reject_memories(
    job_id: str,
    request: RejectRequest,
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
):
    """Reject selected memories.

    Args:
        job_id: Job ID
        request: Reject request with memory IDs
        user_id: User ID
        settings: Application settings

    Returns:
        Rejection result
    """
    from ..importers.extractor import ImportManager

    import_manager = ImportManager(user_id, settings.storage.base_dir)

    try:
        result = await import_manager.reject_memories(
            memory_ids=request.memory_ids,
        )

        return ConfirmResponse(
            success=result.get("success", False),
            rejected_count=result.get("rejected_count", 0),
        )

    except Exception as e:
        logger.error(f"Reject memories failed: {e}")
        return ConfirmResponse(
            success=False,
            error=str(e),
        )
