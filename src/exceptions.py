"""Custom exceptions for Text-to-SQL system.

This module provides exception classes for error handling across
the multi-sheet query system.
"""


class TextToSQLError(Exception):
    """Base exception class for Text-to-SQL system."""

    pass


class SheetGroupError(TextToSQLError):
    """Sheet group related errors."""

    pass


class NoCommonColumnsError(SheetGroupError):
    """Raised when no common columns found between sheets.

    This typically occurs when trying to UNION sheets with
    completely different column structures.
    """

    def __init__(self, sheets: list[str]):
        """Initialize NoCommonColumnsError.

        Args:
            sheets: List of sheet names that have no common columns
        """
        self.sheets = sheets
        super().__init__(
            f"No common columns found between sheets: {', '.join(sheets)}"
        )


class IncompatibleSheetsError(SheetGroupError):
    """Raised when trying to UNION incompatible sheet groups.

    Some sheet groups cannot be combined via UNION because they
    represent fundamentally different data structures.
    """

    def __init__(self, group1: str, group2: str):
        """Initialize IncompatibleSheetsError.

        Args:
            group1: First group name
            group2: Second group name
        """
        self.group1 = group1
        self.group2 = group2
        super().__init__(
            f"Cannot UNION sheets from incompatible groups: {group1} and {group2}"
        )


class TooManySheetsError(SheetGroupError):
    """Raised when too many sheets are selected for UNION.

    There is a configurable limit on the number of sheets that
    can be combined in a single UNION query.
    """

    def __init__(self, count: int, max_count: int):
        """Initialize TooManySheetsError.

        Args:
            count: Actual number of sheets selected
            max_count: Maximum allowed sheets
        """
        self.count = count
        self.max_count = max_count
        super().__init__(
            f"Too many sheets selected: {count} (max: {max_count})"
        )


class LLMGenerationError(TextToSQLError):
    """LLM SQL generation errors."""

    pass


class UnionSQLGenerationError(LLMGenerationError):
    """Raised when UNION SQL generation fails.

    This can occur due to invalid schema, unsupported query patterns,
    or LLM failures.
    """

    def __init__(self, reason: str, attempted_sql: str | None = None):
        """Initialize UnionSQLGenerationError.

        Args:
            reason: Why the SQL generation failed
            attempted_sql: The SQL that was attempted (if available)
        """
        self.reason = reason
        self.attempted_sql = attempted_sql
        super().__init__(f"Failed to generate UNION SQL: {reason}")


class QueryExecutionError(TextToSQLError):
    """Query execution errors.

    Raised when a valid SQL query fails during execution,
    such as DuckDB runtime errors or data type mismatches.
    """

    pass


class QueryTimeoutError(QueryExecutionError):
    """Raised when query execution exceeds the timeout limit."""

    def __init__(self, timeout_seconds: float, query: str | None = None):
        """Initialize QueryTimeoutError.

        Args:
            timeout_seconds: The timeout limit that was exceeded
            query: The query that timed out (if available)
        """
        self.timeout_seconds = timeout_seconds
        self.query = query
        super().__init__(
            f"Query execution timed out after {timeout_seconds} seconds"
        )


class SchemaError(TextToSQLError):
    """Schema-related errors."""

    pass


class SheetNotFoundError(SchemaError):
    """Raised when a requested sheet does not exist."""

    def __init__(self, sheet_name: str, available_sheets: list[str] | None = None):
        """Initialize SheetNotFoundError.

        Args:
            sheet_name: The sheet that was not found
            available_sheets: List of available sheets (if known)
        """
        self.sheet_name = sheet_name
        self.available_sheets = available_sheets or []
        message = f"Sheet not found: {sheet_name}"
        if available_sheets:
            message += f". Available sheets: {', '.join(available_sheets[:5])}"
            if len(available_sheets) > 5:
                message += f" ... ({len(available_sheets) - 5} more)"
        super().__init__(message)
