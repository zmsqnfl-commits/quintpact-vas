# 프로젝트 연대기 및 교훈 (Log & Lessons)

이 문서는 에이전트 시스템이 스스로 유지보수하는 **작업 이력 및 교훈 기록장**입니다.
작업(`/dev-cycle` 또는 `/migration-cycle`)이 완료되어 `final/` 폴더로 코드가 병합될 때마다, Security 에이전트가 가장 최상단에 새로운 내역과 교훈을 덧붙입니다.

## 2026-06-04 TASK-041 업로드 전 통합 검증
- **분류:** `[릴리즈 검증]`
- **수행 내용:** README/license/manifest 정합성, Hub/Design Studio/Client/NAS smoke, Python/browser/integrity 검증.
- **검증:** html 5 PASS, client 18 passed, integrity 166/166 PASS, browser 5 passed, direct smoke PASS.
- **특이사항:** `final/Run-VAS-System.bat`를 루트 BAT와 동기화했으며 업로드/압축/NAS 업로드는 수행하지 않음.

## 2026-06-03 TASK-040 GitHub 메인 README 정리

- **분류:** `[릴리즈 준비/문서]`
- **수행 내용:**
  1. public release 후보의 루트 README를 GitHub 메인 페이지용 영어 우선 구조로 정리.
  2. 바로 아래에 한국어 안내 섹션을 병기.
  3. features, quick start, folder structure, attribution, license, client form note를 포함.
  4. MIT License, AUTHORS, NOTICE, USE_POLICY, RELEASE_MANIFEST와 충돌하지 않게 보정.
  5. 동일 내용을 `final/README.md`에 동기화.
- **교훈/특이사항:**
  - 공개 저장소 첫 화면은 내부 운영 절차보다 실행, 구조, 라이선스, 고지 위치를 먼저 보여줘야 함.

## 2026-06-03 TASK-039 MIT License 적용

- **분류:** `[릴리즈 준비/라이선스]`
- **수행 내용:**
  1. public release 후보 루트와 `final/`에 MIT License 파일을 추가.
  2. Copyright holder를 `QUINTPACT Team`으로 확정.
  3. README, NOTICE, USE_POLICY, RELEASE_MANIFEST의 TASK-038 잔여 라이선스 미정 문구를 정리.
  4. 실제 GitHub public 업로드, NAS 업로드, 외부 배포, 압축 생성은 수행하지 않음.
- **교훈/특이사항:**
  - MIT 조건은 `LICENSE`가 기준이며, `USE_POLICY.md`는 이번 handoff의 업로드 승인 경계만 보조 기록함.

## 2026-06-03 TASK-038 원저작 표기 및 사용 정책 확정

- **분류:** `[릴리즈 준비/정책]`
- **수행 내용:**
  1. public release 후보의 원저작 표기를 `QUINTPACT Team` / `퀀트펙트 팀`으로 확정.
  2. README, AUTHORS, NOTICE, 허브 카드 표기에서 placeholder author를 제거.
  3. 재배포/수정 허용과 원저작 표기 유지 조건을 `USE_POLICY.md`로 문서화.
  4. 포함/제외 기준과 허브 노출 정책을 `RELEASE_MANIFEST.md`로 문서화.
  5. release 후보 smoke와 공식 표기 검사를 재확인.
- **교훈/특이사항:**
  - 공식 문서에는 구어체 약칭을 쓰지 않고, 영문 공식 표기 `QUINTPACT Team`을 우선 사용함.

## 2026-06-03 TASK-037 public release hub 정리

- **분류:** `[릴리즈 준비/고지]`
- **수행 내용:**
  1. TASK-035 clean copy를 기준으로 별도 public release 후보 폴더를 생성.
  2. 배포용 허브에서 보조 템플릿 카드를 제거하고 Design Studio만 노출.
  3. Client Form/NAS Form, agent rules, taste-skills, docs, scripts, tests는 유지.
  4. `AUTHORS.md`, `NOTICE.md`를 추가하고 README에 원저작/고지 확인 위치를 명시.
  5. release 후보 기준 smoke와 허브 노출 검증을 재실행.
- **교훈/특이사항:**
  - 공개 배포 전 허브 노출 정책과 파일 포함 정책은 분리해서 봐야 함. 허브에서 숨긴 파일도 직접 경로/테스트용으로 유지할 수 있음.

## 2026-06-03 TASK-035 clean copy rehearsal

- **분류:** `[전달 준비/검증]`
- **수행 내용:**
  1. 사용자 직접 실행에서 TASK-034 보정 후 다음 단계로 clean copy rehearsal을 진행.
  2. `Z:\E.Samchon\promake\VAS\VAS-2.5.2-clean-copy-rehearsal-TASK-035-20260603` 별도 폴더를 생성하고 포함/제외 기준을 적용.
  3. 제외 후보로 들어온 `.vas_backups`, `.pytest_cache`, `node_modules`, `test-results`를 clean copy 내부에서만 제거.
  4. clean copy 기준 Python smoke와 Playwright browser smoke를 재확인.
- **교훈/특이사항:**
  - clean copy에서 `node_modules`를 제외하면 `npm run test:browser`는 바로 실행되지 않으므로, 전달용 패키지와 테스트 실행용 의존성 안내를 구분해야 함.

## 2026-06-03 TASK-034 Client Form JSON 저장 단계 버튼 피드백 보정

- **분류:** `[버그픽스/사용성]`
- **수행 내용:**
  1. Client Form 마지막 단계에서 필수 라디오 선택이 비어 있을 때 `JSON 저장 단계로 이동` 버튼이 무반응처럼 보이는 원인을 확인.
  2. 숨은 라디오 input에만 포커스가 가던 검증 흐름을 보이는 선택 그룹 하이라이트와 안내 문구로 보정.
  3. Client Form 전체 입력 후 완료 화면으로 이동하는 browser smoke와 필수 선택 누락 피드백 회귀 테스트를 추가.
- **교훈/특이사항:**
  - 커스텀 카드형 라디오는 네이티브 `reportValidity()`만 쓰면 사용자에게 검증 상태가 보이지 않을 수 있으므로, 보이는 그룹 단위 피드백을 함께 제공해야 함.

## 2026-06-03 TASK-032 canonical version 보정

- **분류:** `[버전/정합성]`
- **수행 내용:**
  1. canonical version을 `2.5.2`로 확정하고 package metadata를 `vas-2-5-2` / `2.5.2`로 보정.
  2. client form과 design studio의 `vasThemeTokensVersion` 저장 기준을 `2.5.2`로 보정.
  3. `src/`, `final/src/`, `final/nas-client-form/` 대응 파일을 동기화.
- **교훈/특이사항:**
  - 과거 이력 로그와 마이그레이션/스트레스 테스트의 legacy 라벨은 역사 기록 또는 별도 레거시 검증명으로 유지함.

## 2026-06-01 TASK-031 버전 표기 정리

- **분류:** `[문서/표기 정합성]`
- **수행 내용:**
  1. README와 문서 index의 현재 버전 표기를 `VAS 2.5.2`로 정리.
  2. 디자인 스튜디오 HTML title의 legacy 버전 표기를 `VAS 2.5.2`로 정리.
  3. 동일 변경을 `final/` 문서와 `final/src/`에 동기화.
- **교훈/특이사항:**
  - 히스토리 로그와 내부 localStorage 버전 상수는 기능/이력 의미가 있어 이번 범위에서 변경하지 않음.

## 2026-06-01 TASK-029 README 실행 안내 정리

- **분류:** `[문서/실행 안내]`
- **수행 내용:**
  1. README에 `Run-VAS-System.bat` 기본 실행 흐름과 수동 확인 경로를 짧게 추가.
  2. 외부 신청서 공유는 전체 VAS가 아니라 `final/nas-client-form/` 패키지임을 명확히 구분.
  3. 동일 내용을 `final/README.md`에 동기화.
- **교훈/특이사항:**
  - 전체 도구 실행 안내와 외부 공유 패키지 안내를 README에서 바로 구분해야 복사 배포와 신청서 공유가 섞이지 않음.

## 2026-06-01 TASK-028 Clean Copy Package Plan 작성

- **분류:** `[문서/배포 계획]`
- **수행 내용:**
  1. `docs/clean-copy-package-plan.md`를 추가해 전체 폴더 전달 전 포함/제외 기준을 정리.
  2. 동일 문서를 `final/docs/`에 동기화하고 README/docs index 링크를 추가.
  3. 실제 복사, 삭제, 압축, 배포 없이 문서 계획만 작성.
- **교훈/특이사항:**
  - 전체 VAS 전달은 기존 폴더를 정리하는 방식보다 clean copy 대상 폴더를 따로 만들고 포함 후보만 복사하는 방식이 안전함.

## 2026-06-01 TASK-026 내부 허브 진입점 사용성 정리

- **분류:** `[사용성/실행 안내]`
- **수행 내용:**
  1. `Run-VAS-System.bat`에 허브 파일 누락 안내와 수동 열기 경로 안내를 추가.
  2. `src/vas-hub.html` title의 legacy 표현을 `VAS 2.5.2 — Agent Hub`로 정리.
  3. 동일 title 변경을 `final/src/vas-hub.html`에 동기화.
- **교훈/특이사항:**
  - 로컬 도구는 서버가 없어도 실행 진입점 누락 안내가 있어야 폴더 복사 배포 시 사용자가 막히는 지점을 줄일 수 있음.

## 2026-05-31 TASK-022 NAS Client Form 패키지 분리

- **분류:** `[배포 패키징/외부 공유]`
- **수행 내용:**
  1. `final/nas-client-form/` 폴더를 생성해 외부 공유용 Client Form 파일만 분리.
  2. `index.html`을 진입점으로 두고 필요한 CSS/JS와 README만 포함.
  3. 내부 허브, 디자인 스튜디오, 테스트, handoff 문서는 패키지에서 제외하고 회귀 테스트를 추가.
- **교훈/특이사항:**
  - 외부 NAS 공유는 전체 VAS 배포가 아니라 목적 파일만 담은 작은 패키지로 분리해야 내부 도구 노출과 복사 누락을 줄일 수 있음.

## 2026-05-31 TASK-021 Client Form 외부용 문구 정리

- **분류:** `[UX 문구/외부 공유]`
- **수행 내용:**
  1. Client Form에서 내부 허브 복귀 링크를 제거하고 외부 공유용 안내 문구로 교체.
  2. Submit/완료/첨부파일/일정 placeholder 문구를 실제 JSON 저장 흐름에 맞게 KR/EN 동시 정리.
  3. 실제 전송, 파일 업로드, NAS 연동 기능은 추가하지 않고 회귀 테스트만 보강.
- **교훈/특이사항:**
  - 외부 공유 화면은 내부 작업자용 언어와 실제 동작이 조금만 어긋나도 제출/업로드 오해가 생기므로 문구가 기능만큼 중요함.

## 2026-05-31 TASK-018 디자인 스튜디오 사용 문서화

- **분류:** `[문서/운영 가이드]`
- **수행 내용:**
  1. `docs/design-studio-controls.md`를 추가해 프리셋, Taste Profile, Agent Prompt, Token Export 흐름을 정리.
  2. `README.md`와 `docs/index.md`에 문서 링크를 추가하고 `final/`에 동기화.
  3. 기능/UI 파일은 수정하지 않고 문서 검증만 수행.
- **교훈/특이사항:**
  - 내부 도구는 기능이 늘어난 뒤 짧은 작업자용 문서가 있어야 다음 에이전트가 같은 흐름을 반복 설명하지 않아도 됨.

## 2026-05-31 TASK-017 taste profile 수동 선택 UI

- **분류:** `[기능/프롬프트 제어]`
- **수행 내용:**
  1. 디자인 스튜디오 프롬프트 영역에 Taste Profile 수동 선택 컨트롤 추가.
  2. 기본값은 프리셋 기준 자동으로 유지하고, 수동 선택/자동 복귀 흐름을 `design-profile-control.js`로 분리.
  3. prompt 구조와 preview token 회귀 테스트를 확장해 자동/수동 profile 전환을 검증.
- **교훈/특이사항:**
  - 큰 컨트롤러 파일은 직접 키우지 않고 보조 제어 파일로 분리하면 500줄 규칙과 유지보수성을 함께 지킬 수 있음.

## 2026-05-31 TASK-016 preview token 회귀 테스트 추가

- **분류:** `[테스트/회귀 방지]`
- **수행 내용:**
  1. `tests/design-preview-token.spec.js`를 추가해 preset font/color/radius의 preview CSS 변수 반영을 자동 검증.
  2. `npm run test:design-preview` 명령을 추가하고 `test:browser`에 포함.
  3. Python 경량 테스트와 Playwright 브라우저 스모크 통과 확인.
- **교훈/특이사항:**
  - 콘솔 에러만 확인하면 select/token 불일치를 놓칠 수 있어 DOM CSS 변수까지 직접 검증해야 함.

## 2026-05-31 TASK-015 font option/preset 정합성 수정

- **분류:** `[안정화/토큰 정합성]`
- **수행 내용:**
  1. `fontFamily` select에서 `Inter` option을 제거.
  2. `linear`, `github` 포함 모든 preset font 값이 select option에 존재하도록 옵션 동기화.
  3. `src/`와 `final/src/` 동기화 및 브라우저 스모크 통과 확인.
- **교훈/특이사항:**
  - preset 값이 select option에 없으면 브라우저가 빈 값으로 떨어져 preview token 반영이 누락될 수 있음.

## 2026-05-31 TASK-014 디자인 컨트롤러 브라우저 스모크

- **분류:** `[테스트/검증]`
- **수행 내용:**
  1. `test_html_syntax.py` 5개 항목 PASS 확인.
  2. `src/design-controller.html`에서 프리셋 18개 prompt 섹션/프로필 매핑 확인.
  3. JSON/CSS/Tailwind export, prompt/output 복사, 콘솔 에러 0개 확인.
  4. `linear`, `github` 프리셋의 font 값이 select 옵션과 불일치해 preview font 반영이 비어지는 위험 발견.
- **교훈/특이사항:**
  - 프롬프트 브리지는 단위 문법 테스트만으로 부족하므로 실제 브라우저에서 프리셋 순회, export, preview 변수 반영까지 확인해야 함.

## 2026-05-31 TASK-011 프리셋 문구 정리

- **분류:** `[프롬프트/디자인 기준 정합성]`
- **수행 내용:**
  1. `design-presets.js`의 `Clone` 표현을 `Reference` 기준으로 완화.
  2. 프리셋 prompt/font 값에서 `Inter` 직접 지시를 제거하고 Pretendard/Geist 계열 기준으로 정리.
  3. 과한 보라/파랑 계열 표현과 일부 primary 값을 muted accent 기준으로 보정.
- **교훈/특이사항:**
  - 프리셋은 브랜드 복제가 아니라 시각 문법 참고로 표현해야 VAS baseline과 충돌하지 않음.

## 2026-05-31 TASK-010 디자인 taste 브리지 구현

- **분류:** `[기능/프롬프트 품질 보강]`
- **수행 내용:**
  1. `design-taste-pack.js`를 추가해 taste-skills 핵심 원칙을 경량 프롬프트 브리지로 연결.
  2. `design-controller.html`에 브리지 스크립트를 추가하고, `applyPreset()`에서 `composeAgentPrompt()` fallback 흐름 적용.
  3. `src/`와 `final/src/` 동기화 및 경량 테스트/브라우저 확인 완료.
- **교훈/특이사항:**
  - 대형 스킬 원문을 직접 싣지 않고 요약 profile로 연결하면 VAS의 경량성을 유지하면서 프롬프트 품질을 높일 수 있음.

## 2026-05-31 제작 대상 판별 규칙 추가

- **분류:** `[운영/가드레일]`
- **수행 내용:**
  1. VAS 폴더를 기본 제작 대상이 아닌 제작 도구로 해석하도록 `.agents/CONTEXT.md`, `docs/INSTRUCTIONS.md`, `README.md`에 규칙 추가.
  2. 일반 앱/사이트/도구 제작 요청은 VAS 코어에 섞지 않고 `final/projects/<project-name>/`에 격리하도록 기준 명시.
- **교훈/특이사항:**
  - 공유형 메타 도구 프로젝트는 "도구 자체 수정"과 "도구로 만든 산출물"을 먼저 분리해야 코어가 불필요하게 비대해지지 않음.

## 2026-05-31 경량 공유 원칙 명문화

- **분류:** `[운영 원칙 정리]`
- **수행 내용:**
  1. 여러 사용자가 같은 폴더를 가볍게 실행할 수 있도록 프로젝트 내부에 무거운 플러그인·개인 스킬·외부 저장소 원본을 넣지 않는 규칙을 명문화.
  2. 선택 확장은 사용자 홈 경로(`~/.codex/skills`, `~/plugins`, `~/.agents/plugins`)에 설치하도록 기준 정리.
- **교훈/특이사항:**
  - 공유 폴더는 실행 최소 단위만 담고, 개인화된 능력 확장은 사용자별 환경에 두는 편이 유지보수와 배포에 유리함.

## 2026-05-31 테스트 실행 보완

- **분류:** `[테스트/검증 보완]`
- **수행 내용:**
  1. `npm run test:python` 실행 중 발견된 `final/AGENTS.md` 누락을 동기화로 보완.
  2. Playwright 번들 브라우저가 없는 환경에서도 기존 Chrome으로 `test:browser`를 실행할 수 있도록 `tests/playwright.config.js`를 추가.
- **교훈/특이사항:**
  - Playwright 패키지만 있고 브라우저 바이너리가 없는 환경에서는 시스템 Chrome fallback 설정이 필요함.

## 2026-05-31 구조 보완 및 500줄 규칙 복구

- **분류:** `[유지보수/정합성 보완]`
- **수행 내용:**
  1. `design-controller.html`의 인라인 스크립트를 `design-controller.js`로 분리하여 HTML 파일을 500줄 이하로 복구.
  2. `test_dryrun_10scenarios.py`의 시나리오 데이터를 `dryrun_scenarios.py`로 분리하고, 분리된 프리셋 구조(`design-presets.js`)를 테스트가 인식하도록 수정.
  3. 루트에서 `docs/`로 이동된 문서 경로와 내장 하이브리드 디자인 스튜디오 기준 문서를 최신 구조에 맞게 정리.
  4. `src/`, `docs/`, `scripts/` 변경분을 `final/`에 동기화.
- **교훈/특이사항:**
  - 기능 분리 후에는 테스트의 정적 참조 대상도 함께 갱신해야 False Negative를 막을 수 있음.

## 2026-05-24 프로젝트 구조 및 테스트 정합성 최적화

- **분류:** `[아키텍처/구조 개선]`
- **수행 내용:**
  1. `setup-from-application.md` 워크플로우를 수정하여 향후 생성되는 신규 프로젝트는 모두 `final/[프로젝트명]/` 폴더 내부에 격리하도록 변경.
  2. 시스템의 대문 역할을 하던 기존 `index.html`을 `vas-hub.html`로 이름 변경 후 `src/` 내부로 이동. (새 프로젝트에게 `index.html` 이름을 양보하기 위함)
  3. `Run-VAS-System.bat`이 `src/vas-hub.html`을 실행하도록 변경하고 모든 관련 HTML 링크들을 일괄 업데이트.
  4. 비기술자 사용자 경험을 위해 루트에 있던 개발/테스트용 파일(`HANDOFF.md`, `package.json`, `package-lock.json`, `requirements-dev.txt`, `node_modules/`)을 각각 `docs/`와 `tests/` 내부로 이동시켜 완벽히 숨김.
  5. 130개의 10-Loop 무결성 테스트에서 하드코딩 검사를 동적 검사로 리팩토링 및 100% 통과 재확인.
  6. 최종적으로 모든 변경사항을 `final/` 디렉터리에 1:1 바이트 동기화 완료.
- **교훈/특이사항:**
  - 루트 경로를 오직 `.gitignore`, `README.md`, `Run-VAS-System.bat` 등 필수 뼈대만 남김으로써 시스템의 복잡도를 획기적으로 낮추었음.
  - 테스트 코드는 파일 구조의 변경(동적 생성 버튼 등)에 취약할 수 있으므로, 구조 변경 시 반드시 10-Loop 테스트를 돌려 False Positive(오탐)를 함께 잡아내야 함.

## 2026-05-23 테스트 코드 정합성 보완 (test_html_syntax.py)

- **분류:** `[유지보수 및 버그 픽스]`
- **수행 내용:**
  1. `test_html_syntax.py`의 `open-design-studio.html` 참조를 `design-controller.html`로 업데이트하여 깨진 테스트 스크립트 수정.
  2. 작업공간(VAS 2.5) 전체 폴더/파일 무결성 검증 100% PASS 확인.
- **교훈/특이사항:**
  - 파일명 변경 시 테스트 스크립트도 동기화하여야 함을 재확인.

## 2026-05-23 디자인 스튜디오 및 테마 고도화 (UX/UI 및 데이터 모듈화)

- **분류:** `[기능 고도화 및 버그 픽스]`
- **수행 내용:**
  1. **UX/UI 개선**: 허브 메인 페이지(`vas-hub.html`) 레이아웃 정리, 테마 갤러리 카드 텍스트 단일화.
  2. **기능 고도화**: 스튜디오(`design-controller.html`)의 18+개 프리셋을 3대 카테고리로 분리 렌더링.
  3. **코드 최적화**: 500줄이 넘어가던 컨트롤러에서 `PRESETS` 데이터를 `design-presets.js`로 외부 모듈화하여 구조 개선 완료.
  4. **신규 기능 1**: 프리셋 `즐겨찾기` 기능 추가 (별표 클릭 시 localStorage에 저장되어 최상단 노출).
  5. **신규 기능 2**: `Undo(되돌리기)` 버튼 추가. 이전 5개의 테마 변경 기록을 추적하여 안전하게 원상복구.
  6. **버그 픽스**: 
     - Undo 사용 시 예전 버전 데이터 포맷 오류로 인한 멈춤 현상 수정 (초기 데이터 주입 및 안전 방어코드 추가).
     - CSS 코드 노출 버그 및 누락되었던 폰트, 색상값 복구 오류 수정.
  7. 삭제가 필요했던 옛날 `OPEN_DESIGN_BRIDGE.md` 및 `.bat` 고아 파일 완벽 정리 및 `final/` 디렉터리 동기화 완료.
- **교훈/특이사항:**
  - UI에 스크립트 기능(Undo 등)을 연결할 때, localStorage 기반의 과거 데이터가 문제를 일으킬 수 있으므로 **하위 호환성 체크 및 방어적 초기화 코드(try-catch, fallback)** 작성이 필수적임을 확인.
  - CSS 주입 시 `style` 태그 스코프를 벗어나 텍스트로 노출되는 실수를 방지하기 위해, 파일 분리 정책(`css` 파일로 완전히 이관)이 매우 효과적임.

## 2026-05-23 외부 엔진 폐기 및 하이브리드 스튜디오 전환 (VAS 2.5.0 릴리즈)

- **분류:** `[아키텍처 간소화 및 디자인 스튜디오 업그레이드]`
- **수행 내용:**
  1. 기존의 무거운 Open Design 외부 앱(Electron) 연동 및 로컬 서버 구동 로직(`server.js`)을 전면 폐기.
  2. 브릿지 관련 스크립트(`open-design-create-job.py` 등) 삭제 및 `Run-VAS-System.bat`을 예전 로컬 웹 직접 실행 모드로 원상 복구.
  3. 백업에서 가볍고 강력했던 **자체 내장 스튜디오(`design-controller.html`)**를 추출하여 복구.
  4. 복구된 내장 스튜디오에 오픈 디자인 급의 고급스러운 다크 모드 전문 툴(UI/UX) 디자인을 덧입혀 "하이브리드 디자인 스튜디오"로 업그레이드 (Awwwards 톤 앤 매너 적용).
  5. 배포본(`final/`) 완벽 동기화 및 쓰레기 파일 클린업 완료.
- **교훈/특이사항:**
  - 사용자 피드백(어렵고 무겁다)에 기민하게 반응하여, 고도화된 기능(외부 엔진 연동)보다 "직관성과 가벼움"을 택하는 것이 시스템 철학에 맞음. 과거의 가벼운 에셋을 버리지 않고 보관해둔 백업 정책(`.vas_backups/`) 덕분에 10분 내로 빠른 아키텍처 롤백 및 융합이 가능했음.

## 2026-05-23 Open Design 원클릭 자동 실행 및 로컬 서버 도입

- **분류:** `[UX 개선 및 아키텍처 전환]`
- **수행 내용:**
  1. 브라우저 보안 정책으로 인한 `.bat` 파일 직접 실행 불가 문제를 해결하기 위해, 외부 의존성(npm) 없는 Node.js 내장 모듈 기반의 초경량 로컬 서버(`server.js`) 구축.
  2. `Run-VAS-System.bat`이 서버를 구동하고 브라우저를 띄우는 방식으로 부트스트랩 시퀀스 변경.
  3. `as-hub.html` 내에 로컬 서버 API(`/api/open-design/launch`)와 연동하여 버튼 원클릭으로 Open Design 설치 확인 및 자동 실행/설치를 수행하도록 기능 개편.
  4. 모달 창 대신 직관적인 토스트(Toast) 알림 UI로 진행 상태(확인 중, 설치 시작, 실행 완료) 표시.
- **교훈/특이사항:**
  - `file://` 프로토콜 한계를 극복하기 위해선 가벼운 로컬 데몬(서버) 레이어가 필수적임. Node.js 내장 모듈만 활용하여 의존성 없는 로컬 환경을 보장하면서도 강력한 시스템 권한 앱 실행 제어가 가능해짐.

## 2026-05-23 Open Design 실행 모달 UX 수정 (브라우저 보안 정책 대응)

- **분류:** `[UX 버그 픽스]`
- **수행 내용:**
  1. `as-hub.html` 모달의 "실행 시도" 버튼이 `window.open('scripts/Run-Open-Design.bat')`을 호출하여 브라우저가 bat 파일을 텍스트로 표시하던 문제 수정.
  2. 모달을 스텝 가이드 형태로 전환: ① 파일 탐색기에서 프로젝트 폴더 열기 → ② bat 파일 더블클릭 안내.
  3. "실행 시도" 버튼을 "📋 경로 복사" 버튼으로 변경하여 실용적 UX 제공.
  4. 스텝 넘버 UI 스타일(네오브루탈리즘 컬러 뱃지) 추가.
- **교훈/특이사항:**
  - 브라우저 보안 샌드박스(`file://` 프로토콜 포함)에서는 `.bat`, `.exe` 등 로컬 실행 파일을 `window.open()`이나 `<a download>`로 실행/다운로드할 수 없음. 로컬 독립형 웹앱에서는 실행 안내형 UX가 유일한 해결책.

## 2026-05-23 Open Design 메인 엔진 전환

- **분류:** `[디자인 시스템 대체 및 단순화]`
- **수행 내용:**
  1. 자체 `design-controller.html` 기반 디자인 컨트롤러를 제거하고 Open Design을 `tools/open-design/` submodule로 포함.
  2. 허브 첫 카드를 `Open Design Studio`로 전환하고, 비개발자가 의뢰서 작성 → 작업 JSON 생성 → Open Design 실행 순서를 볼 수 있는 `src/open-design-studio.html`을 추가.
  3. Designer 스킬과 디자인 시스템 문서를 Open Design 우선 구조로 정리.
  4. `final/` 배포본도 동일 구조로 동기화.
- **교훈/특이사항:**
  - 더 완성도 높은 외부 디자인 런타임이 있을 때는 내부 유사 기능을 유지하기보다 과감히 제거하고, VAS는 운영/브릿지/배포 역할에 집중하는 편이 사용자 경험이 명확함.

## 2026-05-23 Open Design JSON 브릿지 도입

- **분류:** `[디자인 엔진 연동 아키텍처]`
- **수행 내용:**
  1. Open Design을 VAS 내부 코드에 직접 섞지 않고 별도 실행 엔진으로 운용하는 JSON 브릿지 방식을 채택.
  2. `docs/OPEN_DESIGN_BRIDGE.md`에 작업 JSON과 결과 JSON 계약, 실행/회수 명령, 운영 규칙을 문서화.
  3. `scripts/open-design-create-job.py`, `scripts/open-design-collect-result.py`, `scripts/Run-Open-Design.bat`를 추가해 VAS 의뢰를 Open Design 작업으로 만들고 결과 산출물을 `final/open-design-output/`로 회수할 수 있게 함.
  4. 신규 브릿지 파일을 `final/`에 동기화하여 Final-Centric 운영 규칙을 유지.
- **교훈/특이사항:**
  - 대형 외부 런타임은 VAS와 직접 병합하기보다 JSON 계약을 경계로 연결하는 편이 업데이트, 실패 복구, 보안 검토에 유리함.

## 2026-05-20 Stark 2.4.1 패치: 네오브루탈리즘 테두리 두께 및 버전 최적화 (Stark 2.4.1 패치)

- **분류:** `[디자인 QA 및 스타일 튜닝]`
- **수행 내용:**
  1. **네오브루탈리즘 디폴트 테두리 두께 슬림화:** 카드의 4px 보더가 다소 둔탁하고 과하게 굵다는 사용자 피드백을 반영하여, 세련되면서도 강렬한 느낌을 동시에 주는 `2px`로 전격 슬림화(Manual Override 프리셋 `neobrutal` 내 `bw`를 `4`에서 `2`로 조정).
  2. **디폴트 로더 버전 패치(v2.4.1):** 사용자가 F5 새로고침 시 이 2px 슬림 보더 네오브루탈리즘 테마가 즉각적이고 완벽하게 자동 주입/복원되도록 `CURRENT_VERSION` 플래그를 `'2.4.1'`로 전격 격상.
  3. **디자인 스튜디오 버전 및 프롬프트 개선:** 디자인 스튜디오(`src/design-controller.html`)의 프리셋 저장 버전도 `'2.4.1'`로 통일하고, AI 프롬프트 설명도 슬림화된 2px 보더 사양에 맞게 미세 튜닝 완료.
  4. **무결성 100% 검증 및 Final-Centric 동기화:** `src/` 내 수정된 핵심 파일들을 `final/` 배포 경로에 완벽 동기화하고, 131개 통합 무결성 테스트를 가동하여 100% 무결점을 보장함.

## 2026-05-20 로컬 브라우저 구버전 테마 덤프 파괴 및 Stark 강제 복원 (Stark 2.4 패치)

- **분류:** `[로컬 브라우저 구버전 테마 덤프 파괴 및 Stark 강제 복원]`
- **수행 내용:**
  1. **버전 기반 테마 복원 프레임워크(Versioned Theme Safeguard) 구축:** 구버전 Vercel/Apple 등 둥글둥글한 로컬스토리지 찌꺼기가 브라우저에 남아있어 고객 신청서 페이지(`client-application.html`)가 F5 새로고침을 해도 영구적으로 둥근 형태로 깨져 보이던 심각한 캐싱 부조화를 원천 해결.
  2. **최초 로드 시 Stark 2.4 강제 자동 패치 구현:** `src/client-application-init.js` 내부에서 `vasThemeTokensVersion` 플래그가 `'2.4'`가 아닌 구버전이거나 존재하지 않는다면, 기존의 모든 둥근 테마 캐시를 무조건 즉시 폭파(Purge)하고, 시그니처 기본 테마인 **Stark Neo-Brutalism(각진 0px 모서리, 4px 검정 굵은 보더, 하드 섀도우)** 디폴트 토큰을 localStorage에 강제 강경 주입하도록 설계.
  3. **디자인 스튜디오 버전 연동:** 디자인 스튜디오(`src/design-controller.html`)에서 사용자가 명시적으로 수동 프리셋을 지정할 때에만 버전 `'2.4'` 토큰과 테마 정보를 동시 저장하게 세팅하여 신청서와의 영구적인 싱크를 보장.
  4. **배포본 미러링 및 검증:** 수정한 파일들을 `final/` 폴더에 완벽 동기화하고, 131개 무결성 테스트를 가동하여 100% 올패스 검증 확인 완료.

## 2026-05-20 디자인 스튜디오 기본 테마 및 초기화 오류 개선 (Neo-Brutalism 기본값 설정)

- **분류:** `[디자인 스튜디오 기본 테마 및 초기화 오류 개선]`
- **수행 내용:**
  1. **디자인 스튜디오 초기 로딩 기본 프리셋 개정:** `src/design-controller.html`에서 브라우저가 최초 실행되거나 아무 버튼도 클릭하지 않은 채 켜졌을 때, `PRESETS.vercel`로 잡혀있어 Vercel 테마(둥근 모서리, 연회색 보더)가 자동으로 `localStorage`에 저장되어 고객 신청서 폼(`client-application.html`)의 각진 검은색 네모 정체성을 깨뜨리던 초기화 로직을 완벽 교정.
  2. **시그니처 테마 Neo-Brutalism 기본 프리셋화:** 디자인 스튜디오의 최초 활성화 프리셋 및 초기 로드 테마를 **`neobrutal` (Neo-Brutalism)**로 격상. 이로 인해 스튜디오에 처음 접속하거나 초기 구동 시 무조건 이 프로젝트의 원조 비주얼 정체성인 **각진 모서리(0px), 4px의 굵은 검정 테두리, 하드 블랙 섀도우** 테마가 안전하게 자동 설정 및 동적 전파되도록 개선.
  3. **프로그램 방식 프리셋 적용 예외 처리:** `applyPreset` 함수에서 `event` 객체가 undefined인 상태로 호출되더라도 에러가 발생하지 않도록 예외 처리 코드를 보강하고, target element가 없을 시 HTML attribute 매칭을 통해 올바른 프리셋 버튼에 `active` 클래스가 자동으로 바인딩되도록 유연성 확대.
  4. **배포본 미러링 완벽 동기화 및 무결성 검증:** 수정된 `src/design-controller.html`과 `docs/log.md`를 `final/` 배포 경로에 완벽히 동기화 복사 완료하고, 131개 시나리오 10-Loop 통합 정합성 검증 테스트를 스모크 1회 구동하여 100% 무결점으로 통과함을 보장.

## 2026-05-20 기본 디자인 정체성 강화 및 배포 동기화 (Stark 테두리 복원)

- **분류:** `[기본 디자인 정체성 강화 및 배포 동기화]`
- **수행 내용:**
  1. **기본 네모 디자인(네오브루탈리즘 테두리) 복원 및 선명도 강화:** `src/client-style.css`에서 기본 테두리 색상(`--border`)을 흐릿한 연회색(`#e4e4e7`)에서 강력하고 직관적인 Stark 검은색(`#09090b`)으로 전격 개정. 이를 통해 로컬 스토리지에 테마 토큰이 존재하지 않는 기본 초기 구동 상태에서도 고유의 각진 네모 디자인 정체성이 선명하게 드러나도록 보장.
  2. **배포본 미러링 완벽 동기화:** 수정된 `src/client-style.css` 파일을 안전하게 `final/src/client-style.css`로 동기화(복사) 완료.
  3. **131개 통합 무결성 테스트 검증:** 10-Loop 통합 검증 테스트(`tests/test_integrity_10loop.py`)를 Fallback 모드로 단 1회 실행하여 131개 시나리오가 100% 정상 통과함을 보장.
- **교훈/특이사항:**
  - **동적 테마 전파 메커니즘의 예외 상황:** `design-controller.html`에서 다른 프리셋(예: Vercel, Apple 등 둥글고 희미한 테두리)을 적용할 때 `localStorage`를 통해 고객 신청서 페이지로 스타일 토큰이 동적 전파되며, 이로 인해 원래의 네오브루탈리즘 테두리가 사라진 것처럼 보이는 현상이 발생함. 이러한 동적 연동 구조와 "네모 디자인"으로의 즉시 실시간 복구 방법(컨트롤러에서 Neo-Brutalism 버튼 클릭)을 사용자에게 친절하게 가이드하는 것이 유지보수성 측면에서 중요함.

## 2026-05-20 컴퓨터 이관 및 오프라인 보장을 위한 시스템 폰트 폴백 스택 고도화

- **분류:** `[이식성 및 폰트 세이프가드 보강]`
- **수행 내용:**
  1. **시스템 폰트 폴백 스택 주입:** `client-style.css`, `design-controller.css`, `as-hub.html`에서 오직 웹 CDN 폰트(`Pretendard`, `Geist Mono` 등)에만 기대던 설계를 탈피. 인터넷 연결 유무나 컴퓨터 OS 이관 여부에 영향받지 않도록 `system-ui`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `ui-monospace`, `SFMono-Regular` 등 OS 안전 시스템 폰트 스택을 대거 보강.
  2. **동적 테마 패치 복원력 고도화:** `as-hub.html` 및 `client-application-init.js` 내부의 `localStorage` 기반 테마 복원 스크립트를 정비하여, 프리셋 전환이나 토큰 덮어쓰기 시에도 이중으로 시스템 폴백이 상속되도록 예외 처리.
  3. **한글 깨짐 주석 정비:** UTF-8 한글 깨짐이 존재하던 `client-application-init.js` 상단의 주석을 바르게 교정.
  4. **Final-Centric 동기화 및 무결성 검증:** 루트의 변경 사항을 `final/` 내 4개 파일에 완벽 복사 미러링하고, 131개 시나리오 통합 무결성 테스트 100% PASS 확인 완료.
- **교훈/특이사항:**
  - **오프라인 퍼스트(Offline-First) 정신:** CDN 웹 폰트는 인터넷 연결 속도 및 신뢰성에 크게 구애받으므로, 컴퓨터가 바뀌는 상황(경로 및 인터넷 환경 단절)을 대비해 CSS 폰트 스택과 JS 문자열 파서의 2중 안전 장치(폴백 스택)를 꼼꼼하게 마련하는 것이 웹앱의 지속가능한 이식성에 절대적으로 유리함.

## 2026-05-20 완료 화면 복귀 후 뒤로가기 시 네비게이션 실종 버그 패치

- **분류:** `[네비게이션 UX 및 레이아웃 버그 픽스]`
- **수행 내용:**
  1. **인라인 디스플레이 스타일 조작 제거:** `showDone()`과 `goBackFromDone()` 함수에서 사용하던 강제 인라인 `style.display = 'none' / 'block'` 조작을 완전히 제거.
  2. **클래스 기반 가시성 제어 정형화:** CSS `.active` 규칙에 의해 display 속성이 자연스럽게 결정되도록 일관성을 부여하고, opacity 및 transform 트랜지션만 인라인으로 부드럽게 복구되도록 리팩토링.
  3. **레이아웃 왜곡 원천 차단:** 완료 화면에서 복귀 후 뒤로가기를 할 때 이전 스텝이 투명한 상태로 자리를 차지하여 네비게이션 버튼을 화면 아래로 밀어버리던 기하학적 레이아웃 충돌 문제를 완벽히 해결.
  4. **무결성 검증 완료:** 131개 검증 시나리오 통합 무결성 테스트 100% PASS 확인 및 `final/` 배포 미러링 완벽 동기화 완료.

---

## 2026-05-20 프리뷰 내 전체 텍스트 요소 실시간 자간 동기화

- **분류:** `[디자인 QA 및 버그 픽스]`
- **수행 내용:**
  1. **실시간 자간 상속 대상 전면 확장:** `src/design-controller.css` 및 `final/src/design-controller.css`에서 특정 선택자(`.adv-preview h2, p, h3` 등)에만 적용되던 `letter-spacing: var(--p-ls, inherit);` 규칙을 `.adv-preview` 하위의 모든 요소(`.adv-preview *`)로 확장.
  2. **모든 비주얼 컴포넌트 자간 연동 완료:** 스탯 카드(`.p-stat-card`)의 `.label`, `.value`, `.trend` 뿐만 아니라 인풋 필드(`.p-input`), 버튼 등 프리뷰 내 모든 한글/영문 텍스트가 자간 슬라이더 조절 시 100% 동기화되어 실시간 반응하도록 해결.
  3. **통합 테스트 자가 검증:** `test_integrity_10loop.py` 를 실행하여 131개 무결성 테스트 항목 100% 올패스 통과.
- **교훈/특이사항:**
  - **CSS 변수 상속의 활용:** 프리뷰 컴포넌트 내부에서 일부 요소만 자간이 누락되는 파편화를 방지하기 위해서는, 특정 태그를 전수 나열하기보다 와일드카드(`*`) 상속 설계를 적용하여 뷰 컨테이너 전체의 통일성을 확보하는 것이 훨씬 견고함.

---

## 2026-05-20 루트 폴더 레이아웃 초간소화 및 디렉토리 대정리

- **분류:** `[구조 최적화 + 테스트 아키텍처 고도화]`
- **수행 내용:**
  1. **루트 간소화:** 루트 경로를 `README.md`, `Run-VAS-System.bat`, `as-hub.html` 3대 핵심 파일로 압축 및 격리하여 비기술자의 복잡도 장벽 완화.
  2. **논리적 서브폴더 구성:** 핵심 코드는 `src/`, 백업 스크립트는 `scripts/`, 가이드는 `docs/` 및 `.agents/`로 이관.
  3. **자가 검증 테스트 실행기 구축:** `test_html_syntax.py`, `test_client_form.py` 등을 `pytest` 없이 파이썬 기본 인터프리터로 직접 실행하는 Direct Python Runner 탑재.
  4. **한글 자간 동기화 패치:** 자간 슬라이더 조절 시 프리뷰 한글이 반응하지 않는 현상 수정을 위해 `--p-ls` 변수 바인딩 적용.
  5. **Final-Centric 동기화:** `final/` 폴더 내 구조와 바이트 크기를 루트의 최신 상태와 100% 미러링 완료.
- **교훈/특이사항:**
  - **구조적 직관성과 이식성:** 비기술적 사용자들의 경험(UX)은 직관적인 루트 폴더 구조에서 출발하며, 서드파티 의존성(`pytest` 등)이 없어도 단위 테스트가 가능하게 설계하는 것이 장기적 이식성에 유리함.

---

## 2026-05-19 마이그레이션 아카이빙 자동화

- **분류:** `[인프라 강화]`
- **수행 내용:**
  1. `vas-migration-archive.py` 신규 구축: 원본 프로젝트 스캔 및 백업 압축 배치. ZIP 검증 및 중복 격리 등 5중 안전장치 탑재.
  2. `migration-cycle.md` Step -1 추가하여 자동 아카이빙 연동.
- **교훈/특이사항:**
  - **보관 정책 이원화:** `.vas_backups/`(체크포인트 10개)와 `.temp data/`(백업 1개)의 주기를 달리 관리하여 디스크 효율성 극대화.

---

## 2026-05-19 프로젝트 무결성 감사 + 마이그레이션 보강

- **분류:** `[유지보수 + 인프라 강화]`
- **수행 내용:**
  1. 백업 오타 교정, `final/` 15개 파일 크기 동기화 및 `test_integrity_10loop.py` 검증 항목 대폭 강화 (98건).
  2. `test_dryrun_10scenarios.py`를 통한 10종 프로젝트 시뮬레이션 및 정규식 단어 경계(`\b`) 버그 해결.
- **교훈/특이사항:**
  - **서브스트링 매칭 함정:** `"invoice"` 안에 `"voice"`가 잘못 매칭되는 true-positive 예방을 위해 regex 단어 경계(`\b`) 필수 적용.

---

## ⚠️ 에이전트 행동 금지사항 (2026-05-19 등록 — 반드시 숙지)

> 사용자가 같은 말을 두 번 하지 않도록, 다음 규칙을 작업 전 반드시 체크한다.

### 파일 조작
- **PowerShell `Set-Content`로 한글 파일 절대 금지.** 이중 개행 및 깨짐 방지를 위해 Python `open(..., encoding='utf-8')` 사용.
- **색상 교체 범위 주의:** `as-hub.html`과 `client-application.html`은 개별 디자인 시스템으로 격리.
- **파일 추가 전 존재 여부 확인:** 루트에 없는 파일 허브 링크 시 404 발생 주의.

### 디자인 변경
- **허브(`as-hub.html`) 디자인 확정 상태 임의 변경 금지:**
  - 카드 모서리 `border-radius: 0` 유지
  - 카드 텍스트 호버 시 펴지는 애니메이션 유지
  - 카드 배경색 design=yellow, prompt=blue 고정
- **CSS 우선순위:** hover 및 transform 계열 규칙 설계 시 구체적 선택자 간섭 차단.
- **TASTE-RULES 적용:** Anti-Center Bias 기반 비대칭 앵커링 유지.

### 워크플로우 및 컨텍스트 압축 (Log Condensation)
- **Final-Centric:** `final/` 폴더 파일은 확인 없이 루트 복사 금지.
- **로그 자동 압축 (Log Condensation):** 작업 완료 시 이전 오래된 로그를 3~4줄 이내로 Pruning/Merge하여 토큰 낭비 방지.

### 테스트 기본 규칙
- **경량화 규칙:** 평소 개발 시 10-Loop 스트레스 테스트 대신 단일 경량 스모크 테스트(`python tests/test_integrity_10loop.py`)만 단 1회 실행.
- **스트레스 테스트 제한:** `run_10x_stress.py` 등은 사용자의 명시적 요청이 있을 때만 최종 구동.

---

## 2026-05-19 ~ 2026-05-17 이전 작업 이력 요약 (Condensed Logs)

- **2026-05-19 [코드 품질 감사 및 분리]:** `client-application.html` 인라인 스크립트를 `client-application-init.js`로 100% 분리. `client-style.css`를 3개 파일로 모듈식 분리하고 500줄 규칙 준수.
- **2026-05-19 [Auto-Orchestrator 도입]:** 에이전트 간 연속 실행 프로토콜(`CONTEXT.md`) 주입. 프론트엔드용 `Tester Bypass` 경량 룰 추가.
- **2026-05-19 [디자인 정합성 복구]:** Pretendard 폰트 jsDelivr CDN 교체로 폰트 깨짐 해결. Geist Mono 사용 시 Pretendard 자동 폴백 백신 주입.
- **2026-05-19 [client-application UX 수술]:** DONE 화면 백 버튼 및 호버 애니메이션 추가. 선택 블록 시각 버그(보호색) 해결. 새로 작성하기(`clearForm()`) 및 CDN 오프라인 감지 UI 구현.
- **2026-05-18 [LLM Wiki 아키텍처 통합]:** 파편화된 히스토리를 `docs/log.md` SSoT로 통합하여 에이전트 간 맥락 유지 구조 정비.
- **2026-05-18 [전체 에이전트 품질 점검]:** `dashboard.html`에서 세션 건강도 로직 분리. HTML 문법 검사 도입.
- **2026-05-17 [Phase 1 완료]:** 독립형 로컬 HTTP 서버 및 6개의 디자인 허브 페이지(index, dashboard, history, controller 등) 최초 구축.
