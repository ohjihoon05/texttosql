"""Query-related models for Text-to-SQL system."""

from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional
from datetime import datetime

from .schema import SheetSchema


class ResponseType(str, Enum):
    """Response type classification based on result count."""

    EMPTY = "empty"  # 0 rows
    SINGLE = "single"  # 1 row
    FEW = "few"  # 2-10 rows
    MANY = "many"  # 10+ rows
    ERROR = "error"  # Query failed


class ResponseContext(BaseModel):
    """Context for LLM response generation."""

    question: str = Field(..., description="Original user question")
    sql_query: str = Field(default="", description="Executed SQL query")
    row_count: int = Field(default=0, ge=0, description="Number of result rows")
    column_names: List[str] = Field(default_factory=list, description="Column names")
    sample_data: List[Dict[str, Any]] = Field(
        default_factory=list, description="Sample data rows (max 5)"
    )
    response_type: ResponseType = Field(
        default=ResponseType.EMPTY, description="Response type classification"
    )


class QueryContext(BaseModel):
    """Context for SQL generation."""

    question: str = Field(..., min_length=1, max_length=500, description="User's natural language question")
    relevant_sheets: List[SheetSchema] = Field(
        default_factory=list,
        description="Filtered relevant sheets"
    )
    terminology_hints: List[str] = Field(
        default_factory=list,
        description="RAG terminology hints"
    )
    previous_queries: List[str] = Field(
        default_factory=list,
        description="Previous queries in conversation"
    )

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()

    @field_validator("relevant_sheets")
    @classmethod
    def limit_relevant_sheets(cls, v: List[SheetSchema]) -> List[SheetSchema]:
        if len(v) > 10:
            raise ValueError("Maximum 10 relevant sheets allowed")
        return v


class SQLQuery(BaseModel):
    """Generated SQL query."""

    raw_sql: str = Field(..., description="Raw SQL query string")
    explanation: str = Field(default="", description="Natural language explanation of the query")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")
    tables_used: List[str] = Field(default_factory=list, description="Tables referenced in query")

    @field_validator("raw_sql")
    @classmethod
    def validate_sql(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("SQL query cannot be empty")
        v = v.strip()
        # Basic validation: only SELECT queries allowed
        if not v.upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")
        # Block dangerous operations
        dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"]
        for keyword in dangerous:
            if keyword in v.upper():
                raise ValueError(f"{keyword} operations are not allowed")
        return v


class QueryResult(BaseModel):
    """Result of executing a query."""

    success: bool = Field(..., description="Whether query execution succeeded")
    data: List[Dict[str, Any]] = Field(default_factory=list, description="Query result data")
    row_count: int = Field(default=0, ge=0, description="Number of rows returned")
    column_names: List[str] = Field(default_factory=list, description="Column names in result")
    execution_time_ms: float = Field(default=0.0, ge=0, description="Execution time in milliseconds")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")

    @property
    def is_empty(self) -> bool:
        """Check if result has no data."""
        return self.row_count == 0

    def to_markdown_table(self, max_rows: int = 20) -> str:
        """Convert result to markdown table format."""
        if not self.success:
            return f"Error: {self.error_message}"

        if self.is_empty:
            return "No results found."

        if not self.column_names:
            return "No columns in result."

        # Header
        lines = ["| " + " | ".join(self.column_names) + " |"]
        lines.append("| " + " | ".join(["---"] * len(self.column_names)) + " |")

        # Data rows (limit to max_rows)
        for row in self.data[:max_rows]:
            values = [str(row.get(col, "")) for col in self.column_names]
            lines.append("| " + " | ".join(values) + " |")

        if self.row_count > max_rows:
            lines.append(f"\n... and {self.row_count - max_rows} more rows")

        return "\n".join(lines)


class FormattedResponse(BaseModel):
    """Final formatted response for user."""

    answer: str = Field(..., description="Natural language answer")
    sql_query: str = Field(default="", description="SQL query used")
    data_preview: str = Field(default="", description="Data preview in table format")
    source_sheets: List[str] = Field(default_factory=list, description="Source sheet names")
    response_type: ResponseType = Field(
        default=ResponseType.EMPTY, description="Response type classification"
    )
    suggested_questions: List[str] = Field(
        default_factory=list, description="Suggested follow-up questions"
    )


class CacheEntry(BaseModel):
    """Cache entry for query results."""

    question_hash: str = Field(..., description="Hash of the question")
    question: str = Field(..., description="Original question")
    sql_query: str = Field(..., description="Generated SQL query")
    result_json: str = Field(..., description="JSON-serialized result")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    hit_count: int = Field(default=0, ge=0, description="Number of cache hits")

    @field_validator("expires_at")
    @classmethod
    def expires_after_created(cls, v: datetime, info) -> datetime:
        created = info.data.get("created_at", datetime.now())
        if v <= created:
            raise ValueError("expires_at must be after created_at")
        return v

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.now() > self.expires_at
