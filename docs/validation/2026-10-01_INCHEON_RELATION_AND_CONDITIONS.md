# 인천 취소 후 공고 관계 및 조건 구조화 — 2026-10-01

## LH 공식 이력 재조회

LH 목록 API(인천, 임대주택 유형 06, 2025.02.01~2025.05.31)와 상세 네 건을 다시 조회했다.

| 공고 ID | 공식 상세에서 확인한 관계 | 처리 |
|---|---|---|
| `2015122300017558` | [원공고](https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=2015122300017558&ccrCnntSysDsCd=03&uppAisTpCd=06&aisTpCd=09&mi=1026)의 현재 공고 값은 `…7563` | 기존 모집 원본 |
| `2015122300017563` | [취소공고](https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=2015122300017563&ccrCnntSysDsCd=03&uppAisTpCd=06&aisTpCd=09&mi=1026)의 원공고 값은 `…7558`, 취소 사유는 `인천권역 3개소 재공고 예정` | 취소·PDF 없음 |
| `2015122300017565` | [새 공고](https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=2015122300017565&ccrCnntSysDsCd=03&uppAisTpCd=06&aisTpCd=09&mi=1026)의 현재 공고 값은 `…7569`; 원공고 값은 비어 있음 | 새 이력의 원본, PDF 첨부 있음 |
| `2015122300017569` | [정정공고](https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=2015122300017569&ccrCnntSysDsCd=03&uppAisTpCd=06&aisTpCd=09&mi=1026)의 원공고 값은 `…7565` | 신청자격 관련 기타 안내 및 별지 1·7 서식 일부 추가·정정 |

새 공고와 정정공고는 제목·지역·모집 시점상 취소 상세에서 예고한 재공고의 **강한 후보**다. 그러나 새 공고 상세에는 취소 공고 `…7563`이나 그 원공고 `…7558`의 번호가 없고, 반대 방향의 명시적 연결도 확인하지 못했다. 따라서 취소 이력과 새 이력을 확정 관계로 합치거나 취소 공고의 값을 승계하지 않는다. 새 정정본은 신청자격 관련 변경이므로 별도 전체 문서 검토 전에는 확인 항목을 제공하지 않는다. [새 공고 보존 상세](../references/lh-detail-2015122300017565.html)와 [정정본 보존 상세](../references/lh-detail-2015122300017569.html)를 회귀검사에 사용한다.

## P3 첫 구조화 기록

[강서염창 정정공고 PDF](../references/lh-notice-2015122300020807.pdf)의 6쪽에서 검토한 일반공급·우선공급 접수 회차 2개와 59A 소득 1·2구간의 **기본** 임대조건 2개를 [구조화 기록](../../backend/structured_conditions/2015122300020807.json)에 넣었다. 각 항목은 [검토 사실](../../backend/document_reviews/2015122300020807.json)의 ID에 연결하고 공고 ID·PDF SHA-256으로 문서 버전을 고정했다. 접수 시각은 `Asia/Seoul` 오프셋을 보존한다. 현장 접수 제한은 안내 문구로 남기며 개인의 신청 자격을 판정하지 않는다.

PDF 표의 단위는 **원**이다. 1구간 보증금 90,663,000원·월 659,460원, 2구간 보증금 103,615,000원·월 753,670원을 기본 조건으로만 기록했다. 같은 표의 최대 증액·감액 전환은 아직 구조화하지 않았고 이 금액들과 섞지 않는다. 날짜·금액·대상·근거 ID·PDF 해시가 어긋나면 [검사 도구](../../backend/structured_conditions.py)가 거부한다.

```powershell
.venv\Scripts\python.exe -m backend.structured_conditions --conditions backend/structured_conditions/2015122300020807.json --review backend/document_reviews/2015122300020807.json --pdf docs/references/lh-notice-2015122300020807.pdf
```

이 데이터는 검토용 내부 기록이다. 앱의 접수 중 판정, 공급정보 API 금액, 개인 적격 판단 또는 `verified` 승격에는 아직 사용하지 않는다. 후속 작업은 최대 전환 조건의 근거 대조, 다른 표본의 단위·대상 모델링, 별도 변경 공지 확인이다.

서버 전체 회귀검사 155개와 접수 상태 참조 규칙 26개가 통과했고, 위 로컬 PDF 대조 CLI는 `valid / windows=2 / rents=2`를 반환했다. 모바일 실기 접근성 검사는 이번 변경에서 실행하지 않았다.
