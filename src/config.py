"""Configuration management for Excel Text-to-SQL system."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # LLM Configuration
    llm_base_url: str = Field(
        default="http://10.249.22.191:11435",
        description="Ollama server URL"
    )
    llm_model: str = Field(
        default="gpt-oss:20b",
        description="Primary LLM model"
    )
    llm_fallback_model: str = Field(
        default="llama3.2:1b",
        description="Fallback LLM model"
    )
    llm_timeout: int = Field(
        default=30,
        description="LLM request timeout in seconds"
    )

    # Cache Configuration
    cache_ttl_hours: int = Field(
        default=1,
        description="Cache TTL in hours"
    )
    cache_max_size: int = Field(
        default=100,
        description="Maximum cache entries"
    )
    cache_db_path: Path = Field(
        default=Path("data/cache.db"),
        description="SQLite cache database path"
    )

    # Excel Configuration
    max_excel_size_mb: float = Field(
        default=10.0,
        description="Maximum Excel file size in MB"
    )
    max_sheets: int = Field(
        default=50,
        description="Maximum number of sheets"
    )
    max_relevant_sheets: int = Field(
        default=5,
        description="Maximum relevant sheets for LLM context"
    )

    # Chainlit Configuration
    chainlit_port: int = Field(
        default=3003,
        description="Chainlit server port"
    )
    chainlit_host: str = Field(
        default="0.0.0.0",
        description="Chainlit server host"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Global settings instance (cached)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get application settings (cached singleton).

    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Backwards compatibility
settings = get_settings()
