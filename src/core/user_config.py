"""User configuration management."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Default providers with base URLs
DEFAULT_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-coder"],
    },
    "siliconflow": {
        "name": "SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": [
            "Qwen/Qwen2.5-7B-Instruct",
            "Qwen/Qwen2.5-14B-Instruct",
            "THUDM/glm-4-9b-chat",
            "deepseek-ai/DeepSeek-V2-Chat",
        ],
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
    },
    "moonshot": {
        "name": "月之暗面 (Moonshot)",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    },
    "zhipu": {
        "name": "智谱AI (ZhipuAI)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4", "glm-4-flash", "glm-4-plus"],
    },
    "baidu": {
        "name": "百度 (文心一言)",
        "base_url": "https://qianfan.baidubce.com/v2",
        "models": ["ernie-4.0-8k", "ernie-3.5-8k", "ernie-speed-8k"],
    },
    "tencent": {
        "name": "腾讯混元",
        "base_url": "https://hunyuan.tencentcos.cn",
        "models": ["hunyuan", "hunyuan-pro", "hunyuan-lite"],
    },
    "ali": {
        "name": "阿里 (通义千问)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-turbo", "qwen-plus", "qwen-max", "qwen-max-longcontext"],
    },
    "ollama": {
        "name": "Ollama (本地)",
        "base_url": "http://localhost:11434",
        "models": [],
    },
}


class UserConfig:
    """User-specific configuration manager."""

    def __init__(self, user_id: str, base_dir: str = "./data"):
        """Initialize user config.

        Args:
            user_id: User identifier
            base_dir: Base data directory
        """
        self.user_id = user_id
        self.base_dir = Path(base_dir) / "users" / user_id
        self.config_file = self.base_dir / "config.json"
        self._ensure_dir()

    def _ensure_dir(self):
        """Ensure config directory exists."""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def get(self) -> Dict[str, Any]:
        """Get user config.

        Returns:
            User configuration dict
        """
        if not self.config_file.exists():
            return self._default_config()

        try:
            async with aiofiles.open(self.config_file, "r") as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.error(f"Error reading user config: {e}")
            return self._default_config()

    async def save(self, config: Dict[str, Any]) -> bool:
        """Save user config.

        Args:
            config: Configuration to save

        Returns:
            Success status
        """
        try:
            # Merge with defaults
            current = await self.get()
            current.update(config)

            async with aiofiles.open(self.config_file, "w") as f:
                await f.write(json.dumps(current, indent=2, ensure_ascii=False))

            logger.info(f"Saved config for user {self.user_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving user config: {e}")
            return False

    async def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM-specific config.

        Returns:
            LLM configuration
        """
        config = await self.get()
        return config.get("llm", {})

    def _default_config(self) -> Dict[str, Any]:
        """Get default config.

        Returns:
            Default configuration
        """
        return {
            "llm": {
                "provider": "deepseek",
                "api_key": "",
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "temperature": 0.7,
            },
            "retrieval": {
                "use_memory": True,
                "enhanced_mode": False,
                "top_k": 5,
            },
        }


async def get_user_config(user_id: str, base_dir: str = "./data") -> UserConfig:
    """Get user config instance.

    Args:
        user_id: User identifier
        base_dir: Base data directory

    Returns:
        UserConfig instance
    """
    return UserConfig(user_id, base_dir)
