# 위임 결과와 검사 대상 연결

주 실행자가 실제 호스트의 위임·반환 보고와 선택한 파일의 지문을 연결합니다. 사용자가 별도 폼을 작성할 필요는 없습니다. 설정과 진행 요약은 그대로 두고 같은 PC 저장소의 work에 최신 실행 한 건을 보관합니다.

VAS는 명시한 상대 파일만 읽어 크기·SHA-256·존재 여부를 기록합니다. 명령을 실행하거나 앱 파일을 수정하지 않습니다. 실제 호출 ID·상태·검사 결과는 **호스트가 보고한 정보**이며, 지문 일치는 선택한 파일의 특정 시점 내용만 확인합니다. 전체 프로젝트 무변경·테스트 실행·사용자 수용을 인증하지 않습니다.

## 주 실행자의 순서

1. 최신 resume, 원본·지침·실제 검사 명령을 읽고 필요한 설정을 save합니다. prepared 상태의 인계를 확보합니다.
2. work open으로 현재 인계에 연결된 실행 기록을 엽니다. result가 없는 pending 작업이 있으면 덮어쓰기를 거부합니다. timed-out·unreturned로 종결해 저장했어도 실제 호스트 종료 여부는 주 실행자가 확인해야 합니다.
3. 각 구현·위임 직전 work start로 담당 파일과 관찰 파일을 등록합니다. 반환된 unitId를 실제 호스트 호출과 연결합니다. 하위 에이전트에게 세션·인계 정보, 같은 질문·다음 행동, 담당 범위와 역할 전체 지침을 전달합니다.
4. 실제 도구의 호출 ID·반환 상태·변경 파일을 확인한 뒤 work finish로 회수합니다. 시간 초과·취소·미회수도 그대로 기록합니다. VAS가 실제 호스트를 조회·중지했다고 주장하지 않습니다.
5. 구현이 끝난 뒤 **검사 직전에 별도 verification 작업을 start**합니다. 원본에서 확인한 검사 명령을 실제 호스트에서 실행하고, 직후 finish로 종료 코드·조건별 결과를 기록합니다. 구현 전 지문을 검사 직전 지문으로 대신하지 않습니다.
6. work inspect로 현재 파일과 앞뒤 지문을 대조합니다. 범위 위반·검사 중/후 변경·미회수·누락 조건이 있으면 실제 원인에 해당하는 작업만 보완합니다.
7. 결과 v1과 조건별 evidence의 artifactVersion에 inspect에서 확인한 값을 사용해 assess합니다. 실제 결과가 실패했다면 실패 그대로 제출합니다. 일치하는 해시만 붙여 실패를 성공으로 바꾸지 않습니다.
8. 평가를 당시 revision의 결과로 확보하고 최신 resume → checkpoint → 재조회로 요약과 다음 행동을 저장합니다.

에이전트 중 주 실행자만 기록을 씁니다. 사용자가 저장을 원하지 않거나 저장소에 접근할 수 없으면 생성·복원했다고 말하지 않고 실제 확인한 결과를 대화에서 보고합니다.

## 명령과 revision

N은 현재 세션 revision, W는 resume.work.revision입니다. work가 없으면 W=0입니다. 공통 옵션 --state-home·--vas-root는 work 등 하위 명령 **앞**에 둡니다. 아래 명령은 에이전트가 실행하며 ID·N·W·UNIT을 실제 응답으로 바꿉니다.

~~~text
python scripts/vas-session.py work open --session ID --expected-revision N --expected-work-revision W
python scripts/vas-session.py work start --session ID --expected-revision N --expected-work-revision W
python scripts/vas-session.py work finish --session ID --expected-revision N --expected-work-revision W --unit UNIT
python scripts/vas-session.py work inspect --session ID --expected-revision N
~~~

start·finish 입력은 정제한 UTF-8 JSON 표준입력입니다. 원본 대화·코드·로그·개인 경로·인증값을 인수나 임시 JSON에 저장하지 않습니다. 정상 대상의 open·start·finish 응답은 resumed이며 로컬 work 기록을 포함합니다. start의 새 작업 ID는 최상위 unitId입니다. inspect는 inspected를 반환합니다. 대상이 사라진 finish·clear는 저장에 성공해도 target_unavailable로 응답할 수 있으므로 work revision과 반환 보고·삭제 여부를 함께 확인합니다.

open·start·finish는 W만 증가시키고 N은 유지합니다. 설정·진행 요약의 저장은 종전대로 N을 증가시킵니다. 이미 바뀐 N/W로 덮어쓰지 말고 최신 상태를 읽어 차이를 대조합니다. 다른 실행자가 쓴 work를 예전 사본으로 덮어쓰지 않습니다.

실행 기록은 시작 당시 세션·설정·역할 자료·인계·대상 연결에 묶입니다. 이후 설정 변경이나 checkpoint 뒤에도 이전 기록은 그 당시 문맥으로 남습니다. 새 revision으로 고쳐 붙이지 않습니다. 단순 nextStep 변경으로 문맥이 달라졌다는 표시를 앱 파일 변경으로 설명하지 않습니다.

## 작업 시작 입력

다음은 형식 예시이며 실제 대상과 조건으로 바꿉니다. 관찰 파일에는 관련 구현·검사·설정·의존성 파일을 선택합니다. 감시할 범위를 생략한 채 전체 앱을 검사했다고 말하지 않습니다.

~~~json
{
  "kind": "implementation",
  "role": "implementer",
  "mode": "delegated",
  "label": "예약 중복 처리",
  "observedFiles": ["booking.py", "test_booking.py"],
  "writableFiles": ["booking.py"],
  "criterionIds": ["C1"],
  "command": ""
}
~~~

- kind: implementation, review, verification. role: main, implementer, designer, reviewer. mode: direct 또는 delegated.
- label은 비어 있지 않은 200자 이하 문자열입니다. 직접 수행했으면 direct로 기록하며 별도 에이전트를 실행했다고 보고하지 않습니다.
- observedFiles는 명시한 상대 파일 목록입니다. writableFiles는 그중 수정할 수 있는 파일만 지정하며 review·verification과 reviewer 역할은 빈 배열입니다.
- criterionIds는 시작 당시 원래 완료조건 ID입니다. 조건 내용 해시도 연결하므로 재정렬된 C1을 예전 C1과 같은 조건으로 간주하지 않습니다.
- verification은 비어 있지 않은 실제 검사 command와 criterionIds가 필요합니다. command는 500자 이하 참고 문자열이며 VAS가 실행하지 않습니다.
- 일반 역할의 writableFiles·criterionIds·command는 각각 빈 배열·빈 배열·빈 문자열로 생략할 수 있습니다. supersedes는 생략하면 null입니다.

병렬 구현에서는 관찰 범위와 쓰기 담당을 겹치지 않게 나눕니다. 동시에 다른 실행자가 관찰 파일을 바꾸었다면 변경을 감지할 수 있지만 누가 수정했는지는 지문만으로 판단하지 않습니다. 작업을 합친 뒤 검토·검증 작업으로 전체 관련 범위를 다시 관찰합니다.

## 반환 보고

~~~json
{
  "state": "returned",
  "hostCallId": "call_replace_with_observed_id",
  "summary": "예약 중복 검증을 구현했다.",
  "changedFiles": ["booking.py"],
  "exitCode": null,
  "criteria": []
}
~~~

위 ID는 자리표시자입니다. 실제 ID는 영문·숫자로 시작하는 영문·숫자·점·밑줄·콜론·하이픈 160자 이하이며 정제로 변형된 ID는 거부합니다. 실제 호출에 사용했고 호스트가 같은 범위에서 지원하는 상대 작업 이름도 식별자로 사용할 수 있습니다. 이 경우 주 실행자가 원래 호출과 전체 식별자의 대응을 확인합니다. 지원하지 않는 형식은 임의로 자르거나 다른 ID로 바꾸지 않습니다. ID를 만들거나 다른 호출의 ID를 복사하지 않으며 VAS는 이 ID를 호스트에 조회해 인증하지 않습니다.

state는 returned, failed, timed-out, unreturned, cancelled입니다. hostCallId와 비어 있지 않은 summary(1,000자 이하)는 필수입니다. changedFiles는 실제 diff에서 확인한 상대 파일이며 생략하면 빈 배열입니다. 관찰하지 않은 파일까지 변경했다고 보고했다면 해당 내용은 호스트 보고로 구분합니다.

verification의 returned는 종료 코드 0과 할당된 모든 조건의 보고가 필요합니다. 각 조건은 id, status(passed·failed·not-run·unknown), summary(500자 이하)입니다. 구현·검토의 returned는 exitCode null 또는 0을 허용합니다. failed는 0 아닌 정수 또는 null, 시간 초과·미회수·취소는 null입니다. 불리언·문자열 종료 코드는 거부합니다. 실패·미실행을 passed로 기록하지 않습니다.

대상 연결이 바뀌었거나 반환 지문을 읽을 수 없어도 반환 보고는 원래 문맥에 보존하며 afterError로 파일 미확인을 구분합니다. 해당 기록으로 검사 성공이나 현재 파일 일치를 주장하지 않습니다.

## 비교 결과와 재검사

inspect는 조회만 수행합니다. hostReportsVerified=false·complete=false를 유지합니다. artifactVersion은 선택한 파일들의 현재 지문 묶음이며 프로젝트 전체 버전이나 테스트 인증이 아닙니다.

| 항목 | 뜻 |
|---|---|
| contextMatches | 현재 설정·인계·대상 연결과 시작 당시 문맥 일치 |
| observedChangedFiles | 앞뒤 관찰 시점에 실제 달라진 선택 파일 |
| observedOutOfScopeFiles | 선택 파일 중 허용 쓰기 범위 밖에서 관찰한 변경 |
| reportedOutOfScopeFiles | 호스트가 보고한 변경 중 허용 범위를 벗어난 파일 |
| changedSinceReturn | 반환 직후와 현재 관찰에서 내용·존재 여부가 달라진 파일 |
| sampleMatches | 검증·검토의 전후/현재 표본 일치. 실제 명령 실행이나 사용자 확인의 증거 아님 |
| coveredCriteria·missingCriteria | 재사용 가능한 표본과 호스트 통과 보고로 연결한 자동 조건, 누락된 필수 자동 조건 |

검사 실패·미회수·시간 초과·범위 밖 변경·검사 중/후 파일 변경·조건 미확인을 별도 이유로 표시합니다. work가 있는 assess는 이 결과와 제출한 artifactVersion도 대조합니다. 불일치나 미해결 이유가 있으면 incomplete이며, 표본이 일치해도 사용자 직접 확인 없는 보고를 complete로 승격하지 않습니다. work가 없는 이전 세션의 평가 경로는 유지합니다.

관련 검사만 다시 할 때는 기존 호스트 작업의 반환·종료를 실제로 확인한 뒤, 같은 kind·role·mode·관찰/쓰기 범위·조건·명령을 사용해 새 start의 supersedes에 앞선 unitId를 지정합니다. 새 직전 지문을 확보하고 실제 검사를 다시 합니다. 이전 보고는 남고 최신 후속 작업을 검사 재사용 대상으로 봅니다. 다만 과거의 관찰·보고된 범위 밖 변경은 historical=true로 계속 표시하여 재시도가 이를 해결한 것처럼 보이지 않게 합니다. 실제 변경을 검토·정리한 뒤 모든 작업이 반환된 실행을 명시적으로 새 open으로 교체할 수 있습니다. 완료 보고의 해시·ID만 바꿔 재검사로 만들지 않습니다.

## 제한과 삭제

최신 실행 기록 1건에 최대 12작업·20조건·합쳐서 64개 관찰 파일을 둡니다. 기록은 128 KiB, 파일 읽기는 파일당 1 MiB·한 번에 합계 16 MiB 이내입니다. 기존 전체 저장소 2 MiB·64세션 제한도 적용합니다. 한도를 넘으면 기존 상태를 보존하고 범위를 다시 나눕니다.

파일은 디렉터리 탐색·glob 없이 상대 경로로 명시합니다. 절대경로·상위 이동·예약 이름·링크·하드링크·특수 파일·민감 경로는 거부합니다. 없는 파일도 기록하여 생성·삭제를 비교합니다. 파일 본문은 저장하지 않으며 앱 파일을 잠그지 않습니다. 관찰 사이에 바뀌었다가 같은 내용으로 돌아온 변경이나 관찰하지 않은 파일은 이 방식으로 알 수 없습니다.

work는 웹 응답·공유 export·prepare 인계에 자동 편입되지 않습니다. resume의 로컬 기록과 필요한 부분만 위임합니다. 진행 요약의 referenceOnly=true·filesVerified=false는 유지합니다.

사용자가 실행 기록만 지우라고 요청하면 work clear에 최신 N/W를 전달합니다. 실제 삭제 시 N을 1 올리고 설정·진행 요약을 보존합니다. 기록이 손상되어 revision을 읽을 수 없으면 본문을 숨기며, 명시적 삭제에만 W=-1을 사용합니다. 손상된 기록을 자동 삭제·덮어쓰지 않습니다.

~~~text
python scripts/vas-session.py work clear --session ID --expected-revision N --expected-work-revision W
python scripts/vas-session.py forget --session ID --expected-revision N --expected-work-revision W
~~~

전체 세션 삭제는 실행 기록도 함께 지웁니다. work가 있는 세션의 forget에는 W가 필수이며 동시 반환으로 바뀐 기록을 오래된 삭제 요청이 지우지 않도록 검사합니다. work가 없는 이전 세션은 기존 forget 명령을 그대로 사용할 수 있습니다. 앱 파일이나 OS 백업을 삭제하는 명령은 아닙니다.

관련 절차: [구현과 검증](CHAT-EXECUTION.md), [진행 요약](CHAT-PROGRESS.md), [주 실행자 지침](../.agents/EXECUTION.md).
