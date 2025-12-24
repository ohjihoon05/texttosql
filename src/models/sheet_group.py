"""Multi-sheet query models for Text-to-SQL system.

This module provides Pydantic models for sheet grouping, multi-sheet context,
and UNION query result handling.
"""

from enum import Enum
from typing import Any, Optional
import re

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """Question type classification for sheet selection."""

    PERSON = "PERSON"  # 담당자 기반 (김철수가 뭘 했어?)
    PERIOD = "PERIOD"  # 기간 기반 (이번 주 완료된 티켓)
    EQUIPMENT = "EQUIPMENT"  # 설비 기반 (CVD 설비 고장 이력)
    STATISTICS = "STATISTICS"  # 통계 기반 (몇 건, 총, 평균)
    UNKNOWN = "UNKNOWN"  # 분류 불가


class UnionStrategy(str, Enum):
    """UNION query strategy."""

    COMMON_COLUMNS = "COMMON_COLUMNS"  # 공통 컬럼만 사용 (기본)
    NULL_PADDING = "NULL_PADDING"  # NULL 패딩으로 모든 컬럼 유지 (향후)


class SheetGroup(BaseModel):
    """Sheet group definition model.

    Defines a logical group of sheets that can be queried together
    using UNION ALL.
    """

    name: str = Field(..., description="그룹 이름 (예: TICKET_DAILY)")
    pattern: str = Field(..., description="시트 이름 정규식 패턴")
    description: Optional[str] = Field(None, description="그룹 설명")
    union_compatible_with: list[str] = Field(
        default_factory=list,
        description="UNION 가능한 그룹 목록"
    )
    priority: int = Field(
        default=0,
        ge=0,
        description="시트 선택 우선순위 (높을수록 우선)"
    )

    def matches(self, sheet_name: str) -> bool:
        """Check if sheet name matches this group's pattern.

        Args:
            sheet_name: Sheet name to check

        Returns:
            True if sheet name matches pattern
        """
        try:
            return bool(re.match(self.pattern, sheet_name))
        except re.error:
            return False

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "TICKET_DAILY",
                "pattern": r"^Daily_\d{8}$",
                "description": "일일 티켓 시트",
                "union_compatible_with": ["TICKET_WEEKLY", "TICKET_MONTHLY"],
                "priority": 10
            }
        }
    }


class SheetGroupConfig(BaseModel):
    """Sheet group configuration model.

    Manages multiple sheet groups and provides group lookup functionality.
    """

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
        """Get group name for a sheet.

        Args:
            sheet_name: Sheet name to classify

        Returns:
            Group name (or default_group if no match)
        """
        # Sort by priority descending
        for group in sorted(self.groups, key=lambda g: -g.priority):
            if group.matches(sheet_name):
                return group.name
        return self.default_group

    def get_compatible_groups(self, group_name: str) -> list[str]:
        """Get list of UNION-compatible groups.

        Args:
            group_name: Base group name

        Returns:
            List of compatible group names (including self)
        """
        for group in self.groups:
            if group.name == group_name:
                return [group_name] + group.union_compatible_with
        return [group_name]

    def get_group_definition(self, group_name: str) -> Optional[SheetGroup]:
        """Get SheetGroup definition by name.

        Args:
            group_name: Group name to find

        Returns:
            SheetGroup if found, None otherwise
        """
        for group in self.groups:
            if group.name == group_name:
                return group
        return None


class SheetSelection(BaseModel):
    """Selected sheet information for multi-sheet query."""

    sheet_name: str = Field(..., description="시트 이름")
    group_name: str = Field(..., description="속한 그룹 이름")
    common_columns: list[str] = Field(
        default_factory=list,
        description="공통 컬럼 목록"
    )
    row_count: Optional[int] = Field(None, description="예상 행 수")

    model_config = {
        "json_schema_extra": {
            "example": {
                "sheet_name": "Daily_20241217",
                "group_name": "TICKET_DAILY",
                "common_columns": ["날짜", "티켓번호", "담당자", "상태"],
                "row_count": 85
            }
        }
    }


class MultiSheetContext(BaseModel):
    """Multi-sheet query context.

    Contains all information needed to generate and execute
    a UNION ALL query across multiple sheets.
    """

    question_type: QuestionType = Field(
        ...,
        description="질문 유형"
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
    union_strategy: UnionStrategy = Field(
        default=UnionStrategy.COMMON_COLUMNS,
        description="UNION 전략"
    )

    @property
    def sheet_count(self) -> int:
        """Get number of selected sheets."""
        return len(self.selected_sheets)

    @property
    def requires_union(self) -> bool:
        """Check if UNION is needed (more than 1 sheet)."""
        return self.sheet_count > 1

    @property
    def sheet_names(self) -> list[str]:
        """Get list of selected sheet names."""
        return [s.sheet_name for s in self.selected_sheets]

    model_config = {
        "json_schema_extra": {
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
    }


class SheetResultSummary(BaseModel):
    """Per-sheet result summary."""

    sheet_name: str = Field(..., description="시트 이름")
    row_count: int = Field(default=0, ge=0, description="해당 시트 결과 건수")
    matched: bool = Field(default=False, description="결과 포함 여부")


class UnionQueryResult(BaseModel):
    """UNION query result with per-sheet breakdown."""

    success: bool = Field(..., description="쿼리 성공 여부")
    data: list[dict[str, Any]] = Field(
        default_factory=list,
        description="쿼리 결과 데이터"
    )
    total_rows: int = Field(default=0, ge=0, description="총 행 수")
    sheet_summaries: list[SheetResultSummary] = Field(
        default_factory=list,
        description="시트별 결과 요약"
    )
    executed_sql: Optional[str] = Field(None, description="실행된 SQL")
    execution_time_ms: Optional[float] = Field(None, ge=0, description="실행 시간 (ms)")
    error_message: Optional[str] = Field(None, description="에러 메시지")

    @property
    def sheets_queried(self) -> int:
        """Get number of sheets queried."""
        return len(self.sheet_summaries)

    @property
    def is_empty(self) -> bool:
        """Check if result has no data."""
        return self.total_rows == 0

    model_config = {
        "json_schema_extra": {
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
    }
