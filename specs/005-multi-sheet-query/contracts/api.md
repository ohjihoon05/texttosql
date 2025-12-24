# API Contracts: Multi-Sheet Query Support

**Branch**: `005-multi-sheet-query` | **Date**: 2024-12-24

## Overview

내부 서비스 간 API 인터페이스 정의.

---

## Service Interfaces

### 1. SheetGroupManager

시트 그룹 분류 및 관리 서비스.

**Location**: `src/services/sheet_group_manager.py`

```python
from abc import ABC, abstractmethod
from models.sheet_group import (
    SheetGroup,
    SheetGroupConfig,
    SheetSelection,
    MultiSheetContext
)
from models.schema import ExcelSchema

class ISheetGroupManager(ABC):
    """시트 그룹 관리자 인터페이스"""

    @abstractmethod
    def classify_sheet(self, sheet_name: str) -> str:
        """
        시트를 그룹으로 분류

        Args:
            sheet_name: 시트 이름

        Returns:
            그룹 이름 (예: "TICKET_DAILY")

        Raises:
            ValueError: 시트 이름이 비어있는 경우
        """
        pass

    @abstractmethod
    def get_sheets_by_group(self, group_name: str) -> list[str]:
        """
        그룹에 속한 모든 시트 반환

        Args:
            group_name: 그룹 이름

        Returns:
            시트 이름 목록
        """
        pass

    @abstractmethod
    def find_common_columns(
        self,
        sheet_names: list[str],
        schema: ExcelSchema
    ) -> list[str]:
        """
        시트들의 공통 컬럼 찾기

        Args:
            sheet_names: 시트 이름 목록
            schema: Excel 스키마

        Returns:
            공통 컬럼 이름 목록

        Raises:
            ValueError: 공통 컬럼이 없는 경우
        """
        pass

    @abstractmethod
    def select_relevant_sheets(
        self,
        question: str,
        schema: ExcelSchema
    ) -> list[SheetSelection]:
        """
        질문에 관련된 시트 선택

        Args:
            question: 사용자 질문
            schema: Excel 스키마

        Returns:
            선택된 시트 목록 (최대 10개)
        """
        pass

    @abstractmethod
    def create_multi_sheet_context(
        self,
        question: str,
        schema: ExcelSchema
    ) -> MultiSheetContext:
        """
        다중 시트 쿼리 컨텍스트 생성

        Args:
            question: 사용자 질문
            schema: Excel 스키마

        Returns:
            다중 시트 컨텍스트
        """
        pass
```

---

### 2. LLMRouter (확장)

LLM SQL 생성 서비스 확장.

**Location**: `src/services/llm_router.py`

```python
from abc import ABC, abstractmethod
from models.query import QueryContext
from models.sheet_group import MultiSheetContext

class ILLMRouter(ABC):
    """LLM 라우터 인터페이스"""

    # 기존 메서드
    @abstractmethod
    async def generate_sql(
        self,
        question: str,
        context: QueryContext
    ) -> str:
        """SQL 생성 (단일 시트)"""
        pass

    # 신규 메서드
    @abstractmethod
    async def generate_union_sql(
        self,
        question: str,
        multi_sheet_context: MultiSheetContext
    ) -> str:
        """
        UNION ALL SQL 생성

        Args:
            question: 사용자 질문
            multi_sheet_context: 다중 시트 컨텍스트

        Returns:
            UNION ALL SQL 쿼리

        Raises:
            LLMGenerationError: SQL 생성 실패
            InvalidSchemaError: 스키마 불일치

        Example:
            SELECT 날짜, 담당자, 작업내용
            FROM "Daily_20241217"
            UNION ALL
            SELECT 날짜, 담당자, 작업내용
            FROM "Daily_20241218"
            WHERE 담당자 LIKE '%김철수%'
        """
        pass

    @abstractmethod
    def get_few_shot_examples(
        self,
        question_type: str
    ) -> list[dict[str, str]]:
        """
        질문 유형별 Few-shot 예제 반환

        Args:
            question_type: 질문 유형 (PERSON, PERIOD, EQUIPMENT, STATISTICS)

        Returns:
            [{"question": "...", "sql": "..."}, ...]
        """
        pass
```

---

### 3. SQLAgent (확장)

SQL 에이전트 서비스 확장.

**Location**: `src/services/sql_agent.py`

```python
from abc import ABC, abstractmethod
from models.query import QueryContext, QueryResult
from models.sheet_group import MultiSheetContext, UnionQueryResult

class ISQLAgent(ABC):
    """SQL 에이전트 인터페이스"""

    # 기존 메서드
    @abstractmethod
    async def ask(
        self,
        question: str,
        excel_path: str
    ) -> QueryResult:
        """질문에 답변 (단일/다중 시트 자동 결정)"""
        pass

    # 신규 메서드
    @abstractmethod
    async def execute_multi_sheet_query(
        self,
        context: MultiSheetContext,
        sql: str
    ) -> UnionQueryResult:
        """
        다중 시트 UNION 쿼리 실행

        Args:
            context: 다중 시트 컨텍스트
            sql: UNION ALL SQL

        Returns:
            UNION 쿼리 결과

        Raises:
            QueryExecutionError: 쿼리 실행 실패
            TimeoutError: 실행 시간 초과 (10초)
        """
        pass

    @abstractmethod
    def should_use_multi_sheet(
        self,
        question: str
    ) -> bool:
        """
        다중 시트 쿼리 필요 여부 판단

        Args:
            question: 사용자 질문

        Returns:
            True if 다중 시트 쿼리 필요
        """
        pass
```

---

### 4. ExcelLoader (확장)

Excel 로더 서비스 확장.

**Location**: `src/services/excel_loader.py`

```python
from abc import ABC, abstractmethod
from models.schema import ExcelSchema

class IExcelLoader(ABC):
    """Excel 로더 인터페이스"""

    # 기존 메서드
    @abstractmethod
    async def load(self, file_path: str) -> ExcelSchema:
        """Excel 파일 로드"""
        pass

    @abstractmethod
    async def execute_query(self, sql: str) -> list[dict]:
        """SQL 쿼리 실행"""
        pass

    # 신규 메서드
    @abstractmethod
    async def execute_union_query(
        self,
        sql: str,
        timeout_seconds: float = 10.0
    ) -> tuple[list[dict], dict[str, int]]:
        """
        UNION 쿼리 실행 (시트별 건수 포함)

        Args:
            sql: UNION ALL SQL
            timeout_seconds: 타임아웃 (기본 10초)

        Returns:
            (결과 데이터, {시트명: 건수})

        Raises:
            QueryExecutionError: 쿼리 실행 실패
            TimeoutError: 타임아웃 초과
        """
        pass

    @abstractmethod
    def get_sheet_row_count(self, sheet_name: str) -> int:
        """
        시트 행 수 조회

        Args:
            sheet_name: 시트 이름

        Returns:
            행 수
        """
        pass
```

---

## Error Handling Contracts

### Exception Classes

```python
# src/exceptions.py

class TextToSQLError(Exception):
    """기본 예외 클래스"""
    pass

class SheetGroupError(TextToSQLError):
    """시트 그룹 관련 오류"""
    pass

class NoCommonColumnsError(SheetGroupError):
    """공통 컬럼 없음 오류"""
    def __init__(self, sheets: list[str]):
        self.sheets = sheets
        super().__init__(
            f"No common columns found between sheets: {', '.join(sheets)}"
        )

class IncompatibleSheetsError(SheetGroupError):
    """호환되지 않는 시트 조합 오류"""
    def __init__(self, group1: str, group2: str):
        self.group1 = group1
        self.group2 = group2
        super().__init__(
            f"Cannot UNION sheets from incompatible groups: {group1} and {group2}"
        )

class TooManySheetsError(SheetGroupError):
    """시트 개수 초과 오류"""
    def __init__(self, count: int, max_count: int):
        self.count = count
        self.max_count = max_count
        super().__init__(
            f"Too many sheets selected: {count} (max: {max_count})"
        )

class LLMGenerationError(TextToSQLError):
    """LLM SQL 생성 오류"""
    pass

class UnionSQLGenerationError(LLMGenerationError):
    """UNION SQL 생성 오류"""
    def __init__(self, reason: str, attempted_sql: str = None):
        self.reason = reason
        self.attempted_sql = attempted_sql
        super().__init__(f"Failed to generate UNION SQL: {reason}")

class QueryExecutionError(TextToSQLError):
    """쿼리 실행 오류"""
    pass
```

---

## Request/Response Contracts

### ask() 요청/응답

```python
# Request
{
    "question": "김철수가 뭘 했어?",
    "excel_path": "/data/report.xlsx"
}

# Response (Success - Multi-sheet)
{
    "success": True,
    "data": [
        {"날짜": "2024-12-17", "담당자": "김철수", "작업내용": "장비 점검"},
        {"날짜": "2024-12-18", "담당자": "김철수", "작업내용": "PM 작업"}
    ],
    "sql_query": "SELECT ... UNION ALL ...",
    "sheet_summaries": [
        {"sheet_name": "Daily_20241217", "row_count": 3},
        {"sheet_name": "Daily_20241218", "row_count": 2}
    ],
    "total_sheets_queried": 2,
    "natural_response": "김철수 담당자는 최근 5건의 작업을 수행했습니다..."
}

# Response (Error)
{
    "success": False,
    "error_code": "NO_COMMON_COLUMNS",
    "error_message": "선택된 시트들 사이에 공통 컬럼이 없습니다",
    "suggestion": "같은 유형의 시트만 조회해 주세요"
}
```

---

## Integration Flow

```
┌────────────────────────────────────────────────────────────────┐
│                         SQLAgent.ask()                          │
│  1. should_use_multi_sheet(question) 호출                       │
│     └─ True 반환                                                │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│           SheetGroupManager.create_multi_sheet_context()        │
│  1. classify_sheet() - 각 시트 그룹 분류                        │
│  2. select_relevant_sheets() - 관련 시트 선택                   │
│  3. find_common_columns() - 공통 컬럼 식별                      │
│  4. MultiSheetContext 생성 및 반환                              │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│              LLMRouter.generate_union_sql()                     │
│  1. get_few_shot_examples(question_type) - 예제 가져오기        │
│  2. 프롬프트 구성 (시트 목록 + 공통 컬럼 + Few-shot)             │
│  3. LLM 호출 → UNION ALL SQL 생성                               │
│  4. SQL 검증 및 반환                                            │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│           ExcelLoader.execute_union_query()                     │
│  1. DuckDB에서 UNION ALL SQL 실행                               │
│  2. 시트별 건수 집계                                            │
│  3. 결과 반환                                                   │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                     UnionQueryResult                            │
│  - success: True                                                │
│  - data: [...]                                                  │
│  - sheet_summaries: [{sheet: ..., count: ...}, ...]             │
└────────────────────────────────────────────────────────────────┘
```

---

## Configuration Contract

```python
# Environment Variables

TEXTTOSQL_MAX_UNION_SHEETS=10           # 최대 UNION 시트 수
TEXTTOSQL_DEFAULT_UNION_STRATEGY=COMMON_COLUMNS  # UNION 전략
TEXTTOSQL_QUERY_TIMEOUT=10.0            # 쿼리 타임아웃 (초)

# Sheet Group Patterns (config.py)
TEXTTOSQL_SHEET_PATTERNS = {
    "TICKET_DAILY": r"^Daily_\d{8}$",
    "TICKET_WEEKLY": r"^Weekly_W\d{1,2}$",
    "TICKET_MONTHLY": r"^Monthly_",
    "EQUIPMENT": r"^Equipment_",
    "TEAM": r"^Team_"
}
```

---

## Testing Contracts

### Unit Test Requirements

| 서비스 | 테스트 항목 | 커버리지 목표 |
|--------|------------|--------------|
| SheetGroupManager | classify_sheet, find_common_columns | 90% |
| LLMRouter | generate_union_sql, get_few_shot_examples | 80% |
| SQLAgent | should_use_multi_sheet, execute_multi_sheet_query | 85% |
| ExcelLoader | execute_union_query | 90% |

### Integration Test Requirements

| 시나리오 | 예상 결과 |
|----------|----------|
| 담당자 질문 → 5개 Daily 시트 UNION | 성공, 100건+ |
| 기간 질문 → Weekly + Monthly UNION | 성공, 컬럼 일치 |
| 설비 질문 → EQUIPMENT + TICKET 시도 | IncompatibleSheetsError |
| 11개 시트 선택 | TooManySheetsError |
