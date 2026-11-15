"""Plain-language recovery hints for the error codes a chat host is most likely to meet.

A hint says what happened and what to do next. It never contains a path, a revision
number or other state: the host must read the current state again before retrying.
"""

_REREAD = "python -B scripts/vas.py start로 현재 상태를 다시 읽고, 거기 나온 값으로 다시 시도하세요."

HINTS = {
    "revision_conflict": "세션이 다른 곳에서 먼저 바뀌었거나, 이미 마감한 판본에 다른 내용을 다시 보냈습니다. " + _REREAD,
    "progress_revision_conflict": "진행 기록이 다른 곳에서 먼저 바뀌었습니다. " + _REREAD,
    "work_revision_conflict": "작업 기록이 다른 곳에서 먼저 바뀌었습니다. " + _REREAD,
    "project_prompt_conflict": "프로젝트 지시가 읽는 사이에 바뀌었습니다. " + _REREAD,
    "shared_progress_conflict": "공유 요약을 다른 호스트가 먼저 썼습니다. " + _REREAD,
    "shared_progress_full": ("공유 요약 한 건이 너무 크거나 기록 수가 한도에 닿았습니다. 요약과 검사 문장을 "
                             "줄여 다시 시도하세요. 기록 수 한도에 닿은 경우 이 버전에는 정리 기능이 없습니다."),
    "execution_result_mismatch": ("보고한 결과가 지금의 준비(prepare) 결과와 짝이 맞지 않습니다. prepare를 다시 "
                                  "실행하고 거기서 나온 payloadSha256을 --prepared-hash로 넘기세요."),
    "finish_invalid_arguments": ("세션 마감에는 --session, --expected-revision, --expected-progress-revision이 함께 "
                                 "필요하고, 결과를 플래그로 보고하면 --prepared-hash도 필요합니다. 작은 수정은 "
                                 "--summary만 쓰세요."),
    "finish_summary_required": "--check, --next-step, --expected-shared-revision은 --summary와 함께 써야 합니다.",
    "finish_input_invalid": "--summary는 비어 있지 않은 글이어야 하고 --check는 10개까지입니다.",
    "finish_check_invalid": "--check는 '이름:상태' 형식입니다. 상태는 통과, 실패, 건너뜀, 미실행(또는 passed, failed, skipped, not-run)입니다.",
    "session_not_found": "그 번호의 세션이 이 PC에 없습니다. " + _REREAD,
    "session_review_required": "저장된 세션이 지금 파일·지시와 달라졌습니다. start가 알려 주는 항목을 대조한 뒤 진행하세요.",
    "memory_conflict": "지금 상태(vas-state/now.md)가 다른 곳에서 먼저 바뀌었습니다. " + _REREAD,
    "memory_criterion_unknown": "그 번호의 완료조건이 지금 상태에 없습니다. vas-state/now.md의 완료조건 번호(C1, C2 …)를 확인하세요.",
    "memory_file_path_invalid": "--file에는 프로젝트 폴더 기준 상대 경로만 씁니다(예: src/index.html).",
    "memory_invalid": "--summary와 찾을 말은 비어 있지 않은 글이어야 합니다. plan에는 바꿀 항목을 하나 이상 주세요.",
    "vas_root_invalid": ("여기는 VAS 프로젝트 폴더가 아닙니다. Run-VAS-System.bat, src, ui가 함께 보이는 폴더에서 "
                         "실행하세요."),
}


def hint_for(code):
    return HINTS.get(code)
