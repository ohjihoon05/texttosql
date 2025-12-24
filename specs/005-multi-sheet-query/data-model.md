# Data Model: Multi-Sheet Query Support

**Branch**: `005-multi-sheet-query` | **Date**: 2024-12-24

## Overview

다중 시트 쿼리 지원을 위한 Pydantic 데이터 모델 정의.

---

## New Models

### SheetGroup

시트 그룹 정의 모델.

```python
from pydantic import BaseModel, Field
from typing import Optional
import re

class SheetGroup(BaseModel):
    """시트 그룹 정의"""

    name: str = Field(..., description="그룹 이름 (예: TICKET_DAILY)")
    pattern: str = Field(..., description="시트 이름 정규식 패턴")
    description: Optional[str] = Field(None, description="그룹 설명")
    union_compatible_with: list[str] = Field(
        default_factory=list,
        description="UNION 가능한 그룹 목록"
    )
    priority: int = Field(
        default=0,
        description="시트 선택 우선순위 (높을수록 우선)"
    )

    def matches(self, sheet_name: str) -> bool:
        """시트 이름이 패턴과 일치하는지 확인"""
        return bool(re.match(self.pattern, sheet_name))

    class Config:
        json_schema_extra = {
            "example": {
                "name": "TICKET_DAILY",
                "pattern": r"^Daily_\d{8}$",
                "description": "일일 티켓 시트",
                "union_compatible_with": ["TICKET_WEEKLY", "TICKET_MONTHLY"],
                "priority": 10
            }
        }
```

### SheetGroupConfig

시트 그룹 설정 모델.

```python
from pydantic import BaseModel, Field

class SheetGroupConfig(BaseModel):
    """시트 그룹 설정"""

    groups: list[SheetGroup] = Field(
        default_factory=list,
        description="정의된 시트 그룹 목록"
    )
    default_group: str = Field(
        default="UNKNOWN",
        description="매칭되지 않는 시트의 기본 그룹"
    )
    max_union_sheets: int = Field(
        default=10,
        ge=1,
        le=20,
        description="UNION 가능한 최대 시트 수"
    )

    def get_group(self, sheet_name: str) -> str:
        """시트 이름으로 그룹 찾기"""
        for group in sorted(self.groups, key=lambda g: -g.priority):
            if group.matches(sheet_name):
                return group.name
        return self.default_group

    def get_compatible_groups(self, group_name: str) -> list[str]:
        """UNION 호환 그룹 목록 반환"""
        for group in self.groups:
            if group.name == group_name:
                return [group_name] + group.union_compatible_with
        return [group_name]
```

### SheetSelection

선택된 시트 정보.

```python
from pydantic import BaseModel, Field
from typing import Optional

class SheetSelection(BaseModel):
    """선택된 시트 정보"""

    sheet_name: str = Field(..., description="시트 이름")
    group_name: str = Field(..., description="속한 그룹 이름")
    common_columns: list[str] = Field(
        default_factory=list,
        description="공통 컬럼 목록"
    )
    row_count: Optional[int] = Field(None, description="예상 행 수")

    class Config:
        json_schema_extra = {
            "example": {
                "sheet_name": "Daily_20241217",
                "group_name": "TICKET_DAILY",
                "common_columns": ["날짜", "티켓번호", "담당자", "상태"],
                "row_count": 85
            }
        }
```

### MultiSheetContext

다중 시트 쿼리 컨텍스트.

```python
from pydantic import BaseModel, Field
from typing import Optional

class MultiSheetContext(BaseModel):
    """다중 시트 쿼리 컨텍스트"""

    question_type: str = Field(
        ...,
        description="질문 유형 (PERSON, PERIOD, EQUIPMENT, STATISTICS)"
    )
    selected_sheets: list[SheetSelection] = Field(
        default_factory=list,
        description="선택된 시트 목록"
    )
    common_columns: list[str] = Field(
        default_factory=list,
        description="모든 시트의 공통 컬럼"
    )
    use_union: bool = Field(
        default=False,
        description="UNION ALL 사용 여부"
    )
    union_strategy: str = Field(
        default="COMMON_COLUMNS",
        description="UNION 전략 (COMMON_COLUMNS, NULL_PADDING)"
    )

    @property
    def sheet_count(self) -> int:
        """선택된 시트 수"""
        return len(self.selected_sheets)

    @property
    def requires_union(self) -> bool:
        """UNION이 필요한지 여부"""
        return self.sheet_count > 1

    class Config:
        json_schema_extra = {
            "example": {
                "question_type": "PERSON",
                "selected_sheets": [
                    {"sheet_name": "Daily_20241217", "group_name": "TICKET_DAILY"},
                    {"sheet_name": "Daily_20241218", "group_name": "TICKET_DAILY"}
                ],
                "common_columns": ["날짜", "티켓번호", "담당자"],
                "use_union": True,
                "union_strategy": "COMMON_COLUMNS"
            }
        }
```

### UnionQueryResult

UNION 쿼리 결과.

```python
from pydantic import BaseModel, Field
from typing import Any, Optional

class SheetResultSummary(BaseModel):
    """시트별 결과 요약"""
    sheet_name: str
    row_count: int

class UnionQueryResult(BaseModel):
    """UNION 쿼리 결과"""

    success: bool = Field(..., description="쿼리 성공 여부")
    data: list[dict[str, Any]] = Field(
        default_factory=list,
        description="쿼리 결과 데이터"
    )
    total_rows: int = Field(default=0, description="총 행 수")
    sheet_summaries: list[SheetResultSummary] = Field(
        default_factory=list,
        description="시트별 결과 요약"
    )
    executed_sql: Optional[str] = Field(None, description="실행된 SQL")
    execution_time_ms: Optional[float] = Field(None, description="실행 시간 (ms)")
    error_message: Optional[str] = Field(None, description="에러 메시지")

    @property
    def sheets_queried(self) -> int:
        """쿼리된 시트 수"""
        return len(self.sheet_summaries)

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": [{"날짜": "2024-12-17", "담당자": "김철수"}],
                "total_rows": 150,
                "sheet_summaries": [
                    {"sheet_name": "Daily_20241217", "row_count": 85},
                    {"sheet_name": "Daily_20241218", "row_count": 65}
                ],
                "executed_sql": "SELECT ... UNION ALL ...",
                "execution_time_ms": 45.2
            }
        }
```

---

## Extended Models

### QueryContext (수정)

기존 QueryContext에 다중 시트 지원 필드 추가.

```python
# src/models/query.py 수정

class QueryContext(BaseModel):
    """쿼리 컨텍스트 (확장)"""

    # 기존 필드
    question: str
    excel_schema: ExcelSchema

    # 신규 필드
    multi_sheet_context: Optional[MultiSheetContext] = Field(
        None,
        description="다중 시트 컨텍스트"
    )

    @property
    def is_multi_sheet_query(self) -> bool:
        """다중 시트 쿼리 여부"""
        return (
            self.multi_sheet_context is not None
            and self.multi_sheet_context.requires_union
        )
```

### QueryResult (수정)

기존 QueryResult에 시트별 요약 추가.

```python
# src/models/query.py 수정

class QueryResult(BaseModel):
    """쿼리 결과 (확장)"""

    # 기존 필드
    success: bool
    data: list[dict[str, Any]]
    sql_query: str

    # 신규 필드
    sheet_summaries: list[SheetResultSummary] = Field(
        default_factory=list,
        description="시트별 결과 요약"
    )
    total_sheets_queried: int = Field(
        default=1,
        description="쿼리된 시트 수"
    )
```

---

## Configuration Model

### config.py 확장

```python
# src/config.py 수정

from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # 기존 설정...

    # 시트 그룹 설정
    sheet_group_patterns: dict[str, str] = {
        "TICKET_DAILY": r"^Daily_\d{8}$",
        "TICKET_WEEKLY": r"^Weekly_W\d{1,2}$",
        "TICKET_MONTHLY": r"^Monthly_",
        "EQUIPMENT": r"^Equipment_",
        "TEAM": r"^Team_"
    }

    # UNION 설정
    max_union_sheets: int = 10
    default_union_strategy: str = "COMMON_COLUMNS"

    # 질문 유형별 기본 시트 그룹
    question_type_sheet_groups: dict[str, list[str]] = {
        "PERSON": ["TICKET_DAILY", "TICKET_WEEKLY", "TICKET_MONTHLY"],
        "PERIOD": ["TICKET_DAILY", "TICKET_WEEKLY", "TICKET_MONTHLY"],
        "EQUIPMENT": ["EQUIPMENT", "TICKET_DAILY", "TICKET_WEEKLY"],
        "STATISTICS": ["TICKET_MONTHLY", "TICKET_WEEKLY"]
    }

    class Config:
        env_prefix = "TEXTTOSQL_"
```

---

## Enum Definitions

```python
from enum import Enum

class QuestionType(str, Enum):
    """질문 유형"""
    PERSON = "PERSON"           # 담당자 기반
    PERIOD = "PERIOD"           # 기간 기반
    EQUIPMENT = "EQUIPMENT"     # 설비 기반
    STATISTICS = "STATISTICS"   # 통계 기반
    UNKNOWN = "UNKNOWN"         # 분류 불가

class UnionStrategy(str, Enum):
    """UNION 전략"""
    COMMON_COLUMNS = "COMMON_COLUMNS"  # 공통 컬럼만 (기본)
    NULL_PADDING = "NULL_PADDING"      # NULL 패딩 (향후)

class SheetGroupName(str, Enum):
    """시트 그룹 이름"""
    TICKET_DAILY = "TICKET_DAILY"
    TICKET_WEEKLY = "TICKET_WEEKLY"
    TICKET_MONTHLY = "TICKET_MONTHLY"
    EQUIPMENT = "EQUIPMENT"
    TEAM = "TEAM"
    UNKNOWN = "UNKNOWN"
```

---

## File Location

```
src/models/
├── __init__.py          # 모델 re-export
├── schema.py            # 기존: ExcelSchema, SheetSchema, ColumnInfo
├── query.py             # 기존: QueryContext, QueryResult (확장)
└── sheet_group.py       # 신규: SheetGroup, SheetGroupConfig,
                         #       SheetSelection, MultiSheetContext,
                         #       UnionQueryResult, Enums
```

---

## Model Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                      SheetGroupConfig                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  SheetGroup  │  │  SheetGroup  │  │  SheetGroup  │ ...  │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ classifies
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    MultiSheetContext                        │
│  ┌────────────────────────────────────────────────────┐    │
│  │  selected_sheets: list[SheetSelection]              │    │
│  │  ┌───────────────┐  ┌───────────────┐              │    │
│  │  │ SheetSelection│  │ SheetSelection│  ...         │    │
│  │  └───────────────┘  └───────────────┘              │    │
│  └────────────────────────────────────────────────────┘    │
│  common_columns: list[str]                                  │
│  question_type: QuestionType                                │
│  union_strategy: UnionStrategy                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ produces
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    UnionQueryResult                         │
│  success: bool                                              │
│  data: list[dict]                                           │
│  sheet_summaries: list[SheetResultSummary]                  │
│  executed_sql: str                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Validation Rules

| 모델 | 필드 | 검증 규칙 |
|------|------|-----------|
| SheetGroup | pattern | 유효한 정규식 |
| SheetGroup | priority | 0 이상 정수 |
| SheetGroupConfig | max_union_sheets | 1-20 범위 |
| MultiSheetContext | selected_sheets | 비어있지 않음 |
| MultiSheetContext | common_columns | UNION 시 1개 이상 |
| UnionQueryResult | sheet_summaries | 합계 = total_rows |

---

## Usage Examples

### 시트 그룹 분류

```python
config = SheetGroupConfig(
    groups=[
        SheetGroup(
            name="TICKET_DAILY",
            pattern=r"^Daily_\d{8}$",
            union_compatible_with=["TICKET_WEEKLY", "TICKET_MONTHLY"]
        ),
        SheetGroup(
            name="TICKET_WEEKLY",
            pattern=r"^Weekly_W\d{1,2}$",
            union_compatible_with=["TICKET_DAILY", "TICKET_MONTHLY"]
        )
    ]
)

group = config.get_group("Daily_20241217")  # "TICKET_DAILY"
compatible = config.get_compatible_groups("TICKET_DAILY")
# ["TICKET_DAILY", "TICKET_WEEKLY", "TICKET_MONTHLY"]
```

### 다중 시트 컨텍스트 생성

```python
context = MultiSheetContext(
    question_type="PERSON",
    selected_sheets=[
        SheetSelection(sheet_name="Daily_20241217", group_name="TICKET_DAILY"),
        SheetSelection(sheet_name="Daily_20241218", group_name="TICKET_DAILY"),
    ],
    common_columns=["날짜", "티켓번호", "담당자", "작업내용", "상태"],
    use_union=True
)

assert context.requires_union == True
assert context.sheet_count == 2
```
