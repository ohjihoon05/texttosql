# Quickstart: Excel Text-to-SQL System

**Feature ID**: 001-excel-text-to-sql
**Date**: 2024-12-23

## Prerequisites

- Python 3.11+
- wonik4 서버 접근 가능 (10.249.22.191:11435)
- Excel 파일 (.xlsx)

## Installation

```bash
# 1. 프로젝트 클론
cd /home/wonchatgpt/oz/Projects/texttosql

# 2. 가상환경 생성
python -m venv venv
source venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt
```

## Configuration

`.env` 파일 생성:

```bash
# LLM 설정
OLLAMA_BASE_URL=http://10.249.22.191:11435
OLLAMA_MODEL=gpt-oss:20b
OLLAMA_TIMEOUT=30

# Fallback 설정
FALLBACK_ENABLED=true
FALLBACK_MODEL=llama3.2:1b
FALLBACK_URL=http://localhost:11434

# 캐시 설정
CACHE_TTL_SECONDS=3600
CACHE_DB_PATH=./data/cache.db

# 성능 설정
QUERY_TIMEOUT_SECONDS=10
MAX_RESULT_ROWS=100
```

## Running the Application

```bash
# Chainlit 서버 시작
chainlit run src/main.py --port 3000

# 또는 개발 모드 (자동 리로드)
chainlit run src/main.py --port 3000 --watch
```

## Usage

### 1. 파일 업로드

브라우저에서 `http://localhost:3000` 접속 후 Excel 파일 업로드.

### 2. 자연어 질문

```
예시 질문들:
- "김철수가 이번 주에 뭘 했어?"
- "12월 20일 CS 건수는 몇 건이야?"
- "ASM 설비 관련 이슈 목록 보여줘"
- "이번 달 완료된 작업 통계 보여줘"
```

### 3. 결과 확인

시스템이 SQL을 생성하고 결과를 테이블 형태로 표시.

## Project Structure

```
texttosql/
├── src/
│   ├── main.py              # Chainlit 엔트리포인트
│   ├── config.py            # 설정 관리
│   ├── models/              # 데이터 모델
│   ├── services/            # 비즈니스 로직
│   └── utils/               # 유틸리티
├── tests/                   # 테스트
├── data/                    # 데이터 파일
├── specs/                   # 스펙 문서
├── requirements.txt
└── .env
```

## Testing

```bash
# 전체 테스트
pytest tests/

# 특정 테스트
pytest tests/unit/test_excel_loader.py -v

# 커버리지 포함
pytest tests/ --cov=src --cov-report=html
```

## Troubleshooting

### LLM 연결 실패

```bash
# wonik4 연결 확인
curl http://10.249.22.191:11435/api/tags
```

### Excel 로딩 오류

- 파일 크기 확인 (< 10MB)
- .xlsx 형식 확인 (.xls 미지원)

### 느린 응답

- 캐시 확인 (`data/cache.db`)
- 스키마 필터링 로그 확인

## Next Steps

1. `/speckit.tasks` 실행하여 상세 태스크 생성
2. Phase 1 (MVP) 구현 시작
3. 샘플 Excel로 테스트
