"""Tests for configuration module."""

import pytest

from src.core.config import Settings, get_settings


def test_settings_defaults():
    """Test default settings values."""
    settings = Settings()

    assert settings.server.host == "0.0.0.0"
    assert settings.server.port == 8000
    assert settings.storage.base_dir == "./data"
    assert settings.memory.short_term_max_messages == 1000
    assert settings.llm.provider == "ollama"
    assert settings.retrieval.top_k == 5


def test_get_settings():
    """Test get_settings returns Settings instance."""
    settings = get_settings()
    assert isinstance(settings, Settings)


def test_storage_paths():
    """Test storage directory structure."""
    settings = Settings()
    base_dir = settings.storage.base_dir

    assert settings.storage.users_dir == "users"
    assert settings.memory.long_term_chunk_size == 2000


def test_llm_settings():
    """Test LLM configuration."""
    settings = Settings()

    assert settings.llm.ollama.base_url == "http://localhost:11434"
    assert settings.llm.ollama.model == "llama2"
    assert settings.llm.openai.model == "gpt-3.5-turbo"
