# 운영 가이드

## 실행

- 일반 사용자: `Run-VAS-System.bat` 더블클릭
- 수동 실행: `powershell -ExecutionPolicy Bypass -File scripts/Start-VAS.ps1`
- 사용하지 않으면 로컬 서버는 기본 30분 뒤 종료됩니다.

Windows 정밀 폴더 분석에는 Python 3.10 이상을 사용합니다. 웹판은 파일 내용 없이 이름·크기·구조만 분석합니다.

## 저장과 복구

- 코어 체크포인트: `.vas_backups/checkpoint_*.zip` 최신 10개
- Windows 작업 기억: `%LOCALAPPDATA%\QUINTPACT\VAS\`
- 브라우저 작업 기억: IndexedDB
- 기존 프로젝트·가져오기 자료: `workspace/`에 그대로 보존

## 개인정보

- 기본값은 작업 기억 사용 안 함입니다.
- 동의 전 이벤트를 기록하지 않습니다.
- 설정에서 사용·중지·삭제·전체 초기화를 언제든 실행할 수 있습니다.
- 비밀값, 파일 내용, 절대 경로, 파일명은 작업 기억에 저장하지 않습니다.
- 최종 JSON에는 연락처와 작업 기억 원본을 넣지 않습니다.
- 신청서 초안은 복구용으로만 브라우저에 저장하며 JSON 저장 뒤 삭제합니다.

## 검증

```powershell
npm.cmd run knowledge:check
npm.cmd run test:python
npm.cmd run test:browser
npm.cmd run test:package
```

`npm.cmd run test:release`의 10회 반복은 명시적 요청 때만 실행합니다.

## 배포

`npm.cmd run release:build` 후 `dist/SHA256SUMS.txt`와 ZIP의 `manifest.json`을 확인합니다. `.git`, `workspace`, 백업, 캐시, 환경 변수, 작업 기억은 배포에서 제외합니다.
