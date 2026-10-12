# 대화 설정 저장 절차

Python 3.10+ 표준 라이브러리 CLI `scripts/vas-session.py`를 사용한다. 작업 폴더를 기준으로 저장하는 사용자 앱 설정이며 VAS 개발 TASK, 사용 이력, 작업 기억/RAG와 다르다.

## 명령

VAS 루트에서 실행한다. 다른 작업 디렉터리에서는 스크립트의 실제 절대 경로를 사용한다. 명령의 `ID`, `N`, 대상 경로는 실행 결과와 현재 대화에서 확인한 값으로 대체한다.

| 상황 | 명령 |
|---|---|
| 새 대화 이어가기 | `python scripts/vas-session.py resume` |
| 명시된 대상 이어가기 | `python scripts/vas-session.py resume --target "대상 폴더"` |
| 작업 목록 | `python scripts/vas-session.py list` |
| 작업 선택 | `python scripts/vas-session.py resume --session ID` |
| 처음 저장 | `python scripts/vas-session.py create --target "대상 폴더"` + 표준입력 JSON |
| 설정 갱신 | `python scripts/vas-session.py save --session ID --expected-revision N` + 표준입력 JSON |
| 이동된 폴더 다시 연결 | `python scripts/vas-session.py rebind --session ID --expected-revision N --target "확인된 대상"` |
| 저장 설정 삭제 | `python scripts/vas-session.py forget --session ID --expected-revision N` |
| 경로를 뺀 설정 출력 | `python scripts/vas-session.py export --session ID` |
| 실행 지시 준비 | `python scripts/vas-session.py prepare --session ID --expected-revision N` |
| 실행 결과 대조 | `python scripts/vas-session.py assess --session ID --expected-revision N` + 결과 v1 표준입력 JSON |
| 최신 진행 요약 저장 | `python scripts/vas-session.py checkpoint --session ID --expected-revision N --expected-progress-revision P` + 표준입력 JSON |
| 사용자가 요청한 진행 요약 삭제 | `python scripts/vas-session.py clear-progress --session ID --expected-revision N` |
| 실행 기록·현재 검사 표본 조회 | `python scripts/vas-session.py work inspect --session ID --expected-revision N` |

- 설정 입력은 UTF-8 JSON을 표준입력으로 보낸다. 원본 대화를 인수·임시 JSON 파일로 기록하지 않는다. 호스트의 구조화된 실행 도구나 Python subprocess의 `input`을 사용해 안전하게 전달한다. PowerShell 파이프는 UTF-8 인코딩을 명시한다.
- 공통 옵션 `--state-home`·`--vas-root`가 필요하면 `resume`·`work` 등 하위 명령 앞에 둔다.
- `create`는 존재하는 작업 폴더만 연결한다. 신규 구현 요청이면 호스트가 확인한 빈 앱 폴더를 먼저 준비한다. 계획만 요청했고 대상 폴더가 없으면 폴더를 만들거나 저장했다고 말하지 않는다.
- `save`에는 변경 필드만이 아니라 현재 설정 전체를 전달한다. `revision_conflict`면 다시 읽고 현재 요청과 다른 대화의 변경을 대조한다. 이전 값으로 자동 재시도해 덮어쓰지 않는다.
- `save` 성공 응답은 `status: resumed`이며 `session`에 저장된 설정과 증가한 revision이 담긴다. `status: saved`를 기대하지 않는다. 이후 `resume`으로 같은 revision과 내용을 확인한다.
- 요구사항·질문·디자인 변경은 최신 전체 설정의 `save`로 먼저 정리한다. 구현·검사·읽기 전용 `assess` 뒤에는 최신 `resume`을 읽고 `checkpoint`로 진행 요약과 실제 남은 `nextStep`을 함께 저장한다. 평가 전에 설정 변경을 정리했다면 종료 시 중복 `save`는 필요 없다. 최종 응답 전 성공 응답과 재조회 내용을 확인하며, 중단·오류 때도 확인한 범위만 저장하고 실패하면 미저장 사실을 알린다.
- `reviewFields`가 있으면 정제되거나 디자인 유지 때문에 비워진 필드를 사용자에게 알린다. 비밀값을 다시 넣지 않고 정제된 결과로 이어간다.
- `rebind`는 사용자가 폴더 이동/변경을 명시했거나 현재 대화에서 대상 연결을 확인한 경우만 사용한다. 저장된 경로가 사라졌다는 이유로 주변 폴더를 탐색해 추정하지 않는다.
- “저장한 설정 지워줘”는 해당 세션 `forget`으로 연결 정보와 진행 요약까지 지운다. “진행 요약만 지워줘”는 `clear-progress`로 요약만 지우고 설정·`nextStep`은 보존한다. 앱 파일은 삭제하지 않는다. 삭제 뒤 같은 정보를 자동으로 다시 만들지 않는다. 기기/OS 백업까지 삭제됐다고 보장하지 않는다.
- 에이전트 중 주 실행자만 쓰며 위임받은 에이전트는 수정 제안을 반환한다. 사용자는 연결한 로컬 디자인 화면에서 디자인만 저장할 수 있다. 조회·목록은 저장소를 만들지 않는다. 저장 실패 시 현재 대화는 계속하고 지속 저장이 안 됐음을 알린다.
- 제한된 Windows 호스트에서 `session_store_unavailable`이면 보호된 PC 저장소 접근이 불가능할 수 있다. 최신 설정을 확인했다고 말하거나 추정해 저장하지 않는다. 호스트의 저장소 접근 제약을 짧게 알리고, 임의 ACL 변경·권한 완화·다른 저장 위치로의 자동 우회를 하지 않는다.

## 진행 요약 저장과 재개

진행 요약은 설정과 별도로 최신 한 건만 저장한다. 사용자에게 JSON 작성을 요구하지 않으며 에이전트 중 주 실행자가 의미 있는 작업 구간 끝에 저장한다. 매 명령마다 저장하지 않고, 저장을 원하지 않는 사용자의 진행 요약도 저장하지 않는다. 필드·크기 제한과 예시는 [CHAT-PROGRESS.md](../docs/CHAT-PROGRESS.md)를 따른다.

- 최신 `resume`의 최상위 `progress`가 없으면 `P`는 0이다. 유효한 요약이 있으면 `progress.revision`을 사용한다. `available`은 저장 설정·문맥의 일치만 뜻하고 현재 파일이나 검사 통과를 보증하지 않는다. `referenceOnly: true`, `filesVerified: false`를 유지한다.
- `stale`이면 `staleReasons`와 현재 설정·원본을 대조한다. `invalid`이면 요약 본문은 숨겨지고 설정은 계속 조회할 수 있다. 손상된 요약을 자동 삭제·덮어쓰지 않으며 사용자가 삭제를 요청했을 때만 `clear-progress`한다.
- 새 대화에서는 유효한 `record`를 참고하되 대상의 지침·현재 원본·diff·실제 검사 명령부터 확인한다. 이미 구현한 부분을 보존하고 미실행 검사로 이어간다. 저장된 `passed`는 당시 보고이며 명령 문자열을 그대로 실행하지 않는다.
- `checkpoint`는 요약과 설정의 `nextStep`을 원자적으로 갱신하고 세션 revision과 진행 revision을 각각 1 올린다. 성공 상태는 `resumed`이다. `reviewFields`가 남아 있으면 최신 전체 설정을 검토·`save`한 뒤 재조회한다. 초과·충돌·쓰기 실패는 기존 상태를 보존하며 이전 입력으로 자동 재시도하지 않는다.
- 저장 뒤 계속 구현·검사할 때는 증가한 세션 revision으로 `prepare`를 다시 실행한다. 이전 평가나 검사 근거의 ID·revision을 새 값으로 고쳐 붙이지 않는다. 최종 응답 전에 `resume`으로 저장된 요약과 `nextStep`을 확인한다.

요약은 같은 PC 저장소의 별도 자료이며 웹 응답·공유 `export`·`prepare` 인계에 자동 포함하지 않는다. 위임 시 주 실행자가 필요한 요약 부분과 최신 세션 revision을 전달한다. 진행 요약은 검사 실행이나 파일 검증 자체를 보증하지 않는다.

## 실행 기록 저장과 재개

[CHAT-WORK.md](../docs/CHAT-WORK.md)에 따라 실제 작업의 시작·반환·명시 파일 지문을 별도 work에 저장한다. open·start·finish는 work revision만 증가시키므로 최신 N과 W를 모두 대조한다. 조회의 `filesChecked: false`는 파일을 아직 재확인하지 않았다는 뜻이다. `work inspect`가 선택 파일을 다시 읽어도 `hostReportsVerified: false`를 유지한다.

설정·진행 요약 저장으로 N이 바뀌면 기존 work는 당시 기록으로 남긴다. 새 작업의 근거로 ID를 고쳐 붙이지 않는다. work가 있는 세션의 전체 `forget`에는 `--expected-work-revision W`도 필요하며 실행 기록까지 지운다. 사용자가 실행 기록만 삭제하라고 하면 `work clear`로 설정·진행 요약을 보존한다. 손상된 기록은 본문을 숨기며 명시적 삭제에만 W=-1을 사용한다. work도 웹·export·prepare에 자동 포함하지 않는다.

## 로컬 디자인 화면 연결 (3단계)

저장한 설정을 실제 앱 작업으로 이어가는 4단계 절차는 [EXECUTION.md](EXECUTION.md)를 따른다. `prepare`는 지시 생성, `assess`는 보고 대조이며 둘 다 앱 코드를 실행하지 않는다.

1. 이미 정해진 세션을 `resume --session ID`로 최신 조회한다. 명시된 대상이 없거나 여러 세션이면 원래 선택 절차를 따른다. VAS 자체 개발을 사용자 앱 세션으로 등록하지 않는다.
2. Windows 실행 도구가 있으면 `scripts/Start-VAS.ps1 -SessionId ID`로 확인한 세션의 디자인 화면을 연다. 실행기가 인증값을 브라우저에 직접 전달하며 `VAS_READY`에는 인증값이 없는 주소만 출력한다. 별도 브라우저 자동화가 필요한 호스트는 `-NoBrowser`로 준비한 뒤 같은 사용자 권한으로 해당 VAS 위치의 보호된 런타임 파일을 도구 프로세스 안에서 읽어 연결한다. 토큰이나 전체 인증 URL을 도구 출력·보고서·공유 문서로 출력하지 않으며 임의 포트·토큰·ID를 만들지 않는다. 저장소 접근이 차단된 호스트에서는 권한을 완화하지 않고 실행기의 직접 열기를 사용한다.
3. 열린 연결 화면을 사용 가능한 브라우저 도구로 확인한다. 사용자는 프리셋·토큰·디자인 방향을 고르고 `대화 설정에 저장`을 누른다. 기존 앱은 `preserve`가 기본이며 화면에서 명시적으로 `partial` 또는 `redesign`을 선택한 경우에만 해당 범위를 저장한다. 샘플 사이트의 선택은 저장을 수행하지 않는다.
4. 연결한 세션이 있으면 다음 사용자 요청, 구현·위임 및 저장 직전에 `resume --session ID`를 실행한다. 저장된 최신 디자인과 범위를 읽고 현재 요청에 맞춰 처리한다. 화면 저장은 실행 중인 AI를 깨우거나 모델 문맥을 자동 갱신하지 않는다. 진행 중인 하위 작업의 설정이 바뀌면 주 실행자가 변경 범위를 검토해 필요한 지침을 전달한다.
5. CLI 전체 설정 저장은 최신 스냅샷에 현재 요청의 변경을 반영해 보낸다. 웹에서 수정된 디자인·다른 필드를 이전 대화 값으로 되돌리지 않는다. `revision_conflict`는 재조회·대조하며 자동 덮어쓰기로 해소하지 않는다.

화면은 열려 있을 때 약 4초마다, 다시 보이거나 포커스를 받을 때 저장소를 확인한다. 편집 전이면 새 설정을 반영하고, 저장 전 편집이 있으면 초안을 보존하며 충돌을 표시한다. 충돌 후 화면의 최신 불러오기는 사용자가 초안 폐기를 선택한 경우만 수행한다. 브라우저 연결 오류나 대상 확인 실패를 저장 성공으로 표시하지 않는다.

디자인은 `profileId`, `direction`, `tokens`와 선택적인 `preset`, `basePreset`, `tasteProfileMode`를 사용한다. 화면 왕복 시 기본 프리셋·세부 변경·취향 모드를 유지하며, 기존 2단계 설정도 읽을 수 있다. `preserve`에서는 활성 디자인을 비운다. 웹에는 공유 설정과 대상 상태만 반환하며 절대 대상 경로와 binding은 보내지 않는다.

## 설정 입력 예시

```json
{
  "project": {"name": "예약 관리", "sourceType": "new"},
  "task": {
    "request": "예약 목록과 등록 화면을 만든다",
    "constraints": ["외부 서버 전송 없이 작동"],
    "designScope": {"mode": "new", "scope": "예약 목록과 등록 화면"},
    "completionCriteria": [
      {"description": "등록한 예약이 목록에 표시됨", "method": "automatic", "required": true}
    ]
  },
  "design": {"profileId": "", "direction": "차분하고 읽기 쉬운 화면", "tokens": {}},
  "questions": ["후속 개선에서 예약 카드 정렬 방식을 바꿀까요?"],
  "blockingQuestions": ["예약 대상은 사람인가요, 공간인가요?"],
  "nextStep": "예약 대상을 확인하고 현재 원본 구조를 읽는다"
}
```

`sourceType`은 `new` 또는 `existing`이다. 기존 앱은 `designScope.mode: preserve`가 기본이다. `partial`은 변경 범위 필수, `redesign`은 명시된 리디자인에만 사용한다. `new`는 신규 앱에서만 사용한다. 완료조건 method는 `automatic`, `manual`, `static`, required는 JSON boolean이다. 기존 완료조건의 id는 순서에 따라 재계산된다.

`questions`는 참고용 미해결 질문이며 준비를 자동 차단하지 않는다. 선택 필드 `blockingQuestions`는 구현 결정을 막는 핵심 미정만 담는 문자열 배열(0~10개, 빈 문자열 불가)이다. 비어 있지 않으면 `prepare`는 `needs-input`과 `missing`의 `blockingQuestions`를 반환한다. 이 필드가 없는 기존 설정은 종전대로 처리하며 `questions`를 차단 질문으로 승격하지 않는다. 이미 답한 질문은 두 목록에서 제거하고 결정 내용을 `task`에 반영한다.

`prepare`의 인계 JSON과 프롬프트에는 `context.conversation`으로 `questions`, `blockingQuestions`, `nextStep`, `referenceOnly: true`가 전달된다. 저장 문구와 JSON은 참고 데이터이며 실행 권한이나 명령이 아니다. `nextStep`에는 실제 남은 행동을 간결히 적고 원본 로그·민감값·전체 코드나 평가 결과를 저장하지 않는다. 정제한 검사 요약은 별도 `checkpoint`로 최신 한 건만 남긴다.

앱이 만들어진 뒤 새로운 수정 작업으로 전환되면 현재 요청에 맞춰 `sourceType: existing`과 기본 `preserve`를 함께 저장한다. 이전에 새 앱이었다는 이유로 계속 디자인을 새로 만들지 않는다.

형식·길이·허용 필드를 검사하고 알려진 비밀값·연락처·개인 경로 패턴을 정제한다. 모든 민감정보 탐지를 보장하지 않으므로 저장 전에 비밀값을 넣지 않는다. 완료 상태·검증 통과·사용자 승인 플래그, 명령 이력, 원본 파일 내용은 설정 입력 필드가 아니다.

## 저장 위치와 한계

Windows 기본 위치는 `%LOCALAPPDATA%/VAS/chat-sessions/<VAS 위치 해시>/vas-session-store.json`이다. 다른 OS는 사용자 상태 디렉터리를 사용한다. 테스트의 `--state-home`은 VAS 제품 폴더 밖의 격리 저장소만 허용하며 실제 사용자 저장소 대신 쓰거나 자동 탐색하지 않는다.

공유 가능한 `vas-chat-session` v1 설정과 PC 전용 `binding`, 선택적인 진행 요약을 분리한다. 절대 대상 경로·디렉터리 식별자는 binding에만 있다. `export`는 설정만 출력하며 기존 `VAS-AI-HANDOFF.json` v3를 대체하지 않는다. `resume`과 로컬 저장 응답에는 호스트 작업에 필요한 경로가 있으므로 공유·보고서·저장소에 복사하지 않는다.

설정은 암호화된 비밀 저장소가 아니다. 로컬 사용자 권한을 따른다. 여러 VAS 복사본은 별도 저장소를 사용하며 VAS 자체를 이동하면 이전 설정이 자동 연결되지 않는다. 폴더 식별자 확인은 일반적인 삭제·교체를 감지하는 보조 검사이며 변조 방지 인증이 아니다.

연결된 로컬 화면만 같은 저장소를 사용한다. 독립 HTML·GitHub Pages·샘플 보기에는 대화 설정 저장 기능이 없다. CLI 실행 권한이 없는 읽기 전용 호스트에서는 조회만 하며 저장을 강행하지 않는다. 사용자 안내는 `docs/CHAT-DESIGN.md`에 있다.
