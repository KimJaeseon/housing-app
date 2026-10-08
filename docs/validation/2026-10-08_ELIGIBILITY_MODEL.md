# 자격 적용 대상·예외 구조화 — 2026-10-08

이 문서는 첫 규칙 9개 단계의 검증 이력이다. 같은 날 후속 작업에서 규칙 46개·근거 47개 및 Schema 0.2.0으로 확장했다. 현재 파일·검사 결과는 [후속 확장 기록](2026-10-08_ELIGIBILITY_EXPANSION.md)을 따른다.

## 이번 구현

강서염창 정정공고 `2015122300020807`의 보존 PDF 8·9쪽을 pdfplumber로 추출하고 pypdfium2로 렌더링해 시각 대조했다. 보존 PDF의 SHA-256은 기존 `ecf4a3f2da9a75976de662566050b04e2bfcd58c34a18a2bef3cfc61ab76c252`와 일치한다. 이번 작업은 보존 문서의 검토이며 공식 사이트나 현재 상태를 새로 조회한 결과가 아니다.

- 자격 판단 기준일: 모집공고일 2026-09-17.
- 19세 미만 신청 제한 원칙과 미성년자 예외 4가지. 모든 예외의 법정대리인 동의 또는 대리, 자녀·형제자매의 동일 주민등록표 등재 등 조건을 보존했다.
- 주택소유 검증 대상: 일반 세대구성원, 청년 본인, 혼인 중이 아니며 단독세대주로 입주하려는 고령자 본인, 예비신혼부부의 혼인으로 구성될 세대.

총 10개 근거 사실(기준일 1개, 자격 9개)을 별도 `backend/eligibility_reviews/`에 등록했다. `backend/eligibility_conditions/`의 규칙 9개는 근거 ID와 공고 ID·PDF 해시에 연결한다. 기존 앱 표시용 `document_reviews/`의 12항목은 이번 내부 기록과 별개다.

`shared/contracts/eligibility-conditions.schema.json`과 `backend/eligibility_conditions.py`는 형식, 기준일, 근거 전체 대응, 대상, 연령, 주택 검증 범위, 예외의 부모 관계와 조건 누락을 검사한다. 숫자 부분 일치(19세를 9세로 변조), 예외 부모 누락·교차·순환, 법정대리인·주민등록 조건 누락을 거부한다. CLI는 PDF 바이트 해시까지 확인한다. JSON 간 대조는 원문 의미를 자동 증명하지 않으므로 새 규칙은 원문 시각 대조 후 등록한다.

## 검증 경계

`coverage=partial`, `applicant_evaluation=false`를 강제하며 소득·자산·전체 세대구성원 정의·주택소유 인정 예외·공급구분별 요건·결격 사유·최종 변경 공지를 미검토로 유지한다. 미성년자 예외는 다른 신청 요건을 면제하지 않으며, 주택소유 검증 대상 예외는 소득·자산 검증 대상을 축소하는 규칙이 아니다.

개인 입력 비교, 공고 `verified` 승격, 서버 응답 및 앱 화면에는 연결하지 않았다. 실제 iPhone·Android 기기 검사는 사용자 요청에 따라 제외했다. 화면 변경이 없어 웹 빌드·UI QA도 이번 변경에서는 실행하지 않았다.

## 재현

```powershell
.\.venv\Scripts\python.exe -m backend.eligibility_conditions --conditions backend/eligibility_conditions/2015122300020807.json --review backend/eligibility_reviews/2015122300020807.json --pdf docs/references/lh-notice-2015122300020807.pdf
```

기대 결과: `valid_partial`, `rules=9`, `applicant_evaluation=false`. 변경 PDF는 `invalid_eligibility`, 종료 코드 2.

## 검사 결과

- 자격 규칙 신규 검사 12개와 기존 임대조건·검토 기록·문서 파서 회귀 검사 43개, 합계 55개 통과.
- 기존 참조 규칙 검사는 별도로 26개 통과.
- 품질 검토에서 연령 부분 일치 및 예외 부모 관계 우회를 발견해 수정하고 부정 사례를 검사에 추가했다.
- 최초 일반 unittest 실행은 기본 임시 폴더 접근 오류와 기존 FastAPI TestClient 경로의 지연으로 중단했다. 작업 폴더 내 `tmp/test-temp`를 임시 폴더로 지정한 다음 영향받은 55개 검사를 실행했다. 서버 전체 재검사 완료로 보고하지 않는다.

통과 명령은 프로젝트 루트에서 다음과 같다.

```powershell
@'
import tempfile, unittest
from pathlib import Path
p = Path('tmp/test-temp').resolve()
p.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(p)
names = ['backend.test_eligibility_conditions', 'backend.test_structured_conditions', 'backend.test_document_review', 'backend.test_lh_document.DocumentTests']
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
raise SystemExit(not result.wasSuccessful())
'@ | .\.venv\Scripts\python.exe -
```

다음 작업은 전체 세대구성원 정의·주택소유 인정 예외·공급유형별 자격과 소득·자산 기준의 연결이다. 이후 별도 변경 공지와 공고 유효성을 조사하고 검증 완료 판정기에 연결한다.
