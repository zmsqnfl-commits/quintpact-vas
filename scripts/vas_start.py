"""Read a compact, local resume view; starting a conversation never mutates the project."""
import os
from pathlib import Path

from vas_project_layout import is_project_engine
from vas_memory import read_memory
from vas_project_prompt import read_project_prompt, read_project_start
from vas_portable_progress import MAX_SLOTS, read_shared_progress
from vas_session import SessionManager, require
from vas_session_store import SessionStoreError


CLI = "python -B scripts/vas-session.py"


def _brief(text, limit=240):
    return text if len(text) <= limit else text[:limit - 1] + "…"


PLAN = 'python -B scripts/vas.py plan --request "요청" --criterion "끝났다고 볼 조건 (확인 방법)"'
DONE = 'python -B scripts/vas.py done --summary "한 일" --check "확인한 것:통과" --file src/바뀐파일 --next-step "다음 할 일"'


def _initial_action(state, shared, memory=None):
    question = ("누가 어떤 일에 쓸 새 앱이고 첫 기능은 무엇인가요?" if state == "empty" else
                "현재 앱에서 어떤 동작을 바꾸고 싶나요?")
    remembered = bool(memory and memory.get("status") == "available")
    action = {
        "code": "continue" if remembered else "review-shared" if shared else "clarify-scope",
        "message": ("프로젝트 기억의 지금 상태와 다음 할 일부터 이어가세요. 이미 정한 것은 다시 묻지 마세요. "
                    if remembered else "") +
                   ("이전 버전이 남긴 공유 요약이 있습니다(간단 마감만 썼거나, 다른 PC·호스트에서 "
                    "작업했거나, 폴더 이름·위치가 바뀐 경우). 요약을 현재 파일과 대조해 이어가세요. "
                    if shared and not remembered else "") +
                   "대화·저장 지시에서 이미 정한 내용은 묻지 마세요. 이전 앱이 언급됐고 이전 여부만 "
                   "미정이면 새로 만들지 그 앱을 이어갈지만 물으세요.",
        "questionIfNeeded": question,
        "designQuestion": "화면이 있는 새 작업이고 디자인이 정해지지 않았으면 만들기 전에 한 번만 묻고 답을 기다리세요: "
                          "원하는 디자인이나 참고할 사이트·이미지가 있으면 알려 주세요. 없으면 제가 정해서 진행하겠습니다.",
        "planCommand": PLAN, "doneCommand": DONE,
        "when": "범위와 끝났다고 볼 조건이 정해지면 plan으로 적고, 작업을 마치거나 멈출 때 done으로 남기세요",
        "withoutPython": "Python을 쓸 수 없으면 .agents/MEMORY.md의 양식대로 vas-state의 파일을 직접 읽고 쓰세요.",
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
    action["finishAfterPrepare"] = (
        "작업 전 prepare의 finishArguments를 보관하세요. 작업 뒤 그 인자에 요약·실제 검사·조건별 결과를 "
        "붙여 한 번 전달합니다. 설정 변경 후 start를 다시 실행하세요.")
    action["finishStdin"] = "직접 작성한 v1 보고서가 있는 경우에만 finishCommand에 progress 및 result JSON을 전달합니다."
    return session, action


def shared_brief(record):
    if record is None:
        return None
    result = dict(record)
    result["summary"] = _brief(record["summary"], 240)
    result["nextStep"] = _brief(record["nextStep"], 240)
    result["checks"] = record["checks"][:4]
    for key in ("decisions", "remaining"):
        if key in record:
            result[key] = [_brief(item, 120) for item in record[key][:2]]
    if "scope" in record:
        scope = record["scope"]
        result["scope"] = {"objective": _brief(scope["objective"], 240),
                           "criteria": [_brief(item, 120) for item in scope["criteria"][:3]]}
    if result != record:
        result["truncated"] = True
        if "markdownPath" not in result:
            result["readCommand"] = "python -B scripts/vas-project-prompt.py progress"
    if record.get("revision", 0) >= MAX_SLOTS * 9 // 10:
        result["capacityWarning"] = (f"공유 요약이 {record['revision']}/{MAX_SLOTS}건입니다. "
                                     "한도에 닿으면 더 기록할 수 없습니다.")
    return result


def memory_brief(root):
    """What the project folder itself remembers, short enough to read every time."""
    view = read_memory(root, limit=5)
    if view["status"] == "empty":
        return {"status": "empty", "message": "프로젝트 기억이 아직 없습니다. 범위가 정해지면 plan으로 적으세요."}
    brief = {"status": "available", "recordCount": view["recordCount"],
             "message": "지금 상태를 읽고, 기록은 요청과 관련 있는 것만 골라 여세요."}
    if view["now"]:
        sections = {name: _brief(text, 300) for name, text in view["now"]["sections"].items()
                    if text and text != "(없음)"}
        brief["now"] = {"revision": view["now"]["revision"], "path": view["now"]["path"], "sections": sections}
    if view["records"]:
        brief["recent"] = [f"{item['number']:04d} {item['date']} {item['title']}: {_brief(item['summary'], 120)}"
                           for item in view["records"]]
        brief["indexPath"] = view["indexPath"]
    return brief


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
              "projectPrompt": prompt_brief, "sharedProgress": shared_brief(shared),
              "memory": memory_brief(root)}
    try:
        manager = SessionManager(root, state_home)
        require(manager.root == manager.project_root, "vas_root_invalid")
        view = manager.resume(target=manager.root, allow_empty=True)
    except SessionStoreError as error:
        return dict(result, status="partial", code=error.code, session={"status": "unavailable"},
                    nextAction={"code": "review-local-state", "command": "python -B scripts/vas.py start",
                                "message": "PC 세션 조회가 막혔습니다. 프로젝트 기억(vas-state)과 현재 앱·대화를 대조해 "
                                           "진행하고 작업은 done으로 남기세요. PC 저장소를 복구하면 다시 조회하세요."})
    if view["status"] == "empty":
        result.update(session={"status": "none"}, nextAction=_initial_action(state, shared, result["memory"]))
    else:
        session, action = _resume_action(view, prompt["revision"], shared["revision"] if shared else 0)
        result.update(session=session, nextAction=action)
    require(read_project_prompt(root) == prompt, "project_prompt_conflict")
    return result
