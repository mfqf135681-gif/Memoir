"""Operation logs API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ...core.memory_store import MemoryStore
from ..dependencies import get_current_user_id, get_memory_store

router = APIRouter(prefix="/v1/logs", tags=["logs"])


@router.get("")
async def get_operation_logs(
    operation: Optional[str] = Query(None, description="Filter by operation type"),
    limit: int = Query(100, ge=1, le=1000),
    store: MemoryStore = Depends(get_memory_store),
):
    """Get operation logs.

    Args:
        operation: Optional operation filter
        limit: Maximum number of entries
        store: Memory store

    Returns:
        List of operation logs
    """
    try:
        logs = await store.get_operations(
            operation=operation,
            limit=limit,
        )
        return {"logs": logs, "total": len(logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/short-term")
async def get_short_term_logs(
    session_id: Optional[str] = Query(None, description="Filter by session"),
    limit: int = Query(100, ge=1, le=1000),
    store: MemoryStore = Depends(get_memory_store),
):
    """Get short-term memory logs.

    Args:
        session_id: Optional session filter
        limit: Maximum number of entries
        store: Memory store

    Returns:
        List of short-term log entries
    """
    try:
        entries = await store.read_short_term(
            limit=limit,
            session_id=session_id,
        )
        return {"entries": entries, "total": len(entries)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
