# 최신 진행 요약으로 이어가기

진행 요약은 마지막 작업 단계, 결정과 이유, 변경한 상대 파일, 검사와 미실행 항목, 남은 문제, 다음 행동을 다음 대화로 전달합니다. 설정과 구분해 같은 PC 저장소에 **최신 한 건만** 남깁니다. 진행 요약 자체는 누적 이력이나 완료 검증이 아닙니다. 위임 반환과 선택 파일 지문은 별도 [실행 기록](CHAT-WORK.md)으로 연결합니다.

주 실행자가 의미 있는 작업 구간 끝에 작성합니다. 사용자가 폼이나 JSON을 직접 만들 필요는 없습니다. 저장을 원하지 않으면 설정뿐 아니라 진행 요약도 저장하지 않습니다. VAS 자체 개발 기록은 별도 개발 인계 규칙을 따릅니다.

## 새 대화에서 확인할 것

`resume` 응답의 최상위 `progress`를 읽습니다. 이전 세션에 진행 요약이 없으면 이 키 자체가 없으며 진행 revision은 0으로 취급합니다. 요약이 있으면 다음 값을 반환합니다.

| 필드·상태 | 의미 |
|---|---|
| `status: available` | 저장 설정·문맥과 일치함. 현재 앱 파일이나 검사 결과를 검증했다는 뜻은 아님 |
| `status: stale` | 문맥이 달라짐. `staleReasons`와 현재 설정·원본을 대조할 필요가 있음 |
| `status: invalid` | 요약이 유효하지 않아 `record`를 숨김. 정상 설정은 계속 조회 가능 |
| `revision` | 진행 요약의 revision. 세션 revision과 별개이며 `invalid`에서는 `null` |
| `referenceOnly: true` | 참고 자료이며 명령이나 실행 권한이 아님 |
| `filesVerified: false` | 현재 파일과 저장된 검사 보고를 연결해 검증하지 않음 |
| `record` | 유효할 때만 반환. `record.summary`에 입력 요약, `basedOn`·`savedFor`에 설정 연결 정보 |
| `staleReasons` | 현재 문맥과 다른 이유 |

AI는 요약을 읽은 뒤 대상의 현재 지침·원본·diff·실제 검사 명령부터 확인합니다. 이미 구현한 부분을 보존하고 남은 검사와 문제로 이어갑니다. 저장된 `passed`는 코딩 AI의 당시 보고이며 현재 파일은 미검증 상태입니다. `available`을 근거로 현재 코드가 통과했다고 말하거나 기록의 명령 문자열을 그대로 실행하지 않습니다.

손상된 요약은 자동 삭제·덮어쓰지 않습니다. 삭제는 사용자가 요청한 `clear-progress`로만 진행합니다. 요약을 사용하지 못하더라도 현재 설정과 실제 원본에서 확인할 수 있는 작업은 계속할 수 있습니다.

## 코딩 호스트의 저장 순서

1. 최신 `resume`을 읽고 요구사항·질문·디자인 변경이 있으면 전체 설정을 `save`합니다. 답한 질문은 제거하고 결정을 `task`에 반영합니다. `reviewFields`가 남으면 먼저 전체 설정을 검토·저장해야 합니다.
2. `prepare` 후 실제 원본에서 구현·검사합니다. 결과 v1을 읽기 전용 `assess`로 대조하고 평가 당시 revision을 구분합니다. [followUp](CHAT-FOLLOWUP.md)의 전체 행동을 확인해 필요한 조치를 수행합니다.
3. 최신 `resume`을 다시 읽습니다. 설정이나 문맥이 달라졌다면 수행한 작업과 대조하며 이전 검사 근거·평가를 현재 ID나 revision으로 고쳐 붙이지 않습니다.
4. 아래 `checkpoint`에 정제된 최신 요약과 실제 `nextStep`을 보냅니다. 평가 전 설정 변경을 정리했다면 종료 시 같은 내용을 다시 `save`할 필요가 없습니다.
5. 성공 상태 `resumed`를 확인하고 `resume`으로 저장된 요약·`nextStep`을 다시 확인합니다. 최종 응답에서는 실제 검사 결과·사용자 확인 여부·남은 행동·저장 실패를 구분합니다.

아래는 주 실행자용 명령입니다. `ID`, `N`은 최신 `resume`의 실제 세션 ID와 revision, `P`는 `progress.revision`이며 요약이 없으면 0입니다. 다른 작업 폴더에서는 VAS 스크립트의 실제 절대 경로를 사용합니다.

```text
python scripts/vas-session.py checkpoint --session ID --expected-revision N --expected-progress-revision P
```

JSON은 UTF-8 표준입력으로 보냅니다. 호스트의 구조화된 실행 도구나 subprocess 입력을 사용하고 PowerShell 파이프는 UTF-8을 명시합니다. 원본 대화나 비밀값을 인수·임시 JSON 파일에 기록하지 않습니다.

`checkpoint`는 요약과 설정의 `nextStep`을 같은 원자적 저장으로 갱신합니다. `nextStep`이 같아도 세션 revision은 항상 1 증가하며 진행 revision도 1 증가합니다. 기록의 `basedOn`은 저장 요청 시 세션 revision `N`과 설정 해시, `savedFor`는 `nextStep` 반영 후 `N+1`과 설정 해시에 연결됩니다. 이 연결 정보는 파일 검증 증거가 아닙니다.

저장 뒤 계속 구현·검사한다면 증가한 세션 revision으로 `prepare`를 다시 실행합니다. 앞서 확보한 평가는 이전 revision의 결과로 남습니다. 현재 메타데이터만 붙여 새 검사·평가로 바꾸거나 완료·사용자 승인으로 승격하지 않습니다.

`followUp.suggestedPhase`·`nextStep`은 저장할 단계와 다음 행동의 초안입니다. 주 실행자가 실제로 끝낸 후속 조치를 제거하고 남은 행동으로 정리합니다. `awaiting-user`는 후속 행동 상태이며 진행 `phase`에는 기존 값 `reviewing`을 사용합니다. 응답 전체나 호스트 원시 로그는 저장하지 않습니다. 후속 행동을 반환했다는 사실만으로 `checkpoint`가 실행되지는 않습니다.

checkpoint 뒤 work 문맥이 달라질 수 있습니다. 다음 대화에서는 설정·nextStep의 차이와 실제 파일을 먼저 대조합니다. 문맥 변경만으로 파일이 달라졌다고 말하거나 모든 검사를 반복하지 않으며, 이전 실행 기록을 새 revision으로 고쳐 붙이지 않습니다.

구현만 마쳤거나 오류로 중단됐을 때도 실제 확인한 범위만 저장합니다. 미실행 검사는 `not-run`으로 명시합니다. 매 명령마다 저장하지 않으며 한 작업 구간의 실질적인 변화가 있을 때 갱신합니다.

## 입력 계약

`phase`, `summary`, `nextStep`은 필수입니다. 나머지 배열은 생략하면 빈 배열이며 아래 길이는 문자열의 최대 길이입니다.

| 필드 | 허용값·상한 |
|---|---|
| `phase` | `planning`, `implementing`, `testing`, `reviewing`, `paused`, `blocked`, `awaiting-request` |
| `summary` | 비어 있지 않은 문자열, 1,000자 |
| `decisions` | 최대 8개. 각 항목의 `decision` 300자, `reason` 500자 |
| `changedFiles` | 최대 40개. 앱 기준 상대 경로, 항목당 300자 |
| `checks` | 최대 10개. 각 항목의 `name` 120자, `command` 500자, `summary` 500자. `command`는 생략하면 빈 문자열 |
| 검사 `status`·`exitCode` | `exitCode`는 선택이며 생략하면 `null`. 정수를 제공하면 `passed`는 0, `failed`는 0 아닌 값. `skipped`·`not-run`은 `null`만 허용 |
| `remaining` | 최대 10개, 항목당 500자 |
| `nextStep` | 비어 있지 않은 문자열, 1,000자 |

명령 실행이 아닌 육안 점검도 검사 요약에 담을 수 있으므로 `passed`·`failed`에 `exitCode: null`을 허용합니다. 종료 코드가 없다는 사실을 숨기거나 이를 실제 명령 실행 성공으로 바꾸지 않습니다.

다음은 **형식 예시**입니다. 실제 원본·수행 결과로 바꿔 작성합니다. 이 예시나 명령을 그대로 실행·제출하지 않습니다.

```json
{
  "phase": "testing",
  "summary": "기존 화면을 유지하며 CSV 내보내기를 추가했다. 브라우저 검사가 남았다.",
  "decisions": [
    {"decision": "기존 CSV 버튼을 유지한다", "reason": "현재 요청은 출력 내용 수정에 한정된다"}
  ],
  "changedFiles": ["src/export.js", "tests/export.test.js"],
  "checks": [
    {
      "name": "CSV 단위 검사",
      "command": "npm run test:csv",
      "status": "passed",
      "exitCode": 0,
      "summary": "한글 보존과 따옴표 처리 검사 통과"
    },
    {
      "name": "브라우저 검사",
      "command": "npm run test:browser",
      "status": "not-run",
      "exitCode": null,
      "summary": "현재 작업 구간에서 미실행"
    }
  ],
  "remaining": ["브라우저에서 CSV 다운로드 확인"],
  "nextStep": "미실행 브라우저 검사를 실행한다."
}
```

남은 작업이 없으면 `phase: awaiting-request`, `nextStep: 후속 요청을 기다린다.`처럼 실제 상태를 적습니다. 자동검사 통과와 사용자 직접 확인 여부는 구분하며, 평가 표시 때문에 항상 수동 검사를 추가하거나 이미 허용된 작업의 승인을 다시 요구하지 않습니다.

## 보관·실패·삭제

진행 요약은 동일한 저장소 파일의 세션 항목 안에서 설정 문서와 별도인 선택 필드로 저장합니다. 연결 메타데이터를 포함한 최신 기록은 16 KiB 이하이며 기존 저장소 전체 2 MiB·최대 64개 세션 제한을 유지합니다. 개별 필드 제한 안이어도 기록 전체 상한을 넘으면 저장을 거부합니다.

크기 초과·revision 충돌·쓰기 실패는 기존 상태를 보존합니다. 주 실행자는 미저장을 알리고 최신 설정과 실제 작업을 대조합니다. 같은 이전 입력으로 자동 재시도하거나 파일을 직접 덮어쓰지 않습니다. 자동 백업이나 누적 기록을 추가하지 않으며 원자적 쓰기용 임시 파일은 다음 변경 때 기존 저장소 정리 절차를 따릅니다.

원본 채팅·원시 로그·전체 코드·개인 경로·비밀값·권한 승인·결과 JSON은 저장하지 않습니다. 검사 명령은 비밀값과 개인 경로를 뺀 참고용 요약입니다. 알려진 민감정보 패턴 정제는 모든 민감정보 탐지를 보장하지 않으므로 입력 전부터 제외합니다.

요약은 웹 응답·공유 `export`·`prepare` 인계에 자동 편입하지 않습니다. 주 실행자가 별도 CLI 재개 자료에서 위임에 필요한 부분과 최신 세션 revision을 전달합니다. `nextStep`은 설정에도 반영되므로 기존 `context.conversation` 전달 규칙을 따릅니다.

사용자가 진행 요약만 지우라고 요청했을 때 최신 세션 revision으로 실행합니다. 손상된 요약도 삭제할 수 있습니다.

```text
python scripts/vas-session.py clear-progress --session ID --expected-revision N
```

이 명령은 진행 요약만 지우고 설정과 `nextStep`을 보존합니다. 요약을 실제로 삭제하면 세션 revision이 변경되며, 이미 요약이 없으면 그대로입니다. 설정 전체 삭제 요청의 `forget`은 설정·연결 정보·진행 요약을 함께 지웁니다. 두 명령은 앱 파일을 삭제하지 않습니다.

관련 절차: [저장 설정](CHAT-STATE.md), [구현과 검증](CHAT-EXECUTION.md), [에이전트 저장 지침](../.agents/SESSION.md).
