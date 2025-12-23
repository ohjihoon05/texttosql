# Quickstart: AI 서비스 스타일 자연어 응답

## 개요

SQL 조회 결과를 LLM을 사용해 자연스러운 대화형 응답으로 변환합니다.

## 변경 전/후 비교

### Before
```
사용자: 김철수가 뭘 했어?
시스템: 5건의 결과를 찾았습니다. (실행 시간: 15.2ms)
```

### After
```
사용자: 김철수가 뭘 했어?
시스템: 김철수님은 최근 5건의 작업을 수행했습니다.
        - 12월 20일: PM 점검 (Team_A팀)
        - 12월 21일: 설비 이상 조치 (Team_A팀)
        - ...
        가장 최근 활동은 12월 22일 설비 점검입니다.
```

## 핵심 변경 사항

1. **신규 모듈**: `src/services/response_generator.py`
   - ResponseGenerator 클래스
   - LLM 기반 응답 생성

2. **수정 모듈**: `src/services/sql_agent.py`
   - `_format_answer` → `async` 변환
   - ResponseGenerator 호출

3. **모델 확장**: `src/models/query.py`
   - ResponseType enum 추가
   - FormattedResponse 필드 확장

## 테스트 실행

```bash
# 단위 테스트
pytest tests/unit/test_response_generator.py -v

# 통합 테스트
pytest tests/integration/test_response_flow.py -v

# 전체 테스트
pytest tests/ -v
```

## 주요 프롬프트

```python
RESPONSE_PROMPT = """당신은 반도체 설비 CS 리포트 분석 도우미입니다.
사용자 질문과 SQL 조회 결과를 바탕으로 자연스러운 한국어로 답변하세요.

## 질문
{question}

## 조회 결과 ({row_count}건)
{result_json}

## 지침
- 존칭 사용 (예: ~님, ~입니다)
- 핵심 정보 먼저 언급
- 결과가 없으면 대안 제시
- 10건 이상이면 요약 중심
"""
```
