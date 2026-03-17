"""Configuration API routes."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...core.config import Settings, get_settings
from ...core.llm_client import DynamicLLMClient, create_dynamic_client
from ...core.user_config import DEFAULT_PROVIDERS, get_user_config
from ..dependencies import get_current_user_id, get_settings_dep

router = APIRouter(prefix="/v1/config", tags=["config"])


class UserLLMConfig(BaseModel):
    """User LLM configuration."""

    provider: str
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.7


class UserConfigUpdate(BaseModel):
    """User config update model."""

    llm: UserLLMConfig
    retrieval: Dict[str, Any] = {}


@router.get("")
async def get_config(
    settings: Settings = Depends(get_settings_dep),
):
    """Get current configuration (non-sensitive parts only).

    Args:
        settings: Application settings

    Returns:
        Public configuration
    """
    # Return non-sensitive config
    return {
        "server": settings.server.model_dump(),
        "memory": settings.memory.model_dump(),
        "index": {
            "vector": settings.index.vector.model_dump(),
            "fulltext": settings.index.fulltext.model_dump(),
        },
        "llm": {
            "provider": settings.llm.provider,
            "ollama": {
                "base_url": settings.llm.ollama.base_url,
                "model": settings.llm.ollama.model,
            },
            "openai": {
                "model": settings.llm.openai.model,
                "base_url": settings.llm.openai.base_url,
            },
        },
        "retrieval": settings.retrieval.model_dump(),
    }


@router.get("/providers")
async def get_providers():
    """Get available LLM providers.

    Returns:
        List of providers with base URLs
    """
    return {"providers": DEFAULT_PROVIDERS}


@router.get("/user")
async def get_user_config_endpoint(
    user_id: str = Depends(get_current_user_id),
):
    """Get user-specific configuration.

    Args:
        user_id: User ID

    Returns:
        User configuration
    """
    from ...core.config import get_settings

    settings = get_settings()
    config = await get_user_config(user_id, settings.storage.base_dir)
    user_cfg = await config.get()

    # Don't return API key in plain text
    if user_cfg.get("llm", {}).get("api_key"):
        user_cfg["llm"]["api_key"] = "***" if len(user_cfg["llm"]["api_key"]) > 4 else ""

    return user_cfg


@router.put("/user")
async def update_user_config(
    config_update: UserConfigUpdate,
    user_id: str = Depends(get_current_user_id),
):
    """Update user-specific configuration.

    Args:
        config_update: New configuration
        user_id: User ID

    Returns:
        Success status
    """
    from ...core.config import get_settings

    settings = get_settings()
    config = await get_user_config(user_id, settings.storage.base_dir)

    success = await config.save(config_update.model_dump())
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save config")

    return {"success": True}


@router.post("/user/test")
async def test_llm_connection(
    config: UserLLMConfig,
):
    """Test LLM connection.

    Args:
        config: LLM configuration to test

    Returns:
        Connection status
    """
    try:
        client = create_dynamic_client(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
        )

        is_available = await client.health_check()

        return {
            "success": is_available,
            "message": "连接成功" if is_available else "连接失败"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)}"
        }


@router.get("/llm/models")
async def list_llm_models(
    settings: Settings = Depends(get_settings_dep),
):
    """List available LLM models.

    Args:
        settings: Application settings

    Returns:
        List of available models
    """
    from ...core.llm_client import get_llm_client

    try:
        client = get_llm_client(settings=settings)

        # Try to list models based on provider
        if hasattr(client, "list_models"):
            models = await client.list_models()
            return {"models": models}

        return {"models": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
