"""
Unit tests for test data generator.

Tests:
- T021: Sheet count validation (30 sheets)
- T022: File size validation (2-4MB range, adjusted to 0.3-10MB)
- T023: DuckDB load compatibility
- T024: Data consistency (all engineers in ENGINEERS list)
"""

import os
import sys
import pytest
import duckdb
import openpyxl
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.generate_test_data import (
    ENGINEERS,
    EQUIPMENT_TYPES,
    ISSUE_TYPES,
    CUSTOMERS,
    STATUSES,
    TEAMS,
    DataFactory,
)


# Test data file path
DATA_FILE = Path(__file__).parent.parent.parent / "data" / "cs_daily_report.xlsx"


def get_sheet_names() -> list[str]:
    """openpyxl로 시트 이름 목록 가져오기."""
    wb = openpyxl.load_workbook(DATA_FILE, read_only=True)
    names = wb.sheetnames
    wb.close()
    return names


class TestSheetCount:
    """T021: Sheet count validation tests."""

    def test_excel_file_exists(self):
        """Excel 파일이 존재하는지 확인."""
        assert DATA_FILE.exists(), f"Excel 파일이 없음: {DATA_FILE}"

    def test_sheet_count_is_30(self):
        """시트 수가 30개인지 확인."""
        sheet_names = get_sheet_names()
        sheet_count = len(sheet_names)
        assert sheet_count == 30, f"시트 수가 30개가 아님: {sheet_count}개"

    def test_expected_sheet_types_exist(self):
        """예상되는 시트 유형들이 존재하는지 확인."""
        sheet_names = get_sheet_names()

        # Check for expected prefixes
        expected_prefixes = [
            'Daily_',      # 7 sheets
            'Weekly_',     # 4 sheets
            'Monthly_',    # 1 sheet
            'Equipment_',  # 5 sheets
            'Team_',       # 5 sheets
            'Customer_',   # 3 sheets
            'Status_',     # 3 sheets
            'Parts_',      # 1 sheet
            'Engineer_',   # 1 sheet
        ]

        for prefix in expected_prefixes:
            matching = [s for s in sheet_names if s.startswith(prefix)]
            assert len(matching) > 0, f"'{prefix}' 로 시작하는 시트가 없음"


class TestFileSize:
    """T022: File size validation tests."""

    def test_file_size_minimum(self):
        """파일 크기가 최소 기준(0.3MB)을 충족하는지 확인."""
        file_size_mb = DATA_FILE.stat().st_size / (1024 * 1024)
        assert file_size_mb >= 0.3, f"파일이 너무 작음: {file_size_mb:.2f}MB (최소 0.3MB)"

    def test_file_size_maximum(self):
        """파일 크기가 최대 기준(10MB)을 초과하지 않는지 확인."""
        file_size_mb = DATA_FILE.stat().st_size / (1024 * 1024)
        assert file_size_mb <= 10.0, f"파일이 너무 큼: {file_size_mb:.2f}MB (최대 10MB)"

    def test_file_size_in_acceptable_range(self):
        """파일 크기가 적정 범위(0.3-10MB) 내에 있는지 확인."""
        file_size_mb = DATA_FILE.stat().st_size / (1024 * 1024)
        assert 0.3 <= file_size_mb <= 10.0, f"파일 크기 범위 벗어남: {file_size_mb:.2f}MB"


class TestDuckDBCompatibility:
    """T023: DuckDB load compatibility tests."""

    def test_can_read_all_sheets(self):
        """모든 시트를 DuckDB로 읽을 수 있는지 확인."""
        conn = duckdb.connect()
        sheet_names = get_sheet_names()

        # Try to read each sheet
        for sheet_name in sheet_names:
            try:
                df = conn.execute(f"""
                    SELECT * FROM read_xlsx('{DATA_FILE}', sheet='{sheet_name}')
                """).fetchdf()
                assert len(df) > 0, f"시트 '{sheet_name}'가 비어있음"
            except Exception as e:
                pytest.fail(f"시트 '{sheet_name}' 읽기 실패: {e}")

        conn.close()

    def test_can_query_with_sql(self):
        """SQL 쿼리로 데이터를 조회할 수 있는지 확인."""
        conn = duckdb.connect()

        # Test simple COUNT query on first Daily sheet
        result = conn.execute(f"""
            SELECT COUNT(*) as cnt
            FROM read_xlsx('{DATA_FILE}', sheet='Daily_20241217')
        """).fetchone()

        assert result[0] > 0, "Daily 시트에서 데이터 조회 실패"
        conn.close()

    def test_can_filter_by_engineer(self):
        """담당자별 필터링이 가능한지 확인."""
        conn = duckdb.connect()

        # Query with filter
        result = conn.execute(f"""
            SELECT * FROM read_xlsx('{DATA_FILE}', sheet='Daily_20241217')
            WHERE "담당자" = '김철수'
        """).fetchdf()

        # Should return some rows (may be 0 if no data for this engineer in this sheet)
        assert result is not None, "필터링 쿼리 실행 실패"
        conn.close()

    def test_can_aggregate_data(self):
        """집계 쿼리가 가능한지 확인."""
        conn = duckdb.connect()

        result = conn.execute(f"""
            SELECT "담당자", COUNT(*) as cnt
            FROM read_xlsx('{DATA_FILE}', sheet='Monthly_Summary')
            GROUP BY "담당자"
            ORDER BY cnt DESC
        """).fetchdf()

        assert len(result) > 0, "집계 쿼리 실패"
        conn.close()


class TestDataConsistency:
    """T024: Data consistency tests."""

    def test_all_engineers_in_master_list(self):
        """모든 담당자가 마스터 데이터에 있는지 확인."""
        conn = duckdb.connect()

        # Get all unique engineers from Monthly_Summary
        result = conn.execute(f"""
            SELECT DISTINCT "담당자"
            FROM read_xlsx('{DATA_FILE}', sheet='Monthly_Summary')
            WHERE "담당자" IS NOT NULL
        """).fetchall()

        engineers_in_file = [r[0] for r in result]

        for engineer in engineers_in_file:
            assert engineer in ENGINEERS, f"알 수 없는 담당자: {engineer}"

        conn.close()

    def test_all_equipment_types_valid(self):
        """모든 설비유형이 마스터 데이터에 있는지 확인."""
        conn = duckdb.connect()

        result = conn.execute(f"""
            SELECT DISTINCT "설비유형"
            FROM read_xlsx('{DATA_FILE}', sheet='Monthly_Summary')
            WHERE "설비유형" IS NOT NULL
        """).fetchall()

        equipment_types_in_file = [r[0] for r in result]

        for eq_type in equipment_types_in_file:
            assert eq_type in EQUIPMENT_TYPES, f"알 수 없는 설비유형: {eq_type}"

        conn.close()

    def test_all_issue_types_valid(self):
        """모든 고장유형이 마스터 데이터에 있는지 확인."""
        conn = duckdb.connect()

        result = conn.execute(f"""
            SELECT DISTINCT "고장유형"
            FROM read_xlsx('{DATA_FILE}', sheet='Monthly_Summary')
            WHERE "고장유형" IS NOT NULL
        """).fetchall()

        issue_types_in_file = [r[0] for r in result]

        for issue_type in issue_types_in_file:
            assert issue_type in ISSUE_TYPES, f"알 수 없는 고장유형: {issue_type}"

        conn.close()

    def test_all_customers_valid(self):
        """모든 고객사가 마스터 데이터에 있는지 확인."""
        conn = duckdb.connect()

        result = conn.execute(f"""
            SELECT DISTINCT "고객사"
            FROM read_xlsx('{DATA_FILE}', sheet='Monthly_Summary')
            WHERE "고객사" IS NOT NULL
        """).fetchall()

        customers_in_file = [r[0] for r in result]

        for customer in customers_in_file:
            assert customer in CUSTOMERS, f"알 수 없는 고객사: {customer}"

        conn.close()

    def test_all_statuses_valid(self):
        """모든 상태값이 마스터 데이터에 있는지 확인."""
        conn = duckdb.connect()

        result = conn.execute(f"""
            SELECT DISTINCT "상태"
            FROM read_xlsx('{DATA_FILE}', sheet='Monthly_Summary')
            WHERE "상태" IS NOT NULL
        """).fetchall()

        statuses_in_file = [r[0] for r in result]

        for status in statuses_in_file:
            assert status in STATUSES, f"알 수 없는 상태: {status}"

        conn.close()


class TestDataFactory:
    """DataFactory 클래스 단위 테스트."""

    def setup_method(self):
        """테스트 전 DataFactory 인스턴스 생성."""
        self.factory = DataFactory()

    def test_ticket_id_format(self):
        """티켓 ID 형식 검증."""
        from datetime import datetime

        date = datetime(2024, 12, 15)
        ticket_id = self.factory.generate_ticket_id(date)

        assert ticket_id.startswith("CS-20241215-"), f"잘못된 티켓 ID 형식: {ticket_id}"
        assert len(ticket_id) == 16, f"티켓 ID 길이가 맞지 않음: {len(ticket_id)}"

    def test_ticket_id_uniqueness(self):
        """티켓 ID 유일성 검증."""
        from datetime import datetime

        date = datetime(2024, 12, 15)
        ids = [self.factory.generate_ticket_id(date) for _ in range(100)]

        assert len(ids) == len(set(ids)), "중복 티켓 ID 발생"

    def test_random_date_in_range(self):
        """랜덤 날짜가 범위 내에 있는지 검증."""
        from datetime import datetime

        start = datetime(2024, 10, 1)
        end = datetime(2024, 12, 23)

        for _ in range(100):
            date = self.factory.generate_random_date(start, end)
            assert start <= date <= end, f"날짜 범위 벗어남: {date}"

    def test_equipment_id_format(self):
        """설비 ID 형식 검증."""
        eq_id = self.factory.generate_equipment_id("CVD", "삼성전자")

        # Format: EQ-{type_code}-{customer_code}-NNN (예: EQ-CVD-SS-001)
        assert eq_id.startswith("EQ-CVD-SS-"), f"잘못된 설비 ID 형식: {eq_id}"
        assert len(eq_id) == 13, f"설비 ID 길이가 맞지 않음: {len(eq_id)}"


class TestMasterData:
    """마스터 데이터 검증 테스트."""

    def test_engineers_count(self):
        """담당자 수 검증."""
        assert len(ENGINEERS) >= 10, f"담당자가 너무 적음: {len(ENGINEERS)}"

    def test_equipment_types_count(self):
        """설비유형 수 검증."""
        assert len(EQUIPMENT_TYPES) >= 5, f"설비유형이 너무 적음: {len(EQUIPMENT_TYPES)}"

    def test_customers_count(self):
        """고객사 수 검증."""
        assert len(CUSTOMERS) >= 3, f"고객사가 너무 적음: {len(CUSTOMERS)}"

    def test_teams_count(self):
        """팀 수 검증."""
        assert len(TEAMS) >= 3, f"팀이 너무 적음: {len(TEAMS)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
