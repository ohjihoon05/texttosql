"""Unit tests for SheetGroupManager.

Tests cover:
- Sheet classification (classify_sheet)
- Common column finding (find_common_columns)
- Relevant sheet selection (select_relevant_sheets)
- Multi-sheet context creation (create_multi_sheet_context)
"""

import pytest
from src.models.schema import ExcelSchema, SheetSchema, ColumnInfo
from src.models.sheet_group import QuestionType
from src.services.sheet_group_manager import SheetGroupManager


@pytest.fixture
def sample_schema() -> ExcelSchema:
    """Create a sample ExcelSchema for testing."""
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

    # Weekly has extra column
    weekly_columns = ticket_columns + [
        ColumnInfo(name="주차", dtype="int64", sample_values=["52"]),
    ]

    # Monthly has extra columns
    monthly_columns = ticket_columns + [
        ColumnInfo(name="월", dtype="object", sample_values=["12월"]),
        ColumnInfo(name="SLA_충족", dtype="object", sample_values=["Y"]),
    ]

    # Equipment has different columns
    equipment_columns = [
        ColumnInfo(name="설비코드", dtype="object", sample_values=["CVD001"]),
        ColumnInfo(name="설비명", dtype="object", sample_values=["CVD 장비 1호"]),
        ColumnInfo(name="설치일", dtype="object", sample_values=["2020-01-15"]),
        ColumnInfo(name="상태", dtype="object", sample_values=["가동중"]),
    ]

    sheets = {
        "Daily_20241217": SheetSchema(name="Daily_20241217", columns=ticket_columns, row_count=85),
        "Daily_20241218": SheetSchema(name="Daily_20241218", columns=ticket_columns, row_count=72),
        "Daily_20241219": SheetSchema(name="Daily_20241219", columns=ticket_columns, row_count=91),
        "Weekly_W52": SheetSchema(name="Weekly_W52", columns=weekly_columns, row_count=350),
        "Monthly_Summary": SheetSchema(name="Monthly_Summary", columns=monthly_columns, row_count=500),
        "Equipment_List": SheetSchema(name="Equipment_List", columns=equipment_columns, row_count=150),
    }

    return ExcelSchema(
        file_name="test_report.xlsx",
        file_size_mb=2.5,
        sheets=sheets,
    )


@pytest.fixture
def manager(sample_schema: ExcelSchema) -> SheetGroupManager:
    """Create SheetGroupManager with sample schema."""
    return SheetGroupManager(schema=sample_schema)


class TestClassifySheet:
    """Tests for classify_sheet method."""

    def test_classify_daily_sheet(self, manager: SheetGroupManager):
        """Daily sheets should be classified as TICKET_DAILY."""
        assert manager.classify_sheet("Daily_20241217") == "TICKET_DAILY"
        assert manager.classify_sheet("Daily_20241218") == "TICKET_DAILY"
        assert manager.classify_sheet("Daily_20241219") == "TICKET_DAILY"

    def test_classify_weekly_sheet(self, manager: SheetGroupManager):
        """Weekly sheets should be classified as TICKET_WEEKLY."""
        assert manager.classify_sheet("Weekly_W52") == "TICKET_WEEKLY"
        assert manager.classify_sheet("Weekly_W1") == "TICKET_WEEKLY"

    def test_classify_monthly_sheet(self, manager: SheetGroupManager):
        """Monthly sheets should be classified as TICKET_MONTHLY."""
        assert manager.classify_sheet("Monthly_Summary") == "TICKET_MONTHLY"
        assert manager.classify_sheet("Monthly_Report") == "TICKET_MONTHLY"

    def test_classify_equipment_sheet(self, manager: SheetGroupManager):
        """Equipment sheets should be classified as EQUIPMENT."""
        assert manager.classify_sheet("Equipment_List") == "EQUIPMENT"
        assert manager.classify_sheet("Equipment_Status") == "EQUIPMENT"

    def test_classify_unknown_sheet(self, manager: SheetGroupManager):
        """Unknown sheets should be classified as UNKNOWN."""
        assert manager.classify_sheet("RandomSheet") == "UNKNOWN"
        assert manager.classify_sheet("Something_Else") == "UNKNOWN"

    def test_classify_empty_sheet_name_raises(self, manager: SheetGroupManager):
        """Empty sheet name should raise ValueError."""
        with pytest.raises(ValueError, match="Sheet name cannot be empty"):
            manager.classify_sheet("")


class TestGetSheetsByGroup:
    """Tests for get_sheets_by_group method."""

    def test_get_daily_sheets(self, manager: SheetGroupManager):
        """Should return all daily sheets."""
        sheets = manager.get_sheets_by_group("TICKET_DAILY")
        assert len(sheets) == 3
        assert "Daily_20241217" in sheets
        assert "Daily_20241218" in sheets
        assert "Daily_20241219" in sheets

    def test_get_weekly_sheets(self, manager: SheetGroupManager):
        """Should return all weekly sheets."""
        sheets = manager.get_sheets_by_group("TICKET_WEEKLY")
        assert len(sheets) == 1
        assert "Weekly_W52" in sheets

    def test_get_nonexistent_group(self, manager: SheetGroupManager):
        """Should return empty list for nonexistent group."""
        sheets = manager.get_sheets_by_group("NONEXISTENT")
        assert sheets == []


class TestFindCommonColumns:
    """Tests for find_common_columns method."""

    def test_common_columns_same_group(self, manager: SheetGroupManager):
        """Daily sheets should have same columns."""
        common = manager.find_common_columns(["Daily_20241217", "Daily_20241218"])
        assert "날짜" in common
        assert "담당자" in common
        assert "티켓번호" in common
        assert "상태" in common
        assert len(common) == 7  # All ticket columns

    def test_common_columns_daily_weekly(self, manager: SheetGroupManager):
        """Daily and Weekly should share base columns."""
        common = manager.find_common_columns(["Daily_20241217", "Weekly_W52"])
        assert "날짜" in common
        assert "담당자" in common
        assert "주차" not in common  # Weekly-specific

    def test_common_columns_with_equipment(self, manager: SheetGroupManager):
        """Ticket and Equipment sheets have few common columns."""
        common = manager.find_common_columns(["Daily_20241217", "Equipment_List"])
        # Only 설비코드 and 상태 are common
        assert "설비코드" in common
        assert "상태" in common
        assert "담당자" not in common

    def test_common_columns_empty_list(self, manager: SheetGroupManager):
        """Empty sheet list should return empty columns."""
        common = manager.find_common_columns([])
        assert common == []

    def test_common_columns_single_sheet(self, manager: SheetGroupManager):
        """Single sheet should return all its columns."""
        common = manager.find_common_columns(["Daily_20241217"])
        assert len(common) == 7

    def test_common_columns_no_schema_raises(self):
        """Should raise if no schema available."""
        manager = SheetGroupManager()
        with pytest.raises(ValueError, match="No schema available"):
            manager.find_common_columns(["Daily_20241217"])


class TestGetCompatibleSheets:
    """Tests for get_compatible_sheets method."""

    def test_daily_compatible_with_weekly_monthly(self, manager: SheetGroupManager):
        """Daily sheet should be compatible with Weekly and Monthly."""
        compatible = manager.get_compatible_sheets("Daily_20241217")
        # Should include all Daily, Weekly, and Monthly sheets
        assert "Daily_20241217" in compatible
        assert "Weekly_W52" in compatible
        assert "Monthly_Summary" in compatible
        # Should NOT include Equipment
        assert "Equipment_List" not in compatible

    def test_equipment_not_compatible_with_tickets(self, manager: SheetGroupManager):
        """Equipment should not be compatible with ticket sheets."""
        compatible = manager.get_compatible_sheets("Equipment_List")
        # Should only include Equipment sheets
        assert "Equipment_List" in compatible
        assert "Daily_20241217" not in compatible
        assert "Weekly_W52" not in compatible


class TestDetectQuestionType:
    """Tests for _detect_question_type method (T019)."""

    def test_detect_person_type_korean_name(self, manager: SheetGroupManager):
        """Should detect PERSON type for Korean name queries."""
        assert manager._detect_question_type("김철수가 뭘 했어?") == QuestionType.PERSON
        assert manager._detect_question_type("박영희 담당자 작업 내역") == QuestionType.PERSON
        assert manager._detect_question_type("이민수 작업 조회") == QuestionType.PERSON

    def test_detect_person_type_with_keywords(self, manager: SheetGroupManager):
        """Should detect PERSON type with person-related keywords."""
        assert manager._detect_question_type("담당자별 작업 현황") == QuestionType.PERSON
        assert manager._detect_question_type("누가 이 작업을 했어?") == QuestionType.PERSON

    def test_detect_period_type(self, manager: SheetGroupManager):
        """Should detect PERIOD type for date/time queries."""
        assert manager._detect_question_type("이번 주 완료된 티켓") == QuestionType.PERIOD
        assert manager._detect_question_type("12월 작업 현황") == QuestionType.PERIOD
        assert manager._detect_question_type("오늘 처리된 건") == QuestionType.PERIOD

    def test_detect_period_type_extended(self, manager: SheetGroupManager):
        """T032: Extended PERIOD type detection tests."""
        # Week-based queries
        assert manager._detect_question_type("이번주 작업 현황") == QuestionType.PERIOD
        assert manager._detect_question_type("지난주 완료 건") == QuestionType.PERIOD
        assert manager._detect_question_type("저번 주 티켓") == QuestionType.PERIOD
        assert manager._detect_question_type("금주 처리 현황") == QuestionType.PERIOD
        assert manager._detect_question_type("52주 티켓 현황") == QuestionType.PERIOD

        # Day-based queries
        assert manager._detect_question_type("어제 처리된 티켓") == QuestionType.PERIOD
        assert manager._detect_question_type("내일 예정된 작업") == QuestionType.PERIOD

        # Month-based queries
        assert manager._detect_question_type("이번 달 작업 현황") == QuestionType.PERIOD
        assert manager._detect_question_type("저번 달 티켓") == QuestionType.PERIOD
        assert manager._detect_question_type("지난달 완료 건수") == QuestionType.PERIOD
        assert manager._detect_question_type("이번달 작업") == QuestionType.PERIOD

        # Date pattern queries
        assert manager._detect_question_type("2024-12-17 티켓 조회") == QuestionType.PERIOD
        assert manager._detect_question_type("12월 17일 작업") == QuestionType.PERIOD

        # Generic period keywords
        assert manager._detect_question_type("특정 기간 작업 조회") == QuestionType.PERIOD
        assert manager._detect_question_type("날짜별 현황") == QuestionType.PERIOD

    def test_detect_equipment_type(self, manager: SheetGroupManager):
        """Should detect EQUIPMENT type for equipment queries."""
        assert manager._detect_question_type("CVD 설비 고장 이력") == QuestionType.EQUIPMENT
        assert manager._detect_question_type("설비별 작업 현황") == QuestionType.EQUIPMENT

    def test_detect_equipment_type_extended(self, manager: SheetGroupManager):
        """T039: Extended EQUIPMENT type detection tests."""
        # Equipment code patterns
        assert manager._detect_question_type("CVD 설비 점검 이력") == QuestionType.EQUIPMENT
        assert manager._detect_question_type("PVD 장비 고장 현황") == QuestionType.EQUIPMENT
        assert manager._detect_question_type("ETCH 공정 설비 상태") == QuestionType.EQUIPMENT
        assert manager._detect_question_type("CMP 설비 정비 이력") == QuestionType.EQUIPMENT

        # Equipment keywords
        assert manager._detect_question_type("설비 점검 일정") == QuestionType.EQUIPMENT
        assert manager._detect_question_type("장비 고장 통계") == QuestionType.EQUIPMENT
        assert manager._detect_question_type("설비코드 CVD-001 조회") == QuestionType.EQUIPMENT
        assert manager._detect_question_type("설비명으로 검색") == QuestionType.EQUIPMENT

        # Maintenance keywords
        assert manager._detect_question_type("CVD 정비 이력 조회") == QuestionType.EQUIPMENT
        assert manager._detect_question_type("PVD 유지보수 현황") == QuestionType.EQUIPMENT
        assert manager._detect_question_type("ETCH 고장 빈도") == QuestionType.EQUIPMENT

        # Combined patterns - equipment + fault
        assert manager._detect_question_type("CVD 설비 오류 이력") == QuestionType.EQUIPMENT
        assert manager._detect_question_type("반도체 장비 고장 분석") == QuestionType.EQUIPMENT

    def test_detect_statistics_type(self, manager: SheetGroupManager):
        """Should detect STATISTICS type for aggregate queries."""
        assert manager._detect_question_type("총 몇 건 처리했어?") == QuestionType.STATISTICS
        assert manager._detect_question_type("평균 처리 시간") == QuestionType.STATISTICS

    def test_detect_unknown_type(self, manager: SheetGroupManager):
        """Should return UNKNOWN for unclassifiable queries."""
        assert manager._detect_question_type("아무거나") == QuestionType.UNKNOWN


class TestSelectRelevantSheets:
    """Tests for select_relevant_sheets method (T019)."""

    def test_select_sheets_for_person_query(self, manager: SheetGroupManager):
        """PERSON query should select ticket-type sheets with 담당자 column."""
        selections = manager.select_relevant_sheets("김철수가 뭘 했어?")
        sheet_names = [s.sheet_name for s in selections]

        # Should include all ticket sheets (Daily, Weekly, Monthly)
        assert any("Daily" in name for name in sheet_names)
        assert any("Weekly" in name for name in sheet_names)
        assert any("Monthly" in name for name in sheet_names)

        # Should NOT include Equipment (no 담당자 column)
        assert not any("Equipment" in name for name in sheet_names)

    def test_select_sheets_respects_max_limit(self, manager: SheetGroupManager):
        """Should not exceed max_union_sheets limit."""
        selections = manager.select_relevant_sheets("김철수가 뭘 했어?")
        assert len(selections) <= manager.settings.max_union_sheets

    def test_select_sheets_returns_sheet_selections(self, manager: SheetGroupManager):
        """Should return properly structured SheetSelection objects."""
        selections = manager.select_relevant_sheets("김철수가 뭘 했어?")

        for selection in selections:
            assert selection.sheet_name is not None
            assert selection.group_name is not None


class TestExtractPeriodInfo:
    """Tests for extract_period_info method (T035)."""

    def test_extract_this_week(self, manager: SheetGroupManager):
        """'이번 주' should extract this week's date range."""
        result = manager.extract_period_info("이번 주 완료된 티켓")

        assert result["period_type"] == "week"
        assert result["relative"] == "this"
        assert result["start_date"] is not None
        assert result["end_date"] is not None
        assert result["raw_expression"] == "이번 주"

    def test_extract_last_week(self, manager: SheetGroupManager):
        """'지난주' should extract last week's date range."""
        result = manager.extract_period_info("지난주 처리된 건")

        assert result["period_type"] == "week"
        assert result["relative"] == "last"
        assert result["start_date"] is not None
        assert result["end_date"] is not None

    def test_extract_this_month(self, manager: SheetGroupManager):
        """'이번 달' should extract this month's date range."""
        result = manager.extract_period_info("이번 달 작업 현황")

        assert result["period_type"] == "month"
        assert result["relative"] == "this"
        assert result["start_date"] is not None
        assert result["end_date"] is not None

    def test_extract_last_month(self, manager: SheetGroupManager):
        """'지난달' should extract last month's date range."""
        result = manager.extract_period_info("지난달 완료 건수")

        assert result["period_type"] == "month"
        assert result["relative"] == "last"

    def test_extract_today(self, manager: SheetGroupManager):
        """'오늘' should extract today's date."""
        result = manager.extract_period_info("오늘 처리된 티켓")

        assert result["period_type"] == "day"
        assert result["relative"] == "this"
        assert result["start_date"] == result["end_date"]

    def test_extract_yesterday(self, manager: SheetGroupManager):
        """'어제' should extract yesterday's date."""
        result = manager.extract_period_info("어제 완료된 작업")

        assert result["period_type"] == "day"
        assert result["relative"] == "last"

    def test_extract_specific_date_iso(self, manager: SheetGroupManager):
        """ISO date '2024-12-17' should be extracted."""
        result = manager.extract_period_info("2024-12-17 티켓 조회")

        assert result["period_type"] == "date_range"
        assert result["start_date"] == "2024-12-17"
        assert result["end_date"] == "2024-12-17"

    def test_extract_specific_month(self, manager: SheetGroupManager):
        """'12월' should extract the entire month."""
        result = manager.extract_period_info("12월 작업 현황")

        assert result["period_type"] == "month"
        assert result["raw_expression"] == "12월"
        assert result["start_date"] is not None  # Should be YYYY-12-01
        assert "12-01" in result["start_date"]

    def test_extract_specific_date_korean(self, manager: SheetGroupManager):
        """'12월 17일' should extract specific date."""
        result = manager.extract_period_info("12월 17일 작업")

        assert result["period_type"] == "date_range"
        assert "12-17" in result["start_date"]

    def test_extract_week_number(self, manager: SheetGroupManager):
        """'52주' should extract week 52's date range."""
        result = manager.extract_period_info("52주 티켓 현황")

        assert result["period_type"] == "week"
        assert result["raw_expression"] == "52주"
        assert result["start_date"] is not None
        assert result["end_date"] is not None

    def test_extract_no_period(self, manager: SheetGroupManager):
        """Question without period should return empty result."""
        result = manager.extract_period_info("김철수가 뭘 했어?")

        assert result["period_type"] is None
        assert result["start_date"] is None
        assert result["end_date"] is None

    def test_extract_geumju(self, manager: SheetGroupManager):
        """'금주' should be same as '이번 주'."""
        result = manager.extract_period_info("금주 처리 현황")

        assert result["period_type"] == "week"
        assert result["relative"] == "this"


class TestExtractEquipmentInfo:
    """Tests for extract_equipment_info method (T042)."""

    def test_extract_cvd_equipment(self, manager: SheetGroupManager):
        """'CVD 설비' should extract CVD code."""
        result = manager.extract_equipment_info("CVD 설비 고장 이력")

        assert result["equipment_codes"] == ["CVD"]
        assert result["fault_type"] == "고장"

    def test_extract_pvd_equipment(self, manager: SheetGroupManager):
        """'PVD 장비' should extract PVD code."""
        result = manager.extract_equipment_info("PVD 장비 점검 현황")

        assert result["equipment_codes"] == ["PVD"]
        assert result["fault_type"] == "점검"

    def test_extract_etch_equipment(self, manager: SheetGroupManager):
        """'ETCH 공정' should extract ETCH code."""
        result = manager.extract_equipment_info("ETCH 공정 설비 정비")

        assert result["equipment_codes"] == ["ETCH"]
        assert result["fault_type"] == "정비"

    def test_extract_specific_equipment_code(self, manager: SheetGroupManager):
        """'CVD-001' should extract specific pattern."""
        result = manager.extract_equipment_info("CVD-001 설비 상태 조회")

        assert result["equipment_codes"] == ["CVD"]
        assert result["equipment_pattern"] == "CVD-001"

    def test_extract_multiple_equipment_codes(self, manager: SheetGroupManager):
        """Multiple equipment codes in question."""
        result = manager.extract_equipment_info("CVD와 PVD 설비 비교")

        assert "CVD" in result["equipment_codes"]
        assert "PVD" in result["equipment_codes"]

    def test_extract_fault_type_gojang(self, manager: SheetGroupManager):
        """'고장' keyword should be detected."""
        result = manager.extract_equipment_info("설비 고장 이력")

        assert result["fault_type"] == "고장"

    def test_extract_fault_type_jeomgeom(self, manager: SheetGroupManager):
        """'점검' keyword should be detected."""
        result = manager.extract_equipment_info("설비 점검 일정")

        assert result["fault_type"] == "점검"

    def test_extract_fault_type_jeongbi(self, manager: SheetGroupManager):
        """'유지보수' should map to '정비'."""
        result = manager.extract_equipment_info("설비 유지보수 현황")

        assert result["fault_type"] == "정비"

    def test_extract_no_equipment(self, manager: SheetGroupManager):
        """Question without equipment should return empty result."""
        result = manager.extract_equipment_info("김철수가 뭘 했어?")

        assert result["equipment_codes"] is None
        assert result["fault_type"] is None

    def test_extract_case_insensitive(self, manager: SheetGroupManager):
        """Equipment codes should be detected case-insensitively."""
        result = manager.extract_equipment_info("cvd 설비 조회")

        assert result["equipment_codes"] == ["CVD"]


class TestCreateMultiSheetContext:
    """Tests for create_multi_sheet_context method (T020)."""

    def test_create_context_for_person_query(self, manager: SheetGroupManager):
        """Should create proper context for PERSON type query."""
        context = manager.create_multi_sheet_context("김철수가 뭘 했어?")

        assert context.question_type == QuestionType.PERSON
        assert len(context.selected_sheets) > 0
        assert len(context.common_columns) > 0
        assert "담당자" in context.common_columns

    def test_create_context_sets_union_flag(self, manager: SheetGroupManager):
        """Should set use_union=True when multiple sheets selected."""
        context = manager.create_multi_sheet_context("김철수가 뭘 했어?")

        if len(context.selected_sheets) > 1:
            assert context.use_union is True

    def test_create_context_finds_common_columns(self, manager: SheetGroupManager):
        """Should identify common columns across selected sheets."""
        context = manager.create_multi_sheet_context("김철수가 뭘 했어?")

        # Common columns should be subset of each selected sheet's columns
        for selection in context.selected_sheets:
            sheet = manager._schema.get_sheet(selection.sheet_name)
            if sheet:
                for col in context.common_columns:
                    assert col in sheet.column_names

    def test_create_context_without_schema_raises(self):
        """Should raise error when no schema available."""
        manager = SheetGroupManager()
        with pytest.raises(ValueError, match="No schema available"):
            manager.create_multi_sheet_context("김철수가 뭘 했어?")


class TestMetadataCaching:
    """Tests for metadata caching (T053/FR-011)."""

    def test_common_columns_cached(self, manager: SheetGroupManager):
        """Common columns should be cached after first call."""
        sheets = ["Daily_20241217", "Daily_20241218"]

        # First call
        result1 = manager.find_common_columns(sheets)

        # Second call should use cache
        result2 = manager.find_common_columns(sheets)

        assert result1 == result2
        # Verify cache was used (check cache stats via internal cache)
        cache_info = manager._cached_find_common_columns.cache_info()
        assert cache_info.hits >= 1

    def test_sheet_group_classification_cached(self, manager: SheetGroupManager):
        """Sheet group classification should be cached."""
        # Clear any existing cache from initialization
        manager._cached_classify_sheet.cache_clear()

        # First call
        group1 = manager.classify_sheet("Daily_20241217")

        # Second call should use cache
        group2 = manager.classify_sheet("Daily_20241217")

        assert group1 == group2
        # Check cache was used
        cache_info = manager._cached_classify_sheet.cache_info()
        assert cache_info.hits >= 1

    def test_cache_cleared_on_schema_change(self, manager: SheetGroupManager, sample_schema: ExcelSchema):
        """Cache should be cleared when schema changes."""
        # Populate cache
        _ = manager.find_common_columns(["Daily_20241217", "Daily_20241218"])

        # Change schema (triggers cache clear)
        manager.set_schema(sample_schema)

        # Cache should be cleared
        cache_info = manager._cached_find_common_columns.cache_info()
        assert cache_info.currsize == 0

    def test_required_columns_cached(self, manager: SheetGroupManager):
        """Required columns for question type should be cached."""
        from src.models.sheet_group import QuestionType

        # First call
        cols1 = manager._get_required_columns_for_type(QuestionType.PERSON)

        # Second call should use cache
        cols2 = manager._get_required_columns_for_type(QuestionType.PERSON)

        assert cols1 == cols2
        cache_info = manager._cached_required_columns.cache_info()
        assert cache_info.hits >= 1
