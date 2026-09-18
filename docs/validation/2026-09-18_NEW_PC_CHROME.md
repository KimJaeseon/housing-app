# 새 PC 가이드 및 Chrome QA 검증

2026-09-18, 기존 Windows 개발 PC에서 실행.

- Python 3.12.14, Node.js 24.19.0, pnpm 11.19.0.
- Chrome 153.0.8010.52 headless 실행 성공.
- backend unittest 114개 통과.
- reference_rules 계약 검사 26개 통과.
- TypeScript 검사 및 Expo 웹 export 통과.
- Chrome qa.mjs 42개 결과 항목: 접근성 violations 없음, passed=false 없음.
- 문서의 로컬 링크 존재 여부 확인.
- 두 QA 스크립트의 JavaScript 구문 검사 통과.

QA 실행 결과는 frontend/qa/results.json과 해당 PNG에 기록된다. 기존 파일과 내용이 달라진 두 화면 PNG를 함께 갱신했다.

이번에는 실제 LH 조회 자동검사(qa-live-list.mjs), 모바일 실기 검사, 새 PC의 빈 환경에서 의존성 설치는 실행하지 않았다. 실제 조회 스크립트의 브라우저 채널도 Chrome으로 변경했으나 외부 API 호출 성공을 재검증한 것은 아니다.
