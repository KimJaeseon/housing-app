# 최신 실행 안내 (2026-09-16 목록 연결 이후)

현재 상태와 실행 명령은 [직접 실행·테스트](../guides/RUN_AND_TEST.md), 검증 결과는 [목록 연결 보고서](../validation/2026-09-16_LIST_INTEGRATION.md)를 우선한다. 아래는 개발 단계별 기록으로 최신 상태와 다른 과거 설명이 포함되어 있다.

---

# 로컬 서버 실행 및 현재 상태

2026-09-10. FastAPI 검색 API 기본 구조와 서버 데이터 검증기 구현.

## 실행 (PowerShell, 프로젝트 폴더)

```powershell
Set-Location C:\data\menual\housing-app-guidelines
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

브라우저에서 http://127.0.0.1:8000/docs 를 연다. 종료는 Ctrl+C.
다른 PC에서는 Python 3.12 가상환경 생성 후 backend/requirements.lock.txt를 설치한다.

## 키 없이 로컬 검색 흐름 테스트

서버를 실행한 상태에서 별도 PowerShell:

```powershell
$taskHeaders = @{
  'X-Session-Token' = [guid]::NewGuid().ToString('N')
  'Idempotency-Key' = [guid]::NewGuid().ToString('N')
}
$taskJob = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/v1/search-jobs' -Headers $taskHeaders -ContentType 'application/json' -Body '{"region":"서울"}'
Invoke-RestMethod -Uri ('http://127.0.0.1:8000/v1/search-jobs/' + $taskJob.id) -Headers $taskHeaders
```

예상: 생성 202/queued, 조회 failed/ADAPTER_NOT_CONFIGURED. 실제 수집기가 없음을 정직하게 표현한다. 실패를 정상 0건으로 표시하지 않는다. 취소 테스트는 새 작업을 만든 후 조회 전에 POST /v1/search-jobs/{id}/cancel을 호출한다. 취소는 반복 호출해도 revision이 증가하지 않는다. 종료된 작업의 취소는 기존 종단 상태를 유지한다.

POST 생성 직후 백그라운드 작업을 제출한다. GET은 읽기 전용이다. 기본 설정에서는 작업이 ADAPTER_NOT_CONFIGURED로 종료한다. 응답 시점에 따라 queued/researching/failed가 보일 수 있다. LH 활성화 시에도 전체 공고 조사가 아닌 1페이지 연결 검사만 수행한다.

## 자동 검사

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_api -v
.\.venv\Scripts\python.exe backend/contracts/test_reference_rules.py
```

서버 검사 14개, 기존 판정 검사 26개 통과. JSON Schema 규격과 기존 5개 응답 예시의 적합성 검사도 이제 실행했다. 첫 검사에서 날짜 형식 검증 의존성 누락을 발견해 jsonschema format 패키지를 추가한 뒤 재검사 통과했다. httpx 사용에 관한 Starlette 지원 중단 예정 경고는 남아 있으나 테스트 실패는 아니다.

## 제한 및 다음 구현

- localhost 개발용, 메모리 저장(최대 1,000 작업); 재시작하면 작업 소멸. 단일 프로세스만 지원.
- 세션 토큰은 임시 작업 접근용 capability이며 Supabase 계정 인증이 아니다. 토큰은 공유하지 않는다.
- 서울·인천만 입력 지원. 경기도 시·군 정규화는 미구현이며 잘못된 지역을 추정하지 않고 오류 반환.
- 맞춤 입력·저장·로그인·앱·영속 작업 큐·TTL 정리·사용자별 속도 제한은 미구현. 메모리 작업 실행은 2개, 실행+대기는 8개로 제한한다.
- 구조와 일부 참조/값 의미를 검증하지만 전체 모집 자격·시간·금액의 의미 검증은 미완료.
- 공식 검증 어댑터가 없으므로 verified 공고 입력은 전부 거부한다. 미완성 검증으로 신청 가능 정보를 내보내지 않는다.
- 실제 LH 목록 테스트 도구는 API_TEST_GUIDE.md 참조. 목록 응답 성공만으로 원문 검증 완료가 되지 않는다.

다음 단계: 승인키로 목록 응답 구조 확인 → 허용된 상세·첨부 경로 검증 → 공고 검증 어댑터와 실제 작업 큐 연결 → 경기도 지역 정규화 및 모바일 연동.

## 0.2 단계 - LH 연결 검사 통합

서버·작업 큐·LH 도구 검사 34개와 실제 HTTP 기동 검사 통과. 기존 판정 검사 26개는 이전 단계 통과 기록이며 이번 변경 대상이 아니다. 승인키 환경변수의 존재 여부만 확인했고 미설정이었다. 실제 LH 요청 미실행.

- 연결 검사는 기본 비활성. LH_ENABLE_PROBE=1, LH_SERVICE_KEY, LH_POSTED_DATE, LH_CLOSING_DATE가 있어야 외부 요청한다.
- 한 검색당 임대주택(06) 목록 1페이지, 최대 요청 건수 3개. 전체 유형·페이지 수집 아님.
- 성공 신호도 RESPONSE_VERIFICATION_PENDING으로 반환한다. 미검증 공고를 기본 목록에 넣지 않는다.
- 재시도는 자동 실행하지 않는다. 사용자 새 검색은 새 Idempotency-Key를 사용한다.
- 대기 중 취소는 외부 호출 전 차단한다. 이미 전송된 HTTP 요청은 강제 중단하지 못하지만 늦은 응답은 취소 상태를 덮어쓰지 않는다. 요청 timeout은 15초이며 전체 작업의 강제 종료 시한은 미구현이다.
- 프로세스 재시작·다중 프로세스·영속 큐 복구는 아직 지원하지 않는다.

### 숨김 키 입력 후 서버 실행

```powershell
.\.venv\Scripts\python.exe -m backend.serve_lh --posted 2026.09.01 --closing 2026.09.30
```

일반 인증키(Decoding)를 숨김 입력한다. 날짜는 공식 가이드와 표본에 맞춘다. 위 명령은 서버만 기동하며 실제 호출은 /v1/search-jobs 검색 요청 때 발생한다. /docs 또는 위 PowerShell 예시로 서울·인천 검색 후 GET으로 진행 상태를 확인한다. 키는 프로세스 환경에만 유지하고 종료 후 제거한다. 공개 배포에 사용하지 않는다.

다음 필수 단계는 실응답 포장 구조·페이지·원문 연결 검증이며 승인키 없이는 확인 완료로 진행할 수 없다. 키 자체를 대화로 공유하지 않는다.

## 승인키 저장 방식 업데이트 (2026-09-16)

반복 숨김 입력 대신 로컬 암호화 파일을 자동으로 읽는다. 최초 등록 및 키 교체는 KEY_MANAGEMENT.md를 따른다. serve_lh는 저장된 키를 새 평문 환경변수로 복사하지 않는다. 기존 프로세스 한정 키 안내보다 이 절이 우선한다. 서버 자동검사 현재 52개 통과.


## 실제 연결 검증 (2026-09-16)

암호화 키 파일을 사용한 LH API 연결과 목록 응답 구조 검증을 통과했다. 서울 임대주택 표본 2건은 모두 접수마감이다. 서버는 공고 검증 미완료를 RESPONSE_VERIFICATION_PENDING으로 유지한다. 최신 결과: ../validation/2026-09-16_LH_LIVE.md. 서버 회귀 검사 60개 통과.

