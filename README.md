# 수도권 공공주택 앱

현재 단계: LH 임대주택 목록의 기간·페이지 조회, 확인 필요/마감·취소 구분, 앱 목록·상세·공식 원문 연결. 원문 검증 완료 공고와 로그인·저장 기능은 아직 미구현이다.

- [프로그램 명세서](docs/PROGRAM_SPECIFICATION.md) — 기능·화면·API·데이터·현재 구현 및 후속 개발 기준
- [직접 실행·테스트 안내](docs/guides/RUN_AND_TEST.md)
- [키 암호화 저장 안내](docs/backend/KEY_MANAGEMENT.md)
- [제공된 API 가이드 반영 결과](docs/validation/2026-09-16_GUIDE_ALIGNMENT.md)
- [목록 연결 구현·검증 결과](docs/validation/2026-09-16_LIST_INTEGRATION.md)

## 실행

프로젝트 루트 PowerShell에서 서버:

```powershell
.\.venv\Scripts\python.exe -m backend.serve_lh --start 2026.08.01 --end 2026.09.16
```

frontend 폴더의 다른 PowerShell에서 `pnpm web`. pnpm이 PATH에 없으면 직접 테스트 안내의 번들 경로를 사용한다. 웹 주소는 http://localhost:8081.

일반 `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --no-access-log` 실행은 기본적으로 실제 LH 요청을 비활성화한다. 실제 목록 모드는 위 serve_lh 명령을 사용한다.

## 폴더

- docs/: 명세·설계·검증·사용 안내
- frontend/: Expo·React Native 화면, API 클라이언트, 웹 접근성 검사
- backend/: FastAPI, LH 목록 수집, 암호화 키 도구, 서버 검사
- shared/contracts/: JSON Schema와 합성 응답 예시
- .venv/: 로컬 Python 실행 환경
- .secrets/: 암호화 키 파일. Git 제외, 수동 배포·공유에서도 제외한다.

## 검사

루트: `.\.venv\Scripts\python.exe -m unittest discover -s backend -p "test_*.py"`, `.\.venv\Scripts\python.exe backend/contracts/test_reference_rules.py`.

frontend: `pnpm exec tsc --noEmit`, `pnpm exec expo export --platform web`, `node qa.mjs`.

실제 LH를 호출하는 별도 검사는 `node qa-live-list.mjs`. 실행 전 개발 서버를 종료한다. 자세한 기대 결과와 한계는 직접 테스트 안내를 따른다.

처음 읽을 지침: docs/PROJECT_BRIEF.md → docs/PROJECT_INSTRUCTIONS.md → docs/WORKFLOW.md. 모든 모바일 변경에 docs/design/ACCESSIBILITY_POLICY.md를 적용한다. 실제 VoiceOver·TalkBack 실기 검사는 미완료다.


2026-09-17: 공고 상세의 주택형별 공급정보 조회를 추가했다. 저장된 암호화 키를 재사용하며, 공급정보 API 별도 활용승인 확인이 필요하다. [공급정보 구현·검증 기록](docs/validation/2026-09-17_SUPPLY_INTEGRATION.md), [실행 및 직접 테스트](docs/guides/RUN_AND_TEST.md)를 참고한다.

2026-09-17 사용자 확인: 공급정보 API 활용신청 완료. 승인 반영 및 신청 이후 실제 성공 응답은 재확인 전이다. 상세 범위와 검수 기준은 프로그램 명세서에 통합했다.


최신 재확인 — 2026-09-17 12:04 (한국 시간) 재확인: 저장된 암호화 키로 새 목록 조사 후 서울번동3 정정공고의 공급정보를 실제 요청했다. HTTP 200, available, 주택형 3건 및 서버 스키마·의미 검증 통과. 승인 반영에 따른 접근 성공을 확인했다. 보증금·월 임대료는 API의 공고문 참조 응답으로 미확인 유지. 해당 공고는 마감 상태이며 신청 가능 공고로 승격하지 않았다. 앱에서는 기존 실패 결과를 재사용하지 않도록 새 검색 후 상세의 공급정보 조회를 실행한다.

## 소스 관리

프론트엔드·백엔드·공통 계약·문서를 하나의 GitHub 저장소로 관리한다. [GitHub 작업 안내](docs/guides/GITHUB_WORKFLOW.md)를 따른다.

