# Data Model: Excel Text-to-SQL System

**Feature ID**: 001-excel-text-to-sql
**Date**: 2024-12-23

## Overview

Excel 데이터를 SQL로 쿼리하기 위한 데이터 모델 정의.

## Core Models

### 1. ExcelSchema

Excel 파일의 스키마 정보를 표현.

```python
from pydantic import BaseModel
from typing import Dict, List, Optional

class ColumnInfo(BaseModel):
    """컬럼 정보"""
    name: str
    dtype: str  # 'string', 'int64', 'float64', 'datetime64', etc.
    nullable: bool = True
    sample_values: List[str] = []  # 상위 5개 샘플

class SheetSchema(BaseModel):
    """시트 스키마"""
    name: str
    columns: List[ColumnInfo]
    row_count: int
    relevance_score: float = 0.0  # 질문 관련도 점수

class ExcelSchema(BaseModel):
    """Excel 파일 전체 스키마"""
    file_name: str
    file_size_mb: float
    sheets: Dict[str, SheetSchema]
    load_time_seconds: float
```

### 2. QueryContext

LLM에 전달할 쿼리 컨텍스트.

```python
class QueryContext(BaseModel):
    """SQL 생성을 위한 컨텍스트"""
    question: str
    relevant_sheets: List[SheetSchema]  # 필터링된 시트들
    terminology_hints: List[str] = []    # RAG에서 가져온 용어 힌트
    previous_queries: List[str] = []     # 대화 히스토리

class SQLQuery(BaseModel):
    """생성된 SQL 쿼리"""
    raw_sql: str
    explanation: str  # SQL 설명 (자연어)
    confidence: float = 0.0
    tables_used: List[str] = []
```

### 3. QueryResult

쿼리 실행 결과.

```python
from typing import Any

class QueryResult(BaseModel):
    """쿼리 실행 결과"""
    success: bool
    data: List[Dict[str, Any]] = []
    row_count: int = 0
    column_names: List[str] = []
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None

class FormattedResponse(BaseModel):
    """사용자에게 표시할 최종 응답"""
    answer: str           # 자연어 답변
    sql_query: str        # 사용된 SQL
    data_preview: str     # 테이블 형태 미리보기
    source_sheets: List[str]
```

### 4. CacheEntry

쿼리 캐시 엔트리.

```python
from datetime import datetime

class CacheEntry(BaseModel):
    """캐시 엔트리"""
    question_hash: str
    question: str
    sql_query: str
    result_json: str
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0
```

## Database Schemas

### DuckDB Tables (동적 생성)

Excel 시트가 DuckDB 테이블로 자동 변환됨.

```sql
-- 예시: Sheet1 → sheet1 테이블
CREATE TABLE sheet1 AS
SELECT * FROM read_xlsx('report.xlsx', sheet='Sheet1');

-- 스키마 조회
DESCRIBE sheet1;
```

### SQLite Cache Schema

```sql
-- 쿼리 캐시 테이블
CREATE TABLE IF NOT EXISTS query_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_hash TEXT UNIQUE NOT NULL,
    question TEXT NOT NULL,
    sql_query TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    hit_count INTEGER DEFAULT 0
);

CREATE INDEX idx_cache_hash ON query_cache(question_hash);
CREATE INDEX idx_cache_expires ON query_cache(expires_at);

-- 스키마 캐시 테이블
CREATE TABLE IF NOT EXISTS schema_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT UNIQUE NOT NULL,
    schema_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### ChromaDB Collections

```python
# 반도체 용어 컬렉션
terminology_collection = client.get_or_create_collection(
    name="semiconductor_terminology",
    metadata={"description": "반도체 설비 CS 전문 용어"}
)

# 문서 스키마
{
    "id": "term_001",
    "document": "ASM: 반도체 장비 제조사 (ASM International)",
    "metadata": {
        "category": "manufacturer",
        "aliases": ["에이에스엠", "asm"],
        "related_terms": ["CVD", "ALD", "Epitaxy"]
    }
}
```

## Data Flow

```
┌─────────────────┐
│  Excel File     │
│  (3-4MB, 30시트) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Excel Loader   │────▶│  ExcelSchema    │
│  (openpyxl)     │     │  (메타데이터)    │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│    DuckDB       │     │  Schema Cache   │
│  (쿼리 엔진)     │     │  (SQLite)       │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│  Query Result   │
│  (DataFrame)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Formatted      │
│  Response       │
└─────────────────┘
```

## Type Mappings

### Excel → Python → SQL

| Excel Type | Python Type | DuckDB Type |
|------------|-------------|-------------|
| Text | str | VARCHAR |
| Number (int) | int | INTEGER |
| Number (float) | float | DOUBLE |
| Date | datetime | DATE |
| DateTime | datetime | TIMESTAMP |
| Boolean | bool | BOOLEAN |
| Empty | None | NULL |

### Korean Text Processing

```python
# 형태소 분석 결과 타입
class MorphemeResult(BaseModel):
    original: str
    morphemes: List[str]      # 형태소 분리 결과
    nouns: List[str]          # 명사만 추출
    keywords: List[str]       # 검색용 키워드
```

## Validation Rules

1. **ExcelSchema**
   - file_size_mb: 0 < size <= 10 (10MB 제한)
   - sheets: 1 <= len(sheets) <= 50

2. **QueryContext**
   - question: 1 <= len(question) <= 500
   - relevant_sheets: len <= 10

3. **SQLQuery**
   - raw_sql: SELECT 문만 허용 (INSERT/UPDATE/DELETE 금지)
   - confidence: 0.0 <= confidence <= 1.0

4. **CacheEntry**
   - expires_at > created_at
   - TTL: 기본 1시간
