# Feature Specification: Multi-Sheet Query Support

**Feature Branch**: `005-multi-sheet-query`
**Created**: 2024-12-24
**Status**: Draft
**Input**: User description: "LLM이 여러 시트에서 데이터를 검색하도록 SQL 생성 개선"

## 배경

현재 시스템은 사용자 질문에 대해 단일 시트만 쿼리하는 SQL을 생성한다. 예를 들어 "김철수가 뭘 했어?"라고 질문하면 `Engineer_Performance` 시트만 조회하여 1건만 반환하지만, 실제로 김철수 관련 데이터는 Daily, Weekly, Monthly 등 여러 시트에 200건 이상 존재한다.

## User Scenarios & Testing

### User Story 1 - 담당자별 전체 업무 조회 (Priority: P1)

사용자가 "김철수가 뭘 했어?"라고 질문하면, 시스템은 모든 관련 시트(Daily, Weekly, Monthly 등)에서 김철수가 담당한 모든 티켓/업무를 검색하여 종합적인 결과를 보여준다.

**Why this priority**: 핵심 사용 사례이며 현재 가장 큰 불만 사항. 단일 시트 조회로는 담당자의 실제 업무량과 성과를 파악할 수 없다.

**Independent Test**: "김철수가 뭘 했어?" 질문 시 여러 시트에서 검색된 모든 결과가 표시되고, 총 건수가 200건 이상으로 표시되면 성공.

**Acceptance Scenarios**:

1. **Given** Excel 파일이 로드된 상태, **When** 사용자가 "김철수가 뭘 했어?"라고 질문, **Then** Daily, Weekly, Monthly 등 모든 시트에서 김철수 관련 데이터를 검색하여 결과 표시
2. **Given** 담당자 이름 검색 요청, **When** 해당 담당자가 여러 시트에 존재, **Then** UNION ALL을 사용하여 모든 시트의 데이터를 통합하여 반환
3. **Given** 검색 결과가 있을 때, **When** 결과 표시, **Then** 어느 시트에서 왔는지 출처 정보도 함께 표시

---

### User Story 2 - 기간별 업무 조회 (Priority: P2)

사용자가 "이번 주 처리된 티켓 보여줘" 또는 "12월 김철수 업무"처럼 기간을 지정하면, 해당 기간의 모든 관련 시트에서 데이터를 검색한다.

**Why this priority**: 기간별 분석은 일상적인 업무 리포팅에 필수적이며, P1 기능의 자연스러운 확장이다.

**Independent Test**: "이번 주 완료된 티켓" 질문 시 Weekly 시트와 Daily 시트를 모두 검색하여 결과 표시.

**Acceptance Scenarios**:

1. **Given** Excel 파일이 로드된 상태, **When** 사용자가 "이번 주 완료된 티켓" 질문, **Then** 관련 Weekly 및 Daily 시트에서 상태가 '완료'인 데이터 검색
2. **Given** 날짜 범위 지정 질문, **When** 여러 시트에 해당 기간 데이터 존재, **Then** 모든 관련 시트에서 데이터 통합 반환

---

### User Story 3 - 설비별 고장 이력 조회 (Priority: P2)

사용자가 "CVD 설비 고장 이력"이라고 질문하면, Equipment_CVD 시트뿐만 아니라 Daily, Weekly, Monthly 시트에서도 CVD 관련 고장 데이터를 검색한다.

**Why this priority**: 설비 관리자가 특정 설비 유형의 전체 이력을 파악해야 할 때 필수적인 기능이다.

**Independent Test**: "CVD 설비 고장 이력" 질문 시 Equipment_CVD 시트와 다른 시트들에서 설비유형='CVD'인 데이터를 모두 검색.

**Acceptance Scenarios**:

1. **Given** Excel 파일이 로드된 상태, **When** 사용자가 "CVD 설비 고장 보여줘" 질문, **Then** 설비유형이 CVD인 모든 데이터를 여러 시트에서 검색하여 통합 표시

---

### Edge Cases

- 검색 결과가 너무 많을 때 (1000건 이상): 상위 100건만 표시하고 총 건수 안내
- 시트 간 컬럼 구조가 다를 때: 공통 컬럼만 선택하여 UNION 수행
- 검색어가 여러 시트에 없을 때: "검색 결과가 없습니다" 메시지 표시
- 동일 데이터가 여러 시트에 중복 존재할 때: 중복 제거 옵션 제공 (기본값: 중복 허용)

## Requirements

### Functional Requirements

- **FR-001**: LLM 프롬프트에 "관련 시트가 여러 개일 경우 UNION ALL을 사용하여 통합 쿼리 생성" 지침 추가
- **FR-002**: 시스템은 질문 유형(담당자, 기간, 설비 등)에 따라 관련 시트를 자동으로 식별해야 함 (상세: FR-002 구체화 섹션 참조)
- **FR-003**: 생성된 SQL에 시트 출처를 식별할 수 있는 컬럼 추가 (예: SELECT 'Daily_20241217' as source_sheet, ...)
- **FR-004**: 시트 간 컬럼 구조가 다른 경우 공통 컬럼을 자동으로 식별하여 UNION 가능하도록 처리 (상세: FR-004 구체화 섹션 참조)
- **FR-005**: 대량 결과(100건 이상) 시 결과 요약 정보 제공 (총 건수, 시트별 건수 등)
- **FR-006**: UNION 쿼리 생성 시 각 시트의 테이블 이름 매핑 정보를 LLM에 정확히 전달
- **FR-007**: 검색 결과가 100건 초과 시, 상위 100건만 반환하고 "총 {N}건 중 100건 표시" 메시지 포함
- **FR-008**: 검색 결과가 0건일 경우, 검색한 시트 목록을 사용자에게 안내
- **FR-009**: 중복 데이터 처리는 기본값 UNION ALL(중복 허용), 향후 UNION DISTINCT 옵션 제공
- **FR-010**: 검색 결과는 접수일자 기준 최신순으로 정렬
- **FR-011**: 시트 메타데이터(시트명, 컬럼, 타입, 행수)를 캐싱하여 재분석 시간 단축
- **FR-012**: UNION 쿼리 실패 시 fallback 전략 수행 (컬럼 캐스팅 → 공통 컬럼만 → 단일 시트)
- **FR-013**: 다중 시트 쿼리 시 식별된 시트 목록, 공통 컬럼, SQL, 시트별 건수를 로깅
- **FR-014**: LLM 프롬프트에 UNION ALL Few-shot 예제 3개 이상 포함

### Key Entities

- **시트 그룹**: Daily 시트들, Weekly 시트들, Monthly 시트, Equipment 시트들, Team 시트들 등 유사 구조를 가진 시트들의 논리적 그룹
- **쿼리 컨텍스트**: 질문 유형, 관련 시트 목록, 공통 컬럼, 필터 조건 등 SQL 생성에 필요한 메타데이터

## Success Criteria

### Measurable Outcomes

- **SC-001**: "김철수가 뭘 했어?" 질문 시 5개 이상의 시트에서 데이터를 검색하여 100건 이상의 결과 반환
- **SC-002**: 담당자/기간/설비 유형 관련 질문의 90% 이상에서 다중 시트 쿼리가 정상 생성됨
- **SC-003**: UNION 쿼리 실행 시간이 단일 시트 쿼리 대비 3배 이내 (10초 이내 응답)
- **SC-004**: 사용자가 원하는 데이터를 한 번의 질문으로 모두 확인 가능 (재질문 필요 없음)

## Assumptions

- 모든 Daily 시트는 동일한 컬럼 구조를 가짐 (ticket_id, 접수일자, 고객사, 설비ID, 설비유형, 고장유형, 증상, 담당자, 팀, 상태, 조치내용, 완료일자, 소요시간)
- Weekly 시트는 Daily 시트 컬럼 + '주차' 컬럼
- Monthly 시트는 Weekly 시트 컬럼 + '월', 'SLA_충족' 컬럼
- Equipment 시트는 설비 마스터 정보로 담당자 컬럼이 없음
- Team 시트는 팀원 통계 정보로 ticket_id 컬럼이 없음
- LLM이 UNION ALL 구문을 이해하고 올바르게 생성할 수 있음 (Few-shot 예제로 검증 필요)

---

## FR-002 구체화: 관련 시트 식별 알고리즘

### FR-002-1: 시트 그룹 정의

시스템은 시트를 다음 논리적 그룹으로 분류해야 함:

| 그룹명 | 시트 패턴 | 용도 | UNION 가능 | 컬럼 수 |
|--------|----------|------|-----------|--------|
| TICKET_DAILY | `Daily_YYYYMMDD` | 일별 티켓 이력 | ✅ (동일 스키마) | 13 |
| TICKET_WEEKLY | `Weekly_WNN` | 주별 티켓 요약 | ✅ (Daily + 주차) | 14 |
| TICKET_MONTHLY | `Monthly_*` | 월별 티켓 요약 | ✅ (Weekly + 월,SLA) | 15 |
| EQUIPMENT | `Equipment_*` | 설비 마스터 | ❌ (다른 스키마) | 10 |
| TEAM | `Team_*` | 팀원 통계 | ❌ (다른 스키마) | 8 |

### FR-002-2: 질문 유형별 시트 선택 규칙

#### 담당자 질문 (예: "김철수가 뭘 했어?", "김철수 업무")
- **대상 그룹**: TICKET_DAILY + TICKET_WEEKLY + TICKET_MONTHLY
- **제외**: EQUIPMENT (담당자 컬럼 없음), TEAM (통계 데이터)
- **필터 컬럼**: `담당자`

#### 기간 질문 (예: "이번 주 완료된 티켓", "12월 업무")
- **대상 그룹**: 기간에 해당하는 Daily/Weekly/Monthly 시트
- **예시**:
  - "이번 주" → 해당 주의 Daily_* + Weekly_WNN
  - "12월" → 12월 Daily_* + Weekly_* + Monthly_Summary
- **필터 컬럼**: `접수일자`, `완료일자`

#### 설비 질문 (예: "CVD 설비 고장 이력")
- **대상 그룹**: TICKET_DAILY + TICKET_WEEKLY + TICKET_MONTHLY
- **참조용**: Equipment_CVD (설비 상세 정보 JOIN 필요 시)
- **필터 컬럼**: `설비유형`

#### 통계 질문 (예: "A팀 처리 실적", "팀별 평균 처리시간")
- **대상 그룹**: TEAM
- **필터 컬럼**: `팀`, `담당자`

### FR-002-3: 시트 선택 알고리즘

```
입력: 사용자 질문, 시트 메타데이터
출력: 검색 대상 시트 목록 (최대 10개)

1. 키워드 추출
   - 담당자명: 패턴 매칭 ("~가 뭘 했어", "~의 업무", "~ 업무")
   - 날짜/기간: 정규식 ("이번 주", "12월", "20241217", "지난 주")
   - 설비유형: Equipment 시트의 설비유형 목록과 매칭 (CVD, Etching, Sputter 등)
   - 통계 키워드: "실적", "통계", "평균", "처리건수"

2. 질문 유형 분류 (우선순위 순)
   - 통계 중심: 통계 키워드 포함
   - 담당자 중심: 담당자명 포함
   - 기간 중심: 날짜/기간 포함
   - 설비 중심: 설비유형/설비ID 포함
   - 기본값: TICKET_DAILY + TICKET_WEEKLY + TICKET_MONTHLY

3. 시트 그룹 선택
   - 질문 유형에 따라 적절한 그룹 선택
   - 그룹 내 시트 중 관련 시트만 필터링

4. 시트 개수 제한
   - UNION ALL 성능을 위해 최대 10개 시트
   - 초과 시: 가장 최신 시트 우선 선택
   - 예: Daily 시트 7개 + Weekly 최신 2개 + Monthly 1개 = 10개
```

### FR-002-4: 시트 선택 실패 시 처리

시트 선택 결과가 0개인 경우:
1. 기본 시트 그룹 제안 메시지 출력
2. "검색 대상 시트를 특정할 수 없습니다. Daily, Weekly, Monthly 시트를 모두 검색할까요?"
3. 사용자 확인 후 전체 티켓 시트 검색 수행

---

## FR-004 구체화: 공통 컬럼 식별 및 UNION 쿼리 생성

### FR-004-1: 시트 그룹별 스키마 사전 분석

시스템 시작 시 각 시트 그룹의 공통 컬럼을 사전 계산하여 캐싱:

```json
{
  "TICKET_DAILY_WEEKLY_MONTHLY": {
    "common_columns": [
      "ticket_id", "접수일자", "고객사", "설비ID", "설비유형",
      "고장유형", "증상", "담당자", "팀", "상태",
      "조치내용", "완료일자", "소요시간"
    ],
    "daily_only": [],
    "weekly_only": ["주차"],
    "monthly_only": ["월", "SLA_충족"]
  }
}
```

### FR-004-2: UNION 쿼리 생성 전략

#### 전략 A - 공통 컬럼만 사용 (기본값)
- 모든 시트에 존재하는 컬럼만 SELECT
- 장점: 단순함, 오류 가능성 낮음
- 단점: 일부 정보 손실 (주차, 월, SLA_충족)

#### 전략 B - NULL 패딩 (향후 옵션)
- 없는 컬럼은 NULL로 채움
- 예: `SELECT ... NULL as 주차, NULL as 월 FROM Daily_*`
- 장점: 모든 정보 보존
- 단점: 쿼리 복잡도 증가

**기본값**: 전략 A (공통 컬럼)

### FR-004-3: UNION ALL 쿼리 생성 규칙

생성될 SQL 형태:

```sql
SELECT 'Daily_20241217' as source_sheet, ticket_id, 접수일자, 담당자, 상태, 조치내용
FROM Daily_20241217
WHERE 담당자 LIKE '%김철수%'

UNION ALL

SELECT 'Weekly_W52' as source_sheet, ticket_id, 접수일자, 담당자, 상태, 조치내용
FROM Weekly_W52
WHERE 담당자 LIKE '%김철수%'

UNION ALL

SELECT 'Monthly_Summary' as source_sheet, ticket_id, 접수일자, 담당자, 상태, 조치내용
FROM Monthly_Summary
WHERE 담당자 LIKE '%김철수%'

ORDER BY 접수일자 DESC
LIMIT 100
```

### FR-004-4: LLM 프롬프트 Few-shot 예제

LLM 프롬프트에 포함할 UNION ALL 예제:

```
## Multi-Sheet Query Examples

### 예제 1 - 담당자 검색
질문: "김철수가 뭘 했어?"
대상 시트: Daily_20241217, Daily_20241218, Weekly_W52
SQL:
SELECT 'Daily_20241217' as source_sheet, ticket_id, 접수일자, 담당자, 상태, 조치내용
FROM Daily_20241217 WHERE 담당자 LIKE '%김철수%'
UNION ALL
SELECT 'Daily_20241218' as source_sheet, ticket_id, 접수일자, 담당자, 상태, 조치내용
FROM Daily_20241218 WHERE 담당자 LIKE '%김철수%'
UNION ALL
SELECT 'Weekly_W52' as source_sheet, ticket_id, 접수일자, 담당자, 상태, 조치내용
FROM Weekly_W52 WHERE 담당자 LIKE '%김철수%'
ORDER BY 접수일자 DESC

### 예제 2 - 설비유형 검색
질문: "CVD 설비 고장 보여줘"
대상 시트: Daily_20241217, Weekly_W52
SQL:
SELECT 'Daily_20241217' as source_sheet, ticket_id, 접수일자, 설비ID, 설비유형, 고장유형, 담당자
FROM Daily_20241217 WHERE 설비유형 = 'CVD'
UNION ALL
SELECT 'Weekly_W52' as source_sheet, ticket_id, 접수일자, 설비ID, 설비유형, 고장유형, 담당자
FROM Weekly_W52 WHERE 설비유형 = 'CVD'
ORDER BY 접수일자 DESC

### 예제 3 - 상태 검색
질문: "이번 주 완료된 티켓"
대상 시트: Weekly_W52
SQL:
SELECT 'Weekly_W52' as source_sheet, ticket_id, 접수일자, 담당자, 상태, 완료일자
FROM Weekly_W52 WHERE 상태 = '완료'
ORDER BY 완료일자 DESC
```

### FR-004-5: 컬럼 매핑 규칙 (향후 확장)

현재 데이터에서는 컬럼명이 일치하지만, 향후 확장을 위한 매핑 테이블:

| 표준 컬럼명 | 허용 별칭 |
|------------|----------|
| 담당자 | 담당엔지니어, responsible_engineer, engineer |
| 상태 | status, 처리상태 |
| 완료일자 | completion_date, 종료일자 |

매핑 발견 시: `SELECT 원본컬럼 AS 표준컬럼명` 형태로 변환

---

## Non-Functional Requirements

### Performance (성능)

- **NFR-001**: P95 응답 시간 10초 이내, P50 5초 이내
- **NFR-002**: 5개 시트 UNION ALL 쿼리 실행 시간 3초 이내
- **NFR-003**: 시트 메타데이터 분석 시간 100ms 이내 (캐싱 적용 시 10ms)
- **NFR-004**: LLM SQL 생성 시간 3초 이내 (네트워크 지연 제외)
- **NFR-005**: 메모리 사용량 증가 100MB 이내

### Scalability (확장성)

- **NFR-006**: 최대 100개 시트 지원, UNION 쿼리는 최대 10개 시트
- **NFR-007**: 시트당 최대 10,000행 지원

### Usability (사용성)

- **NFR-008**: 쿼리 실행 중 진행 상태 표시 (예: "3개 시트 검색 중...")
- **NFR-009**: 결과 표시 시 시트별 건수 요약 제공 (예: "Daily: 150건, Weekly: 30건")

### Reliability (안정성)

- **NFR-010**: 5개 시트 중 1개 시트 쿼리 실패 시에도 나머지 4개 결과 반환 (부분 실패 허용)
- **NFR-011**: LLM 서버 장애 시 fallback 모델로 자동 전환

### Maintainability (유지보수성)

- **NFR-012**: 신규 시트 추가 시 자동 인식 (재시작 불필요)
- **NFR-013**: 시트 그룹 패턴을 설정 파일로 관리

---

## Error Handling Requirements

- **EH-001**: LLM이 유효하지 않은 SQL 생성 시 재시도 1회, 실패 시 단일 시트 쿼리로 fallback
- **EH-002**: 컬럼 타입 불일치 발견 시 VARCHAR로 자동 캐스팅
- **EH-003**: UNION ALL 쿼리 실행 실패 시 각 시트를 개별 조회하여 결과 병합
- **EH-004**: LLM 서버(10.249.22.191:11435) 연결 실패 시 로컬 fallback 모델(llama3.2:1b) 사용
- **EH-005**: 시트 읽기 실패 시 해당 시트 건너뛰고 나머지 시트로 쿼리 계속

---

## Technical Validation

### DuckDB UNION ALL 검증

테스트 쿼리:
```sql
SELECT 'Daily_20241217' as source, ticket_id, 담당자
FROM Daily_20241217
UNION ALL
SELECT 'Weekly_W52' as source, ticket_id, 담당자
FROM Weekly_W52
```
**기대 결과**: 컬럼 매핑 및 UNION 성공

### LLM UNION ALL 생성 능력 검증

gpt-oss:20b 모델로 다음 3가지 패턴 테스트:
1. 2개 시트 UNION ALL
2. 5개 시트 UNION ALL
3. WHERE 조건 포함 UNION ALL

**성공 기준**: 3가지 패턴 모두에서 실행 가능한 SQL 생성

### 프롬프트 토큰 제한 검증

- 시트 메타데이터: 시트당 최대 200 토큰
- 10개 시트 = 2000 토큰
- Few-shot 예제 = 1000 토큰
- 질문 + 기타 = 500 토큰
- **총 3500 토큰** (gpt-oss:20b 컨텍스트 충분)

---

## Implementation Guide

### 신규 파일

- `src/services/sheet_group_manager.py`: 시트 그룹 분류 및 공통 컬럼 분석
- `src/models/sheet_group.py`: SheetGroup, SheetGroupConfig 모델

### 수정 파일

- `src/services/sql_agent.py`: SheetGroupManager 의존성 추가, relevant_sheets 계산
- `src/services/llm_router.py`: Few-shot 예제 추가, UNION 쿼리 생성 로직
- `src/config.py`: 시트 그룹 패턴 설정 추가

### 구현 체크리스트

#### Phase 1: 기반 작업
- [ ] SheetGroup 모델 정의
- [ ] SheetGroupManager 서비스 구현
- [ ] 공통 컬럼 분석 로직 구현
- [ ] 시트 그룹 패턴 설정 파일 작성

#### Phase 2: LLM 프롬프트 개선
- [ ] UNION ALL Few-shot 예제 3개 추가
- [ ] 시트 선택 로직 프롬프트 작성
- [ ] 프롬프트 토큰 길이 검증

#### Phase 3: SQL 생성 로직
- [ ] sql_agent.py에 relevant_sheets 계산 로직 추가
- [ ] llm_router.py에 UNION ALL 생성 지원 추가
- [ ] 쿼리 실행 전 검증 로직 추가

#### Phase 4: 결과 처리
- [ ] 시트별 건수 집계 로직
- [ ] 대량 결과 페이지네이션
- [ ] 결과 요약 메시지 생성

#### Phase 5: 에러 처리 및 fallback
- [ ] UNION 실패 시 개별 쿼리 fallback
- [ ] 부분 실패 허용 로직
- [ ] 로깅 강화

#### Phase 6: 테스트
- [ ] 단위 테스트: SheetGroupManager
- [ ] 통합 테스트: User Stories 기반
- [ ] 성능 테스트: SC-003 검증
- [ ] Edge Cases 테스트
