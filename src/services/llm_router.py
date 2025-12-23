"""LLM routing and SQL generation using Ollama."""

import logging
from typing import Any

from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate

from src.config import get_settings
from src.models.schema import ExcelSchema
from src.models.query import QueryContext, SQLQuery

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
