# Data Model: AI 서비스 스타일 자연어 응답

**Date**: 2025-12-23
**Feature**: 004-ai-response-style

## Entities

### ResponseContext (신규)

LLM 응답 생성을 위한 컨텍스트.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| question | str | 원본 질문 | 필수, 1-500자 |
| sql_query | str | 실행된 SQL | 필수 |
| result | QueryResult | SQL 실행 결과 | 필수 |
| column_names | List[str] | 컬럼명 목록 | 필수 |

### ResponseType (신규 Enum)

응답 유형 분류.

| Value | Description | Trigger Condition |
|-------|-------------|-------------------|
| EMPTY | 결과 없음 | row_count == 0 |
| SINGLE | 단건 결과 | row_count == 1 |
| FEW | 소수 결과 | 2 <= row_count <= 10 |
| MANY | 다건 결과 | row_count > 10 |
| ERROR | 오류 발생 | success == False |

### FormattedResponse (기존 확장)

기존 모델에 필드 추가.

| Field | Type | Description | Status |
|-------|------|-------------|--------|
| answer | str | 자연어 답변 | 기존 |
| sql_query | str | 실행 SQL | 기존 |
| data_preview | str | 데이터 테이블 | 기존 |
| source_sheets | List[str] | 소스 시트 | 기존 |
| response_type | ResponseType | 응답 유형 | **신규** |
| suggested_questions | List[str] | 후속 질문 제안 | **신규 (P3)** |

## Relationships

```
QueryResult --> ResponseContext --> ResponseGenerator --> FormattedResponse
                     |                    |
                     v                    v
              ResponseType           LLM (Ollama)
```

## State Transitions

```
Query Received
     |
     v
SQL Executed --> [success=False] --> ERROR response
     |
     v (success=True)
Check row_count
     |
     +-- 0 --> EMPTY response
     +-- 1 --> SINGLE response  
     +-- 2-10 --> FEW response
     +-- >10 --> MANY response
```
