# 디자인 시스템 (Design System)

이 문서는 VAS 2.6.1 에이전트 팀이 UI/UX를 개발할 때 참조하는 **단일 진실 공급원(Single Source of Truth)**입니다.
과거의 고정된(하드코딩된) 다크모드 룰은 폐기되었으며, 메인 디자인 시스템과 산출물 생성은 **내장 하이브리드 디자인 스튜디오**를 기준으로 합니다.

---

## 🎨 1. 디자인 토큰 추출 원칙 (Vibecoding Core)

Implementer 및 Designer 에이전트는 코딩을 시작하기 전, **`src/design-controller.html`과 `src/design-presets.js`의 토큰/프리셋** 또는 사용자가 제공한 산출물을 기준으로 삼아야 합니다.

- **비개발자 권장 흐름:** `Run-VAS-System.bat` 실행 → VAS 허브 → 디자인 스튜디오 → 프리셋/토큰 조정 → JSON/CSS/Tailwind 추출.
- **디자인 스튜디오 위치:** `src/design-controller.html`
- **신규 기본값:** `awwwards` 프리셋과 `Editorial Motion` Taste Profile을 사용합니다.
- 사용자(팀 리드)가 특정 디자인 시스템, 토큰 JSON, 또는 산출물을 제공하면 해당 파일을 최상위 시각 명세로 간주합니다.
- 임의의 보라색/형광색 템플릿(Slop) 그라디언트나 촌스러운 중앙 정렬은 원천 차단됩니다.

## 🔤 2. 공통 타이포그래피 (Typography Tokens)

프리셋 프롬프트에서 별도의 폰트를 지정하지 않은 경우, 아래 기본 룰을 따릅니다.

- **기본 한글 폰트:** 운영체제 기본 sans 스택 (`system-ui`, `Segoe UI`, `Malgun Gothic`, `Apple SD Gothic Neo`)
- **숫자 및 코드 폰트:** 시스템 mono 스택 (`ui-monospace`, `Cascadia Code`, `Consolas`)
- **헤드라인 규칙:** 거대하게 키우지 말고 `tracking-tighter` (자간 좁게), `leading-none` (행간 좁게) 적용.
- **이모지 규칙:** 시스템 이모지 대신 Phosphor/Radix 등 고품질 웹 아이콘 사용 원칙.

## 🪄 3. 공통 애니메이션 및 모션 (Motion Specs)

프리셋 프롬프트에서 모션 속도(Speed)를 지정받으면 해당 속도를 기준 삼아 애니메이션을 구성합니다. 무거운 외부 라이브러리(Framer Motion 등) 없이 순수 Vanilla CSS와 JS만으로 구현합니다.

- **타이밍 함수 (Timing Function):** 
  - 기본 모션: `cubic-bezier(0.16, 1, 0.3, 1)` 적용 (스프링처럼 쫀득한 움직임)
- **택타일 피드백 (Tactile Feedback):**
  - 모든 버튼/인터랙티브 요소는 `:active` 상태에서 `transform: scale(0.98);` 로 살짝 눌리는 물리적 피드백 제공.

## 📐 4. 레이아웃과 형태 (Layout & Shapes)

- **비대칭성 (Asymmetry):** 뻔한 3단 횡렬 배치, 무조건적인 텍스트 가운데 정렬 금지.
- **음수 공간 (Negative Space):** 빽빽한 컨테이너(Card) 남용 금지. 선(Divider)과 여백만으로 데이터를 그룹화하여 공기처럼 가벼운 레이아웃 지향.
- **Radius 및 Border:** 프리셋에서 주어진 토큰(예: IBM Carbon의 경우 0px, Google M3의 경우 16px)을 완벽하게 따라야 합니다.

## 5. 기본값과 호환성

- 새 저장소는 `awwwards`로 시작합니다.
- 기존 저장소의 색상·간격·프리셋은 자동 전환하지 않습니다.
- 허브와 연결 화면은 `VASThemeState`의 토큰을 사용하고, URL 상태 브리지로 선택값을 이어갑니다.
