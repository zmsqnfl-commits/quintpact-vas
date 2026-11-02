"""Read a compact, local resume view; starting a conversation never mutates the project."""
import os
from pathlib import Path

from vas_project_layout import is_project_engine
from vas_project_prompt import read_project_prompt, read_project_start
from vas_portable_progress import read_shared_progress
from vas_session import SessionManager, require
from vas_session_store import SessionStoreError


CLI = "python -B scripts/vas-session.py"


def _brief(text, limit=240):
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _initial_action(state, shared):
    question = ("누가 어떤 일에 쓸 새 앱이고 첫 기능은 무엇인가요?" if state == "empty" else
                "현재 앱에서 어떤 동작을 바꾸고 싶나요?")
    action = {
        "code": "review-shared" if shared else "clarify-scope",
        "message": ("다른 호스트의 요약을 현재 파일과 대조하세요. " if shared else "") +
                   "대화·저장 지시에서 이미 정한 내용은 묻지 마세요. 이전 앱이 언급됐고 이전 여부만 "
                   "미정이면 새로 만들지 그 앱을 이어갈지만 물으세요.",
        "questionIfNeeded": question, "sessionCommand": CLI + " create --target .",
        "when": "여러 단계로 이어갈 작업의 범위·완료조건이 합의되고 구현을 요청받은 뒤에만 세션 생성",
        "lightweight": "이미 합의한 작은 문구·스타일 수정은 앱을 고치고 확인한 뒤 quick finish로 기록하세요.",
        "stdin": "합의한 project와 task를 담은 설정 JSON",
    }
    return action


def _resume_action(view, prompt_revision, shared_revision):
    require(view["status"] == "resumed", "target_unavailable")
    doc = view["session"]
    sid, revision, settings = doc["sessionId"], doc["revision"], doc["settings"]
    session = {"status": "resumed", "sessionId": sid, "revision": revision,
               "request": _brief(settings["task"]["request"]), "nextStep": _brief(settings["nextStep"]),
               "readCommand": f"{CLI} resume --session {sid}"}
    for key in ("progress", "work"):
        if key in view:
            record = view[key]
            require(record["status"] != "invalid", "session_" + key + "_invalid")
            session[key] = {"status": record["status"], "revision": record["revision"]}
    if "progress" in session:
        summary = view["progress"]["record"]["summary"]
        session["progress"].update(phase=summary["phase"], summary=_brief(summary["summary"]))
    args = f"--session {sid} --expected-revision {revision}"
    command = f"{CLI} prepare {args}"
    action = {"code": "resume", "command": command,
              "message": "현재 대화·앱·공유 요약을 로컬 기록과 대조하세요. 여러 단계로 이어갈 구현은 편집 전에 준비 결과를 확인하세요.",
              "when": "세션 기반의 구현을 요청받은 경우",
              "lightweight": "합의한 한 파일의 작은 수정은 실제 검사 후 quick finish로 남길 수 있습니다."}
    needs_review = bool(view.get("reviewFields")) or any(view.get(k, {}).get("status") == "stale"
                                                          for k in ("progress", "work"))
    blockers = settings.get("blockingQuestions", [])
    if needs_review:
        action.update(code="review-session", message="이전 기록이 달라졌습니다. 현재 파일과 지시를 대조하세요.",
                      command=session["readCommand"])
    elif blockers:
        action.update(code="resolve-blockers", message="대화에서 이미 답한 내용은 반영하고 필요한 질문만 하세요.",
                      questionIfNeeded=_brief(blockers[0]), command=session["readCommand"],
                      sessionCommand=f"{CLI} save {args}",
                      when="미정 사항이 해결된 뒤", stdin="현재 합의로 갱신한 전체 설정 JSON")
    progress_revision = session.get("progress", {}).get("revision", 0)
    action["finishCommand"] = (
        f"python -B scripts/vas.py finish {args} --expected-progress-revision {progress_revision} "
        f"--expected-project-prompt-revision {prompt_revision} --expected-shared-revision {shared_revision}")
    action["finishStdin"] = "실제 검사 뒤 progress 및 result를 담은 JSON. 설정 변경 후 start를 다시 실행하세요."
    return session, action


def start(root, state_home=None):
    root = Path(root)
    require(".." not in root.parts, "vas_root_invalid")
    root = Path(os.path.abspath(root))
    require(root.name.casefold() != ".vas" and is_project_engine(root), "vas_root_invalid")
    prompt, state = read_project_start(root)
    shared = read_shared_progress(root)
    prompt_brief = dict(prompt)
    if len(prompt["prompt"]) > 500:
        prompt_brief.update(prompt=_brief(prompt["prompt"], 500), truncated=True,
                            readCommand="python -B scripts/vas-project-prompt.py get")
    result = {"status": "ok", "app": {"directory": "src", "state": state,
                                       "interpretation": "새 앱 자리" if state == "empty" else "기존 항목을 확인하세요"},
              "projectPrompt": prompt_brief, "sharedProgress": shared}
    try:
        manager = SessionManager(root, state_home)
        require(manager.root == manager.project_root, "vas_root_invalid")
        view = manager.resume(target=manager.root, allow_empty=True)
    except SessionStoreError as error:
        return dict(result, status="partial", code=error.code, session={"status": "unavailable"},
                    nextAction={"code": "review-local-state", "command": "python -B scripts/vas.py start",
                                "message": "PC 세션 조회가 막혔습니다. 공유 요약과 현재 앱·대화를 대조해 진행하고 "
                                           "실제 검사는 quick finish로 남기세요. PC 저장소를 복구하면 다시 조회하세요."})
    if view["status"] == "empty":
        result.update(session={"status": "none"}, nextAction=_initial_action(state, shared))
    else:
        session, action = _resume_action(view, prompt["revision"], shared["revision"] if shared else 0)
        result.update(session=session, nextAction=action)
    require(read_project_prompt(root) == prompt, "project_prompt_conflict")
    return result
