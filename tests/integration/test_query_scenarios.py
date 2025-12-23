"""
Integration tests for query scenarios.

Tests natural language query patterns against generated test data:
- US2 (T025-T028): 담당자 기반 질의
- US3 (T029-T032): 설비/장비 기반 질의
- US4 (T033-T036): 날짜/기간 기반 질의
- US5 (T037-T039): 복합 조건 질의
- US6 (T040-T043): 집계/통계 질의
- Edge Cases (T044-T046): 특수 케이스
"""

import sys
import pytest
import duckdb
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.generate_test_data import (
    ENGINEERS,
    EQUIPMENT_TYPES,
    CUSTOMERS,
)

# Test data file path
DATA_FILE = Path(__file__).parent.parent.parent / "data" / "cs_daily_report.xlsx"


@pytest.fixture(scope="module")
def db_connection():
    """DuckDB 연결 fixture."""
    conn = duckdb.connect()
    yield conn
    conn.close()


# =============================================================================
# Phase 4: US2 - 담당자 기반 질의 테스트 (T025-T028)
# =============================================================================

class TestEngineerQueries:
    """US2: 담당자 기반 질의 테스트."""

    # T025: Engineer query fixtures
    @pytest.fixture
    def engineer_data(self, db_connection):
        """담당자 쿼리용 fixture 데이터."""
        return {
            "engineers": ENGINEERS,
            "sample_engineer": "김철수",
            "monthly_sheet": "Monthly_Summary",
        }

    # T026: Query "김철수" returns only 김철수's data
    def test_query_specific_engineer(self, db_connection, engineer_data):
        """특정 담당자 조회 시 해당 담당자 데이터만 반환되는지 확인."""
        engineer = engineer_data["sample_engineer"]
        sheet = engineer_data["monthly_sheet"]

        result = db_connection.execute(f"""
            SELECT * FROM read_xlsx('{DATA_FILE}', sheet='{sheet}')
            WHERE "담당자" = '{engineer}'
        """).fetchdf()

        # 결과가 있고, 모든 담당자가 김철수인지 확인
        assert len(result) > 0, f"'{engineer}' 담당자 데이터가 없음"
        assert all(result["담당자"] == engineer), f"다른 담당자 데이터 포함됨"

    # T027: Query "이영희 담당 건" returns 이영희's data
    def test_query_engineer_cases(self, db_connection):
        """담당자 담당 건 조회 테스트."""
        engineer = "이영희"

        result = db_connection.execute(f"""
            SELECT COUNT(*) as cnt
            FROM read_xlsx('{DATA_FILE}', sheet='Monthly_Summary')
            WHERE "담당자" = '{engineer}'
        """).fetchone()

        # 이영희 담당 건수가 있어야 함
        assert result[0] > 0, f"'{engineer}' 담당 건이 없음"

    # T028: Query non-existent engineer returns empty
    def test_query_nonexistent_engineer(self, db_connection):
        """존재하지 않는 담당자 조회 시 빈 결과 반환."""
        fake_engineer = "홍길동_없는사람"

        result = db_connection.execute(f"""
            SELECT * FROM read_xlsx('{DATA_FILE}', sheet='Monthly_Summary')
            WHERE "담당자" = '{fake_engineer}'
        """).fetchdf()

        assert len(result) == 0, f"존재하지 않는 담당자 '{fake_engineer}'에 대한 데이터가 있음"


# =============================================================================
# Phase 5: US3 - 설비/장비 기반 질의 테스트 (T029-T032)
# =============================================================================

class TestEquipmentQueries:
    """US3: 설비/장비 기반 질의 테스트."""

    # T029: Equipment query fixtures
    @pytest.fixture
    def equipment_data(self):
        """설비 쿼리용 fixture 데이터."""
        return {
            "equipment_types": list(EQUIPMENT_TYPES.keys()),
            "cvd_full_name": EQUIPMENT_TYPES["CVD"],
            "sputter_korean": "Sputter",
            "etching_korean": "Etching",
        }

    # T030: Query "CVD" returns only CVD equipment data
    def test_query_cvd_equipment(self, db_connection, equipment_data):
        """CVD 설비 조회 시 CVD 데이터만 반환되는지 확인."""
        result = db_connection.execute(f"""
            SELECT * FROM read_xlsx('{DATA_FILE}', sheet='Equipment_CVD')
        """).fetchdf()

        assert len(result) > 0, "CVD 장비 데이터가 없음"
        # CVD 시트에는 모든 데이터가 CVD 관련
        assert all(result["설비유형"] == "CVD"), "CVD가 아닌 설비유형 포함됨"

    # T031: Query "스퍼터" returns Sputter equipment data
    def test_query_sputter_equipment(self, db_connection):
        """스퍼터 설비 조회 테스트."""
        result = db_connection.execute(f"""
            SELECT * FROM read_xlsx('{DATA_FILE}', sheet='Equipment_Sputter')
        """).fetchdf()

        assert len(result) > 0, "Sputter 장비 데이터가 없음"
        assert all(result["설비유형"] == "Sputter"), "Sputter가 아닌 설비유형 포함됨"

    # T032: Query "에칭 설비 현황" returns Etching data
    def test_query_etching_status(self, db_connection):
        """에칭 설비 현황 조회 테스트."""
        result = db_connection.execute(f"""
            SELECT "설비유형", "상태", COUNT(*) as cnt
            FROM read_xlsx('{DATA_FILE}', sheet='Equipment_Etching')
            GROUP BY "설비유형", "상태"
        """).fetchdf()

        assert len(result) > 0, "Etching 설비 현황 데이터가 없음"
        assert all(result["설비유형"] == "Etching"), "Etching이 아닌 설비유형 포함됨"


# =============================================================================
# Phase 6: US4 - 날짜/기간 기반 질의 테스트 (T033-T036)
# =============================================================================

class TestDateQueries:
    """US4: 날짜/기간 기반 질의 테스트."""

    # T033: Date query fixtures
    @pytest.fixture
    def date_data(self):
        """날짜 쿼리용 fixture 데이터."""
        return {
            "target_month": 12,
            "target_year": 2024,
            "daily_sheet": "Daily_20241217",
            "date_range_start": "2024-12-17",
            "date_range_end": "2024-12-23",
        }

    # T034: Query "12월" returns December data only
    def test_query_december_data(self, db_connection, date_data):
        """12월 데이터 조회 테스트."""
        result = db_connection.execute(f"""
            SELECT * FROM read_xlsx('{DATA_FILE}', sheet='Monthly_Summary')
            WHERE EXTRACT(MONTH FROM CAST("접수일자" AS DATE)) = 12
        """).fetchdf()

        # 12월 데이터가 있어야 함
        assert len(result) > 0, "12월 데이터가 없음"

    # T035: Query specific date returns that date's data
    def test_query_specific_date(self, db_connection, date_data):
        """특정 날짜 데이터 조회 테스트."""
        result = db_connection.execute(f"""
            SELECT * FROM read_xlsx('{DATA_FILE}', sheet='{date_data["daily_sheet"]}')
        """).fetchdf()

        assert len(result) > 0, f"{date_data['daily_sheet']} 시트 데이터가 없음"

    # T036: Query "최근 일주일" returns last 7 days data
    def test_query_last_week_data(self, db_connection, date_data):
        """최근 일주일 데이터 조회 테스트 (7개 Daily 시트)."""
        daily_sheets = [
            "Daily_20241217", "Daily_20241218", "Daily_20241219",
            "Daily_20241220", "Daily_20241221", "Daily_20241222", "Daily_20241223"
        ]

        total_rows = 0
        for sheet in daily_sheets:
            result = db_connection.execute(f"""
                SELECT COUNT(*) as cnt FROM read_xlsx('{DATA_FILE}', sheet='{sheet}')
            """).fetchone()
            total_rows += result[0]

        assert total_rows > 0, "최근 일주일 Daily 시트에 데이터가 없음"


# =============================================================================
# Phase 7: US5 - 복합 조건 질의 테스트 (T037-T039)
# =============================================================================

class TestComplexQueries:
    """US5: 복합 조건 질의 테스트."""

    # T037: Complex query fixtures
    @pytest.fixture
    def complex_data(self):
        """복합 조건 쿼리용 fixture 데이터."""
        return {
            "engineer": "김철수",
            "equipment_type": "CVD",
            "customer": "삼성전자",
            "month": 12,
        }

    # T038: Query "김철수 + 12월 + CVD" returns intersection
    def test_query_engineer_month_equipment(self, db_connection, complex_data):
        """담당자 + 월 + 설비유형 복합 조건 테스트."""
        result = db_connection.execute(f"""
            SELECT * FROM read_xlsx('{DATA_FILE}', sheet='Monthly_Summary')
            WHERE "담당자" = '{complex_data["engineer"]}'
              AND "설비유형" = '{complex_data["equipment_type"]}'
              AND EXTRACT(MONTH FROM CAST("접수일자" AS DATE)) = {complex_data["month"]}
        """).fetchdf()

        # 조건을 모두 만족하는 데이터 확인
        if len(result) > 0:
            assert all(result["담당자"] == complex_data["engineer"]), "담당자 조건 불일치"
            assert all(result["설비유형"] == complex_data["equipment_type"]), "설비유형 조건 불일치"

    # T039: Query "삼성전자 에칭 이번 달" returns correct filtered data
    def test_query_customer_equipment_month(self, db_connection):
        """고객사 + 설비 + 기간 복합 조건 테스트."""
        result = db_connection.execute(f"""
            SELECT * FROM read_xlsx('{DATA_FILE}', sheet='Customer_삼성전자')
            WHERE "설비유형" = 'Etching'
        """).fetchdf()

        # 삼성전자 고객 시트에서 에칭 설비 데이터 확인
        if len(result) > 0:
            assert all(result["고객사"] == "삼성전자"), "고객사 조건 불일치"
            assert all(result["설비유형"] == "Etching"), "설비유형 조건 불일치"


# =============================================================================
# Phase 8: US6 - 집계/통계 질의 테스트 (T040-T043)
# =============================================================================

class TestAggregationQueries:
    """US6: 집계/통계 질의 테스트."""

    # T040: Aggregation query fixtures
    @pytest.fixture
    def agg_data(self):
        """집계 쿼리용 fixture 데이터."""
        return {
            "monthly_sheet": "Monthly_Summary",
        }

    # T041: Query "설비별 건수" returns GROUP BY equipment_type result
    def test_query_count_by_equipment(self, db_connection, agg_data):
        """설비유형별 건수 집계 테스트."""
        result = db_connection.execute(f"""
            SELECT "설비유형", COUNT(*) as 건수
            FROM read_xlsx('{DATA_FILE}', sheet='{agg_data["monthly_sheet"]}')
            GROUP BY "설비유형"
            ORDER BY 건수 DESC
        """).fetchdf()

        assert len(result) > 0, "설비유형별 집계 결과가 없음"
        assert "설비유형" in result.columns, "설비유형 컬럼이 없음"
        assert "건수" in result.columns, "건수 컬럼이 없음"
        # 모든 설비유형에 대한 집계 확인
        assert len(result) >= 3, f"설비유형이 너무 적음: {len(result)}개"

    # T042: Query "담당자별 처리 현황" returns COUNT by engineer
    def test_query_count_by_engineer(self, db_connection, agg_data):
        """담당자별 처리 현황 집계 테스트."""
        result = db_connection.execute(f"""
            SELECT "담당자", COUNT(*) as 처리건수
            FROM read_xlsx('{DATA_FILE}', sheet='{agg_data["monthly_sheet"]}')
            GROUP BY "담당자"
            ORDER BY 처리건수 DESC
        """).fetchdf()

        assert len(result) > 0, "담당자별 집계 결과가 없음"
        # 여러 담당자가 있어야 함
        assert len(result) >= 5, f"담당자가 너무 적음: {len(result)}명"

    # T043: Query "고장 유형별 통계" returns distribution by issue_type
    def test_query_distribution_by_issue_type(self, db_connection, agg_data):
        """고장유형별 분포 통계 테스트."""
        result = db_connection.execute(f"""
            SELECT "고장유형", COUNT(*) as 건수,
                   ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as 비율
            FROM read_xlsx('{DATA_FILE}', sheet='{agg_data["monthly_sheet"]}')
            GROUP BY "고장유형"
            ORDER BY 건수 DESC
        """).fetchdf()

        assert len(result) > 0, "고장유형별 통계 결과가 없음"
        # 비율 합계가 100%인지 확인
        total_ratio = result["비율"].sum()
        assert abs(total_ratio - 100.0) < 1.0, f"비율 합계 오류: {total_ratio}%"


# =============================================================================
# Phase 9: Edge Cases (T044-T046)
# =============================================================================

class TestEdgeCases:
    """Edge case 테스트."""

    # T044: Korean sheet names with special characters
    def test_korean_sheet_names(self, db_connection):
        """한글 시트명 (특수문자 포함) 처리 테스트."""
        korean_sheets = ["Team_A팀", "Team_B팀", "Customer_삼성전자", "Customer_SK하이닉스"]

        for sheet in korean_sheets:
            try:
                result = db_connection.execute(f"""
                    SELECT COUNT(*) as cnt FROM read_xlsx('{DATA_FILE}', sheet='{sheet}')
                """).fetchone()
                assert result[0] > 0, f"한글 시트 '{sheet}' 읽기 실패"
            except Exception as e:
                pytest.fail(f"한글 시트 '{sheet}' 처리 오류: {e}")

    # T045: Partial name matching (김철 vs 김철수)
    def test_partial_name_matching(self, db_connection):
        """부분 이름 매칭 테스트 (LIKE 패턴)."""
        # 정확한 이름으로 조회
        exact_result = db_connection.execute(f"""
            SELECT COUNT(*) FROM read_xlsx('{DATA_FILE}', sheet='Monthly_Summary')
            WHERE "담당자" = '김철수'
        """).fetchone()

        # 부분 이름으로 조회 (LIKE 패턴)
        partial_result = db_connection.execute(f"""
            SELECT COUNT(*) FROM read_xlsx('{DATA_FILE}', sheet='Monthly_Summary')
            WHERE "담당자" LIKE '김철%'
        """).fetchone()

        # 부분 매칭이 정확한 매칭보다 같거나 많아야 함
        assert partial_result[0] >= exact_result[0], "부분 매칭 결과가 더 적음"

    # T046: Equipment abbreviation vs full name
    def test_equipment_abbreviation_vs_full_name(self, db_connection):
        """설비 약어 vs 전체 이름 처리 테스트."""
        # 약어로 조회 (CVD)
        abbrev_result = db_connection.execute(f"""
            SELECT COUNT(*) FROM read_xlsx('{DATA_FILE}', sheet='Equipment_CVD')
        """).fetchone()

        # 시트가 존재하고 데이터가 있어야 함
        assert abbrev_result[0] > 0, "CVD 약어 시트 데이터 없음"

        # 전체 이름 확인 (데이터 내 설비유형 컬럼)
        full_name_check = db_connection.execute(f"""
            SELECT DISTINCT "설비유형"
            FROM read_xlsx('{DATA_FILE}', sheet='Equipment_CVD')
        """).fetchone()

        # CVD가 약어로 저장되어 있음
        assert full_name_check[0] == "CVD", f"설비유형이 약어가 아님: {full_name_check[0]}"


# =============================================================================
# Additional Integration Tests
# =============================================================================

class TestCrossSheetConsistency:
    """시트 간 데이터 일관성 테스트."""

    def test_engineer_performance_matches_summary(self, db_connection):
        """Engineer_Performance 시트와 Monthly_Summary 일관성 확인."""
        # Monthly_Summary에서 담당자별 건수
        summary_counts = db_connection.execute(f"""
            SELECT "담당자", COUNT(*) as cnt
            FROM read_xlsx('{DATA_FILE}', sheet='Monthly_Summary')
            GROUP BY "담당자"
        """).fetchdf()

        # Engineer_Performance 시트 존재 확인
        perf_data = db_connection.execute(f"""
            SELECT * FROM read_xlsx('{DATA_FILE}', sheet='Engineer_Performance')
        """).fetchdf()

        assert len(perf_data) > 0, "Engineer_Performance 데이터가 없음"

        # 담당자 목록이 일치하는지 확인
        summary_engineers = set(summary_counts["담당자"].tolist())
        perf_engineers = set(perf_data["담당자"].tolist())

        assert summary_engineers == perf_engineers, "담당자 목록 불일치"

    def test_equipment_sheets_cover_all_types(self, db_connection):
        """Equipment_* 시트가 모든 설비유형을 커버하는지 확인."""
        equipment_sheets = [
            "Equipment_CVD", "Equipment_Etching", "Equipment_Sputter",
            "Equipment_Diffusion", "Equipment_CMP"
        ]

        covered_types = set()
        for sheet in equipment_sheets:
            result = db_connection.execute(f"""
                SELECT DISTINCT "설비유형"
                FROM read_xlsx('{DATA_FILE}', sheet='{sheet}')
            """).fetchone()
            if result:
                covered_types.add(result[0])

        # 최소 5개 설비유형이 커버되어야 함
        assert len(covered_types) >= 5, f"커버된 설비유형이 부족: {covered_types}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
