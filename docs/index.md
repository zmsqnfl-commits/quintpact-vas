# VAS 2.9.0 시스템 지도

## 사용자 흐름

AI에서 VAS 폴더 열기 → 작업 종류·실제 대상 구분 → 설정 저장·디자인 화면 연결 → 최신 설정으로 인계 준비 → 코딩 호스트에서 원본 확인·구현·필요한 위임·검증 → 결과와 원래 조건 대조. 같은 PC의 같은 VAS 설치에서 새 대화로 설정을 이어갈 수 있습니다. [대화로 시작하기](CHAT-START.md), [설정 저장과 재개](CHAT-STATE.md), [채팅과 디자인 연결](CHAT-DESIGN.md), [구현과 검증](CHAT-EXECUTION.md)을 참고하세요.

기존 화면 설정 흐름:

```text
Run-VAS-System.bat
  -> 시작 화면
     -> 새 프로젝트 -> 요구사항 -> 디자인 -> 프롬프트 복사
     -> 기존 프로그램 -> 폴더 위치 -> 작업 작성 -> 디자인 -> 프롬프트 복사
  -> 코딩 도구에서 RBG 확인 후 실제 작업
```

기존 웹 화면은 프롬프트와 선택 JSON을 만듭니다. 로컬 디자인 스튜디오는 저장된 채팅 작업을 선택해 디자인을 함께 사용할 수 있습니다. 앱 실행이나 배포를 관리하는 프로젝트 대시보드는 제공하지 않습니다. 이번 버전의 변경과 지원 범위는 [2.9.0 릴리스 안내](releases/2.9.0.md)에 있습니다.

## 구성

| 영역 | 역할 | 기준 파일 |
|---|---|---|
| 시작 | 두 가지 시작 방식 선택 | `src/vas-hub.html` |
| 새 프로젝트 | 요구사항·디자인·프롬프트와 선택 JSON | `src/client-application.html` |
| 기존 프로그램 | 폴더 위치·작업·디자인 프롬프트와 선택 JSON | `src/project-import.html` |
| 공통 도움말·설정 | 작업 순서와 작업 기억 제어 | `src/setup-tools.js` |
| 디자인 | 프리셋·토큰·에이전트 디자인 지침 | `src/design-controller.html` |
| 채팅 설정 | PC 전용 연결 정보와 공유 설정의 저장·재개 | `scripts/vas-session.py`, `scripts/vas_session.py` |
| 디자인 연결 | 명시된 세션의 화면 저장·최신 조회·충돌 처리 | `src/chat-design-sync.js`, `scripts/vas_session_web.py` |
| 대화 실행 인계 | 최신 설정·역할 자료에 연결된 준비와 결과 대조 | `scripts/vas_session_execution.py`, `.agents/EXECUTION.md` |
| 디자인 샘플 | 선택한 토큰으로 실제 샘플 사이트 확인 | `src/design-sample.html` |
| 검증 앱 | VAS 인계로 만든 별도 Morrow 작업 보드 | `src/proof-app/index.html`, `docs/verification/README.md` |
| 범위·완료조건 | 디자인 변경 권한과 조건별 확인 방법 | `src/task-policy.js`, `src/task-inputs.js`, `scripts/vas_task_policy.py` |
| 완료 평가 | 자기보고와 별도 사용자 관찰에 따른 평가 | `src/result-assessment.js`, `scripts/vas_result_assessment.py` |
| 인계 계약 | 인계 v3 생성과 호환용 결과 v1 검증 | `src/agent-contract.js`, `src/handoff-workflow.js`, `scripts/vas_ai_contract.py` |
| 호환 모듈 | 결과 JSON 검증·RAG 검토(기본 UI 미노출) | `src/ai-result-import.js`, `src/handoff-context-review.js` |
| 런타임 | 로컬 웹 실행과 호환 API | `scripts/Start-VAS.ps1` |
| 배포 | Windows·독립 폼·Pages 생성 | `scripts/build_release.py` |

## 저장·호환

- 작업 기억: Windows 사용자 로컬 또는 브라우저 IndexedDB
- 일반 디자인 설정: 브라우저 저장소와 URL 상태
- 연결된 채팅 디자인: PC의 공통 세션 저장소, 저장 전 화면 초안은 메모리만 사용
- 체크포인트: `.vas_backups/` 최신 10개
- 배포물: `dist/`
- 기존 `workspace/` 프로젝트와 복사·등록 모듈은 삭제하지 않지만 기본 UI에는 노출하지 않습니다.

## 운영 원칙

- 모든 기능은 외부 CDN 없이 동작합니다.
- 브라우저 최초 저장소 초기화가 불가능하면 임시 저장임을 표시합니다. 연결된 저장소의 쓰기·삭제 실패를 성공으로 처리하지 않습니다.
- 작업 기억은 동의 없이 자동 활성화하지 않습니다.
- 최종 JSON에는 요구사항·디자인·안전 규칙·AI 안내만 포함하며 구조·기술 스택은 추정하지 않습니다.
- 기존 프로그램의 절대 경로는 복사 프롬프트에만 넣고 JSON·작업 기억에는 저장하지 않습니다.
- 대화 재개에 필요한 대상 경로는 제품 밖의 PC 전용 binding에만 저장하며 공유 설정·브라우저 응답에는 포함하지 않습니다.
- 화면 저장은 AI를 실행하지 않습니다. 다음 요청·구현·위임·저장 전에 주 실행자가 최신 세션을 재조회합니다.
- 실행 인계 준비와 결과 대조는 앱 코드를 실행하지 않습니다. 실제 원본 확인·구현·역할 호출·테스트는 코딩 호스트가 수행합니다.
- 대화 실행 결과는 현재 세션·revision·설정·역할 자료에 연결한 인계와 대조합니다. 오래된 결과의 ID만 바꿔 최신 작업의 증거로 재사용하지 않습니다.
- AI 보고·VAS 평가·사용자 확인을 구분합니다. 대화 실행 CLI는 사용자 직접 확인을 입력받지 않으며 보고만으로 완료를 인증하지 않습니다.
- 기본 저장·복사는 인계 영수증을 만들지 않습니다.
- 호환용 반복 계약은 ID·해시·sourceType과 중복을 검사합니다. 로컬 영수증이 없을 때는 사용자 수동 확인이 필요하며, 확인된 불일치·중복은 수동 확인으로 우회할 수 없습니다.
- 해시는 입력 일관성을 확인합니다. 실제 에이전트 실행·권한·테스트 성공의 증명은 코딩 호스트의 실행 결과에서 별도로 확인합니다.
- 파일은 500줄 이하로 유지합니다.

상세 범위·완료 판정·호환 정책: [작업 범위와 완료 확인](completion-policy.md).
