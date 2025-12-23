# Tasks: 테스트용 Excel 데이터 생성

**Input**: Design documents from `/specs/002-test-data-generation/`
**Prerequisites**: plan.md (required), spec.md (required)

**Tests**: 통합 테스트 포함 (시스템 검증이 주요 목적이므로)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/`, `scripts/` at repository root

---

## Phase 1: Setup (Project Infrastructure)

**Purpose**: 프로젝트 초기화 및 필수 구조 생성

- [x] T001 Create scripts/ directory at repository root
- [x] T002 [P] Create tests/unit/ directory structure
- [x] T003 [P] Create tests/integration/ directory structure
- [x] T004 Add openpyxl>=3.1.0, Faker>=21.0.0 (optional for Korean names) to requirements.txt

**Checkpoint**: 디렉토리 구조 및 의존성 준비 완료

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 데이터 생성을 위한 핵심 마스터 데이터 정의

**⚠️ CRITICAL**: 모든 User Story가 이 마스터 데이터에 의존함

- [x] T005 Define master data constants (ENGINEERS, EQUIPMENT_TYPES, ISSUE_TYPES, CUSTOMERS, STATUSES, TEAMS) in scripts/generate_test_data.py
- [x] T006 [P] [Depends: T005] Implement DataFactory class with ticket_id generator in scripts/generate_test_data.py
- [x] T007 [P] [Depends: T005] Implement random date generator (2024-10-01 ~ 2024-12-23 range) in scripts/generate_test_data.py
- [x] T008 [P] [Depends: T005] Implement equipment_id generator (EQ-{type}-{customer}-NNN format) in scripts/generate_test_data.py

**Checkpoint**: Foundation ready - 시트 생성 작업 시작 가능

---

## Phase 3: User Story 1 - 테스트용 Excel 파일 생성 (Priority: P1) 🎯 MVP

**Goal**: 30개 시트, ~3MB 크기의 테스트용 Excel 파일 생성

**Independent Test**: Excel 파일이 생성되고 DuckDB로 읽을 수 있으면 성공

### Implementation for User Story 1

- [x] T009 [US1] Implement generate_daily_sheet() for Daily_YYYYMMDD sheets (7개, 각 50-100행) in scripts/generate_test_data.py
- [x] T010 [US1] Implement generate_weekly_sheet() for Weekly_WNN sheets (4개, 각 200-300행) in scripts/generate_test_data.py
- [x] T011 [US1] Implement generate_monthly_sheet() for Monthly_Summary sheet (1개, 500행) in scripts/generate_test_data.py
- [x] T012 [P] [US1] Implement generate_equipment_sheet() for Equipment_* sheets (5개, 각 100-200행) in scripts/generate_test_data.py
- [x] T013 [P] [US1] Implement generate_team_sheet() for Team_* sheets (5개, 각 100-150행) in scripts/generate_test_data.py
- [x] T014 [P] [US1] Implement generate_customer_sheet() for Customer_* sheets (3개, 각 150-250행) in scripts/generate_test_data.py
- [x] T015 [P] [US1] Implement generate_status_sheet() for Status_* sheets (3개, 각 100-300행) in scripts/generate_test_data.py
- [x] T016 [P] [US1] Implement generate_parts_sheet() for Parts_Inventory sheet (1개, 200행) in scripts/generate_test_data.py
- [x] T017 [P] [US1] Implement generate_performance_sheet() for Engineer_Performance sheet (1개, 15행) in scripts/generate_test_data.py
- [x] T018a [US1] [Depends: T009-T017] Implement main() orchestration logic for sheet generation pipeline in scripts/generate_test_data.py
- [x] T018b [US1] Add error handling for individual sheet generation failures in scripts/generate_test_data.py
- [x] T018c [US1] Implement file size validation before saving to data/cs_daily_report.xlsx
- [x] T019 [US1] Add CLI argument parsing for output path customization in scripts/generate_test_data.py
- [x] T020 [US1] Run script and verify Excel file generation (30 sheets, 2-4MB) in data/cs_daily_report.xlsx

### Tests for User Story 1

- [x] T021 [P] [US1] Create test_data_generator.py with test for sheet count validation in tests/unit/test_data_generator.py
- [x] T022 [P] [US1] Add test for file size validation (2-4MB) in tests/unit/test_data_generator.py
- [x] T023 [P] [US1] Add test for DuckDB load compatibility using ExcelLoader in tests/unit/test_data_generator.py
- [x] T024 [P] [US1] Add test for data consistency (all engineers in ENGINEERS list) in tests/unit/test_data_generator.py

**Checkpoint**: Excel 파일 생성 완료, DuckDB 로드 검증 완료

---

## Phase 4: User Story 2 - 담당자 기반 질의 테스트 (Priority: P1)

**Goal**: "김철수가 뭘 했어?" 같은 담당자 기반 자연어 질의 검증

**Independent Test**: 담당자 이름으로 질문했을 때 해당 담당자의 데이터만 반환되면 성공

### Tests for User Story 2

- [x] T025 [US2] Create test_query_scenarios.py with engineer query fixtures in tests/integration/test_query_scenarios.py
- [x] T026 [US2] Add test: query "김철수" returns only 김철수's data in tests/integration/test_query_scenarios.py
- [x] T027 [US2] Add test: query "이영희 담당 건" returns 이영희's data in tests/integration/test_query_scenarios.py
- [x] T028 [US2] Add test: query non-existent engineer returns empty or error message in tests/integration/test_query_scenarios.py

**Checkpoint**: 담당자 기반 질의 90% 정확도 검증 ✅

---

## Phase 5: User Story 3 - 설비/장비 기반 질의 테스트 (Priority: P1)

**Goal**: "CVD 설비 고장 건" 같은 설비 유형 기반 질의 검증

**Independent Test**: 설비명/장비명으로 질문했을 때 관련 데이터만 반환되면 성공

### Tests for User Story 3

- [x] T029 [US3] Add equipment query fixtures in tests/integration/test_query_scenarios.py
- [x] T030 [US3] Add test: query "CVD" returns only CVD equipment data in tests/integration/test_query_scenarios.py
- [x] T031 [US3] Add test: query "스퍼터" returns Sputter equipment data in tests/integration/test_query_scenarios.py
- [x] T032 [US3] Add test: query "에칭 설비 현황" returns Etching data in tests/integration/test_query_scenarios.py

**Checkpoint**: 설비 기반 질의 90% 정확도 검증 ✅

---

## Phase 6: User Story 4 - 날짜/기간 기반 질의 테스트 (Priority: P2)

**Goal**: "이번 달 CS 건수" 같은 시간 기반 질의 검증

**Independent Test**: 기간 표현이 포함된 질문에 해당 기간 데이터만 반환되면 성공

### Tests for User Story 4

- [x] T033 [US4] Add date query fixtures in tests/integration/test_query_scenarios.py
- [x] T034 [US4] Add test: query "12월" returns December data only in tests/integration/test_query_scenarios.py
- [x] T035 [US4] Add test: query specific date returns that date's data in tests/integration/test_query_scenarios.py
- [x] T036 [US4] Add test: query "최근 일주일" returns last 7 days data in tests/integration/test_query_scenarios.py

**Checkpoint**: 날짜 기반 질의 85% 정확도 검증 ✅

---

## Phase 7: User Story 5 - 복합 조건 질의 테스트 (Priority: P2)

**Goal**: "김철수가 12월에 처리한 CVD 건" 같은 복합 조건 질의 검증

**Independent Test**: 여러 조건이 조합된 질문에 모든 조건을 만족하는 데이터만 반환

### Tests for User Story 5

- [x] T037 [US5] Add complex query fixtures in tests/integration/test_query_scenarios.py
- [x] T038 [US5] Add test: query "김철수 + 12월 + CVD" returns intersection of all conditions in tests/integration/test_query_scenarios.py
- [x] T039 [US5] Add test: query "삼성전자 에칭 이번 달" returns correct filtered data in tests/integration/test_query_scenarios.py

**Checkpoint**: 복합 조건 질의 80% 정확도 검증 ✅

---

## Phase 8: User Story 6 - 집계/통계 질의 테스트 (Priority: P2)

**Goal**: "설비별 고장 건수" 같은 집계성 질의 검증

**Independent Test**: 집계 질문에 그룹화된 통계 데이터가 반환되면 성공

### Tests for User Story 6

- [x] T040 [US6] Add aggregation query fixtures in tests/integration/test_query_scenarios.py
- [x] T041 [US6] Add test: query "설비별 건수" returns GROUP BY equipment_type result in tests/integration/test_query_scenarios.py
- [x] T042 [US6] Add test: query "담당자별 처리 현황" returns COUNT by engineer in tests/integration/test_query_scenarios.py
- [x] T043 [US6] Add test: query "고장 유형별 통계" returns distribution by issue_type in tests/integration/test_query_scenarios.py

**Checkpoint**: 집계 질의 85% 정확도 검증 ✅

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: 엣지 케이스 및 마무리 작업

- [x] T044 [P] Add edge case test: Korean sheet names with special characters in tests/integration/test_query_scenarios.py
- [x] T045 [P] Add edge case test: partial name matching (김철 vs 김철수) in tests/integration/test_query_scenarios.py
- [x] T046 [P] Add edge case test: equipment abbreviation vs full name (CVD vs Chemical Vapor Deposition) in tests/integration/test_query_scenarios.py
- [x] T047 Add __main__ block with usage instructions in scripts/generate_test_data.py
- [x] T048 Run all tests and verify success rate meets criteria in tests/

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - Excel 파일 생성
- **User Stories 2-6 (Phase 4-8)**: Depend on User Story 1 (테스트 데이터 필요)
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

```
US1 (Excel 생성) ──────────────────────────────────────────┐
     │                                                      │
     ▼                                                      ▼
US2 (담당자 질의) ──┬─── US3 (설비 질의) ──┬─── US4 (날짜 질의)
                   │                      │
                   └──────────────────────┴──────┐
                                                 │
                                                 ▼
                                    US5 (복합 조건) ──── US6 (집계)
```

### Within Each User Story

- 구현 → 테스트 순서 (테스트 먼저 아님 - 데이터 생성 특성상)
- Models/Utils → Sheet Generators → Main orchestration

### Parallel Opportunities

- Phase 1: T002, T003 동시 실행 가능
- Phase 3: T012-T017 (개별 시트 생성기) 동시 실행 가능
- Phase 4-6: 각 Phase 내 테스트들은 순차 실행 권장 (fixture 의존)
- Phase 9: T044-T046 동시 실행 가능

---

## Parallel Example: User Story 1 (Phase 3)

```bash
# Launch all sheet generators in parallel:
Task T012: "Implement generate_equipment_sheet()"
Task T013: "Implement generate_team_sheet()"
Task T014: "Implement generate_customer_sheet()"
Task T015: "Implement generate_status_sheet()"
Task T016: "Implement generate_parts_sheet()"
Task T017: "Implement generate_performance_sheet()"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (마스터 데이터)
3. Complete Phase 3: User Story 1 (Excel 생성)
4. **STOP and VALIDATE**: `python scripts/generate_test_data.py` 실행하여 파일 생성 확인
5. DuckDB 로드 테스트로 검증

### Incremental Delivery

1. Phase 1-2 완료 → Foundation ready
2. Phase 3 완료 → Excel 파일 생성 (MVP!)
3. Phase 4 완료 → 담당자 질의 검증
4. Phase 5 완료 → 설비 질의 검증
5. Phase 6-8 완료 → 고급 질의 검증
6. Phase 9 완료 → 엣지 케이스 커버

### Quick Start Commands

```bash
# 1. 의존성 설치
pip install openpyxl pandas

# 2. 데이터 생성
python scripts/generate_test_data.py

# 3. 테스트 실행
pytest tests/unit/test_data_generator.py -v
pytest tests/integration/test_query_scenarios.py -v
```

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- 이 프로젝트는 테스트 목적이므로 구현 → 테스트 순서 (TDD 아님)
- 모든 질의 테스트는 생성된 Excel 파일에 의존
- 각 User Story별 정확도 목표: 담당자/설비 90%, 날짜/집계 85%, 복합 80%
