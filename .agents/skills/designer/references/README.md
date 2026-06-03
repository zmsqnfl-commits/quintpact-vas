# 🎨 Designer 레퍼런스 — Claude Design 활용 가이드

> 이 문서는 Designer 에이전트가 참조하는 디자인 패턴 및 도구 활용 가이드입니다.
> `/setup-from-application` 실행 시 프로젝트에 맞게 자동 커스터마이징됩니다.

---

## 1. Claude Design 활용 워크플로우

### 디자인 시스템 구축 절차

```
1. 기존 에셋 분석 (로고, 색상, 폰트, 기존 CSS)
   ↓
2. 디자인 토큰 추출 및 정의
   ↓
3. 컴포넌트 구조 설계 (Atomic Design 참고)
   ↓
4. 프로토타입 생성 및 사용자 확인
   ↓
5. Implementer 핸드오프
```

### 디자인 토큰 구조 예시

```json
{
  "colors": {
    "primary": "#3B82F6",
    "secondary": "#8B5CF6",
    "background": "#0F172A",
    "surface": "#1E293B",
    "text": "#F8FAFC",
    "textMuted": "#94A3B8"
  },
  "typography": {
    "fontFamily": "Inter, sans-serif",
    "headingSize": "2rem",
    "bodySize": "1rem",
    "lineHeight": 1.6
  },
  "spacing": {
    "xs": "0.25rem",
    "sm": "0.5rem",
    "md": "1rem",
    "lg": "1.5rem",
    "xl": "2rem"
  },
  "borderRadius": {
    "sm": "0.25rem",
    "md": "0.5rem",
    "lg": "1rem",
    "full": "9999px"
  }
}
```

---

## 2. Figma 연동 패턴

### 방법 A — Figma 커넥터 (공식)
1. Claude 설정에서 Figma 계정 연결
2. 파일 키로 디자인 파일 접근
3. 컴포넌트/프레임 단위로 읽기/편집

### 방법 B — Figma MCP (Model Context Protocol)
1. `mcp_config_template.json`에 Figma MCP 서버 설정
2. 양방향 동기화: Claude → Figma (디자인 푸시), Figma → Claude (컨텍스트 풀)
3. 디자인 시스템 변경 사항 자동 반영

### 방법 C — html.to.design 플러그인
1. Claude에서 Artifact(HTML/CSS) 생성
2. URL 발행 후 Figma 플러그인으로 임포트
3. 편집 가능한 네이티브 Figma 레이어로 변환

---

## 3. 핸드오프 체크리스트

Designer → Implementer 인계 시 아래 항목을 포함합니다:

- [ ] 디자인 토큰 파일 (`src/assets/design-tokens.json` 또는 CSS 변수)
- [ ] 컴포넌트 목록 및 상태 정의 (hover, active, disabled 등)
- [ ] 반응형 브레이크포인트 (mobile, tablet, desktop)
- [ ] 시각 에셋 파일 (아이콘, 이미지 → `src/assets/`)
- [ ] 인터랙션 명세 (애니메이션, 전환 효과)
- [ ] 접근성 요구사항 (색상 대비, 키보드 내비게이션)

---

## 4. 디자인 원칙 (기본값)

| 원칙 | 설명 |
|------|------|
| **일관성** | 디자인 토큰을 통해 전체 프로젝트에서 동일한 시각 언어 유지 |
| **접근성** | WCAG 2.1 AA 기준 충족 (색상 대비 4.5:1 이상) |
| **반응형** | 모바일 우선(Mobile-First) 접근 |
| **성능** | 에셋 최적화 (WebP, SVG 우선, 불필요한 이미지 제거) |
| **재사용성** | Atomic Design 패턴으로 컴포넌트 계층 구성 |

> 이 원칙은 프로젝트 특성에 따라 `/setup-from-application`에서 조정됩니다.
