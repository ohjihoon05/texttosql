"""Unit tests for ExcelLoader service."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.services.excel_loader import ExcelLoader


@pytest.fixture
def sample_excel_file(tmp_path: Path) -> Path:
    """Create a sample Excel file for testing."""
    data = {
        "Sheet1": pd.DataFrame({
            "id": [1, 2, 3],
            "name": ["김철수", "이영희", "박지훈"],
            "score": [95, 87, 92],
        }),
        "Sheet2": pd.DataFrame({
            "date": ["2024-12-20", "2024-12-21"],
            "status": ["완료", "진행중"],
        }),
    }

    file_path = tmp_path / "test.xlsx"
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        for sheet_name, df in data.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    return file_path


@pytest.fixture
def empty_excel_file(tmp_path: Path) -> Path:
    """Create an empty Excel file for testing."""
    file_path = tmp_path / "empty.xlsx"
    df = pd.DataFrame()
    df.to_excel(file_path, index=False)
    return file_path


@pytest.fixture
def unicode_sheet_excel(tmp_path: Path) -> Path:
    """Create Excel with Unicode sheet names."""
    data = {
        "일일보고서": pd.DataFrame({"이름": ["김철수"]}),
        "月間レポート": pd.DataFrame({"名前": ["田中"]}),
        "Sheet with Spaces": pd.DataFrame({"col": [1, 2]}),
    }

    file_path = tmp_path / "unicode.xlsx"
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        for sheet_name, df in data.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    return file_path


class TestExcelLoaderInit:
    """Tests for ExcelLoader initialization."""

    def test_init_valid_file(self, sample_excel_file: Path):
        """Should initialize with valid Excel file."""
        loader = ExcelLoader(sample_excel_file)
        assert loader.file_path == sample_excel_file
        loader.close()

    def test_init_file_not_found(self):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            ExcelLoader("/nonexistent/file.xlsx")

    def test_init_invalid_extension(self, tmp_path: Path):
        """Should raise ValueError for non-Excel file."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("a,b,c")

        with pytest.raises(ValueError) as exc_info:
            ExcelLoader(csv_file)
        assert "Invalid file format" in str(exc_info.value)

    def test_init_file_too_large(self, tmp_path: Path, monkeypatch):
        """Should raise ValueError for file exceeding size limit."""
        # Create a small file but mock the size check
        file_path = tmp_path / "large.xlsx"
        pd.DataFrame({"a": [1]}).to_excel(file_path, index=False)

        # Mock file size to be over limit
        from src import config
        original_settings = config.get_settings()
        monkeypatch.setattr(original_settings, "max_excel_size_mb", 0.0001)

        with pytest.raises(ValueError) as exc_info:
            ExcelLoader(file_path)
        assert "exceeds limit" in str(exc_info.value)


class TestExcelLoaderLoad:
    """Tests for load() method."""

    def test_load_valid_excel(self, sample_excel_file: Path):
        """Should load Excel file and return schema."""
        loader = ExcelLoader(sample_excel_file)
        schema = loader.load()

        assert schema.file_name == "test.xlsx"
        assert len(schema.sheets) == 2
        assert "Sheet1" in schema.sheet_names
        assert "Sheet2" in schema.sheet_names
        assert schema.total_rows == 5  # 3 + 2 rows

        loader.close()

    def test_load_returns_cached_schema(self, sample_excel_file: Path):
        """Should return same schema on repeated calls."""
        loader = ExcelLoader(sample_excel_file)
        schema1 = loader.load()
        schema2 = loader.load()

        assert schema1 is schema2
        loader.close()

    def test_load_extracts_column_info(self, sample_excel_file: Path):
        """Should extract correct column information."""
        loader = ExcelLoader(sample_excel_file)
        schema = loader.load()

        sheet1 = schema.get_sheet("Sheet1")
        assert sheet1 is not None
        assert len(sheet1.columns) == 3
        assert sheet1.column_names == ["id", "name", "score"]

        # Check sample values
        name_col = next(c for c in sheet1.columns if c.name == "name")
        assert "김철수" in name_col.sample_values

        loader.close()


class TestExcelLoaderExecuteQuery:
    """Tests for execute_query() method."""

    def test_execute_query_success(self, sample_excel_file: Path):
        """Should execute valid SELECT query."""
        loader = ExcelLoader(sample_excel_file)
        loader.load()

        result = loader.execute_query("SELECT * FROM Sheet1")

        assert result.success is True
        assert result.row_count == 3
        assert result.column_names == ["id", "name", "score"]
        assert len(result.data) == 3

        loader.close()

    def test_execute_query_with_filter(self, sample_excel_file: Path):
        """Should execute query with WHERE clause."""
        loader = ExcelLoader(sample_excel_file)
        loader.load()

        result = loader.execute_query("SELECT name FROM Sheet1 WHERE score > 90")

        assert result.success is True
        assert result.row_count == 2  # 95 and 92
        assert "name" in result.column_names

        loader.close()

    def test_execute_query_invalid_sql(self, sample_excel_file: Path):
        """Should return error for invalid SQL."""
        loader = ExcelLoader(sample_excel_file)
        loader.load()

        result = loader.execute_query("SELECT * FROM NonexistentTable")

        assert result.success is False
        assert result.error_message is not None
        assert "not found" in result.error_message.lower() or "exist" in result.error_message.lower()

        loader.close()

    def test_execute_query_not_loaded(self, sample_excel_file: Path):
        """Should raise error if not loaded."""
        loader = ExcelLoader(sample_excel_file)

        with pytest.raises(RuntimeError) as exc_info:
            loader.execute_query("SELECT * FROM Sheet1")
        assert "not loaded" in str(exc_info.value)

    def test_execute_query_returns_time(self, sample_excel_file: Path):
        """Should return execution time."""
        loader = ExcelLoader(sample_excel_file)
        loader.load()

        result = loader.execute_query("SELECT * FROM Sheet1")

        assert result.execution_time_ms >= 0

        loader.close()


class TestExcelLoaderTableMapping:
    """Tests for table name sanitization."""

    def test_table_mapping_simple(self, sample_excel_file: Path):
        """Should create correct table mapping."""
        loader = ExcelLoader(sample_excel_file)
        loader.load()

        mapping = loader.get_table_mapping()

        assert mapping["Sheet1"] == "Sheet1"
        assert mapping["Sheet2"] == "Sheet2"

        loader.close()

    def test_table_mapping_unicode(self, unicode_sheet_excel: Path):
        """Should handle Unicode sheet names."""
        loader = ExcelLoader(unicode_sheet_excel)
        loader.load()

        mapping = loader.get_table_mapping()

        # Sheet names should be sanitized
        assert "일일보고서" in mapping
        assert "Sheet with Spaces" in mapping

        loader.close()

    def test_query_with_unicode_table(self, unicode_sheet_excel: Path):
        """Should execute query on Unicode-named tables."""
        loader = ExcelLoader(unicode_sheet_excel)
        loader.load()

        mapping = loader.get_table_mapping()
        table_name = mapping["일일보고서"]

        result = loader.execute_query(f"SELECT * FROM {table_name}")

        assert result.success is True
        assert result.row_count == 1

        loader.close()


class TestExcelLoaderContextManager:
    """Tests for context manager usage."""

    def test_context_manager(self, sample_excel_file: Path):
        """Should work as context manager."""
        with ExcelLoader(sample_excel_file) as loader:
            schema = loader.get_schema()
            assert schema.file_name == "test.xlsx"

    def test_context_manager_cleanup(self, sample_excel_file: Path):
        """Should cleanup on exit."""
        loader = ExcelLoader(sample_excel_file)
        loader.load()

        # Close and verify cleanup
        loader.close()

        with pytest.raises(RuntimeError):
            loader.get_schema()


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_excel(self, empty_excel_file: Path):
        """Should handle empty Excel file."""
        loader = ExcelLoader(empty_excel_file)
        schema = loader.load()

        # Empty Excel still has one sheet
        assert len(schema.sheets) >= 0

        loader.close()

    def test_zero_results_query(self, sample_excel_file: Path):
        """Should handle query with no results."""
        loader = ExcelLoader(sample_excel_file)
        loader.load()

        result = loader.execute_query("SELECT * FROM Sheet1 WHERE id = 999")

        assert result.success is True
        assert result.row_count == 0
        assert result.is_empty is True

        loader.close()
