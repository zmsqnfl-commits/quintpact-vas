# VAS 2.6.1

VAS는 새 프로젝트를 만들거나 기존 프로그램을 안전하게 가져와 계속 개발하는 로컬 작업 허브입니다.

처음 받은 사용자는 [`00-처음-사용하기.txt`](00-처음-사용하기.txt)부터 읽으면 됩니다.

## 바로 시작

1. `Run-VAS-System.bat`를 더블클릭합니다.
2. **새 프로젝트 만들기** 또는 **기존 프로그램 가져오기**를 누릅니다.
3. 화면 안내대로 디자인과 프로젝트 RAG까지 이어갑니다.
4. 다음 실행부터는 **내 프로젝트 → 계속 작업**을 누릅니다.

Windows 실행본은 숨겨진 로컬 서버를 자동으로 켜고 브라우저를 엽니다. 사용하지 않으면 서버는 자동 종료되며 BAT를 다시 실행하면 이어서 열립니다. 파일을 직접 열어도 신청서·디자인·검색 기능은 동작하지만, 폴더 가져오기와 Windows 로컬 메모리는 실행본에서만 사용할 수 있습니다.

기존 프로젝트 가져오기에는 Python 3.10 이상이 필요합니다. 준비되지 않은 경우 가져오기 화면에서 바로 안내하며, 나머지 기능은 계속 사용할 수 있습니다.

## 기존 프로젝트 가져오기

가져오기는 원본을 실행하지 않습니다. 숨김 파일, Git 저장소, 의존성, 대용량 파일, 의심 파일을 먼저 분석하고 보고서를 보여줍니다. 승인하면 체크포인트와 해시를 만든 뒤 `workspace/projects/<프로젝트명>/`으로 복제합니다.

- 원본 폴더는 기본적으로 그대로 남습니다.
- Git 이력은 가능한 경우 보존하며 복구용 bundle도 만듭니다.
- 실패하면 중간 복사본을 제거하고 이전 상태로 되돌립니다.
- 원본 삭제는 고급 메뉴의 별도 확인 없이는 실행되지 않습니다.

자세한 방법: [docs/import-existing-project.md](docs/import-existing-project.md)

## 개인화와 RAG

동의한 사용자에게만 현재 프로젝트의 검색·탐색 흐름을 로컬에 저장합니다. 새 프로젝트는 민감 항목을 뺀 요구사항만 RAG에 연결하며, 가져온 프로그램은 가져오기 화면에서 RAG 색인을 선택한 경우에만 허용된 텍스트를 연결합니다. 기록은 외부로 자동 전송하지 않으며 **내 사용 기록**에서 일시정지·삭제·내보내기 할 수 있습니다.

프로젝트 목록의 **안전 ZIP**은 요구사항·디자인 토큰·RAG 메타데이터·무결성 해시만 담습니다. 원본 소스, 환경 변수, 절대 경로, 개인화 기록은 제외합니다.

## 개발 및 검증

```powershell
npm.cmd ci
python -m pip install -r tests/requirements-dev.txt
npm.cmd run knowledge:index
npm.cmd run test:python
npm.cmd run test:browser
npm.cmd run test:package
```

10회 스트레스 검사는 명시적인 릴리즈 검증 때만 `npm.cmd run test:release`로 실행합니다.

## 배포

```powershell
npm.cmd run release:build
```

`dist/`에 Windows 전체 실행본, 독립 신청서, GitHub Pages 정적 파일, SHA-256 목록이 생성됩니다. `src/`, `docs/`, `scripts/`, `tests/`가 유일한 작업 원본이며 생성물은 Git에 넣지 않습니다.

운영 구조: [docs/index.md](docs/index.md) · 운영: [docs/OPERATIONS.md](docs/OPERATIONS.md) · 인계: [docs/HANDOFF.md](docs/HANDOFF.md)
