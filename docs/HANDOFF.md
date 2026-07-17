# VAS 2.6.3 AI 인계

새 프로젝트와 기존 프로그램 모두 `VAS-AI-HANDOFF.json`을 만듭니다.

## 사용

1. 새 프로젝트는 빈 폴더, 기존 프로그램은 원본 폴더를 코딩 도구에서 엽니다.
2. `VAS-AI-HANDOFF.json`을 첨부합니다.
3. VAS에서 복사한 프롬프트를 붙여넣습니다.

## JSON 계약

- `project`: 이름, 신규·기존 구분, 목표
- `task`: 요청, 제약, 완료 기준
- `analysis`: 기존 프로그램의 기술·구조 요약
- `context.requirements`: 사용자가 확인한 요구사항
- `context.design`: 프리셋, 토큰, 디자인 지침
- `security`: 원본 불변과 제외 규칙
- `assistantGuide`: 코딩 도구에 붙여넣을 문장

절대 경로, 비밀값, 연락처, 작업 기억 원본은 포함하지 않습니다.
