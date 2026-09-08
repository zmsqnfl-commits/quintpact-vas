# 디자인 스튜디오 사용 흐름

VAS 디자인 스튜디오는 프리셋과 Taste Profile을 조정하고 실제 디자인 토큰과 구현 지침을 코딩 AI에 전달합니다.

## 사용

1. `src/design-controller.html` 또는 허브의 디자인 스튜디오를 엽니다.
2. 프리셋을 고르고 색상·폰트·간격 등을 조정합니다.
3. Taste Profile을 자동으로 두거나 원하는 방향을 선택합니다.
4. 설정을 저장한 뒤 신청서에서 프롬프트를 복사합니다. JSON 저장은 선택입니다.
5. 코딩 AI에서 실제 작업 폴더를 열고 프롬프트와 참고 파일 원본을 전달합니다.

새 환경은 `awwwards / Architecture Editorial (curatedEditorial)`으로 시작합니다. 기존 선택과 사용자 토큰이 우선합니다.

## 프리셋과 Taste Profile

- 프리셋은 색상·폰트·간격·반경·테두리·그림자를 정합니다.
- 세부 값을 바꾸면 `preset`은 `custom`이 되지만 `basePreset`에 원래 방향을 유지합니다.
- 자동 Taste Profile은 `basePreset`을 따릅니다. 색상 하나를 바꿔도 디자인 방향이 초기화되지 않습니다.
- 수동 Taste Profile은 프리셋을 바꿔도 유지되며, 자동 선택으로 되돌릴 수 있습니다.
- 선택값은 저장·새로고침·되돌리기·화면 이동에서도 유지됩니다.
- Taste Profile은 프롬프트와 미리보기 배치를 변경합니다. 확정된 색상 등 토큰은 덮어쓰지 않습니다.
- 미리보기는 방향을 보여주는 샘플입니다. 완성 화면은 실제 프로젝트에서 구현 후 비교해야 합니다.

## 전달 내용

프롬프트에는 Designer 스킬 본문, 프로필 규칙, 프리셋 방향, 정확한 디자인 토큰, 사용자 요구사항과 검증 기준이 포함됩니다.
사용자 요구와 대상 프로젝트 규칙 → 확정된 토큰·참고 자료 → Taste Profile → 프리셋 기본값 순으로 적용합니다.
VAS 자체의 Vanilla JS·오프라인 제약을 다른 프로젝트의 React 등 기술 스택에 강제하지 않습니다.

참고 URL은 보존합니다. 참고 파일은 이름만 전달하므로 코딩 AI에 원본을 별도로 첨부해야 합니다.
파일을 받지 못한 AI가 내용을 보았다고 가정하지 않도록 프롬프트에도 안내합니다.

## 토큰 내보내기

- JSON: 현재 토큰 저장·불러오기. 외부 토큰 JSON만 불러오면 출처 프리셋은 `custom`입니다.
- CSS: CSS 변수로 내보내기.
- Tailwind: 대상 프로젝트에 맞게 적용할 참고용 설정.

## 지침 유지보수

원본은 `.agents/skills/designer/SKILL.md`, `references/profiles/*.md`, `.agents/HANDOFF-WORKFLOW.md`입니다.
변경 후 `npm run agents:build`와 `npm run knowledge:index`를 실행합니다.
생성된 `src/agent-resources.js`는 일반 화면과 독립 신청서에서 같은 지침을 사용하게 합니다.

`npm run test:python`, `npm run test:browser`, `npm run test:package`로 상태 보존·프롬프트·배포 포함 여부를 확인합니다.
