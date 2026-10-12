"""Atomic progress persistence, optimistic races, and recovery using local fixtures."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vas_session_store as storage
from vas_session import SessionManager
from vas_session_store import SessionStoreError

MARKER = "storage-fixture-progress-to-remove"


@pytest.fixture
def layout(tmp_path):
    root = tmp_path / "vas"
    (root / "src").mkdir(parents=True)
    (root / "Run-VAS-System.bat").write_text("@echo off", encoding="utf-8")
    (root / "src/vas-hub.html").write_text("VAS", encoding="utf-8")
    target = tmp_path / "app"
    target.mkdir()
    sentinel = target / "sentinel.txt"
    sentinel.write_bytes(b"fixture source stays unchanged")
    manager = SessionManager(root, tmp_path / "state")
    settings = {
        "project": {"name": "Storage fixture", "sourceType": "new"},
        "task": {
            "request": "Implement a fixture list",
            "designScope": {"mode": "new", "scope": "Fixture list"},
            "completionCriteria": [
                {"description": "Read fixture list", "method": "automatic", "required": True}
            ],
        },
        "nextStep": "Prepare fixture work",
    }
    session = manager.create(settings, target)["session"]
    yield manager, session["sessionId"]
    assert list(target.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"fixture source stays unchanged"


def payload(summary=MARKER, next_step="Run fixture checks"):
    return {"phase": "implementing", "summary": summary, "nextStep": next_step}


def checkpoint(layout, raw=None):
    manager, identifier = layout
    current = manager.resume(identifier)
    revision = current.get("progress", {}).get("revision", 0)
    return manager.checkpoint(
        identifier, current["session"]["revision"], revision, raw or payload()
    )


def no_temporary_files(manager):
    assert {item.name for item in manager.store.directory.iterdir()} == {
        "vas-session-store.json", ".lock"
    }


def no_payload_remnants(manager):
    no_temporary_files(manager)
    for path in manager.store.directory.iterdir():
        assert MARKER.encode("utf-8") not in path.read_bytes()


def run_child(layout, code, *arguments):
    manager, identifier = layout
    prefix = """import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from vas_session import SessionError, SessionManager
m = SessionManager(Path(sys.argv[2]), Path(sys.argv[3]))
identifier = sys.argv[4]
"""
    environment = dict(os.environ, PYTHONUTF8="1")
    return subprocess.Popen(
        [sys.executable, "-c", prefix + code, str(ROOT / "scripts"),
         str(manager.root), str(manager.store.home), identifier, *map(str, arguments)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=environment,
    )


def finish(child, expected=0):
    try:
        out, err = child.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        child.kill()
        child.communicate()
        pytest.fail("fixture subprocess did not finish")
    assert child.returncode == expected, err
    return out


def test_checkpoint_survives_new_process_without_duplicate_store(layout):
    manager, _ = layout
    saved = checkpoint(layout)
    before = manager.store.path.read_bytes()
    resumed = json.loads(finish(run_child(
        layout, "print(json.dumps(m.resume(identifier), ensure_ascii=False))"
    )))
    assert resumed == saved
    assert resumed["session"]["settings"]["nextStep"] == "Run fixture checks"
    assert manager.store.path.read_bytes() == before
    no_temporary_files(manager)


def test_checkpoint_store_byte_limit_preserves_both_revisions_and_recovers(layout, monkeypatch):
    manager, identifier = layout
    saved = checkpoint(layout)
    before = manager.store.path.read_bytes()
    with monkeypatch.context() as patch:
        patch.setattr(storage, "MAX_BYTES", len(before) + 128)
        with pytest.raises(SessionStoreError, match="^session_store_too_large$"):
            checkpoint(layout, payload("가" * 200, "Run expanded fixture checks"))
        assert manager.store.path.read_bytes() == before
        assert manager.resume(identifier) == saved
        no_temporary_files(manager)
    recovered = checkpoint(layout, payload("Recovered fixture progress", "Retry fixture checks"))
    assert recovered["session"]["revision"] == saved["session"]["revision"] + 1
    assert recovered["progress"]["revision"] == saved["progress"]["revision"] + 1
    assert recovered["session"]["settings"]["nextStep"] == "Retry fixture checks"
    no_temporary_files(manager)


@pytest.mark.parametrize("operation", ["checkpoint", "clear", "forget"])
def test_replace_failure_preserves_settings_progress_and_allows_retry(
    layout, monkeypatch, operation
):
    manager, identifier = layout
    saved = checkpoint(layout)
    before = manager.store.path.read_bytes()

    def mutate():
        if operation == "checkpoint":
            return checkpoint(layout, payload("Replacement fixture", "Review replacement"))
        if operation == "clear":
            return manager.clear_progress(identifier, saved["session"]["revision"])
        return manager.forget(identifier, saved["session"]["revision"])

    def broken_replace(*_args):
        raise OSError("fixture storage replacement failure")

    with monkeypatch.context() as patch:
        patch.setattr(storage.os, "replace", broken_replace)
        with pytest.raises(SessionStoreError, match="^session_store_write_failed$"):
            mutate()
        assert manager.store.path.read_bytes() == before
        assert manager.resume(identifier) == saved
        no_temporary_files(manager)
    recovered = mutate()
    if operation == "checkpoint":
        assert recovered["session"]["revision"] == saved["session"]["revision"] + 1
        assert recovered["progress"]["revision"] == saved["progress"]["revision"] + 1
        assert recovered["session"]["settings"]["nextStep"] == "Review replacement"
    elif operation == "clear":
        assert "progress" not in recovered
        assert recovered["session"]["settings"] == saved["session"]["settings"]
    else:
        assert recovered["status"] == "forgotten"
        assert manager.store.read()["sessions"] == {}
    no_payload_remnants(manager)


@pytest.mark.parametrize("operation", ["clear", "forget"])
def test_progress_removal_cleans_payload_and_abandoned_temporary_files(layout, operation):
    manager, identifier = layout
    saved = checkpoint(layout)
    abandoned = manager.store.directory / ".sessions-abandoned.tmp"
    abandoned.write_text(MARKER, encoding="utf-8")
    if operation == "clear":
        cleared = manager.clear_progress(identifier, saved["session"]["revision"])
        assert "progress" not in cleared
        assert "progress" not in manager.store.read()["sessions"][identifier]
        assert cleared["session"]["revision"] == saved["session"]["revision"] + 1
        assert cleared["session"]["settings"] == saved["session"]["settings"]
    else:
        assert manager.forget(identifier, saved["session"]["revision"])["status"] == "forgotten"
        assert manager.resume() == {"status": "empty"}
    no_payload_remnants(manager)


def test_two_processes_with_same_revisions_commit_exactly_one_checkpoint(layout):
    manager, identifier = layout
    saved = checkpoint(layout)
    session_revision = saved["session"]["revision"]
    progress_revision = saved["progress"]["revision"]
    code = """print("ready", flush=True)
sys.stdin.readline()
raw = {"phase": "implementing", "summary": "Writer " + sys.argv[7],
       "nextStep": "Review writer " + sys.argv[7]}
try:
    value = m.checkpoint(identifier, int(sys.argv[5]), int(sys.argv[6]), raw)
    print(json.dumps({"status": "saved", "value": value}))
except SessionError as error:
    print(json.dumps({"status": "error", "code": error.code}))
"""
    children = [run_child(layout, code, session_revision, progress_revision, writer)
                for writer in ("one", "two")]
    try:
        for child in children:
            assert child.stdout.readline().strip() == "ready"
        for child in children:
            child.stdin.write("\n")
            child.stdin.flush()
        outputs = [json.loads(finish(child)) for child in children]
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.communicate()
    assert sorted(item["status"] for item in outputs) == ["error", "saved"]
    conflict = next(item for item in outputs if item["status"] == "error")
    assert conflict["code"] == "revision_conflict"
    winner = next(item["value"] for item in outputs if item["status"] == "saved")
    current = manager.resume(identifier)
    assert current == winner
    assert current["session"]["revision"] == session_revision + 1
    assert current["progress"]["revision"] == progress_revision + 1
    no_temporary_files(manager)


def test_process_exit_during_checkpoint_keeps_snapshot_and_next_write_recovers(layout):
    manager, identifier = layout
    saved = checkpoint(layout)
    before = manager.store.path.read_bytes()
    code = """os.fsync = lambda _fd: os._exit(29)
m.checkpoint(identifier, int(sys.argv[5]), int(sys.argv[6]),
             {"phase": "implementing", "summary": "Interrupted fixture write",
              "nextStep": "Uncommitted fixture next step"})
"""
    finish(run_child(layout, code, saved["session"]["revision"],
                     saved["progress"]["revision"]), expected=29)
    assert manager.store.path.read_bytes() == before
    assert manager.resume(identifier) == saved
    assert list(manager.store.directory.glob(".sessions-*.tmp"))
    recovered = checkpoint(layout, payload("Recovered fixture", "Check recovered fixture"))
    assert recovered["session"]["revision"] == saved["session"]["revision"] + 1
    assert recovered["progress"]["revision"] == saved["progress"]["revision"] + 1
    assert recovered["session"]["settings"]["nextStep"] == "Check recovered fixture"
    no_temporary_files(manager)
