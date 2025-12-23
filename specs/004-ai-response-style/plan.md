# Implementation Plan: AI 서비스 스타일 자연어 응답

**Branch**: `004-ai-response-style` | **Date**: 2025-12-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-ai-response-style/spec.md`

## Summary

SQL 조회 결과를 LLM을 활용하여 자연스러운 대화형 응답으로 변환. 기존 단순 "N건 결과" 형식에서 "김철수님은 [날짜]에 [작업]을 수행했습니다" 형태의 AI 서비스 스타일 응답으로 개선.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: LangChain, langchain-ollama, Chainlit, Pydantic, DuckDB
**Storage**: DuckDB (in-memory), SQLite (cache)
**Testing**: pytest
**Target Platform**: Windows/Linux server, Chainlit Web UI
**Project Type**: Single project (backend only)
**Performance Goals**: 응답 생성 < 2초 추가 지연
**Constraints**: 로컬 Ollama LLM 사용, 외부 API 불가
**Scale/Scope**: 단일 사용자, 30개 시트 Excel

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Simplicity | PASS | 기존 LLMRouter 패턴 확장 |
| Test-First | PASS | 단위/통합 테스트 계획 포함 |
| Library-First | PASS | response_generator 모듈로 분리 |

## Project Structure

### Documentation (this feature)

```text
specs/004-ai-response-style/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/
├── models/
│   └── query.py         # FormattedResponse 확장
├── services/
│   ├── sql_agent.py     # _format_answer 수정
│   ├── llm_router.py    # 기존 유지
│   └── response_generator.py  # 신규: LLM 응답 생성
└── main.py              # 변경 없음

tests/
├── unit/
│   └── test_response_generator.py  # 신규
└── integration/
    └── test_response_flow.py       # 신규
```

**Structure Decision**: 기존 src/services 구조 유지, response_generator.py 모듈 추가

## Complexity Tracking

> No violations - simple extension of existing patterns.
