# CLAUDE.md - Excel Text-to-SQL Project

## Project Overview

반도체 설비 CS 데일리 리포트 Excel 파일을 자연어로 질의하는 Text-to-SQL 시스템.
사용자가 "김철수가 뭘 했어?"처럼 자연어로 질문하면 SQL로 변환하여 결과 반환.

## Best Practices

- 간단하고 모듈화된 코드 선호
- 기존 코드 스타일과 패턴 따르기
- Pydantic 모델로 데이터 검증
- 비동기(async/await) 패턴 사용
- 명확한 에러 메시지 제공

## Tech Stack

- Python 3.11+
- Chainlit (UI Framework)
- LangChain + langchain-ollama (LLM Orchestration)
- DuckDB (Excel Query Engine)
- SQLite (Cache)
- ChromaDB (RAG - 반도체 용어)
- Pydantic (Data Validation)
- pytest (Testing)

## Network & Ports

- **Host IP**: 192.168.20.83
- **Chainlit Port**: 3003
- **App URL**: http://192.168.20.83:3003

## External Services

- **LLM Server**: wonik4 (10.249.22.191:11435)
- **Model**: gpt-oss:20b
- **Fallback**: llama3.2:1b (local)

## Project Structure

```
src/
├── main.py              # Chainlit 엔트리포인트
├── config.py            # 설정 관리
├── models/              # Pydantic 데이터 모델
├── services/            # 비즈니스 로직
│   ├── excel_loader.py  # Excel → DuckDB
│   ├── schema_filter.py # 관련 시트 필터링
│   ├── query_cache.py   # 쿼리 캐싱
│   ├── llm_router.py    # LLM fallback 라우팅
│   └── sql_agent.py     # LangChain SQL Agent
├── rag/                 # RAG 시스템
└── utils/               # 유틸리티

tests/
├── unit/                # 단위 테스트
└── integration/         # 통합 테스트

specs/                   # Speckit 문서
data/                    # 데이터 파일 (Excel, 캐시)
```

## Planning

- 새 기능 추가 전 `specs/001-excel-text-to-sql/` 문서 확인
- 기존 서비스 패턴 확인 후 일관성 유지
- 복잡한 작업은 먼저 명확히 하기

## Documentation References

- 기능 명세: `specs/001-excel-text-to-sql/spec.md`
- 기술 결정: `specs/001-excel-text-to-sql/research.md`
- 구현 계획: `specs/001-excel-text-to-sql/plan.md`
- 데이터 모델: `specs/001-excel-text-to-sql/data-model.md`
- API 명세: `specs/001-excel-text-to-sql/contracts/api.md`

## Key Constraints

1. **보안**: 외부 API 사용 불가, 로컬 Ollama LLM만 사용
2. **성능**: 응답 < 10초, 캐시 히트 < 2초
3. **데이터**: 3-4MB Excel, 약 30개 시트
4. **도메인**: 반도체 설비 전문 용어 포함

## Common Commands

```bash
# 개발 서버 실행 (네트워크 접근 가능)
chainlit run src/main.py --port 3003 --host 192.168.20.83

# 테스트 실행
pytest tests/ -v

# 커버리지 포함
pytest tests/ --cov=src --cov-report=html

# Ollama 서버 연결 확인
curl http://10.249.22.191:11435/api/tags

# 린트 (설정 시)
ruff check src/
ruff format src/
```

## Code Patterns

### LLM 호출
```python
from langchain_ollama import OllamaLLM

llm = OllamaLLM(
    model="gpt-oss:20b",
    base_url="http://10.249.22.191:11435",
    temperature=0
)
```

### DuckDB Excel 쿼리
```python
import duckdb

conn = duckdb.connect()
df = conn.execute("SELECT * FROM read_xlsx('file.xlsx', sheet='Sheet1')").df()
```

### Chainlit 메시지
```python
import chainlit as cl

@cl.on_message
async def on_message(message: cl.Message):
    await cl.Message(content="응답").send()
```

## Final Steps

작업 완료 시 다음 순서로 확인:

1. `ruff check src/` - 린트 에러 확인
2. `ruff format src/` - 코드 포맷팅
3. `pytest tests/` - 테스트 통과 확인
4. 필요시 `specs/` 문서 업데이트

## Active Technologies
- Python 3.11 + LangChain, langchain-ollama, Chainlit, Pydantic, DuckDB (004-ai-response-style)
- DuckDB (in-memory), SQLite (cache) (004-ai-response-style)

## Recent Changes
- 004-ai-response-style: Added Python 3.11 + LangChain, langchain-ollama, Chainlit, Pydantic, DuckDB
