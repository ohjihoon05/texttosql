"""SQL Agent combining Excel loading and LLM for natural language queries."""

import logging
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.models.schema import ExcelSchema
from src.models.query import QueryContext, QueryResult, FormattedResponse
from src.services.excel_loader import ExcelLoader
from src.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class SQLAgent:
    """Agent for processing natural language queries on Excel data."""

    def __init__(self, file_path: str | Path | None = None):
        """Initialize SQL Agent.

        Args:
            file_path: Optional path to Excel file. Can be set later via load_file().
        """
        self.settings = get_settings()
        self._loader: ExcelLoader | None = None
        self._llm_router = LLMRouter()
        self._schema: ExcelSchema | None = None
        self._table_mapping: dict[str, str] = {}

        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str | Path) -> ExcelSchema:
        """Load Excel file for querying.

        Args:
            file_path: Path to Excel file

        Returns:
            ExcelSchema with file information

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is invalid
        """
        # Close existing loader if any
        if self._loader is not None:
            self._loader.close()

        self._loader = ExcelLoader(file_path)
        self._schema = self._loader.load()
        self._table_mapping = self._loader.get_table_mapping()

        logger.info(
            f"Loaded Excel file: {self._schema.file_name} "
            f"with {len(self._schema.sheets)} sheets"
        )

        return self._schema

    def get_schema(self) -> ExcelSchema | None:
        """Get current Excel schema.

        Returns:
            ExcelSchema if file is loaded, None otherwise
        """
        return self._schema

    async def ask(self, question: str) -> FormattedResponse:
        """Ask a natural language question about the Excel data.

        Args:
            question: Natural language question

        Returns:
            FormattedResponse with answer, SQL, and data preview

        Raises:
            RuntimeError: If no file is loaded
        """
        if self._loader is None or self._schema is None:
            raise RuntimeError("No Excel file loaded. Call load_file() first.")

        # Create query context
        context = QueryContext(
            question=question,
            relevant_sheets=[],  # TODO: Add schema filtering
            terminology_hints=[],  # TODO: Add RAG hints
            previous_queries=[],
        )

        try:
            # Generate SQL using LLM
            sql_query = await self._llm_router.generate_sql(
                context=context,
                schema=self._schema,
                table_mapping=self._table_mapping,
            )

            logger.info(f"Generated SQL: {sql_query.raw_sql}")

            # Execute SQL
            result = self._loader.execute_query(sql_query.raw_sql)

            if result.success:
                # Format successful response
                answer = self._format_answer(question, result)
                data_preview = result.to_markdown_table(max_rows=10)
                source_sheets = sql_query.tables_used

                return FormattedResponse(
                    answer=answer,
                    sql_query=sql_query.raw_sql,
                    data_preview=data_preview,
                    source_sheets=source_sheets,
                )
            else:
                # Handle query execution failure
                logger.error(f"Query execution failed: {result.error_message}")
                return FormattedResponse(
                    answer=f"쿼리 실행 중 오류가 발생했습니다: {result.error_message}",
                    sql_query=sql_query.raw_sql,
                    data_preview="",
                    source_sheets=[],
                )

        except ValueError as e:
            # SQL generation failed with explanation
            logger.warning(f"Cannot generate SQL: {e}")
            return FormattedResponse(
                answer=f"질문에 대한 SQL을 생성할 수 없습니다: {e}",
                sql_query="",
                data_preview="",
                source_sheets=[],
            )

        except Exception as e:
            logger.error(f"Unexpected error in ask(): {e}")
            return FormattedResponse(
                answer=f"처리 중 오류가 발생했습니다: {e}",
                sql_query="",
                data_preview="",
                source_sheets=[],
            )

    def _format_answer(self, question: str, result: QueryResult) -> str:
        """Format query result into natural language answer.

        Args:
            question: Original question
            result: Query result

        Returns:
            Natural language answer string
        """
        if result.is_empty:
            return "검색 결과가 없습니다."

        if result.row_count == 1:
            return f"1건의 결과를 찾았습니다. (실행 시간: {result.execution_time_ms:.1f}ms)"

        return (
            f"{result.row_count}건의 결과를 찾았습니다. "
            f"(실행 시간: {result.execution_time_ms:.1f}ms)"
        )

    async def health_check(self) -> dict[str, Any]:
        """Check system health including LLM connectivity.

        Returns:
            Dict with health status
        """
        llm_health = await self._llm_router.health_check()

        return {
            "llm": llm_health,
            "file_loaded": self._schema is not None,
            "file_name": self._schema.file_name if self._schema else None,
            "sheet_count": len(self._schema.sheets) if self._schema else 0,
        }

    def close(self) -> None:
        """Close resources and cleanup."""
        if self._loader is not None:
            self._loader.close()
            self._loader = None
        self._schema = None
        self._table_mapping.clear()

    def __enter__(self) -> "SQLAgent":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
