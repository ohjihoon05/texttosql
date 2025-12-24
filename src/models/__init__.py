"""Data models for Excel Text-to-SQL system."""

from .schema import ColumnInfo, SheetSchema, ExcelSchema
from .query import QueryContext, SQLQuery, QueryResult, FormattedResponse, CacheEntry
from .sheet_group import (
    QuestionType,
    UnionStrategy,
    SheetGroup,
    SheetGroupConfig,
    SheetSelection,
    MultiSheetContext,
    SheetResultSummary,
    UnionQueryResult,
)

__all__ = [
    # Schema models
    "ColumnInfo",
    "SheetSchema",
    "ExcelSchema",
    # Query models
    "QueryContext",
    "SQLQuery",
    "QueryResult",
    "FormattedResponse",
    "CacheEntry",
    # Multi-sheet models
    "QuestionType",
    "UnionStrategy",
    "SheetGroup",
    "SheetGroupConfig",
    "SheetSelection",
    "MultiSheetContext",
    "SheetResultSummary",
    "UnionQueryResult",
]
