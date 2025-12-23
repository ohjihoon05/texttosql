#!/usr/bin/env python3
"""
테스트용 Excel 데이터 생성 스크립트
반도체 설비 CS 데일리 리포트 형식의 Excel 파일(30개 시트, ~3MB)을 생성한다.
"""

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook


# =============================================================================
# T005: Master Data Constants
# =============================================================================

# 담당자 (15명)
ENGINEERS = [
    "김철수", "이영희", "박민수", "정수진", "최동욱",
    "한지민", "오승환", "강예린", "윤성준", "임하늘",
    "조현우", "서지원", "남궁민", "황보람", "전인수"
]

# 팀 배정
TEAMS = {
    "A팀": ["김철수", "이영희", "박민수"],
    "B팀": ["정수진", "최동욱", "한지민"],
    "C팀": ["오승환", "강예린", "윤성준"],
    "D팀": ["임하늘", "조현우", "서지원"],
    "E팀": ["남궁민", "황보람", "전인수"],
}

# 담당자 → 팀 매핑
ENGINEER_TO_TEAM = {
    engineer: team
    for team, engineers in TEAMS.items()
    for engineer in engineers
}

# 설비 유형 (8종)
EQUIPMENT_TYPES = {
    "CVD": "Chemical Vapor Deposition",
    "Etching": "에칭",
    "Sputter": "스퍼터링",
    "Diffusion": "확산로",
    "CMP": "Chemical Mechanical Polishing",
    "Ion Implant": "이온주입",
    "Cleaning": "세정",
    "Metrology": "계측",
}

# 고장 유형 (6종)
ISSUE_TYPES = ["H/W 고장", "S/W 오류", "센서 이상", "부품 마모", "정기점검", "긴급호출"]

# 고객사 (5개)
CUSTOMERS = ["삼성전자", "SK하이닉스", "마이크론", "인텔", "TSMC"]

# 상태 (4종)
STATUSES = ["접수", "진행중", "완료", "보류"]

# 증상 예시
SYMPTOMS = [
    "온도 이상 경보 발생",
    "진공도 저하",
    "파티클 카운트 증가",
    "압력 센서 오류",
    "가스 유량 이상",
    "전원 불안정",
    "웨이퍼 이송 오류",
    "RF 파워 저하",
    "냉각수 온도 상승",
    "알람 발생 빈번",
]

# 조치 내용 예시
ACTIONS = [
    "부품 교체 완료",
    "소프트웨어 업데이트",
    "센서 캘리브레이션",
    "정기 점검 완료",
    "긴급 조치 후 모니터링 중",
    "고객사 협의 후 일정 조율",
    "부품 발주 대기",
    "원격 진단 완료",
    "현장 출동 조치",
    "예방 정비 권고",
]

# 부품 목록
PARTS = [
    ("P001", "RF Generator", "CVD"),
    ("P002", "Vacuum Pump", "Etching"),
    ("P003", "Target Material", "Sputter"),
    ("P004", "Heater Element", "Diffusion"),
    ("P005", "Polishing Pad", "CMP"),
    ("P006", "Ion Source", "Ion Implant"),
    ("P007", "Filter Cartridge", "Cleaning"),
    ("P008", "Optical Sensor", "Metrology"),
    ("P009", "Mass Flow Controller", "CVD"),
    ("P010", "Chuck Assembly", "Etching"),
]


# =============================================================================
# T006: DataFactory Class
# =============================================================================

class DataFactory:
    """테스트 데이터 생성을 위한 팩토리 클래스"""

    def __init__(self, seed: int | None = None):
        """
        Args:
            seed: 랜덤 시드 (재현성을 위해)
        """
        if seed is not None:
            random.seed(seed)
        self._ticket_counters: dict[str, int] = {}
        self._equipment_counters: dict[str, int] = {}

    def generate_ticket_id(self, date: datetime) -> str:
        """티켓 ID 생성 (CS-YYYYMMDD-NNNN 형식)

        Args:
            date: 티켓 생성 날짜

        Returns:
            티켓 ID (예: CS-20241201-0001)
        """
        date_str = date.strftime("%Y%m%d")
        if date_str not in self._ticket_counters:
            self._ticket_counters[date_str] = 0
        self._ticket_counters[date_str] += 1
        return f"CS-{date_str}-{self._ticket_counters[date_str]:04d}"

    # T007: Random Date Generator
    def generate_random_date(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None
    ) -> datetime:
        """랜덤 날짜 생성 (2024-10-01 ~ 2024-12-23 기본 범위)

        Args:
            start_date: 시작 날짜 (기본: 2024-10-01)
            end_date: 종료 날짜 (기본: 2024-12-23)

        Returns:
            랜덤 날짜
        """
        if start_date is None:
            start_date = datetime(2024, 10, 1)
        if end_date is None:
            end_date = datetime(2024, 12, 23)

        delta = end_date - start_date
        random_days = random.randint(0, delta.days)
        return start_date + timedelta(days=random_days)

    # T008: Equipment ID Generator
    def generate_equipment_id(self, equipment_type: str, customer: str) -> str:
        """설비 ID 생성 (EQ-{유형코드}-{고객코드}-NNN 형식)

        Args:
            equipment_type: 설비 유형 (예: CVD, Etching)
            customer: 고객사 이름

        Returns:
            설비 ID (예: EQ-CVD-SS-001)
        """
        # 고객사 코드 매핑
        customer_codes = {
            "삼성전자": "SS",
            "SK하이닉스": "SK",
            "마이크론": "MC",
            "인텔": "IN",
            "TSMC": "TS",
        }

        # 설비 유형 코드 (첫 3글자)
        type_code = equipment_type[:3].upper()
        customer_code = customer_codes.get(customer, "XX")

        key = f"{type_code}-{customer_code}"
        if key not in self._equipment_counters:
            self._equipment_counters[key] = 0
        self._equipment_counters[key] += 1

        return f"EQ-{type_code}-{customer_code}-{self._equipment_counters[key]:03d}"

    def generate_processing_time(self) -> float:
        """처리 시간 생성 (0.5 ~ 8시간)"""
        return round(random.uniform(0.5, 8.0), 1)

    def random_choice(self, items: list[Any]) -> Any:
        """리스트에서 랜덤 선택"""
        return random.choice(items)

    def random_sample(self, items: list[Any], k: int) -> list[Any]:
        """리스트에서 k개 랜덤 샘플"""
        return random.sample(items, min(k, len(items)))


# =============================================================================
# Sheet Generators (T009-T017)
# =============================================================================

def generate_daily_sheet(factory: DataFactory, target_date: datetime, row_count: int | None = None) -> pd.DataFrame:
    """Daily_YYYYMMDD 시트 생성 (T009)

    Args:
        factory: DataFactory 인스턴스
        target_date: 대상 날짜
        row_count: 행 수 (기본: 150-300)

    Returns:
        DataFrame
    """
    if row_count is None:
        row_count = random.randint(150, 300)

    rows = []
    for _ in range(row_count):
        engineer = factory.random_choice(ENGINEERS)
        equipment_type = factory.random_choice(list(EQUIPMENT_TYPES.keys()))
        customer = factory.random_choice(CUSTOMERS)
        status = factory.random_choice(STATUSES)

        completed_date = None
        processing_time = None
        if status == "완료":
            completed_date = target_date + timedelta(hours=random.randint(1, 48))
            processing_time = factory.generate_processing_time()

        rows.append({
            "ticket_id": factory.generate_ticket_id(target_date),
            "접수일자": target_date.strftime("%Y-%m-%d"),
            "고객사": customer,
            "설비ID": factory.generate_equipment_id(equipment_type, customer),
            "설비유형": equipment_type,
            "고장유형": factory.random_choice(ISSUE_TYPES),
            "증상": factory.random_choice(SYMPTOMS),
            "담당자": engineer,
            "팀": ENGINEER_TO_TEAM[engineer],
            "상태": status,
            "조치내용": factory.random_choice(ACTIONS) if status in ["완료", "진행중"] else None,
            "완료일자": completed_date.strftime("%Y-%m-%d %H:%M") if completed_date else None,
            "소요시간": processing_time,
        })

    return pd.DataFrame(rows)


def generate_weekly_sheet(factory: DataFactory, week_num: int, year: int = 2024) -> pd.DataFrame:
    """Weekly_WNN 시트 생성 (T010)

    Args:
        factory: DataFactory 인스턴스
        week_num: 주차 번호 (1-52)
        year: 연도

    Returns:
        DataFrame (200-300행)
    """
    # 해당 주의 날짜 범위 계산
    first_day = datetime(year, 1, 1)
    start_of_week = first_day + timedelta(weeks=week_num - 1)

    row_count = random.randint(400, 600)
    all_rows = []

    for _ in range(row_count):
        day_offset = random.randint(0, 6)
        target_date = start_of_week + timedelta(days=day_offset)

        # 날짜가 범위를 벗어나면 조정
        if target_date > datetime(2024, 12, 23):
            target_date = datetime(2024, 12, 23)
        if target_date < datetime(2024, 10, 1):
            target_date = datetime(2024, 10, 1)

        engineer = factory.random_choice(ENGINEERS)
        equipment_type = factory.random_choice(list(EQUIPMENT_TYPES.keys()))
        customer = factory.random_choice(CUSTOMERS)
        status = factory.random_choice(STATUSES)

        completed_date = None
        processing_time = None
        if status == "완료":
            completed_date = target_date + timedelta(hours=random.randint(1, 48))
            processing_time = factory.generate_processing_time()

        all_rows.append({
            "ticket_id": factory.generate_ticket_id(target_date),
            "접수일자": target_date.strftime("%Y-%m-%d"),
            "주차": f"W{week_num:02d}",
            "고객사": customer,
            "설비ID": factory.generate_equipment_id(equipment_type, customer),
            "설비유형": equipment_type,
            "고장유형": factory.random_choice(ISSUE_TYPES),
            "증상": factory.random_choice(SYMPTOMS),
            "담당자": engineer,
            "팀": ENGINEER_TO_TEAM[engineer],
            "상태": status,
            "조치내용": factory.random_choice(ACTIONS) if status in ["완료", "진행중"] else None,
            "완료일자": completed_date.strftime("%Y-%m-%d %H:%M") if completed_date else None,
            "소요시간": processing_time,
        })

    return pd.DataFrame(all_rows)


def generate_monthly_sheet(factory: DataFactory) -> pd.DataFrame:
    """Monthly_Summary 시트 생성 (T011)

    Args:
        factory: DataFactory 인스턴스

    Returns:
        DataFrame (500행)
    """
    rows = []

    for _ in range(1000):
        target_date = factory.generate_random_date()
        engineer = factory.random_choice(ENGINEERS)
        equipment_type = factory.random_choice(list(EQUIPMENT_TYPES.keys()))
        customer = factory.random_choice(CUSTOMERS)
        status = factory.random_choice(STATUSES)

        completed_date = None
        processing_time = None
        if status == "완료":
            completed_date = target_date + timedelta(hours=random.randint(1, 72))
            processing_time = factory.generate_processing_time()

        rows.append({
            "ticket_id": factory.generate_ticket_id(target_date),
            "접수일자": target_date.strftime("%Y-%m-%d"),
            "월": target_date.strftime("%Y-%m"),
            "고객사": customer,
            "설비ID": factory.generate_equipment_id(equipment_type, customer),
            "설비유형": equipment_type,
            "고장유형": factory.random_choice(ISSUE_TYPES),
            "증상": factory.random_choice(SYMPTOMS),
            "담당자": engineer,
            "팀": ENGINEER_TO_TEAM[engineer],
            "상태": status,
            "조치내용": factory.random_choice(ACTIONS) if status in ["완료", "진행중"] else None,
            "완료일자": completed_date.strftime("%Y-%m-%d %H:%M") if completed_date else None,
            "소요시간": processing_time,
            "SLA_충족": "Y" if processing_time and processing_time < 4.0 else "N" if processing_time else None,
        })

    return pd.DataFrame(rows)


def generate_equipment_sheet(factory: DataFactory, equipment_type: str) -> pd.DataFrame:
    """Equipment_* 시트 생성 (T012)

    Args:
        factory: DataFactory 인스턴스
        equipment_type: 설비 유형

    Returns:
        DataFrame (100-200행)
    """
    row_count = random.randint(200, 400)
    rows = []

    for _ in range(row_count):
        customer = factory.random_choice(CUSTOMERS)
        install_date = datetime(2020, 1, 1) + timedelta(days=random.randint(0, 1500))
        last_maintenance = factory.generate_random_date()

        rows.append({
            "설비ID": factory.generate_equipment_id(equipment_type, customer),
            "설비명": f"{equipment_type}_{random.randint(1, 100):03d}",
            "설비유형": equipment_type,
            "설비상세": EQUIPMENT_TYPES[equipment_type],
            "고객사": customer,
            "설치일": install_date.strftime("%Y-%m-%d"),
            "최근점검일": last_maintenance.strftime("%Y-%m-%d"),
            "누적고장건수": random.randint(0, 50),
            "주요고장이력": factory.random_choice(ISSUE_TYPES),
            "상태": factory.random_choice(["정상", "점검중", "고장", "대기"]),
        })

    return pd.DataFrame(rows)


def generate_team_sheet(factory: DataFactory, team_name: str) -> pd.DataFrame:
    """Team_* 시트 생성 (T013)

    Args:
        factory: DataFactory 인스턴스
        team_name: 팀 이름

    Returns:
        DataFrame (100-150행)
    """
    row_count = random.randint(200, 350)
    rows = []

    team_members = TEAMS.get(team_name, ENGINEERS[:3])

    for _ in range(row_count):
        engineer = factory.random_choice(team_members)

        rows.append({
            "담당자": engineer,
            "팀": team_name,
            "처리건수": random.randint(10, 100),
            "평균처리시간": round(random.uniform(1.0, 6.0), 1),
            "전문분야": factory.random_choice(list(EQUIPMENT_TYPES.keys())),
            "담당고객사": factory.random_choice(CUSTOMERS),
            "고객만족도": round(random.uniform(3.5, 5.0), 1),
            "월": factory.generate_random_date().strftime("%Y-%m"),
        })

    return pd.DataFrame(rows)


def generate_customer_sheet(factory: DataFactory, customer: str) -> pd.DataFrame:
    """Customer_* 시트 생성 (T014)

    Args:
        factory: DataFactory 인스턴스
        customer: 고객사 이름

    Returns:
        DataFrame (150-250행)
    """
    row_count = random.randint(350, 500)
    rows = []

    for _ in range(row_count):
        target_date = factory.generate_random_date()
        engineer = factory.random_choice(ENGINEERS)
        equipment_type = factory.random_choice(list(EQUIPMENT_TYPES.keys()))
        status = factory.random_choice(STATUSES)

        completed_date = None
        processing_time = None
        if status == "완료":
            completed_date = target_date + timedelta(hours=random.randint(1, 48))
            processing_time = factory.generate_processing_time()

        rows.append({
            "ticket_id": factory.generate_ticket_id(target_date),
            "접수일자": target_date.strftime("%Y-%m-%d"),
            "고객사": customer,
            "설비ID": factory.generate_equipment_id(equipment_type, customer),
            "설비유형": equipment_type,
            "고장유형": factory.random_choice(ISSUE_TYPES),
            "담당자": engineer,
            "팀": ENGINEER_TO_TEAM[engineer],
            "상태": status,
            "조치내용": factory.random_choice(ACTIONS) if status in ["완료", "진행중"] else None,
            "완료일자": completed_date.strftime("%Y-%m-%d %H:%M") if completed_date else None,
            "소요시간": processing_time,
        })

    return pd.DataFrame(rows)


def generate_status_sheet(factory: DataFactory, status: str) -> pd.DataFrame:
    """Status_* 시트 생성 (T015)

    Args:
        factory: DataFactory 인스턴스
        status: 상태 (접수, 진행중, 완료, 보류)

    Returns:
        DataFrame (100-300행)
    """
    row_count = random.randint(300, 500)
    rows = []

    for _ in range(row_count):
        target_date = factory.generate_random_date()
        engineer = factory.random_choice(ENGINEERS)
        equipment_type = factory.random_choice(list(EQUIPMENT_TYPES.keys()))
        customer = factory.random_choice(CUSTOMERS)

        completed_date = None
        processing_time = None
        if status == "완료":
            completed_date = target_date + timedelta(hours=random.randint(1, 48))
            processing_time = factory.generate_processing_time()

        rows.append({
            "ticket_id": factory.generate_ticket_id(target_date),
            "접수일자": target_date.strftime("%Y-%m-%d"),
            "고객사": customer,
            "설비ID": factory.generate_equipment_id(equipment_type, customer),
            "설비유형": equipment_type,
            "고장유형": factory.random_choice(ISSUE_TYPES),
            "담당자": engineer,
            "팀": ENGINEER_TO_TEAM[engineer],
            "상태": status,
            "조치내용": factory.random_choice(ACTIONS) if status in ["완료", "진행중"] else None,
            "완료일자": completed_date.strftime("%Y-%m-%d %H:%M") if completed_date else None,
            "소요시간": processing_time,
        })

    return pd.DataFrame(rows)


def generate_parts_sheet(factory: DataFactory) -> pd.DataFrame:
    """Parts_Inventory 시트 생성 (T016)

    Args:
        factory: DataFactory 인스턴스

    Returns:
        DataFrame (200행)
    """
    rows = []
    suppliers = ["국내부품A", "국내부품B", "해외부품C", "해외부품D", "정품센터"]

    for i in range(400):
        part = factory.random_choice(PARTS)

        rows.append({
            "부품코드": f"{part[0]}_{i:03d}",
            "부품명": part[1],
            "설비유형": part[2],
            "현재재고": random.randint(0, 100),
            "안전재고": random.randint(5, 20),
            "단가": random.randint(10000, 5000000),
            "납품업체": factory.random_choice(suppliers),
            "리드타임": random.randint(1, 30),
            "최근입고일": factory.generate_random_date().strftime("%Y-%m-%d"),
        })

    return pd.DataFrame(rows)


def generate_performance_sheet(factory: DataFactory) -> pd.DataFrame:
    """Engineer_Performance 시트 생성 (T017)

    Args:
        factory: DataFactory 인스턴스

    Returns:
        DataFrame (15행 - 엔지니어 수)
    """
    rows = []

    for engineer in ENGINEERS:
        rows.append({
            "담당자": engineer,
            "팀": ENGINEER_TO_TEAM[engineer],
            "처리건수": random.randint(50, 200),
            "평균처리시간": round(random.uniform(1.0, 5.0), 1),
            "고객만족도": round(random.uniform(3.5, 5.0), 1),
            "전문분야": factory.random_choice(list(EQUIPMENT_TYPES.keys())),
            "담당고객사": ", ".join(factory.random_sample(CUSTOMERS, 2)),
            "인증자격": factory.random_choice(["전문", "숙련", "신입"]),
            "입사년도": random.randint(2015, 2023),
        })

    return pd.DataFrame(rows)


# =============================================================================
# T018a/b/c: Main Orchestration
# =============================================================================

def generate_all_sheets(factory: DataFactory) -> dict[str, pd.DataFrame]:
    """모든 시트 생성 오케스트레이션 (T018a)

    Args:
        factory: DataFactory 인스턴스

    Returns:
        시트명 -> DataFrame 딕셔너리
    """
    sheets: dict[str, pd.DataFrame] = {}
    errors: list[str] = []

    print("[INFO] Generating test data...")

    # Daily sheets (7개)
    print("  - Daily 시트 생성 중...")
    for i in range(7):
        target_date = datetime(2024, 12, 17) + timedelta(days=i)
        sheet_name = f"Daily_{target_date.strftime('%Y%m%d')}"
        try:
            sheets[sheet_name] = generate_daily_sheet(
                factory, target_date, random.randint(50, 100)
            )
        except Exception as e:
            errors.append(f"{sheet_name}: {e}")

    # Weekly sheets (4개)
    print("  - Weekly 시트 생성 중...")
    for week in [49, 50, 51, 52]:
        sheet_name = f"Weekly_W{week:02d}"
        try:
            sheets[sheet_name] = generate_weekly_sheet(factory, week)
        except Exception as e:
            errors.append(f"{sheet_name}: {e}")

    # Monthly summary (1개)
    print("  - Monthly 시트 생성 중...")
    try:
        sheets["Monthly_Summary"] = generate_monthly_sheet(factory)
    except Exception as e:
        errors.append(f"Monthly_Summary: {e}")

    # Equipment sheets (5개)
    print("  - Equipment 시트 생성 중...")
    equipment_types = list(EQUIPMENT_TYPES.keys())[:5]
    for eq_type in equipment_types:
        sheet_name = f"Equipment_{eq_type}"
        try:
            sheets[sheet_name] = generate_equipment_sheet(factory, eq_type)
        except Exception as e:
            errors.append(f"{sheet_name}: {e}")

    # Team sheets (5개)
    print("  - Team 시트 생성 중...")
    for team_name in TEAMS.keys():
        sheet_name = f"Team_{team_name}"
        try:
            sheets[sheet_name] = generate_team_sheet(factory, team_name)
        except Exception as e:
            errors.append(f"{sheet_name}: {e}")

    # Customer sheets (3개)
    print("  - Customer 시트 생성 중...")
    for customer in CUSTOMERS[:3]:
        sheet_name = f"Customer_{customer}"
        try:
            sheets[sheet_name] = generate_customer_sheet(factory, customer)
        except Exception as e:
            errors.append(f"{sheet_name}: {e}")

    # Status sheets (3개)
    print("  - Status 시트 생성 중...")
    for status in ["완료", "진행중", "보류"]:
        sheet_name = f"Status_{status}"
        try:
            sheets[sheet_name] = generate_status_sheet(factory, status)
        except Exception as e:
            errors.append(f"{sheet_name}: {e}")

    # Parts inventory (1개)
    print("  - Parts 시트 생성 중...")
    try:
        sheets["Parts_Inventory"] = generate_parts_sheet(factory)
    except Exception as e:
        errors.append(f"Parts_Inventory: {e}")

    # Engineer performance (1개)
    print("  - Performance 시트 생성 중...")
    try:
        sheets["Engineer_Performance"] = generate_performance_sheet(factory)
    except Exception as e:
        errors.append(f"Engineer_Performance: {e}")

    # T018b: Error handling
    if errors:
        print(f"\n[WARN] Some sheets failed to generate:")
        for err in errors:
            print(f"   - {err}")

    return sheets


def save_to_excel(sheets: dict[str, pd.DataFrame], output_path: Path) -> bool:
    """Excel 파일 저장 (T018c)

    Args:
        sheets: 시트명 -> DataFrame 딕셔너리
        output_path: 출력 파일 경로

    Returns:
        성공 여부
    """
    try:
        # 디렉토리 생성
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Excel 저장
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        # 파일 크기 검증 (T018c)
        file_size_mb = output_path.stat().st_size / (1024 * 1024)

        if file_size_mb < 0.3:
            print(f"[WARN] File size too small: {file_size_mb:.2f}MB")
        elif file_size_mb > 10.0:
            print(f"[WARN] File size too large: {file_size_mb:.2f}MB")
        else:
            print(f"[OK] File size valid: {file_size_mb:.2f}MB")

        return True

    except Exception as e:
        print(f"[ERROR] Failed to save file: {e}")
        return False


# =============================================================================
# T019: CLI Argument Parsing
# =============================================================================

def parse_args() -> argparse.Namespace:
    """CLI 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="반도체 설비 CS 데일리 리포트 테스트 데이터 생성"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="data/cs_daily_report.xlsx",
        help="출력 파일 경로 (기본: data/cs_daily_report.xlsx)"
    )
    parser.add_argument(
        "-s", "--seed",
        type=int,
        default=42,
        help="랜덤 시드 (기본: 42)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="상세 로깅 활성화"
    )
    return parser.parse_args()


# =============================================================================
# T047: __main__ block
# =============================================================================

if __name__ == "__main__":
    args = parse_args()

    print("=" * 60)
    print("[Generator] Semiconductor CS Daily Report Test Data")
    print("=" * 60)
    print(f"  Output: {args.output}")
    print(f"  Seed: {args.seed}")
    print()

    # 데이터 생성
    factory = DataFactory(seed=args.seed)
    sheets = generate_all_sheets(factory)

    print(f"\n[OK] Generated sheets: {len(sheets)}")

    # 파일 저장
    output_path = Path(args.output)
    if save_to_excel(sheets, output_path):
        print(f"\n[DONE] Saved to: {output_path.absolute()}")

        # 요약 출력
        total_rows = sum(len(df) for df in sheets.values())
        print(f"   - Total sheets: {len(sheets)}")
        print(f"   - Total rows: {total_rows:,}")
        print(f"   - File size: {output_path.stat().st_size / (1024*1024):.2f}MB")
    else:
        print("\n[FAIL] Generation failed")
        exit(1)
