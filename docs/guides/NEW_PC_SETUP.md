# 다른 PC에서 설치·실행·테스트하기

작성일: 2026-09-18. 대상: Windows 10/11, PowerShell. 저장소: https://github.com/KimJaeseon/housing-app

처음 받는 PC는 **clone → 도구·의존성 설치 → 키 없는 검사 → 필요하면 LH 키 등록·실제 조회** 순서로 진행한다. 이미 받은 PC는 7절의 pull 절차를 따른다. 명령은 블록별로 실행하고 오류가 나면 다음 단계로 넘어가지 않는다.

현재 키 저장은 Windows DPAPI를 사용하고 QA 스크립트는 `.venv/Scripts/python.exe`와 Chrome를 직접 실행한다. macOS/Linux에서 아래 명령을 그대로 실행할 수는 없다. Codex 설치는 필요하지 않다.

## 1. 준비할 프로그램

| 프로그램 | 기준 | 확인 명령 |
|---|---|---|
| Git for Windows | Git 명령 사용 가능 | `git --version` |
| Python | 3.12.x, 현재 개발 PC 3.12.14 | `py -3.12 --version` |
| Node.js | 24.x, 현재 개발 PC 24.19.0 | `node --version` |
| pnpm | 11.19.0 | `pnpm.cmd --version` |
| Google Chrome | 설치된 정식 버전 | 시작 메뉴에서 실행 확인 |

설치 안내: [Git](https://git-scm.com/downloads/win), [Python](https://www.python.org/downloads/windows/), [Node.js](https://nodejs.org/en/download), [Chrome](https://www.google.com/chrome/).

Node.js 설치 후 새 PowerShell에서 pnpm을 설치한다. `.cmd`를 사용하면 PowerShell의 npm.ps1/pnpm.ps1 실행 정책 문제를 피할 수 있다.

```powershell
npm.cmd install --global pnpm@11.19.0
git --version
py -3.12 --version
node --version
pnpm.cmd --version
```

프로젝트의 React Native 패키지가 Node 24에서 요구하는 최소 버전은 24.3.0이다. 현재 개발 PC 버전은 참고용이며, 새 PC에서 설치가 검증됐다는 의미는 아니다. [pnpm 설치 안내](https://pnpm.io/installation)

## 2. 처음 내려받기 — clone

아래는 사용자 홈 아래에 housing-app 폴더를 만드는 예시다. 이미 같은 이름의 폴더가 있으면 다른 위치를 선택한다. 공개 저장소를 내려받는 데 GitHub 로그인은 필요 없다.

```powershell
Set-Location $env:USERPROFILE
git clone https://github.com/KimJaeseon/housing-app.git
Set-Location .\housing-app
git status --short --branch
```

이후 명령의 '프로젝트 루트'는 방금 생성된 housing-app 폴더다. 기존 개발 PC의 C:\data\menual 경로를 만들 필요는 없다.

## 3. 의존성 설치

프로젝트 루트에서 Python 환경을 만든다. 가상환경 활성화 없이 실행 파일을 직접 사용하므로 Activate.ps1 설정은 필요 없다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
.\.venv\Scripts\python.exe -m pip check
```

프론트엔드 의존성을 설치한다.

```powershell
Set-Location .\frontend
pnpm.cmd install --frozen-lockfile
Set-Location ..
```

다른 PC의 .venv, node_modules, dist 폴더를 복사하지 않는다. 저장소의 잠금 파일로 다시 설치한다. 패키지 다운로드에는 인터넷이 필요하다.

## 4. LH 승인키 없이 자동검사

실행 중인 개발 서버가 있다면 해당 터미널에서 Ctrl+C로 종료한다. 웹 QA는 8000·18800 포트를 직접 사용하며 다른 프로세스를 종료하거나 재사용하지 않는다.

프로젝트 루트에서:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -p "test_*.py"
.\.venv\Scripts\python.exe backend/contracts/test_reference_rules.py
```

기대 결과: 두 명령 모두 종료 코드 0, unittest 결과 OK. 실제 LH 승인키는 필요하지 않다.

이어 프론트엔드를 검사한다. API 주소를 localhost로 고정한 뒤 빌드해야 다른 PC의 주소가 결과물에 섞이지 않는다.

```powershell
Set-Location .\frontend
$env:EXPO_PUBLIC_API_URL='http://127.0.0.1:8000'
$env:LH_ENABLE_PROBE='0'
$env:LH_ENABLE_LIST='0'
$env:LH_ENABLE_SUPPLY='0'
pnpm.cmd exec tsc --noEmit
pnpm.cmd exec expo export --platform web
node qa.mjs
Set-Location ..
```

기대 결과: 타입 검사·빌드·QA 모두 종료 코드 0. QA는 합성 응답과 로컬 서버를 사용한다. frontend/qa/results.json에서 violations가 빈 배열이고 passed 항목이 false가 아닌지 확인한다. 검사별 PNG도 같은 폴더에 생성된다. 기존 검증 자료와 달라질 수 있으므로 실행 후 git status로 변경 파일을 확인한다.

QA는 `channel: 'chrome'`를 사용하므로 **Google Chrome 설치가 필요**하다. Playwright의 Chromium만 설치하는 것으로 대체되지 않는다. [Playwright 브라우저 안내](https://playwright.dev/docs/browsers)

## 5. 브라우저에서 수동 테스트

서로 다른 PowerShell 창 두 개를 연다. 아래 경로는 2절의 clone 위치 기준이다.

창 1 — 키 없이 서버 실행:

```powershell
Set-Location "$env:USERPROFILE\housing-app"
$env:LH_ENABLE_PROBE='0'
$env:LH_ENABLE_LIST='0'
$env:LH_ENABLE_SUPPLY='0'
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

창 2 — 화면 실행:

```powershell
Set-Location "$env:USERPROFILE\housing-app\frontend"
$env:EXPO_PUBLIC_API_URL='http://127.0.0.1:8000'
pnpm.cmd web
```

브라우저에서 http://localhost:8081 을 연다. Expo가 다른 포트를 선택했다면 터미널에 표시된 주소를 사용한다.

- http://127.0.0.1:8000/health 에서 status가 ok이고 live_collection이 false인지 확인한다.
- 앱의 '가상 화면 미리보기로 전환'에서 목록·상세·오류·빈 결과를 확인한다.
- 이 실행 방식에서 실제 검색은 서비스 미준비 안내가 정상이다. 실제 공고가 없다는 뜻은 아니다.
- 종료는 각 창에서 Ctrl+C. 자동검사를 다시 실행하기 전에 서버를 종료한다.

## 6. 실제 LH 조회 — 승인키 필요

새 PC의 프로젝트 루트에서 해당 PC의 Windows 사용자 계정으로 키를 다시 등록한다.

```powershell
.\.venv\Scripts\python.exe -m backend.key_store save
.\.venv\Scripts\python.exe -m backend.key_store status
```

숨김 입력란에 발급받은 일반 인증키를 입력한다. ready는 로컬 저장·복호화 가능 상태이며 외부 API 활용승인을 보장하지 않는다. `.secrets/lh-service-key.dpapi`는 PC·계정에 종속되므로 이전 PC에서 복사하지 않는다. 키를 명령행 인자, GitHub, EXPO_PUBLIC_ 변수에 넣지 않는다. 목록 API와 공급정보 API의 활용승인을 각각 확인한다. 자세한 내용은 [키 관리](../backend/KEY_MANAGEMENT.md)를 따른다.

창 1의 기존 서버를 종료한 뒤 프로젝트 루트에서 실행한다. 이전에 설정한 LH_SERVICE_KEY 환경변수가 있으면 저장 파일보다 우선하므로 아래 명령으로 현재 창에서 해제한다.

```powershell
Remove-Item Env:LH_SERVICE_KEY -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m backend.serve_lh --start 2026.08.01 --end 2026.09.16
```

창 2는 5절의 pnpm.cmd web을 그대로 사용한다. health의 live_collection이 true인지 확인한 뒤 서울 검색 → 확인 필요 또는 마감·취소 탭 → 상세 → 공급정보 조회를 확인한다.

날짜는 **게시일 조회 범위**다. 위 날짜는 기존 검증 표본을 재현하기 위한 예시이며 현재 모집 중 공고 전체를 보장하지 않는다. 최근 범위는 서버를 종료하고 날짜를 YYYY.MM.DD 형식으로 바꿔 재실행한다. 원문·신청 자격 검증이 끝난 공고와 목록 조회 성공은 구분한다.

선택: 실제 목록 연동 자동검사. 개발 서버를 종료하고 4절의 웹 빌드를 마친 뒤 실행한다.

```powershell
Set-Location .\frontend
$env:EXPO_PUBLIC_API_URL='http://127.0.0.1:8000'
Remove-Item Env:LH_SERVICE_KEY -ErrorAction SilentlyContinue
node qa-live-list.mjs
Set-Location ..
```

이 스크립트는 저장된 키로 실제 LH 검색을 수행하며 내부 날짜가 2026.08.01~2026.09.16으로 고정돼 있다. 마감·취소 2건과 특정 정정공고를 기대하므로 원천 데이터가 변하면 실패할 수 있다. 실패 시 API 승인·응답과 기대값을 함께 검토한다. 결과는 frontend/qa/live-results.json이다. 이 검사는 공급정보 전체와 모바일 실기 검사를 대체하지 않는다.

## 7. 이후 최신 소스 받기 — pull

개발 서버를 종료하고 프로젝트 루트에서 먼저 변경 상태를 확인한다.

```powershell
git status --short --branch
```

변경 사항이 있으면 필요한 코드·검증 자료를 먼저 검토해서 커밋하거나 따로 보관한다. 테스트가 갱신한 파일도 확인한다. 변경이 남은 상태에서 강제 초기화하거나 덮어쓰지 않는다. 로컬 변경을 정리한 뒤:

```powershell
git switch main
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
.\.venv\Scripts\python.exe -m pip check
Set-Location .\frontend
pnpm.cmd install --frozen-lockfile
Set-Location ..
```

그다음 4절 검사와 웹 빌드를 다시 진행한다. --ff-only가 실패하면 로컬·원격 이력이 갈라진 것이므로 자동 강제 병합하지 말고 변경 내역을 확인한다. 키는 pull할 때마다 다시 등록할 필요가 없다.

## 8. 자주 막히는 부분

| 증상 | 확인·해결 |
|---|---|
| git/node/pnpm 명령을 찾지 못함 | 설치 후 PowerShell을 새로 열고 PATH 및 버전 확인 |
| py -3.12 실패 | Python 3.12와 실행 런처 설치 확인. python --version이 3.12라면 python -m venv .venv 사용 가능 |
| pnpm.ps1 실행이 차단됨 | pnpm 대신 pnpm.cmd, npm 대신 npm.cmd 사용 |
| frozen-lockfile 오류 | pnpm 11.19.0과 최신 소스 확인. 잠금 파일을 임의 삭제하지 말고 package.json과 일치 여부 확인 |
| 패키지 버전을 찾을 수 없음 | 사내 미러·네트워크·레지스트리 설정과 잠금 버전 확인. 임의 최신 버전 교체는 별도 변경으로 검토 |
| Chrome executable 없음 | Chrome 정식 버전을 설치하고 재실행 |
| Port 8000/18800 is in use | 해당 개발 서버 창에서 Ctrl+C 후 재시도 |
| QA에서 빈 화면/404 | frontend에서 웹 빌드 성공 및 dist/index.html 생성 확인 |
| 앱에서 서버 연결 실패 | /health 확인, EXPO_PUBLIC_API_URL 확인 후 Expo 재시작·웹 재빌드 |
| 로컬 키를 읽을 수 없음 | 새 PC·현재 Windows 계정에서 key_store save 재실행 |
| API_KEY_NOT_REGISTERED / 403 | 해당 API 활용승인·키·승인 반영 상태 확인 |
| 확인된 공고가 0건 | 원문 검증 미완료 상태와 조회 범위 확인. 전체 공고 없음으로 해석하지 않음 |

휴대폰 실기 연결과 VoiceOver/TalkBack 검수는 [직접 테스트 안내](RUN_AND_TEST.md)의 4절을 참고한다. 웹 검사 통과를 네이티브 앱 통과로 기록하지 않는다.

## 9. 문서 검증 범위

명령·경로·포트·환경변수·브라우저 조건은 현재 저장소 코드와 대조했다. 런타임 버전은 기존 개발 PC에서 확인했다. 이 문서 작성만으로 별도의 새 PC에서 의존성 설치 및 전체 검사를 완료한 것은 아니다. 테스트 결과를 공유할 때 OS, Python/Node/pnpm 버전, 커밋 ID(git rev-parse --short HEAD), 실패한 명령과 키를 제거한 오류 메시지를 함께 남긴다.


작성 시 기존 개발 PC에서 실행한 검사 결과는 [Chrome 검증 기록](../validation/2026-09-18_NEW_PC_CHROME.md)을 참고한다.
