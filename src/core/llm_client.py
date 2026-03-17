"""LLM client implementations for Memoir.

Supports Ollama and OpenAI backends.
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

from ..utils.logger import get_logger
from .config import LLMSettings, Settings, get_settings

logger = get_logger(__name__)


class LLMClientBase(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional generation parameters

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the LLM service is available.

        Returns:
            True if available, False otherwise
        """
        pass


class OllamaClient(LLMClientBase):
    """Ollama LLM client."""

    def __init__(self, settings: Optional[LLMSettings] = None):
        """Initialize Ollama client.

        Args:
            settings: LLM settings
        """
        self.settings = settings or get_settings().llm
        self.base_url = self.settings.ollama.base_url
        self.model = self.settings.ollama.model
        self.timeout = self.settings.ollama.timeout

    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> str:
        """Generate a response using Ollama.

        Args:
            messages: List of message dicts
            **kwargs: Additional parameters (temperature, etc.)

        Returns:
            Generated text
        """
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 0.9),
                "num_predict": kwargs.get("max_tokens", 2048),
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                return data.get("message", {}).get("content", "")

            except httpx.HTTPStatusError as e:
                logger.error(f"Ollama HTTP error: {e.response.status_code} - {e.response.text}")
                raise RuntimeError(f"Ollama request failed: {e.response.status_code}")
            except httpx.RequestError as e:
                logger.error(f"Ollama request error: {e}")
                raise RuntimeError(f"Ollama connection failed: {e}")

    async def embed(self, text: str) -> List[float]:
        """Generate embeddings using Ollama.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        url = f"{self.base_url}/api/embeddings"

        # Use a smaller model for embeddings if available
        model = "nomic-embed-text" if kwargs.get("use_nomic", False) else self.model

        payload = {
            "model": model,
            "prompt": text,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                return data.get("embedding", [])

            except httpx.HTTPStatusError as e:
                logger.error(f"Ollama embed HTTP error: {e}")
                raise RuntimeError(f"Ollama embed failed: {e.response.status_code}")
            except httpx.RequestError as e:
                logger.error(f"Ollama embed request error: {e}")
                raise RuntimeError(f"Ollama embed connection failed: {e}")

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available Ollama models.

        Returns:
            List of available models
        """
        url = f"{self.base_url}/api/tags"

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                return data.get("models", [])
            except Exception as e:
                logger.error(f"Error listing Ollama models: {e}")
                return []

    async def health_check(self) -> bool:
        """Check if Ollama service is available.

        Returns:
            True if available, False otherwise
        """
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            return False


class OpenAIClient(LLMClientBase):
    """OpenAI API client."""

    def __init__(self, settings: Optional[LLMSettings] = None):
        """Initialize OpenAI client.

        Args:
            settings: LLM settings
        """
        self.settings = settings or get_settings().llm
        self.api_key = self.settings.openai.api_key or os.environ.get("OPENAI_API_KEY")
        self.model = self.settings.openai.model
        self.base_url = self.settings.openai.base_url

        if not self.api_key:
            raise ValueError("OpenAI API key not provided")

    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> str:
        """Generate a response using OpenAI API.

        Args:
            messages: List of message dicts
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

                return data["choices"][0]["message"]["content"]

            except httpx.HTTPStatusError as e:
                logger.error(f"OpenAI HTTP error: {e.response.status_code} - {e.response.text}")
                raise RuntimeError(f"OpenAI request failed: {e.response.status_code}")
            except httpx.RequestError as e:
                logger.error(f"OpenAI request error: {e}")
                raise RuntimeError(f"OpenAI connection failed: {e}")

    async def embed(self, text: str) -> List[float]:
        """Generate embeddings using OpenAI API.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        url = f"{self.base_url}/embeddings"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "text-embedding-ada-002",
            "input": text,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

                return data["data"][0]["embedding"]

            except httpx.HTTPStatusError as e:
                logger.error(f"OpenAI embed HTTP error: {e}")
                raise RuntimeError(f"OpenAI embed failed: {e.response.status_code}")
            except httpx.RequestError as e:
                logger.error(f"OpenAI embed request error: {e}")
                raise RuntimeError(f"OpenAI embed connection failed: {e}")

    async def health_check(self) -> bool:
        """Check if OpenAI API service is available.

        Returns:
            True if available, False otherwise
        """
        url = f"{self.base_url}/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=headers)
                return response.status_code == 200
        except Exception:
            return False


def get_llm_client(provider: Optional[str] = None, settings: Optional[Settings] = None) -> LLMClientBase:
    """Get LLM client based on provider setting.

    Args:
        provider: Provider name ('ollama' or 'openai')
        settings: Optional settings override

    Returns:
        LLM client instance
    """
    settings = settings or get_settings()
    provider = provider or settings.llm.provider

    if provider == "openai":
        return OpenAIClient(settings.llm)
    else:
        return OllamaClient(settings.llm)


class DynamicLLMClient(LLMClientBase):
    """Dynamic LLM client that uses user-specific configuration."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "gpt-3.5-turbo",
        timeout: int = 120,
    ):
        """Initialize dynamic LLM client.

        Args:
            api_key: API key
            base_url: Base URL
            model: Model name
            timeout: Request timeout
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> str:
        """Generate a response using the API.

        Args:
            messages: List of message dicts
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

                return data["choices"][0]["message"]["content"]

            except httpx.HTTPStatusError as e:
                logger.error(f"API HTTP error: {e.response.status_code} - {e.response.text}")
                raise RuntimeError(f"API request failed: {e.response.status_code}")
            except httpx.RequestError as e:
                logger.error(f"API request error: {e}")
                raise RuntimeError(f"API connection failed: {e}")

    async def embed(self, text: str) -> List[float]:
        """Generate embeddings.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        url = f"{self.base_url}/embeddings"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "text-embedding-ada-002",
            "input": text,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

                return data["data"][0]["embedding"]

            except Exception as e:
                logger.error(f"Embed error: {e}")
                raise RuntimeError(f"Embed failed: {e}")

    async def health_check(self) -> bool:
        """Check if the API service is available.

        Returns:
            True if available, False otherwise
        """
        url = f"{self.base_url}/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=headers)
                return response.status_code == 200
        except Exception:
            return False


def create_dynamic_client(
    api_key: str,
    base_url: str,
    model: str = "gpt-3.5-turbo",
) -> DynamicLLMClient:
    """Create a dynamic LLM client.

    Args:
        api_key: API key
        base_url: Base URL
        model: Model name

    Returns:
        DynamicLLMClient instance
    """
    return DynamicLLMClient(api_key, base_url, model)
