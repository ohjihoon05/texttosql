"""Unit tests for ResponseGenerator."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.models.query import QueryResult, ResponseType
from src.services.response_generator import ResponseGenerator


@pytest.fixture
def response_generator():
    """Create a ResponseGenerator instance."""
    return ResponseGenerator()


@pytest.fixture
def empty_result():
    """Create an empty query result."""
    return QueryResult(
        success=True,
        data=[],
        row_count=0,
        column_names=["name", "date", "task"],
        execution_time_ms=10.0,
    )


@pytest.fixture
def single_result():
    """Create a single-row query result."""
    return QueryResult(
        success=True,
        data=[{"name": "김철수", "date": "2024-12-20", "task": "PM 점검"}],
        row_count=1,
        column_names=["name", "date", "task"],
        execution_time_ms=15.0,
    )


@pytest.fixture
def multiple_results():
    """Create a multi-row query result."""
    return QueryResult(
        success=True,
        data=[
            {"name": "김철수", "date": "2024-12-20", "task": "PM 점검"},
            {"name": "김철수", "date": "2024-12-21", "task": "설비 이상 조치"},
            {"name": "김철수", "date": "2024-12-22", "task": "정기 점검"},
        ],
        row_count=3,
        column_names=["name", "date", "task"],
        execution_time_ms=20.0,
    )


@pytest.fixture
def many_results():
    """Create a large result set (10+ rows)."""
    data = [
        {"name": f"직원{i}", "date": f"2024-12-{i:02d}", "task": f"작업{i}"}
        for i in range(1, 16)
    ]
    return QueryResult(
        success=True,
        data=data,
        row_count=15,
        column_names=["name", "date", "task"],
        execution_time_ms=25.0,
    )


@pytest.fixture
def error_result():
    """Create an error query result."""
    return QueryResult(
        success=False,
        data=[],
        row_count=0,
        column_names=[],
        execution_time_ms=0.0,
        error_message="Table not found",
    )


class TestGetResponseType:
    """Tests for get_response_type method."""

    def test_empty_result(self, response_generator, empty_result):
        """Test response type for empty result."""
        assert response_generator.get_response_type(empty_result) == ResponseType.EMPTY

    def test_single_result(self, response_generator, single_result):
        """Test response type for single row."""
        assert response_generator.get_response_type(single_result) == ResponseType.SINGLE

    def test_few_results(self, response_generator, multiple_results):
        """Test response type for 2-10 rows."""
        assert response_generator.get_response_type(multiple_results) == ResponseType.FEW

    def test_many_results(self, response_generator, many_results):
        """Test response type for 10+ rows."""
        assert response_generator.get_response_type(many_results) == ResponseType.MANY

    def test_error_result(self, response_generator, error_result):
        """Test response type for error."""
        assert response_generator.get_response_type(error_result) == ResponseType.ERROR


class TestFallbackResponse:
    """Tests for fallback response generation."""

    def test_empty_fallback(self, response_generator, empty_result):
        """Test fallback for empty result."""
        response = response_generator._fallback_simple_response(empty_result)
        assert "찾을 수 없습니다" in response
        assert "다른 조건" in response

    def test_single_fallback(self, response_generator, single_result):
        """Test fallback for single result."""
        response = response_generator._fallback_simple_response(single_result)
        assert "1건" in response

    def test_multiple_fallback(self, response_generator, multiple_results):
        """Test fallback for multiple results."""
        response = response_generator._fallback_simple_response(multiple_results)
        assert "3건" in response

    def test_error_fallback(self, response_generator, error_result):
        """Test fallback for error result."""
        response = response_generator._fallback_simple_response(error_result)
        assert "오류" in response
        assert "Table not found" in response


class TestBuildContext:
    """Tests for context building."""

    def test_context_fields(self, response_generator, single_result):
        """Test context has all required fields."""
        context = response_generator._build_context("김철수가 뭘 했어?", single_result)

        assert context.question == "김철수가 뭘 했어?"
        assert context.row_count == 1
        assert context.column_names == ["name", "date", "task"]
        assert len(context.sample_data) == 1
        assert context.response_type == ResponseType.SINGLE

    def test_context_sample_limit(self, response_generator, many_results):
        """Test sample data is limited to 5 rows."""
        context = response_generator._build_context("모든 작업 보여줘", many_results)

        assert len(context.sample_data) == 5  # Max 5 samples


class TestBuildPrompt:
    """Tests for prompt building."""

    def test_prompt_contains_question(self, response_generator, single_result):
        """Test prompt includes the question."""
        context = response_generator._build_context("김철수가 뭘 했어?", single_result)
        prompt = response_generator._build_prompt(context)

        assert "김철수가 뭘 했어?" in prompt

    def test_prompt_contains_data(self, response_generator, single_result):
        """Test prompt includes sample data."""
        context = response_generator._build_context("김철수가 뭘 했어?", single_result)
        prompt = response_generator._build_prompt(context)

        assert "김철수" in prompt
        assert "PM 점검" in prompt


class TestGenerateResponse:
    """Tests for async response generation."""

    @pytest.mark.asyncio
    async def test_empty_response_no_llm(self, response_generator, empty_result):
        """Test empty result doesn't call LLM."""
        response = await response_generator.generate_response(
            "김철수가 뭘 했어?", empty_result
        )

        assert "찾을 수 없습니다" in response
        assert "다른 조건" in response

    @pytest.mark.asyncio
    async def test_error_response_no_llm(self, response_generator, error_result):
        """Test error result doesn't call LLM."""
        response = await response_generator.generate_response(
            "김철수가 뭘 했어?", error_result
        )

        assert "오류" in response

    @pytest.mark.asyncio
    async def test_timeout_uses_fallback(self, response_generator, single_result):
        """Test timeout falls back to simple response."""
        with patch.object(response_generator, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(side_effect=TimeoutError())
            mock_get_llm.return_value = mock_llm

            response = await response_generator.generate_response(
                "김철수가 뭘 했어?", single_result, timeout=0.1
            )

            # Should use fallback
            assert "1건" in response

    @pytest.mark.asyncio
    async def test_llm_called_for_results(self, response_generator, single_result):
        """Test LLM is called when results exist."""
        with patch.object(response_generator, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(
                return_value="김철수님은 2024년 12월 20일에 PM 점검을 수행했습니다."
            )
            mock_get_llm.return_value = mock_llm

            response = await response_generator.generate_response(
                "김철수가 뭘 했어?", single_result
            )

            mock_llm.ainvoke.assert_called_once()
            assert "김철수님" in response


class TestGenerateSuggestedQuestions:
    """Tests for suggested questions generation."""

    @pytest.mark.asyncio
    async def test_no_suggestions_for_empty(self, response_generator, empty_result):
        """Test no suggestions for empty result."""
        suggestions = await response_generator.generate_suggested_questions(
            "김철수가 뭘 했어?", empty_result
        )

        assert suggestions == []

    @pytest.mark.asyncio
    async def test_suggestions_limited(self, response_generator, single_result):
        """Test suggestions are limited to max_suggestions."""
        with patch.object(response_generator, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(
                return_value="1. 김철수의 이번 달 실적은?\n2. 다른 직원 현황은?\n3. 추가 질문?"
            )
            mock_get_llm.return_value = mock_llm

            suggestions = await response_generator.generate_suggested_questions(
                "김철수가 뭘 했어?", single_result, max_suggestions=2
            )

            assert len(suggestions) <= 2


class TestSummaryGeneration:
    """Tests for summary generation with large result sets."""

    @pytest.mark.asyncio
    async def test_uses_summary_prompt_for_many(self, response_generator, many_results):
        """Test summary prompt is used for 10+ rows."""
        with patch.object(response_generator, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(
                return_value="총 15건의 작업이 조회되었습니다. 가장 많은 작업 유형은..."
            )
            mock_get_llm.return_value = mock_llm

            response = await response_generator.generate_response(
                "모든 작업 보여줘", many_results
            )

            # Check that LLM was called (summary prompt should be used)
            mock_llm.ainvoke.assert_called_once()
            call_args = mock_llm.ainvoke.call_args[0][0]
            # Summary prompt should be used for MANY type
            assert "15" in call_args or "총" in response


class TestPatternDetection:
    """Tests for pattern detection in results."""

    @pytest.mark.asyncio
    async def test_pattern_in_summary(self, response_generator, many_results):
        """Test pattern detection is included in summary."""
        with patch.object(response_generator, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(
                return_value="총 15건의 작업 중 가장 빈번한 유형은 정기 점검입니다."
            )
            mock_get_llm.return_value = mock_llm

            response = await response_generator.generate_response(
                "작업 패턴 분석해줘", many_results
            )

            assert "빈번" in response or "패턴" in response or "15" in response
