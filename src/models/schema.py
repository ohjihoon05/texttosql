"""Excel schema models for Text-to-SQL system."""

from pydantic import BaseModel, Field, field_validator
from typing import Dict, List


class ColumnInfo(BaseModel):
    """Column information within a sheet."""

    name: str = Field(..., description="Column name")
    dtype: str = Field(..., description="Data type (string, int64, float64, datetime64, etc.)")
    nullable: bool = Field(default=True, description="Whether column allows null values")
    sample_values: List[str] = Field(
        default_factory=list,
        description="Sample values from the column (top 5)"
    )

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Column name cannot be empty")
        return v.strip()


class SheetSchema(BaseModel):
    """Schema for a single Excel sheet."""

    name: str = Field(..., description="Sheet name")
    columns: List[ColumnInfo] = Field(default_factory=list, description="List of columns")
    row_count: int = Field(default=0, ge=0, description="Number of rows in the sheet")
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Relevance score for query filtering"
    )

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Sheet name cannot be empty")
        return v.strip()

    @property
    def column_names(self) -> List[str]:
        """Get list of column names."""
        return [col.name for col in self.columns]


class ExcelSchema(BaseModel):
    """Schema for an entire Excel file."""

    file_name: str = Field(..., description="Excel file name")
    file_size_mb: float = Field(..., ge=0, le=10, description="File size in MB (max 10MB)")
    sheets: Dict[str, SheetSchema] = Field(
        default_factory=dict,
        description="Dictionary of sheet name to schema"
    )
    load_time_seconds: float = Field(default=0.0, ge=0, description="Time taken to load file")

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("File name cannot be empty")
        if not v.lower().endswith((".xlsx", ".xls")):
            raise ValueError("File must be an Excel file (.xlsx or .xls)")
        return v.strip()

    @field_validator("sheets")
    @classmethod
    def validate_sheets(cls, v: Dict[str, SheetSchema]) -> Dict[str, SheetSchema]:
        if len(v) > 50:
            raise ValueError("Maximum 50 sheets allowed")
        return v

    @property
    def sheet_names(self) -> List[str]:
        """Get list of sheet names."""
        return list(self.sheets.keys())

    @property
    def total_rows(self) -> int:
        """Get total row count across all sheets."""
        return sum(sheet.row_count for sheet in self.sheets.values())

    def get_sheet(self, name: str) -> SheetSchema | None:
        """Get sheet schema by name."""
        return self.sheets.get(name)

    def to_context_string(self) -> str:
        """Convert schema to string for LLM context."""
        lines = [f"Excel File: {self.file_name}"]
        lines.append(f"Total Sheets: {len(self.sheets)}")
        lines.append("")

        for sheet_name, sheet in self.sheets.items():
            lines.append(f"Sheet: {sheet_name} ({sheet.row_count} rows)")
            for col in sheet.columns:
                sample = ", ".join(col.sample_values[:3]) if col.sample_values else "N/A"
                lines.append(f"  - {col.name} ({col.dtype}): {sample}")
            lines.append("")

        return "\n".join(lines)
