"""Selected-file evidence stays local, scoped and bound to its prepared task."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vas_session_execution as execution
import vas_session_work as lifecycle
import vas_work_files as files
from vas_session import SessionError, SessionManager


@pytest.fixture
def setup(tmp_path):
    root, app = tmp_path / "vas", tmp_path / "app"
    (root / "src").mkdir(parents=True)
    (root / "Run-VAS-System.bat").write_text("@echo off", encoding="utf-8")
    (root / "src/vas-hub.html").write_text("VAS", encoding="utf-8")
    app.mkdir()
    (app / "app.py").write_text("value = 1\n", encoding="utf-8")
    (app / "test_app.py").write_text("assert True\n", encoding="utf-8")
    settings = {"project": {"name": "Booking", "sourceType": "existing"},
                "task": {"request": "Fix booking", "designScope": {"mode": "preserve"},
                         "completionCriteria": [{"description": "Booking passes checks",
                                                 "method": "automatic", "required": True}]},
                "nextStep": "Implement then check"}
    manager = SessionManager(root, tmp_path / "state")
    session = manager.create(settings, app)["session"]
    return manager, session, app


def opened(setup):
    manager, session, _ = setup
    return lifecycle.open_work(manager, session["sessionId"], 1, 0)


def assignment(kind="verification", **changes):
    raw = {"kind": kind, "role": "main", "mode": "direct", "label": "Booking check",
           "observedFiles": ["app.py", "test_app.py"], "writableFiles": [],
           "criterionIds": ["C1"], "command": "python -m pytest test_app.py"}
    if kind == "implementation":
        raw.update(role="implementer", mode="delegated", writableFiles=["app.py"])
    raw.update(changes)
    return raw


def report(state="returned", **changes):
    raw = {"state": state, "hostCallId": "call-example-1", "summary": "Host returned",
           "changedFiles": [], "exitCode": 0 if state == "returned" else None,
           "criteria": [{"id": "C1", "status": "passed", "summary": "Host reports passed"}]
                       if state == "returned" else []}
    raw.update(changes)
    return raw


def start(setup, raw=None, revision=1, work_revision=1):
    manager, session, _ = setup
    return lifecycle.start_work(manager, session["sessionId"], revision, work_revision,
                                assignment() if raw is None else raw)


def finish(setup, started, raw=None, revision=1, work_revision=None):
    manager, session, _ = setup
    return lifecycle.finish_work(manager, session["sessionId"], revision,
                                 started["work"]["revision"] if work_revision is None else work_revision,
                                 started["unitId"], report() if raw is None else raw)


def inspect(setup, revision=1):
    manager, session, _ = setup
    return lifecycle.inspect_work(manager, session["sessionId"], revision)


def test_open_binds_prepared_context_without_changing_settings_or_app(setup):
    manager, session, app = setup
    before = {path.name: path.read_bytes() for path in app.iterdir()}
    view = opened(setup)
    work = view["work"]["record"]
    handoff = execution.prepare(manager, session["sessionId"], 1)["handoff"]
    assert view["session"] == session and work["revision"] == 1
    assert work["context"]["handoffId"] == handoff["workflow"]["handoffId"]
    assert work["context"]["handoffPayloadSha256"] == handoff["integrity"]["payloadSha256"]
    assert work["context"]["targetBindingSha256"]
    assert str(app) not in json.dumps(work)
    assert view["work"]["filesChecked"] is False and view["work"]["hostReportsVerified"] is False
    assert {path.name: path.read_bytes() for path in app.iterdir()} == before
    assert inspect(setup)["missingCriteria"] == ["C1"]


def test_unchanged_check_covers_sample_but_never_authenticates_host_or_accepts_result(setup):
    opened(setup)
    finished = finish(setup, start(setup))
    manager, session, _ = setup
    before = manager.store.path.read_bytes()
    checked = inspect(setup)
    assert checked["contextMatches"] is True and checked["reasons"] == []
    assert checked["coveredCriteria"] == ["C1"] and checked["missingCriteria"] == []
    assert checked["units"][0]["sampleMatches"] is True
    assert checked["artifactVersion"].startswith("vas-files-")
    assert checked["complete"] is False and checked["hostReportsVerified"] is False
    assert manager.store.path.read_bytes() == before
    resumed = SessionManager(manager.root, manager.store.home).resume(session_id=session["sessionId"])
    assert resumed == finished


def test_edit_after_pass_invalidates_that_check_and_changes_artifact(setup):
    opened(setup)
    finish(setup, start(setup))
    before = inspect(setup)
    (setup[2] / "app.py").write_text("value = 2\n", encoding="utf-8")
    after = inspect(setup)
    assert after["units"][0]["changedSinceReturn"] == ["app.py"]
    assert "work-files-changed" in after["units"][0]["reasons"]
    assert after["missingCriteria"] == ["C1"]
    assert after["artifactVersion"] != before["artifactVersion"]
    assert setup[0].resume(session_id=setup[1]["sessionId"])["work"]["filesChecked"] is False


def test_mutation_during_check_is_detected_even_when_later_files_match_return(setup):
    opened(setup)
    running = start(setup)
    (setup[2] / "app.py").write_text("value = 2\n", encoding="utf-8")
    finish(setup, running)
    unit = inspect(setup)["units"][0]
    assert unit["observedChangedFiles"] == ["app.py"]
    assert unit["observedOutOfScopeFiles"] == ["app.py"]
    assert unit["changedSinceReturn"] == []
    assert "work-inputs-changed" in unit["reasons"] and not unit["sampleMatches"]


@pytest.mark.parametrize("state", ["failed", "timed-out", "unreturned", "cancelled"])
def test_failed_or_missing_returns_never_cover_checks_and_can_be_superseded(setup, state):
    opened(setup)
    first = start(setup)
    assert "work-unreturned" in inspect(setup)["units"][0]["reasons"]
    finish(setup, first, report(state))
    assert "work-" + state in inspect(setup)["units"][0]["reasons"]
    retry = start(setup, assignment(supersedes=first["unitId"]), work_revision=3)
    finish(setup, retry)
    checked = inspect(setup)
    assert checked["reasons"] == [] and checked["coveredCriteria"] == ["C1"]
    assert len(checked["units"]) == 1 and len(setup[0].resume(session_id=setup[1]["sessionId"])["work"]["record"]["units"]) == 2


def test_two_independent_units_keep_report_ids_and_parallel_returns(setup):
    opened(setup)
    implementation = start(setup, assignment("implementation"))
    review = start(setup, assignment("review", role="reviewer", mode="delegated",
                                   observedFiles=["test_app.py"]), work_revision=2)
    (setup[2] / "app.py").write_text("value = 2\n", encoding="utf-8")
    finish(setup, review, report(hostCallId="agent-review"), work_revision=3)
    finish(setup, implementation, report(hostCallId="agent-implementation", changedFiles=["app.py"]), work_revision=4)
    checked = inspect(setup)
    assert checked["units"][0]["observedChangedFiles"] == ["app.py"]
    assert checked["units"][0]["reasons"] == []
    assert checked["units"][1]["sampleMatches"] is True
    assert checked["missingCriteria"] == ["C1"]  # Review report alone is no automatic check.


@pytest.mark.parametrize("observed,reported", [(True, False), (False, True), (True, True)])
def test_observed_and_reported_scope_are_independently_checked(setup, observed, reported):
    opened(setup)
    running = start(setup, assignment("implementation"))
    if observed:
        (setup[2] / "test_app.py").write_text("assert False\n", encoding="utf-8")
    finish(setup, running, report(changedFiles=["other.py"] if reported else []))
    unit = inspect(setup)["units"][0]
    assert unit["observedOutOfScopeFiles"] == (["test_app.py"] if observed else [])
    assert unit["reportedOutOfScopeFiles"] == (["other.py"] if reported else [])
    assert "work-out-of-scope" in unit["reasons"]


def test_later_controlled_implementation_drift_does_not_invalidate_earlier_implementation(setup):
    opened(setup)
    first = start(setup, assignment("implementation"))
    (setup[2] / "app.py").write_text("value = 2\n", encoding="utf-8")
    finish(setup, first, report(changedFiles=["app.py"]))
    second = start(setup, assignment("implementation"), work_revision=3)
    (setup[2] / "app.py").write_text("value = 3\n", encoding="utf-8")
    finish(setup, second, report(changedFiles=["app.py"]))
    check = start(setup, work_revision=5)
    finish(setup, check)
    checked = inspect(setup)
    assert checked["units"][0]["changedSinceReturn"] == ["app.py"]
    assert checked["units"][0]["reasons"] == [] and checked["reasons"] == []


@pytest.mark.parametrize("action", ["settings", "criteria", "rebind", "checkpoint"])
def test_context_changes_prevent_new_units_but_preserve_return_at_original_context(setup, tmp_path, action):
    manager, session, app = setup
    opened(setup)
    running = start(setup)
    if action == "rebind":
        new_app = tmp_path / "replacement"
        new_app.mkdir()
        manager.rebind(session["sessionId"], 1, new_app)
    elif action == "checkpoint":
        manager.checkpoint(session["sessionId"], 1, 0,
                           {"phase": "paused", "summary": "Pause", "nextStep": "Continue"})
    else:
        settings = deepcopy(session["settings"])
        if action == "settings":
            settings["nextStep"] = "New next step"
        else:
            settings["task"]["completionCriteria"][0]["description"] = "Another check"
        manager.save(session["sessionId"], 1, settings)
    with pytest.raises(SessionError, match="work_context_changed"):
        start(setup, revision=2, work_revision=2)
    returned = finish(setup, running, revision=2)
    work = returned["work"]["record"]
    assert work["context"]["sessionRevision"] == 1 and returned["work"]["status"] == "stale"
    checked = inspect(setup, revision=2)
    assert not checked["contextMatches"] and checked["coveredCriteria"] == []
    assert "work-context-changed" in checked["reasons"]
    if action == "rebind":
        assert work["units"][0]["afterError"] == "work_target_changed"
        assert checked["artifactVersion"] is None
    else:
        assert checked["units"][0]["changedSinceReturn"] == []


def test_resource_change_is_stale_and_start_rejected(setup, tmp_path, monkeypatch):
    opened(setup)
    resources = tmp_path / "resources.json"
    value = json.loads(execution.RESOURCES.read_text(encoding="utf-8"))
    value["profiles"][next(iter(value["profiles"]))]["label"] += " changed"
    resources.write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setattr(execution, "RESOURCES", resources)
    view = setup[0].resume(session_id=setup[1]["sessionId"])["work"]
    assert "agent-resources-changed" in view["staleReasons"]
    with pytest.raises(SessionError, match="work_context_changed"):
        start(setup)
    assert "work-context-changed" in inspect(setup)["reasons"]


def test_finish_keeps_return_when_capture_fails_without_claiming_valid_sample(setup, monkeypatch):
    opened(setup)
    running = start(setup)
    def fail(*_args):
        raise SessionError("work_files_changed")
    monkeypatch.setattr(files, "capture", fail)
    view = finish(setup, running)
    unit = view["work"]["record"]["units"][0]
    assert unit["result"]["state"] == "returned" and unit["after"] is None
    assert unit["afterError"] == "work_files_changed"
    checked = inspect(setup)
    assert checked["artifactVersion"] is None and checked["coveredCriteria"] == []


def test_work_view_never_prepares_or_reads_application_files(setup, monkeypatch):
    opened(setup)
    def fail(*_args, **_kwargs):
        raise AssertionError("Unexpected application read")
    monkeypatch.setattr(files, "capture", fail)
    monkeypatch.setattr(execution, "prepare", fail)
    view = setup[0].resume(session_id=setup[1]["sessionId"])["work"]
    assert view["status"] == "available" and view["filesChecked"] is False


def test_selected_missing_file_creation_is_a_change(setup):
    opened(setup)
    running = start(setup, assignment(observedFiles=["later.py"]))
    assert running["work"]["record"]["units"][0]["before"]["files"][0]["state"] == "missing"
    (setup[2] / "later.py").write_text("created", encoding="utf-8")
    finish(setup, running)
    assert "work-inputs-changed" in inspect(setup)["units"][0]["reasons"]


def test_failed_criterion_with_zero_command_exit_does_not_cover(setup):
    opened(setup)
    finish(setup, start(setup), report(criteria=[{"id": "C1", "status": "failed", "summary": "Semantic failure"}]))
    checked = inspect(setup)
    assert checked["missingCriteria"] == ["C1"]
    assert "work-criterion-unconfirmed" in checked["units"][0]["reasons"]


def test_pending_run_cannot_be_replaced_and_completed_run_keeps_monotonic_revision(setup):
    manager, session, _ = setup
    opened(setup)
    running = start(setup)
    with pytest.raises(SessionError, match="work_pending"):
        lifecycle.open_work(manager, session["sessionId"], 1, 2)
    finish(setup, running)
    original = manager.resume(session_id=session["sessionId"])["work"]["record"]
    next_run = lifecycle.open_work(manager, session["sessionId"], 1, 3)["work"]["record"]
    assert next_run["revision"] == 4 and next_run["runId"] != original["runId"]
    assert next_run["units"] == []


def test_criterion_reorder_preserves_old_meaning_and_requires_new_run(setup):
    manager, session, _ = setup
    settings = deepcopy(session["settings"])
    settings["task"]["completionCriteria"].append(
        {"description": "List bookings", "method": "automatic", "required": True})
    saved = manager.save(session["sessionId"], 1, settings)["session"]
    lifecycle.open_work(manager, session["sessionId"], 2, 0)
    old = manager.resume(session_id=session["sessionId"])["work"]["record"]
    settings = deepcopy(saved["settings"])
    settings["task"]["completionCriteria"].reverse()
    manager.save(session["sessionId"], 2, settings)
    with pytest.raises(SessionError, match="work_context_changed"):
        start(setup, revision=3)
    retained = manager.resume(session_id=session["sessionId"])["work"]["record"]
    assert retained["criteria"] == old["criteria"]
    assert inspect(setup, revision=3)["coveredCriteria"] == []


def test_manual_and_static_reports_do_not_auto_certify_user_acceptance(setup):
    manager, session, _ = setup
    settings = deepcopy(session["settings"])
    settings["task"]["completionCriteria"] = [
        {"description": "User accepts layout", "method": "manual", "required": True},
        {"description": "Read source", "method": "static", "required": True}]
    manager.save(session["sessionId"], 1, settings)
    lifecycle.open_work(manager, session["sessionId"], 2, 0)
    running = start(setup, assignment(criterionIds=["C1", "C2"]), revision=2)
    finish(setup, running, report(criteria=[
        {"id": "C1", "status": "passed", "summary": "Host claim"},
        {"id": "C2", "status": "passed", "summary": "Host claim"}]), revision=2)
    checked = inspect(setup, revision=2)
    assert checked["coveredCriteria"] == [] and checked["complete"] is False
    assert checked["hostReportsVerified"] is False


def test_rerun_only_affected_check_preserves_independent_criterion_coverage(setup):
    manager, session, app = setup
    settings = deepcopy(session["settings"])
    settings["task"]["completionCriteria"].append(
        {"description": "List bookings", "method": "automatic", "required": True})
    manager.save(session["sessionId"], 1, settings)
    lifecycle.open_work(manager, session["sessionId"], 2, 0)
    first = start(setup, assignment(observedFiles=["app.py"]), revision=2)
    finish(setup, first, revision=2)
    second = start(setup, assignment(observedFiles=["test_app.py"], criterionIds=["C2"]),
                   revision=2, work_revision=3)
    finish(setup, second, report(criteria=[{"id": "C2", "status": "passed", "summary": "Passed"}]), revision=2)
    (app / "app.py").write_text("value = 2\n", encoding="utf-8")
    stale = inspect(setup, revision=2)
    assert stale["coveredCriteria"] == ["C2"] and stale["missingCriteria"] == ["C1"]
    retry = start(setup, assignment(observedFiles=["app.py"], supersedes=first["unitId"]),
                  revision=2, work_revision=5)
    finish(setup, retry, revision=2)
    checked = inspect(setup, revision=2)
    assert checked["coveredCriteria"] == ["C1", "C2"] and checked["reasons"] == []
    assert {unit["unitId"] for unit in checked["units"]} == {second["unitId"], retry["unitId"]}


@pytest.mark.parametrize("kind", ["implementation", "review"])
def test_failed_criterion_in_successful_host_return_is_not_erased_by_other_passing_check(setup, kind):
    opened(setup)
    running = start(setup, assignment(kind))
    finish(setup, running, report(criteria=[{"id": "C1", "status": "failed", "summary": "Failure found"}]))
    finish(setup, start(setup, work_revision=3))
    checked = inspect(setup)
    assert "work-failed" in checked["units"][0]["reasons"]
    assert "work-failed:" + running["unitId"] in checked["reasons"]
    assert checked["complete"] is False


@pytest.mark.parametrize("observed,reported", [(True, False), (False, True), (True, True)])
def test_retry_keeps_historical_scope_violation_until_explicit_new_run(setup, observed, reported):
    manager, session, app = setup
    opened(setup)
    first = start(setup, assignment("implementation"))
    if observed:
        (app / "test_app.py").write_text("assert False\n", encoding="utf-8")
    finish(setup, first, report(changedFiles=["outside.py"] if reported else []))
    retry = start(setup, assignment("implementation", supersedes=first["unitId"]), work_revision=3)
    finish(setup, retry)
    verification = start(setup, work_revision=5)
    finish(setup, verification)
    checked = inspect(setup)
    historical = next(unit for unit in checked["units"] if unit["unitId"] == first["unitId"])
    assert historical["historical"] is True and historical["supersededBy"] == retry["unitId"]
    assert historical["reasons"] == ["work-out-of-scope"] and not historical["sampleMatches"]
    assert historical["changedSinceReturn"] == []
    assert historical["observedOutOfScopeFiles"] == (["test_app.py"] if observed else [])
    assert historical["reportedOutOfScopeFiles"] == (["outside.py"] if reported else [])
    assert "work-out-of-scope:" + first["unitId"] in checked["reasons"]
    assert checked["coveredCriteria"] == ["C1"]  # Passing check does not erase the historical violation.
    assert all(not unit["historical"] and unit["supersededBy"] is None
               for unit in checked["units"] if unit["unitId"] != first["unitId"])
    reopened = lifecycle.open_work(manager, session["sessionId"], 1, 7)
    assert reopened["work"]["revision"] == 8 and reopened["work"]["record"]["units"] == []
    assert not any(reason.startswith("work-out-of-scope") for reason in inspect(setup)["reasons"])
