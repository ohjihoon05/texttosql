# Feature Specification: Excel Text-to-SQL System

**Feature ID**: 001-excel-text-to-sql
**Status**: Draft
**Created**: 2024-12-23
**Branch**: `001-excel-text-to-sql`

## Overview

반도체 설비 CS 데일리 리포트 Excel 파일을 자연어로 질의할 수 있는 Text-to-SQL 시스템.
사용자가 "김철수가 뭘 했어?"처럼 자연어로 질문하면 Excel 데이터에서 SQL 쿼리를 생성하여 결과를 반환한다.

### Key Constraints
- **보안**: 외부 API 사용 불가, 로컬 Ollama LLM만 사용
- **LLM 리소스**: wonik4 서버 (10.249.22.191:11435) 사용
- **데이터**: 3-4MB Excel 파일, 약 30개 시트
- **도메인**: 반도체 설비 전문 용어 포함

## User Stories

### Primary User Story
```
AS A CS 담당자
I WANT TO Excel 데이터를 자연어로 질의하고 싶다
SO THAT 수작업 검색 없이 빠르게 정보를 찾을 수 있다
```

### Detailed Scenarios
1. **이름 검색**: "김철수가 이번 주에 뭘 했어?" → 해당 담당자의 활동 조회
2. **날짜 검색**: "12월 20일 CS 건수는?" → 날짜별 통계 조회
3. **설비 검색**: "ASM 설비 관련 이슈는?" → 설비별 필터링

## System Architecture

```
┌─────────────────┐     ┌─────────────────────────────────┐
│   User (Web)    │     │         Python Backend          │
│    Chainlit     │────▶│  ┌─────────────────────────┐    │
│   UI (3000)     │     │  │   LangChain + Ollama    │    │
└─────────────────┘     │  │   (langchain_ollama)    │    │
                        │  └───────────┬─────────────┘    │
                        │              │                  │
                        │  ┌───────────▼─────────────┐    │
                        │  │    Schema Filter        │    │
                        │  │  (30 sheets → 5 관련)   │    │
                        │  └───────────┬─────────────┘    │
                        │              │                  │
                        │  ┌───────────▼─────────────┐    │
                        │  │   Query Cache           │    │
                        │  │  (Redis/In-Memory)      │    │
                        │  └───────────┬─────────────┘    │
                        │              │                  │
                        │  ┌───────────▼─────────────┐    │
                        │  │  DuckDB + SQLite        │    │
                        │  │  (Excel Data Engine)    │    │
                        │  └───────────┬─────────────┘    │
                        │              │                  │
                        │  ┌───────────▼─────────────┐    │
                        │  │     ChromaDB (RAG)      │    │
                        │  │  (반도체 전문 용어)      │    │
                        │  └─────────────────────────┘    │
                        └─────────────────────────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────────┐
                        │    wonik4 Ollama Server         │
                        │    10.249.22.191:11435          │
                        │    Model: gpt-oss:20b           │
                        └─────────────────────────────────┘
```

## Technical Requirements

### Core Components

#### 1. UI Layer - Chainlit
- **Framework**: Chainlit (Apache 2.0 License, 무료)
- **Port**: 3000
- **Features**: 대화형 인터페이스, 스트리밍 응답, 파일 업로드

#### 2. LLM Integration - LangChain + Ollama
- **Library**: `langchain_ollama` (최신 권장)
- **Endpoint**: `http://10.249.22.191:11435`
- **Model**: `gpt-oss:20b`
- **Fallback**: Local lightweight model (llama3.2:1b) for SPOF mitigation

#### 3. Database Engine - DuckDB + SQLite
- **Primary**: DuckDB (Excel 직접 쿼리, 50x faster than SQLite)
- **Secondary**: SQLite (복잡한 조인, 디스크 캐싱)
- **Caching**: 디스크 기반 SQLite 캐시 (재시작 시 데이터 유지)

#### 4. Schema Intelligence
- **Schema Filtering**: 30개 시트 → 질문 관련 5개만 선택
- **Column Sampling**: 각 컬럼 상위 5개 값 샘플링으로 컨텍스트 제공
- **Metadata Caching**: 스키마 정보 캐싱으로 LLM 토큰 절약

#### 5. Query Optimization
- **Query Cache**: 동일 질문 캐싱 (TTL: 1시간)
- **Streaming**: 긴 응답 시 점진적 출력
- **Timeout**: 쿼리 실행 10초 제한

#### 6. RAG System - ChromaDB
- **용도**: 반도체 설비 전문 용어 매핑
- **데이터**: 용어집 + 약어 사전
- **임베딩**: Local embedding model (all-MiniLM-L6-v2)

### Non-Functional Requirements

| Category | Requirement | Target |
|----------|-------------|--------|
| Performance | 응답 시간 | < 10초 (캐시 히트 시 < 2초) |
| Performance | Excel 로딩 | < 5초 (4MB 파일) |
| Availability | LLM Fallback | Local model 자동 전환 |
| Scalability | 동시 사용자 | 1-5명 |
| Data Integrity | 캐시 지속성 | 디스크 기반 (재시작 유지) |

## Implementation Priorities

### Phase 1: MVP (Must Have)
1. Chainlit UI 기본 구조
2. Excel → DuckDB 로딩
3. LangChain + Ollama 연동 (원격)
4. 기본 Text-to-SQL 변환
5. 결과 표시

### Phase 2: Enhancement (Should Have)
1. Schema Filtering (관련 시트만 선택)
2. Query Cache 구현
3. Streaming 응답
4. 에러 핸들링 개선

### Phase 3: Optimization (Nice to Have)
1. ChromaDB RAG (전문 용어)
2. Fallback LLM 구현
3. 히스토리 기반 학습

### Phase 4: Security (Deferred)
1. HTTPS 통신
2. SQL Injection 방어 강화
3. 입력 검증 고도화

## Success Criteria

1. **기능**: 자연어 질문 → SQL 변환 → 결과 반환 성공률 > 80%
2. **성능**: 평균 응답 시간 < 10초
3. **안정성**: 원격 LLM 실패 시 fallback 동작
4. **사용성**: 비개발자도 사용 가능한 UI

## Dependencies

### Python Packages
```
chainlit>=1.0.0
langchain>=0.3.0
langchain-ollama>=0.2.0
duckdb>=0.9.0
pandas>=2.0.0
openpyxl>=3.1.0
chromadb>=0.4.0
sentence-transformers>=2.2.0
```

### External Services
- wonik4 Ollama Server (10.249.22.191:11435)

## Glossary

| Term | Description |
|------|-------------|
| Text-to-SQL | 자연어를 SQL 쿼리로 변환하는 기술 |
| Schema Filtering | 질문과 관련된 테이블/시트만 선택하는 기법 |
| RAG | Retrieval-Augmented Generation, 검색 증강 생성 |
| DuckDB | 분석용 인메모리 데이터베이스 (Excel 직접 쿼리 지원) |
