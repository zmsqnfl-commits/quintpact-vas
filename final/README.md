# VAS 2.5.2

VAS 2.5.2, the Vibecoding Agent System, is a local-first static HTML toolkit for setting up an AI agent team, editing design-system presets, and sharing a lightweight client intake form without a server.

- Original author: `QUINTPACT Team`
- Korean author name: `퀀트펙트 팀`
- License: MIT License
- Copyright holder: `QUINTPACT Team`

## Features

- Local static HTML workflow that runs from files.
- Public release hub exposing the VAS Design Studio entry point.
- Design Studio for editing theme tokens and prompt presets.
- Client Form and NAS Client Form packages for JSON-based intake.
- Agent rules, taste-skill references, docs, scripts, and tests kept with the public package.
- Clean-copy oriented release layout that excludes caches, backups, runtime dependencies, and sensitive-file candidates.

## Quick Start

Use Windows Explorer:

```text
Run-VAS-System.bat
```

Or open the hub directly:

```text
src/vas-hub.html
```

For the NAS client form package:

```text
final/nas-client-form/index.html
```

For smoke checks:

```powershell
python tests\test_html_syntax.py
python tests\test_client_form.py
cd tests
npm run test:browser
```

`node_modules/` is intentionally not bundled in this public package. Browser tests require dependencies to be installed locally or referenced from a prepared test environment.

## Folder Structure

```text
.
├── Run-VAS-System.bat
├── README.md
├── LICENSE
├── AUTHORS.md
├── NOTICE.md
├── USE_POLICY.md
├── RELEASE_MANIFEST.md
├── .agents/
├── docs/
├── final/
├── scripts/
├── src/
└── tests/
```

Key paths:

- `src/vas-hub.html`: public release hub.
- `src/design-controller.html`: VAS Design Studio.
- `src/client-application.html`: retained Client Form.
- `final/nas-client-form/`: standalone NAS Client Form package.
- `docs/`: operational docs and release notes.
- `tests/`: Python and Playwright smoke tests.

## Attribution

Use `QUINTPACT Team` as the primary public-release author name. Use `퀀트펙트 팀` only where Korean attribution is needed. Do not use colloquial abbreviations as official document attribution.

See:

- `AUTHORS.md` for author naming.
- `NOTICE.md` for third-party notices.
- `USE_POLICY.md` for release-process boundaries.

## License

VAS 2.5.2 is released under the MIT License.

```text
Copyright (c) 2026 QUINTPACT Team
```

See `LICENSE` for the full license text.

## Client Form Note

The Client Form and NAS Client Form are static JSON intake forms. They do not upload data to a server automatically. Users save the generated JSON locally and handle delivery through their own approved process.

## Release Boundary

This package has been published to the public GitHub repository. NAS upload, external distribution package creation, and archive creation still require separate project-owner approval.

---

# VAS 2.5.2 한국어 안내

VAS 2.5.2는 AI 에이전트 팀 구성, 디자인 시스템 프리셋 편집, 서버 없는 클라이언트 신청서 공유를 위한 로컬 우선 정적 HTML 도구입니다.

- 공식 영문 원저작 표기: `QUINTPACT Team`
- 공식 한국어 원저작 표기: `퀀트펙트 팀`
- 라이선스: MIT License
- Copyright holder: `QUINTPACT Team`

## 주요 기능

- 파일에서 바로 실행되는 로컬 정적 HTML 워크플로우.
- public release 허브에서 VAS Design Studio 진입점 노출.
- 테마 토큰과 프롬프트 프리셋을 편집하는 Design Studio.
- JSON 기반 접수를 위한 Client Form 및 NAS Client Form 패키지.
- agent rules, taste-skill 참고자료, docs, scripts, tests 유지.
- 캐시, 백업, 런타임 의존성, 민감 후보 파일을 제외하는 clean-copy 기준 구조.

## 빠른 실행

Windows Explorer에서 실행:

```text
Run-VAS-System.bat
```

또는 허브 직접 열기:

```text
src/vas-hub.html
```

NAS Client Form 패키지:

```text
final/nas-client-form/index.html
```

스모크 테스트:

```powershell
python tests\test_html_syntax.py
python tests\test_client_form.py
cd tests
npm run test:browser
```

이 public package에는 `node_modules/`가 포함되지 않습니다. 브라우저 테스트는 로컬 의존성 설치 또는 준비된 테스트 환경 참조가 필요합니다.

## 폴더 구조

```text
.
├── Run-VAS-System.bat
├── README.md
├── LICENSE
├── AUTHORS.md
├── NOTICE.md
├── USE_POLICY.md
├── RELEASE_MANIFEST.md
├── .agents/
├── docs/
├── final/
├── scripts/
├── src/
└── tests/
```

주요 경로:

- `src/vas-hub.html`: public release 허브.
- `src/design-controller.html`: VAS Design Studio.
- `src/client-application.html`: 유지되는 Client Form.
- `final/nas-client-form/`: 독립 실행 NAS Client Form 패키지.
- `docs/`: 운영 문서와 릴리즈 로그.
- `tests/`: Python 및 Playwright smoke 테스트.

## 원저작 표기

공식 공개 문서에는 `QUINTPACT Team`을 우선 사용합니다. 한국어 표기가 필요할 때만 `퀀트펙트 팀`을 사용합니다. 구어체 약칭은 공식 문서 표기로 사용하지 않습니다.

참조:

- `AUTHORS.md`: 원저작 표기 기준.
- `NOTICE.md`: 외부 고지.
- `USE_POLICY.md`: release 진행 승인 경계.

## 라이선스

VAS 2.5.2는 MIT License로 배포됩니다.

```text
Copyright (c) 2026 QUINTPACT Team
```

전체 라이선스 문구는 `LICENSE`를 확인하세요.

## Client Form 안내

Client Form과 NAS Client Form은 정적 JSON 신청서입니다. 서버로 데이터를 자동 업로드하지 않습니다. 사용자는 생성된 JSON을 로컬에 저장하고, 승인된 절차로 별도 전달해야 합니다.

## Release 경계

이 패키지는 public GitHub 저장소에 업로드된 상태입니다. NAS 업로드, 외부 배포 패키지 생성, 압축 파일 생성은 여전히 별도 프로젝트 소유자 승인이 필요합니다.
