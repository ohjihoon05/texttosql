"""Unit tests for query models."""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from pydantic import ValidationError

from src.models.query import (
    QueryContext,
    SQLQuery,
    QueryResult,
    FormattedResponse,
    CacheEntry,
)
from src.models.schema import SheetSchema, ColumnInfo
from src.models.sheet_group import (
    MultiSheetContext,
    QuestionType,
    SheetSelection,
    UnionStrategy,
)


class TestQueryContext:
    """Tests for QueryContext model."""

    def test_create_valid_context(self):
        """Valid query context creation."""
        ctx = QueryContext(
            question="김철수가 어떤 작업을 했어?",
            relevant_sheets=[],
            terminology_hints=["CS", "설비"],
            previous_queries=[]
        )
        assert ctx.question == "김철수가 어떤 작업을 했어?"
        assert ctx.terminology_hints == ["CS", "설비"]

    def test_question_stripped(self):
        """Question should be stripped of whitespace."""
        ctx = QueryContext(question="  질문입니다  ")
        assert ctx.question == "질문입니다"

    def test_question_empty_raises(self):
        """Empty question should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            QueryContext(question="")
        # Either min_length validation or custom validator triggers
        error_msg = str(exc_info.value).lower()
        assert "question" in error_msg and ("empty" in error_msg or "character" in error_msg)

    def test_question_whitespace_only_raises(self):
        """Whitespace-only question should raise."""
        with pytest.raises(ValidationError) as exc_info:
            QueryContext(question="   ")
        assert "Question cannot be empty" in str(exc_info.value)

    def test_question_min_length(self):
        """Question must be at least 1 character."""
        ctx = QueryContext(question="?")
        assert ctx.question == "?"

    def test_question_max_length(self):
        """Question must not exceed 500 characters."""
        valid_question = "a" * 500
        ctx = QueryContext(question=valid_question)
        assert len(ctx.question) == 500

        with pytest.raises(ValidationError):
            QueryContext(question="a" * 501)

    def test_relevant_sheets_limit(self):
        """Maximum 10 relevant sheets allowed."""
        sheets = [SheetSchema(name=f"Sheet{i}") for i in range(10)]
        ctx = QueryContext(question="test", relevant_sheets=sheets)
        assert len(ctx.relevant_sheets) == 10

        sheets_11 = [SheetSchema(name=f"Sheet{i}") for i in range(11)]
        with pytest.raises(ValidationError) as exc_info:
            QueryContext(question="test", relevant_sheets=sheets_11)
        assert "Maximum 10 relevant sheets" in str(exc_info.value)

    def test_default_values(self):
        """Default values should be empty lists."""
        ctx = QueryContext(question="test question")
        assert ctx.relevant_sheets == []
        assert ctx.terminology_hints == []
        assert ctx.previous_queries == []


class TestQueryContextMultiSheet:
    """Tests for QueryContext multi-sheet support (T056)."""

    def test_multi_sheet_context_field_exists(self):
        """QueryContext should have optional multi_sheet_context field."""
        ctx = QueryContext(question="김철수가 뭘 했어?")
        assert hasattr(ctx, "multi_sheet_context")
        assert ctx.multi_sheet_context is None

    def test_multi_sheet_context_with_value(self):
        """QueryContext should accept MultiSheetContext."""
        multi_ctx = MultiSheetContext(
            question_type=QuestionType.PERSON,
            selected_sheets=[
                SheetSelection(sheet_name="Daily_20241217", group_name="TICKET_DAILY"),
                SheetSelection(sheet_name="Daily_20241218", group_name="TICKET_DAILY"),
            ],
            common_columns=["날짜", "담당자", "티켓번호"],
            use_union=True,
        )
        ctx = QueryContext(
            question="김철수가 뭘 했어?",
            multi_sheet_context=multi_ctx,
        )
        assert ctx.multi_sheet_context is not None
        assert ctx.multi_sheet_context.question_type == QuestionType.PERSON
        assert ctx.multi_sheet_context.sheet_count == 2
        assert ctx.multi_sheet_context.use_union is True

    def test_multi_sheet_context_is_optional(self):
        """multi_sheet_context should be optional."""
        ctx = QueryContext(question="테스트 질문")
        assert ctx.multi_sheet_context is None

    def test_multi_sheet_context_with_union_strategy(self):
        """MultiSheetContext should contain union_strategy."""
        multi_ctx = MultiSheetContext(
            question_type=QuestionType.PERIOD,
            selected_sheets=[],
            use_union=False,
            union_strategy=UnionStrategy.COMMON_COLUMNS,
        )
        ctx = QueryContext(
            question="이번 주 완료된 작업",
            multi_sheet_context=multi_ctx,
        )
        assert ctx.multi_sheet_context.union_strategy == UnionStrategy.COMMON_COLUMNS

    def test_query_context_requires_union_property(self):
        """QueryContext should expose requires_union from multi_sheet_context."""
        # Without multi_sheet_context
        ctx = QueryContext(question="질문")
        assert ctx.requires_union is False

        # With multi_sheet_context (single sheet)
        multi_ctx_single = MultiSheetContext(
            question_type=QuestionType.PERSON,
            selected_sheets=[
                SheetSelection(sheet_name="Daily_20241217", group_name="TICKET_DAILY"),
            ],
        )
        ctx_single = QueryContext(question="질문", multi_sheet_context=multi_ctx_single)
        assert ctx_single.requires_union is False

        # With multi_sheet_context (multiple sheets)
        multi_ctx_multi = MultiSheetContext(
            question_type=QuestionType.PERSON,
            selected_sheets=[
                SheetSelection(sheet_name="Daily_20241217", group_name="TICKET_DAILY"),
                SheetSelection(sheet_name="Daily_20241218", group_name="TICKET_DAILY"),
            ],
        )
        ctx_multi = QueryContext(question="질문", multi_sheet_context=multi_ctx_multi)
        assert ctx_multi.requires_union is True

    def test_query_context_sheet_names_property(self):
        """QueryContext should expose sheet_names from multi_sheet_context."""
        # Without multi_sheet_context
        ctx = QueryContext(question="질문")
        assert ctx.sheet_names == []

        # With multi_sheet_context
        multi_ctx = MultiSheetContext(
            question_type=QuestionType.PERSON,
            selected_sheets=[
                SheetSelection(sheet_name="Daily_20241217", group_name="TICKET_DAILY"),
                SheetSelection(sheet_name="Daily_20241218", group_name="TICKET_DAILY"),
            ],
        )
        ctx_with = QueryContext(question="질문", multi_sheet_context=multi_ctx)
        assert ctx_with.sheet_names == ["Daily_20241217", "Daily_20241218"]


class TestSQLQuery:
    """Tests for SQLQuery model."""

    def test_create_valid_query(self):
        """Valid SQL query creation."""
        query = SQLQuery(
            raw_sql="SELECT * FROM customers WHERE name = '김철수'",
            explanation="김철수 이름으로 검색",
            confidence=0.85,
            tables_used=["customers"]
        )
        assert "SELECT" in query.raw_sql
        assert query.confidence == 0.85

    def test_sql_stripped(self):
        """SQL should be stripped of whitespace."""
        query = SQLQuery(raw_sql="  SELECT * FROM test  ")
        assert query.raw_sql == "SELECT * FROM test"

    def test_sql_empty_raises(self):
        """Empty SQL should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SQLQuery(raw_sql="")
        assert "SQL query cannot be empty" in str(exc_info.value)

    def test_sql_must_start_with_select(self):
        """SQL must start with SELECT."""
        with pytest.raises(ValidationError) as exc_info:
            SQLQuery(raw_sql="UPDATE users SET name = 'test'")
        assert "Only SELECT queries are allowed" in str(exc_info.value)

    def test_sql_case_insensitive_select(self):
        """SELECT check should be case-insensitive."""
        query = SQLQuery(raw_sql="select * from test")
        assert query.raw_sql == "select * from test"

        query2 = SQLQuery(raw_sql="Select name From test")
        assert "Select" in query2.raw_sql

    def test_dangerous_operations_blocked(self):
        """Dangerous SQL operations should be blocked."""
        dangerous_queries = [
            "SELECT * FROM users; INSERT INTO log VALUES (1)",
            "SELECT * FROM users; UPDATE users SET admin = 1",
            "SELECT * FROM users; DELETE FROM users",
            "SELECT * FROM users; DROP TABLE users",
            "SELECT * FROM users; CREATE TABLE hack (id INT)",
            "SELECT * FROM users; ALTER TABLE users ADD col INT",
            "SELECT * FROM users; TRUNCATE TABLE users",
        ]
        for sql in dangerous_queries:
            with pytest.raises(ValidationError) as exc_info:
                SQLQuery(raw_sql=sql)
            assert "not allowed" in str(exc_info.value).lower()

    def test_confidence_range(self):
        """Confidence must be between 0 and 1."""
        query = SQLQuery(raw_sql="SELECT 1", confidence=0.0)
        assert query.confidence == 0.0

        query = SQLQuery(raw_sql="SELECT 1", confidence=1.0)
        assert query.confidence == 1.0

        with pytest.raises(ValidationError):
            SQLQuery(raw_sql="SELECT 1", confidence=-0.1)

        with pytest.raises(ValidationError):
            SQLQuery(raw_sql="SELECT 1", confidence=1.1)

    def test_default_values(self):
        """Default values should be applied."""
        query = SQLQuery(raw_sql="SELECT * FROM test")
        assert query.explanation == ""
        assert query.confidence == 0.0
        assert query.tables_used == []


class TestQueryResult:
    """Tests for QueryResult model."""

    def test_create_successful_result(self):
        """Successful query result creation."""
        df = pd.DataFrame([
            {"id": 1, "name": "김철수"},
            {"id": 2, "name": "이영희"}
        ])
        result = QueryResult(
            success=True,
            data=df,
            row_count=2,
            column_names=["id", "name"],
            execution_time_ms=45.5
        )
        assert result.success is True
        assert result.row_count == 2
        assert not result.is_empty

    def test_create_failed_result(self):
        """Failed query result creation."""
        result = QueryResult(
            success=False,
            error_message="Table not found"
        )
        assert result.success is False
        assert result.error_message == "Table not found"

    def test_is_empty_property(self):
        """is_empty should return True when row_count is 0."""
        result = QueryResult(success=True, row_count=0)
        assert result.is_empty is True

        result = QueryResult(success=True, row_count=1)
        assert result.is_empty is False

    def test_to_markdown_table_success(self):
        """to_markdown_table should generate valid markdown."""
        df = pd.DataFrame([
            {"name": "김철수", "score": 95},
            {"name": "이영희", "score": 87},
        ])
        result = QueryResult(
            success=True,
            data=df,
            row_count=2,
            column_names=["name", "score"]
        )
        md = result.to_markdown_table()
        assert "| name | score |" in md
        assert "| --- | --- |" in md
        assert "| 김철수 | 95 |" in md
        assert "| 이영희 | 87 |" in md

    def test_to_markdown_table_empty(self):
        """to_markdown_table should handle empty results."""
        result = QueryResult(success=True, row_count=0)
        md = result.to_markdown_table()
        assert "No results found" in md

    def test_to_markdown_table_error(self):
        """to_markdown_table should show error message on failure."""
        result = QueryResult(
            success=False,
            error_message="Invalid SQL syntax"
        )
        md = result.to_markdown_table()
        assert "Error:" in md
        assert "Invalid SQL syntax" in md

    def test_to_markdown_table_no_columns(self):
        """to_markdown_table should handle no columns case."""
        result = QueryResult(
            success=True,
            row_count=1,
            column_names=[]
        )
        md = result.to_markdown_table()
        assert "No columns" in md

    def test_to_markdown_table_max_rows(self):
        """to_markdown_table should limit rows."""
        df = pd.DataFrame([{"id": i} for i in range(100)])
        result = QueryResult(
            success=True,
            data=df,
            row_count=100,
            column_names=["id"]
        )
        md = result.to_markdown_table(max_rows=20)
        assert "80 more rows" in md

    def test_execution_time_non_negative(self):
        """execution_time_ms should be non-negative."""
        result = QueryResult(success=True, execution_time_ms=0.0)
        assert result.execution_time_ms == 0.0

        with pytest.raises(ValidationError):
            QueryResult(success=True, execution_time_ms=-1.0)

    def test_row_count_non_negative(self):
        """row_count should be non-negative."""
        result = QueryResult(success=True, row_count=0)
        assert result.row_count == 0

        with pytest.raises(ValidationError):
            QueryResult(success=True, row_count=-1)

    def test_to_dict_list(self):
        """to_dict_list should convert DataFrame to list of dicts."""
        df = pd.DataFrame([
            {"id": 1, "name": "김철수"},
            {"id": 2, "name": "이영희"}
        ])
        result = QueryResult(
            success=True,
            data=df,
            row_count=2,
            column_names=["id", "name"]
        )
        data_list = result.to_dict_list()
        assert len(data_list) == 2
        assert data_list[0]["name"] == "김철수"

    def test_to_dict_list_empty(self):
        """to_dict_list should return empty list when data is None."""
        result = QueryResult(success=True, row_count=0)
        data_list = result.to_dict_list()
        assert data_list == []


class TestFormattedResponse:
    """Tests for FormattedResponse model."""

    def test_create_valid_response(self):
        """Valid formatted response creation."""
        response = FormattedResponse(
            answer="김철수는 3건의 CS를 처리했습니다.",
            sql_query="SELECT COUNT(*) FROM cs WHERE engineer = '김철수'",
            data_preview="| count |\n|---|\n| 3 |",
            source_sheets=["CS_Daily", "Engineer_Log"]
        )
        assert "김철수" in response.answer
        assert len(response.source_sheets) == 2

    def test_default_values(self):
        """Default values should be applied."""
        response = FormattedResponse(answer="Test answer")
        assert response.sql_query == ""
        assert response.data_preview == ""
        assert response.source_sheets == []


class TestCacheEntry:
    """Tests for CacheEntry model."""

    def test_create_valid_cache_entry(self):
        """Valid cache entry creation."""
        now = datetime.now()
        entry = CacheEntry(
            question_hash="abc123",
            question="김철수가 뭘 했어?",
            sql_query="SELECT * FROM cs WHERE name = '김철수'",
            result_json='{"rows": []}',
            created_at=now,
            expires_at=now + timedelta(hours=1)
        )
        assert entry.question_hash == "abc123"
        assert entry.hit_count == 0
        assert not entry.is_expired

    def test_is_expired_property(self):
        """is_expired should correctly identify expired entries."""
        now = datetime.now()
        # Not expired
        entry = CacheEntry(
            question_hash="hash1",
            question="test",
            sql_query="SELECT 1",
            result_json="{}",
            created_at=now,
            expires_at=now + timedelta(hours=1)
        )
        assert entry.is_expired is False

        # Already expired
        expired_entry = CacheEntry(
            question_hash="hash2",
            question="test",
            sql_query="SELECT 1",
            result_json="{}",
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1)
        )
        assert expired_entry.is_expired is True

    def test_expires_at_must_be_after_created(self):
        """expires_at must be after created_at."""
        now = datetime.now()
        with pytest.raises(ValidationError) as exc_info:
            CacheEntry(
                question_hash="hash",
                question="test",
                sql_query="SELECT 1",
                result_json="{}",
                created_at=now,
                expires_at=now - timedelta(seconds=1)
            )
        assert "expires_at must be after created_at" in str(exc_info.value)

    def test_hit_count_non_negative(self):
        """hit_count should be non-negative."""
        now = datetime.now()
        entry = CacheEntry(
            question_hash="hash",
            question="test",
            sql_query="SELECT 1",
            result_json="{}",
            created_at=now,
            expires_at=now + timedelta(hours=1),
            hit_count=0
        )
        assert entry.hit_count == 0

        with pytest.raises(ValidationError):
            CacheEntry(
                question_hash="hash",
                question="test",
                sql_query="SELECT 1",
                result_json="{}",
                created_at=now,
                expires_at=now + timedelta(hours=1),
                hit_count=-1
            )
