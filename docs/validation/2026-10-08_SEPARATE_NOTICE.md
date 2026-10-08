# 별도 공지 근거 연결 첫 단계

2026-10-08. P4의 별도 공지 캡처·보존·로컬 검사 단계다. 공지 전체 검색과 법령 검토 완료, 운영 판정기 또는 API 연결을 뜻하지 않는다.

## 실제 공식 근거

- [LH 공지 원문](https://apply.lh.or.kr/lhapply/apply/noti/an/view.do?bbsSn=9102835612&ccrCnntSysDsCd=03&mi=1079): 강서염창 통합공공임대주택 청약접수결과, 게시일 2026-10-01.
- [첨부 PDF](https://apply.lh.or.kr/lhapply/lhFile.do?fileid=68835087): 2쪽, SHA256 `c986139c9f4dd2b274caa1e3c1afe8695024563cac1113e66d67619af0bce544`.
- 캡처 시각은 `backend/separate_notices/9102835612.json`에 보존한다. 웹 조회와 공개 HTTPS 캡처를 사용했으며 API 키·쿠키·사용자 세션을 보내지 않았다.
- PDF 두 쪽의 텍스트 추출과 렌더링을 대조했다. 2쪽에는 우선공급 미달 호수가 일반공급으로 전환된다는 안내가 있다. 이번 작업은 경쟁률·전환 호수의 자격/금액 규칙 반영을 하지 않았다.

제목·첨부명·문서 내용은 강서염창과 관련되지만 모집공고 번호 직접 연결 근거는 아직 없다. 따라서 `candidate_official_id=2015122300020807`, `relation=candidate`, `coverage=partial`로만 기록한다. 이 한 건은 최신 변경 없음이나 전체 공지 조사의 증거가 아니다.

## 구현

`backend/separate_notice.py`는 고정 LH 공지 URL을 요청 전에 검사하고 리다이렉트를 차단한다. HTML은 1MiB, PDF는 각 10MiB, 첨부는 최대 5개로 제한한다. 공지 번호·제목·게시일·본문·첨부 파일 ID를 파싱하며 외부 링크, 중복·지원하지 않는 첨부, PDF 서명 부재를 거부한다. 복수 PDF를 모두 보존하며 하나를 임의로 선택하지 않는다.

보존 HTML은 공개 공지 본문·첨부 링크만 직렬화한 추출본이다. 페이지의 폼·세션 값·스크립트·탐색 영역을 보존하지 않는다. 원 응답의 SHA256은 출처 지문으로 기록하고, 추출본의 별도 SHA256을 실제 파일과 검사한다. 원 응답 전체 바이트는 저장하지 않으므로 원 응답 해시를 로컬에서 재검사할 수는 없다. 저장 파일은 공개 추출 HTML과 원 PDF다.

추출본의 공백을 정규화하고 `.gitattributes`로 이 HTML의 Git 줄바꿈 변환을 막는다. 커밋에 들어갈 HTML·PDF 바이트의 해시가 기록과 일치하는 것도 확인했다. 마지막 추출 보완 후 전용 검사 20개를 재검사했다.

`shared/contracts/separate-notice.schema.json`은 후보 관계와 부분 검토 상태를 강제한다. `load_snapshot`은 Schema·대상 공고·고정 파일명·경로 범위·모든 파일 해시·HTML 재파싱·첨부 목록 일치를 검사한다. 이는 저장 근거의 일관성 검사이며 원문 내용의 법적 적용성이나 전체 조사 완료를 자동 증명하지 않는다.

검증 관문에 다음 옵션을 추가했다.

```powershell
./.venv/Scripts/python.exe -m backend.verification_gate --conditions backend/eligibility_conditions/2015122300020807.json --review backend/eligibility_reviews/2015122300020807.json --pdf docs/references/lh-notice-2015122300020807.pdf --separate-notice backend/separate_notices/9102835612.json --artifact-dir docs/references
```

정상 스냅샷은 `valid_candidate`와 첨부 수를 반환하지만 `SEPARATE_NOTICES_PENDING` 및 `SEPARATE_NOTICE_RELATION_UNCONFIRMED`를 유지한다. 잘못된 스냅샷은 `SEPARATE_NOTICE_ARTIFACT_INVALID`, 종료 코드 2를 반환한다. 기존 자격 자료가 유효하면 93규칙 검사 결과는 유지한다. 부분 자료는 종료 코드 1이며 verified 승격은 계속 차단한다.

## 다음 순서

검증: 서버 전체 213개와 참조 규칙 26개 통과. 별도 공지·관문 전용 검사 20개를 포함한다. 실제 저장 근거 재검사, 제목/ID 오류, 외부 URL·리다이렉트, 파일 변경·누락, 다중 첨부 중 후속 파일 누락, 용량 초과, 관계 완료 위조와 미완료 사유 유지를 검사했다. 기존 Starlette deprecation 경고는 비차단이다.

1. 별도 공지 목록 검색·페이지 범위·검색 시점과 누락을 기록하고, 공고 번호 직접 연결 및 변경 영향 검토 근거를 추가한다.
2. 법령·별첨의 적용 시점과 PDF 문구 충돌을 공식 근거로 확인한다. 원 금액표·갱신표 등 미검토 차원도 완료해야 한다.
3. 필수 근거 전체의 긍정·누락·충돌 판정을 구현한 뒤 API와 화면에 사유를 연결한다. 앱의 verified는 그 전에 열지 않는다.

화면 변경이 없어 웹 UI 검사는 이번 범위에서 실행하지 않았다. 실제 iPhone·Android 기기 테스트는 사용자 요청에 따라 제외했다.
