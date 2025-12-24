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
    llm_fallback_url: str = Field(
        default="http://192.168.20.83:11434",
        description="Fallback Ollama server URL"
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
    default_excel_path: Optional[Path] = Field(
        default=Path("/home/wonchatgpt/oz/Projects/texttosql/data/cs_daily_report.xlsx"),
        description="Default Excel file to load on startup"
    )
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

    # Multi-Sheet Query Configuration (T011-T013)
    max_union_sheets: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum sheets for UNION query"
    )
    default_union_strategy: str = Field(
        default="COMMON_COLUMNS",
        description="Default UNION strategy (COMMON_COLUMNS or NULL_PADDING)"
    )
    query_timeout: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Query execution timeout in seconds"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Sheet group pattern definitions (T011)
SHEET_GROUP_PATTERNS: dict[str, str] = {
    "TICKET_DAILY": r"^Daily_\d{8}$",
    "TICKET_WEEKLY": r"^Weekly_W\d{1,2}$",
    "TICKET_MONTHLY": r"^Monthly_",
    "EQUIPMENT": r"^Equipment_",
    "TEAM": r"^Team_",
}

# Question type to sheet group mapping (T013)
QUESTION_TYPE_SHEET_GROUPS: dict[str, list[str]] = {
    "PERSON": ["TICKET_DAILY", "TICKET_WEEKLY", "TICKET_MONTHLY"],
    "PERIOD": ["TICKET_DAILY", "TICKET_WEEKLY", "TICKET_MONTHLY"],
    "EQUIPMENT": ["EQUIPMENT", "TICKET_DAILY", "TICKET_WEEKLY"],
    "STATISTICS": ["TICKET_MONTHLY", "TICKET_WEEKLY"],
}

# Sheet group compatibility matrix (for UNION)
SHEET_GROUP_COMPATIBILITY: dict[str, list[str]] = {
    "TICKET_DAILY": ["TICKET_WEEKLY", "TICKET_MONTHLY"],
    "TICKET_WEEKLY": ["TICKET_DAILY", "TICKET_MONTHLY"],
    "TICKET_MONTHLY": ["TICKET_DAILY", "TICKET_WEEKLY"],
    "EQUIPMENT": [],  # Not compatible with TICKET groups
    "TEAM": [],  # Not compatible with other groups
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
