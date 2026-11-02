"""The close-out command saves only current, genuinely assessed or explicitly paused work."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_project_prompt_handoff import SETTINGS, prepared, report
from vas_project_prompt import save_project_prompt
from vas_session import SessionError, SessionManager
from vas_session_work import open_work
import vas_finish


@pytest.fixture
def kit(tmp_path):
    root = tmp_path / "메뉴판"
    (root / "ui").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "ui/vas-hub.html").write_text("tool")
    (root / "Run-VAS-System.bat").write_text("tool")
    (root / "project-layout.json").write_text('{"layout":"vas-project","version":2}')
    state = tmp_path / "state"
    manager = SessionManager(root, state)
    sid = manager.create(SETTINGS, root)["session"]["sessionId"]
    return manager, sid, root, root, state


def close(kit, raw, *flags):
    _, sid, _, engine, state = kit
    cli = Path(__file__).resolve().parents[1] / "scripts/vas.py"
    proc = subprocess.run([sys.executable, "-B", str(cli), "--vas-root", str(engine),
                           "--state-home", str(state), "finish", "--session", sid,
                           "--expected-revision", "1", "--expected-progress-revision", "0", *flags],
                          input=json.dumps(raw, ensure_ascii=False), text=True, encoding="utf-8",
                          capture_output=True, timeout=30)
    assert not proc.stderr, proc.stderr
    return proc.returncode, json.loads(proc.stdout)


def test_real_cli_assesses_saves_reads_back_and_safe_retry(kit):
    manager, sid, _, engine, _ = kit
    save_project_prompt(engine, 0, "Use the approved settings")
    response = report(prepared(kit))
    response["status"] = "blocked"
    response["tests"][0]["status"] = "failed"
    response["remaining"] = [{"severity": "blocker", "summary": "sum differs", "nextAction": "Fix sum"}]
    raw = {"progress": {"summary": "Checked sum"}, "result": response}
    flags = ("--expected-project-prompt-revision", "1")
    code, view = close(kit, raw, *flags)
    assert code == 0 and view["status"] == "checkpointed"
    assert (view["revision"], view["progressRevision"], view["projectPromptRevision"]) == (2, 1, 1)
    assert not view["complete"] and view["userAcceptance"] == "not-recorded"
    assert view["assessment"]["status"] != "complete" and view["reportedStatus"] == "blocked"
    assert view["followUp"]["actions"] and view["nextStep"] == view["followUp"]["nextStep"]
    saved = manager.resume(session_id=sid)["progress"]
    assert saved["status"] == "available" and saved["record"]["summary"] == view["progress"]
    assert view["progress"]["phase"] == "blocked"
    assert "sum differs Fix sum" in view["progress"]["remaining"]
    assert view["progress"]["checks"][0]["status"] == "failed"
    assert view["progress"]["checks"][0]["exitCode"] is None
    before = manager.store.path.read_bytes()
    assert view["sharedProgress"]["revision"] == 1 and view["privateCheckpoint"] == "confirmed"
    code, retry = close(kit, raw, *flags)
    assert code == 0 and retry["replayed"] and retry["assessment"] is None
    assert retry["assessmentStatus"] == view["assessment"]["status"] and retry["sharedProgress"] == view["sharedProgress"]
    assert manager.store.path.read_bytes() == before
    raw["progress"]["summary"] = "different checkpoint"
    assert close(kit, raw, *flags)[1]["code"] == "revision_conflict"
    assert manager.store.path.read_bytes() == before


def test_pause_records_no_assessment_or_fake_test(kit):
    manager, sid, _, _, _ = kit
    raw = {"result": None, "progress": {"phase": "paused", "summary": "Waiting for input",
                                        "nextStep": "Ask which app to use"}}
    code, value = close(kit, raw)
    assert code == 0 and value["assessment"] is value["followUp"] is None
    assert value["progress"]["checks"] == [] and not value["complete"]
    assert manager.resume(session_id=sid)["session"]["settings"]["nextStep"] == "Ask which app to use"


def test_mismatch_invalid_input_and_prompt_conflict_do_not_write(kit):
    manager, _, _, engine, _ = kit
    payload = report(prepared(kit))
    raw = {"result": payload, "progress": {"summary": "About to test"}}
    before = manager.store.path.read_bytes()
    payload["handoffId"] = "h_" + "f" * 32
    assert close(kit, raw)[1]["code"] == "execution_result_mismatch"
    payload["iteration"] = True
    assert close(kit, raw)[1]["code"] == "execution_result_invalid"
    assert close(kit, {"result": None, "progress": {"phase": "awaiting-request"}})[1]["code"] == "finish_result_required"
    save_project_prompt(engine, 0, "User changed prompt")
    assert close(kit, raw, "--expected-project-prompt-revision", "0")[1]["code"] == "project_prompt_conflict"
    assert manager.store.path.read_bytes() == before


def test_cannot_finish_external_project_or_skip_unresolved_actions(kit, tmp_path):
    manager, sid, _, _, _ = kit
    payload = report(prepared(kit))
    raw = {"result": payload, "progress": {"summary": "Host claims done", "phase": "awaiting-request"}}
    before = manager.store.path.read_bytes()
    assert close(kit, raw)[1]["code"] == "finish_followup_pending"
    assert manager.store.path.read_bytes() == before
    external = tmp_path / "different app"
    external.mkdir()
    manager.rebind(sid, 1, external)
    before = manager.store.path.read_bytes()
    assert close(kit, raw)[1]["code"] == "finish_target_mismatch"
    assert manager.store.path.read_bytes() == before


def test_work_changed_between_assessment_and_checkpoint_is_not_saved(kit, monkeypatch):
    manager, sid, _, _, _ = kit
    payload = report(prepared(kit))
    underlying = vas_finish.assess_with_result

    def concurrent(*args):
        decision = underlying(*args)
        open_work(manager, sid, 1, 0)
        return decision

    monkeypatch.setattr(vas_finish, "assess_with_result", concurrent)
    with pytest.raises(SessionError, match="work_revision_conflict"):
        vas_finish.finish(manager, sid, 1, 0, {"result": payload, "progress": {"summary": "Review"}})
    resumed = manager.resume(session_id=sid)
    assert resumed["session"]["revision"] == 1 and resumed["work"]["revision"] == 1
    assert "progress" not in resumed


def test_reread_does_not_report_a_superseded_save_as_confirmed(kit, monkeypatch):
    manager, sid, _, _, _ = kit
    underlying = vas_finish.checkpoint

    def supersede(*args, **kwargs):
        saved = underlying(*args, **kwargs)
        manager.save(sid, 2, saved["session"]["settings"])
        return saved

    monkeypatch.setattr(vas_finish, "checkpoint", supersede)
    outcome = vas_finish.finish(manager, sid, 1, 0, {"result": None, "progress": {
        "phase": "paused", "summary": "Waiting", "nextStep": "Check the current settings"}})
    assert outcome["status"] == "partial" and outcome["code"] == "finish_readback_conflict"
    assert outcome["privateCheckpoint"] == "saved-unconfirmed" and outcome["sharedProgress"] is None
    assert manager.resume(session_id=sid)["session"]["revision"] == 3


def quick(kit, *args):
    _, _, _, root, state_home = kit
    cli = Path(__file__).resolve().parents[1] / "scripts/vas.py"
    run = subprocess.run([sys.executable, "-B", str(cli), "--vas-root", str(root),
                          "--state-home", str(state_home), "finish", *args],
                         capture_output=True, check=False, timeout=30)
    assert not run.stderr, run.stderr
    return run.returncode, json.loads(run.stdout)


def test_portable_quick_close_does_not_change_a_private_checkpoint(kit):
    manager, sid, _, _, _ = kit
    original = manager.store.path.read_bytes()
    code, recorded = quick(kit, "--summary", "Menu label checked", "--check", "메뉴판 표시: 통과",
                           "--check", "휴대전화: 미실행", "--next-step", "Check phone")
    assert code == 0 and recorded["privateSession"] == "available"
    assert recorded["privateCheckpoint"] == "not-written" and recorded["assessment"] is None
    note = recorded["sharedProgress"]
    assert note["revision"] == 1 and note["checks"] == [
        {"name": "메뉴판 표시", "status": "passed"}, {"name": "휴대전화", "status": "not-run"}]
    assert "progress" not in manager.resume(session_id=sid)
    assert manager.store.path.read_bytes() == original
    assert quick(kit, "--summary", "Wrong check", "--check", "missing-status")[1]["code"] == "finish_check_invalid"


def test_missing_session_and_partial_shared_failure_use_distinct_outcomes(kit):
    manager, sid, app, root, state = kit
    other_host = (None, None, app, root, state.parent / "fresh-other-host")
    code, empty = quick(other_host)
    assert code == 0 and empty["status"] == "not-recorded" and empty["privateSession"] == "none"
    assert not other_host[-1].exists() and empty["sharedProgress"] is None
    code, shared = quick(other_host, "--summary", "Other host wrote first")
    assert code == 0 and shared["privateSession"] == "none" and shared["sharedProgress"]["revision"] == 1

    raw = {"result": None, "progress": {"phase": "paused", "summary": "Local paused", "nextStep": "Compare notes"}}
    code, partial = close(kit, raw, "--expected-shared-revision", "0")
    assert code == 1 and partial["status"] == "partial" and partial["sharedError"]
    assert partial["privateCheckpoint"] == "confirmed" and partial["sharedProgress"] is None
    assert manager.resume(session_id=sid)["session"]["revision"] == 2
    before = manager.store.path.read_bytes()
    code, restored = close(kit, raw, "--expected-shared-revision", "1")
    assert code == 0 and restored["replayed"]
    assert restored["sharedProgress"]["revision"] == 2 and restored["progressRevision"] == 1
    assert manager.store.path.read_bytes() == before


def test_quick_close_works_when_only_the_private_store_is_unavailable(kit, tmp_path):
    manager, _, app, root, _ = kit
    inaccessible = tmp_path / "not-a-state-directory"
    inaccessible.write_text("untouched")
    fixture = (None, None, app, root, inaccessible)
    before = manager.store.path.read_bytes()
    code, brief = quick(fixture, "--summary", "Changed a label", "--check", "UI: failed")
    assert code == 0 and brief["privateSession"] == "unavailable"
    assert brief["privateCheckpoint"] == "not-written" and brief["privateError"]
    assert brief["sharedProgress"]["revision"] == 1
    assert inaccessible.read_text() == "untouched" and manager.store.path.read_bytes() == before


def test_conflicting_summary_cannot_report_a_failed_check_as_passed(kit):
    manager = kit[0]
    payload = report(prepared(kit))
    payload["tests"][0]["status"] = "failed"
    false_check = dict(payload["tests"][0], status="passed")
    raw = {"result": payload, "progress": {"summary": "Summary", "checks": [false_check]}}
    before = manager.store.path.read_bytes()
    assert close(kit, raw)[1]["code"] == "finish_check_conflict"
    assert manager.store.path.read_bytes() == before


def test_many_submitted_tests_preserve_failed_and_skipped_outcomes_in_shared_note(kit):
    payload = report(prepared(kit))
    template = payload["tests"][0]
    payload["tests"] = [dict(template, name=f"check {i}", status=state) for i, state in
                        enumerate(["failed", "skipped"] + ["passed"] * 11)]
    code, view = close(kit, {"result": payload, "progress": {"summary": "Tested 13 cases"}})
    assert code == 0
    checks = view["progress"]["checks"]
    assert [(item["status"], item["summary"]) for item in checks] == [
        ("failed", "1 failed"), ("skipped", "1 skipped"), ("passed", "11 passed")]
    assert [item["status"] for item in view["sharedProgress"]["checks"]] == ["failed", "skipped", "passed"]
