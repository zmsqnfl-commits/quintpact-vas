# Clean Copy Package Plan

이 문서는 VAS 전체 폴더를 다른 사람에게 폴더째 전달하기 전, 깨끗한 복사본을 만들기 위한 포함/제외 기준입니다.
TASK-035에서는 이 기준으로 별도 clean copy rehearsal을 수행했습니다.

## 기준 경로

```text
Z:\E.Samchon\promake\VAS\VAS 2.5.2
```

## 목적

- 루트 실행 진입점이 유지된 VAS 전체 작업 도구를 전달한다.
- 개발 캐시, 백업, Git 내부 데이터, 민감 후보 파일은 제외한다.
- 사용자는 복사본에서 `Run-VAS-System.bat`를 더블클릭해 내부 허브를 연다.
- 외부 신청서 공유만 필요하면 전체 VAS가 아니라 `final/nas-client-form/`만 별도 사용한다.

## 포함 후보

```text
Run-VAS-System.bat
README.md
AGENTS.md
CLAUDE.md
GEMINI.md
.cursorrules
.windsurfrules
.gitignore
.agents/
docs/
final/
scripts/
src/
tests/
```

## 포함 이유

- `Run-VAS-System.bat`: 기본 실행 진입점.
- `README.md`: 최초 사용자 안내.
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.cursorrules`, `.windsurfrules`: AI 도구별 규칙 진입점.
- `.agents/`: 에이전트 공통 컨텍스트와 로컬 스킬 기준.
- `docs/`: 운영, 인계, 사용 흐름, 패키징 기준 문서.
- `final/`: 검증된 산출물 기준 폴더.
- `scripts/`: 백업/검증 보조 스크립트.
- `src/`: 내부 허브와 작업 화면 원본.
- `tests/`: 전달 전/후 경량 검증 기준.

## 제외 후보

```text
.git/
.pytest_cache/
.temp data/
.vas_backups/
node_modules/
data/
logs/
backups/
secrets/
credentials/
.env
.env.*
*.key
*.pem
*.token
*.log
```

## 제외 이유

- `.git/`: 전달용 실행 패키지에는 Git 히스토리와 내부 상태가 필요하지 않다.
- `.pytest_cache/`: 테스트 캐시다.
- `.temp data/`: 임시 작업 영역이며 내용 확인 없이 제외한다.
- `.vas_backups/`: 로컬 백업 ZIP 영역이며 복사본을 불필요하게 무겁게 만든다.
- `node_modules/`: 현재 루트에는 없지만 있으면 재생성 가능한 의존성 폴더다.
- `data/`, `logs/`, `backups/`, `secrets/`, `credentials/`: 런타임/민감 후보이므로 제외한다.
- `.env`, 키, 토큰, 로그 파일: 값 확인 없이 제외한다.

## 권장 절차

1. 현재 작업 폴더를 직접 정리하지 않는다.
2. 별도 위치에 빈 clean copy 대상 폴더를 준비한다.
3. 포함 후보만 복사한다.
4. 제외 후보가 clean copy 안에 들어가지 않았는지 파일명/폴더명 수준으로 확인한다.
5. `Run-VAS-System.bat`가 clean copy 루트에 있는지 확인한다.
6. `src/vas-hub.html`, `src/design-controller.html`, `src/client-application.html`이 있는지 확인한다.
7. `final/nas-client-form/index.html`이 있는지 확인한다.
8. 전달 전 경량 테스트와 허브 smoke를 실행한다.

## 전달 전 검증 명령

```powershell
python tests\test_html_syntax.py
python tests\test_client_form.py
cd tests
npm run test:browser
```

`node_modules/`를 제외한 clean copy에서는 `npm run test:browser`가 바로 실행되지 않습니다.
TASK-035 rehearsal에서는 새 설치나 의존성 복사 없이 원본 `tests/node_modules`를 `NODE_PATH`로 지정해 clean copy 대상 browser smoke만 재확인했습니다.

## 브라우저 확인

- `Run-VAS-System.bat`는 clean copy 루트에서 실행한다.
- 직접 확인이 필요하면 브라우저에서 `src/vas-hub.html`을 연다.
- 허브에서 `design-controller.html`, `client-application.html` 링크가 열리는지 확인한다.

## 주의 사항

- 이 계획은 전체 VAS 작업 도구 전달용이다.
- 외부 신청자에게 공유할 것은 전체 VAS가 아니라 `final/nas-client-form/` 패키지다.
- 대상 PC의 보안 정책이나 기본 브라우저 연결 상태는 별도 확인이 필요하다.
- 오프라인/폐쇄망에서는 외부 CDN 폰트나 아이콘 표시가 달라질 수 있다.
- `final/` 폴더만 단독 실행 패키지로 쓰려면 별도 점검이 필요하다.

## TASK-035 rehearsal 결과

- clean copy 위치: `Z:\E.Samchon\promake\VAS\VAS-2.5.2-clean-copy-rehearsal-TASK-035-20260603`
- 포함 후보 복사 완료.
- 제외 후보 이름 기준 재검사 완료.
- clean copy 내부에 들어온 제외 후보와 테스트 생성 캐시는 제거 완료.
- Python smoke와 browser smoke 통과.
- 실제 압축 안 함.
- 실제 USB/NAS/외부 배포 안 함.
- 민감 파일 내용 열람 안 함.
