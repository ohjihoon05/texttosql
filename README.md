# Excel Text-to-SQL

반도체 설비 CS 데일리 리포트 Excel 파일에 자연어로 질문하면 SQL로 바꿔 답을 돌려주는 시스템입니다.
화면은 Chainlit, 질의 엔진은 DuckDB, LLM은 로컬 Ollama를 씁니다.

작업 규칙과 설계 문서 위치는 [`CLAUDE.md`](CLAUDE.md)에 있어요.

## 설치

Python 3.11 이상이 필요합니다(`pyproject.toml`).

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env`에는 `LLM_BASE_URL`, `LLM_MODEL`, `LLM_FALLBACK_MODEL`을 적어요. `src/config.py`의 `LLM_BASE_URL` 기본값은 이 PC에서 닿지 않을 수 있는 서버 주소라서, 쓰는 Ollama 주소를 `.env`에 꼭 적어 주세요.

## 실행

테스트용 Excel 파일 만들기(기본 출력 `data/cs_daily_report.xlsx`, `--seed`로 시드 지정):

```bash
python scripts/generate_test_data.py
```

개발 서버 실행:

```bash
chainlit run src/main.py --port 3000 --watch
```

`Dockerfile`도 있지만 이미지 안으로 `data/` 폴더를 복사하므로 빌드 전에 그 폴더가 있어야 해요. 도커로 실제 띄워 본 결과는 확인 못 함.

## 테스트와 린트

```bash
pytest tests/ -v
ruff check src/
```

## 주요 파일

| 경로 | 내용 |
|---|---|
| `src/main.py` | Chainlit 진입점 |
| `src/config.py` | 설정(환경변수와 `.env`에서 읽음) |
| `src/services/excel_loader.py` | Excel을 DuckDB로 읽어 들임 |
| `src/services/sql_agent.py` | 자연어를 SQL로 바꿔 실행 |
| `src/services/llm_router.py` | 기본 모델과 대체 모델 사이 전환 |
| `src/services/response_generator.py` | 답변 문장 만들기 |
| `src/models/` | Pydantic 데이터 모델 |
| `scripts/generate_test_data.py` | 테스트용 Excel 생성기 |
| `tests/unit/`, `tests/integration/` | 단위·통합 테스트 |
| `specs/` | 기능별 명세·계획·작업 목록 |
