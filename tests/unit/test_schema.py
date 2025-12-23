"""Unit tests for schema models."""

import pytest
from pydantic import ValidationError

from src.models.schema import ColumnInfo, SheetSchema, ExcelSchema


class TestColumnInfo:
    """Tests for ColumnInfo model."""

    def test_create_valid_column(self):
        """Valid column info creation."""
        col = ColumnInfo(
            name="customer_name",
            dtype="string",
            nullable=True,
            sample_values=["김철수", "이영희", "박지훈"]
        )
        assert col.name == "customer_name"
        assert col.dtype == "string"
        assert col.nullable is True
        assert len(col.sample_values) == 3

    def test_column_name_stripped(self):
        """Column name should be stripped of whitespace."""
        col = ColumnInfo(name="  test_col  ", dtype="int64")
        assert col.name == "test_col"

    def test_column_name_empty_raises(self):
        """Empty column name should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ColumnInfo(name="", dtype="string")
        assert "Column name cannot be empty" in str(exc_info.value)

    def test_column_name_whitespace_only_raises(self):
        """Whitespace-only column name should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ColumnInfo(name="   ", dtype="string")
        assert "Column name cannot be empty" in str(exc_info.value)

    def test_default_values(self):
        """Default values should be applied correctly."""
        col = ColumnInfo(name="test", dtype="float64")
        assert col.nullable is True
        assert col.sample_values == []


class TestSheetSchema:
    """Tests for SheetSchema model."""

    def test_create_valid_sheet(self):
        """Valid sheet schema creation."""
        cols = [
            ColumnInfo(name="id", dtype="int64"),
            ColumnInfo(name="name", dtype="string"),
        ]
        sheet = SheetSchema(name="customers", columns=cols, row_count=100)
        assert sheet.name == "customers"
        assert len(sheet.columns) == 2
        assert sheet.row_count == 100

    def test_sheet_name_stripped(self):
        """Sheet name should be stripped."""
        sheet = SheetSchema(name="  Sheet1  ")
        assert sheet.name == "Sheet1"

    def test_sheet_name_empty_raises(self):
        """Empty sheet name should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SheetSchema(name="")
        assert "Sheet name cannot be empty" in str(exc_info.value)

    def test_column_names_property(self):
        """column_names property should return list of names."""
        cols = [
            ColumnInfo(name="col1", dtype="int64"),
            ColumnInfo(name="col2", dtype="string"),
            ColumnInfo(name="col3", dtype="float64"),
        ]
        sheet = SheetSchema(name="test", columns=cols)
        assert sheet.column_names == ["col1", "col2", "col3"]

    def test_empty_columns(self):
        """Sheet with no columns should work."""
        sheet = SheetSchema(name="empty_sheet")
        assert sheet.column_names == []

    def test_relevance_score_range(self):
        """relevance_score should be between 0 and 1."""
        sheet = SheetSchema(name="test", relevance_score=0.75)
        assert sheet.relevance_score == 0.75

        with pytest.raises(ValidationError):
            SheetSchema(name="test", relevance_score=1.5)

        with pytest.raises(ValidationError):
            SheetSchema(name="test", relevance_score=-0.1)

    def test_row_count_non_negative(self):
        """row_count should be non-negative."""
        sheet = SheetSchema(name="test", row_count=0)
        assert sheet.row_count == 0

        with pytest.raises(ValidationError):
            SheetSchema(name="test", row_count=-1)


class TestExcelSchema:
    """Tests for ExcelSchema model."""

    def test_create_valid_excel(self):
        """Valid Excel schema creation."""
        sheet = SheetSchema(name="Sheet1", row_count=50)
        excel = ExcelSchema(
            file_name="report.xlsx",
            file_size_mb=2.5,
            sheets={"Sheet1": sheet}
        )
        assert excel.file_name == "report.xlsx"
        assert excel.file_size_mb == 2.5
        assert len(excel.sheets) == 1

    def test_file_name_validation_xlsx(self):
        """Should accept .xlsx files."""
        excel = ExcelSchema(file_name="test.xlsx", file_size_mb=1.0)
        assert excel.file_name == "test.xlsx"

    def test_file_name_validation_xls(self):
        """Should accept .xls files."""
        excel = ExcelSchema(file_name="test.xls", file_size_mb=1.0)
        assert excel.file_name == "test.xls"

    def test_file_name_validation_uppercase(self):
        """Should accept uppercase extensions."""
        excel = ExcelSchema(file_name="TEST.XLSX", file_size_mb=1.0)
        assert excel.file_name == "TEST.XLSX"

    def test_file_name_invalid_extension_raises(self):
        """Invalid extension should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ExcelSchema(file_name="test.csv", file_size_mb=1.0)
        assert "Excel file" in str(exc_info.value)

    def test_file_name_empty_raises(self):
        """Empty file name should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ExcelSchema(file_name="", file_size_mb=1.0)
        assert "File name cannot be empty" in str(exc_info.value)

    def test_file_size_max_limit(self):
        """File size should not exceed 10MB."""
        excel = ExcelSchema(file_name="test.xlsx", file_size_mb=10.0)
        assert excel.file_size_mb == 10.0

        with pytest.raises(ValidationError):
            ExcelSchema(file_name="test.xlsx", file_size_mb=10.1)

    def test_file_size_min_limit(self):
        """File size should be non-negative."""
        excel = ExcelSchema(file_name="test.xlsx", file_size_mb=0.0)
        assert excel.file_size_mb == 0.0

        with pytest.raises(ValidationError):
            ExcelSchema(file_name="test.xlsx", file_size_mb=-0.1)

    def test_sheets_max_limit(self):
        """Should not allow more than 50 sheets."""
        sheets = {f"Sheet{i}": SheetSchema(name=f"Sheet{i}") for i in range(50)}
        excel = ExcelSchema(file_name="test.xlsx", file_size_mb=1.0, sheets=sheets)
        assert len(excel.sheets) == 50

        sheets_51 = {f"Sheet{i}": SheetSchema(name=f"Sheet{i}") for i in range(51)}
        with pytest.raises(ValidationError) as exc_info:
            ExcelSchema(file_name="test.xlsx", file_size_mb=1.0, sheets=sheets_51)
        assert "Maximum 50 sheets" in str(exc_info.value)

    def test_sheet_names_property(self):
        """sheet_names should return list of sheet names."""
        sheets = {
            "데이터": SheetSchema(name="데이터"),
            "요약": SheetSchema(name="요약"),
        }
        excel = ExcelSchema(file_name="test.xlsx", file_size_mb=1.0, sheets=sheets)
        assert set(excel.sheet_names) == {"데이터", "요약"}

    def test_total_rows_property(self):
        """total_rows should sum all sheet row counts."""
        sheets = {
            "Sheet1": SheetSchema(name="Sheet1", row_count=100),
            "Sheet2": SheetSchema(name="Sheet2", row_count=200),
            "Sheet3": SheetSchema(name="Sheet3", row_count=50),
        }
        excel = ExcelSchema(file_name="test.xlsx", file_size_mb=1.0, sheets=sheets)
        assert excel.total_rows == 350

    def test_get_sheet_exists(self):
        """get_sheet should return sheet when exists."""
        sheet = SheetSchema(name="Sheet1", row_count=100)
        excel = ExcelSchema(
            file_name="test.xlsx",
            file_size_mb=1.0,
            sheets={"Sheet1": sheet}
        )
        result = excel.get_sheet("Sheet1")
        assert result is not None
        assert result.row_count == 100

    def test_get_sheet_not_exists(self):
        """get_sheet should return None when not exists."""
        excel = ExcelSchema(file_name="test.xlsx", file_size_mb=1.0)
        result = excel.get_sheet("NonExistent")
        assert result is None

    def test_to_context_string(self):
        """to_context_string should generate readable format."""
        cols = [
            ColumnInfo(
                name="name",
                dtype="string",
                sample_values=["김철수", "이영희"]
            ),
            ColumnInfo(
                name="score",
                dtype="int64",
                sample_values=["95", "87"]
            ),
        ]
        sheet = SheetSchema(name="Students", columns=cols, row_count=50)
        excel = ExcelSchema(
            file_name="grades.xlsx",
            file_size_mb=0.5,
            sheets={"Students": sheet}
        )

        context = excel.to_context_string()
        assert "grades.xlsx" in context
        assert "Students" in context
        assert "50 rows" in context
        assert "name" in context
        assert "string" in context
        assert "김철수" in context

    def test_unicode_sheet_names(self):
        """Should handle Korean/Unicode sheet names."""
        sheets = {
            "일일보고서": SheetSchema(name="일일보고서"),
            "月間サマリー": SheetSchema(name="月間サマリー"),
        }
        excel = ExcelSchema(file_name="report.xlsx", file_size_mb=1.0, sheets=sheets)
        assert "일일보고서" in excel.sheet_names
        assert "月間サマリー" in excel.sheet_names
