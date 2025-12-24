"""LLM-based response generator for natural language answers."""

import asyncio
import json
import logging
from typing import List

from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate

from src.config import get_settings
from src.models.query import QueryResult, ResponseType, ResponseContext

logger = logging.getLogger(__name__)


# Prompt template for natural language response generation
RESPONSE_PROMPT = """당신은 반도체 설비 CS 데일리 리포트 분석 도우미입니다.
사용자의 질문과 SQL 조회 결과를 바탕으로 자연스러운 한국어로 답변하세요.

## 지침
- 존칭을 사용하세요 (예: ~님, ~입니다, ~했습니다)
- 핵심 정보를 먼저 언급하세요
- 결과가 없으면 친절하게 안내하고 대안을 제시하세요
- 숫자나 날짜는 명확하게 표현하세요
- 간결하되 필요한 정보는 모두 포함하세요

## 사용자 질문
{question}

## 조회 결과 정보
- 결과 건수: {row_count}건
- 컬럼: {columns}

## 조회된 데이터 (샘플)
{sample_data}

## 응답 형식
자연스러운 한국어 문장으로 답변하세요. 마크다운 형식이나 특수 기호 없이 일반 텍스트로 작성하세요.

답변:"""


# Prompt for summarizing large result sets
SUMMARY_PROMPT = """당신은 반도체 설비 CS 데일리 리포트 분석 도우미입니다.
대량의 조회 결과를 요약하여 핵심 인사이트를 제공하세요.

## 사용자 질문
{question}

## 조회 결과 정보
- 총 결과 건수: {row_count}건
- 컬럼: {columns}

## 샘플 데이터 (상위 5건)
{sample_data}

## 지침
- 전체 결과의 패턴이나 특징을 요약하세요
- 가장 빈번한 항목이나 특이사항을 언급하세요
- 필요시 상위 몇 개의 예시를 포함하세요
- 존칭을 사용하고 자연스러운 문장으로 작성하세요

요약 답변:"""


# Prompt for generating follow-up question suggestions
SUGGESTION_PROMPT = """사용자의 질문과 조회 결과를 바탕으로 관련된 후속 질문 2개를 제안하세요.

## 원본 질문
{question}

## 조회 결과 요약
- 결과 건수: {row_count}건
- 주요 컬럼: {columns}

## 지침
- 사용자가 더 깊이 탐색할 수 있는 질문을 제안하세요
- 자연스러운 한국어 질문 형태로 작성하세요
- 각 질문은 한 줄로 작성하세요

후속 질문 (한 줄에 하나씩):"""


class ResponseGenerator:
    """Generate natural language responses from SQL query results using LLM."""

    def __init__(self):
        """Initialize response generator with LLM settings."""
        self.settings = get_settings()
        self._llm: OllamaLLM | None = None
        self._response_prompt = PromptTemplate(
            input_variables=["question", "row_count", "columns", "sample_data"],
            template=RESPONSE_PROMPT,
        )
        self._summary_prompt = PromptTemplate(
            input_variables=["question", "row_count", "columns", "sample_data"],
            template=SUMMARY_PROMPT,
        )
        self._suggestion_prompt = PromptTemplate(
            input_variables=["question", "row_count", "columns"],
            template=SUGGESTION_PROMPT,
        )

    def _get_llm(self) -> OllamaLLM:
        """Get or create LLM instance."""
        if self._llm is None:
            self._llm = OllamaLLM(
                model=self.settings.llm_fallback_model,  # Use smaller model for responses
                base_url=self.settings.llm_base_url,
                temperature=0.7,  # Slightly creative for natural responses
                num_predict=150,  # Limit response length for speed
            )
        return self._llm

    def get_response_type(self, result: QueryResult) -> ResponseType:
        """Determine response type from query result.

        Args:
            result: Query result to analyze

        Returns:
            ResponseType enum value
        """
        if not result.success:
            return ResponseType.ERROR

        if result.row_count == 0:
            return ResponseType.EMPTY
        elif result.row_count == 1:
            return ResponseType.SINGLE
        elif result.row_count <= 10:
            return ResponseType.FEW
        else:
            return ResponseType.MANY

    def _build_context(self, question: str, result: QueryResult) -> ResponseContext:
        """Build response context from query result.

        Args:
            question: Original user question
            result: Query result

        Returns:
            ResponseContext with formatted data
        """
        response_type = self.get_response_type(result)
        # Use to_dict_list() for DataFrame compatibility
        sample_data = result.to_dict_list()[:5] if result.data is not None else []

        return ResponseContext(
            question=question,
            sql_query="",
            row_count=result.row_count,
            column_names=result.column_names,
            sample_data=sample_data,
            response_type=response_type,
        )

    def _build_prompt(self, context: ResponseContext, use_summary: bool = False) -> str:
        """Build prompt string from context.

        Args:
            context: Response context
            use_summary: Whether to use summary prompt for large results

        Returns:
            Formatted prompt string
        """
        # Format sample data as readable text
        if context.sample_data:
            data_lines = []
            for i, row in enumerate(context.sample_data, 1):
                row_str = ", ".join(f"{k}: {v}" for k, v in row.items())
                data_lines.append(f"{i}. {row_str}")
            sample_data_str = "\n".join(data_lines)
        else:
            sample_data_str = "(데이터 없음)"

        columns_str = ", ".join(context.column_names) if context.column_names else "(없음)"

        template = self._summary_prompt if use_summary else self._response_prompt

        return template.format(
            question=context.question,
            row_count=context.row_count,
            columns=columns_str,
            sample_data=sample_data_str,
        )

    def _fallback_simple_response(self, result: QueryResult) -> str:
        """Generate simple fallback response when LLM times out.

        Args:
            result: Query result

        Returns:
            Simple formatted response string
        """
        response_type = self.get_response_type(result)

        if response_type == ResponseType.ERROR:
            return f"쿼리 실행 중 오류가 발생했습니다: {result.error_message}"

        if response_type == ResponseType.EMPTY:
            return "해당 조건에 맞는 데이터를 찾을 수 없습니다. 다른 조건으로 검색해보시겠어요?"

        if response_type == ResponseType.SINGLE:
            return f"1건의 결과를 찾았습니다. (실행 시간: {result.execution_time_ms:.1f}ms)"

        return (
            f"{result.row_count}건의 결과를 찾았습니다. "
            f"(실행 시간: {result.execution_time_ms:.1f}ms)"
        )

    async def generate_response(
        self,
        question: str,
        result: QueryResult,
        timeout: float = 15.0,
    ) -> str:
        """Generate natural language response from query result.

        Args:
            question: Original user question
            result: SQL query result
            timeout: LLM call timeout in seconds

        Returns:
            Natural language response string
        """
        context = self._build_context(question, result)

        # Handle error and empty cases without LLM
        if context.response_type == ResponseType.ERROR:
            return f"쿼리 실행 중 오류가 발생했습니다: {result.error_message}"

        if context.response_type == ResponseType.EMPTY:
            return "해당 조건에 맞는 데이터를 찾을 수 없습니다. 다른 조건으로 검색해보시겠어요?"

        # Use summary prompt for large result sets
        use_summary = context.response_type == ResponseType.MANY
        prompt = self._build_prompt(context, use_summary=use_summary)

        try:
            llm = self._get_llm()

            # Direct call without asyncio.wait_for (compatibility issue with langchain_ollama)
            response = await llm.ainvoke(prompt)

            # Clean up response
            response = response.strip()
            logger.info(f"Generated natural language response ({len(response)} chars)")
            return response

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return self._fallback_simple_response(result)

    async def generate_suggested_questions(
        self,
        question: str,
        result: QueryResult,
        max_suggestions: int = 2,
    ) -> List[str]:
        """Generate follow-up question suggestions.

        Args:
            question: Original question
            result: Query result for context
            max_suggestions: Maximum suggestions to return

        Returns:
            List of suggested follow-up questions
        """
        if result.row_count == 0:
            return []

        columns_str = ", ".join(result.column_names[:5]) if result.column_names else ""

        prompt = self._suggestion_prompt.format(
            question=question,
            row_count=result.row_count,
            columns=columns_str,
        )

        try:
            llm = self._get_llm()

            response = await asyncio.wait_for(
                llm.ainvoke(prompt),
                timeout=2.0,
            )

            # Parse response into list of questions
            lines = [line.strip() for line in response.strip().split("\n")]
            suggestions = [
                line.lstrip("0123456789.-) ").strip()
                for line in lines
                if line and "?" in line
            ]

            return suggestions[:max_suggestions]

        except Exception as e:
            logger.warning(f"Failed to generate suggestions: {e}")
            return []
