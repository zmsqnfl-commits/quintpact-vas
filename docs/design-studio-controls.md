# 디자인 스튜디오 사용 흐름

VAS 디자인 스튜디오는 프리셋을 고르고, 필요한 경우 Taste Profile을 조정한 뒤, 에이전트용 prompt와 디자인 토큰을 내보내는 내부 작업자용 도구입니다.

## 진입점

- 브라우저에서 `src/design-controller.html`을 엽니다.
- 일반 사용자는 `Run-VAS-System.bat` 또는 `src/vas-hub.html`에서 디자인 스튜디오로 들어갈 수 있습니다.

## 기본 흐름

1. 프리셋을 선택합니다.
2. `Taste Profile`은 기본값인 `프리셋 기준 자동`으로 둡니다.
3. `AI 에이전트 시스템 프롬프트`를 확인하고 복사합니다.
4. 필요하면 색상, 폰트, 여백, 둥글기, 테두리, 그림자를 조정합니다.
5. `포맷 추출 (JSON/CSS)` 또는 `토큰 다운로드`로 토큰을 내보냅니다.

## 프리셋

프리셋은 전체 디자인 방향을 한 번에 정합니다.

- 색상, 폰트, 반경, 여백, 그림자 같은 preview token을 반영합니다.
- Agent Prompt의 `[PRESET DIRECTION]`에 프리셋 의도를 넣습니다.
- 자동 모드에서는 프리셋에 맞는 Taste Profile을 함께 고릅니다.

## Taste Profile

`Taste Profile`은 prompt의 디자인 판단 성향을 정합니다. 화면 preview token 자체를 바꾸는 기능은 아닙니다.

### 프리셋 기준 자동

- 기본값입니다.
- 프리셋마다 정해진 profile mapping을 사용합니다.
- 다른 프리셋을 선택하면 해당 프리셋 기준 profile로 자동 전환됩니다.

### 수동 선택

- 특정 profile을 직접 고르면 prompt의 `Taste Profile`과 `[TASTE PROFILE RULES]`가 바뀝니다.
- 수동 선택 상태에서 다른 프리셋을 골라도 수동 profile이 유지됩니다.
- 다시 자동으로 돌아가려면 `Taste Profile`에서 `프리셋 기준 자동`을 선택합니다.
- 선택값은 브라우저 `localStorage.vasTasteProfileMode`에 저장됩니다.

## Agent Prompt

Agent Prompt는 에이전트에게 전달할 작업 지시문입니다. 아래 5개 섹션은 유지되어야 합니다.

- `[BASELINE RULES]`
- `[TASTE PROFILE RULES]`
- `[PRESET DIRECTION]`
- `[CONFLICT POLICY]`
- `[OUTPUT CONTRACT]`

## Token Export

- `JSON`: 현재 디자인 토큰을 저장하거나 다시 불러올 때 사용합니다.
- `CSS`: CSS 변수 형태로 다른 HTML/CSS 작업에 옮길 때 사용합니다.
- `Tailwind`: Tailwind config 형태가 필요한 경우 참고용으로 사용합니다.
- `코드 복사`: 현재 선택된 출력 형식을 클립보드에 복사합니다.

## 검증 명령

```powershell
python tests\test_html_syntax.py
npm.cmd run test:browser
```

브라우저 검사는 프리셋 토큰 반영과 Taste Profile 자동/수동 전환을 함께 확인합니다.
