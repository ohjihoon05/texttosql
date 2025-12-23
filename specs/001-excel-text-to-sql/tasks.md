# Tasks: Excel Text-to-SQL System

**Feature**: 001-excel-text-to-sql
**Generated**: 2024-12-23
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

---

## Phase 1: Setup

**Goal**: 프로젝트 구조 및 개발 환경 설정

- [X] T001 [P] Create project directory structure per plan.md in src/, tests/, data/
- [X] T002 [P] Create requirements.txt with all dependencies in ./requirements.txt
- [X] T003 [P] Create .env.example with configuration template in ./.env.example
- [X] T004 [P] Create config.py with Settings class in src/config.py
- [X] T005 [P] Create __init__.py files for all packages in src/
- [X] T005a Create pyproject.toml with ruff + pytest config in ./pyproject.toml
- [X] T005b Create pytest.ini and tests/conftest.py in tests/

**Exit Criteria**:
- [ ] `pip install -r requirements.txt` 성공
- [ ] `python -c "from src.config import Settings"` 성공
- [ ] `pytest --version` 실행 가능

---

## Phase 2: Foundational (Core Models)

**Goal**: 핵심 데이터 모델 구현 (모든 User Story에서 사용)

- [X] T006 Create ColumnInfo and SheetSchema models in src/models/schema.py
- [X] T007 Create ExcelSchema model with validation in src/models/schema.py
- [X] T008 [P] Create QueryContext and SQLQuery models in src/models/query.py
- [X] T009 [P] Create QueryResult and FormattedResponse models in src/models/query.py
- [X] T010 Create CacheEntry model in src/models/query.py
- [X] T011 Create models __init__.py with exports in src/models/__init__.py

**Exit Criteria**:
- [X] `from src.models import ExcelSchema, QueryContext, QueryResult` 성공
- [X] Pydantic 검증 동작 확인

---

## Phase 2.5: Model Unit Tests

**Goal**: 핵심 모델에 대한 단위 테스트

- [X] T011a Create test_schema.py with ExcelSchema tests in tests/unit/test_schema.py
- [X] T011b Create test_query.py with QueryContext/QueryResult tests in tests/unit/test_query.py
- [X] T011c [P] Add invalid data validation tests in tests/unit/

**Exit Criteria**:
- [X] `pytest tests/unit/test_schema.py -v` 통과 (27 tests)
- [X] `pytest tests/unit/test_query.py -v` 통과 (32 tests)
- [X] Invalid 데이터 입력 시 ValidationError 발생 확인

---

## Phase 3: User Story 1 - 기본 Text-to-SQL (MVP)

**Story**: CS 담당자가 Excel 데이터를 자연어로 질의할 수 있다

**Independent Test Criteria**:
- Excel 업로드 → 스키마 표시
- 자연어 질문 → SQL 생성 → 결과 표시

### Services

- [X] T012 [US1] Create ExcelLoader class skeleton in src/services/excel_loader.py
- [X] T013 [US1] Implement load() method with DuckDB in src/services/excel_loader.py
- [X] T014 [US1] Implement get_schema() method in src/services/excel_loader.py
- [X] T015 [US1] Implement execute_query() method in src/services/excel_loader.py
- [X] T016 [P] [US1] Create LLMRouter class skeleton in src/services/llm_router.py
- [X] T017 [US1] Implement generate_sql() with langchain_ollama in src/services/llm_router.py
- [X] T018 [P] [US1] Create SQLAgent class in src/services/sql_agent.py
- [X] T019 [US1] Implement ask() method combining loader and LLM in src/services/sql_agent.py

### UI Layer

- [X] T020 [US1] Create Chainlit main.py with on_chat_start in src/main.py
- [X] T021 [US1] Implement file upload handler in src/main.py
- [X] T022 [US1] Implement on_message handler for queries in src/main.py
- [X] T023 [US1] Add result formatting as markdown table in src/main.py

### Integration

- [X] T024 [P] [US1] Create sample.xlsx test file in data/sample.xlsx
- [ ] T025 [US1] Manual E2E test: upload → query → result

**Exit Criteria**:
- [ ] `chainlit run src/main.py` 실행 성공
- [ ] 샘플 Excel 업로드 후 스키마 표시 (< 3초)
- [ ] "김철수 검색" 질문 → 정확한 결과 반환 (< 10초)
- [ ] 결과가 markdown table 형식으로 표시됨

---

## Phase 3.5: Service Unit Tests

**Goal**: 핵심 서비스에 대한 단위 테스트

### ExcelLoader Tests

- [X] T025a Create test_excel_loader.py in tests/unit/test_excel_loader.py
  - [X] test_load_valid_excel()
  - [X] test_load_invalid_file()
  - [X] test_get_schema()
  - [X] test_execute_query_success()
  - [X] test_execute_query_invalid_sql()

### LLMRouter Tests (Deferred - requires LLM connection)

- [ ] T025b Create test_llm_router.py in tests/unit/test_llm_router.py
  - [ ] test_generate_sql_success()
  - [ ] test_generate_sql_with_mock()
  - [ ] test_health_check()

### SQLAgent Tests (Deferred - requires LLM connection)

- [ ] T025c Create test_sql_agent.py in tests/unit/test_sql_agent.py
  - [ ] test_ask_basic_query()
  - [ ] test_ask_returns_formatted_result()

### Edge Case Tests

- [X] T025d [P] Create test_edge_cases.py in tests/unit/test_excel_loader.py
  - [X] test_empty_excel()
  - [X] test_unicode_sheet_names()
  - [X] test_zero_results_query()

**Exit Criteria**:
- [X] `pytest tests/unit/ -v` 전체 통과 (78 tests)
- [ ] `pytest tests/unit/ --cov=src/services --cov-report=term` 커버리지 > 70%

---

## Phase 4: User Story 2 - Schema Filtering (성능 개선)

**Story**: 30개 시트 중 질문과 관련된 5개만 선택하여 LLM 토큰 절약

**Independent Test Criteria**:
- 30개 시트 Excel → 질문 시 5개 시트만 컨텍스트에 포함

### Services

- [ ] T026 [US2] Create SchemaFilter class skeleton in src/services/schema_filter.py
- [ ] T027 [US2] Implement keyword extraction (basic) in src/services/schema_filter.py
- [ ] T028 [US2] Implement relevance scoring logic in src/services/schema_filter.py
- [ ] T029 [US2] Implement filter_relevant() method in src/services/schema_filter.py
- [ ] T030 [US2] Implement generate_context() for LLM prompt in src/services/schema_filter.py

### Integration

- [ ] T031 [US2] Integrate SchemaFilter into SQLAgent in src/services/sql_agent.py
- [ ] T032 [US2] Add logging for filtered sheets in src/services/sql_agent.py

**Exit Criteria**:
- [ ] 30개 시트 Excel → 질문과 관련된 시트 5개 이하만 선택 (로그 확인)
- [ ] LLM 프롬프트 토큰 수 70% 이상 감소 (30→5개 시트 기준)

---

## Phase 5: User Story 3 - Query Cache (응답 속도)

**Story**: 반복 질문 시 캐시에서 즉시 응답 (< 2초)

**Independent Test Criteria**:
- 동일 질문 재질의 시 캐시 히트
- 캐시 히트 시 < 2초 응답

### Services

- [ ] T033 [US3] Create QueryCache class skeleton in src/services/query_cache.py
- [ ] T034 [US3] Implement SQLite cache table initialization in src/services/query_cache.py
- [ ] T035 [US3] Implement get() method with hash lookup in src/services/query_cache.py
- [ ] T036 [US3] Implement set() method with TTL in src/services/query_cache.py
- [ ] T037 [US3] Implement invalidate_all() for file change in src/services/query_cache.py
- [ ] T038 [P] [US3] Add in-memory cache layer (LRU) in src/services/query_cache.py

### Integration

- [ ] T039 [US3] Integrate QueryCache into SQLAgent in src/services/sql_agent.py
- [ ] T040 [US3] Add cache hit/miss logging in src/services/sql_agent.py

**Exit Criteria**:
- [ ] 동일 질문 재질의 시 캐시 히트 확인 (로그)
- [ ] 캐시 히트 응답 시간 < 2초
- [ ] 캐시 DB 파일 생성 확인 (data/cache.db)
- [ ] LRU eviction 동작 확인 (max_size=100 초과 시)

---

## Phase 6: User Story 4 - Streaming Response (UX 개선)

**Story**: 긴 응답 시 점진적으로 표시하여 대기 시간 체감 감소

**Independent Test Criteria**:
- LLM 응답이 청크 단위로 표시됨

### Services

- [ ] T041 [US4] Add stream_response() method to LLMRouter in src/services/llm_router.py
- [ ] T042 [US4] Implement async generator for streaming in src/services/llm_router.py

### UI Layer

- [ ] T043 [US4] Update on_message to use streaming in src/main.py
- [ ] T044 [US4] Add progress indicator during SQL generation in src/main.py

**Exit Criteria**:
- [ ] >500자 응답 시 청크 단위로 점진적 출력
- [ ] 첫 청크 응답 시간 < 2초 (TTFT)
- [ ] Progress indicator "SQL 생성 중..." 표시

---

## Phase 7: User Story 5 - Error Handling (안정성)

**Story**: 에러 발생 시 명확한 메시지 표시 및 복구

**Independent Test Criteria**:
- 각 에러 타입별 적절한 메시지 표시

### Error Handling

- [ ] T045 [US5] Create custom exception classes in src/utils/exceptions.py
- [ ] T046 [US5] Add error handling to ExcelLoader in src/services/excel_loader.py
- [ ] T047 [US5] Add error handling to LLMRouter in src/services/llm_router.py
- [ ] T048 [US5] Add error handling to SQLAgent in src/services/sql_agent.py
- [ ] T049 [US5] Update on_message with try/except in src/main.py
- [ ] T050 [US5] Implement user-friendly error messages in src/main.py

**Exit Criteria**:
- [ ] 각 에러 코드(E001-E009)에 대한 적절한 메시지 확인

---

## Phase 8: User Story 6 - RAG Terminology (Phase 3)

**Story**: 반도체 전문 용어를 인식하여 SQL 생성 정확도 향상

**Independent Test Criteria**:
- "ASM 설비" 질문 시 정확한 필터링

### RAG System

- [ ] T051 [US6] Create terminology.json with sample terms in data/terminology.json
- [ ] T052 [US6] Create embeddings.py with local model in src/rag/embeddings.py
- [ ] T053 [US6] Create terminology.py with ChromaDB setup in src/rag/terminology.py
- [ ] T054 [US6] Implement term lookup method in src/rag/terminology.py
- [ ] T055 [US6] Integrate terminology hints into QueryContext in src/services/sql_agent.py

**Exit Criteria**:
- [ ] 전문 용어 포함 질문 시 정확도 향상 확인

---

## Phase 9: User Story 7 - LLM Fallback (Phase 3)

**Story**: 원격 LLM 장애 시 로컬 모델로 자동 전환

**Independent Test Criteria**:
- 원격 LLM 타임아웃 시 fallback 동작

### Fallback Logic

- [ ] T056 [US7] Add retry logic with exponential backoff in src/services/llm_router.py
- [ ] T057 [US7] Add fallback LLM configuration in src/services/llm_router.py
- [ ] T058 [US7] Implement automatic fallback switching in src/services/llm_router.py
- [ ] T059 [US7] Add fallback status indicator in UI in src/main.py

**Exit Criteria**:
- [ ] 원격 LLM 차단 시 fallback 자동 전환 확인

---

## Phase 10: Polish & Cross-Cutting

**Goal**: 코드 정리, 문서화, 품질 검증

### Documentation
- [ ] T060 Add docstrings to all public methods
- [ ] T061 Create README.md with usage instructions in ./README.md

### Quality Gates
- [ ] T062 [P] Run ruff check and fix linting issues
- [ ] T063 [P] Run ruff format for code formatting
- [ ] T064 Create .gitignore with common patterns in ./.gitignore
- [ ] T064a Run pytest with coverage report (target: >75%)
- [ ] T064b [P] Create pre-commit config in .pre-commit-config.yaml

**Exit Criteria**:
- [ ] `ruff check src/` 에러 없음
- [ ] `pytest tests/ --cov=src --cov-fail-under=75` 통과
- [ ] README.md 완성
- [ ] pre-commit hooks 설치 및 동작 확인

---

## Dependencies Graph

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Models)
    │
    ▼
Phase 2.5 (Model Tests)
    │
    ▼
Phase 3 (US1: MVP)
    │
    ▼
Phase 3.5 (Service Tests)
    │
    ├──▶ Phase 4 (US2: Schema Filter)
    │
    ├──▶ Phase 5 (US3: Query Cache)
    │
    ├──▶ Phase 6 (US4: Streaming) ◄── Phase 3 (LLMRouter 의존)
    │
    ├──▶ Phase 7 (US5: Error Handling)
    │
    └──▶ Phase 8 (US6: RAG) ──▶ Phase 9 (US7: Fallback)
                                      │
                                      ▼
                              Phase 10 (Polish)
```

**Note**: Phase 4-7은 Phase 3.5 완료 후 병렬 진행 가능

## Parallel Execution Opportunities

### Phase 1
- T001 || T002 || T003 (디렉토리, requirements, .env - 독립적)
- T004 (config.py) || T005 (__init__.py)
- T005a || T005b (pyproject.toml || pytest 설정)

### Phase 2
- T006 || T010 (서로 다른 모델 파일)
- T008 (QueryContext) || T009 (QueryResult)

### Phase 2.5
- T011a || T011b (schema tests || query tests)

### Phase 3
- T016 (LLMRouter) || T018 (SQLAgent) after T015
- T020 || T021 || T022 (UI 핸들러들)
- T024 (sample.xlsx) - 구현과 독립적, 먼저 시작 가능

### Phase 3.5
- T025a || T025b || T025c (각 서비스 테스트 독립)
- T025d (edge cases) 독립 진행 가능

### Phase 5
- T033-T037 (SQLite) || T038 (LRU) 병렬 구현 후 통합

### Phase 8
- T051 (terminology.json) || T052 (embeddings.py)

### Phase 10
- T062 (lint) || T063 (format)

---

## Summary

| Phase | Story | Task Count | Parallelizable |
|-------|-------|------------|----------------|
| 1 | Setup | 7 | 5 |
| 2 | Foundational | 6 | 2 |
| 2.5 | Model Tests | 3 | 2 |
| 3 | US1: MVP | 14 | 6 |
| 3.5 | Service Tests | 4 | 4 |
| 4 | US2: Schema Filter | 7 | 0 |
| 5 | US3: Query Cache | 8 | 2 |
| 6 | US4: Streaming | 4 | 0 |
| 7 | US5: Error Handling | 6 | 0 |
| 8 | US6: RAG | 5 | 2 |
| 9 | US7: Fallback | 4 | 0 |
| 10 | Polish | 7 | 3 |
| **Total** | | **75** | **26** |

---

## MVP Scope (Recommended)

**Phase 1 + 2 + 2.5 + 3 + 3.5 구현 시 MVP 완성 (테스트 포함)**

- 총 34개 태스크
- 핵심 기능: Excel 업로드 → 자연어 질문 → SQL 결과
- 테스트 커버리지: > 70%

**Phase 4-7 추가 시 Production Ready**

- 총 59개 태스크
- 추가 기능: 캐싱, 스트리밍, 에러 핸들링, 스키마 필터링

---

## Future: Security (Phase 11)

> 보안 관련 태스크는 Production 이후 별도 Phase로 진행

- [ ] T070 Input validation (SQL injection 방어)
- [ ] T071 File upload validation (확장자, 크기, MIME)
- [ ] T072 Cache encryption (민감 데이터)
- [ ] T073 Security audit (bandit, safety)
