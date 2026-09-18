# LH 승인키 영구 저장 및 사용

2026-09-16. Windows 로컬 개발용.

## 최초 등록 / 키 교체

프로젝트 폴더에서 아래 명령을 실행한다. 키를 명령 뒤에 붙이지 않는다.

```powershell
cd C:\data\menual\housing-app-guidelines
.\.venv\Scripts\python.exe -m backend.key_store save
```

숨김 입력란에 승인키를 입력하고 Enter를 누른다. 입력 중 문자가 보이지 않는 것은 정상이다. 프로젝트의 save-lh-key.cmd를 탐색기에서 실행해도 동일하다. 동일 명령으로 새 키를 등록하면 암호화 파일을 교체한다. 잘못된 형식은 기존 파일을 덮어쓰지 않는다.

저장 파일: `.secrets/lh-service-key.dpapi`. 평문 .env 파일을 만들지 않는다. Windows DPAPI의 현재 사용자 범위로 암호화하며, 보통 같은 PC와 Windows 계정에서 사용한다. 파일을 다른 PC로 복사하는 방식으로 이전하지 말고 새 환경에서 키를 다시 등록한다. 같은 사용자 권한의 프로그램과 관리자에 대한 완전한 비밀 격리를 보장하는 방식은 아니다.

## 저장 상태 확인

```powershell
.\.venv\Scripts\python.exe -m backend.key_store status
```

키 내용 없이 ready / not configured만 표시한다. ready는 로컬 복호화 가능 상태이며 API 승인 유효성 검증 결과가 아니다. 파일이 손상됐거나 계정이 다르면 실패로 처리하며 외부 요청하지 않는다.

## 실제 연결 확인

```powershell
.\.venv\Scripts\python.exe -m backend.lh_probe --start 2026.08.01 --end 2026.09.16 --region 11 --type 06
```

키 파일을 자동으로 읽는다. 날짜는 게시일 조회 시작/종료다. 실제 목록 수집에서는 응답에 반영된 기간까지 확인한다. 1페이지 최대 3행, 자동 재시도 없음. 출력은 상태 코드와 건수 요약이며 키·요청 URL·원응답은 출력하지 않는다. 성공 신호는 공고 검증 완료가 아니다.

앱 연동 서버:

```powershell
.\.venv\Scripts\python.exe -m backend.serve_lh --start 2026.08.01 --end 2026.09.16
```

서버 역시 파일을 자동으로 읽으며 새 평문 환경변수를 만들지 않는다. serve_lh는 현재 실제 목록 수집 모드를 활성화한다. 개발자가 별도로 설정한 LH_SERVICE_KEY 환경변수가 있다면 해당 값이 우선한다. 일반 backend.app 기동은 기존처럼 연결 검사 비활성 상태를 유지한다. serve_lh 실행 후 검색 요청 때만 연결 검사가 발생한다.

## 보관 및 삭제

- .secrets/와 *.dpapi는 프로젝트 .gitignore에 제외했다. 수동 압축·백업 시에도 .secrets 폴더를 제외한다.
- frontend에는 키를 전달하지 않는다. EXPO_PUBLIC_ 환경변수에 키를 넣지 않는다.
- 키는 런타임 메모리와 공식 HTTPS API 인증 요청에서 사용된다. 메모리에 평문이 전혀 생기지 않는다는 의미는 아니다.
- 저장을 해제하려면 서버 종료 후 해당 dpapi 파일만 삭제한다. 별도 LH_SERVICE_KEY 환경변수가 있으면 그것도 해제한다. 키 폐기는 발급 포털에서 진행한다.
- 향후 공개 배포는 이 로컬 파일을 업로드하지 않고 배포 환경의 비밀 저장소를 별도로 설정한다.

설계 근거: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata

## 검증

2026-09-16 서버 자동검사 52개 통과. 합성 키로 실제 Windows DPAPI 왕복·교체·변조 거부, 평문 미보관, 환경변수 우선순위, 저장 오류 시 외부 요청 차단, CLI 비노출을 검사했다. 실제 키 등록 및 LH 호출은 별도 단계다.
