"""Memory management API routes."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...core.memory_index import MemoryIndex
from ...core.memory_retriever import MemoryRetriever
from ...core.memory_store import MemoryStore
from ..dependencies import (
    get_current_user_id,
    get_memory_index,
    get_memory_retriever,
    get_memory_store,
)

router = APIRouter(prefix="/v1/memories", tags=["memories"])


class MemoryCreate(BaseModel):
    """Memory creation model."""

    content: str
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class MemoryResponse(BaseModel):
    """Memory response model."""

    id: str
    title: Optional[str]
    tags: List[str]
    created_at: str
    content: Optional[str] = None


class SearchRequest(BaseModel):
    """Search request model."""

    query: str
    top_k: int = 5
    session_id: Optional[str] = None


@router.get("")
async def list_memories(
    include_content: bool = Query(False, description="Include full content"),
    limit: int = Query(50, ge=1, le=1000),
    store: MemoryStore = Depends(get_memory_store),
):
    """List all long-term memories.

    Args:
        include_content: Include full content
        limit: Maximum number of results
        store: Memory store

    Returns:
        List of memories
    """
    try:
        memories = await store.list_memories(include_content=include_content)
        return {"memories": memories[:limit], "total": len(memories)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{memory_id}")
async def get_memory(
    memory_id: str,
    store: MemoryStore = Depends(get_memory_store),
):
    """Get a specific memory.

    Args:
        memory_id: Memory ID
        store: Memory store

    Returns:
        Memory details
    """
    try:
        memories = await store.read_long_term(memory_id=memory_id)
        if not memories:
            raise HTTPException(status_code=404, detail="Memory not found")
        return memories[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_memory(
    memory: MemoryCreate,
    store: MemoryStore = Depends(get_memory_store),
    index: MemoryIndex = Depends(get_memory_index),
):
    """Create a new long-term memory.

    Args:
        memory: Memory data
        store: Memory store
        index: Memory index

    Returns:
        Created memory ID
    """
    try:
        memory_id = await store.append_long_term(
            content=memory.content,
            title=memory.title,
            tags=memory.tags,
            metadata=memory.metadata,
        )

        # Update index
        await index.update_memory_file(
            memory_id=memory_id,
            content=memory.content,
            title=memory.title,
            tags=memory.tags,
        )

        return {"id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{memory_id}")
async def update_memory(
    memory_id: str,
    memory: MemoryCreate,
    store: MemoryStore = Depends(get_memory_store),
    index: MemoryIndex = Depends(get_memory_index),
):
    """Update a memory.

    Args:
        memory_id: Memory ID
        memory: Updated memory data
        store: Memory store
        index: Memory index

    Returns:
        Success status
    """
    try:
        # Delete old memory
        deleted = await store.delete_memory(memory_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Memory not found")

        # Create new memory with updated content
        new_memory_id = await store.append_long_term(
            content=memory.content,
            title=memory.title,
            tags=memory.tags,
            metadata=memory.metadata,
        )

        # Update index
        await index.update_memory_file(
            memory_id=new_memory_id,
            content=memory.content,
            title=memory.title,
            tags=memory.tags,
        )

        return {"id": new_memory_id, "success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    store: MemoryStore = Depends(get_memory_store),
    index: MemoryIndex = Depends(get_memory_index),
):
    """Delete a memory.

    Args:
        memory_id: Memory ID
        store: Memory store
        index: Memory index

    Returns:
        Success status
    """
    try:
        deleted = await store.delete_memory(memory_id)
        if deleted:
            await index.delete_memory(memory_id)
            return {"success": True}
        raise HTTPException(status_code=404, detail="Memory not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_memories(
    request: SearchRequest,
    retriever: MemoryRetriever = Depends(get_memory_retriever),
):
    """Search memories using associative retrieval.

    Args:
        request: Search request
        retriever: Memory retriever

    Returns:
        Search results
    """
    try:
        results = await retriever.retrieve(
            query=request.query,
            session_id=request.session_id,
            include_short_term=True,
            include_long_term=True,
            expand_session=True,
            expand_time=True,
            expand_similar=False,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/index/stats")
async def get_index_stats(
    index: MemoryIndex = Depends(get_memory_index),
):
    """Get index statistics.

    Args:
        index: Memory index

    Returns:
        Index statistics
    """
    try:
        stats = await index.get_index_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index/rebuild")
async def rebuild_index(
    force: bool = Query(False, description="Force rebuild"),
    index: MemoryIndex = Depends(get_memory_index),
):
    """Rebuild the memory index.

    Args:
        force: Force full rebuild
        index: Memory index

    Returns:
        Rebuild status
    """
    try:
        await index.index_user_memories(force_rebuild=force)
        stats = await index.get_index_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
