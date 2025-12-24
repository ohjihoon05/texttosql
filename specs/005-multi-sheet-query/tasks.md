# Tasks: Multi-Sheet Query Support

**Input**: Design documents from `/specs/005-multi-sheet-query/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: 테스트 태스크 포함 (spec.md Phase 6에 테스트 요구사항 명시됨)

**Organization**: User Story 기준 구성 (독립적 구현/테스트 가능)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 실행 가능 (다른 파일, 의존성 없음)
- **[Story]**: 해당 User Story (US1, US2, US3)
- 모든 파일 경로 명시

---

## Phase 1: Setup (기반 인프라)

**Purpose**: 신규 모델 및 설정 파일 초기 구조

- [X] T001 Create `src/models/sheet_group.py` with base imports and docstring
- [X] T002 [P] Create `src/services/sheet_group_manager.py` with base class structure
- [X] T003 [P] Create `tests/unit/test_sheet_group_manager.py` with test class structure
- [X] T004 [P] Create `tests/unit/test_llm_router_union.py` with test class structure

---

## Phase 2: Foundational (핵심 모델 및 설정)

**Purpose**: 모든 User Story가 의존하는 핵심 구성요소

**⚠️ CRITICAL**: 이 Phase 완료 전까지 User Story 작업 불가

### Pydantic Models (data-model.md 기반)

- [X] T005 [P] Implement `QuestionType` and `UnionStrategy` Enums in `src/models/sheet_group.py`
- [X] T006 [P] Implement `SheetGroup` model with pattern matching in `src/models/sheet_group.py`
- [X] T007 [P] Implement `SheetGroupConfig` model with group management in `src/models/sheet_group.py`
- [X] T008 Implement `SheetSelection` and `MultiSheetContext` models in `src/models/sheet_group.py`
- [X] T009 Implement `UnionQueryResult` and `SheetResultSummary` models in `src/models/sheet_group.py`
- [X] T010 Export new models from `src/models/__init__.py`

### Configuration (config.py 확장)

- [X] T011 Add `SHEET_GROUP_PATTERNS` dict to `src/config.py`
- [X] T012 Add `MAX_UNION_SHEETS`, `DEFAULT_UNION_STRATEGY` settings to `src/config.py`
- [X] T013 Add `QUESTION_TYPE_SHEET_GROUPS` mapping to `src/config.py`

### SheetGroupManager Core (contracts/api.md 기반)

- [X] T014 Implement `classify_sheet()` method in `src/services/sheet_group_manager.py`
- [X] T015 Implement `get_sheets_by_group()` method in `src/services/sheet_group_manager.py`
- [X] T016 Implement `find_common_columns()` method in `src/services/sheet_group_manager.py`
- [X] T017 Implement unit tests for T014-T016 in `tests/unit/test_sheet_group_manager.py`

### Error Handling (contracts/api.md 기반)

- [X] T018 [P] Create exception classes in `src/exceptions.py` (NoCommonColumnsError, IncompatibleSheetsError, TooManySheetsError)

**Checkpoint**: 핵심 모델과 SheetGroupManager 기본 기능 완료

---

## Phase 3: User Story 1 - 담당자별 전체 업무 조회 (Priority: P1) 🎯 MVP

**Goal**: "김철수가 뭘 했어?" 질문 시 모든 관련 시트에서 담당자 데이터 통합 검색

**Independent Test**: "김철수가 뭘 했어?" 질문 → 5개+ 시트에서 100건+ 결과 반환

### Tests for User Story 1

- [ ] T019 [P] [US1] Write unit test for `select_relevant_sheets()` with person name in `tests/unit/test_sheet_group_manager.py`
- [ ] T020 [P] [US1] Write unit test for `create_multi_sheet_context()` with PERSON type in `tests/unit/test_sheet_group_manager.py`
- [ ] T021 [P] [US1] Write integration test for person query in `tests/integration/test_multi_sheet_query.py`

### Implementation for User Story 1

- [ ] T022 [US1] Implement `_detect_question_type()` helper for PERSON detection in `src/services/sheet_group_manager.py`
- [ ] T023 [US1] Implement `select_relevant_sheets()` for PERSON queries in `src/services/sheet_group_manager.py`
- [ ] T024 [US1] Implement `create_multi_sheet_context()` method in `src/services/sheet_group_manager.py`
- [ ] T025 [US1] Add UNION ALL Few-shot Example 1 (담당자 검색) to `src/services/llm_router.py`
- [ ] T026 [US1] Implement `generate_union_sql()` method in `src/services/llm_router.py`
- [ ] T027 [US1] Implement `should_use_multi_sheet()` method in `src/services/sql_agent.py`
- [ ] T028 [US1] Integrate SheetGroupManager into SQLAgent in `src/services/sql_agent.py`
- [ ] T029 [US1] Implement `execute_union_query()` in `src/services/excel_loader.py`
- [ ] T030 [US1] Add sheet source column (`source_sheet`) to UNION query results
- [ ] T031 [US1] Add result summary with sheet-wise counts in response

**Checkpoint**: US1 완료 - "김철수가 뭘 했어?" 질문으로 독립 테스트 가능

---

## Phase 4: User Story 2 - 기간별 업무 조회 (Priority: P2)

**Goal**: "이번 주 완료된 티켓" 질문 시 기간에 해당하는 시트에서 검색

**Independent Test**: "이번 주 완료된 티켓" 질문 → Weekly + Daily 시트 통합 검색

### Tests for User Story 2

- [ ] T032 [P] [US2] Write unit test for PERIOD question type detection in `tests/unit/test_sheet_group_manager.py`
- [ ] T033 [P] [US2] Write integration test for period query in `tests/integration/test_multi_sheet_query.py`

### Implementation for User Story 2

- [ ] T034 [US2] Add PERIOD type to `_detect_question_type()` in `src/services/sheet_group_manager.py`
- [ ] T035 [US2] Implement date/period extraction helper in `src/services/sheet_group_manager.py`
- [ ] T036 [US2] Implement sheet selection for PERIOD queries (date-matching logic) in `src/services/sheet_group_manager.py`
- [ ] T037 [US2] Add UNION ALL Few-shot Example 2 (기간 검색) to `src/services/llm_router.py`
- [ ] T038 [US2] Add date filter handling in `generate_union_sql()` in `src/services/llm_router.py`

**Checkpoint**: US2 완료 - "이번 주 완료된 티켓" 질문으로 독립 테스트 가능

---

## Phase 5: User Story 3 - 설비별 고장 이력 조회 (Priority: P2)

**Goal**: "CVD 설비 고장 이력" 질문 시 설비 관련 시트에서 검색

**Independent Test**: "CVD 설비 고장 이력" 질문 → TICKET 시트들에서 설비유형='CVD' 검색

### Tests for User Story 3

- [ ] T039 [P] [US3] Write unit test for EQUIPMENT question type detection in `tests/unit/test_sheet_group_manager.py`
- [ ] T040 [P] [US3] Write integration test for equipment query in `tests/integration/test_multi_sheet_query.py`

### Implementation for User Story 3

- [ ] T041 [US3] Add EQUIPMENT type to `_detect_question_type()` in `src/services/sheet_group_manager.py`
- [ ] T042 [US3] Implement equipment keyword extraction in `src/services/sheet_group_manager.py`
- [ ] T043 [US3] Implement sheet selection for EQUIPMENT queries in `src/services/sheet_group_manager.py`
- [ ] T044 [US3] Add UNION ALL Few-shot Example 3 (설비 검색) to `src/services/llm_router.py`

**Checkpoint**: US3 완료 - "CVD 설비 고장 이력" 질문으로 독립 테스트 가능

---

## Phase 6: Error Handling & Fallback

**Purpose**: 에러 처리 및 부분 실패 허용 로직 (EH-001 ~ EH-005)

- [ ] T045 [P] Implement SQL validation and retry logic (EH-001) in `src/services/llm_router.py`
- [ ] T046 [P] Implement VARCHAR auto-casting fallback (EH-002) in `src/services/excel_loader.py`
- [ ] T047 Implement individual sheet query fallback (EH-003) in `src/services/sql_agent.py`
- [ ] T048 Implement LLM server fallback to local model (EH-004) in `src/services/llm_router.py`
- [ ] T049 Implement partial failure handling (EH-005) in `src/services/sql_agent.py`
- [ ] T050 Add comprehensive logging for multi-sheet queries (FR-013) in `src/services/sql_agent.py`

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 성능 최적화, 엣지 케이스, 문서화

- [ ] T051 [P] Implement result limit (100건) and pagination message (FR-007) in `src/services/sql_agent.py`
- [ ] T052 [P] Implement empty result handling with sheet list (FR-008) in `src/services/sql_agent.py`
- [ ] T053 [P] Implement metadata caching for sheets (FR-011) in `src/services/sheet_group_manager.py`
- [ ] T054 Add performance test for SC-003 (10초 이내 응답) in `tests/integration/test_multi_sheet_query.py`
- [ ] T055 [P] Add edge case tests (1000+ results, empty result, column mismatch) in `tests/unit/test_sheet_group_manager.py`
- [ ] T056 Update `src/models/query.py` with multi-sheet context fields
- [ ] T057 Run and validate `specs/005-multi-sheet-query/quickstart.md` scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup (T001-T004)
    ↓
Phase 2: Foundational (T005-T018) [BLOCKS ALL USER STORIES]
    ↓
    ├─→ Phase 3: US1 (T019-T031) - MVP 🎯
    │       ↓
    ├─→ Phase 4: US2 (T032-T038) - can start after Phase 2, may use US1 components
    │       ↓
    ├─→ Phase 5: US3 (T039-T044) - can start after Phase 2, may use US1 components
    ↓
Phase 6: Error Handling (T045-T050) - after all US complete
    ↓
Phase 7: Polish (T051-T057) - final phase
```

### User Story Dependencies

- **US1 (P1)**: Phase 2 완료 후 독립 실행 가능
- **US2 (P2)**: Phase 2 완료 후 실행 가능, US1 `generate_union_sql()` 재사용
- **US3 (P2)**: Phase 2 완료 후 실행 가능, US1 `generate_union_sql()` 재사용

### Within Each User Story

1. Tests FIRST (fail 확인)
2. Helper methods
3. Main implementation
4. Integration with existing services
5. Verify tests pass

### Parallel Opportunities

**Phase 1**: T001, T002, T003, T004 동시 실행 가능

**Phase 2**:
- T005, T006, T007 동시 실행 가능 (Enum + 개별 모델)
- T011, T012, T013 동시 실행 가능 (config 독립 섹션)
- T018 독립 실행 가능

**User Stories**: US1 완료 후 US2, US3 동시 실행 가능

---

## Parallel Example: Phase 2 Foundational

```bash
# Launch models in parallel:
Task: "Implement QuestionType and UnionStrategy Enums in src/models/sheet_group.py"
Task: "Implement SheetGroup model with pattern matching in src/models/sheet_group.py"
Task: "Implement SheetGroupConfig model with group management in src/models/sheet_group.py"

# Launch config in parallel:
Task: "Add SHEET_GROUP_PATTERNS dict to src/config.py"
Task: "Add MAX_UNION_SHEETS, DEFAULT_UNION_STRATEGY settings to src/config.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. ✅ Phase 1: Setup (T001-T004)
2. ✅ Phase 2: Foundational (T005-T018)
3. ✅ Phase 3: User Story 1 (T019-T031)
4. **STOP and VALIDATE**: "김철수가 뭘 했어?" 테스트
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → 핵심 인프라 완료
2. User Story 1 → "담당자별 조회" 기능 (MVP!)
3. User Story 2 → "기간별 조회" 추가
4. User Story 3 → "설비별 조회" 추가
5. Error Handling → 안정성 강화
6. Polish → 성능/엣지케이스

---

## Summary

| Phase | Task Count | Key Deliverable |
|-------|------------|-----------------|
| Phase 1: Setup | 4 | 파일 구조 |
| Phase 2: Foundational | 14 | 모델, 설정, 핵심 서비스 |
| Phase 3: US1 (MVP) | 13 | 담당자별 다중 시트 쿼리 |
| Phase 4: US2 | 7 | 기간별 다중 시트 쿼리 |
| Phase 5: US3 | 6 | 설비별 다중 시트 쿼리 |
| Phase 6: Error Handling | 6 | Fallback 및 로깅 |
| Phase 7: Polish | 7 | 성능, 엣지케이스, 문서 |
| **Total** | **57** | |

### MVP Scope (Recommended)

**Phase 1-3만 완료 (31 tasks)** → "김철수가 뭘 했어?" 질문으로 다중 시트 UNION ALL 쿼리 동작 검증

### Format Validation

✅ 모든 태스크: `- [ ] [TaskID] [P?] [Story?] Description with file path` 형식 준수
✅ 모든 태스크에 파일 경로 포함
✅ User Story 태스크에 [US1], [US2], [US3] 라벨 포함
✅ 병렬 가능 태스크에 [P] 마커 포함
