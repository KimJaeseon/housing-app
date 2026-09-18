# 폴더 정리 기록

2026-09-16

- mobile → frontend
- server → backend (Python 패키지 이름도 backend로 변경)
- 프로젝트 명세·검수·역할·설계·검증 기록 → docs
- 공통 JSON Schema와 합성 응답 → shared/contracts
- 설계용 Python 규칙·검사 → backend/contracts
- 루트 README와 PROJECT_INSTRUCTIONS는 진입 안내
- .venv는 실행 환경 경로 안정성을 위해 루트에 유지

문서 내 과거 파일명은 당시 기록일 수 있다. 현재 실행 명령은 루트 README.md를 기준으로 한다.
서버 36개 검사, 규칙 검사 26개 통과. 프론트엔드 타입 검사 통과. 접근성 검사 재실행 결과는 frontend/qa/results.json 참조.
