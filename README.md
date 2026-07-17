# VAS 2.6.2

VAS는 새 프로젝트를 만들고, 기존 프로그램을 코딩 AI가 이해할 안전한 전달팩으로 바꾸는 로컬 작업 허브입니다.

처음 받은 사용자는 [`00-처음-사용하기.txt`](00-처음-사용하기.txt)부터 읽으면 됩니다.

## 바로 시작

1. `Run-VAS-System.bat`를 더블클릭합니다.
2. **새 프로젝트 만들기** 또는 **기존 프로그램 AI로 연결**을 누릅니다.
3. 기존 프로그램은 폴더 선택 → 안전 분석 → 내용 확인 → AI 전달팩 저장 순서로 진행합니다.
4. Codex·Claude·Antigravity 등에서 원본 폴더를 열고 JSON을 첨부한 뒤 복사된 프롬프트를 붙여넣습니다.

Windows 실행본은 숨겨진 로컬 서버를 자동으로 켜고 브라우저를 엽니다. 사용하지 않으면 서버는 자동 종료되며 BAT를 다시 실행하면 이어서 열립니다. 파일을 직접 열어도 신청서·디자인·검색 기능은 동작하지만, 폴더 가져오기와 Windows 로컬 메모리는 실행본에서만 사용할 수 있습니다.

Windows판의 정밀 분석·검토 소스 ZIP·복사 등록에는 Python 3.10 이상이 필요합니다. 웹판은 파일 내용 없는 분석 JSON을 만들 수 있습니다.

## 기존 프로그램 AI로 연결

기본 흐름은 원본을 실행하거나 복사하지 않습니다. Git 내부, 의존성, 캐시, 링크, 비밀값 후보를 제외한 뒤 `VAS-AI-HANDOFF.json`과 붙여넣을 문장을 만듭니다.

- **분석 JSON**: 파일 내용 없이 구조·기술·작업 요청만 전달합니다.
- **검토 소스 ZIP**: 사용자가 직접 고른 안전한 텍스트 발췌만 추가합니다.
- 등록 프로젝트의 활성 RAG는 미리보기 항목만 포함하며 개인화 메모리는 항상 제외합니다.
- VAS 안으로 복사할 때만 화면 아래 **고급 기능**을 열어 백업·복제·해시 검증·등록을 진행합니다.

자세한 방법: [docs/import-existing-project.md](docs/import-existing-project.md)

## 개인화와 RAG

동의한 사용자에게만 현재 프로젝트의 검색·탐색 흐름을 로컬에 저장합니다. 새 프로젝트는 민감 항목을 뺀 요구사항만 RAG에 연결하며, 가져온 프로그램은 가져오기 화면에서 RAG 색인을 선택한 경우에만 허용된 텍스트를 연결합니다. 기록은 외부로 자동 전송하지 않으며 **내 사용 기록**에서 일시정지·삭제·내보내기 할 수 있습니다.

프로젝트 목록의 **AI 전달팩**은 코딩 AI용 JSON을 만들고, **보관 ZIP**은 요구사항·디자인 토큰·RAG 메타데이터·무결성 해시만 보관합니다. 둘 다 환경 변수, 절대 경로, 개인화 기록을 제외합니다.

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
