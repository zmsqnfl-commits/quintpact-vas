# VAS 2.5.2 - Project Compass (Index)

## Operations

- [Operations Guide](./OPERATIONS.md): release flow, verification commands, backup policy, Git hygiene, and failure routing.
- [Design System](./design-system.md): built-in hybrid design studio, token presets, and visual rules.

이 파일은 에이전트 팀이 작업을 시작하기 전에 가장 먼저 읽어야 하는 **단일 진실 공급원(Single Source of Truth)**입니다.
프로젝트의 현재 상태, 기술 아키텍처 요약, 핵심 위키 문서들의 링크를 포함합니다.

---

## 🧭 프로젝트 현황 (Current State)
- **버전:** VAS 2.5.2 (Taste-Skill + Final-Centric 아키텍처 적용 및 내장 하이브리드 디자인 스튜디오 전환 완료)
- **주요 목적:** AI 에이전트 6인 팀 협업을 돕는 인간(Human) 인터페이스 및 허브 제공.
- **최근 업데이트:** LLM Wiki 방식 도입으로 인해 문서를 파편화하지 않고 `docs/` 위키 폴더 하나에서 모든 지식을 관리하도록 구조 통합.

## 🏗️ 시스템 아키텍처 (Architecture)
- **프론트엔드 스택:** 순수 Vanilla JS, HTML, Vanilla CSS
- **외부 라이브러리:** 최소화. (Pretendard 폰트 CDN, Phosphor/Radix 아이콘 CDN 사용 중)
- **로컬 구동 방식:** 완전 독립형 로컬 파일 (Run-VAS-System.bat 또는 브라우저에서 `vas-hub.html` 직접 실행)

## 📁 주요 위키 문서 (Wiki Directory)

- 📜 [**연대기 및 교훈 (docs/log.md)**](./log.md)
  - 과거에 어떤 작업이 언제 이루어졌는지, 어떤 버그/교훈이 있었는지 확인할 때 참고하세요. (이전 `HISTORY.md`와 `LESSONS.md`의 합본)
- 🎨 [**디자인 시스템 명세 (docs/design-system.md)**](./design-system.md)
  - Designer 에이전트가 확정한 컴포넌트 명세, 색상 토큰 등이 정의되어 있습니다. UI 개발 전 필독.
- 🧩 [**디자인 스튜디오 사용 흐름 (docs/design-studio-controls.md)**](./design-studio-controls.md)
  - 프리셋, Taste Profile, Agent Prompt, Token Export 흐름을 짧게 정리합니다.
- 📦 [**Clean Copy Package Plan (docs/clean-copy-package-plan.md)**](./clean-copy-package-plan.md)
  - 전체 VAS 폴더 전달 전 포함/제외 기준과 검증 흐름을 정리합니다.
- 🔌 [**하이브리드 디자인 스튜디오 (src/design-controller.html)**](../src/design-controller.html)
  - VAS 내장 디자인 컨트롤러에서 프리셋, 세부 토큰, JSON/CSS/Tailwind 내보내기를 직접 처리합니다.
- 📐 **디자인 엔지니어링 룰 (TASTE-RULES.md)**
  - `.agents/skills/designer/TASTE-RULES.md`
  - 뻔하고 지루한 AI 템플릿(Slop) 생성을 금지하고 고급스러운 Vanilla UI를 뽑아내기 위한 절대 수칙.

---

> **에이전트 행동 지침:**
> 코드를 `final/` 폴더에 병합할 때, 위 내용 중 변경된 아키텍처나 주요 상태가 있다면 이 `docs/index.md`를 함께 업데이트해야 합니다.
