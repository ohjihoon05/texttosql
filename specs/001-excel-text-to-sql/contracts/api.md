# API Contracts: Excel Text-to-SQL System

**Feature ID**: 001-excel-text-to-sql
**Date**: 2024-12-23

## Overview

Chainlit 기반 시스템이므로 REST API가 아닌 Chainlit 메시지 인터페이스를 정의.

## Chainlit Message Interface

### 1. File Upload

사용자가 Excel 파일 업로드 시 처리.

```python
@cl.on_chat_start
async def on_chat_start():
    """채팅 시작 시 파일 업로드 요청"""
    files = await cl.AskFileMessage(
        content="분석할 Excel 파일을 업로드해주세요.",
        accept=["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
        max_size_mb=10
    ).send()
```

**Request**: Excel 파일 (.xlsx)
**Response**: 로딩 확인 메시지

```python
# 성공 시
await cl.Message(
    content=f"✅ {file.name} 로딩 완료!\n"
            f"- 시트 수: {len(schema.sheets)}\n"
            f"- 총 행 수: {total_rows:,}\n"
            f"- 로딩 시간: {load_time:.2f}초\n\n"
            f"자연어로 질문해주세요. 예: '김철수가 이번 주에 뭘 했어?'"
).send()

# 실패 시
await cl.Message(
    content=f"❌ 파일 로딩 실패: {error_message}"
).send()
```

### 2. Natural Language Query

자연어 질문 → SQL 변환 → 결과 반환.

```python
@cl.on_message
async def on_message(message: cl.Message):
    """사용자 메시지 처리"""
```

**Request**: 자연어 질문 (str)
```
"김철수가 이번 주에 뭘 했어?"
```

**Response**: 구조화된 답변
```python
# Step 1: 처리 중 표시
step = cl.Step(name="SQL 생성 중...")
await step.send()

# Step 2: SQL 쿼리 표시
await cl.Message(
    content="```sql\n"
            "SELECT * FROM daily_report\n"
            "WHERE 담당자 = '김철수'\n"
            "AND 날짜 >= '2024-12-16'\n"
            "```"
).send()

# Step 3: 결과 표시
await cl.Message(
    content="## 조회 결과 (5건)\n\n"
            "| 날짜 | 업무 | 설비 | 상태 |\n"
            "|------|------|------|------|\n"
            "| 12/20 | PM 점검 | ASM-01 | 완료 |\n"
            "| ... | ... | ... | ... |"
).send()
```

### 3. Error Responses

| Error Type | Message Format |
|------------|----------------|
| No File | "❌ 먼저 Excel 파일을 업로드해주세요." |
| Invalid Query | "🤔 질문을 이해하지 못했어요. 다시 한번 설명해주세요." |
| SQL Error | "⚠️ SQL 실행 오류: {error}\n\n시도한 쿼리:\n```sql\n{sql}\n```" |
| Timeout | "⏱️ 응답 시간 초과. 좀 더 구체적인 질문을 해주세요." |
| LLM Error | "🔄 AI 서버 연결 문제. 대체 모델로 재시도 중..." |

## Internal Service Interfaces

### ExcelLoader

```python
class ExcelLoader:
    async def load(self, file_path: str) -> ExcelSchema:
        """Excel 파일을 DuckDB에 로드하고 스키마 반환"""
        pass

    async def get_schema(self) -> ExcelSchema:
        """현재 로드된 스키마 반환"""
        pass

    async def execute_query(self, sql: str) -> QueryResult:
        """SQL 쿼리 실행"""
        pass
```

### SchemaFilter

```python
class SchemaFilter:
    def filter_relevant(
        self,
        question: str,
        schema: ExcelSchema,
        max_sheets: int = 5
    ) -> List[SheetSchema]:
        """질문과 관련된 시트만 필터링"""
        pass

    def generate_context(
        self,
        sheets: List[SheetSchema]
    ) -> str:
        """LLM 프롬프트용 스키마 컨텍스트 생성"""
        pass
```

### QueryCache

```python
class QueryCache:
    async def get(self, question: str) -> Optional[CacheEntry]:
        """캐시에서 결과 조회"""
        pass

    async def set(
        self,
        question: str,
        sql: str,
        result: QueryResult,
        ttl_seconds: int = 3600
    ) -> None:
        """결과를 캐시에 저장"""
        pass

    async def invalidate_all(self) -> None:
        """캐시 전체 무효화 (파일 변경 시)"""
        pass
```

### LLMRouter

```python
class LLMRouter:
    async def generate_sql(
        self,
        context: QueryContext
    ) -> SQLQuery:
        """자연어를 SQL로 변환"""
        pass

    async def explain_result(
        self,
        question: str,
        result: QueryResult
    ) -> str:
        """결과를 자연어로 설명"""
        pass
```

## Streaming Interface

긴 응답을 위한 스트리밍 지원.

```python
@cl.on_message
async def on_message(message: cl.Message):
    # 스트리밍 메시지 생성
    msg = cl.Message(content="")
    await msg.send()

    # 청크 단위로 업데이트
    async for chunk in llm_router.stream_response(context):
        await msg.stream_token(chunk)

    # 스트리밍 완료
    await msg.update()
```

## Configuration Interface

환경 설정 인터페이스.

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Ollama 설정
    ollama_base_url: str = "http://10.249.22.191:11435"
    ollama_model: str = "gpt-oss:20b"
    ollama_timeout: int = 30

    # Fallback 설정
    fallback_enabled: bool = True
    fallback_model: str = "llama3.2:1b"
    fallback_url: str = "http://localhost:11434"

    # 캐시 설정
    cache_ttl_seconds: int = 3600
    cache_db_path: str = "./data/cache.db"

    # 스키마 필터링
    max_relevant_sheets: int = 5
    column_sample_size: int = 5

    # 성능
    query_timeout_seconds: int = 10
    max_result_rows: int = 100

    class Config:
        env_file = ".env"
```

## Error Codes

| Code | Name | Description |
|------|------|-------------|
| E001 | FILE_NOT_FOUND | 파일이 존재하지 않음 |
| E002 | FILE_TOO_LARGE | 파일 크기 초과 (>10MB) |
| E003 | INVALID_FORMAT | 지원하지 않는 파일 형식 |
| E004 | SCHEMA_ERROR | 스키마 파싱 실패 |
| E005 | SQL_GENERATION_FAILED | SQL 생성 실패 |
| E006 | SQL_EXECUTION_ERROR | SQL 실행 오류 |
| E007 | LLM_TIMEOUT | LLM 응답 시간 초과 |
| E008 | LLM_UNAVAILABLE | LLM 서버 연결 불가 |
| E009 | CACHE_ERROR | 캐시 작업 실패 |
