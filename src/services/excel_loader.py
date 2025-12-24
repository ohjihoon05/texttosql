"""Excel file loading and query execution using DuckDB."""

import os
import time
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.config import get_settings
from src.models.schema import ColumnInfo, ExcelSchema, SheetSchema
from src.models.query import QueryResult


class ExcelLoader:
    """Load Excel files and execute SQL queries using DuckDB."""

    def __init__(self, file_path: str | Path):
        """Initialize ExcelLoader with file path.

        Args:
            file_path: Path to Excel file (.xlsx or .xls)

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file exceeds size limit or invalid format
        """
        self.file_path = Path(file_path)
        self._validate_file()

        self.settings = get_settings()
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._schema: ExcelSchema | None = None
        self._dataframes: dict[str, pd.DataFrame] = {}

    def _validate_file(self) -> None:
        """Validate file exists and meets requirements."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"Excel file not found: {self.file_path}")

        if not self.file_path.suffix.lower() in (".xlsx", ".xls"):
            raise ValueError(f"Invalid file format: {self.file_path.suffix}")

        file_size_mb = self.file_path.stat().st_size / (1024 * 1024)
        settings = get_settings()
        if file_size_mb > settings.max_excel_size_mb:
            raise ValueError(
                f"File size {file_size_mb:.2f}MB exceeds limit "
                f"of {settings.max_excel_size_mb}MB"
            )

    def load(self) -> ExcelSchema:
        """Load Excel file and return schema.

        Returns:
            ExcelSchema with all sheet information

        Raises:
            Exception: If file loading fails
        """
        if self._schema is not None:
            return self._schema

        start_time = time.time()

        # Read all sheets
        excel_file = pd.ExcelFile(self.file_path)
        sheets: dict[str, SheetSchema] = {}

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            self._dataframes[sheet_name] = df

            # Build column info
            columns: list[ColumnInfo] = []
            for col_name in df.columns:
                col_data = df[col_name]
                sample_values = (
                    col_data.dropna()
                    .head(5)
                    .astype(str)
                    .tolist()
                )
                columns.append(
                    ColumnInfo(
                        name=str(col_name),
                        dtype=str(col_data.dtype),
                        nullable=col_data.isna().any(),
                        sample_values=sample_values,
                    )
                )

            sheets[sheet_name] = SheetSchema(
                name=sheet_name,
                columns=columns,
                row_count=len(df),
            )

        load_time = time.time() - start_time
        file_size_mb = self.file_path.stat().st_size / (1024 * 1024)

        self._schema = ExcelSchema(
            file_name=self.file_path.name,
            file_size_mb=round(file_size_mb, 2),
            sheets=sheets,
            load_time_seconds=round(load_time, 2),
        )

        # Initialize DuckDB connection with loaded data
        self._init_duckdb()

        return self._schema

    def _init_duckdb(self) -> None:
        """Initialize DuckDB connection and register DataFrames as tables."""
        self._conn = duckdb.connect(":memory:")

        for sheet_name, df in self._dataframes.items():
            # Skip empty DataFrames (DuckDB requires at least one column)
            if df.empty and len(df.columns) == 0:
                continue

            # Sanitize table name for SQL
            table_name = self._sanitize_table_name(sheet_name)
            self._conn.register(table_name, df)

    def _sanitize_table_name(self, name: str) -> str:
        """Sanitize sheet name for use as SQL table name.

        Args:
            name: Original sheet name

        Returns:
            Sanitized table name safe for SQL
        """
        # Replace spaces and special chars with underscores
        sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
        # Ensure doesn't start with number
        if sanitized and sanitized[0].isdigit():
            sanitized = "_" + sanitized
        return sanitized or "_unnamed"

    def get_schema(self) -> ExcelSchema:
        """Get schema of loaded Excel file.

        Returns:
            ExcelSchema with file and sheet information

        Raises:
            RuntimeError: If file hasn't been loaded yet
        """
        if self._schema is None:
            raise RuntimeError("Excel file not loaded. Call load() first.")
        return self._schema

    def get_table_mapping(self) -> dict[str, str]:
        """Get mapping of original sheet names to SQL table names.

        Returns:
            Dict mapping sheet name to sanitized table name
        """
        if self._schema is None:
            raise RuntimeError("Excel file not loaded. Call load() first.")

        return {
            sheet_name: self._sanitize_table_name(sheet_name)
            for sheet_name in self._schema.sheet_names
        }

    def execute_query(self, sql: str) -> QueryResult:
        """Execute SQL query on loaded Excel data.

        Args:
            sql: SQL query string (SELECT only)

        Returns:
            QueryResult with success status and data (as DataFrame)
        """
        if self._conn is None:
            raise RuntimeError("Excel file not loaded. Call load() first.")

        start_time = time.time()

        try:
            # Execute query
            result = self._conn.execute(sql)
            df = result.df()

            execution_time = (time.time() - start_time) * 1000  # ms

            return QueryResult(
                success=True,
                data=df,
                row_count=len(df),
                column_names=list(df.columns),
                execution_time_ms=round(execution_time, 2),
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return QueryResult(
                success=False,
                error_message=str(e),
                execution_time_ms=round(execution_time, 2),
            )

    def execute_query_with_auto_cast(self, sql: str) -> QueryResult:
        """Execute SQL with automatic VARCHAR casting on type mismatch (EH-002).

        Args:
            sql: SQL query string

        Returns:
            QueryResult with auto-cast fallback on type errors
        """
        # First try without casting
        result = self.execute_query(sql)

        if result.success:
            return result

        # Check if error is type mismatch
        error_msg = result.error_message or ""
        type_error_keywords = [
            "Type mismatch",
            "UNION type",
            "incompatible types",
            "Cannot compare",
            "type conversion",
        ]

        is_type_error = any(kw.lower() in error_msg.lower() for kw in type_error_keywords)

        if not is_type_error:
            return result

        # Try with VARCHAR casting
        logger.info("Type mismatch detected, attempting VARCHAR auto-casting")

        casted_sql = self._add_varchar_casting(sql)
        if casted_sql == sql:
            # No changes made, return original error
            return result

        casted_result = self.execute_query(casted_sql)
        if casted_result.success:
            logger.info("VARCHAR auto-casting successful")
        return casted_result

    def _add_varchar_casting(self, sql: str) -> str:
        """Add CAST(column AS VARCHAR) to SELECT columns in UNION queries.

        Args:
            sql: Original SQL query

        Returns:
            SQL with VARCHAR casting applied
        """
        import re

        # Simple approach: wrap each column in CAST AS VARCHAR for UNION queries
        if "UNION" not in sql.upper():
            return sql

        # Split by UNION ALL or UNION
        parts = re.split(r'\bUNION\s+ALL\b|\bUNION\b', sql, flags=re.IGNORECASE)
        if len(parts) < 2:
            return sql

        casted_parts = []
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Extract SELECT columns
            match = re.match(
                r'SELECT\s+(.+?)\s+FROM\s+(.+)',
                part,
                re.IGNORECASE | re.DOTALL
            )
            if not match:
                casted_parts.append(part)
                continue

            columns_str = match.group(1)
            rest = match.group(2)

            # Parse columns (simple split by comma, respecting parentheses)
            columns = self._split_columns(columns_str)

            # Wrap each column in CAST AS VARCHAR
            casted_columns = []
            for col in columns:
                col = col.strip()
                # Skip if already casted or is a literal/function
                if "CAST(" in col.upper() or "'" in col:
                    casted_columns.append(col)
                elif " as " in col.lower():
                    # Has alias: col as alias
                    col_parts = re.split(r'\s+as\s+', col, flags=re.IGNORECASE)
                    original = col_parts[0].strip()
                    alias = col_parts[-1].strip()
                    casted_columns.append(f"CAST({original} AS VARCHAR) as {alias}")
                else:
                    casted_columns.append(f"CAST({col} AS VARCHAR)")

            casted_parts.append(f"SELECT {', '.join(casted_columns)} FROM {rest}")

        return "\nUNION ALL\n".join(casted_parts)

    def _split_columns(self, columns_str: str) -> list[str]:
        """Split column list respecting parentheses.

        Args:
            columns_str: Comma-separated column string

        Returns:
            List of column expressions
        """
        columns = []
        current = ""
        paren_depth = 0

        for char in columns_str:
            if char == '(':
                paren_depth += 1
                current += char
            elif char == ')':
                paren_depth -= 1
                current += char
            elif char == ',' and paren_depth == 0:
                columns.append(current.strip())
                current = ""
            else:
                current += char

        if current.strip():
            columns.append(current.strip())

        return columns

    def close(self) -> None:
        """Close DuckDB connection and cleanup resources."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self._dataframes.clear()
        self._schema = None

    def __enter__(self) -> "ExcelLoader":
        """Context manager entry."""
        self.load()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
