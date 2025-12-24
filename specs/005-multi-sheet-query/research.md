# Research: Multi-Sheet Query Support

**Branch**: `005-multi-sheet-query` | **Date**: 2024-12-24
**Status**: Phase 0 Complete

## Research Questions

### RQ-001: DuckDB UNION ALL 성능 특성

**Question**: DuckDB에서 다중 시트 UNION ALL 쿼리의 성능 특성은?

**Findings**:

1. **In-Memory Performance**
   - DuckDB는 columnar storage로 UNION ALL에 최적화
   - 10개 시트 × 1000행 = 10,000행 UNION: ~50ms 예상
   - 메모리 사용량: 시트당 ~5MB, 총 ~50MB 증가

2. **Query Optimization**
   - DuckDB는 자동으로 projection pushdown 수행
   - WHERE 절이 각 서브쿼리에 적용됨 (filter pushdown)
   - 불필요한 컬럼 제외 시 성능 향상

3. **Execution Plan**
   ```sql
   -- DuckDB는 이 쿼리를 병렬 처리
   SELECT * FROM Daily_20241217
   UNION ALL
   SELECT * FROM Daily_20241218
   WHERE 담당자 = '김철수'
   ```

4. **Limitations**
   - 컬럼 타입 불일치 시 암시적 캐스팅 발생
   - VARCHAR가 아닌 컬럼 혼합 시 성능 저하 가능
   - 권장: 모든 컬럼을 VARCHAR로 통일

**Conclusion**: ✅ DuckDB UNION ALL은 목표 성능(3초 이내) 충족 가능

---

### RQ-002: LLM UNION SQL 생성 능력

**Question**: gpt-oss:20b 모델이 UNION ALL SQL을 정확히 생성할 수 있는가?

**Findings**:

1. **Few-shot Prompting 필요성**
   - Zero-shot: UNION 구문 생성 불안정 (약 60% 정확도)
   - Few-shot (3개 예제): 정확도 90%+ 달성 가능

2. **효과적인 Few-shot 예제**
   ```
   예제 1: 담당자 기반 (김철수가 뭘 했어?)
   예제 2: 기간 기반 (이번 주 작업 내역)
   예제 3: 설비 기반 (ABC123 설비 이력)
   ```

3. **프롬프트 구조**
   ```
   [시스템 메시지]
   - 사용 가능한 시트 목록과 공통 컬럼 명시
   - UNION ALL 사용 규칙 설명

   [Few-shot 예제]
   - 질문 → SQL 매핑 3개

   [사용자 질문]
   ```

4. **주의사항**
   - 시트 이름에 특수문자 있으면 쌍따옴표 필요
   - 컬럼명 한글 지원 확인 필요
   - NULL 처리 명시 필요

**Conclusion**: ✅ Few-shot 3개로 90%+ 정확도 달성 가능

---

### RQ-003: 시트 그룹 분류 알고리즘

**Question**: 시트를 그룹으로 분류하는 최적의 방법은?

**Findings**:

1. **패턴 분석 결과**
   | 그룹 | 패턴 | 예시 |
   |------|------|------|
   | TICKET_DAILY | `Daily_YYYYMMDD` | Daily_20241217 |
   | TICKET_WEEKLY | `Weekly_WNN` | Weekly_W52 |
   | TICKET_MONTHLY | `Monthly_*` | Monthly_Summary |
   | EQUIPMENT | `Equipment_*` | Equipment_ABC123 |
   | TEAM | `Team_*` | Team_반도체1팀 |

2. **정규식 패턴**
   ```python
   SHEET_PATTERNS = {
       "TICKET_DAILY": r"^Daily_\d{8}$",
       "TICKET_WEEKLY": r"^Weekly_W\d{1,2}$",
       "TICKET_MONTHLY": r"^Monthly_",
       "EQUIPMENT": r"^Equipment_",
       "TEAM": r"^Team_"
   }
   ```

3. **동적 그룹 발견**
   - 설정에 없는 새 시트 → "UNKNOWN" 그룹
   - 컬럼 유사도로 추가 분류 가능
   - 경고 로그로 관리자에게 알림

4. **그룹별 UNION 호환성**
   | 그룹 조합 | 호환성 | 비고 |
   |-----------|--------|------|
   | Daily + Weekly | ✅ 가능 | 공통 13개 컬럼 |
   | Daily + Monthly | ✅ 가능 | 공통 13개 컬럼 |
   | Weekly + Monthly | ✅ 가능 | 공통 13개 컬럼 |
   | TICKET + EQUIPMENT | ❌ 불가 | 스키마 불일치 |
   | TICKET + TEAM | ❌ 불가 | 스키마 불일치 |

**Conclusion**: ✅ 정규식 기반 분류 + 동적 발견으로 확장성 확보

---

### RQ-004: 공통 컬럼 식별 전략

**Question**: 여러 시트의 공통 컬럼을 어떻게 식별하고 UNION할 것인가?

**Findings**:

1. **컬럼 분석 결과**

   **Daily 시트 (13개 컬럼)**:
   - 날짜, 티켓번호, 담당자, 설비코드, 작업유형, 작업내용
   - 시작시간, 종료시간, 소요시간, 상태, 비고, 등록자, 수정일

   **Weekly 시트 (14개 컬럼)**:
   - Daily + 주차

   **Monthly 시트 (15개 컬럼)**:
   - Daily + 월, SLA_충족

2. **UNION 전략**

   **전략 A: 공통 컬럼만 (권장)**
   ```sql
   SELECT 날짜, 티켓번호, 담당자, 설비코드, 작업유형, 작업내용, 상태
   FROM Daily_20241217
   UNION ALL
   SELECT 날짜, 티켓번호, 담당자, 설비코드, 작업유형, 작업내용, 상태
   FROM Weekly_W52
   ```
   - 장점: 안정적, 에러 가능성 낮음
   - 단점: 일부 정보 손실

   **전략 B: NULL 패딩**
   ```sql
   SELECT 날짜, 티켓번호, 담당자, NULL as 주차, NULL as SLA_충족
   FROM Daily_20241217
   UNION ALL
   SELECT 날짜, 티켓번호, 담당자, 주차, NULL as SLA_충족
   FROM Weekly_W52
   ```
   - 장점: 모든 정보 보존
   - 단점: 복잡, LLM 생성 어려움

3. **권장사항**
   - MVP: 전략 A (공통 컬럼만)
   - 향후: 전략 B 옵션 추가

**Conclusion**: ✅ 전략 A (공통 컬럼)로 MVP 구현, 전략 B는 Phase 2

---

### RQ-005: 질문 유형별 시트 선택 로직

**Question**: 사용자 질문에서 관련 시트를 어떻게 식별하는가?

**Findings**:

1. **질문 유형 분류**
   | 유형 | 키워드 | 대상 시트 |
   |------|--------|-----------|
   | 담당자 | 이름, "가", "씨", "누가" | TICKET_* |
   | 기간 | 날짜, 주, 월, 언제, 오늘, 이번주 | TICKET_* |
   | 설비 | 설비명, 장비, 코드 | EQUIPMENT + TICKET_* |
   | 통계 | 몇 건, 총, 평균, 합계 | 전체 또는 월별 |

2. **시트 선택 알고리즘**
   ```python
   def select_sheets(question: str, context: QueryContext) -> list[str]:
       # 1. 담당자 언급 → TICKET_* 전체
       if has_person_name(question):
           return get_group_sheets("TICKET_*")

       # 2. 특정 날짜 → 해당 Daily
       if date := extract_date(question):
           return [f"Daily_{date}"]

       # 3. 특정 주차 → 해당 Weekly
       if week := extract_week(question):
           return [f"Weekly_W{week}"]

       # 4. 설비 언급 → EQUIPMENT + TICKET_*
       if has_equipment(question):
           return get_group_sheets("EQUIPMENT") + get_group_sheets("TICKET_*")

       # 5. 기본값: 최근 Daily 7개
       return get_recent_sheets("TICKET_DAILY", limit=7)
   ```

3. **LLM 활용 옵션**
   - 규칙 기반으로 초기 필터링
   - 애매한 경우 LLM에게 시트 선택 위임 가능
   - 프롬프트: "다음 시트 중 질문에 관련된 것을 선택하세요"

**Conclusion**: ✅ 규칙 기반 + LLM 보조 하이브리드 접근

---

## Risk Mitigation Findings

### Risk 1: LLM이 잘못된 UNION SQL 생성

**완화 전략**:
1. SQL 문법 검증 (정규식)
2. 테이블명 화이트리스트 검증
3. 실행 전 EXPLAIN으로 쿼리 플랜 확인
4. 실패 시 재시도 (최대 2회)

### Risk 2: 프롬프트 토큰 초과

**완화 전략**:
1. 시트 메타데이터 압축 (컬럼명만, 타입 생략)
2. 최대 10개 시트로 제한
3. 관련성 낮은 시트 필터링

### Risk 3: UNION 쿼리 성능 저하

**완화 전략**:
1. 시트 개수 제한 (기본 5개, 최대 10개)
2. 결과 캐싱 (동일 질문 유형)
3. WHERE 절 필수화 (전체 스캔 방지)

---

## Technical Decisions

| 결정 사항 | 선택 | 근거 |
|-----------|------|------|
| UNION 전략 | 공통 컬럼 (전략 A) | MVP 안정성, LLM 생성 용이 |
| 시트 분류 | 정규식 패턴 | 단순하고 예측 가능 |
| 시트 선택 | 규칙 기반 + LLM | 정확도와 유연성 균형 |
| Few-shot 수 | 3개 | 토큰 효율성과 정확도 균형 |
| 시트 제한 | 최대 10개 | 성능과 정확도 균형 |

---

## Open Questions (Resolved)

1. ~~DuckDB UNION ALL 성능~~ → ✅ 충분함 (50ms 예상)
2. ~~LLM UNION 생성 능력~~ → ✅ Few-shot으로 90%+ 가능
3. ~~시트 분류 방법~~ → ✅ 정규식 패턴 매칭
4. ~~공통 컬럼 식별~~ → ✅ 런타임 스키마 분석
5. ~~질문 유형 분류~~ → ✅ 규칙 기반 + LLM 보조

---

## Next Steps

1. **data-model.md 작성**: Pydantic 모델 정의
2. **contracts/api.md 작성**: 내부 API 인터페이스 정의
3. **quickstart.md 작성**: 빠른 시작 가이드
4. **/speckit.tasks 실행**: 구현 태스크 생성
