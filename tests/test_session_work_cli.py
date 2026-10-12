"""CLI handoff binding and private work records across fresh processes."""
from copy import deepcopy
import json
import subprocess
import sys

import pytest

from test_chat_session import run_cli, successful_cli
from test_session_execution import result
from test_session_work import setup, assignment, report, opened, start, finish, inspect
from test_session_progress_cli import progress
from vas_session import SessionError
from vas_session_execution import assess, prepare
from vas_session_web import dispatch
import vas_session_work as lifecycle
import vas_session_execution as execution


def cli(setup, *args, data=None):
    manager, _, app = setup
    return successful_cli((manager.root, manager.store.home, app), *args, data=data)


def work(setup, action, number=None, payload=None, unit=None):
    manager, session, _ = setup
    args = ["work", action, "--session", session["sessionId"], "--expected-revision",
            str(manager.resume(session["sessionId"])["session"]["revision"])]
    if number is not None:
        args += ["--expected-work-revision", str(number)]
    if unit:
        args += ["--unit", unit]
    return cli(setup, *args, data=payload)


def final_report(prepared, inspected):
    value = result(prepared)
    value["artifactVersion"] = inspected["artifactVersion"]
    for item in value["evidence"]:
        item["artifactVersion"] = inspected["artifactVersion"]
    return value


def test_real_command_fresh_cli_assessment_rejects_post_test_change_and_reuses_only_retry(setup):
    manager, session, app = setup
    (app / "test_app.py").write_text("import app\nassert app.value == 2\n", encoding="utf-8")
    prepared = prepare(manager, session["sessionId"], 1)
    work(setup, "open", 0)
    implementation = work(setup, "start", 1, assignment("implementation"))
    (app / "app.py").write_text("value = 2\n", encoding="utf-8")
    work(setup, "finish", 2, report(changedFiles=["app.py"], criteria=[], exitCode=None),
         implementation["unitId"])
    checking = work(setup, "start", 3, assignment(command="python -B test_app.py"))
    executed = subprocess.run([sys.executable, "-B", "test_app.py"], cwd=app, capture_output=True)
    assert executed.returncode == 0, executed.stderr
    work(setup, "finish", 4, report(), checking["unitId"])
    inspected = work(setup, "inspect")
    assert inspected["reasons"] == [] and inspected["coveredCriteria"] == ["C1"]
    assert inspected["hostReportsVerified"] is False and inspected["complete"] is False
    submitted = final_report(prepared, inspected)
    before_store = manager.store.path.read_bytes()
    response = cli(setup, "assess", "--session", session["sessionId"], "--expected-revision", "1", data=submitted)
    assert response["assessment"]["status"] == "needs-verification"
    assert response["workChecks"]["reasons"] == []
    assert manager.store.path.read_bytes() == before_store

    # Even a harmless source edit makes the earlier sample stale.
    (app / "app.py").write_text("value = 2  # inspected code changed\n", encoding="utf-8")
    stale = cli(setup, "assess", "--session", session["sessionId"], "--expected-revision", "1", data=submitted)
    assert stale["assessment"]["status"] == "incomplete"
    assert "work-artifact-mismatch" in stale["assessment"]["reasons"]
    assert any(reason.startswith("work-files-changed:") for reason in stale["assessment"]["reasons"])
    retry = work(setup, "start", 5, assignment(command="python -B test_app.py", supersedes=checking["unitId"]))
    assert subprocess.run([sys.executable, "-B", "test_app.py"], cwd=app).returncode == 0
    work(setup, "finish", 6, report(hostCallId="call-retry"), retry["unitId"])
    current = work(setup, "inspect")
    assert current["reasons"] == []
    assert {unit["unitId"] for unit in current["units"]} == {implementation["unitId"], retry["unitId"]}
    assert len(manager.resume(session["sessionId"])["work"]["record"]["units"]) == 3
    response = assess(manager, session["sessionId"], 1, final_report(prepared, current))
    assert response["assessment"]["status"] == "needs-verification"


def test_work_is_local_and_checkpoint_keeps_historical_context_without_current_claim(setup):
    manager, session, app = setup
    original_app = {path.name: path.read_bytes() for path in app.iterdir()}
    opened(setup)
    finish(setup, start(setup, assignment(label="PrivateWorkMarker")))
    before = manager.store.path.read_bytes()
    public = [manager.export(session["sessionId"]), prepare(manager, session["sessionId"], 1),
              dispatch(manager, "get", {"sessionId": session["sessionId"]}),
              dispatch(manager, "list", {})]
    for value in public:
        text = json.dumps(value)
        assert "PrivateWorkMarker" not in text and "targetBindingSha256" not in text
        assert "vas-session-work" not in text
    assert manager.store.path.read_bytes() == before
    saved = manager.checkpoint(session["sessionId"], 1, 0, progress())
    assert saved["work"]["status"] == "stale" and saved["work"]["record"]["context"]["sessionRevision"] == 1
    assert saved["progress"]["filesVerified"] is False
    check = work(setup, "inspect")
    assert "work-context-changed" in check["reasons"]
    assert check["units"][0]["sampleMatches"] is True
    assert check["units"][0]["changedSinceReturn"] == []
    assert check["coveredCriteria"] == []
    assert {path.name: path.read_bytes() for path in app.iterdir()} == original_app


@pytest.mark.parametrize("raw", [
    '{"kind":"review","kind":"verification"}',
    '{"kind":"review","role":"reviewer","mode":"direct","label":"check","observedFiles":["app.py"],"approved":true}',
    '{"kind":"review","role":"reviewer","mode":"direct","label":"check","observedFiles":["../outside.txt"]}',
], ids=["duplicate-key", "unknown-field", "unsafe-selector"])
def test_invalid_cli_work_input_never_overwrites_snapshot(setup, raw):
    manager, session, app = setup
    opened(setup)
    before = manager.store.path.read_bytes()
    response = run_cli((manager.root, manager.store.home, app), "work", "start", "--session",
                       session["sessionId"], "--expected-revision", "1", "--expected-work-revision", "1", raw=raw)
    assert response.returncode == 1
    assert json.loads(response.stdout)["status"] == "error"
    assert manager.store.path.read_bytes() == before


def test_forget_requires_latest_work_revision_and_clears_all_state(setup):
    manager, session, app = setup
    opened(setup)
    pending = start(setup)
    before = manager.store.path.read_bytes()
    for expected in (None, 1, True):
        with pytest.raises(SessionError, match="work_revision_conflict"):
            manager.forget(session["sessionId"], 1, expected)
        assert manager.store.path.read_bytes() == before
    finish(setup, pending)
    response = cli(setup, "forget", "--session", session["sessionId"], "--expected-revision", "1",
                   "--expected-work-revision", "3")
    assert response["status"] == "forgotten"
    assert manager.store.read()["sessions"] == {}
    assert (app / "app.py").exists()


def test_assess_rechecks_independent_work_revision_after_inspection(setup, monkeypatch):
    manager, session, _ = setup
    opened(setup)
    finish(setup, start(setup))
    prepared = prepare(manager, session["sessionId"], 1)
    inspection = inspect(setup)
    original = lifecycle.inspect_work
    def concurrent(*args):
        observed = original(*args)
        lifecycle.start_work(manager, session["sessionId"], 1, 3,
                             assignment(kind="review", role="reviewer", command=""))
        return observed
    monkeypatch.setattr(lifecycle, "inspect_work", concurrent)
    with pytest.raises(SessionError, match="work_revision_conflict"):
        assess(manager, session["sessionId"], 1, final_report(prepared, inspection))


def test_assess_rejects_work_opened_after_observing_absent_work(setup, monkeypatch):
    manager, session, _ = setup
    prepared = prepare(manager, session["sessionId"], 1)
    original_current, original_evaluate = execution._current, execution.evaluate_result
    evaluating, injected = False, False

    def evaluate(*args):
        nonlocal evaluating
        evaluating = True
        return original_evaluate(*args)

    def concurrent(*args):
        nonlocal injected
        observed = original_current(*args)
        if evaluating and not injected:
            injected = True
            opened(setup)
        return observed

    monkeypatch.setattr(execution, "evaluate_result", evaluate)
    monkeypatch.setattr(execution, "_current", concurrent)
    with pytest.raises(SessionError, match="work_revision_conflict"):
        assess(manager, session["sessionId"], 1, result(prepared))
    assert injected


def test_review_failure_cannot_be_masked_by_passing_verification(setup):
    manager, session, _ = setup
    opened(setup)
    review = start(setup, assignment(kind="review", role="reviewer", command=""))
    finish(setup, review, report(criteria=[{"id": "C1", "status": "failed", "summary": "Bug reproduced"}]))
    finish(setup, start(setup, work_revision=3))
    checks = inspect(setup)
    response = assess(manager, session["sessionId"], 1,
                      final_report(prepare(manager, session["sessionId"], 1), checks))
    assert response["assessment"]["status"] == "incomplete"
    assert any(reason.startswith("work-failed:") for reason in response["assessment"]["reasons"])


def test_invalid_work_is_hidden_and_explicit_recovery_forget_works(setup):
    manager, session, app = setup
    opened(setup)
    manager.store.mutate(lambda data: data["sessions"][session["sessionId"]].update(
        work={"raw": "PrivateDamagedWorkMarker"}))
    response = cli(setup, "resume", "--session", session["sessionId"])
    assert response["work"]["status"] == "invalid"
    assert "PrivateDamagedWorkMarker" not in json.dumps(response)
    checked = work(setup, "inspect")
    assert checked["reasons"] == ["work-invalid"]
    with pytest.raises(SessionError, match="work_revision_conflict"):
        manager.forget(session["sessionId"], 1)
    deleted = cli(setup, "forget", "--session", session["sessionId"], "--expected-revision", "1",
                  "--expected-work-revision", "-1")
    assert deleted["status"] == "forgotten" and (app / "app.py").exists()
