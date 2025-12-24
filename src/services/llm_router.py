"""LLM routing and SQL generation using Ollama."""

import logging
from typing import Any

from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate

from src.config import get_settings
from src.models.schema import ExcelSchema
from src.models.query import QueryContext, SQLQuery
from src.models.sheet_group import MultiSheetContext, QuestionType
from src.exceptions import UnionSQLGenerationError

logger = logging.getLogger(__name__)


# SQL generation prompt template
SQL_GENERATION_PROMPT = """You are a SQL expert. Given the following Excel schema and user question, generate a SQL query to answer the question.

## Excel Schema
{schema_context}

## Table Name Mapping
{table_mapping}

## User Question
{question}

## Instructions
1. Generate ONLY a SELECT query - no INSERT, UPDATE, DELETE, etc.
2. Use the table names from the mapping above (sanitized names, not original sheet names)
3. Be concise and efficient
4. If the question cannot be answered from the data, explain why

## Response Format
Return ONLY the SQL query without any markdown formatting or explanation.
If the query is not possible, return: -- Cannot generate query: <reason>

SQL Query:"""


class LLMRouter:
    """Route requests to LLM for SQL generation with fallback support."""

    def __init__(self):
        """Initialize LLM router with primary and fallback models."""
        self.settings = get_settings()
        self._primary_llm: OllamaLLM | None = None
        self._fallback_llm: OllamaLLM | None = None
        self._prompt = PromptTemplate(
            input_variables=["schema_context", "table_mapping", "question"],
            template=SQL_GENERATION_PROMPT,
        )

    def _get_primary_llm(self) -> OllamaLLM:
        """Get or create primary LLM instance."""
        if self._primary_llm is None:
            self._primary_llm = OllamaLLM(
                model=self.settings.llm_model,
                base_url=self.settings.llm_base_url,
                temperature=0,
                num_predict=1024,
            )
        return self._primary_llm

    def _get_fallback_llm(self) -> OllamaLLM:
        """Get or create fallback LLM instance."""
        if self._fallback_llm is None:
            # Fallback uses same base URL but different model
            self._fallback_llm = OllamaLLM(
                model=self.settings.llm_fallback_model,
                base_url=self.settings.llm_base_url,
                temperature=0,
                num_predict=1024,
            )
        return self._fallback_llm

    async def health_check(self) -> dict[str, Any]:
        """Check LLM server connectivity.

        Returns:
            Dict with health status for primary and fallback models
        """
        results = {"primary": False, "fallback": False}

        try:
            llm = self._get_primary_llm()
            await llm.ainvoke("test")
            results["primary"] = True
        except Exception as e:
            logger.warning(f"Primary LLM health check failed: {e}")

        try:
            llm = self._get_fallback_llm()
            await llm.ainvoke("test")
            results["fallback"] = True
        except Exception as e:
            logger.warning(f"Fallback LLM health check failed: {e}")

        return results

    async def generate_sql(
        self,
        context: QueryContext,
        schema: ExcelSchema,
        table_mapping: dict[str, str],
    ) -> SQLQuery:
        """Generate SQL query from natural language question.

        Args:
            context: Query context with question and hints
            schema: Excel schema for context
            table_mapping: Mapping of sheet names to SQL table names

        Returns:
            SQLQuery with generated SQL and metadata
        """
        # Format inputs
        schema_context = schema.to_context_string()
        table_mapping_str = "\n".join(
            f"- Sheet '{k}' -> Table '{v}'" for k, v in table_mapping.items()
        )

        prompt_text = self._prompt.format(
            schema_context=schema_context,
            table_mapping=table_mapping_str,
            question=context.question,
        )

        # Try primary LLM first
        try:
            llm = self._get_primary_llm()
            response = await llm.ainvoke(prompt_text)
            logger.debug(f"Raw LLM response: {response[:500] if response else 'EMPTY'}")
            confidence = 0.85  # Primary model gets higher confidence
            logger.info(f"SQL generated using primary model: {self.settings.llm_model}")

        except Exception as e:
            logger.warning(f"Primary LLM failed, trying fallback: {e}")
            try:
                llm = self._get_fallback_llm()
                response = await llm.ainvoke(prompt_text)
                confidence = 0.65  # Fallback model gets lower confidence
                logger.info(
                    f"SQL generated using fallback model: {self.settings.llm_fallback_model}"
                )
            except Exception as fallback_error:
                logger.error(f"Both LLMs failed: {fallback_error}")
                raise RuntimeError(
                    f"All LLM models failed. Primary: {e}, Fallback: {fallback_error}"
                )

        # Parse response
        raw_sql = self._parse_sql_response(response)

        # Extract table names from SQL
        tables_used = self._extract_tables(raw_sql, table_mapping)

        return SQLQuery(
            raw_sql=raw_sql,
            explanation=f"Generated from question: {context.question}",
            confidence=confidence,
            tables_used=tables_used,
        )

    def _parse_sql_response(self, response: str) -> str:
        """Parse SQL from LLM response.

        Args:
            response: Raw LLM response

        Returns:
            Cleaned SQL query string
        """
        logger.info(f"Parsing LLM response (len={len(response)}): {response[:300]}...")

        # Clean up response
        sql = response.strip()

        # Remove markdown code blocks if present
        if sql.startswith("```sql"):
            sql = sql[6:]
        elif sql.startswith("```"):
            sql = sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3]

        # Handle error responses
        if sql.startswith("--"):
            # This is a comment indicating query couldn't be generated
            raise ValueError(sql)

        # Try to extract SELECT statement if response has extra text
        sql = sql.strip()
        if not sql.upper().startswith("SELECT"):
            # Look for SELECT in the response
            import re
            match = re.search(r'(SELECT\s+.+)', sql, re.IGNORECASE | re.DOTALL)
            if match:
                sql = match.group(1)
                logger.info(f"Extracted SELECT from response: {sql[:100]}...")

        if not sql:
            raise ValueError("LLM returned empty response - no SQL generated")

        return sql.strip()

    def _extract_tables(
        self, sql: str, table_mapping: dict[str, str]
    ) -> list[str]:
        """Extract table names used in SQL query.

        Args:
            sql: SQL query string
            table_mapping: Mapping of sheet names to table names

        Returns:
            List of table names found in query
        """
        sql_upper = sql.upper()
        tables = []

        for table_name in table_mapping.values():
            if table_name.upper() in sql_upper:
                tables.append(table_name)

        return tables

    def generate_sql_sync(
        self,
        context: QueryContext,
        schema: ExcelSchema,
        table_mapping: dict[str, str],
    ) -> SQLQuery:
        """Synchronous wrapper for generate_sql.

        Args:
            context: Query context with question and hints
            schema: Excel schema for context
            table_mapping: Mapping of sheet names to SQL table names

        Returns:
            SQLQuery with generated SQL and metadata
        """
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self.generate_sql(context, schema, table_mapping)
        )

    def get_few_shot_examples(self, question_type: QuestionType) -> list[dict[str, str]]:
        """Get few-shot examples for a question type.

        Args:
            question_type: The type of question

        Returns:
            List of example dicts with 'question' and 'sql' keys
        """
        examples = {
            QuestionType.PERSON: [
                {
                    "question": "김철수가 뭘 했어?",
                    "sql": """SELECT 날짜, 담당자, 작업내용, 상태, 'Daily_20241217' as source_sheet
FROM "Daily_20241217"
WHERE 담당자 LIKE '%김철수%'
UNION ALL
SELECT 날짜, 담당자, 작업내용, 상태, 'Daily_20241218' as source_sheet
FROM "Daily_20241218"
WHERE 담당자 LIKE '%김철수%'
ORDER BY 날짜 DESC"""
                },
                {
                    "question": "박영희 담당자 작업 내역 조회",
                    "sql": """SELECT 날짜, 담당자, 티켓번호, 작업유형, 작업내용, 상태, 'Daily_20241217' as source_sheet
FROM "Daily_20241217"
WHERE 담당자 = '박영희'
UNION ALL
SELECT 날짜, 담당자, 티켓번호, 작업유형, 작업내용, 상태, 'Weekly_W52' as source_sheet
FROM "Weekly_W52"
WHERE 담당자 = '박영희'
ORDER BY 날짜 DESC"""
                },
            ],
            QuestionType.PERIOD: [
                {
                    "question": "이번 주 완료된 티켓",
                    "sql": """SELECT 날짜, 티켓번호, 담당자, 작업내용, 상태, 'Daily_20241217' as source_sheet
FROM "Daily_20241217"
WHERE 상태 = '완료'
UNION ALL
SELECT 날짜, 티켓번호, 담당자, 작업내용, 상태, 'Daily_20241218' as source_sheet
FROM "Daily_20241218"
WHERE 상태 = '완료'
ORDER BY 날짜 DESC"""
                },
            ],
            QuestionType.EQUIPMENT: [
                {
                    "question": "CVD 설비 고장 이력",
                    "sql": """SELECT 날짜, 설비코드, 작업유형, 작업내용, 담당자, 'Daily_20241217' as source_sheet
FROM "Daily_20241217"
WHERE 설비코드 LIKE '%CVD%' AND 작업유형 LIKE '%고장%'
UNION ALL
SELECT 날짜, 설비코드, 작업유형, 작업내용, 담당자, 'Weekly_W52' as source_sheet
FROM "Weekly_W52"
WHERE 설비코드 LIKE '%CVD%' AND 작업유형 LIKE '%고장%'
ORDER BY 날짜 DESC"""
                },
            ],
            QuestionType.STATISTICS: [
                {
                    "question": "담당자별 총 처리 건수",
                    "sql": """SELECT 담당자, COUNT(*) as 총건수
FROM (
    SELECT 담당자 FROM "Daily_20241217"
    UNION ALL
    SELECT 담당자 FROM "Daily_20241218"
)
GROUP BY 담당자
ORDER BY 총건수 DESC"""
                },
            ],
        }
        return examples.get(question_type, [])

    async def generate_union_sql(
        self,
        question: str,
        multi_sheet_context: MultiSheetContext,
        period_info: dict[str, str | None] | None = None,
        equipment_info: dict[str, str | list[str] | None] | None = None,
    ) -> str:
        """Generate UNION ALL SQL for multi-sheet queries.

        Args:
            question: User's natural language question
            multi_sheet_context: Context with selected sheets and common columns
            period_info: Optional period extraction result from SheetGroupManager
            equipment_info: Optional equipment extraction result from SheetGroupManager

        Returns:
            UNION ALL SQL query string

        Raises:
            UnionSQLGenerationError: If SQL generation fails
        """
        if not multi_sheet_context.selected_sheets:
            raise UnionSQLGenerationError("No sheets selected for query")

        if not multi_sheet_context.common_columns:
            raise UnionSQLGenerationError("No common columns found across sheets")

        # Build prompt with few-shot examples
        few_shot_examples = self.get_few_shot_examples(multi_sheet_context.question_type)
        examples_text = ""
        for example in few_shot_examples[:2]:  # Use up to 2 examples
            examples_text += f"""
Example Question: {example['question']}
Example SQL:
{example['sql']}

"""

        # Build sheet info for prompt
        sheets_info = ", ".join([
            f'"{s.sheet_name}"' for s in multi_sheet_context.selected_sheets
        ])
        columns_info = ", ".join(multi_sheet_context.common_columns)

        prompt = f"""You are a SQL expert. Generate a UNION ALL query to search across multiple sheets.

## Available Sheets
{sheets_info}

## Common Columns (use ONLY these)
{columns_info}

## Important Rules
1. Use UNION ALL to combine results from all sheets
2. Each SELECT must use the SAME columns in the SAME order
3. Add a source_sheet column to identify which sheet each row came from
4. Use double quotes for table/sheet names: "Sheet_Name"
5. Only use the common columns listed above
6. Add appropriate WHERE clause based on the question
7. Order results by 날짜 DESC if available

{examples_text}

## User Question
{question}

## Response
Return ONLY the SQL query without any explanation or markdown formatting.

SQL Query:"""

        max_retries = 1  # EH-001: Retry once on invalid SQL
        last_error = None
        last_sql = None

        for attempt in range(max_retries + 1):
            try:
                llm = self._get_primary_llm()
                response = await llm.ainvoke(prompt)
                sql = self._parse_sql_response(response)
                last_sql = sql

                # Validate SQL syntax (EH-001)
                is_valid, validation_error = self._validate_sql_syntax(sql)
                if not is_valid:
                    logger.warning(
                        f"SQL validation failed (attempt {attempt + 1}): {validation_error}"
                    )
                    last_error = validation_error
                    if attempt < max_retries:
                        # Retry with a more explicit prompt
                        prompt += "\n\nIMPORTANT: Generate valid SQL only. Previous attempt had error: " + validation_error
                        continue
                    else:
                        # Max retries exceeded, use fallback
                        logger.warning("Max retries exceeded, using fallback SQL")
                        break

                # Validate that the SQL is a UNION query if multiple sheets
                if len(multi_sheet_context.selected_sheets) > 1:
                    if "UNION" not in sql.upper():
                        logger.warning("Generated SQL doesn't contain UNION, using fallback...")
                        sql = self._build_simple_union_sql(
                            question, multi_sheet_context, period_info, equipment_info
                        )

                logger.info(f"Generated UNION SQL: {sql[:200]}...")
                return sql

            except Exception as e:
                logger.error(f"Failed to generate UNION SQL (attempt {attempt + 1}): {e}")
                last_error = str(e)
                if attempt < max_retries:
                    continue

        # All retries failed, use fallback (EH-001)
        logger.info("Using fallback simple UNION SQL after validation/retry failures")
        try:
            sql = self._build_simple_union_sql(
                question, multi_sheet_context, period_info, equipment_info
            )
            logger.info("Fallback simple UNION SQL generated successfully")
            return sql
        except Exception as fallback_error:
            raise UnionSQLGenerationError(
                str(last_error), attempted_sql=last_sql
            ) from fallback_error

    def _build_simple_union_sql(
        self,
        question: str,
        context: MultiSheetContext,
        period_info: dict[str, str | None] | None = None,
        equipment_info: dict[str, str | list[str] | None] | None = None,
    ) -> str:
        """Build a simple UNION ALL SQL as fallback.

        Args:
            question: User's question for WHERE clause hints
            context: Multi-sheet context
            period_info: Optional period extraction result from SheetGroupManager
            equipment_info: Optional equipment extraction result from SheetGroupManager

        Returns:
            Simple UNION ALL SQL query
        """
        columns = context.common_columns
        if not columns:
            raise UnionSQLGenerationError("No common columns for UNION query")

        # Build column list
        column_list = ", ".join(columns)

        # Build WHERE clause based on question type
        where_clause = self._build_where_clause(
            question, context.question_type, period_info, equipment_info
        )

        # Build UNION query parts
        query_parts = []
        for selection in context.selected_sheets:
            sheet_name = selection.sheet_name
            part = f"""SELECT {column_list}, '{sheet_name}' as source_sheet
FROM "{sheet_name}"{where_clause}"""
            query_parts.append(part)

        # Combine with UNION ALL
        sql = "\nUNION ALL\n".join(query_parts)

        # Add ORDER BY if 날짜 column exists
        if "날짜" in columns:
            sql += "\nORDER BY 날짜 DESC"

        return sql

    def _build_where_clause(
        self,
        question: str,
        question_type: QuestionType,
        period_info: dict[str, str | None] | None = None,
        equipment_info: dict[str, str | list[str] | None] | None = None,
    ) -> str:
        """Build WHERE clause based on question and type.

        Args:
            question: User's question
            question_type: Detected question type
            period_info: Optional period extraction result from SheetGroupManager
            equipment_info: Optional equipment extraction result from SheetGroupManager

        Returns:
            WHERE clause string (including WHERE keyword) or empty string
        """
        import re

        if question_type == QuestionType.PERSON:
            # Extract Korean name from question
            korean_surnames = "김이박최정강조윤장임한오서신권황안송류홍"
            name_pattern = rf'([{korean_surnames}][가-힣]{{2}})'
            match = re.search(name_pattern, question)
            if match:
                name = match.group(1)
                return f"\nWHERE 담당자 LIKE '%{name}%'"

        elif question_type == QuestionType.PERIOD:
            # Build date filter based on period info
            conditions = []

            if period_info and period_info.get("start_date") and period_info.get("end_date"):
                start_date = period_info["start_date"]
                end_date = period_info["end_date"]

                if start_date == end_date:
                    # Single date
                    conditions.append(f"날짜 = '{start_date}'")
                else:
                    # Date range
                    conditions.append(f"날짜 >= '{start_date}' AND 날짜 <= '{end_date}'")

            # Check for status keywords in question
            if "완료" in question:
                conditions.append("상태 = '완료'")
            elif "진행" in question or "진행중" in question:
                conditions.append("상태 = '진행중'")
            elif "대기" in question:
                conditions.append("상태 = '대기'")

            if conditions:
                return "\nWHERE " + " AND ".join(conditions)

        elif question_type == QuestionType.EQUIPMENT:
            conditions = []

            # Use equipment_info if provided
            if equipment_info:
                if equipment_info.get("equipment_pattern"):
                    # Specific equipment code like CVD-001
                    pattern = equipment_info["equipment_pattern"]
                    conditions.append(f"설비코드 LIKE '%{pattern}%'")
                elif equipment_info.get("equipment_codes"):
                    # Multiple equipment codes - OR them together
                    codes = equipment_info["equipment_codes"]
                    if isinstance(codes, list) and len(codes) == 1:
                        conditions.append(f"설비코드 LIKE '%{codes[0]}%'")
                    elif isinstance(codes, list) and len(codes) > 1:
                        code_conditions = [f"설비코드 LIKE '%{c}%'" for c in codes]
                        conditions.append(f"({' OR '.join(code_conditions)})")

                # Add fault type filter if available
                if equipment_info.get("fault_type"):
                    fault_type = equipment_info["fault_type"]
                    conditions.append(f"작업유형 LIKE '%{fault_type}%'")
            else:
                # Fallback: extract equipment code from question directly
                equipment_keywords = ["CVD", "PVD", "ETCH", "CMP", "DIFF", "IMP", "LITHO", "PHOTO", "CLEAN"]
                for keyword in equipment_keywords:
                    if keyword in question.upper():
                        conditions.append(f"설비코드 LIKE '%{keyword}%'")
                        break

            if conditions:
                return "\nWHERE " + " AND ".join(conditions)

        return ""

    def _validate_sql_syntax(self, sql: str) -> tuple[bool, str | None]:
        """Validate SQL syntax for basic correctness.

        Args:
            sql: SQL query string to validate

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.
        """
        if not sql or not sql.strip():
            return False, "Query is empty"

        sql_upper = sql.upper().strip()

        # Must be a SELECT query
        if not sql_upper.startswith("SELECT") and "SELECT" not in sql_upper:
            return False, "Query must contain SELECT statement"

        # Check for dangerous keywords
        dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "INSERT", "UPDATE", "ALTER", "CREATE"]
        for keyword in dangerous_keywords:
            # Check for keyword followed by space or at end
            if f" {keyword} " in f" {sql_upper} ":
                return False, f"Query contains dangerous keyword: {keyword}"

        # Check for balanced quotes
        double_quote_count = sql.count('"')
        if double_quote_count % 2 != 0:
            return False, "Unbalanced double quotes in query"

        single_quote_count = sql.count("'")
        if single_quote_count % 2 != 0:
            return False, "Unbalanced single quotes in query"

        # Check for balanced parentheses
        open_parens = sql.count("(")
        close_parens = sql.count(")")
        if open_parens != close_parens:
            return False, "Unbalanced parentheses in query"

        return True, None
