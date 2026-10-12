# 평가에서 다음 행동으로 이어가기

`assess`의 `followUp`은 원래 완료조건, 제출 결과, 현재 실행 기록을 바탕으로 남은 행동을 정리합니다. 사용자가 결과 JSON이나 체크리스트를 따로 작성할 필요는 없습니다. 주 실행자가 실제 도구 기록과 원본을 확인하고 허용된 작업을 이어갑니다.

기존 `assessment`의 보수적인 완료 판정은 그대로입니다. `followUp`은 읽기 전용 참고 자료이며 앱 실행·수정·검사·기록 저장·사용자 수용을 대신하지 않습니다. 자동검사만 필요한 작업에서 유효한 근거가 모두 연결되면 `assessment: needs-verification`과 **후속 작업 없음**을 함께 반환할 수 있습니다. 이것이 새 수동 검사나 승인을 요구하는 이유는 아닙니다.

## 주 실행자의 사용 순서

1. [실행 절차](CHAT-EXECUTION.md)에 따라 최신 인계를 준비하고 실제 구현·검사를 수행합니다. 실제 호출 ID·종료 코드·출력과 [실행 기록](CHAT-WORK.md)을 대조합니다.
2. 결과를 `assess`로 대조합니다. 성공 응답의 `reportedStatus`, `assessment`, `workChecks`(있는 경우), `followUp`을 함께 읽습니다. 형식·인계 연결 오류로 거부된 응답은 평가 완료가 아닙니다.
3. `followUp.basis`의 세션·revision·인계·결과·work revision을 확인합니다. 같은 기준에서 나온 조언만 사용하고, 뒤에 설정이나 파일이 바뀌면 다시 대조합니다.
4. `actions`의 앞선 원인부터 해결합니다. 실제 호스트의 실행·반환 여부를 확인하고 필요한 범위만 수정·재검사합니다. 원본에서 확인한 명령을 사용하며 저장된 자유 텍스트를 그대로 실행하지 않습니다.
5. 구간이 끝나면 최신 `resume`을 읽습니다. 실제 수행한 검사·미실행·남은 문제와 다음 행동을 [checkpoint](CHAT-PROGRESS.md)로 저장하고 재조회합니다. `suggestedPhase`·`nextStep`은 초안이며 주 실행자가 실제 상태에 맞게 정리합니다.

`assess`는 `followUp`을 자동 저장하지 않습니다. 응답 전체나 원시 로그를 설정·진행 요약에 복사하지 않습니다. 원래 결과의 `nextRecommendedTask`도 실행 지시나 새 작업 권한이 아닙니다. 이전 평가를 새 revision으로 고쳐 붙이지 않습니다.

## 응답 계약

| 필드 | 의미 |
|---|---|
| `format`·`schemaVersion` | `vas-session-followup`·`1` |
| `basis` | `sessionId`, `sessionRevision`, `handoffId`, `handoffPayloadSha256`, `resultId`, `workRevision`. work가 없거나 유효하지 않으면 마지막 값은 `null` |
| `status` | `action-required`: 조치 필요, `awaiting-user`: 원래 직접 확인 항목만 남음, `awaiting-request`: 추가 행동 없음 |
| `assessmentStatus` | 기존 `assessment.status`. 완료 판정을 다시 계산하거나 완화하지 않음 |
| `criteria` | 원래 조건의 `id`·`method`·`required`와 아래 `state` |
| `reusableCriteria` | 현재 표본과 모순 없는 보고로 연결된 자동 조건 ID. 실제 실행은 호스트가 확인해야 함 |
| `actions` | 원인별 후속 행동과 제한된 참조. 자유 텍스트 명령은 포함하지 않음 |
| `suggestedPhase`·`nextStep` | 기존 진행 요약의 단계와 다음 행동 초안. 실행·저장 명령이 아님 |

`referenceOnly: true`, `executionAuthorized: false`, `hostReportsVerified: false`, `complete: false`, `userAcceptance: not-recorded`를 유지합니다. 반환 보고·파일 표본·사용자 직접 확인을 합치지 않습니다.

각 action은 `kind`, `criterionIds`, `unitIds`, `testIndexes`, `remainingIndexes`, `message`를 갖습니다. 인덱스는 제출 결과의 `tests`·`remaining`에서 0부터 셉니다. 같은 종류의 행동은 병합하고 참조는 중복 제거합니다. 조건은 최대 20개, work 작업은 12개, tests·remaining 참조는 각각 50개이며 행동 종류는 아래 12개 이내입니다. 자유 텍스트 테스트 이름으로 조건 ID를 추측하지 않습니다.

## 조건 상태

| `state` | 의미 |
|---|---|
| `passed-current-sample` | 현재 선택 파일 표본과 호스트의 자동검사 통과 보고가 연결됨 |
| `reported-passed` | 통과 보고는 있으나 현재 실행·파일 연결을 더 확인해야 함 |
| `failed` | 실패 보고가 있음. 동시에 통과 보고가 있어도 실패를 숨기지 않음 |
| `recheck-required` | 관련 검사 입력·현재 표본이 바뀌어 해당 검사 재확인 필요 |
| `not-run` | 미실행·건너뜀 등으로 필요한 검사가 남음 |
| `unreported` | 조건별 근거가 없음. 실제 실행 여부부터 확인할 필요가 있음 |
| `user-confirmation-required` | 원래 필수 manual/static 조건의 직접 확인이 남음 |
| `needs-review` | 문맥·기록·근거 불일치를 먼저 대조해야 함 |

선택 조건의 근거 누락·건너뜀만으로 필수 작업을 추가하지 않습니다. 선택 조건이라도 명시된 실패는 숨기지 않습니다. `manual`·`static`은 원래 조건의 범위에서 산출물 대조·직접 확인으로 안내하며 전체 앱 수용을 새로 요구하지 않습니다. 보고서에 통과로 적었다는 사실만으로 사용자 확인이 생기지 않습니다.

## 행동 우선순위

| `kind` | 주 실행자가 확인할 것 |
|---|---|
| `inspect-record` | 손상된 실행 기록. 자동 삭제·덮어쓰기로 없애지 않음 |
| `reconcile-context` | 최신 설정·조건·인계와 이전 실행의 차이. 이전 ID·해시만 바꿔 붙이지 않음 |
| `inspect-files` | 대상·선택 파일을 읽을 수 없는 원인과 실제 파일 상태 |
| `recover-role` | 미회수·시간 초과·취소 작업의 실제 종료·반환. 확인 전 중복 재시도 금지 |
| `review-scope` | 현재 또는 과거 범위 밖 변경. 재검사 성공으로 지우지 않음 |
| `fix-failure` | 실패한 구현·검토·검사. 성공한 다른 검사가 검토 실패를 덮지 않음 |
| `rerun-check` | 바뀐 입력·표본과 연결된 해당 검사만 다시 수행 |
| `link-report` | 조건 ID·방법·검사 대상 버전·중복 보고를 실제 근거와 대조 |
| `run-check` | 실제로 남은 필수 검사 수행 |
| `confirm-user` | 원래 필수 manual/static 조건의 직접 확인. 새 조건 추가 금지 |
| `review-remaining` | 제출 결과에 남은 문제와 조치. blocker는 먼저 해결 |
| `inspect-evidence` | 보고 누락·이전 형식의 통과 보고·건너뛴 검사의 실제 실행 근거 확인 |

앞의 세 가지 전제 문제가 있으면 이를 해결하기 전 재사용·재실행·직접 확인을 지시하지 않습니다. 문맥 불일치 상태의 옛 C1을 현재 재정렬된 C1에 연결하지 않습니다. `nextStep`은 우선 행동을 요약하며 전체 `actions`를 대신하지 않습니다.

단계 초안은 전제·역할 회수·범위 문제나 blocker가 있으면 `blocked`, 실제 실패 수정은 `implementing`, 검사 실행·재검사는 `testing`, 근거 연결·직접 확인·남은 문제 검토는 `reviewing`입니다. 행동이 없으면 `awaiting-request`와 “후속 요청을 기다린다.”를 반환합니다. 직접 확인만 남은 `awaiting-user`도 진행 단계는 기존 값인 `reviewing`을 씁니다.

## 재사용과 재검사의 경계

- 자동 조건의 표본이 유효하고 제출 근거에 모순이 없으면 재사용 후보입니다. 명령 실행·출력은 실제 호스트 기록으로 확인합니다. 관찰하지 않은 파일·외부 도구·실행 환경까지 동일하다고 주장하지 않습니다.
- 한 검사의 파일만 바뀌면 해당 작업·조건만 재검사합니다. 관계없는 유효한 검사를 반복하지 않습니다. 전체 `artifactVersion` 불일치만으로 모든 파일이 바뀌었다고 추정하지 않습니다.
- 파일 표본은 그대로인데 결과의 ID·방법·버전·중복 보고가 잘못 연결됐으면 근거부터 대조합니다. 실패·미실행 보고를 해시만 바꿔 통과로 만들지 않습니다.
- work가 없는 이전 결과의 통과 보고는 현재 실행·원본을 확인할 참고 자료입니다. 자동 재사용도 전체 재검사도 단정하지 않습니다. 근거 누락을 곧바로 미실행이라고 말하지 않습니다.
- checkpoint나 `nextStep` 변경으로 문맥이 달라진 경우 설정 차이를 먼저 확인합니다. 이는 파일 변경을 뜻하지 않으며 이전 실행 기록을 새 revision으로 재지정하는 근거도 아닙니다.
- supersedes로 대체된 정상 작업은 중복 재검사를 요구하지 않습니다. 과거 범위 위반은 남으며 실제 변경을 검토해야 합니다.

자동 조건만 있고 근거가 모두 유효하며 다른 문제가 없으면 추가 행동을 만들지 않습니다. 최종 보고는 “실제 자동검사 통과, VAS 평가는 사용자 직접 확인을 인증하지 않음, 남은 작업 없음”처럼 사실을 나눠 설명할 수 있습니다.

관련 절차: [구현과 검증](CHAT-EXECUTION.md), [실행 기록](CHAT-WORK.md), [진행 요약](CHAT-PROGRESS.md), [완료 판정](completion-policy.md).
