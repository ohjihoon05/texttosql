"""SQL Agent combining Excel loading and LLM for natural language queries."""

import logging
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.models.schema import ExcelSchema
from src.models.query import QueryContext, QueryResult, FormattedResponse, ResponseType
from src.models.sheet_group import (
    MultiSheetContext,
    UnionQueryResult,
    SheetResultSummary,
    QuestionType,
)
from src.services.excel_loader import ExcelLoader
from src.services.llm_router import LLMRouter
from src.services.response_generator import ResponseGenerator
from src.services.sheet_group_manager import SheetGroupManager
from src.exceptions import UnionSQLGenerationError, QueryExecutionError

logger = logging.getLogger(__name__)


class SQLAgent:
    """Agent for processing natural language queries on Excel data."""

    # T051: Result limit for display (FR-007)
    MAX_DISPLAY_ROWS = 100

    def __init__(self, file_path: str | Path | None = None):
        """Initialize SQL Agent.

        Args:
            file_path: Optional path to Excel file. Can be set later via load_file().
        """
        self.settings = get_settings()
        self._loader: ExcelLoader | None = None
        self._llm_router = LLMRouter()
        self._response_generator = ResponseGenerator()
        self._sheet_group_manager: SheetGroupManager | None = None
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

        # Initialize sheet group manager with schema
        self._sheet_group_manager = SheetGroupManager(schema=self._schema)

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

    def should_use_multi_sheet(self, question: str) -> bool:
        """Determine if question should use multi-sheet query.

        Args:
            question: Natural language question

        Returns:
            True if multi-sheet query is appropriate

        Raises:
            RuntimeError: If no file is loaded
        """
        if self._schema is None or self._sheet_group_manager is None:
            raise RuntimeError("No Excel file loaded. Call load_file() first.")

        # Check if there are multiple sheets to query
        if len(self._schema.sheets) <= 1:
            return False

        # Create multi-sheet context and check if it suggests UNION
        context = self._sheet_group_manager.create_multi_sheet_context(
            question, self._schema
        )

        return context.use_union and len(context.selected_sheets) > 1

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
                # Format successful response using LLM
                answer = await self._format_answer(question, result)
                data_preview = self._format_data_preview(result)
                source_sheets = sql_query.tables_used
                response_type = self._response_generator.get_response_type(result)

                return FormattedResponse(
                    answer=answer,
                    sql_query=sql_query.raw_sql,
                    data_preview=data_preview,
                    source_sheets=source_sheets,
                    response_type=response_type,
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

    async def _format_answer(self, question: str, result: QueryResult) -> str:
        """Format query result into natural language answer using LLM.

        Args:
            question: Original question
            result: Query result

        Returns:
            Natural language answer string
        """
        return await self._response_generator.generate_response(question, result)

    def _format_data_preview(self, result: QueryResult) -> str:
        """Format data preview with row limit and pagination message (T051/FR-007).

        Args:
            result: Query result

        Returns:
            Markdown table with optional pagination message
        """
        if result.data is None or result.row_count == 0:
            return ""

        total_rows = result.row_count
        preview = result.to_markdown_table(max_rows=self.MAX_DISPLAY_ROWS)

        if total_rows > self.MAX_DISPLAY_ROWS:
            hidden_rows = total_rows - self.MAX_DISPLAY_ROWS
            preview += f"\n\n_({hidden_rows}건 더 있음. 전체 결과: {total_rows}건)_"

        return preview

    async def ask_multi_sheet(self, question: str) -> FormattedResponse:
        """Ask a question that spans multiple sheets using UNION.

        Args:
            question: Natural language question

        Returns:
            FormattedResponse with combined results from multiple sheets

        Raises:
            RuntimeError: If no file is loaded
        """
        if self._loader is None or self._schema is None:
            raise RuntimeError("No Excel file loaded. Call load_file() first.")

        if self._sheet_group_manager is None:
            raise RuntimeError("SheetGroupManager not initialized")

        try:
            # T050: Comprehensive logging for multi-sheet queries
            logger.info(f"[MULTI-SHEET] Starting query: '{question[:100]}...'")

            # Create multi-sheet context
            context = self._sheet_group_manager.create_multi_sheet_context(
                question, self._schema
            )

            logger.info(
                f"[MULTI-SHEET] Context created: "
                f"type={context.question_type.value}, "
                f"sheets={len(context.selected_sheets)}, "
                f"use_union={context.use_union}, "
                f"common_cols={len(context.common_columns)}"
            )

            if not context.selected_sheets:
                return FormattedResponse(
                    answer="질문과 관련된 시트를 찾을 수 없습니다.",
                    sql_query="",
                    data_preview="",
                    source_sheets=[],
                )

            if not context.common_columns:
                sheet_names = [s.sheet_name for s in context.selected_sheets]
                return FormattedResponse(
                    answer=f"선택된 시트들 간에 공통 컬럼이 없습니다: {', '.join(sheet_names)}",
                    sql_query="",
                    data_preview="",
                    source_sheets=sheet_names,
                )

            # Extract period info for PERIOD type questions
            period_info = None
            if context.question_type == QuestionType.PERIOD:
                period_info = self._sheet_group_manager.extract_period_info(question)

            # Extract equipment info for EQUIPMENT type questions
            equipment_info = None
            if context.question_type == QuestionType.EQUIPMENT:
                equipment_info = self._sheet_group_manager.extract_equipment_info(question)

            # Log extraction info
            if period_info:
                logger.info(f"[MULTI-SHEET] Period extracted: {period_info}")
            if equipment_info:
                logger.info(f"[MULTI-SHEET] Equipment extracted: {equipment_info}")

            # Generate UNION SQL
            sql_query = await self._llm_router.generate_union_sql(
                question, context, period_info, equipment_info
            )

            logger.info(f"[MULTI-SHEET] SQL generated: {sql_query[:200]}...")

            # Execute SQL with auto-cast fallback for type mismatches (EH-002)
            result = self._loader.execute_query_with_auto_cast(sql_query)

            if result.success:
                logger.info(
                    f"[MULTI-SHEET] Query succeeded: "
                    f"rows={result.row_count}, "
                    f"time_ms={result.execution_time_ms}"
                )

                # Create result summary
                summary = self._create_result_summary(result, context)

                # Format response
                answer = await self._format_multi_sheet_answer(
                    question, result, summary
                )
                data_preview = self._format_data_preview(result)
                source_sheets = [s.sheet_name for s in context.selected_sheets]
                response_type = self._response_generator.get_response_type(result)

                logger.info(
                    f"[MULTI-SHEET] Response ready: "
                    f"type={response_type.value}, "
                    f"sheets={source_sheets}"
                )

                return FormattedResponse(
                    answer=answer,
                    sql_query=sql_query,
                    data_preview=data_preview,
                    source_sheets=source_sheets,
                    response_type=response_type,
                )
            else:
                # EH-003: Try individual sheet queries as fallback
                logger.warning(f"UNION query failed: {result.error_message}, trying individual sheets")
                fallback_result = await self._execute_individual_sheets(
                    question, context, period_info, equipment_info
                )
                if fallback_result is not None:
                    return fallback_result

                return FormattedResponse(
                    answer=f"UNION 쿼리 실행 중 오류가 발생했습니다: {result.error_message}",
                    sql_query=sql_query,
                    data_preview="",
                    source_sheets=[],
                )

        except UnionSQLGenerationError as e:
            logger.warning(f"Cannot generate UNION SQL: {e}")
            return FormattedResponse(
                answer=f"멀티 시트 쿼리 생성 실패: {e}",
                sql_query=e.attempted_sql or "",
                data_preview="",
                source_sheets=[],
            )

        except Exception as e:
            logger.error(f"Unexpected error in ask_multi_sheet(): {e}")
            return FormattedResponse(
                answer=f"멀티 시트 쿼리 처리 중 오류가 발생했습니다: {e}",
                sql_query="",
                data_preview="",
                source_sheets=[],
            )

    def _create_result_summary(
        self, result: QueryResult, context: MultiSheetContext
    ) -> UnionQueryResult:
        """Create summary of UNION query results with per-sheet counts.

        Args:
            result: Query execution result
            context: Multi-sheet context

        Returns:
            UnionQueryResult with summary information
        """
        sheet_summaries: list[SheetResultSummary] = []

        if result.data is not None and "source_sheet" in result.data.columns:
            # Count rows per source sheet
            sheet_counts = result.data["source_sheet"].value_counts().to_dict()

            for selection in context.selected_sheets:
                sheet_name = selection.sheet_name
                row_count = sheet_counts.get(sheet_name, 0)
                sheet_summaries.append(
                    SheetResultSummary(
                        sheet_name=sheet_name,
                        row_count=row_count,
                        matched=row_count > 0,
                    )
                )
        else:
            # No source_sheet column, create summaries without counts
            for selection in context.selected_sheets:
                sheet_summaries.append(
                    SheetResultSummary(
                        sheet_name=selection.sheet_name,
                        row_count=0,
                        matched=False,
                    )
                )

        return UnionQueryResult(
            success=True,
            total_rows=result.row_count,
            sheet_summaries=sheet_summaries,
        )

    async def _format_multi_sheet_answer(
        self,
        question: str,
        result: QueryResult,
        summary: UnionQueryResult,
    ) -> str:
        """Format multi-sheet query result into natural language answer.

        Args:
            question: Original question
            result: Query result
            summary: Union query result summary

        Returns:
            Natural language answer string
        """
        # T052/FR-008: Handle empty results with sheet list
        if result.row_count == 0:
            all_sheets = [s.sheet_name for s in summary.sheet_summaries]
            return (
                f"조회 결과가 없습니다.\n\n"
                f"검색한 시트: {', '.join(all_sheets)}\n"
                f"질문을 다시 확인하거나 조건을 변경해 보세요."
            )

        # Generate base answer
        base_answer = await self._response_generator.generate_response(question, result)

        # Add summary information
        matched_sheets = [s for s in summary.sheet_summaries if s.matched]
        if matched_sheets:
            sheet_info = ", ".join(
                f"{s.sheet_name}({s.row_count}건)" for s in matched_sheets
            )
            summary_text = f"\n\n[조회된 시트: {sheet_info}, 총 {summary.total_rows}건]"
            return base_answer + summary_text

        return base_answer

    async def _execute_individual_sheets(
        self,
        question: str,
        context: MultiSheetContext,
        period_info: dict[str, str | None] | None = None,
        equipment_info: dict[str, str | list[str] | None] | None = None,
    ) -> FormattedResponse | None:
        """Execute queries on individual sheets as fallback (EH-003).

        Args:
            question: User's question
            context: Multi-sheet context
            period_info: Period info for filtering
            equipment_info: Equipment info for filtering

        Returns:
            FormattedResponse if any sheet succeeds, None if all fail
        """
        import pandas as pd

        all_results: list[pd.DataFrame] = []
        successful_sheets: list[str] = []
        failed_sheets: list[str] = []

        for sheet_selection in context.selected_sheets:
            sheet_name = sheet_selection.sheet_name
            try:
                # Build simple query for single sheet
                columns = ", ".join(context.common_columns)
                where_clause = self._llm_router._build_where_clause(
                    question, context.question_type, period_info, equipment_info
                )

                sql = f'SELECT {columns}, \'{sheet_name}\' as source_sheet FROM "{sheet_name}"{where_clause}'

                result = self._loader.execute_query(sql)

                if result.success and result.data is not None:
                    all_results.append(result.data)
                    successful_sheets.append(sheet_name)
                    logger.info(f"Individual sheet query succeeded: {sheet_name}")
                else:
                    failed_sheets.append(sheet_name)
                    logger.warning(f"Individual sheet query failed: {sheet_name}")

            except Exception as e:
                failed_sheets.append(sheet_name)
                logger.warning(f"Error querying sheet {sheet_name}: {e}")

        if not all_results:
            logger.error("All individual sheet queries failed")
            return None

        # Combine results
        combined_df = pd.concat(all_results, ignore_index=True)

        # Create combined result
        combined_result = QueryResult(
            success=True,
            data=combined_df,
            row_count=len(combined_df),
            column_names=list(combined_df.columns),
            execution_time_ms=0,
        )

        # Create summary
        summary = self._create_result_summary(combined_result, context)

        # Format answer
        answer = await self._format_multi_sheet_answer(question, combined_result, summary)

        if failed_sheets:
            answer += f"\n\n⚠️ 일부 시트 조회 실패: {', '.join(failed_sheets)}"

        data_preview = self._format_data_preview(combined_result)
        response_type = self._response_generator.get_response_type(combined_result)

        return FormattedResponse(
            answer=answer,
            sql_query="[개별 시트 쿼리 실행]",
            data_preview=data_preview,
            source_sheets=successful_sheets,
            response_type=response_type,
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
