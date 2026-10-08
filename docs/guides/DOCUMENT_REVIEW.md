# 공고문 검토 기록 작성 절차

내부 자격 기록의 현재 Schema는 0.3.0이다. 추가 조건의 모든 AND 요건과 OR 대안을 보존하고, 소득/자산의 검증 대상을 주택소유 대상과 구분한다. 원문 표의 자산 금액을 가산율로 다시 계산해 대체하지 않는다. 수치 한도는 인정 자녀수 규칙에 연결하며 복수 페이지에 근거가 있으면 `source_locator`에 모두 표시한다. [현재 규칙 93개의 검증·미완료 범위](../validation/2026-10-08_ELIGIBILITY_DETAILS.md)를 참고한다.

자격 적용 대상·예외의 내부 구조화는 `backend/eligibility_reviews/`(기존 검토 Schema)와 `backend/eligibility_conditions/`(자격 전용 Schema)에 별도로 기록한다. 앱 표시용 기록에 자동 합치지 않는다. 기준일과 규칙별 근거, 성년/무주택 원칙의 예외 부모, 예외의 모든 조건, 미검토 범위를 보존한다. `python -m backend.eligibility_conditions --conditions ... --review ... --pdf ...`로 검사하며 `valid_partial`은 신청 자격 판정이 아니다. [실행 예시와 범위](../validation/2026-10-08_ELIGIBILITY_MODEL.md)를 참고한다.

이 절차는 새 LH 공고의 항목별 근거를 등록할 때 사용한다. 한 파일을 검사했다고 해서 공고 전체나 신청 자격이 확인 완료가 되지 않는다.

1. 공식 목록에서 공고 번호·제목·상태를 확인하고 공식 상세의 공고문 파일을 찾는다. 첨부가 여러 개이거나 정정·취소 관계가 불명확하면 한 파일을 임의로 선택하지 않는다.
2. 원본 PDF를 로컬 참고 자료로 보존한다. 추출한 텍스트와 표는 **후보**로만 취급한다. 검토 기록의 `facts`에 자동 복사하지 않는다.
3. PDF를 페이지별로 열어 후보를 눈으로 대조한다. 날짜는 대상·회차·한국 시간, 금액은 원문 단위·원화 환산·주택형·소득 유무·기본/전환 조건을 구별한다. OCR이 불명확한 부분은 확인값으로 등록하지 않는다.
4. `backend/document_reviews/공고번호.json`에 [기록 Schema](../../shared/contracts/document-review.schema.json)에 맞춰 작성한다. `source`에는 현재/원공고 번호, 정정 문구, PDF SHA-256과 쪽수를 넣는다. `review`에는 실제 검토 날짜·방법·검토 범위·미검토 범위를 넣는다. 각 사실에는 고유 ID, 근거 쪽과 다시 찾을 수 있는 `source_locator`를 넣는다.
5. 로컬에서 `python -m backend.document_review --review backend/document_reviews/공고번호.json --pdf 공식공고문.pdf`를 실행한다. 성공 시 공고 번호·항목 수·검토일이 출력된다. `invalid_review`와 종료 코드 2가 나오면 기록 또는 PDF를 수정한다. 이 검사는 구조·식별자·중복·쪽 범위·파일 해시를 검사하며, 본문 값과 환산의 진위를 자동 증명하지 않는다.
6. 서버에서 새 검색 후 해당 공고의 원문 조회를 확인한다. PDF 해시·정정 관계가 달라지거나 기록이 잘못되면 확인 항목이 표시되지 않아야 한다. 검사 결과와 수동 대조한 쪽·범위를 `docs/validation`에 기록한다.

현재 등록된 서울번동3 정정공고는 29쪽 PDF의 1·2·3·12쪽에서 선정한 17개 항목만 포함한다. 전체 자격과 별도 변경 공지는 미검토다. 검토일은 2026-09-17이며, 앱의 원문 조회 시각은 매 요청마다 별도로 기록된다.

서울번동3의 선정된 임대조건 7개는 [구조화 기록](../../backend/structured_conditions/2015122300020605.json)에도 연결했다. PDF 2쪽의 보증금·전환액 단위는 천원, 월 임대료는 원이므로 두 단위를 혼동하지 않는다. 대학생, 청년(소득 없음), 청년(소득 있음), 신혼부부·한부모가족을 합치지 않는다. [검증 기록](../validation/2026-10-01_BUNDONG_UNIT_CONVERSION.md)을 참조한다.

두 번째 서울오류 행복주택 공고는 29쪽 PDF의 1·2·15쪽에서 선정한 8개 항목을 포함한다. 검토일은 2026-10-01이며 공식 상세는 접수마감이다. `python -m backend.document_review --review backend/document_reviews/2015122300019941.json --pdf docs/references/lh-notice-2015122300019941.pdf`로 확인한다. [검증 범위](../validation/2026-10-01_SECOND_NOTICE.md)를 참조한다.

세 번째 강서염창 통합공공임대 정정공고는 38쪽 PDF의 1·6·21쪽에서 선정한 12개 항목을 포함한다. 원공고 6·21쪽도 대조해 현장접수 설명과 계약·입주 예정 연도를 확인했다. 6쪽의 59A 소득 1·2구간 기본 및 최대 증액·감액 금액을 구분했다. 2026-10-01 목록 조회 당시 `접수중`이었지만 앱은 신청 가능 여부를 확정하지 않는다. `python -m backend.document_review --review backend/document_reviews/2015122300020807.json --pdf docs/references/lh-notice-2015122300020807.pdf`로 검사한다. [정정 비교 기록](../validation/2026-10-01_REVISION_CANCELLATION.md)과 [전환 조건 검증](../validation/2026-10-01_RENT_CONVERSIONS.md)을 참조한다.
