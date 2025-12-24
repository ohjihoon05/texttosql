# Quickstart: Multi-Sheet Query Support

**Branch**: `005-multi-sheet-query` | **Date**: 2024-12-24

## 5분 안에 시작하기

### 1. 새 파일 생성

```bash
# 모델 파일 생성
touch src/models/sheet_group.py

# 서비스 파일 생성
touch src/services/sheet_group_manager.py
```

### 2. 기본 모델 구현

```python
# src/models/sheet_group.py

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
import re

class QuestionType(str, Enum):
    PERSON = "PERSON"
    PERIOD = "PERIOD"
    EQUIPMENT = "EQUIPMENT"
    STATISTICS = "STATISTICS"
    UNKNOWN = "UNKNOWN"

class SheetGroup(BaseModel):
    name: str
    pattern: str
    union_compatible_with: list[str] = Field(default_factory=list)

    def matches(self, sheet_name: str) -> bool:
        return bool(re.match(self.pattern, sheet_name))

class SheetSelection(BaseModel):
    sheet_name: str
    group_name: str
    common_columns: list[str] = Field(default_factory=list)

class MultiSheetContext(BaseModel):
    question_type: str
    selected_sheets: list[SheetSelection] = Field(default_factory=list)
    common_columns: list[str] = Field(default_factory=list)
    use_union: bool = False

    @property
    def requires_union(self) -> bool:
        return len(self.selected_sheets) > 1
```

### 3. SheetGroupManager 기본 구현

```python
# src/services/sheet_group_manager.py

from models.sheet_group import SheetGroup, SheetSelection, MultiSheetContext
from models.schema import ExcelSchema
from config import settings

# 기본 시트 그룹 정의
DEFAULT_GROUPS = [
    SheetGroup(
        name="TICKET_DAILY",
        pattern=r"^Daily_\d{8}$",
        union_compatible_with=["TICKET_WEEKLY", "TICKET_MONTHLY"]
    ),
    SheetGroup(
        name="TICKET_WEEKLY",
        pattern=r"^Weekly_W\d{1,2}$",
        union_compatible_with=["TICKET_DAILY", "TICKET_MONTHLY"]
    ),
    SheetGroup(
        name="TICKET_MONTHLY",
        pattern=r"^Monthly_",
        union_compatible_with=["TICKET_DAILY", "TICKET_WEEKLY"]
    ),
]

class SheetGroupManager:
    def __init__(self, groups: list[SheetGroup] = None):
        self.groups = groups or DEFAULT_GROUPS

    def classify_sheet(self, sheet_name: str) -> str:
        """시트를 그룹으로 분류"""
        for group in self.groups:
            if group.matches(sheet_name):
                return group.name
        return "UNKNOWN"

    def find_common_columns(
        self,
        sheet_names: list[str],
        schema: ExcelSchema
    ) -> list[str]:
        """시트들의 공통 컬럼 찾기"""
        if not sheet_names:
            return []

        # 첫 시트의 컬럼으로 시작
        first_sheet = next(
            (s for s in schema.sheets if s.name == sheet_names[0]),
            None
        )
        if not first_sheet:
            return []

        common = set(col.name for col in first_sheet.columns)

        # 나머지 시트와 교집합
        for sheet_name in sheet_names[1:]:
            sheet = next(
                (s for s in schema.sheets if s.name == sheet_name),
                None
            )
            if sheet:
                sheet_cols = set(col.name for col in sheet.columns)
                common &= sheet_cols

        return list(common)

    def select_relevant_sheets(
        self,
        question: str,
        schema: ExcelSchema,
        max_sheets: int = 10
    ) -> list[SheetSelection]:
        """질문에 관련된 시트 선택"""
        # 간단한 구현: TICKET_* 그룹 시트 반환
        selections = []

        for sheet in schema.sheets:
            group = self.classify_sheet(sheet.name)
            if group.startswith("TICKET_"):
                selections.append(
                    SheetSelection(
                        sheet_name=sheet.name,
                        group_name=group
                    )
                )
                if len(selections) >= max_sheets:
                    break

        return selections
```

### 4. LLMRouter 확장

```python
# src/services/llm_router.py 에 추가

# Few-shot 예제
UNION_FEW_SHOT_EXAMPLES = [
    {
        "question": "김철수가 뭘 했어?",
        "sql": '''SELECT 날짜, 담당자, 작업내용, 상태
FROM "Daily_20241217"
UNION ALL
SELECT 날짜, 담당자, 작업내용, 상태
FROM "Daily_20241218"
WHERE 담당자 LIKE '%김철수%'
ORDER BY 날짜 DESC'''
    },
    {
        "question": "이번 주 작업 내역 알려줘",
        "sql": '''SELECT 날짜, 담당자, 작업유형, 작업내용
FROM "Weekly_W52"
UNION ALL
SELECT 날짜, 담당자, 작업유형, 작업내용
FROM "Daily_20241217"
WHERE 날짜 >= '2024-12-16'
ORDER BY 날짜'''
    },
]

UNION_SQL_PROMPT = """다음 시트들에서 UNION ALL을 사용하여 SQL을 생성하세요.

사용 가능한 시트: {sheet_names}
공통 컬럼: {common_columns}

규칙:
1. 모든 SELECT는 동일한 컬럼 순서
2. 시트 이름은 큰따옴표로 감싸기
3. WHERE 절은 마지막 UNION 뒤에만

예제:
{few_shot}

질문: {question}
SQL:"""
```

### 5. 설정 추가

```python
# src/config.py 에 추가

# 시트 그룹 설정
SHEET_GROUP_PATTERNS = {
    "TICKET_DAILY": r"^Daily_\d{8}$",
    "TICKET_WEEKLY": r"^Weekly_W\d{1,2}$",
    "TICKET_MONTHLY": r"^Monthly_",
    "EQUIPMENT": r"^Equipment_",
    "TEAM": r"^Team_"
}

# UNION 설정
MAX_UNION_SHEETS = 10
DEFAULT_UNION_STRATEGY = "COMMON_COLUMNS"
```

### 6. 빠른 테스트

```python
# tests/unit/test_sheet_group_manager.py

import pytest
from services.sheet_group_manager import SheetGroupManager

def test_classify_daily_sheet():
    manager = SheetGroupManager()
    assert manager.classify_sheet("Daily_20241217") == "TICKET_DAILY"

def test_classify_weekly_sheet():
    manager = SheetGroupManager()
    assert manager.classify_sheet("Weekly_W52") == "TICKET_WEEKLY"

def test_classify_unknown_sheet():
    manager = SheetGroupManager()
    assert manager.classify_sheet("RandomSheet") == "UNKNOWN"
```

```bash
# 테스트 실행
pytest tests/unit/test_sheet_group_manager.py -v
```

---

## 다음 단계

1. `/speckit.tasks` 실행하여 상세 태스크 생성
2. 또는 `/speckit.implement` 로 바로 구현 시작

---

## 주요 파일 위치

```
src/
├── models/
│   └── sheet_group.py          # 신규
├── services/
│   ├── sheet_group_manager.py  # 신규
│   ├── llm_router.py           # 수정
│   └── sql_agent.py            # 수정
└── config.py                   # 수정

tests/
└── unit/
    └── test_sheet_group_manager.py  # 신규
```

---

## 체크리스트

- [x] `sheet_group.py` 모델 생성
- [x] `sheet_group_manager.py` 서비스 생성
- [x] `config.py` 설정 추가
- [x] `llm_router.py` Few-shot 예제 추가
- [x] `sql_agent.py` SheetGroupManager 연동
- [x] 단위 테스트 작성 및 통과 (58개)
- [x] 통합 테스트 작성 및 통과 (43개)
- [x] query.py 모델 업데이트 (multi_sheet_context 필드)
