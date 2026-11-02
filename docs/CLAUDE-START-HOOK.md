# Claude Code에서 시작 상태 자동 조회하기

기본 시작 방법은 프로젝트 루트에서 에이전트가 `python -B scripts/vas.py start`를 실행하는 것입니다. Claude Code에서 같은 조회를 자동으로 실행하려면 이 프로젝트의 코드를 신뢰하고 훅 사용을 원하는 경우에만 다음 설정을 적용하세요.

1. [예시 설정](claude-session-start.example.json)의 `hooks.SessionStart` 항목을 프로젝트의 `.claude/settings.local.json`에 추가합니다. 기존 설정과 훅은 보존합니다.
2. 훅 명령이 사용할 Python 3.10 이상을 확인합니다. Linux에서 명령 이름이 `python3`이면 예시의 `command`도 `python3`로 바꿉니다.
3. 프로젝트 폴더 자체에서 Claude Code 세션을 새로 열거나 재개합니다. 훅은 `start`의 읽기 전용 결과를 Claude에 전달합니다. 사용자의 작업 범위 결정과 구현 요청은 대화에서 받습니다.

훅을 실행하지 않는 호스트나 연결 환경에서도 루트 지침에 있는 일반 `start`를 사용할 수 있습니다. 저장소 접근이나 Python 실행 오류가 있으면 해당 오류를 먼저 확인하세요.
