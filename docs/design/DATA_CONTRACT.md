# 공통 데이터 계약 0.1.0 (개발 초안)

작성일 2026-09-10. 원본 명세를 변경하지 않는다. 이 폴더는 API 서버 구현물이 아니다.

## 산출물과 상태

- search-result.schema.json: JSON Schema 2020-12 형식 초안. 별도 JSON Schema 검증기는 현재 미설치로 규격 적합성 검사는 미실행.
- *_completed.json, empty_partial.json, cancelled.json, failed.json, researching.json: 합성 응답 예시. 실제 공고·공식 행정구역 코드를 가장하지 않는다.
- reference_rules.py: 오프라인 판정 참조 코드. 수집기·법적 자격 판정·서버 권한 검사가 아니다.
- test_reference_rules.py / TEST_RESULTS.txt: 26개 합성 경계 검사 통과. 공식 원문 정확성·API 실연동·접근성 통과를 의미하지 않는다.
- MOBILE_CONTRACT_REVIEW.md: 모바일·품질 역할의 계약 요구사항. 해당 요구 중 아직 JSON으로 표현하지 않은 항목은 후속 버전에 반영한다.

## 데이터 구성

검색 작업은 고유 id와 단조 증가 revision을 가진다. 요청 재전송은 동일 idempotency key로 중복을 막고, 사용자의 새 검색은 새 작업을 만든다. 실제 작업 보유권은 서버가 관리하며 임의 id 조회로 다른 사용자의 맞춤 조건에 접근할 수 없어야 한다.

출처별 status와 오류는 공고의 verification_status와 별개다. 확인된 한 공고는 다른 기관 장애 때문에 미검증으로 바꾸지 않는다. 미연결 기관은 uncovered_source_ids로 노출한다. unsupported 출처만 있거나 계획 출처가 비어 있으면 정상 무결과로 처리하지 않는다.

공고 아래 모집 단위별 주소·가격·자격·접수 회차를 둔다. 보증금과 월세, 분양가를 다른 필드로 유지한다. 모든 사실은 value, unit, state, evidence_ids를 가진다. 알려진 숫자 0만 0으로 표현하고, 미확인은 null이다. announced_later는 원문에서 추후 확정을 명시할 때만 가능하다.

문서 버전은 original/correction/cancellation/repost를 구분한다. 정정 관계와 변경 필드 근거를 기록한다. 같은 제목만으로 합치지 않는다. 제목이나 게시일이 최신이라는 이유만으로 current_version_id를 확정하지 않는다.

근거는 원문 URL, 문서 버전, 페이지·표·문단 locator, 확인 시점을 포함한다. 개인정보 명단과 인증키는 근거에 복제하지 않는다. 실제 문서의 수집·재배포 조건은 별도 출처 등록부에서 확인한다.

## JSON Schema 외 의미 검증 (서버에서 추가 강제)

1. 모든 evidence_ids와 버전 참조는 같은 응답 내 존재해야 한다. 중복 id는 거부한다.
2. known은 null이 아니어야 하고 근거가 필요하다. unknown은 null과 이유가 필요하다. not_stated/announced_later도 원문 근거가 필요하다.
3. verified에는 공식 기관·지역·공공주택 유형·유효 회차·가격 조건·자격·정정 관계의 근거가 모두 필요하다. 사실상 필요한 항목이 빠지면 needs_review.
4. 기본 목록은 현재 검색에서 검증된 in_scope + verified + resolved + open/scheduled만 허용한다. 과거 검색의 확인시점을 새 검색 시점으로 바꾸지 않는다.
5. closed/cancelled/out_of_scope는 검색 목록에서 제외한다. 저장 상세에는 마감·취소 상태를 유지한다.
6. 시간은 오프셋 있는 ISO 8601이다. 판정·표시는 KST 기준. 참조 코드의 접수 구간은 [시작, 종료)이며 경계 동작은 공식 접수 규칙과 추가 대조해야 한다.
7. 날짜만 있을 때 시간을 00:00 또는 23:59로 채우지 않는다. raw_schedule을 보존하고 상태에 영향이 있으면 unknown.
8. 신청접수와 서류제출·발표 일정은 구분한다. 여러 접수 회차 중 진행 중 회차를 우선 표시하되 대상자 범위를 함께 읽어준다.
9. 취소는 종단 상태다. 늦게 온 완료 응답이 취소를 덮어쓰지 않는다. 다른 job id 또는 낮은 revision 응답은 화면에서 무시한다.
10. 입력하지 않은 맞춤 조건은 충족이 아니다. 합성 참조 코드는 미확인이 하나라도 있으면 needs_review로 보수적으로 처리한다. mismatch 항목은 사유로 별도 유지해야 한다.

## 내부 API 제안 (아직 미구현)

- POST /v1/search-jobs: 지역 선택, 선택형 맞춤 조건, 요청 중복방지 키. 202와 job id 반환.
- GET /v1/search-jobs/{id}: 이 JSON 응답. 조사 수명은 모바일 연결과 독립.
- POST /v1/search-jobs/{id}/cancel: 취소 요청. 신규 하위 작업 차단, 종단 상태 반환.
- 지역이 모호하면 작업 시작 전 REGION_AMBIGUOUS와 후보를 반환한다. 지원 범위 밖은 REGION_UNSUPPORTED.
- SOURCE_TIMEOUT, RATE_LIMITED, ACCESS_RESTRICTED, ATTACHMENT_FETCH_FAILED, DOCUMENT_PARSE_FAILED, REVISION_UNRESOLVED를 구분한다.
- 빈 결과는 작업 완료·계획 출처 성공·검증 대기 없음일 때만 표시. 일부 실패 시 '확인된 결과 없음, 일부 출처 확인 실패'.
- 저장 API는 로그인 필요. 인증 후 원래 공고로 복귀한다. 임시 맞춤 조건은 일반 로그·결과 URL·분석 이벤트에 포함하지 않는다.
- 호출 상한/재시도 횟수/보존 기간은 공식 서비스 제한 및 운영 환경 확인 후 정한다. 무제한 재시도는 허용하지 않는다.

## 남은 작업

JSON Schema 검증기 적용 및 교차 참조·verified 의미 검증 구현, 실제 최종 정정본 표본, 금액·단위와 중복 병합 검사, 보유권/취소 경쟁조건 API 테스트가 남아 있다. 이 문서의 선언만으로 검사를 통과한 것으로 처리하지 않는다.

다음 구현은 이 규격의 서버 검증기와 API 응답 스켈레톤이다. 실데이터 연동은 승인키와 허용된 원문 경로 검증을 병행한다.


## 2026-09-16 구현 갱신

실행 가능한 서버와 JSON Schema 검증기는 구현되어 있다. 위 미구현 표시는 최초 설계 당시 기록이다. 개발 계약 0.1.0에 선택 필드 collection(기간·페이지·수집 범위), excluded_notices(마감·취소 제외 내역), notice.listing(목록 원자료의 공개 날짜·상태·공식 링크)을 추가했다. 문서 버전 종류 unclassified는 목록만으로 원문 버전을 확정할 수 없음을 뜻한다. 실제 verified 차단은 유지한다. 모든 공고의 checked_in_job_id를 현재 작업과 대조하며 마감·취소를 active notices에 넣으면 서버 검증을 실패시킨다. 상세·목록은 원문 확인 완료를 주장하지 않는다.
