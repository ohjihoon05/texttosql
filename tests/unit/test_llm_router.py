"""Unit tests for LLM Router service."""

import pytest

from src.services.llm_router import LLMRouter
from src.models.sheet_group import QuestionType


@pytest.fixture
def llm_router() -> LLMRouter:
    """Create LLMRouter instance for testing."""
    return LLMRouter()


class TestBuildWhereClause:
    """Tests for _build_where_clause method (T038)."""

    def test_period_with_date_range(self, llm_router: LLMRouter):
        """PERIOD query with date range should generate date filter."""
        period_info = {
            "period_type": "week",
            "start_date": "2024-12-16",
            "end_date": "2024-12-22",
            "relative": "this",
            "raw_expression": "이번 주",
        }
        result = llm_router._build_where_clause(
            question="이번 주 완료된 티켓",
            question_type=QuestionType.PERIOD,
            period_info=period_info,
        )
        assert "날짜 >=" in result
        assert "2024-12-16" in result
        assert "2024-12-22" in result

    def test_period_with_single_date(self, llm_router: LLMRouter):
        """PERIOD query with single date should use equality."""
        period_info = {
            "period_type": "day",
            "start_date": "2024-12-17",
            "end_date": "2024-12-17",
            "relative": "specific",
            "raw_expression": "2024-12-17",
        }
        result = llm_router._build_where_clause(
            question="2024-12-17 티켓 조회",
            question_type=QuestionType.PERIOD,
            period_info=period_info,
        )
        assert "날짜 = '2024-12-17'" in result

    def test_period_with_status_completed(self, llm_router: LLMRouter):
        """PERIOD query with 완료 should include status filter."""
        period_info = {
            "period_type": "week",
            "start_date": "2024-12-16",
            "end_date": "2024-12-22",
            "relative": "this",
            "raw_expression": "이번 주",
        }
        result = llm_router._build_where_clause(
            question="이번 주 완료된 티켓",
            question_type=QuestionType.PERIOD,
            period_info=period_info,
        )
        assert "상태 = '완료'" in result

    def test_period_with_status_in_progress(self, llm_router: LLMRouter):
        """PERIOD query with 진행 should include status filter."""
        period_info = {
            "period_type": "week",
            "start_date": "2024-12-16",
            "end_date": "2024-12-22",
            "relative": "this",
            "raw_expression": "이번 주",
        }
        result = llm_router._build_where_clause(
            question="이번 주 진행중인 작업",
            question_type=QuestionType.PERIOD,
            period_info=period_info,
        )
        assert "상태 = '진행중'" in result

    def test_period_without_period_info(self, llm_router: LLMRouter):
        """PERIOD query without period_info should still check status."""
        result = llm_router._build_where_clause(
            question="완료된 작업 조회",
            question_type=QuestionType.PERIOD,
            period_info=None,
        )
        assert "상태 = '완료'" in result

    def test_person_query_extracts_name(self, llm_router: LLMRouter):
        """PERSON query should extract Korean name."""
        result = llm_router._build_where_clause(
            question="김철수가 뭘 했어?",
            question_type=QuestionType.PERSON,
            period_info=None,
        )
        assert "담당자" in result
        assert "김철수" in result

    def test_equipment_query_extracts_code(self, llm_router: LLMRouter):
        """EQUIPMENT query should extract equipment code."""
        result = llm_router._build_where_clause(
            question="CVD 설비 고장 이력",
            question_type=QuestionType.EQUIPMENT,
            period_info=None,
        )
        assert "설비코드" in result
        assert "CVD" in result

    def test_equipment_with_equipment_info(self, llm_router: LLMRouter):
        """EQUIPMENT query with equipment_info should use provided codes."""
        equipment_info = {
            "equipment_codes": ["CVD"],
            "equipment_pattern": None,
            "fault_type": "고장",
            "raw_expression": "CVD",
        }
        result = llm_router._build_where_clause(
            question="CVD 설비 고장 이력",
            question_type=QuestionType.EQUIPMENT,
            period_info=None,
            equipment_info=equipment_info,
        )
        assert "설비코드 LIKE '%CVD%'" in result
        assert "작업유형 LIKE '%고장%'" in result

    def test_equipment_with_specific_pattern(self, llm_router: LLMRouter):
        """EQUIPMENT query with specific pattern like CVD-001."""
        equipment_info = {
            "equipment_codes": ["CVD"],
            "equipment_pattern": "CVD-001",
            "fault_type": None,
            "raw_expression": "CVD-001",
        }
        result = llm_router._build_where_clause(
            question="CVD-001 설비 상태 조회",
            question_type=QuestionType.EQUIPMENT,
            period_info=None,
            equipment_info=equipment_info,
        )
        assert "CVD-001" in result

    def test_equipment_with_multiple_codes(self, llm_router: LLMRouter):
        """EQUIPMENT query with multiple equipment codes."""
        equipment_info = {
            "equipment_codes": ["CVD", "PVD"],
            "equipment_pattern": None,
            "fault_type": None,
            "raw_expression": "CVD",
        }
        result = llm_router._build_where_clause(
            question="CVD와 PVD 설비 비교",
            question_type=QuestionType.EQUIPMENT,
            period_info=None,
            equipment_info=equipment_info,
        )
        assert "CVD" in result
        assert "PVD" in result
        assert "OR" in result

    def test_unknown_query_returns_empty(self, llm_router: LLMRouter):
        """UNKNOWN query should return empty WHERE clause."""
        result = llm_router._build_where_clause(
            question="보여줘",
            question_type=QuestionType.UNKNOWN,
            period_info=None,
        )
        assert result == ""


class TestGetFewShotExamples:
    """Tests for get_few_shot_examples method."""

    def test_person_examples_exist(self, llm_router: LLMRouter):
        """PERSON type should have few-shot examples."""
        examples = llm_router.get_few_shot_examples(QuestionType.PERSON)
        assert len(examples) >= 1
        assert "question" in examples[0]
        assert "sql" in examples[0]

    def test_period_examples_exist(self, llm_router: LLMRouter):
        """PERIOD type should have few-shot examples."""
        examples = llm_router.get_few_shot_examples(QuestionType.PERIOD)
        assert len(examples) >= 1
        assert "UNION" in examples[0]["sql"]

    def test_equipment_examples_exist(self, llm_router: LLMRouter):
        """EQUIPMENT type should have few-shot examples."""
        examples = llm_router.get_few_shot_examples(QuestionType.EQUIPMENT)
        assert len(examples) >= 1
        assert "설비코드" in examples[0]["sql"]

    def test_statistics_examples_exist(self, llm_router: LLMRouter):
        """STATISTICS type should have few-shot examples."""
        examples = llm_router.get_few_shot_examples(QuestionType.STATISTICS)
        assert len(examples) >= 1
        assert "COUNT" in examples[0]["sql"]

    def test_unknown_returns_empty(self, llm_router: LLMRouter):
        """UNKNOWN type should return empty examples list."""
        examples = llm_router.get_few_shot_examples(QuestionType.UNKNOWN)
        assert examples == []


class TestValidateSQLSyntax:
    """Tests for _validate_sql_syntax method (T045)."""

    def test_valid_select_query(self, llm_router: LLMRouter):
        """Valid SELECT query should pass validation."""
        sql = "SELECT * FROM \"Daily_20241217\""
        is_valid, error = llm_router._validate_sql_syntax(sql)
        assert is_valid is True
        assert error is None

    def test_valid_union_query(self, llm_router: LLMRouter):
        """Valid UNION ALL query should pass validation."""
        sql = """SELECT 날짜, 담당자 FROM "Daily_20241217"
        UNION ALL
        SELECT 날짜, 담당자 FROM "Weekly_W52" """
        is_valid, error = llm_router._validate_sql_syntax(sql)
        assert is_valid is True
        assert error is None

    def test_empty_query_fails(self, llm_router: LLMRouter):
        """Empty query should fail validation."""
        is_valid, error = llm_router._validate_sql_syntax("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_missing_select_fails(self, llm_router: LLMRouter):
        """Query without SELECT should fail validation."""
        sql = "UPDATE table SET x = 1"
        is_valid, error = llm_router._validate_sql_syntax(sql)
        assert is_valid is False
        assert "SELECT" in error

    def test_unbalanced_quotes_fails(self, llm_router: LLMRouter):
        """Query with unbalanced quotes should fail validation."""
        sql = 'SELECT * FROM "Daily_20241217'
        is_valid, error = llm_router._validate_sql_syntax(sql)
        assert is_valid is False
        assert "quote" in error.lower()

    def test_unbalanced_parentheses_fails(self, llm_router: LLMRouter):
        """Query with unbalanced parentheses should fail validation."""
        sql = "SELECT * FROM table WHERE (a = 1"
        is_valid, error = llm_router._validate_sql_syntax(sql)
        assert is_valid is False
        assert "parenthes" in error.lower()

    def test_dangerous_keywords_fails(self, llm_router: LLMRouter):
        """Query with dangerous keywords should fail validation."""
        sql = "SELECT * FROM table; DROP TABLE users;"
        is_valid, error = llm_router._validate_sql_syntax(sql)
        assert is_valid is False
        assert "dangerous" in error.lower() or "DROP" in error
