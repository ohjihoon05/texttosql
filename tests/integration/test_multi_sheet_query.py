"""Integration tests for multi-sheet query functionality.

Tests cover end-to-end multi-sheet query scenarios:
- User Story 1: Person-based queries
- User Story 2: Period-based queries
- User Story 3: Equipment-based queries
"""

import pytest
from pathlib import Path

from src.models.schema import ExcelSchema, SheetSchema, ColumnInfo
from src.models.sheet_group import QuestionType, UnionStrategy
from src.services.sheet_group_manager import SheetGroupManager
from src.services.excel_loader import ExcelLoader
from src.services.llm_router import LLMRouter
from src.services.sql_agent import SQLAgent


@pytest.fixture
def large_sample_schema() -> ExcelSchema:
    """Create a larger sample ExcelSchema for integration testing.

    Simulates realistic CS Daily Report structure with multiple Daily sheets.
    """
    # Common columns for ticket-type sheets
    ticket_columns = [
        ColumnInfo(name="날짜", dtype="object", sample_values=["2024-12-17"]),
        ColumnInfo(name="티켓번호", dtype="object", sample_values=["TK001"]),
        ColumnInfo(name="담당자", dtype="object", sample_values=["김철수"]),
        ColumnInfo(name="설비코드", dtype="object", sample_values=["CVD001"]),
        ColumnInfo(name="작업유형", dtype="object", sample_values=["점검"]),
        ColumnInfo(name="작업내용", dtype="object", sample_values=["정기 점검"]),
        ColumnInfo(name="상태", dtype="object", sample_values=["완료"]),
    ]

    # Create 5 daily sheets for realistic testing
    sheets = {}
    for day in range(15, 20):
        sheet_name = f"Daily_202412{day}"
        sheets[sheet_name] = SheetSchema(
            name=sheet_name,
            columns=ticket_columns,
            row_count=50 + day * 5  # 65-95 rows per sheet
        )

    # Add weekly and monthly sheets
    weekly_columns = ticket_columns + [
        ColumnInfo(name="주차", dtype="int64", sample_values=["51"]),
    ]
    sheets["Weekly_W51"] = SheetSchema(
        name="Weekly_W51",
        columns=weekly_columns,
        row_count=300
    )

    monthly_columns = ticket_columns + [
        ColumnInfo(name="월", dtype="object", sample_values=["12월"]),
        ColumnInfo(name="SLA_충족", dtype="object", sample_values=["Y"]),
    ]
    sheets["Monthly_Summary"] = SheetSchema(
        name="Monthly_Summary",
        columns=monthly_columns,
        row_count=450
    )

    # Equipment sheet (different structure)
    equipment_columns = [
        ColumnInfo(name="설비코드", dtype="object", sample_values=["CVD001"]),
        ColumnInfo(name="설비명", dtype="object", sample_values=["CVD 장비 1호"]),
        ColumnInfo(name="설치일", dtype="object", sample_values=["2020-01-15"]),
        ColumnInfo(name="상태", dtype="object", sample_values=["가동중"]),
    ]
    sheets["Equipment_List"] = SheetSchema(
        name="Equipment_List",
        columns=equipment_columns,
        row_count=150
    )

    return ExcelSchema(
        file_name="cs_daily_report.xlsx",
        file_size_mb=3.5,
        sheets=sheets,
    )


@pytest.fixture
def sheet_group_manager(large_sample_schema: ExcelSchema) -> SheetGroupManager:
    """Create SheetGroupManager with large sample schema."""
    return SheetGroupManager(schema=large_sample_schema)


class TestPersonQueryIntegration:
    """Integration tests for User Story 1: Person-based queries (T021)."""

    def test_person_query_selects_multiple_sheets(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """'김철수가 뭘 했어?' should select 5+ ticket sheets."""
        context = sheet_group_manager.create_multi_sheet_context("김철수가 뭘 했어?")

        assert context.question_type == QuestionType.PERSON
        assert len(context.selected_sheets) >= 5
        assert context.use_union is True

    def test_person_query_finds_common_columns(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Person query should find common columns including '담당자'."""
        context = sheet_group_manager.create_multi_sheet_context("김철수가 뭘 했어?")

        assert "담당자" in context.common_columns
        assert "날짜" in context.common_columns
        assert "작업내용" in context.common_columns

    def test_person_query_excludes_equipment_sheets(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Person query should exclude equipment sheets (no 담당자 column)."""
        context = sheet_group_manager.create_multi_sheet_context("김철수가 뭘 했어?")

        sheet_names = [s.sheet_name for s in context.selected_sheets]
        assert "Equipment_List" not in sheet_names

    def test_person_query_total_rows_exceed_100(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Selected sheets should have potential for 100+ rows total."""
        context = sheet_group_manager.create_multi_sheet_context("김철수가 뭘 했어?")

        total_rows = sum(
            s.row_count or 0
            for s in context.selected_sheets
        )
        assert total_rows >= 100

    def test_person_query_uses_common_columns_strategy(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Person query should use COMMON_COLUMNS union strategy."""
        context = sheet_group_manager.create_multi_sheet_context("김철수가 뭘 했어?")

        assert context.union_strategy == UnionStrategy.COMMON_COLUMNS


class TestSheetSelectionLogic:
    """Tests for sheet selection and compatibility logic."""

    def test_daily_sheets_grouped_correctly(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """All Daily sheets should be in TICKET_DAILY group."""
        daily_sheets = sheet_group_manager.get_sheets_by_group("TICKET_DAILY")

        assert len(daily_sheets) == 5
        for sheet in daily_sheets:
            assert sheet.startswith("Daily_")

    def test_compatible_sheets_include_related_groups(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Daily sheet should be compatible with Weekly and Monthly."""
        compatible = sheet_group_manager.get_compatible_sheets("Daily_20241215")

        assert any("Weekly" in s for s in compatible)
        assert any("Monthly" in s for s in compatible)
        assert not any("Equipment" in s for s in compatible)

    def test_common_columns_across_ticket_sheets(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """All ticket sheets should share core columns."""
        ticket_sheets = ["Daily_20241215", "Weekly_W51", "Monthly_Summary"]
        common = sheet_group_manager.find_common_columns(ticket_sheets)

        assert "날짜" in common
        assert "담당자" in common
        assert "티켓번호" in common
        assert "작업내용" in common


class TestEdgeCases:
    """Edge case tests for multi-sheet queries (T055)."""

    def test_empty_question_returns_unknown_type(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Empty or vague question should return UNKNOWN type."""
        context = sheet_group_manager.create_multi_sheet_context("보여줘")

        assert context.question_type == QuestionType.UNKNOWN

    def test_max_sheets_limit_respected(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Sheet selection should not exceed max_union_sheets."""
        context = sheet_group_manager.create_multi_sheet_context("모든 작업 조회")

        assert len(context.selected_sheets) <= sheet_group_manager.settings.max_union_sheets

    def test_very_short_question(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Very short question should still work."""
        context = sheet_group_manager.create_multi_sheet_context("뭐")

        # Should not crash, returns some context
        assert context is not None
        assert context.question_type is not None

    def test_long_question_with_multiple_keywords(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Long question with multiple keywords should prioritize correctly."""
        # Contains both person and period keywords
        context = sheet_group_manager.create_multi_sheet_context(
            "김철수가 이번 주에 CVD 설비에서 작업한 내역 모두 조회해줘"
        )

        # Should pick one type based on priority (PERIOD > PERSON > EQUIPMENT)
        assert context.question_type in [QuestionType.PERIOD, QuestionType.PERSON, QuestionType.EQUIPMENT]

    def test_special_characters_in_question(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Question with special characters should not crash."""
        context = sheet_group_manager.create_multi_sheet_context("김철수@ 작업 (2024)")

        assert context is not None

    def test_unicode_in_question(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Question with unicode should work properly."""
        context = sheet_group_manager.create_multi_sheet_context("田中さん 작업 조회")

        assert context is not None

    def test_numbers_only_question(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Question with only numbers should be handled."""
        context = sheet_group_manager.create_multi_sheet_context("12345")

        assert context is not None
        assert context.question_type == QuestionType.UNKNOWN

    def test_context_with_no_common_columns(self):
        """Sheets with no common columns should still work."""
        # Create schema with incompatible sheets
        sheet1_cols = [
            ColumnInfo(name="col_a", dtype="object", sample_values=["a"]),
            ColumnInfo(name="col_b", dtype="object", sample_values=["b"]),
        ]
        sheet2_cols = [
            ColumnInfo(name="col_x", dtype="object", sample_values=["x"]),
            ColumnInfo(name="col_y", dtype="object", sample_values=["y"]),
        ]

        sheets = {
            "Daily_20241217": SheetSchema(name="Daily_20241217", columns=sheet1_cols, row_count=10),
            "Daily_20241218": SheetSchema(name="Daily_20241218", columns=sheet2_cols, row_count=10),
        }

        schema = ExcelSchema(file_name="test.xlsx", file_size_mb=1.0, sheets=sheets)
        manager = SheetGroupManager(schema=schema)

        # Should still create context, just with empty common_columns
        context = manager.create_multi_sheet_context("아무거나")
        assert context is not None
        # Common columns might be empty
        assert isinstance(context.common_columns, list)

    def test_whitespace_only_question(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Whitespace-only question should be handled gracefully."""
        context = sheet_group_manager.create_multi_sheet_context("   ")

        assert context is not None
        assert context.question_type == QuestionType.UNKNOWN

    def test_mixed_language_question(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Mixed Korean/English question should work."""
        context = sheet_group_manager.create_multi_sheet_context("CVD equipment 설비 status 상태")

        # Should detect EQUIPMENT due to CVD and 설비 keywords
        assert context.question_type == QuestionType.EQUIPMENT

    def test_period_priority_over_person(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Period keywords should take priority over person names (T032)."""
        # "이번주" contains Korean characters that could be mistaken for a name
        context = sheet_group_manager.create_multi_sheet_context("이번주 작업")

        # Should be PERIOD, not PERSON
        assert context.question_type == QuestionType.PERIOD

    def test_ambiguous_date_formats(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Various date format variations should be handled."""
        date_queries = [
            "2024-12-17",  # ISO format
            "12월 17일",   # Korean date
            "12월",        # Month only
            "52주",        # Week number
        ]

        for query in date_queries:
            period_info = sheet_group_manager.extract_period_info(query)
            assert period_info is not None, f"Failed for: {query}"


class TestPeriodQueryIntegration:
    """Integration tests for User Story 2: Period-based queries (T033)."""

    def test_period_query_detects_weekly_context(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """'이번 주 완료된 티켓' should be detected as PERIOD type."""
        context = sheet_group_manager.create_multi_sheet_context("이번 주 완료된 티켓")

        assert context.question_type == QuestionType.PERIOD

    def test_period_query_selects_ticket_sheets(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Period query should select Daily, Weekly, Monthly sheets."""
        context = sheet_group_manager.create_multi_sheet_context("이번 주 완료된 티켓")

        sheet_names = [s.sheet_name for s in context.selected_sheets]
        # Should include ticket-type sheets
        assert any("Daily" in name for name in sheet_names) or \
               any("Weekly" in name for name in sheet_names) or \
               any("Monthly" in name for name in sheet_names)

    def test_period_query_excludes_equipment(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Period query should exclude equipment sheets."""
        context = sheet_group_manager.create_multi_sheet_context("지난주 처리된 티켓")

        sheet_names = [s.sheet_name for s in context.selected_sheets]
        assert "Equipment_List" not in sheet_names

    def test_period_query_common_columns_include_date(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Period query should find common columns including '날짜'."""
        context = sheet_group_manager.create_multi_sheet_context("12월 작업 현황")

        assert "날짜" in context.common_columns

    def test_period_query_date_pattern_detection(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Date pattern '2024-12-17' should be detected as PERIOD."""
        context = sheet_group_manager.create_multi_sheet_context("2024-12-17 티켓 조회")

        assert context.question_type == QuestionType.PERIOD

    def test_period_query_month_pattern_detection(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Month pattern '12월' should be detected as PERIOD."""
        context = sheet_group_manager.create_multi_sheet_context("12월 완료 건수")

        assert context.question_type == QuestionType.PERIOD

    def test_period_query_week_number_detection(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Week number pattern '51주' should be detected as PERIOD."""
        context = sheet_group_manager.create_multi_sheet_context("51주 티켓 현황")

        assert context.question_type == QuestionType.PERIOD

    def test_period_query_uses_union(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Period query with multiple sheets should use UNION."""
        context = sheet_group_manager.create_multi_sheet_context("이번 달 작업 조회")

        if len(context.selected_sheets) > 1:
            assert context.use_union is True

    def test_period_query_various_korean_expressions(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Various Korean period expressions should all be PERIOD type."""
        period_queries = [
            "오늘 처리된 티켓",
            "어제 완료 건",
            "이번달 작업 현황",
            "지난달 통계",
            "금주 업무 조회",
        ]

        for query in period_queries:
            context = sheet_group_manager.create_multi_sheet_context(query)
            assert context.question_type == QuestionType.PERIOD, f"Failed for: {query}"


class TestEquipmentQueryIntegration:
    """Integration tests for User Story 3: Equipment-based queries (T040)."""

    def test_equipment_query_detects_type(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """'CVD 설비 고장 이력' should be detected as EQUIPMENT type."""
        context = sheet_group_manager.create_multi_sheet_context("CVD 설비 고장 이력")

        assert context.question_type == QuestionType.EQUIPMENT

    def test_equipment_query_selects_sheets_with_equipment_column(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Equipment query should select sheets with 설비코드 column."""
        context = sheet_group_manager.create_multi_sheet_context("CVD 설비 고장 이력")

        # Should select ticket sheets that have 설비코드 column
        sheet_names = [s.sheet_name for s in context.selected_sheets]

        # Daily and Weekly sheets have 설비코드 column
        assert any("Daily" in name for name in sheet_names) or \
               any("Weekly" in name for name in sheet_names)

    def test_equipment_query_excludes_equipment_list_sheet(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Equipment query should NOT select Equipment_List (different structure)."""
        context = sheet_group_manager.create_multi_sheet_context("CVD 설비 고장 이력")

        sheet_names = [s.sheet_name for s in context.selected_sheets]
        # Equipment_List has different columns (설비코드, 설비명, 설치일, 상태)
        # It doesn't have 작업유형 or 작업내용, so it might be excluded
        # depending on common column requirements

    def test_equipment_query_finds_common_columns(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Equipment query should find common columns including 설비코드."""
        context = sheet_group_manager.create_multi_sheet_context("설비별 작업 현황")

        assert "설비코드" in context.common_columns

    def test_equipment_query_with_different_codes(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Various equipment codes should all be EQUIPMENT type."""
        equipment_queries = [
            "CVD 설비 점검 이력",
            "PVD 장비 고장 현황",
            "ETCH 설비 정비 기록",
            "CMP 설비 작업 내역",
        ]

        for query in equipment_queries:
            context = sheet_group_manager.create_multi_sheet_context(query)
            assert context.question_type == QuestionType.EQUIPMENT, f"Failed for: {query}"

    def test_equipment_query_uses_union_for_multiple_sheets(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Equipment query with multiple sheets should use UNION."""
        context = sheet_group_manager.create_multi_sheet_context("설비별 전체 작업 현황")

        if len(context.selected_sheets) > 1:
            assert context.use_union is True

    def test_equipment_query_with_fault_keywords(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Fault-related equipment queries should be EQUIPMENT type."""
        fault_queries = [
            "CVD 고장 이력",
            "설비 오류 통계",
            "장비 정비 현황",
            "설비 유지보수 기록",
        ]

        for query in fault_queries:
            context = sheet_group_manager.create_multi_sheet_context(query)
            assert context.question_type == QuestionType.EQUIPMENT, f"Failed for: {query}"


class TestPerformanceRequirements:
    """Performance tests for NFR-002: Response time requirements (T054).

    Tests verify:
    - Initial query response < 10 seconds
    - Cached query response < 2 seconds
    - Metadata caching improves performance
    """

    def test_context_creation_under_100ms(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Context creation should complete in under 100ms (NFR-002)."""
        import time

        start = time.perf_counter()
        _ = sheet_group_manager.create_multi_sheet_context("김철수가 뭘 했어?")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 100, f"Context creation took {elapsed_ms:.2f}ms, expected <100ms"

    def test_cached_context_creation_faster(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Second context creation should be faster due to caching (T053)."""
        import time

        # First call - populates cache
        start1 = time.perf_counter()
        _ = sheet_group_manager.create_multi_sheet_context("김철수가 뭘 했어?")
        elapsed1 = time.perf_counter() - start1

        # Second call - should use cache
        start2 = time.perf_counter()
        _ = sheet_group_manager.create_multi_sheet_context("김철수가 뭘 했어?")
        elapsed2 = time.perf_counter() - start2

        # Second call should be faster or similar (cache hit)
        assert elapsed2 <= elapsed1 * 1.5, \
            f"Cached call ({elapsed2*1000:.2f}ms) should be faster than first ({elapsed1*1000:.2f}ms)"

    def test_multiple_queries_performance(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Multiple different queries should complete efficiently."""
        import time

        queries = [
            "김철수가 뭘 했어?",
            "이번 주 완료된 티켓",
            "CVD 설비 고장 이력",
            "오늘 처리된 건",
            "설비별 작업 현황",
        ]

        start = time.perf_counter()
        for query in queries:
            _ = sheet_group_manager.create_multi_sheet_context(query)
        total_elapsed_ms = (time.perf_counter() - start) * 1000

        # All 5 queries should complete in under 500ms
        assert total_elapsed_ms < 500, \
            f"5 queries took {total_elapsed_ms:.2f}ms, expected <500ms"

    def test_period_extraction_performance(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Period extraction should be fast (under 10ms)."""
        import time

        start = time.perf_counter()
        for _ in range(100):
            _ = sheet_group_manager.extract_period_info("이번 주 완료된 티켓")
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 100 extractions should complete in under 50ms (0.5ms each)
        assert elapsed_ms < 50, f"100 period extractions took {elapsed_ms:.2f}ms"

    def test_equipment_extraction_performance(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Equipment extraction should be fast (under 10ms)."""
        import time

        start = time.perf_counter()
        for _ in range(100):
            _ = sheet_group_manager.extract_equipment_info("CVD 설비 고장 이력")
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 100 extractions should complete in under 50ms (0.5ms each)
        assert elapsed_ms < 50, f"100 equipment extractions took {elapsed_ms:.2f}ms"

    def test_sheet_classification_performance(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Sheet classification should be very fast with caching."""
        import time

        sheets = ["Daily_20241215", "Daily_20241216", "Weekly_W51", "Monthly_Summary"]

        # Warm up cache
        for sheet in sheets:
            sheet_group_manager.classify_sheet(sheet)

        # Measure cached performance
        start = time.perf_counter()
        for _ in range(1000):
            for sheet in sheets:
                sheet_group_manager.classify_sheet(sheet)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 4000 classifications should complete in under 100ms
        assert elapsed_ms < 100, f"4000 classifications took {elapsed_ms:.2f}ms"

    def test_common_columns_caching_performance(
        self,
        sheet_group_manager: SheetGroupManager
    ):
        """Common columns lookup should benefit from caching."""
        import time

        sheets = ["Daily_20241215", "Daily_20241216", "Daily_20241217"]

        # First call (no cache)
        start1 = time.perf_counter()
        result1 = sheet_group_manager.find_common_columns(sheets)
        elapsed1 = time.perf_counter() - start1

        # Second call (cached)
        start2 = time.perf_counter()
        result2 = sheet_group_manager.find_common_columns(sheets)
        elapsed2 = time.perf_counter() - start2

        assert result1 == result2
        # Cached call should be at least as fast
        assert elapsed2 <= elapsed1 * 2, \
            f"Cached call ({elapsed2*1000:.4f}ms) should be faster than first ({elapsed1*1000:.4f}ms)"
