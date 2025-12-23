# Implementation Plan: 테스트용 Excel 데이터 생성

**Branch**: `002-test-data-generation` | **Date**: 2025-12-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-test-data-generation/spec.md`

## Summary

반도체 설비 CS 데일리 리포트 형식의 테스트용 Excel 파일(30개 시트, ~3MB)을 생성하고, 이를 활용하여 Text-to-SQL 시스템의 자연어 질의 기능을 검증한다. Python openpyxl/pandas를 사용하여 현실적인 더미 데이터를 생성하고, 기존 ExcelLoader를 통해 DuckDB에 로드한 뒤 다양한 질의 패턴을 테스트한다.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: openpyxl, pandas, Faker (한국어 이름 생성)
**Storage**: Excel 파일 → DuckDB in-memory
**Testing**: pytest
**Target Platform**: Linux server (wonchatgpt)
**Project Type**: Single project
**Performance Goals**: 파일 생성 < 30초, 전체 시트 로드 < 5초
**Constraints**: 파일 크기 2~4MB, 시트 30개, 외부 API 사용 불가
**Scale/Scope**: 약 5,000~10,000 행 총 데이터

## Constitution Check

*GATE: Must pass before implementation*

| 원칙 | 상태 | 비고 |
|------|------|------|
| 기존 패턴 준수 | ✅ | 기존 src/services/, tests/ 구조 활용 |
| Pydantic 모델 사용 | ✅ | 테스트 데이터 생성용 모델 정의 |
| 로컬 전용 | ✅ | 외부 API 없이 순수 Python으로 생성 |
| 테스트 가능 | ✅ | pytest로 생성 결과 검증 |

## Project Structure

### Documentation (this feature)

```text
specs/002-test-data-generation/
├── spec.md              # 기능 명세
├── plan.md              # 이 파일
├── checklists/
│   └── requirements.md  # 품질 체크리스트
└── tasks.md             # 태스크 목록 (/speckit.tasks 생성)
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── schema.py        # 기존 (수정 불필요)
│   └── query.py         # 기존 (수정 불필요)
├── services/
│   ├── excel_loader.py  # 기존 (수정 불필요)
│   └── __init__.py
├── config.py            # 기존
└── main.py              # 기존

scripts/
└── generate_test_data.py  # 신규: 테스트 데이터 생성 스크립트

data/
├── sample.xlsx          # 기존 샘플
└── cs_daily_report.xlsx # 신규: 생성된 테스트 파일

tests/
├── unit/
│   └── test_data_generator.py  # 신규: 생성기 단위 테스트
└── integration/
    └── test_query_scenarios.py # 신규: 질의 시나리오 통합 테스트
```

**Structure Decision**: 테스트 데이터 생성은 독립 스크립트(`scripts/`)로 분리하여 재사용성 확보. 생성된 파일은 `data/`에 저장하여 기존 ExcelLoader와 호환.

## Architecture Design

### 컴포넌트 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    generate_test_data.py                     │
│                     (메인 생성 스크립트)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ DataConfig  │  │ DataFactory │  │ SheetGenerators     │  │
│  │             │  │             │  │ - DailySheet        │  │
│  │ - 담당자 목록 │  │ - 티켓 생성  │  │ - WeeklySheet       │  │
│  │ - 설비 유형  │  │ - 날짜 생성  │  │ - EquipmentSheet    │  │
│  │ - 고장 유형  │  │ - 랜덤 선택  │  │ - TeamSheet         │  │
│  │ - 고객사    │  │             │  │ - CustomerSheet     │  │
│  └─────────────┘  └─────────────┘  │ - StatusSheet       │  │
│                                    │ - PartsSheet        │  │
│                                    │ - PerformanceSheet  │  │
│                                    └─────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │  cs_daily_report.xlsx │
                │  (30개 시트, ~3MB)    │
                └─────────────────────┘
                           │
                           ▼
              ┌───────────────────────────┐
              │     ExcelLoader (기존)     │
              │  - load() → ExcelSchema   │
              │  - execute_query(sql)     │
              └───────────────────────────┘
                           │
                           ▼
              ┌───────────────────────────┐
              │   테스트 질의 실행         │
              │  - 담당자 기반 질의        │
              │  - 설비 기반 질의          │
              │  - 기간 기반 질의          │
              │  - 복합 조건 질의          │
              │  - 집계/통계 질의          │
              └───────────────────────────┘
```

### 데이터 생성 전략

#### 1. 마스터 데이터 정의

```python
# 담당자 (15명)
ENGINEERS = ["김철수", "이영희", "박민수", "정수진", "최동욱",
             "한지민", "오승환", "강예린", "윤성준", "임하늘",
             "조현우", "서지원", "남궁민", "황보람", "전인수"]

# 팀 배정
TEAMS = {
    "A팀": ["김철수", "이영희", "박민수"],
    "B팀": ["정수진", "최동욱", "한지민"],
    "C팀": ["오승환", "강예린", "윤성준"],
    "D팀": ["임하늘", "조현우", "서지원"],
    "E팀": ["남궁민", "황보람", "전인수"],
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
```

#### 2. 시트별 생성 로직

| 시트 그룹 | 시트 수 | 컬럼 구조 | 행 수 |
|----------|---------|----------|-------|
| Daily_YYYYMMDD | 7 | ticket_id, 접수일자, 고객사, 설비ID, 설비유형, 고장유형, 증상, 담당자, 상태, 조치내용, 완료일자, 소요시간 | 50-100 |
| Weekly_WNN | 4 | 동일 | 200-300 |
| Monthly_Summary | 1 | 동일 + 집계 컬럼 | 500 |
| Equipment_* | 5 | 설비ID, 설비명, 설비유형, 고객사, 설치일, 최근점검일, 누적고장건수, 주요고장이력 | 100-200 |
| Team_* | 5 | 담당자, 팀, 처리건수, 평균처리시간, 전문분야, 담당고객사 | 100-150 |
| Customer_* | 3 | ticket 기본 + 고객사별 필터 | 150-250 |
| Status_* | 3 | ticket 기본 + 상태별 필터 | 100-300 |
| Parts_Inventory | 1 | 부품코드, 부품명, 설비유형, 현재재고, 안전재고, 단가, 납품업체 | 200 |
| Engineer_Performance | 1 | 담당자, 팀, 처리건수, 평균처리시간, 고객만족도, 전문분야 | 15 |

#### 3. 데이터 일관성 보장

- **날짜 범위**: 2024-10-01 ~ 2024-12-23 (약 3개월)
- **티켓 ID 형식**: `CS-YYYYMMDD-NNNN` (일별 순번)
- **설비 ID 형식**: `EQ-{유형코드}-{고객코드}-NNN`
- **관계 무결성**: Daily 시트의 데이터가 Equipment, Team, Customer 시트에 일관되게 집계

### 테스트 시나리오 설계

#### 질의 유형별 SQL 변환 예상

| 자연어 질의 | 예상 SQL | 검증 포인트 |
|------------|----------|------------|
| "김철수가 뭘 했어?" | `SELECT * FROM Daily_* WHERE 담당자 = '김철수'` | 담당자 필터링 |
| "CVD 설비 고장 건" | `SELECT * FROM Daily_* WHERE 설비유형 = 'CVD'` | 설비유형 필터링 |
| "이번 주 CS 건" | `SELECT * FROM Weekly_W52` | 시트 선택 |
| "설비별 고장 건수" | `SELECT 설비유형, COUNT(*) FROM ... GROUP BY 설비유형` | 집계 연산 |
| "김철수가 12월에 처리한 CVD 건" | `SELECT * FROM ... WHERE 담당자='김철수' AND 설비유형='CVD' AND 접수일자 LIKE '2024-12%'` | 복합 조건 |

## Implementation Phases

### Phase 1: 데이터 생성 스크립트 (P1)

1. `scripts/generate_test_data.py` 생성
2. 마스터 데이터 정의 (담당자, 설비, 고장유형 등)
3. Daily 시트 생성 로직 구현
4. Weekly/Monthly 시트 생성 로직 구현
5. Equipment/Team/Customer/Status 시트 생성
6. Parts/Performance 시트 생성
7. Excel 파일 저장 (openpyxl)

### Phase 2: 생성 검증 테스트 (P1)

1. `tests/unit/test_data_generator.py` 생성
2. 파일 생성 검증 (시트 수, 크기)
3. 데이터 일관성 검증 (담당자, 설비 등 마스터 데이터 일치)
4. DuckDB 로드 검증

### Phase 3: 질의 시나리오 테스트 (P1)

1. `tests/integration/test_query_scenarios.py` 생성
2. 담당자 기반 질의 테스트
3. 설비 기반 질의 테스트
4. 기간 기반 질의 테스트

### Phase 4: 고급 질의 테스트 (P2)

1. 복합 조건 질의 테스트
2. 집계/통계 질의 테스트
3. 엣지 케이스 테스트

## Dependencies

### 신규 패키지

```txt
# requirements.txt 추가
openpyxl>=3.1.0    # Excel 파일 생성
Faker>=21.0.0      # 한국어 더미 데이터 (선택)
```

### 기존 활용

- `pandas`: DataFrame 생성 및 Excel 저장
- `duckdb`: 쿼리 실행
- `pydantic`: 모델 정의

## Risk Assessment

| 리스크 | 영향 | 완화 방안 |
|--------|------|----------|
| 파일 크기 초과 | 중 | 행 수 조절, 압축 고려 |
| 한글 시트명 인코딩 | 중 | openpyxl 한글 지원 확인, 영문 대체 |
| 날짜 형식 불일치 | 저 | ISO 형식(YYYY-MM-DD) 통일 |
| DuckDB 로드 실패 | 중 | 기존 ExcelLoader 테스트 활용 |

## Success Metrics

- [ ] 30개 시트 포함 Excel 파일 생성 (2-4MB)
- [ ] 모든 시트 DuckDB 로드 성공 (5초 이내)
- [ ] 담당자 기반 질의 10건 중 9건 성공
- [ ] 설비 기반 질의 10건 중 9건 성공
- [ ] 기간 기반 질의 10건 중 8건 성공
- [ ] 복합 조건 질의 10건 중 8건 성공
- [ ] 집계 질의 10건 중 8건 성공

## Complexity Tracking

> 이 기능은 단순 스크립트로 기존 아키텍처에 영향 없음

| 항목 | 복잡도 | 비고 |
|------|--------|------|
| 데이터 생성 스크립트 | 낮음 | 독립 실행 |
| 테스트 케이스 | 중간 | 다양한 질의 패턴 커버 필요 |
| 기존 코드 수정 | 없음 | 신규 파일만 추가 |
