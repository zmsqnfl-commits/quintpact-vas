"""The screen's project instruction survives fresh hosts and invalidates old evidence."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vas_session_execution as execution
from vas_project_prompt import ProjectPromptError, read_project_prompt, save_project_prompt
from vas_session import SessionError, SessionManager
from vas_session_work import inspect_work, open_work, start_work

SETTINGS = {"project": {"name": "재고", "sourceType": "new"},
            "task": {"request": "품목과 수량을 표시",
                     "completionCriteria": [{"description": "합계가 맞음", "method": "automatic",
                                             "required": True}]}}
SUMMARY = {"phase": "paused", "summary": "구현 전 준비", "nextStep": "목록 구현",
           "decisions": [], "changedFiles": [], "checks": [], "remaining": []}


@pytest.fixture(params=[1, 2], ids=["nested-v1", "root-v2"])
def kit(tmp_path, request):
    app, private = tmp_path / "재고 앱", tmp_path / "state"
    legacy = request.param == 1
    engine = app / ".vas" if legacy else app
    ui = engine / ("src" if legacy else "ui")
    (app / "src").mkdir(parents=True)
    ui.mkdir(parents=True)
    (ui / "vas-hub.html").write_text("tool")
    (engine / "Run-VAS-System.bat").write_text("@echo off")
    (engine / "project-layout.json").write_text('{"layout":"vas-project","version":%d}' % request.param)
    manager = SessionManager(engine, private)
    sid = manager.create(SETTINGS, app)["session"]["sessionId"]
    return manager, sid, app, engine, private


def prepared(kit, revision=1):
    return execution.prepare(kit[0], kit[1], revision)


def report(prepared):
    handoff = prepared["handoff"]
    return {"format": "vas-ai-result", "schemaVersion": 1, "resultId": "r_0123456789abcdef",
            "handoffId": handoff["workflow"]["handoffId"],
            "handoffPayloadSha256": handoff["integrity"]["payloadSha256"],
            "iteration": 1, "sourceType": handoff["project"]["sourceType"], "status": "complete",
            "tests": [{"name": "합계", "command": "python -m unittest", "status": "passed", "summary": "정상"}],
            "remaining": [], "artifactVersion": "fixture-v1",
            "evidence": [{"criterionId": "C1", "method": "automatic", "outcome": "passed",
                          "artifactVersion": "fixture-v1", "summary": "호스트 보고"}],
            "safety": {"absolutePathsExcluded": True, "secretsExcluded": True, "rawCommandOutputExcluded": True}}


def test_screen_save_reaches_fresh_session_prepare_without_copying_into_session(kit):
    manager, sid, app, engine, private = kit
    original = manager.store.path.read_bytes()
    first = prepared(kit)
    assert "projectPrompt" not in first["handoff"]["context"]
    prompt = "제목은 재고 현황으로 표시하세요.\n결제·구독 기능은 만들지 마세요."
    current = save_project_prompt(engine, 0, prompt)
    fresh = SessionManager(engine, private)
    second = execution.prepare(fresh, sid, 1)
    assert second["handoff"]["context"]["projectPrompt"] == current
    assert prompt.splitlines()[0] in second["handoff"]["assistantGuide"]["pasteText"]
    assert prompt.splitlines()[1] in second["handoff"]["assistantGuide"]["pasteText"]
    assert second["handoff"]["workflow"]["handoffId"] != first["handoff"]["workflow"]["handoffId"]
    assert first["revision"] == second["revision"] == 1
    assert manager.store.path.read_bytes() == original
    assert not list((app / "src").iterdir())
    completed = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/vas-session.py"),
                               "--vas-root", str(engine), "--state-home", str(private),
                               "prepare", "--session", sid, "--expected-revision", "1"],
                              capture_output=True, check=True)
    assert json.loads(completed.stdout)["handoff"]["context"]["projectPrompt"] == current


def test_saved_prompt_invalidates_old_results_and_clearing_removes_the_text(kit):
    manager, sid, _, engine, _ = kit
    save_project_prompt(engine, 0, "표 제목은 재고 현황")
    old = prepared(kit)
    save_project_prompt(engine, 1, "표 제목은 보관 품목")
    with pytest.raises(SessionError, match="execution_result_mismatch"):
        execution.assess(manager, sid, 1, report(old))
    current = prepared(kit)
    assert execution.assess(manager, sid, 1, report(current))["status"] == "assessed"
    save_project_prompt(engine, 2, "")
    cleared = prepared(kit)
    assert cleared["handoff"]["context"]["projectPrompt"] == {"revision": 3, "prompt": ""}
    assert "표 제목은 재고 현황" not in cleared["handoff"]["assistantGuide"]["pasteText"]
    with pytest.raises(SessionError, match="execution_result_mismatch"):
        execution.assess(manager, sid, 1, report(current))


def test_change_while_building_or_assessing_never_returns_a_stale_success(kit, monkeypatch):
    manager, sid, _, engine, _ = kit
    save_project_prompt(engine, 0, "품목 목록 표시")
    build = execution._prompt
    def changing_prompt(*args):
        value = build(*args)
        save_project_prompt(engine, read_project_prompt(engine)["revision"], "품목 합계 표시")
        return value
    with monkeypatch.context() as patch:
        patch.setattr(execution, "_prompt", changing_prompt)
        with pytest.raises(SessionError, match="project_prompt_conflict"):
            prepared(kit)
    latest = report(prepared(kit))
    evaluate = execution.evaluate_result
    def changing_assessment(*args):
        value = evaluate(*args)
        save_project_prompt(engine, read_project_prompt(engine)["revision"], "정렬 버튼도 표시")
        return value
    monkeypatch.setattr(execution, "evaluate_result", changing_assessment)
    with pytest.raises(SessionError, match="project_prompt_conflict"):
        execution.assess(manager, sid, 1, latest)


@pytest.mark.parametrize("initial", [False, True])
def test_new_prompt_marks_work_stale_and_prevents_starting_old_assignment(kit, initial):
    manager, sid, _, engine, _ = kit
    if initial:
        save_project_prompt(engine, 0, "합계를 표시")
    opened = open_work(manager, sid, 1, 0)
    assert opened["work"]["status"] == "available"
    save_project_prompt(engine, int(initial), "합계와 개수를 표시")
    before = manager.store.path.read_bytes()
    assert "project-prompt-changed" in manager.resume(session_id=sid)["work"]["staleReasons"]
    with pytest.raises(SessionError, match="work_context_changed"):
        start_work(manager, sid, 1, 1, {"kind": "implementation", "role": "main", "mode": "direct",
                   "scope": "구현", "observedFiles": ["src/app.py"], "writableFiles": ["src/app.py"],
                   "criterionIds": ["C1"], "supersedes": None})
    assert inspect_work(manager, sid, 1)["contextMatches"] is False
    assert manager.store.path.read_bytes() == before


def test_checkpoint_records_only_prompt_hash_and_does_not_overwrite_new_instructions(kit):
    manager, sid, _, engine, _ = kit
    save_project_prompt(engine, 0, "검증 전 현재 지시를 확인")
    saved = manager.checkpoint(sid, 1, 0, SUMMARY, 1)
    assert saved["progress"]["status"] == "available"
    assert "projectPromptSha256" in saved["progress"]["record"]["savedFor"]
    assert "검증 전 현재 지시를 확인" not in manager.store.path.read_text(encoding="utf-8")
    save_project_prompt(engine, 1, "새 지시로 목록을 다시 확인")
    before = manager.store.path.read_bytes()
    view = manager.resume(session_id=sid)
    assert view["progress"]["status"] == "stale"
    assert "project-prompt-changed" in view["progress"]["staleReasons"]
    for expected in (None, 1, True, "2"):
        with pytest.raises(SessionError, match="project_prompt_conflict"):
            manager.checkpoint(sid, 2, 1, SUMMARY, expected)
    assert manager.store.path.read_bytes() == before
    assert read_project_prompt(engine)["prompt"] == "새 지시로 목록을 다시 확인"
    saved = manager.checkpoint(sid, 2, 1, SUMMARY, 2)
    assert saved["progress"]["status"] == "available"


def test_corrupt_prompt_is_never_treated_as_missing(kit):
    manager, sid, app, engine, _ = kit
    save_project_prompt(engine, 0, "현재 재고 표시")
    manager.checkpoint(sid, 1, 0, SUMMARY, 1)
    (app / "VAS-PROJECT-PROMPT.json").write_text("{")
    with pytest.raises(ProjectPromptError, match="project_prompt_corrupt"):
        prepared(kit, 2)
    assert "project-prompt-unavailable" in manager.resume(session_id=sid)["progress"]["staleReasons"]


def test_prompt_does_not_bypass_task_readiness_or_apply_to_another_target(kit, tmp_path):
    manager, sid, _, engine, _ = kit
    save_project_prompt(engine, 0, "합계가 표시되는 재고 앱 만들기")
    incomplete = deepcopy(SETTINGS)
    incomplete["task"]["request"] = ""
    incomplete["task"]["completionCriteria"] = []
    manager.save(sid, 1, incomplete)
    assert set(prepared(kit, 2)["missing"]) == {"task.request", "task.completionCriteria.required"}
    other = tmp_path / "another-app"
    other.mkdir()
    manager.rebind(sid, 2, other)
    view = prepared(kit, 3)
    assert "projectPrompt" not in view["handoff"]["context"]
    assert "합계가 표시되는 재고 앱 만들기" not in view["handoff"]["assistantGuide"]["pasteText"]


def test_cli_checkpoint_uses_the_actual_project_prompt_revision(kit):
    manager, sid, _, engine, private = kit
    save_project_prompt(engine, 0, "표와 합계 확인")
    command = [sys.executable, "-B", str(ROOT / "scripts/vas-session.py"),
               "--vas-root", str(engine), "--state-home", str(private),
               "checkpoint", "--session", sid, "--expected-revision", "1",
               "--expected-progress-revision", "0"]
    body = json.dumps(SUMMARY, ensure_ascii=False).encode("utf-8")
    failed = subprocess.run(command, input=body, capture_output=True)
    assert failed.returncode == 1 and json.loads(failed.stdout)["code"] == "project_prompt_conflict"
    saved = subprocess.run(command + ["--expected-project-prompt-revision", "1"],
                           input=body, capture_output=True, check=True)
    assert json.loads(saved.stdout)["progress"]["status"] == "available"
    assert manager.resume(session_id=sid)["progress"]["revision"] == 1


def test_checkpoint_rejects_project_prompt_change_during_normalization(kit, monkeypatch):
    import vas_session_progress as progress
    manager, sid, _, engine, _ = kit
    save_project_prompt(engine, 0, "이전 작업의 다음 단계")
    before = manager.store.path.read_bytes()
    normalize = progress.normalize_progress
    changed = False
    def changing_normalization(raw):
        nonlocal changed
        result = normalize(raw)
        if not changed:
            changed = True
            save_project_prompt(engine, 1, "화면에서 새 작업 지시")
        return result
    monkeypatch.setattr(progress, "normalize_progress", changing_normalization)
    with pytest.raises(SessionError, match="project_prompt_conflict"):
        manager.checkpoint(sid, 1, 0, SUMMARY, 1)
    assert manager.store.path.read_bytes() == before
    assert read_project_prompt(engine)["prompt"] == "화면에서 새 작업 지시"
