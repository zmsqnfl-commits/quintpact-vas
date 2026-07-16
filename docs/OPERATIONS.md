# 운영 가이드

## 실행

- 일반 사용자: `Run-VAS-System.bat` 더블클릭
- 수동 실행: `powershell -ExecutionPolicy Bypass -File scripts/Start-VAS.ps1`
- 종료: 사용하지 않으면 기본 30분 뒤 자동 종료; 즉시 종료는 인증된 `/api/shutdown` 사용

기존 프로젝트 가져오기는 Python 3.10 이상을 사용합니다. Python이 없으면 가져오기 화면에서 즉시 안내하고 해당 기능만 비활성화합니다.

서버는 `127.0.0.1`에만 바인딩하고, 시작할 때 만든 세션 토큰과 동일 출처 요청만 허용합니다. 토큰을 URL에서 받은 뒤 세션 저장소로 옮기고 주소에서는 제거합니다.

## 저장과 복구

- 프로젝트: `workspace/projects/`
- 가져오기 작업·프로젝트 등록·프로젝트 RAG: `workspace/.vas/`
- 코어 체크포인트: `.vas_backups/checkpoint_*.zip` 최신 10개
- 가져오기 복구본: `.vas_backups/migrations/` (사용자가 정리하기 전까지 보존)
- Windows 개인화 메모리·런타임 세션: `%LOCALAPPDATA%\QUINTPACT\VAS\`
- 브라우저 전용 개인화 메모리: IndexedDB

가져오기 전 체크포인트와 파일 해시를 생성합니다. 실패한 작업은 staging을 제거하며 완료 작업은 작업 ID로 되돌릴 수 있습니다.

## 개인정보

- 기본값은 수집 안 함입니다.
- 동의 전 이벤트를 기록하지 않습니다.
- 비밀값, 파일 내용, 절대 경로, 파일명은 이벤트에 저장하지 않습니다.
- 프로젝트 RAG는 가져오기 때 별도로 선택하며 허용된 텍스트만 로컬 색인합니다.
- 기록은 사용자가 직접 일시정지·삭제·내보내기·가져오기 합니다.
- 자동 만료나 조용한 삭제를 하지 않습니다.
- 신청서 초안은 복구를 위해 브라우저에 자동 저장됨을 화면에 표시하며, 사용자가 끄거나 삭제할 수 있고 JSON 저장·작업공간 생성 뒤에는 지웁니다.

## 검증

```powershell
npm.cmd ci
python -m pip install -r tests/requirements-dev.txt
npm.cmd run knowledge:check
npm.cmd run test:python
npm.cmd run test:browser
npm.cmd run test:package
```

10회 검사는 사용자가 명시적으로 요청한 경우에만 실행합니다.

## 배포

`npm.cmd run release:build` 후 `dist/SHA256SUMS.txt`와 각 ZIP 내부 `manifest.json`을 확인합니다. 배포 ZIP에는 `.git`, `workspace`, 백업, 캐시, 테스트 결과, 환경 변수, 개인화 데이터가 들어가면 안 됩니다.

## 장애 확인 순서

1. `Run-VAS-System.bat`의 오류 문구를 확인합니다.
2. `/health`가 응답하는지 확인합니다.
3. `npm.cmd run test:python`으로 파일·API 계약을 확인합니다.
4. 가져오기 실패는 작업 ID로 rollback하고 원본 해시가 유지됐는지 확인합니다.
