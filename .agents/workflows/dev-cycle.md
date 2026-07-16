# /dev-cycle

1. Architect: 목적·인터페이스·검증 기준 정의
2. Designer: UI 변경이 있으면 상태·접근성·반응형 명세
3. Implementer: `src/` 또는 `scripts/`에 최소 변경
4. Reviewer: 회귀·데이터 경계·500줄 점검
5. Tester: 관련 단일 테스트와 브라우저 흐름 검증
6. Security: 비밀·사용자 데이터 제외 확인 후 릴리즈 생성
7. `docs/log.md`에 결과 기록

새 사용자 프로그램은 `workspace/projects/<name>/`, VAS 자체 변경은 코어 원본에 둡니다.
