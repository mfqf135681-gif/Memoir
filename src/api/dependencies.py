"""Dependency injection for API routes."""

from typing import Optional

from fastapi import Depends, Header, HTTPException

from ..core.config import Settings, get_settings
from ..core.dialogue_engine import DialogueEngine
from ..core.llm_client import LLMClientBase, create_dynamic_client, get_llm_client
from ..core.memory_index import MemoryIndex
from ..core.memory_retriever import MemoryRetriever
from ..core.memory_store import MemoryStore
from ..core.user_config import get_user_config


async def get_current_user_id(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
) -> str:
    """Get user ID from header.

    Args:
        x_user_id: User ID from header

    Returns:
        User ID

    Raises:
        HTTPException: If no user ID provided
    """
    if not x_user_id:
        # For development, use a default user
        return "default"
        # In production, require user ID:
        # raise HTTPException(status_code=401, detail="User ID required")
    return x_user_id


def get_settings_dep() -> Settings:
    """Get application settings."""
    return get_settings()


def get_memory_store(
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
) -> MemoryStore:
    """Get memory store instance for user.

    Args:
        user_id: User identifier
        settings: Application settings

    Returns:
        MemoryStore instance
    """
    return MemoryStore(user_id, settings)


def get_memory_index(
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
) -> MemoryIndex:
    """Get memory index instance for user.

    Args:
        user_id: User identifier
        settings: Application settings

    Returns:
        MemoryIndex instance
    """
    return MemoryIndex(user_id, settings)


def get_memory_retriever(
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
) -> MemoryRetriever:
    """Get memory retriever instance for user.

    Args:
        user_id: User identifier
        settings: Application settings

    Returns:
        MemoryRetriever instance
    """
    return MemoryRetriever(user_id, settings)


async def get_user_llm_client(
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
) -> Optional[LLMClientBase]:
    """Get user-specific LLM client.

    Args:
        user_id: User identifier
        settings: Application settings

    Returns:
        LLM client instance (dynamic if user has config, else None)
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
    except Exception:
        pass

    return None


def get_dialogue_engine(
    user_id: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dep),
    user_llm: Optional[LLMClientBase] = Depends(get_user_llm_client),
) -> DialogueEngine:
    """Get dialogue engine instance for user.

    Args:
        user_id: User identifier
        settings: Application settings
        user_llm: User-specific LLM client

    Returns:
        DialogueEngine instance
    """
    # Use user-specific LLM if available, otherwise use default
    llm_client = user_llm or get_llm_client(settings=settings)
    return DialogueEngine(user_id, settings, llm_client)


def get_llm_client_dep(
    settings: Settings = Depends(get_settings_dep),
) -> LLMClientBase:
    """Get LLM client.

    Args:
        settings: Application settings

    Returns:
        LLM client instance
    """
    return get_llm_client(settings=settings)
