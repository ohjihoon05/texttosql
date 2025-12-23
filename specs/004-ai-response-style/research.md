# Research: AI 서비스 스타일 자연어 응답

**Date**: 2025-12-23
**Feature**: 004-ai-response-style

## 1. LLM 기반 응답 생성 아키텍처

### Decision: SQL 결과 → LLM → 자연어 응답

**Rationale**:
- 기존 LLMRouter 패턴과 동일한 아키텍처 재사용
- Ollama 모델이 이미 설정되어 있어 추가 인프라 불필요
- 프롬프트 엔지니어링으로 응답 품질 제어 가능

**Alternatives Considered**:
1. **템플릿 기반**: 미리 정의된 응답 패턴에 데이터 삽입
   - 장점: 빠름, LLM 호출 불필요
   - 단점: 경직된 응답, 다양한 질문 유형 대응 어려움
2. **하이브리드**: 단순 쿼리는 템플릿, 복잡한 경우 LLM
   - 장점: 성능과 유연성 균형
   - 단점: 분기 로직 복잡, 유지보수 부담

## 2. 프롬프트 설계 전략

### Decision: 역할 기반 프롬프트 + 응답 포맷 지정

**Rationale**:
- 시스템 역할 정의로 일관된 톤 유지
- 질문/결과/응답 형식 명시로 정확한 출력 유도
- 한국어 자연스러운 어미 사용 지시

**Prompt Structure**:
```
시스템: 당신은 반도체 설비 CS 데일리 리포트 분석 도우미입니다.
입력: 질문, SQL 결과 (JSON), 컬럼 정보
출력: 자연스러운 한국어 문장 (존칭, 데이터 요약 포함)
```

## 3. 응답 유형별 처리

### Decision: 결과 건수 기반 분기

| 결과 건수 | 응답 전략 |
|----------|----------|
| 0건 | 친절한 안내 + 대안 제시 |
| 1건 | 상세 정보 문장화 |
| 2-10건 | 목록 나열 + 요약 |
| 10건+ | 요약 중심 + 상위 N개 예시 |

**Rationale**:
- 사용자 경험 최적화
- 과다 정보 방지
- 일관된 응답 길이 유지

## 4. 성능 최적화

### Decision: 비동기 LLM 호출 + 타임아웃

**Rationale**:
- 기존 async/await 패턴과 일관성
- 응답 지연 시 폴백 메시지 제공
- 2초 타임아웃으로 SC-005 충족

**Implementation**:
```python
async def generate_response(..., timeout=2.0):
    try:
        async with asyncio.timeout(timeout):
            return await llm.ainvoke(prompt)
    except asyncio.TimeoutError:
        return fallback_simple_response(result)
```

## 5. 모듈 구조

### Decision: ResponseGenerator 클래스 분리

**Rationale**:
- 단일 책임 원칙 (SRP)
- 테스트 용이성
- LLMRouter와 독립적 재사용

**Location**: `src/services/response_generator.py`

## 6. 테스트 전략

### Decision: Mock LLM + 실제 응답 검증

**Unit Tests**:
- 프롬프트 생성 로직
- 결과 건수별 분기
- 타임아웃 처리

**Integration Tests**:
- 실제 LLM 호출 (선택적)
- 전체 파이프라인 검증
