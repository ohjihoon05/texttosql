"""Integration tests for the full response generation flow."""

import pytest
import pandas as pd
from unittest.mock import MagicMock, AsyncMock, patch

from src.models.query import QueryResult, ResponseType, FormattedResponse
from src.services.response_generator import ResponseGenerator
from src.services.sql_agent import SQLAgent


@pytest.fixture
def mock_excel_loader():
    """Create a mock Excel loader."""
    loader = MagicMock()
    loader.load.return_value = MagicMock(
        file_name="test.xlsx",
        sheets={"Sheet1": MagicMock()},
        file_size_mb=1.0,
        total_rows=100,
        load_time_seconds=0.5,
    )
    loader.get_table_mapping.return_value = {"Sheet1": "Sheet1"}
    return loader


@pytest.fixture
def sample_query_result():
    """Create a sample query result."""
    df = pd.DataFrame([
        {"name": "김철수", "date": "2024-12-20", "task": "PM 점검", "team": "A팀"},
        {"name": "김철수", "date": "2024-12-21", "task": "설비 조치", "team": "A팀"},
    ])
    return QueryResult(
        success=True,
        data=df,
        row_count=2,
        column_names=["name", "date", "task", "team"],
        execution_time_ms=15.0,
    )


class TestResponseGeneratorIntegration:
    """Integration tests for ResponseGenerator."""

    @pytest.mark.asyncio
    async def test_full_response_flow(self, sample_query_result):
        """Test complete flow from result to natural language response."""
        generator = ResponseGenerator()

        # Test with mock LLM
        with patch.object(generator, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(
                return_value="김철수님은 최근 2건의 작업을 수행했습니다. "
                "12월 20일에 PM 점검, 12월 21일에 설비 조치를 진행했습니다."
            )
            mock_get_llm.return_value = mock_llm

            response = await generator.generate_response(
                "김철수가 뭘 했어?",
                sample_query_result,
            )

            assert "김철수" in response
            assert len(response) > 20  # Should be a meaningful response

    @pytest.mark.asyncio
    async def test_response_type_propagation(self, sample_query_result):
        """Test that response type is correctly determined."""
        generator = ResponseGenerator()

        response_type = generator.get_response_type(sample_query_result)
        assert response_type == ResponseType.FEW

    @pytest.mark.asyncio
    async def test_empty_result_handling(self):
        """Test handling of empty results."""
        generator = ResponseGenerator()

        empty_result = QueryResult(
            success=True,
            data=pd.DataFrame(columns=["name", "task"]),
            row_count=0,
            column_names=["name", "task"],
            execution_time_ms=5.0,
        )

        response = await generator.generate_response(
            "김철수가 뭘 했어?",
            empty_result,
        )

        assert "찾을 수 없습니다" in response
        assert "다른 조건" in response

    @pytest.mark.asyncio
    async def test_large_result_summary(self):
        """Test summary generation for large result sets."""
        generator = ResponseGenerator()

        df = pd.DataFrame([{"id": i, "task": f"작업{i}"} for i in range(20)])
        large_result = QueryResult(
            success=True,
            data=df,
            row_count=20,
            column_names=["id", "task"],
            execution_time_ms=30.0,
        )

        with patch.object(generator, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(
                return_value="총 20건의 작업이 조회되었습니다. 다양한 유형의 작업이 포함되어 있습니다."
            )
            mock_get_llm.return_value = mock_llm

            response = await generator.generate_response(
                "모든 작업 보여줘",
                large_result,
            )

            # Should use summary prompt for MANY type
            assert "20" in response or "총" in response


class TestSQLAgentResponseIntegration:
    """Integration tests for SQLAgent with ResponseGenerator."""

    @pytest.mark.asyncio
    async def test_agent_uses_response_generator(self, mock_excel_loader, sample_query_result):
        """Test that SQLAgent uses ResponseGenerator for formatting."""
        with patch("src.services.sql_agent.ExcelLoader", return_value=mock_excel_loader):
            agent = SQLAgent()
            agent._loader = mock_excel_loader
            agent._schema = mock_excel_loader.load()
            agent._table_mapping = mock_excel_loader.get_table_mapping()

            # Mock the LLM router and response generator
            with patch.object(agent._llm_router, "generate_sql") as mock_sql:
                mock_sql.return_value = MagicMock(
                    raw_sql="SELECT * FROM Sheet1",
                    tables_used=["Sheet1"],
                )
                mock_excel_loader.execute_query.return_value = sample_query_result

                with patch.object(agent._response_generator, "generate_response") as mock_gen:
                    mock_gen.return_value = "김철수님은 2건의 작업을 수행했습니다."

                    response = await agent.ask("김철수가 뭘 했어?")

                    mock_gen.assert_called_once()
                    assert isinstance(response, FormattedResponse)
                    assert "김철수" in response.answer

    @pytest.mark.asyncio
    async def test_agent_response_type_set(self, mock_excel_loader, sample_query_result):
        """Test that response_type is set in FormattedResponse."""
        with patch("src.services.sql_agent.ExcelLoader", return_value=mock_excel_loader):
            agent = SQLAgent()
            agent._loader = mock_excel_loader
            agent._schema = mock_excel_loader.load()
            agent._table_mapping = mock_excel_loader.get_table_mapping()

            with patch.object(agent._llm_router, "generate_sql") as mock_sql:
                mock_sql.return_value = MagicMock(
                    raw_sql="SELECT * FROM Sheet1",
                    tables_used=["Sheet1"],
                )
                mock_excel_loader.execute_query.return_value = sample_query_result

                with patch.object(agent._response_generator, "generate_response") as mock_gen:
                    mock_gen.return_value = "테스트 응답"

                    response = await agent.ask("김철수가 뭘 했어?")

                    assert response.response_type == ResponseType.FEW


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_100_plus_rows_handling(self):
        """Test handling of 100+ rows."""
        generator = ResponseGenerator()

        df = pd.DataFrame([{"id": i} for i in range(150)])
        huge_result = QueryResult(
            success=True,
            data=df,
            row_count=150,
            column_names=["id"],
            execution_time_ms=100.0,
        )

        response_type = generator.get_response_type(huge_result)
        assert response_type == ResponseType.MANY

        # Test fallback response for large results
        fallback = generator._fallback_simple_response(huge_result)
        assert "150건" in fallback

    @pytest.mark.asyncio
    async def test_error_result_handling(self):
        """Test handling of error results."""
        generator = ResponseGenerator()

        error_result = QueryResult(
            success=False,
            data=None,
            row_count=0,
            column_names=[],
            execution_time_ms=0.0,
            error_message="Syntax error in SQL",
        )

        response = await generator.generate_response(
            "김철수가 뭘 했어?",
            error_result,
        )

        assert "오류" in response
        assert "Syntax error" in response

    @pytest.mark.asyncio
    async def test_llm_error_graceful_fallback(self):
        """Test graceful fallback on LLM error."""
        generator = ResponseGenerator()

        df = pd.DataFrame([{"name": "테스트"}])
        result = QueryResult(
            success=True,
            data=df,
            row_count=1,
            column_names=["name"],
            execution_time_ms=10.0,
        )

        with patch.object(generator, "_get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            # Simulate LLM error
            async def error_invoke(*args):
                raise RuntimeError("LLM connection failed")

            mock_llm.ainvoke = error_invoke
            mock_get_llm.return_value = mock_llm

            # Should handle error and use fallback
            response = await generator.generate_response(
                "테스트",
                result,
            )

            assert "1건" in response  # Fallback response
