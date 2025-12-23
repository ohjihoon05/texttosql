# Feature Specification: 테스트용 Excel 데이터 생성

**Feature Branch**: `002-test-data-generation`
**Created**: 2025-12-23
**Status**: Draft
**Input**: 반도체 설비 CS 데일리 리포트 테스트용 Excel 파일(30개 시트, ~3MB) 생성 및 Text-to-SQL 시스템 검증

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 테스트용 Excel 파일 생성 (Priority: P1)

개발자가 Text-to-SQL 시스템을 검증하기 위해 실제 CS 데일리 리포트와 유사한 구조의 테스트용 Excel 파일을 생성한다. 보안상 실제 데이터를 사용할 수 없으므로 현실적인 더미 데이터가 필요하다.

**Why this priority**: 테스트 파일이 없으면 시스템 검증 자체가 불가능함

**Independent Test**: Excel 파일이 생성되고 DuckDB로 읽을 수 있으면 성공

**Acceptance Scenarios**:

1. **Given** 스크립트 실행 환경, **When** 데이터 생성 스크립트 실행, **Then** 30개 시트가 포함된 약 3MB Excel 파일 생성
2. **Given** 생성된 Excel 파일, **When** DuckDB로 각 시트 로드, **Then** 모든 시트가 정상적으로 DataFrame으로 변환됨
3. **Given** 생성된 Excel 파일, **When** Chainlit 앱에서 파일 로드, **Then** 스키마가 정상 추출되고 질의 준비 완료

---

### User Story 2 - 담당자 기반 질의 테스트 (Priority: P1)

사용자가 "김철수가 뭘 했어?", "이영희 담당 건은?" 같은 담당자 기반 자연어 질문을 하면 해당 담당자의 작업 이력이 조회된다.

**Why this priority**: 가장 일반적인 질의 패턴이며 핵심 기능 검증

**Independent Test**: 담당자 이름으로 질문했을 때 해당 담당자의 데이터만 반환되면 성공

**Acceptance Scenarios**:

1. **Given** Excel 데이터 로드 완료, **When** "김철수가 뭘 했어?" 질의, **Then** 김철수 담당 작업 목록 반환
2. **Given** Excel 데이터 로드 완료, **When** "이영희가 처리한 건 보여줘" 질의, **Then** 이영희 담당 CS 건 목록 반환
3. **Given** 존재하지 않는 담당자, **When** "홍길동이 뭘 했어?" 질의, **Then** "해당 담당자의 데이터가 없습니다" 안내

---

### User Story 3 - 설비/장비 기반 질의 테스트 (Priority: P1)

사용자가 "CVD 장비 이슈 뭐 있어?", "에칭 설비 고장 건은?" 같은 설비 유형 기반 질문을 하면 해당 설비의 CS 이력이 조회된다.

**Why this priority**: 반도체 설비 도메인의 핵심 질의 패턴

**Independent Test**: 설비명/장비명으로 질문했을 때 관련 데이터만 반환되면 성공

**Acceptance Scenarios**:

1. **Given** Excel 데이터 로드 완료, **When** "CVD 설비 문제 뭐 있어?" 질의, **Then** CVD 관련 CS 건 목록 반환
2. **Given** Excel 데이터 로드 완료, **When** "스퍼터 장비 고장 이력" 질의, **Then** 스퍼터링 장비 고장 건 반환
3. **Given** Excel 데이터 로드 완료, **When** "에칭 설비 현황" 질의, **Then** 에칭 설비 관련 전체 현황 반환

---

### User Story 4 - 날짜/기간 기반 질의 테스트 (Priority: P2)

사용자가 "지난주 CS 건수", "12월 첫째주 이슈" 같은 시간 기반 질문을 하면 해당 기간의 데이터가 조회된다.

**Why this priority**: 데일리 리포트 특성상 시간 기반 필터링 필수

**Independent Test**: 기간 표현이 포함된 질문에 해당 기간 데이터만 반환되면 성공

**Acceptance Scenarios**:

1. **Given** Excel 데이터 로드 완료, **When** "이번 달 CS 건수는?" 질의, **Then** 해당 월 CS 건수 집계 반환
2. **Given** Excel 데이터 로드 완료, **When** "12월 15일 이슈" 질의, **Then** 해당 날짜 CS 건 목록 반환
3. **Given** Excel 데이터 로드 완료, **When** "최근 일주일 고장 건수" 질의, **Then** 최근 7일간 고장 건수 집계 반환

---

### User Story 5 - 복합 조건 질의 테스트 (Priority: P2)

사용자가 "김철수가 이번 주 처리한 CVD 이슈"처럼 담당자+기간+설비를 조합한 복합 질문을 한다.

**Why this priority**: 실제 업무에서 복합 조건 질의가 빈번함

**Independent Test**: 여러 조건이 조합된 질문에 모든 조건을 만족하는 데이터만 반환

**Acceptance Scenarios**:

1. **Given** Excel 데이터 로드 완료, **When** "김철수가 12월에 처리한 CVD 건" 질의, **Then** 세 조건 모두 만족하는 데이터 반환
2. **Given** Excel 데이터 로드 완료, **When** "이번 주 스퍼터 장비 고장 담당자" 질의, **Then** 해당 기간 스퍼터 고장 건 담당자 목록

---

### User Story 6 - 집계/통계 질의 테스트 (Priority: P2)

사용자가 "이번 달 설비별 고장 건수", "담당자별 처리 현황" 같은 집계성 질문을 한다.

**Why this priority**: 리포트 특성상 집계/요약 질의 빈번

**Independent Test**: 집계 질문에 그룹화된 통계 데이터가 반환되면 성공

**Acceptance Scenarios**:

1. **Given** Excel 데이터 로드 완료, **When** "설비별 CS 건수" 질의, **Then** 설비 유형별 건수 집계 테이블 반환
2. **Given** Excel 데이터 로드 완료, **When** "담당자별 처리 현황" 질의, **Then** 담당자별 처리 건수 집계 반환
3. **Given** Excel 데이터 로드 완료, **When** "고장 유형별 통계" 질의, **Then** 고장 유형 분류별 통계 반환

---

### Edge Cases

- 시트 이름에 특수문자나 한글이 포함된 경우 정상 로드 되는가?
- 빈 시트가 있을 경우 어떻게 처리하는가?
- 날짜 형식이 다양한 경우 (2024-12-15, 12/15, 12월 15일) 정상 파싱되는가?
- 담당자 이름이 부분 일치할 경우 (김철 vs 김철수) 어떻게 처리하는가?
- 설비명 약어와 정식 명칭 혼용 시 (CVD vs Chemical Vapor Deposition) 동일하게 인식하는가?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템 MUST 30개 시트를 포함한 테스트용 Excel 파일 생성
- **FR-002**: 각 시트 MUST 반도체 CS 리포트에 적합한 컬럼 구조 보유 (날짜, 담당자, 설비유형, 고장유형, 조치내용, 상태 등)
- **FR-003**: 테스트 데이터 MUST 현실적인 반도체 설비 용어 및 담당자명 포함
- **FR-004**: 생성된 파일 MUST DuckDB read_xlsx로 정상 로드 가능
- **FR-005**: 테스트 데이터 MUST 다양한 날짜 범위 포함 (최소 3개월)
- **FR-006**: 시스템 MUST 담당자 이름 기반 자연어 질의 처리
- **FR-007**: 시스템 MUST 설비/장비 유형 기반 자연어 질의 처리
- **FR-008**: 시스템 MUST 날짜/기간 기반 자연어 질의 처리
- **FR-009**: 시스템 MUST 복합 조건 (담당자+설비+기간) 질의 처리
- **FR-010**: 시스템 MUST 집계/통계 질의 처리 (GROUP BY 연산)

### Key Entities

- **CS 티켓 (CS Ticket)**: 고객 서비스 요청 건. 티켓ID, 접수일, 고객사, 설비유형, 고장유형, 담당자, 상태, 조치내용 포함
- **담당자 (Engineer)**: CS 처리 담당 엔지니어. 이름, 소속팀, 전문분야
- **설비 (Equipment)**: 반도체 제조 장비. 설비ID, 설비유형(CVD, Etching, Sputter 등), 고객사, 설치일
- **고장 유형 (Issue Type)**: H/W 고장, S/W 오류, 정기점검, 부품교체 등 분류
- **시트 (Sheet)**: 일별/주별/설비별 등 다양한 관점의 리포트 시트

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 생성된 Excel 파일이 25~35개 시트 포함, 2~4MB 크기
- **SC-002**: 모든 시트가 DuckDB로 5초 이내 로드 완료
- **SC-003**: 담당자 기반 질의 정확도 90% 이상 (10건 질의 중 9건 이상 정확한 결과)
- **SC-004**: 설비 기반 질의 정확도 90% 이상
- **SC-005**: 날짜/기간 기반 질의 정확도 85% 이상
- **SC-006**: 복합 조건 질의 정확도 80% 이상
- **SC-007**: 집계 질의 정확도 85% 이상
- **SC-008**: 평균 질의 응답 시간 10초 이내 (캐시 미적용 기준)

## Test Data Specification

### 시트 구성 (30개)

| 시트 번호 | 시트명 | 설명 | 예상 행 수 |
|-----------|--------|------|-----------|
| 1-7 | Daily_YYYYMMDD | 일별 CS 리포트 (최근 7일) | 각 50-100건 |
| 8-11 | Weekly_WNN | 주별 요약 (최근 4주) | 각 200-300건 |
| 12 | Monthly_Summary | 월별 집계 | 500건 |
| 13-17 | Equipment_CVD, Equipment_Etching 등 | 설비유형별 이력 | 각 100-200건 |
| 18-22 | Team_A, Team_B 등 | 팀별 담당 건 | 각 100-150건 |
| 23-25 | Customer_삼성, Customer_SK 등 | 고객사별 | 각 150-250건 |
| 26-28 | Status_진행중, Status_완료 등 | 상태별 | 각 100-300건 |
| 29 | Parts_Inventory | 부품 재고 현황 | 200건 |
| 30 | Engineer_Performance | 엔지니어 성과 요약 | 50건 |

### 컬럼 구조 (주요 시트)

**Daily/Weekly 시트**:
- ticket_id, 접수일자, 고객사, 설비ID, 설비유형, 고장유형, 증상, 담당자, 상태, 조치내용, 완료일자, 소요시간

**Equipment 시트**:
- 설비ID, 설비명, 설비유형, 고객사, 설치일, 최근점검일, 누적고장건수, 주요고장이력

**Team 시트**:
- 담당자, 팀, 처리건수, 평균처리시간, 전문분야, 담당고객사

### 테스트 데이터 요소

**담당자 목록** (15명):
- 김철수, 이영희, 박민수, 정수진, 최동욱, 한지민, 오승환, 강예린, 윤성준, 임하늘, 조현우, 서지원, 남궁민, 황보람, 전인수

**설비 유형** (8종):
- CVD (Chemical Vapor Deposition)
- Etching (에칭)
- Sputter (스퍼터링)
- Diffusion (확산로)
- CMP (Chemical Mechanical Polishing)
- Ion Implant (이온주입)
- Cleaning (세정)
- Metrology (계측)

**고장 유형** (6종):
- H/W 고장, S/W 오류, 센서 이상, 부품 마모, 정기점검, 긴급호출

**고객사** (5개):
- 삼성전자, SK하이닉스, 마이크론, 인텔, TSMC

**상태** (4종):
- 접수, 진행중, 완료, 보류

## 테스트 질의 예시

### 담당자 기반
1. "김철수가 뭘 했어?"
2. "이영희 담당 건은?"
3. "박민수가 처리한 CVD 이슈"
4. "정수진이 이번 주 뭐 했어?"

### 설비 기반
1. "CVD 설비 고장 건"
2. "에칭 장비 이슈 현황"
3. "스퍼터 문제 뭐 있어?"
4. "CMP 정기점검 건"

### 기간 기반
1. "오늘 CS 건"
2. "이번 주 고장 현황"
3. "12월 CS 통계"
4. "지난달 대비 증감"

### 복합 조건
1. "김철수가 12월에 처리한 CVD 건"
2. "삼성전자 에칭 설비 이번 달 이슈"
3. "이번 주 완료된 H/W 고장 건"

### 집계/통계
1. "설비별 고장 건수"
2. "담당자별 처리 현황"
3. "고객사별 CS 통계"
4. "고장 유형별 분포"
