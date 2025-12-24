# Implementation Plan: Multi-Sheet Query Support

**Branch**: `005-multi-sheet-query` | **Date**: 2024-12-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-multi-sheet-query/spec.md`

## Summary

현재 단일 시트만 쿼리하는 Text-to-SQL 시스템을 확장하여 여러 시트에서 UNION ALL을 통해 통합 쿼리할 수 있도록 개선한다. 핵심 기술 접근:
1. **시트 그룹 관리자** (SheetGroupManager): 시트를 논리적 그룹으로 분류하고 공통 컬럼 분석
2. **질문 유형 분류기**: 담당자/기간/설비/통계 질문 유형 식별
3. **UNION ALL 쿼리 생성**: LLM 프롬프트에 Few-shot 예제 추가하여 다중 시트 SQL 생성

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: LangChain, langchain-ollama, Chainlit, Pydantic, DuckDB
**Storage**: DuckDB (in-memory), SQLite (cache)
**Testing**: pytest
**Target Platform**: Linux server (192.168.20.83)
**Project Type**: single (CLI/Web hybrid with Chainlit UI)
**Performance Goals**: P95 < 10s, P50 < 5s, UNION 5개 시트 < 3s
**Constraints**: LLM 응답 < 3s, 메모리 증가 < 100MB, 최대 10개 시트 UNION
**Scale/Scope**: 30개 시트, 시트당 최대 1000행, 총 5000+ rows 처리

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| 기존 코드 스타일 준수 | ✅ PASS | 기존 서비스 패턴 (ExcelLoader, LLMRouter) 따름 |
| Pydantic 모델 사용 | ✅ PASS | SheetGroup, SheetGroupConfig 모델 정의 |
| 비동기 패턴 유지 | ✅ PASS | async/await 패턴 유지 |
| 에러 처리 명확화 | ✅ PASS | EH-001~005 정의됨 |
| 보안 (로컬 LLM만 사용) | ✅ PASS | Ollama 로컬 서버만 사용 |

**Gate Result**: ✅ PASS - 모든 원칙 충족

## Project Structure

### Documentation (this feature)

```text
specs/005-multi-sheet-query/
├── spec.md              # Feature specification (완료)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (내부 API 정의)
├── checklists/          # Quality checklists
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── schema.py           # 기존: ExcelSchema, SheetSchema, ColumnInfo
│   ├── query.py            # 기존: QueryContext, QueryResult, SQLQuery
│   └── sheet_group.py      # 신규: SheetGroup, SheetGroupConfig
├── services/
│   ├── excel_loader.py     # 기존: Excel 로드 및 DuckDB 쿼리
│   ├── llm_router.py       # 수정: Few-shot 예제 추가, UNION 지원
│   ├── sql_agent.py        # 수정: SheetGroupManager 연동
│   ├── response_generator.py # 기존: 응답 포맷팅
│   └── sheet_group_manager.py # 신규: 시트 그룹 분류 및 공통 컬럼 분석
├── config.py               # 수정: 시트 그룹 패턴 설정 추가
└── main.py                 # 기존: Chainlit 엔트리포인트

tests/
├── unit/
│   ├── test_sheet_group_manager.py  # 신규
│   └── test_llm_router_union.py     # 신규
└── integration/
    └── test_multi_sheet_query.py    # 신규
```

**Structure Decision**: 기존 single project 구조 유지. 신규 파일 2개 추가 (models/sheet_group.py, services/sheet_group_manager.py)

## Complexity Tracking

> 위반 사항 없음 - 복잡도 정당화 불필요

---

## Phase 0: Research Summary

**연구 필요 항목**:
1. DuckDB UNION ALL 성능 특성
2. LLM (gpt-oss:20b) UNION SQL 생성 능력
3. 시트 그룹 분류 알고리즘 최적화

**Output**: [research.md](./research.md) 참조

---

## Phase 1: Design Decisions

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Chainlit UI                          │
│                     (main.py - 기존)                         │
└─────────────────────────┬───────────────────────────────────┘
                          │ ask(question)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                       SQLAgent                               │
│                  (sql_agent.py - 수정)                       │
│  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │ SheetGroupManager│  │         LLMRouter               │   │
│  │     (신규)       │──▶│  (수정: Few-shot 추가)          │   │
│  └─────────────────┘  └─────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │ execute_query(union_sql)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      ExcelLoader                             │
│                   (excel_loader.py - 기존)                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    DuckDB                            │    │
│  │  Daily_20241217 ∪ Weekly_W52 ∪ Monthly_Summary      │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **입력**: 사용자 질문 ("김철수가 뭘 했어?")
2. **시트 선택**: SheetGroupManager가 관련 시트 식별
3. **SQL 생성**: LLMRouter가 UNION ALL SQL 생성 (Few-shot 예제 활용)
4. **쿼리 실행**: ExcelLoader가 DuckDB에서 실행
5. **결과 반환**: 시트별 건수 요약 포함

### Key Design Decisions

| 결정 | 선택 | 근거 |
|------|------|------|
| 시트 분류 방식 | 패턴 매칭 (정규식) | 단순하고 예측 가능, 설정으로 확장 가능 |
| UNION 전략 | 공통 컬럼만 (전략 A) | 오류 가능성 낮음, MVP에 적합 |
| 시트 개수 제한 | 최대 10개 | 성능과 프롬프트 크기 균형 |
| fallback 전략 | 개별 쿼리 → 결과 병합 | 부분 실패 허용으로 사용성 개선 |

---

## Implementation Phases

### Phase 1: 기반 작업 (Models & Manager)
- [ ] `models/sheet_group.py`: SheetGroup, SheetGroupConfig 모델
- [ ] `services/sheet_group_manager.py`: 시트 분류, 공통 컬럼 분석
- [ ] `config.py`: 시트 그룹 패턴 설정 추가
- [ ] 단위 테스트: SheetGroupManager

### Phase 2: LLM 프롬프트 개선
- [ ] `llm_router.py`: Few-shot 예제 3개 추가
- [ ] `llm_router.py`: 다중 시트 컨텍스트 전달 로직
- [ ] 프롬프트 토큰 검증

### Phase 3: SQL Agent 통합
- [ ] `sql_agent.py`: SheetGroupManager 연동
- [ ] `sql_agent.py`: relevant_sheets 계산 로직
- [ ] 결과에 시트별 건수 추가

### Phase 4: 에러 처리 및 Fallback
- [ ] UNION 실패 시 개별 쿼리 fallback
- [ ] 부분 실패 허용 로직
- [ ] 로깅 강화

### Phase 5: 테스트 및 검증
- [ ] 통합 테스트: User Stories 기반
- [ ] 성능 테스트: SC-003 검증 (10초 이내)
- [ ] Edge Cases 테스트

---

## Risk Assessment

| 위험 | 확률 | 영향 | 대응 |
|------|------|------|------|
| LLM이 UNION SQL 잘못 생성 | 중 | 높음 | Few-shot 예제 강화, 재시도 로직 |
| 프롬프트 토큰 초과 | 낮 | 중간 | 시트 메타데이터 압축 |
| UNION 쿼리 성능 저하 | 중 | 중간 | 시트 개수 제한 (10개), 캐싱 |
| 컬럼 타입 불일치 | 낮 | 낮음 | VARCHAR 캐스팅 fallback |

---

## Success Metrics

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| SC-001 | 5개+ 시트에서 100건+ 결과 | "김철수가 뭘 했어?" 테스트 |
| SC-002 | 90% 다중 시트 쿼리 성공 | 30개 테스트 질문 세트 |
| SC-003 | 10초 이내 응답 | 성능 테스트 P95 측정 |
| SC-004 | 재질문 없이 완료 | 사용자 테스트 |

---

## Appendix: File Changes Summary

### 신규 파일 (2개)
1. `src/models/sheet_group.py`
2. `src/services/sheet_group_manager.py`

### 수정 파일 (3개)
1. `src/services/sql_agent.py` - SheetGroupManager 연동
2. `src/services/llm_router.py` - Few-shot 예제 추가
3. `src/config.py` - 시트 그룹 설정 추가

### 테스트 파일 (3개)
1. `tests/unit/test_sheet_group_manager.py`
2. `tests/unit/test_llm_router_union.py`
3. `tests/integration/test_multi_sheet_query.py`
