# GitHub 저장소 관리

이 프로젝트는 frontend, backend, shared/contracts, docs를 한 저장소에서 관리한다.

- main: 검토된 기준 코드. 기능 개발은 feature/기능명, 수정은 fix/수정명 브랜치에서 진행하고 Pull Request로 합친다.
- API 변경 시 backend, frontend, shared/contracts와 관련 명세를 함께 수정한다.
- frontend/pnpm-lock.yaml과 backend/requirements.lock.txt는 함께 버전 관리한다.
- .secrets, .venv, .env, node_modules, 빌드 결과와 tmp는 업로드하지 않는다. 키는 docs/backend/KEY_MANAGEMENT.md의 절차로 각 PC에 별도 설정한다.
- 기존 frontend/qa와 docs/validation 자료는 검증 이력으로 보존한다. 재검사 결과는 변경 내용을 검토하고 필요한 증거만 커밋한다.
- 커밋 전 git status와 git diff --cached를 확인한다. 전체 폴더를 압축해 공유하면 Git 제외 규칙이 적용되지 않으므로 주의한다.

## 새 PC에서 시작

1. 저장소를 clone한다.
2. Python 3.12 가상환경을 .venv에 만들고 backend/requirements.lock.txt를 설치한다.
3. frontend에서 pnpm install --frozen-lockfile을 실행한다.
4. docs/guides/RUN_AND_TEST.md에 따라 키 설정과 실행을 진행한다.

## 변경 검증

백엔드 변경은 README의 Python 검사, 프론트엔드 변경은 TypeScript·웹 빌드·접근성 검사를 수행한다. 실제 LH 호출과 실기 접근성 검사는 별도로 실행 여부를 기록한다.

상세한 설치 명령과 pull 후 검사 절차는 [다른 PC 설정 가이드](NEW_PC_SETUP.md)를 따른다.
