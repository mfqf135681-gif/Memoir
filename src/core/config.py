"""Configuration management for Memoir."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class ServerSettings(BaseModel):
    """Server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True


class StorageSettings(BaseModel):
    """Storage configuration."""
    base_dir: str = "./data"
    users_dir: str = "users"
    max_short_term_mb: int = 100


class MemorySettings(BaseModel):
    """Memory configuration."""
    short_term_max_messages: int = 1000
    long_term_chunk_size: int = 2000


class VectorIndexSettings(BaseModel):
    """Vector index configuration."""
    enabled: bool = True
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    device: str = "cpu"


class FulltextIndexSettings(BaseModel):
    """Fulltext index configuration."""
    enabled: bool = True
    fts_language: str = "english"


class IndexSettings(BaseModel):
    """Index configuration."""
    vector: VectorIndexSettings = VectorIndexSettings()
    fulltext: FulltextIndexSettings = FulltextIndexSettings()


class OllamaSettings(BaseModel):
    """Ollama LLM configuration."""
    base_url: str = "http://localhost:11434"
    model: str = "llama2"
    timeout: int = 120


class OpenAISettings(BaseModel):
    """OpenAI LLM configuration."""
    api_key: Optional[str] = None
    model: str = "gpt-3.5-turbo"
    base_url: str = "https://api.openai.com/v1"


class LLMSettings(BaseModel):
    """LLM configuration."""
    provider: str = "ollama"
    ollama: OllamaSettings = OllamaSettings()
    openai: OpenAISettings = OpenAISettings()


class RetrievalSettings(BaseModel):
    """Retrieval configuration."""
    top_k: int = 5
    similarity_threshold: float = 0.7
    expand_session_turns: int = 3
    expand_time_days: int = 7


class LoggingSettings(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class Settings(BaseModel):
    """Main settings container."""
    server: ServerSettings = ServerSettings()
    storage: StorageSettings = StorageSettings()
    memory: MemorySettings = MemorySettings()
    index: IndexSettings = IndexSettings()
    llm: LLMSettings = LLMSettings()
    retrieval: RetrievalSettings = RetrievalSettings()
    logging: LoggingSettings = LoggingSettings()

    @classmethod
    def from_yaml(cls, config_path: str) -> "Settings":
        """Load settings from YAML file."""
        path = Path(config_path)
        if path.exists():
            with open(path) as f:
                config_data = yaml.safe_load(f)
            return cls(**config_data)
        return cls()


def get_settings() -> Settings:
    """Get application settings with environment variable overrides."""
    config_path = os.environ.get("MEMOIR_CONFIG", "config.yaml")

    # Try to find config file in current directory or parent
    for search_path in [config_path, f"../{config_path}", f"../../{config_path}"]:
        if Path(search_path).exists():
            return Settings.from_yaml(search_path)

    return Settings()
