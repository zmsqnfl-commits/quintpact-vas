# VAS 2.6.0 개발 규칙

- HTML/CSS/Vanilla JS, Python, PowerShell만으로 경량 운영합니다.
- 파일당 500줄 이하, 외부 CDN·원격 폰트 금지입니다.
- 코어 원본은 `src/`, `docs/`, `scripts/`, `tests/`입니다.
- 사용자 프로젝트와 메모리는 `workspace/`에만 저장하고 Git·배포에서 제외합니다.
- 저장소 안에 배포 미러 복사본을 만들지 말고 `scripts/build_release.py`로 재현 가능한 배포물을 생성합니다.
- 새 프로젝트와 기존 프로젝트 모두 `workspace/projects/<name>/`에 격리합니다.
- 기존 프로젝트는 읽기 전용 분석 → 승인 → staging 복제 → 해시 검증 → 원자적 승격 순서만 허용합니다.
- 개인화는 동의 기반이며 파일 내용, 비밀값, 절대 경로를 기록하지 않습니다.
- 평소에는 `npm.cmd run test:python`과 `npm.cmd run test:browser`를 사용합니다.
- `npm.cmd run test:release`의 10회 스트레스 검사는 명시적 요청 때만 실행합니다.

시스템 구조는 `docs/index.md`, 가져오기 절차는 `docs/import-existing-project.md`, 운영 절차는 `docs/OPERATIONS.md`를 기준으로 합니다.
