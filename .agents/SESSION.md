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

- 설정 입력은 UTF-8 JSON을 표준입력으로 보낸다. 원본 대화를 인수·임시 JSON 파일로 기록하지 않는다. 호스트의 구조화된 실행 도구나 Python subprocess의 `input`을 사용해 안전하게 전달한다. PowerShell 파이프는 UTF-8 인코딩을 명시한다.
- `create`는 존재하는 작업 폴더만 연결한다. 신규 구현 요청이면 호스트가 확인한 빈 앱 폴더를 먼저 준비한다. 계획만 요청했고 대상 폴더가 없으면 폴더를 만들거나 저장했다고 말하지 않는다.
- `save`에는 변경 필드만이 아니라 현재 설정 전체를 전달한다. `revision_conflict`면 다시 읽고 현재 요청과 다른 대화의 변경을 대조한다. 이전 값으로 자동 재시도해 덮어쓰지 않는다.
- `reviewFields`가 있으면 정제되거나 디자인 유지 때문에 비워진 필드를 사용자에게 알린다. 비밀값을 다시 넣지 않고 정제된 결과로 이어간다.
- `rebind`는 사용자가 폴더 이동/변경을 명시했거나 현재 대화에서 대상 연결을 확인한 경우만 사용한다. 저장된 경로가 사라졌다는 이유로 주변 폴더를 탐색해 추정하지 않는다.
- “저장한 설정 지워줘”는 해당 세션 `forget`으로 연결 정보까지 지운다. 앱 파일은 삭제하지 않는다. 삭제 뒤 같은 설정을 자동으로 다시 만들지 않는다. 기기/OS 백업까지 삭제됐다고 보장하지 않는다.
- 에이전트 중 주 실행자만 쓰며 위임받은 에이전트는 수정 제안을 반환한다. 사용자는 연결한 로컬 디자인 화면에서 디자인만 저장할 수 있다. 조회·목록은 저장소를 만들지 않는다. 저장 실패 시 현재 대화는 계속하고 지속 저장이 안 됐음을 알린다.
- 제한된 Windows 호스트에서 `session_store_unavailable`이면 보호된 PC 저장소 접근이 불가능할 수 있다. 최신 설정을 확인했다고 말하거나 추정해 저장하지 않는다. 호스트의 저장소 접근 제약을 짧게 알리고, 임의 ACL 변경·권한 완화·다른 저장 위치로의 자동 우회를 하지 않는다.

## 로컬 디자인 화면 연결 (3단계)

저장한 설정을 실제 앱 작업으로 이어가는 4단계 절차는 [EXECUTION.md](EXECUTION.md)를 따른다. `prepare`는 지시 생성, `assess`는 보고 대조이며 둘 다 앱 코드를 실행하지 않는다.

1. 이미 정해진 세션을 `resume --session ID`로 최신 조회한다. 명시된 대상이 없거나 여러 세션이면 원래 선택 절차를 따른다. VAS 자체 개발을 사용자 앱 세션으로 등록하지 않는다.
2. Windows 실행 도구가 있으면 `scripts/Start-VAS.ps1 -NoBrowser`를 실행한다. 반환된 `VAS_READY` 주소의 같은 로컬 origin과 인증값을 유지하면서 경로를 `/src/design-controller.html`, 쿼리의 `session`을 실제 세션 ID로 설정한다. URL 도구로 기존 인증 쿼리·fragment를 안전하게 보존하며 임의 포트·토큰·ID를 만들지 않는다. 원본 실행 주소와 토큰은 보고서나 공유 문서에 복사하지 않는다.
3. 브라우저 도구로 연결 화면을 연다. 사용자는 프리셋·토큰·디자인 방향을 고르고 `대화 설정에 저장`을 누른다. 기존 앱은 `preserve`가 기본이며 화면에서 명시적으로 `partial` 또는 `redesign`을 선택한 경우에만 해당 범위를 저장한다. 샘플 사이트의 선택은 저장을 수행하지 않는다.
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
  "questions": ["예약 대상은 사람인가요, 공간인가요?"],
  "nextStep": "예약 대상을 확인하고 현재 원본 구조를 읽는다"
}
```

`sourceType`은 `new` 또는 `existing`이다. 기존 앱은 `designScope.mode: preserve`가 기본이다. `partial`은 변경 범위 필수, `redesign`은 명시된 리디자인에만 사용한다. `new`는 신규 앱에서만 사용한다. 완료조건 method는 `automatic`, `manual`, `static`, required는 JSON boolean이다. 기존 완료조건의 id는 순서에 따라 재계산된다.

앱이 만들어진 뒤 새로운 수정 작업으로 전환되면 현재 요청에 맞춰 `sourceType: existing`과 기본 `preserve`를 함께 저장한다. 이전에 새 앱이었다는 이유로 계속 디자인을 새로 만들지 않는다.

형식·길이·허용 필드를 검사하고 알려진 비밀값·연락처·개인 경로 패턴을 정제한다. 모든 민감정보 탐지를 보장하지 않으므로 저장 전에 비밀값을 넣지 않는다. 완료 상태·검증 통과·사용자 승인 플래그, 명령 이력, 원본 파일 내용은 입력 필드가 아니다.

## 저장 위치와 한계

Windows 기본 위치는 `%LOCALAPPDATA%/VAS/chat-sessions/<VAS 위치 해시>/vas-session-store.json`이다. 다른 OS는 사용자 상태 디렉터리를 사용한다. 테스트의 `--state-home`은 VAS 제품 폴더 밖의 격리 저장소만 허용하며 실제 사용자 저장소 대신 쓰거나 자동 탐색하지 않는다.

공유 가능한 `vas-chat-session` v1 설정과 PC 전용 `binding`을 분리한다. 절대 대상 경로·디렉터리 식별자는 binding에만 있다. `export`는 설정만 출력하며 기존 `VAS-AI-HANDOFF.json` v3를 대체하지 않는다. `resume/create/save/rebind` 출력에는 호스트 작업에 필요한 경로가 있으므로 공유·보고서·저장소에 복사하지 않는다.

설정은 암호화된 비밀 저장소가 아니다. 로컬 사용자 권한을 따른다. 여러 VAS 복사본은 별도 저장소를 사용하며 VAS 자체를 이동하면 이전 설정이 자동 연결되지 않는다. 폴더 식별자 확인은 일반적인 삭제·교체를 감지하는 보조 검사이며 변조 방지 인증이 아니다.

연결된 로컬 화면만 같은 저장소를 사용한다. 독립 HTML·GitHub Pages·샘플 보기에는 대화 설정 저장 기능이 없다. CLI 실행 권한이 없는 읽기 전용 호스트에서는 조회만 하며 저장을 강행하지 않는다. 사용자 안내는 `docs/CHAT-DESIGN.md`에 있다.
