"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
import tempfile
import os

# Enable pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def sample_excel_path():
    """Return path to sample Excel file."""
    return Path(__file__).parent.parent / "data" / "sample.xlsx"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_settings():
    """Return mock settings for testing."""
    from src.config import Settings
    return Settings(
        llm_base_url="http://localhost:11434",
        llm_model="test-model",
        cache_db_path=Path(":memory:"),
    )
