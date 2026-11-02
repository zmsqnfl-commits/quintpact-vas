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


def test_prepared_finish_arguments_bind_the_existing_shared_revision(kit):
    manager, _, _, root, state = kit
    assert vas_finish.quick_finish(root, state, "Prior work", [], "Read next task")["sharedProgress"]["revision"] == 1
    args = prepared(kit)["finishArguments"]
    assert args[args.index("--expected-shared-revision") + 1] == "1"
    code, result = close(kit, {"progress": {"summary": "Check menu"}}, *args[1:])
    assert code == 0 and result["sharedProgress"]["revision"] == 2
    assert manager.resume(session_id=kit[1])["progress"]["revision"] == 1


def test_pause_records_no_assessment_or_fake_test(kit):
    manager, sid, _, _, _ = kit
    raw = {"result": None, "progress": {"phase": "paused", "summary": "Waiting for input",
                                        "nextStep": "Ask which app to use"}}
    code, value = close(kit, raw)
    assert code == 0 and value["assessment"] is value["followUp"] is None
    assert value["progress"]["checks"] == [] and not value["complete"]
    assert manager.resume(session_id=sid)["session"]["settings"]["nextStep"] == "Ask which app to use"


def test_cli_builds_result_from_host_checks_and_retries_once(kit):
    manager, sid, _, _, _ = kit
    handoff = prepared(kit)["handoff"]
    flags = ("--prepared-hash", handoff["integrity"]["payloadSha256"], "--summary", "Checked menu",
             "--artifact-version", "menu-v4", "--criterion", "C1=passed:Total matched",
             "--check", "Menu:passed", "--check", "Phone:not-run", "--changed-file", "created:src/menu.js",
             "--changed-file", "src/display.css", "--remaining", "Open phone preview")
    code, saved = close(kit, None, *flags)
    assert code == 0 and saved["status"] == "checkpointed"
    assert saved["reportedStatus"] == "incomplete" and saved["assessmentStatus"] == "needs-verification"
    assert saved["assessment"]["conditions"] == [
        {"id": "C1", "required": True, "status": "unconfirmed", "source": "agent-submitted"}]
    expected = saved["progress"]
    assert expected["changedFiles"] == ["src/menu.js", "src/display.css"]
    assert expected["remaining"] == ["Open phone preview"]
    assert [c["status"] for c in expected["checks"]] == ["passed", "not-run"]
    basis = saved["followUp"]["basis"]
    assert basis["handoffId"] == handoff["workflow"]["handoffId"]
    assert basis["handoffPayloadSha256"] == flags[1] and basis["resultId"].startswith("r_")
    assert len(basis["resultId"]) == 34
    assert saved["result"]["resultId"] == basis["resultId"] and saved["result"]["tests"][1]["status"] == "skipped"
    before = manager.store.path.read_bytes()
    code, retry = close(kit, None, *flags)
    assert code == 0 and retry["replayed"] and retry["sharedProgress"] == saved["sharedProgress"]
    assert "result" not in retry and "result" not in saved["sharedProgress"]
    assert close(kit, None, *flags, "--remaining", "Changed claim")[1]["code"] == "revision_conflict"
    assert manager.store.path.read_bytes() == before and manager.resume(session_id=sid)["session"]["revision"] == 2


def test_generated_result_actions_evidence_and_check_state_use_only_reported_facts(kit, monkeypatch):
    manager, sid, _, _, _ = kit
    handoff = prepared(kit)["handoff"]
    captured = {}
    assess = vas_finish.assess_with_result

    def inspect(*args):
        captured.update(args[-1])
        return assess(*args)

    monkeypatch.setattr(vas_finish, "assess_with_result", inspect)
    progress = {"summary": "Imported", "changedFiles": ["created:src/server.py", "src/route.py",
                "modified:src\\menu.js", "modified:.env"], "remaining": ["Verify shop configuration"],
                "checks": [{"name": "API", "command": "run-server-check", "status": "passed", "exitCode": 0,
                            "summary": "Got 200"}]}
    out = vas_finish.finish(manager, sid, 1, 0, {"progress": progress},
                            prepared_hash=handoff["integrity"]["payloadSha256"], artifact_version="app-build-4",
                            criteria=["C1=not-run:No matching fixture available"])
    assert captured["evidence"] == [{"criterionId": "C1", "artifactVersion": "app-build-4",
            "method": "automatic", "outcome": "skipped", "summary": "No matching fixture available"}]
    assert captured["tests"] == [{"name": "API", "status": "passed", "summary": "Got 200", "command": "run-server-check"}]
    assert captured["changes"]["relativeFiles"] == [{"path": "src/server.py", "action": "created"},
                                                     {"path": "src/menu.js", "action": "modified"}]
    assert captured["remaining"] == [{"summary": "Verify shop configuration"}] and "readback" not in captured
    assert out["progress"]["checks"][0]["exitCode"] == 0 and out["complete"] is False


def test_draft_requires_original_receipt_and_only_explicit_known_evidence(kit):
    manager, _, _, _, _ = kit
    before = manager.store.path.read_bytes()
    opts = ("--prepared-hash", prepared(kit)["handoff"]["integrity"]["payloadSha256"], "--summary", "Checked")
    assert close(kit, None, *opts, "--criterion", "C1=passed:Looked")[1]["code"] == "finish_artifact_version_required"
    opts += ("--artifact-version", "v1")
    assert close(kit, None, *opts, "--criterion", "C2=passed:Looked")[1]["code"] == "finish_criterion_unknown"
    assert close(kit, None, *opts, "--criterion", "C1=true:value")[1]["code"] == "finish_criterion_invalid"
    assert close(kit, None, *opts, "--criterion", "C1=passed:x", "--criterion", "C1=failed:y")[1]["code"] == "finish_criterion_invalid"
    assert close(kit, None, *opts, "--prepared-hash", "f" * 64)[1]["code"] == "execution_result_mismatch"
    assert manager.store.path.read_bytes() == before
    code, saved = close(kit, {"progress": {"summary": "No tests yet"}}, *opts[:2])
    assert code == 0 and saved["reportedStatus"] == "incomplete"
    assert saved["assessment"]["conditions"][0]["source"] == "missing" and not saved["progress"]["checks"]


def test_strict_report_skipped_matches_not_run_progress_and_rejects_real_disagreement(kit):
    payload = report(prepared(kit))
    item = payload["tests"][0]
    item["status"] = "skipped"
    check = {**item, "status": "passed"}
    raw = {"result": payload, "progress": {"summary": "Check deferred", "checks": [check]}}
    assert close(kit, raw)[1]["code"] == "finish_check_conflict"
    check["status"] = "not-run"
    code, saved = close(kit, raw)
    assert code == 0 and [c["status"] for c in saved["progress"]["checks"]] == ["not-run"]


@pytest.mark.parametrize(("reported", "canonical"), [("failed", "failed"), ("not-run", "skipped"),
                                                     ("not-applicable", "not-applicable")])
def test_unresolved_criterion_is_visible_in_private_and_portable_history_on_retry(kit, reported, canonical):
    manager, sid, root, _, _ = kit
    flags = ("--prepared-hash", prepared(kit)["handoff"]["integrity"]["payloadSha256"],
             "--summary", "Price checked", "--artifact-version", "menu-4", "--remaining", "Review opening hours",
             "--criterion", f"C1={reported}:Price wrong at /home/operator/private " + "메" * 400)
    code, saved = close(kit, None, *flags)
    assert code == 0 and saved["progress"]["checks"] == []
    notes = saved["progress"]["remaining"]
    assert notes[0].startswith(f"C1 {canonical}: Price wrong at [absolute-path]") and notes[0].endswith("…")
    assert len(notes[0].encode("utf-16-le")) <= 600 and notes[1:] == ["Review opening hours"]
    assert manager.resume(session_id=sid)["progress"]["record"]["summary"]["remaining"] == notes
    assert saved["sharedProgress"]["remaining"] == notes
    markdown = (root / "vas-state/progress/000001.md").read_text("utf-8")
    assert f"C1 {canonical}: Price wrong" in markdown and "operator/private" not in markdown
    before = manager.store.path.read_bytes()
    code, retry = close(kit, None, *flags)
    assert code == 0 and retry["replayed"] and retry["sharedProgress"]["remaining"] == notes
    assert manager.store.path.read_bytes() == before and not (root / "vas-state/progress/000002.ok").exists()


def test_concrete_criteria_pack_or_fail_before_replacing_user_remaining(kit):
    manager, _, root, _, _ = kit
    explicit = [f"Open issue {i}" for i in range(9)]
    evidence = [{"criterionId": "C1", "outcome": "failed", "summary": "First failed"},
                {"criterionId": "C2", "outcome": "skipped", "summary": "No camera"}]
    packed = vas_finish._retain_criterion_issues({"remaining": explicit}, evidence)["remaining"]
    assert packed == ["C1 failed: First failed\nC2 skipped: No camera", *explicit]
    before = manager.store.path.read_bytes()
    raw = {"progress": {"summary": "Price checked", "remaining": [*explicit, "One more issue"]}}
    code, error = close(kit, raw, "--prepared-hash", prepared(kit)["handoff"]["integrity"]["payloadSha256"],
                        "--artifact-version", "v4", "--criterion", "C1=failed:Price differs")
    assert code == 1 and error["code"] == "finish_remaining_summary_required"
    assert manager.store.path.read_bytes() == before and not (root / "vas-state/progress").exists()


def test_mismatch_invalid_input_and_prompt_conflict_do_not_write(kit):
    manager, _, _, engine, _ = kit
    payload = report(prepared(kit))
    raw = {"result": payload, "progress": {"summary": "About to test"}}
    before = manager.store.path.read_bytes()
    payload["handoffId"] = "h_" + "f" * 32
    assert close(kit, raw)[1]["code"] == "execution_result_mismatch"
    payload["iteration"] = True
    assert close(kit, raw)[1] == {"status": "error", "code": "execution_result_invalid",
                                  "detail": "invalid_iteration"}
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


def test_file_only_host_keeps_confirmed_scope_and_open_work_across_a_quick_note(kit):
    manager, sid, app, root, state = kit
    report_data = report(prepared(kit))
    report_data["tests"][0].update(status="failed", command="python secret-internal-command.py")
    report_data["remaining"] = [{"severity": "blocker", "summary": "Fix sum"}]
    partial = {"summary": "Stock sum failed", "decisions": [
        {"decision": "Retain old stock data", "reason": "Internal reason only"}]}
    code, full = close(kit, {"result": report_data, "progress": partial})
    assert code == 0
    note = full["sharedProgress"]
    expected_scope = {"objective": SETTINGS["task"]["request"],
                      "criteria": [c["description"] for c in SETTINGS["task"]["completionCriteria"]]}
    assert note["scope"] == expected_scope and note["decisions"] == ["Retain old stock data"]
    assert "Fix sum" in note["remaining"] and note["checks"][0]["status"] == "failed"
    private_bytes = manager.store.path.read_bytes()

    other = (None, None, app, root, state.parent / "file-only")
    code, result = quick(other, "--summary", "Changed title", "--check", "Title: 통과",
                         "--expected-shared-revision", "1")
    assert code == 0 and result["privateSession"] == "none"
    latest = result["sharedProgress"]
    assert latest["revision"] == 2 and latest["scope"] == expected_scope
    assert latest["decisions"] == note["decisions"] and latest["remaining"] == note["remaining"]
    assert latest["nextStep"] == note["nextStep"] and latest["phase"] == "blocked"
    assert latest["checks"] == note["checks"] + [{"name": "Title", "status": "passed"}]
    assert manager.store.path.read_bytes() == private_bytes and not other[-1].exists()
    cmd = Path(__file__).resolve().parents[1] / "scripts/vas.py"
    new_host = subprocess.run([sys.executable, "-B", str(cmd), "--vas-root", str(root),
                               "--state-home", str(other[-1]), "start"], capture_output=True, check=True)
    brief = json.loads(new_host.stdout)["sharedProgress"]
    assert brief["scope"] == expected_scope and brief["decisions"] == latest["decisions"]
    assert len(latest["remaining"]) > 2 and brief["truncated"] is True
    assert brief["remaining"] == latest["remaining"][:2] and brief["markdownPath"] == latest["markdownPath"]
    durable = json.loads((root / "vas-state/progress/000002.json").read_text(encoding="utf-8"))["record"]
    assert durable["scope"] == expected_scope and durable["remaining"] == latest["remaining"]
    markdown = (root / "vas-state/progress/000002.md").read_text(encoding="utf-8")
    assert expected_scope["objective"] in markdown and "Fix sum" in markdown
    assert all(item in markdown for item in latest["remaining"])
    assert all(term not in markdown for term in (sid, str(state), "Internal reason only", "secret-internal-command"))


def test_conflicting_private_scope_requires_full_reconciliation(kit):
    manager, sid, _, root, _ = kit
    raw = {"result": None, "progress": {"phase": "paused", "summary": "Initial task",
           "nextStep": "Continue counting", "remaining": ["Old issue"]}}
    assert close(kit, raw)[0] == 0
    settings = manager.resume(session_id=sid)["session"]["settings"]
    settings["task"].update(request="Show menu labels", completionCriteria=[
        {"description": "Menu visible", "method": "automatic", "required": True}])
    manager.save(sid, 2, settings)
    before = manager.store.path.read_bytes()
    code, conflict = quick(kit, "--summary", "Labels updated", "--expected-shared-revision", "1")
    assert code == 1 and conflict["sharedError"] == "shared_progress_scope_conflict"
    assert manager.store.path.read_bytes() == before

    saved = vas_finish.finish(manager, sid, 3, 1, {"result": None, "progress": {
        "phase": "paused", "summary": "Menu project confirmed", "nextStep": "Check menu labels"}},
        expected_shared_revision=1)
    assert saved["sharedProgress"]["scope"] == {"objective": "Show menu labels", "criteria": ["Menu visible"]}
    assert not saved["sharedProgress"].get("remaining") and not saved["sharedProgress"].get("decisions")


def test_portable_goal_is_redacted_before_visible_bounded_clipping(kit):
    manager, sid, _, _, _ = kit
    settings = manager.resume(session_id=sid)["session"]["settings"]
    settings["task"]["request"] = "Keep /department/private out: " + "재" * 1100
    manager.save(sid, 1, settings)
    saved = vas_finish.finish(manager, sid, 2, 0, {"result": None, "progress": {
        "phase": "paused", "summary": "Goal confirmed", "nextStep": "Check display"}})
    objective = saved["sharedProgress"]["scope"]["objective"]
    assert "[absolute-path]" in objective and "/department/" not in objective
    assert len(objective.encode("utf-16-le")) == 2000 and objective.endswith("…")
