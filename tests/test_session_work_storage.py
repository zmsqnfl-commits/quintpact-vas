"""Work record CAS, atomicity, recovery and read-only inspection races."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_session_work import ROOT, assignment, finish, inspect, opened, report, setup, start
import vas_session_execution as execution
import vas_session_store as store
import vas_session_work as lifecycle
import vas_work_contract as contract
import vas_work_files as files
from vas_ai_contract import canonical
from vas_session import SessionError, SessionManager
from vas_session_web import dispatch


def corrupt(setup, change):
    manager, session, _ = setup
    manager.store.mutate(lambda data: change(data["sessions"][session["sessionId"]]))


@pytest.mark.parametrize("expected", [True, "1", 1.0, -1, 0, 2])
def test_work_revision_is_independent_and_strict_without_partial_commit(setup, expected):
    opened(setup)
    before = setup[0].store.path.read_bytes()
    with pytest.raises(SessionError, match="work_revision_invalid|work_revision_conflict"):
        start(setup, work_revision=expected)
    assert setup[0].store.path.read_bytes() == before


def test_two_concurrent_starts_same_work_revision_have_exactly_one_winner(setup):
    opened(setup)
    def attempt(_):
        try:
            return start(setup)["work"]["revision"]
        except SessionError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert results.count(2) == 1 and results.count("work_revision_conflict") == 1
    assert len(setup[0].resume(session_id=setup[1]["sessionId"])["work"]["record"]["units"]) == 1


@pytest.mark.parametrize("action", ["start", "finish", "clear"])
def test_atomic_write_failure_preserves_complete_previous_bytes(setup, monkeypatch, action):
    opened(setup)
    running = start(setup) if action == "finish" else None
    before = setup[0].store.path.read_bytes()
    def fail(*_args):
        raise OSError("private path must not escape")
    monkeypatch.setattr(store.os, "replace", fail)
    with pytest.raises(store.SessionStoreError, match="session_store_write_failed"):
        if action == "start":
            start(setup)
        elif action == "finish":
            finish(setup, running)
        else:
            lifecycle.clear_work(setup[0], setup[1]["sessionId"], 1, 1)
    assert setup[0].store.path.read_bytes() == before
    assert not list(setup[0].store.directory.glob(".sessions-*.tmp"))


@pytest.mark.parametrize("cap", ["work", "store"])
def test_byte_caps_preserve_previous_bytes(setup, monkeypatch, cap):
    view = opened(setup)
    before = setup[0].store.path.read_bytes()
    if cap == "work":
        monkeypatch.setattr(contract, "MAX_BYTES", len(canonical(view["work"]["record"])) + 50)
        error, code = SessionError, "work_too_large"
    else:
        monkeypatch.setattr(store, "MAX_BYTES", len(before) + 50)
        error, code = store.SessionStoreError, "session_store_too_large"
    with pytest.raises(error, match=code):
        start(setup)
    assert setup[0].store.path.read_bytes() == before


def test_union_path_and_unit_limits_do_not_partially_append(setup):
    opened(setup)
    many = [f"module_{index}.py" for index in range(64)]
    first = start(setup, assignment(observedFiles=many))
    before = setup[0].store.path.read_bytes()
    with pytest.raises(SessionError, match="work_too_large"):
        start(setup, assignment(observedFiles=["extra.py"]), work_revision=2)
    assert setup[0].store.path.read_bytes() == before
    for work_revision in range(2, 13):
        start(setup, assignment(observedFiles=[many[0]]), work_revision=work_revision)
    before = setup[0].store.path.read_bytes()
    with pytest.raises(SessionError, match="work_too_large"):
        start(setup, assignment(observedFiles=[many[0]]), work_revision=13)
    assert setup[0].store.path.read_bytes() == before


def test_invalid_work_is_isolated_and_explicitly_recoverable_without_raw_leak(setup, tmp_path):
    manager, session, _ = setup
    opened(setup)
    other_target = tmp_path / "other-app"
    other_target.mkdir()
    second = manager.create(session["settings"], other_target)["session"]
    corrupt(setup, lambda record: record.update(work={"revision": 999, "secret": "CANARY_PRIVATE"}))
    before = manager.store.path.read_bytes()
    broken = manager.resume(session_id=session["sessionId"])
    assert broken["work"]["status"] == "invalid" and broken["work"]["revision"] is None
    assert "CANARY_PRIVATE" not in json.dumps(broken)
    assert inspect(setup)["reasons"] == ["work-invalid"]
    assert manager.resume(session_id=second["sessionId"])["status"] == "resumed"
    assert manager.export(session["sessionId"]) == session
    assert manager.store.path.read_bytes() == before
    with pytest.raises(SessionError, match="work_invalid"):
        lifecycle.clear_work(manager, session["sessionId"], 1, 999)
    cleared = lifecycle.clear_work(manager, session["sessionId"], 1, -1)
    assert "work" not in cleared and cleared["session"]["revision"] == 2
    assert "CANARY_PRIVATE" not in manager.store.path.read_text(encoding="utf-8")
    assert cleared["session"]["settings"] == session["settings"]


def test_clear_preserves_progress_and_settings_and_guards_forget(setup):
    manager, session, _ = setup
    manager.checkpoint(session["sessionId"], 1, 0,
                       {"phase": "paused", "summary": "Reference only", "nextStep": "Resume check"})
    opened_view = lifecycle.open_work(manager, session["sessionId"], 2, 0)
    original = opened_view["session"]["settings"]
    with pytest.raises(SessionError, match="work_revision"):
        manager.forget(session["sessionId"], 2)
    cleared = lifecycle.clear_work(manager, session["sessionId"], 2, 1)
    assert "work" not in cleared and "progress" in cleared
    assert cleared["session"]["settings"] == original and cleared["session"]["revision"] == 3
    with pytest.raises(SessionError, match="revision_conflict"):
        manager.forget(session["sessionId"], 2)
    manager.forget(session["sessionId"], 3)
    assert manager.store.read()["sessions"] == {}


def test_clear_recovers_missing_target_and_absent_work_noop(setup):
    manager, session, app = setup
    before = manager.store.path.read_bytes()
    assert "work" not in lifecycle.clear_work(manager, session["sessionId"], 1, 0)
    assert manager.store.path.read_bytes() == before
    opened(setup)
    for file in app.iterdir():
        file.unlink()
    app.rmdir()
    cleared = lifecycle.clear_work(manager, session["sessionId"], 1, 1)
    assert cleared["status"] == "target_unavailable" and "work" not in cleared


def test_changed_privacy_rules_require_review_before_open_or_new_assignment(setup):
    manager, session, _ = setup
    corrupt(setup, lambda record: record["document"]["settings"]["task"].update(
        request='Password: "secret-demo-value"'))
    before = manager.store.path.read_bytes()
    assert manager.resume(session_id=session["sessionId"]).get("reviewFields")
    with pytest.raises(SessionError, match="session_review_required"):
        opened(setup)
    assert manager.store.path.read_bytes() == before


def test_text_redaction_is_reported_and_private_work_never_crosses_public_boundaries(setup):
    manager, session, app = setup
    opened(setup)
    running = start(setup, assignment(label='Password: "canary-label"'))
    assert running.get("workReviewFields")
    finished = finish(setup, running, report(summary='API_KEY="canary-token"'))
    assert finished.get("workReviewFields")
    raw = manager.store.path.read_text(encoding="utf-8")
    assert "canary-label" not in raw and "canary-token" not in raw
    for public in (manager.export(session["sessionId"]),
                   execution.prepare(manager, session["sessionId"], 1),
                   dispatch(manager, "get", {"sessionId": session["sessionId"]}),
                   dispatch(manager, "list", {})):
        assert "hostCallId" not in json.dumps(public) and "vas-session-work" not in json.dumps(public)


def test_new_process_resumes_same_work_revision_and_report(setup):
    manager, session, _ = setup
    opened(setup)
    finish(setup, start(setup))
    code = ("import json,sys; from pathlib import Path; from vas_session import SessionManager; "
            "m=SessionManager(Path(sys.argv[1]),Path(sys.argv[2])); "
            "print(json.dumps(m.resume(session_id=sys.argv[3])))")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "scripts"), PYTHONUTF8="1")
    result = subprocess.run([sys.executable, "-c", code, str(manager.root), str(manager.store.home),
                             session["sessionId"]], capture_output=True, text=True, encoding="utf-8", env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == manager.resume(session_id=session["sessionId"])


@pytest.mark.parametrize("mutation", ["settings", "work"])
def test_inspection_never_returns_stale_success_after_concurrent_state_change(setup, monkeypatch, mutation):
    manager, session, _ = setup
    opened(setup)
    finish(setup, start(setup))
    original = files.capture
    def capture_then_mutate(*args):
        sample = original(*args)
        if mutation == "settings":
            manager.save(session["sessionId"], 1, session["settings"])
        else:
            lifecycle.open_work(manager, session["sessionId"], 1, 3)
        return sample
    monkeypatch.setattr(files, "capture", capture_then_mutate)
    with pytest.raises(SessionError, match="revision_conflict" if mutation == "settings" else "work_revision_conflict"):
        inspect(setup)


def test_resource_change_during_before_capture_aborts_append(setup, tmp_path, monkeypatch):
    manager, _, _ = setup
    opened(setup)
    before = manager.store.path.read_bytes()
    resource = tmp_path / "resources.json"
    resource.write_bytes(execution.RESOURCES.read_bytes())
    monkeypatch.setattr(execution, "RESOURCES", resource)
    original = files.capture
    def capture_then_change(*args):
        sample = original(*args)
        resource.write_bytes(resource.read_bytes() + b"\n")
        return sample
    monkeypatch.setattr(files, "capture", capture_then_change)
    with pytest.raises(SessionError, match="work_context_changed"):
        start(setup)
    assert manager.store.path.read_bytes() == before


def test_resource_change_during_inspect_prevents_coverage(setup, tmp_path, monkeypatch):
    opened(setup)
    finish(setup, start(setup))
    resource = tmp_path / "resources.json"
    resource.write_bytes(execution.RESOURCES.read_bytes())
    monkeypatch.setattr(execution, "RESOURCES", resource)
    original = files.capture
    def capture_then_change(*args):
        sample = original(*args)
        resource.write_bytes(resource.read_bytes() + b"\n")
        return sample
    monkeypatch.setattr(files, "capture", capture_then_change)
    checked = inspect(setup)
    assert not checked["contextMatches"] and checked["coveredCriteria"] == []
    assert "work-context-changed" in checked["reasons"]
