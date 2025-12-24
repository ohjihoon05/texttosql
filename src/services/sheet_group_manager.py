"""Sheet group management for multi-sheet queries.

This module provides the SheetGroupManager class for classifying sheets
into groups, finding common columns, and selecting relevant sheets
for UNION queries.
"""

import logging
import re
from functools import lru_cache
from typing import Optional

from src.config import (
    get_settings,
    SHEET_GROUP_PATTERNS,
    SHEET_GROUP_COMPATIBILITY,
    QUESTION_TYPE_SHEET_GROUPS,
)
from src.models.schema import ExcelSchema
from src.models.sheet_group import (
    QuestionType,
    SheetGroup,
    SheetGroupConfig,
    SheetSelection,
    MultiSheetContext,
    UnionStrategy,
)

logger = logging.getLogger(__name__)


class SheetGroupManager:
    """Manage sheet groups for multi-sheet query support.

    This class handles:
    - Sheet classification into logical groups (TICKET_DAILY, TICKET_WEEKLY, etc.)
    - Common column analysis across sheets
    - Relevant sheet selection based on question type
    - Multi-sheet context creation for UNION queries
    """

    def __init__(self, schema: Optional[ExcelSchema] = None):
        """Initialize SheetGroupManager.

        Args:
            schema: Optional ExcelSchema to use for sheet analysis
        """
        self.settings = get_settings()
        self._schema = schema
        self._sheet_groups: dict[str, list[str]] = {}
        self._group_config = self._build_group_config()

        # T053/FR-011: Initialize caching for metadata
        self._init_caches()

        if schema:
            self._classify_all_sheets()

    def _init_caches(self) -> None:
        """Initialize LRU caches for metadata (T053/FR-011).

        Creates cached versions of frequently called methods to improve
        performance when processing multiple queries on the same schema.
        """
        # Create cached functions with lru_cache
        @lru_cache(maxsize=128)
        def _cached_classify_sheet(sheet_name: str) -> str:
            return self._group_config.get_group(sheet_name)

        @lru_cache(maxsize=64)
        def _cached_find_common_columns(sheet_names_tuple: tuple[str, ...]) -> tuple[str, ...]:
            """Cache wrapper - converts list to tuple for hashability."""
            use_schema = self._schema
            if not use_schema:
                return ()

            if not sheet_names_tuple:
                return ()

            column_sets: list[set[str]] = []
            for sheet_name in sheet_names_tuple:
                sheet = use_schema.get_sheet(sheet_name)
                if sheet:
                    column_sets.append(set(sheet.column_names))

            if not column_sets:
                return ()

            common = column_sets[0]
            for cols in column_sets[1:]:
                common = common.intersection(cols)

            return tuple(sorted(list(common)))

        @lru_cache(maxsize=16)
        def _cached_required_columns(question_type_value: str) -> tuple[str, ...]:
            column_requirements = {
                "PERSON": ("담당자",),
                "PERIOD": ("날짜",),
                "EQUIPMENT": ("설비코드",),
                "STATISTICS": (),
                "UNKNOWN": (),
            }
            return column_requirements.get(question_type_value, ())

        self._cached_classify_sheet = _cached_classify_sheet
        self._cached_find_common_columns = _cached_find_common_columns
        self._cached_required_columns = _cached_required_columns

    def _clear_caches(self) -> None:
        """Clear all metadata caches (T053/FR-011).

        Called when schema changes to ensure stale data is not used.
        """
        if hasattr(self, '_cached_classify_sheet'):
            self._cached_classify_sheet.cache_clear()
        if hasattr(self, '_cached_find_common_columns'):
            self._cached_find_common_columns.cache_clear()
        if hasattr(self, '_cached_required_columns'):
            self._cached_required_columns.cache_clear()

        logger.debug("Cleared all metadata caches")

    def _build_group_config(self) -> SheetGroupConfig:
        """Build SheetGroupConfig from config patterns.

        Returns:
            SheetGroupConfig with all defined groups
        """
        groups = []
        for name, pattern in SHEET_GROUP_PATTERNS.items():
            compatible = SHEET_GROUP_COMPATIBILITY.get(name, [])
            groups.append(SheetGroup(
                name=name,
                pattern=pattern,
                union_compatible_with=compatible,
                priority=10 if "DAILY" in name else 5,  # Daily has higher priority
            ))

        return SheetGroupConfig(
            groups=groups,
            max_union_sheets=self.settings.max_union_sheets,
        )

    def set_schema(self, schema: ExcelSchema) -> None:
        """Set or update the Excel schema.

        Args:
            schema: ExcelSchema to use
        """
        self._schema = schema
        self._sheet_groups.clear()
        # T053/FR-011: Clear caches on schema change
        self._clear_caches()
        self._classify_all_sheets()

    def _classify_all_sheets(self) -> None:
        """Classify all sheets in the schema into groups."""
        if not self._schema:
            return

        for sheet_name in self._schema.sheet_names:
            group_name = self.classify_sheet(sheet_name)
            if group_name not in self._sheet_groups:
                self._sheet_groups[group_name] = []
            self._sheet_groups[group_name].append(sheet_name)

        logger.info(f"Classified {len(self._schema.sheet_names)} sheets into {len(self._sheet_groups)} groups")

    def classify_sheet(self, sheet_name: str) -> str:
        """Classify a sheet into a group.

        Uses LRU cache for performance (T053/FR-011).
        Access cache_info via manager.classify_sheet.cache_info()

        Args:
            sheet_name: Sheet name to classify

        Returns:
            Group name (e.g., "TICKET_DAILY")

        Raises:
            ValueError: If sheet_name is empty
        """
        if not sheet_name:
            raise ValueError("Sheet name cannot be empty")

        # T053/FR-011: Use cached version
        return self._cached_classify_sheet(sheet_name)

    def get_sheets_by_group(self, group_name: str) -> list[str]:
        """Get all sheets belonging to a group.

        Args:
            group_name: Group name to query

        Returns:
            List of sheet names in the group
        """
        return self._sheet_groups.get(group_name, [])

    def find_common_columns(
        self,
        sheet_names: list[str],
        schema: Optional[ExcelSchema] = None
    ) -> list[str]:
        """Find columns common to all specified sheets.

        Uses LRU cache for performance when using instance schema (T053/FR-011).

        Args:
            sheet_names: List of sheet names to analyze
            schema: Optional schema (uses instance schema if not provided)

        Returns:
            List of common column names

        Raises:
            ValueError: If no common columns found or sheets don't exist
        """
        use_schema = schema or self._schema
        if not use_schema:
            raise ValueError("No schema available")

        if not sheet_names:
            return []

        # T053/FR-011: Use cached version when using instance schema
        if schema is None and self._schema is not None:
            # Convert to tuple for hashability
            sheet_names_tuple = tuple(sheet_names)
            result_tuple = self._cached_find_common_columns(sheet_names_tuple)
            return list(result_tuple)

        # Non-cached path for external schema
        column_sets: list[set[str]] = []
        for sheet_name in sheet_names:
            sheet = use_schema.get_sheet(sheet_name)
            if sheet:
                column_sets.append(set(sheet.column_names))
            else:
                logger.warning(f"Sheet '{sheet_name}' not found in schema")

        if not column_sets:
            return []

        # Find intersection of all column sets
        common = column_sets[0]
        for cols in column_sets[1:]:
            common = common.intersection(cols)

        result = sorted(list(common))
        logger.debug(f"Found {len(result)} common columns across {len(sheet_names)} sheets")

        return result

    def get_compatible_sheets(self, sheet_name: str) -> list[str]:
        """Get sheets that are UNION-compatible with given sheet.

        Args:
            sheet_name: Reference sheet name

        Returns:
            List of compatible sheet names
        """
        group_name = self.classify_sheet(sheet_name)
        compatible_groups = self._group_config.get_compatible_groups(group_name)

        result = []
        for group in compatible_groups:
            result.extend(self.get_sheets_by_group(group))

        return result

    def _detect_question_type(self, question: str) -> QuestionType:
        """Detect question type from natural language question.

        Args:
            question: User's natural language question

        Returns:
            QuestionType enum value

        Note:
            Detection priority: PERIOD (keywords) > PERSON > EQUIPMENT > STATISTICS > UNKNOWN
            PERIOD keywords are checked first to avoid false positives like "이번주" matching
            as a Korean name (이+번주).
        """
        question_lower = question.lower()

        # PERIOD detection FIRST: date/time related keywords
        # Must be checked before PERSON to prevent "이번주" from matching as name "이번주"
        period_keywords = [
            "이번 주", "저번 주", "지난주", "이번주", "금주",
            "오늘", "어제", "내일",
            "이번 달", "저번 달", "지난달", "이번달",
            "기간", "날짜",
        ]
        # Date patterns: YYYY-MM-DD, MM월, N주, N일
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # 2024-12-17
            r'\d{1,2}월\s*\d{1,2}일',  # 12월 17일
            r'\d{1,2}월',          # 12월
            r'\d{1,2}주',          # 52주
        ]

        for keyword in period_keywords:
            if keyword in question_lower or keyword in question:
                return QuestionType.PERIOD

        for pattern in date_patterns:
            if re.search(pattern, question):
                return QuestionType.PERIOD

        # PERSON detection: Korean names or person-related keywords
        person_keywords = ["담당자별", "담당자가", "담당자는", "누가", "누구"]

        for keyword in person_keywords:
            if keyword in question:
                return QuestionType.PERSON

        # Korean name patterns - must be specific enough to not match common words
        # Common Korean surnames: 김, 이, 박, 최, 정, 강, 조, 윤, 장, 임
        # Pattern: Surname (1 char) + Given name (2 chars) + optional particle
        korean_surnames = "김이박최정강조윤장임한오서신권황안송류홍"
        name_pattern = rf'[{korean_surnames}][가-힣]{{2}}(?:가|이|는|의|씨|님|을|를)?'

        if re.search(name_pattern, question):
            return QuestionType.PERSON

        # Name followed by action words (more restrictive)
        name_action_pattern = rf'[{korean_surnames}][가-힣]{{2}}\s+(?:작업|업무|담당)'
        if re.search(name_action_pattern, question):
            return QuestionType.PERSON

        # EQUIPMENT detection: equipment-related keywords
        equipment_keywords = ["설비", "장비", "CVD", "PVD", "ETCH", "CMP", "설비코드", "설비명"]

        for keyword in equipment_keywords:
            if keyword in question or keyword.lower() in question_lower:
                return QuestionType.EQUIPMENT

        # STATISTICS detection: aggregate/count related keywords
        statistics_keywords = ["총", "몇 건", "몇건", "평균", "합계", "개수", "건수", "통계"]

        for keyword in statistics_keywords:
            if keyword in question:
                return QuestionType.STATISTICS

        return QuestionType.UNKNOWN

    def select_relevant_sheets(
        self,
        question: str,
        schema: Optional[ExcelSchema] = None
    ) -> list[SheetSelection]:
        """Select relevant sheets based on question.

        Args:
            question: User's natural language question
            schema: Optional schema (uses instance schema if not provided)

        Returns:
            List of SheetSelection objects

        Raises:
            ValueError: If no schema available
        """
        use_schema = schema or self._schema
        if not use_schema:
            raise ValueError("No schema available")

        question_type = self._detect_question_type(question)
        target_groups = QUESTION_TYPE_SHEET_GROUPS.get(
            question_type.value,
            ["TICKET_DAILY", "TICKET_WEEKLY", "TICKET_MONTHLY"]
        )

        # Collect all sheets from target groups
        candidate_sheets: list[str] = []
        for group_name in target_groups:
            candidate_sheets.extend(self.get_sheets_by_group(group_name))

        # Filter sheets that have required columns for the question type
        required_columns = self._get_required_columns_for_type(question_type)
        valid_sheets: list[str] = []

        for sheet_name in candidate_sheets:
            sheet = use_schema.get_sheet(sheet_name)
            if sheet and all(col in sheet.column_names for col in required_columns):
                valid_sheets.append(sheet_name)

        # Sort by priority (Daily first, then Weekly, then Monthly)
        valid_sheets = self._sort_sheets_by_priority(valid_sheets)

        # Limit to max_union_sheets
        limited_sheets = valid_sheets[:self.settings.max_union_sheets]

        # Create SheetSelection objects
        selections: list[SheetSelection] = []
        for sheet_name in limited_sheets:
            sheet = use_schema.get_sheet(sheet_name)
            group_name = self.classify_sheet(sheet_name)
            selections.append(SheetSelection(
                sheet_name=sheet_name,
                group_name=group_name,
                row_count=sheet.row_count if sheet else None,
            ))

        logger.info(
            f"Selected {len(selections)} sheets for {question_type.value} query"
        )

        return selections

    def _get_required_columns_for_type(self, question_type: QuestionType) -> list[str]:
        """Get required columns for a question type.

        Uses LRU cache for performance (T053/FR-011).

        Args:
            question_type: The question type

        Returns:
            List of required column names
        """
        # T053/FR-011: Use cached version (pass string for hashability)
        result_tuple = self._cached_required_columns(question_type.value)
        return list(result_tuple)

    def _sort_sheets_by_priority(self, sheets: list[str]) -> list[str]:
        """Sort sheets by priority (Daily > Weekly > Monthly).

        Args:
            sheets: List of sheet names

        Returns:
            Sorted list of sheet names
        """
        def get_priority(sheet_name: str) -> int:
            if sheet_name.startswith("Daily"):
                return 0
            elif sheet_name.startswith("Weekly"):
                return 1
            elif sheet_name.startswith("Monthly"):
                return 2
            else:
                return 3

        return sorted(sheets, key=get_priority)

    def create_multi_sheet_context(
        self,
        question: str,
        schema: Optional[ExcelSchema] = None
    ) -> MultiSheetContext:
        """Create multi-sheet query context.

        Args:
            question: User's natural language question
            schema: Optional schema (uses instance schema if not provided)

        Returns:
            MultiSheetContext with selected sheets and common columns

        Raises:
            ValueError: If no schema available
        """
        use_schema = schema or self._schema
        if not use_schema:
            raise ValueError("No schema available")

        question_type = self._detect_question_type(question)
        selected_sheets = self.select_relevant_sheets(question, use_schema)

        # Find common columns across selected sheets
        sheet_names = [s.sheet_name for s in selected_sheets]
        common_columns = self.find_common_columns(sheet_names, use_schema)

        # Update selections with common columns
        for selection in selected_sheets:
            selection.common_columns = common_columns

        # Determine if UNION is needed
        use_union = len(selected_sheets) > 1

        # Get union strategy from settings
        strategy = UnionStrategy.COMMON_COLUMNS
        if self.settings.default_union_strategy == "NULL_PADDING":
            strategy = UnionStrategy.NULL_PADDING

        context = MultiSheetContext(
            question_type=question_type,
            selected_sheets=selected_sheets,
            common_columns=common_columns,
            use_union=use_union,
            union_strategy=strategy,
        )

        logger.info(
            f"Created multi-sheet context: {len(selected_sheets)} sheets, "
            f"{len(common_columns)} common columns, use_union={use_union}"
        )

        return context

    def extract_period_info(self, question: str) -> dict[str, str | None]:
        """Extract date/period information from question.

        Parses Korean natural language date expressions and converts them
        to structured period information for SQL WHERE clause generation.

        Args:
            question: User's natural language question

        Returns:
            Dictionary with period information:
            - period_type: "week" | "month" | "day" | "date_range" | None
            - start_date: ISO format date string or None
            - end_date: ISO format date string or None
            - relative: "this" | "last" | "next" | None
            - raw_expression: Original matched expression or None

        Examples:
            "이번 주 완료된 티켓" -> {"period_type": "week", "relative": "this", ...}
            "12월 작업 현황" -> {"period_type": "month", "raw_expression": "12월", ...}
            "2024-12-17 티켓" -> {"period_type": "date_range", "start_date": "2024-12-17", ...}
        """
        from datetime import datetime, timedelta

        result: dict[str, str | None] = {
            "period_type": None,
            "start_date": None,
            "end_date": None,
            "relative": None,
            "raw_expression": None,
        }

        today = datetime.now()

        # Relative week expressions
        week_patterns = {
            r"이번\s*주": ("week", "this"),
            r"금주": ("week", "this"),
            r"저번\s*주": ("week", "last"),
            r"지난\s*주": ("week", "last"),
            r"다음\s*주": ("week", "next"),
        }

        for pattern, (period_type, relative) in week_patterns.items():
            match = re.search(pattern, question)
            if match:
                result["period_type"] = period_type
                result["relative"] = relative
                result["raw_expression"] = match.group()

                # Calculate week dates
                if relative == "this":
                    start = today - timedelta(days=today.weekday())
                    end = start + timedelta(days=6)
                elif relative == "last":
                    start = today - timedelta(days=today.weekday() + 7)
                    end = start + timedelta(days=6)
                else:  # next
                    start = today + timedelta(days=7 - today.weekday())
                    end = start + timedelta(days=6)

                result["start_date"] = start.strftime("%Y-%m-%d")
                result["end_date"] = end.strftime("%Y-%m-%d")
                return result

        # Relative month expressions
        month_patterns = {
            r"이번\s*달": ("month", "this"),
            r"이번달": ("month", "this"),
            r"저번\s*달": ("month", "last"),
            r"지난\s*달": ("month", "last"),
            r"지난달": ("month", "last"),
            r"다음\s*달": ("month", "next"),
        }

        for pattern, (period_type, relative) in month_patterns.items():
            match = re.search(pattern, question)
            if match:
                result["period_type"] = period_type
                result["relative"] = relative
                result["raw_expression"] = match.group()

                # Calculate month dates
                if relative == "this":
                    start = today.replace(day=1)
                    # End of this month
                    if today.month == 12:
                        end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
                    else:
                        end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
                elif relative == "last":
                    start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
                    end = today.replace(day=1) - timedelta(days=1)
                else:  # next
                    if today.month == 12:
                        start = today.replace(year=today.year + 1, month=1, day=1)
                        end = today.replace(year=today.year + 1, month=2, day=1) - timedelta(days=1)
                    else:
                        start = today.replace(month=today.month + 1, day=1)
                        if today.month + 1 == 12:
                            end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
                        else:
                            end = today.replace(month=today.month + 2, day=1) - timedelta(days=1)

                result["start_date"] = start.strftime("%Y-%m-%d")
                result["end_date"] = end.strftime("%Y-%m-%d")
                return result

        # Relative day expressions
        day_patterns = {
            r"오늘": ("day", "this"),
            r"어제": ("day", "last"),
            r"내일": ("day", "next"),
        }

        for pattern, (period_type, relative) in day_patterns.items():
            match = re.search(pattern, question)
            if match:
                result["period_type"] = period_type
                result["relative"] = relative
                result["raw_expression"] = match.group()

                if relative == "this":
                    target_date = today
                elif relative == "last":
                    target_date = today - timedelta(days=1)
                else:  # next
                    target_date = today + timedelta(days=1)

                date_str = target_date.strftime("%Y-%m-%d")
                result["start_date"] = date_str
                result["end_date"] = date_str
                return result

        # Specific date pattern: YYYY-MM-DD
        date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", question)
        if date_match:
            result["period_type"] = "date_range"
            result["raw_expression"] = date_match.group()
            result["start_date"] = date_match.group()
            result["end_date"] = date_match.group()
            return result

        # Specific month pattern: N월 (without day)
        month_match = re.search(r"(\d{1,2})월(?!\s*\d{1,2}일)", question)
        if month_match:
            month_num = int(month_match.group(1))
            if 1 <= month_num <= 12:
                result["period_type"] = "month"
                result["raw_expression"] = month_match.group()
                # Assume current year
                year = today.year
                # If month is in the future of current month, might be last year
                if month_num > today.month:
                    # Could be either this year (future) or last year - default to this year
                    pass
                start = datetime(year, month_num, 1)
                if month_num == 12:
                    end = datetime(year + 1, 1, 1) - timedelta(days=1)
                else:
                    end = datetime(year, month_num + 1, 1) - timedelta(days=1)
                result["start_date"] = start.strftime("%Y-%m-%d")
                result["end_date"] = end.strftime("%Y-%m-%d")
                return result

        # Specific date pattern: M월 D일
        date_md_match = re.search(r"(\d{1,2})월\s*(\d{1,2})일", question)
        if date_md_match:
            month_num = int(date_md_match.group(1))
            day_num = int(date_md_match.group(2))
            if 1 <= month_num <= 12 and 1 <= day_num <= 31:
                result["period_type"] = "date_range"
                result["raw_expression"] = date_md_match.group()
                year = today.year
                try:
                    target_date = datetime(year, month_num, day_num)
                    date_str = target_date.strftime("%Y-%m-%d")
                    result["start_date"] = date_str
                    result["end_date"] = date_str
                    return result
                except ValueError:
                    # Invalid date (e.g., Feb 30)
                    pass

        # Week number pattern: N주
        week_match = re.search(r"(\d{1,2})주", question)
        if week_match:
            week_num = int(week_match.group(1))
            if 1 <= week_num <= 53:
                result["period_type"] = "week"
                result["raw_expression"] = week_match.group()
                # Calculate week start/end for the current year
                year = today.year
                # ISO week 1 is the week containing Jan 4th
                jan4 = datetime(year, 1, 4)
                week1_start = jan4 - timedelta(days=jan4.weekday())
                start = week1_start + timedelta(weeks=week_num - 1)
                end = start + timedelta(days=6)
                result["start_date"] = start.strftime("%Y-%m-%d")
                result["end_date"] = end.strftime("%Y-%m-%d")
                return result

        return result

    def extract_equipment_info(self, question: str) -> dict[str, str | list[str] | None]:
        """Extract equipment code/name information from question.

        Parses equipment-related keywords and codes from the question
        for SQL WHERE clause generation.

        Args:
            question: User's natural language question

        Returns:
            Dictionary with equipment information:
            - equipment_codes: List of detected equipment codes (CVD, PVD, etc.)
            - equipment_pattern: Pattern for LIKE query or None
            - fault_type: Type of fault mentioned (고장, 점검, 정비, etc.) or None
            - raw_expression: Original matched expression or None

        Examples:
            "CVD 설비 고장 이력" -> {"equipment_codes": ["CVD"], "fault_type": "고장", ...}
            "PVD-001 장비 점검" -> {"equipment_codes": ["PVD"], "equipment_pattern": "PVD-001", ...}
        """
        import re

        result: dict[str, str | list[str] | None] = {
            "equipment_codes": None,
            "equipment_pattern": None,
            "fault_type": None,
            "raw_expression": None,
        }

        question_upper = question.upper()

        # Standard semiconductor equipment codes
        equipment_codes = ["CVD", "PVD", "ETCH", "CMP", "DIFF", "IMP", "LITHO", "PHOTO", "CLEAN"]
        detected_codes: list[str] = []

        for code in equipment_codes:
            if code in question_upper:
                detected_codes.append(code)

        if detected_codes:
            result["equipment_codes"] = detected_codes
            # Try to find specific equipment pattern (e.g., CVD-001, PVD_002)
            pattern_match = re.search(
                r"(" + "|".join(detected_codes) + r")[-_]?(\d{1,3})",
                question_upper
            )
            if pattern_match:
                result["equipment_pattern"] = pattern_match.group()
                result["raw_expression"] = pattern_match.group()
            else:
                result["raw_expression"] = detected_codes[0]

        # Detect fault/maintenance type
        fault_types = {
            "고장": "고장",
            "오류": "고장",
            "장애": "고장",
            "점검": "점검",
            "정비": "정비",
            "유지보수": "정비",
            "수리": "정비",
        }

        for keyword, fault_type in fault_types.items():
            if keyword in question:
                result["fault_type"] = fault_type
                break

        return result
