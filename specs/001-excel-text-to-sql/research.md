# Technical Research: Excel Text-to-SQL System

**Feature ID**: 001-excel-text-to-sql
**Date**: 2024-12-23
**Status**: Complete

## Research Questions

### RQ1: Database Engine Selection

**Question**: Excel 데이터를 SQL로 쿼리하기 위한 최적의 데이터베이스 엔진은?

**Options Evaluated**:
| Option | Pros | Cons |
|--------|------|------|
| SQLite (in-memory) | 간단, 널리 사용 | Excel 변환 필요, 재시작 시 데이터 손실 |
| DuckDB | Excel 직접 쿼리, 50x 빠름, 분석 최적화 | 상대적으로 새로운 기술 |
| PostgreSQL | 강력한 기능 | 오버헤드 큼, 설치 복잡 |

**Decision**: **DuckDB (Primary) + SQLite (Cache)**
- DuckDB: Excel 파일 직접 쿼리 지원, 분석 워크로드 최적화
- SQLite: 디스크 기반 캐시로 재시작 시 데이터 유지

**Evidence**:
```python
# DuckDB Excel 직접 쿼리 예시
import duckdb
conn = duckdb.connect()
conn.execute("INSTALL spatial; LOAD spatial;")
df = conn.execute("SELECT * FROM read_xlsx('report.xlsx', sheet='Sheet1')").df()
```

---

### RQ2: LangChain + Ollama Integration

**Question**: LangChain과 원격 Ollama 서버 연동 방법?

**Options Evaluated**:
| Option | Pros | Cons |
|--------|------|------|
| langchain.llms.Ollama (deprecated) | 기존 코드 호환 | Deprecated, 향후 제거 예정 |
| langchain_ollama.OllamaLLM | 공식 권장, 최신 기능 | 별도 패키지 설치 필요 |
| 직접 REST API 호출 | 의존성 최소화 | 에러 핸들링 직접 구현 필요 |

**Decision**: **langchain_ollama (Official Package)**

**Evidence**:
```python
from langchain_ollama import OllamaLLM

llm = OllamaLLM(
    model="gpt-oss:20b",
    base_url="http://10.249.22.191:11435",
    temperature=0,  # SQL 생성 시 결정적 출력
    timeout=30
)
```

---

### RQ3: Schema Context Optimization

**Question**: 30개 시트의 스키마를 LLM에 효율적으로 전달하는 방법?

**Options Evaluated**:
| Option | Pros | Cons |
|--------|------|------|
| 전체 스키마 전달 | 단순 구현 | 토큰 낭비, 컨텍스트 오버플로우 위험 |
| Schema Filtering | 관련 시트만 선택, 토큰 절약 | 필터링 로직 구현 필요 |
| RAG 기반 스키마 검색 | 동적 스키마 선택 | 복잡도 증가 |

**Decision**: **Schema Filtering + Column Sampling**

**Implementation Strategy**:
1. 질문에서 키워드 추출
2. 시트명/컬럼명과 키워드 매칭 (유사도 점수)
3. 상위 5개 시트만 선택
4. 각 컬럼에서 샘플 값 5개 추출하여 컨텍스트 제공

**Evidence**:
```python
def filter_relevant_sheets(question: str, all_sheets: dict) -> dict:
    """질문과 관련된 시트만 필터링"""
    keywords = extract_keywords(question)  # 형태소 분석

    scores = {}
    for sheet_name, columns in all_sheets.items():
        score = calculate_relevance(keywords, sheet_name, columns)
        scores[sheet_name] = score

    # 상위 5개 시트만 반환
    top_sheets = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
    return {name: all_sheets[name] for name, _ in top_sheets}
```

---

### RQ4: Query Caching Strategy

**Question**: 반복 질문에 대한 성능 최적화 방법?

**Options Evaluated**:
| Option | Pros | Cons |
|--------|------|------|
| No Cache | 구현 단순 | 매번 LLM 호출, 느림 |
| In-Memory Cache | 빠름 | 재시작 시 손실 |
| Redis | 분산 캐시, 영속성 | 별도 서비스 필요 |
| Disk-based (SQLite) | 영속성, 단일 프로세스 | Redis보다 느림 |

**Decision**: **In-Memory Cache (Primary) + Disk Cache (Secondary)**

**Implementation**:
```python
from functools import lru_cache
import hashlib
import sqlite3

class QueryCache:
    def __init__(self, db_path="cache.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_table()
        self._memory_cache = {}

    def get(self, question: str) -> str | None:
        key = hashlib.md5(question.encode()).hexdigest()

        # 1. Memory cache first
        if key in self._memory_cache:
            return self._memory_cache[key]

        # 2. Disk cache fallback
        row = self.conn.execute(
            "SELECT result FROM cache WHERE key=? AND expires_at > datetime('now')",
            (key,)
        ).fetchone()

        if row:
            self._memory_cache[key] = row[0]
            return row[0]

        return None
```

---

### RQ5: LLM Fallback Strategy

**Question**: 원격 LLM 서버 장애 시 대응 방안?

**Options Evaluated**:
| Option | Pros | Cons |
|--------|------|------|
| No Fallback | 구현 단순 | SPOF, 서비스 중단 |
| Local Lightweight Model | 완전 오프라인 가능 | 품질 저하 |
| Queue + Retry | 일시적 장애 대응 | 영구 장애 시 무력 |

**Decision**: **Local Fallback Model + Retry with Backoff**

**Implementation**:
```python
class LLMRouter:
    def __init__(self):
        self.primary = OllamaLLM(
            model="gpt-oss:20b",
            base_url="http://10.249.22.191:11435"
        )
        self.fallback = OllamaLLM(
            model="llama3.2:1b",
            base_url="http://localhost:11434"  # Local
        )
        self.max_retries = 3

    async def invoke(self, prompt: str) -> str:
        for attempt in range(self.max_retries):
            try:
                return await self.primary.ainvoke(prompt)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.warning(f"Primary LLM failed, using fallback: {e}")
                    return await self.fallback.ainvoke(prompt)
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

---

### RQ6: UI Framework Selection

**Question**: 대화형 Text-to-SQL UI를 위한 최적의 프레임워크?

**Options Evaluated**:
| Option | Pros | Cons |
|--------|------|------|
| Streamlit | 간단, 데이터 앱 특화 | 대화형 UX 제한적 |
| Gradio | ML 데모에 적합 | 채팅 기능 제한적 |
| Chainlit | 채팅 특화, LangChain 통합 | 상대적으로 새로움 |
| Next.js + FastAPI | 완전한 커스터마이징 | 개발 비용 높음 |

**Decision**: **Chainlit**
- Apache 2.0 라이선스 (무료)
- LangChain 네이티브 통합
- 스트리밍 응답 기본 지원
- 파일 업로드 내장

---

## Architecture Decisions

### AD1: Layered Architecture
```
Presentation Layer (Chainlit)
     ↓
Application Layer (LangChain Agent)
     ↓
Domain Layer (Schema Filter, Query Builder)
     ↓
Infrastructure Layer (DuckDB, ChromaDB, Ollama Client)
```

### AD2: Error Handling Strategy
| Error Type | Handling |
|------------|----------|
| LLM Timeout | Fallback to local model |
| Invalid SQL | 사용자에게 재질문 요청 |
| Excel Parse Error | 명확한 에러 메시지 표시 |
| Schema Not Found | 가능한 시트 목록 제안 |

### AD3: Streaming Response
- LLM 응답을 청크 단위로 UI에 전송
- 긴 SQL 결과는 점진적 렌더링
- 타임아웃 전 부분 결과 표시

## Performance Benchmarks (Expected)

| Metric | Target | Notes |
|--------|--------|-------|
| Cold Start | < 5s | Excel 로딩 포함 |
| Cached Query | < 2s | 캐시 히트 시 |
| New Query | < 10s | LLM 호출 포함 |
| Schema Filter | < 500ms | 30개 시트 필터링 |

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Remote LLM 불안정 | Medium | High | Local fallback 구현 |
| 잘못된 SQL 생성 | Medium | Medium | SQL 검증 레이어 추가 |
| 메모리 부족 | Low | High | DuckDB lazy loading |
| 한글 처리 이슈 | Medium | Low | 형태소 분석기 적용 |

## References

1. [LangChain SQL Agent](https://python.langchain.com/docs/tutorials/sql_qa/)
2. [DuckDB Excel Integration](https://duckdb.org/docs/extensions/excel.html)
3. [Chainlit Documentation](https://docs.chainlit.io/)
4. [Text-to-SQL with RAG](https://community.heartcount.io/ko/text-to-sql-rag/)
