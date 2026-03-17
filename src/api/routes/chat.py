"""Chat API routes."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...core.dialogue_engine import DialogueEngine
from ..dependencies import (
    get_current_user_id,
    get_dialogue_engine,
    get_memory_store,
    get_settings_dep,
)

router = APIRouter(prefix="/v1/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Chat request model."""

    message: str
    session_id: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = None
    use_memory: bool = True
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048


class ChatResponse(BaseModel):
    """Chat response model."""

    response: str
    session_id: str
    used_memories: List[Dict[str, Any]]
    context_used: bool


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    engine: DialogueEngine = Depends(get_dialogue_engine),
):
    """Chat with AI assistant with memory integration.

    Args:
        request: Chat request
        engine: Dialogue engine

    Returns:
        Chat response with AI reply and metadata
    """
    try:
        result = await engine.generate(
            message=request.message,
            session_id=request.session_id,
            history=request.history,
            use_memory=request.use_memory,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summarize")
async def summarize_conversation(
    session_id: str,
    title: Optional[str] = None,
    tags: Optional[List[str]] = None,
    engine: DialogueEngine = Depends(get_dialogue_engine),
):
    """Summarize a conversation and store in long-term memory.

    Args:
        session_id: Session to summarize
        title: Optional title
        tags: Optional tags
        engine: Dialogue engine

    Returns:
        Created memory ID
    """
    try:
        memory_id = await engine.summarize_and_store(
            session_id=session_id,
            title=title,
            tags=tags,
        )
        return {"memory_id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
