"""Persistence isolation, process locking, corruption and failure regression tests."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vas_session_store as module
from vas_session_store import SessionStoreError, Store


@pytest.fixture
def store(tmp_path):
    root = tmp_path / "vas"
    root.mkdir()
    return Store(root, tmp_path / "private")


def write(store, name="one", **fields):
    return store.mutate(lambda value: value["sessions"].update({name: fields}))


def expect_error(code, action):
    with pytest.raises(SessionStoreError) as caught:
        action()
    assert caught.value.code == "session_store_" + code
    assert str(caught.value) == caught.value.code


def test_read_missing_store_never_creates_files(store):
    value = store.read()
    assert value == {"format": "vas-chat-store", "schemaVersion": 1,
                     "rootKey": store.root_key, "sessions": {}}
    assert not store.home.exists()
    value["sessions"]["changed"] = {}
    assert not store.read()["sessions"]


def test_mutate_round_trip_returns_callback_result(store):
    def mutation(value):
        value["sessions"]["one"] = {"goal": "예약 앱", "revision": 1}
        return "saved"
    assert store.mutate(mutation) == "saved"
    assert Store(store.root, store.home).read()["sessions"]["one"]["goal"] == "예약 앱"
    assert not list(store.directory.glob("*.tmp"))
    assert store.lock_path.read_bytes() == b""


def test_separate_roots_do_not_share_sessions(store, tmp_path):
    other_root = tmp_path / "another-vas"
    other_root.mkdir()
    other = Store(other_root, store.home)
    write(store, goal="one")
    write(other, goal="two")
    assert store.root_key != other.root_key
    assert store.read()["sessions"]["one"]["goal"] == "one"
    assert other.read()["sessions"]["one"]["goal"] == "two"


def test_root_binding_rejects_copied_store(store, tmp_path):
    write(store)
    other_root = tmp_path / "other"
    other_root.mkdir()
    other = Store(other_root, store.home)
    other.directory.mkdir()
    other.path.write_bytes(store.path.read_bytes())
    expect_error("invalid", other.read)


@pytest.mark.parametrize("location", ["", "nested"])
def test_state_inside_product_is_rejected(store, location):
    expect_error("path_invalid", lambda: Store(store.root, store.root / location))


def test_non_directory_root_is_rejected(tmp_path):
    root = tmp_path / "file"
    root.write_text("data")
    expect_error("path_invalid", lambda: Store(root, tmp_path / "private"))


def test_existing_user_parents_keep_permissions(store):
    if os.name == "nt":
        write(store)
        assert store.path.is_file()
        return
    store.home.mkdir(mode=0o755)
    store.home.chmod(0o755)
    write(store)
    assert stat.S_IMODE(store.home.stat().st_mode) == 0o755
    assert stat.S_IMODE(store.directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.lock_path.stat().st_mode) == 0o600


def test_callback_exception_keeps_existing_bytes(store):
    write(store, goal="before")
    before = store.path.read_bytes()
    def broken(value):
        value["sessions"]["one"]["goal"] = "after"
        raise RuntimeError("callback failure")
    with pytest.raises(RuntimeError, match="callback failure"):
        store.mutate(broken)
    assert store.path.read_bytes() == before
    write(store, goal="recovered")


def test_replace_failure_preserves_original_and_removes_temp(store, monkeypatch):
    write(store, goal="before")
    before = store.path.read_bytes()
    def broken(*_args):
        raise OSError("private path must not appear in result")
    monkeypatch.setattr(module.os, "replace", broken)
    expect_error("write_failed", lambda: write(store, goal="after"))
    assert store.path.read_bytes() == before
    assert not list(store.directory.glob("*.tmp"))


def test_fsync_failure_preserves_original_and_removes_temp(store, monkeypatch):
    write(store, goal="before")
    before = store.path.read_bytes()
    monkeypatch.setattr(module.os, "fsync", lambda *_: (_ for _ in ()).throw(OSError()))
    expect_error("write_failed", lambda: write(store, goal="after"))
    assert store.path.read_bytes() == before
    assert not list(store.directory.glob("*.tmp"))


@pytest.mark.parametrize("raw", [b"{", b"\xff", b'[]', b'{"schemaVersion":1,"schemaVersion":1}',
                                  b'{"nested":{"value":1,"value":2}}'])
def test_corruption_is_not_reset_or_overwritten(store, raw):
    write(store)
    store.path.write_bytes(raw)
    expect_error("invalid", store.read)
    expect_error("invalid", lambda: write(store, goal="no overwrite"))
    assert store.path.read_bytes() == raw


@pytest.mark.parametrize("field,value", [("schemaVersion", True), ("schemaVersion", 2),
                                        ("schemaVersion", "1"), ("format", "other"),
                                        ("sessions", []), ("rootKey", "wrong")])
def test_invalid_envelope_rejected(store, field, value):
    expect_error("invalid", lambda: store.mutate(lambda doc: doc.update({field: value})))
    assert not store.path.exists()


def test_unknown_top_level_and_non_object_record_rejected(store):
    expect_error("invalid", lambda: store.mutate(lambda doc: doc.update(extra="value")))
    expect_error("invalid", lambda: store.mutate(lambda doc: doc["sessions"].update(one=[])))


def test_non_finite_json_rejected_on_read_and_write(store):
    expect_error("invalid", lambda: write(store, value=float("nan")))
    write(store)
    doc = store.read()
    doc["sessions"]["one"]["value"] = float("inf")
    store.path.write_text(json.dumps(doc), encoding="utf-8")
    expect_error("invalid", store.read)


def test_serialization_cannot_introduce_duplicate_keys(store):
    expect_error("invalid", lambda: write(store, nested={1: "one", "1": "another"}))
    assert not store.path.exists()


def test_limits_preserve_original(store, monkeypatch):
    write(store, goal="before")
    before = store.path.read_bytes()
    expect_error("too_large", lambda: store.mutate(
        lambda doc: doc["sessions"].update({str(index): {} for index in range(65)})))
    monkeypatch.setattr(module, "MAX_BYTES", 1024)
    expect_error("too_large", lambda: write(store, goal="x" * 1024))
    assert store.path.read_bytes() == before
    store.path.write_bytes(b" " * 1025)
    expect_error("too_large", store.read)


def test_hardlinked_store_file_rejected(store, tmp_path):
    write(store)
    alias = tmp_path / "alias.json"
    os.link(store.path, alias)
    expect_error("path_invalid", store.read)
    expect_error("path_invalid", lambda: write(store))


def test_hardlinked_lock_rejected(store, tmp_path):
    write(store)
    os.link(store.lock_path, tmp_path / "lock-alias")
    expect_error("path_invalid", lambda: write(store))


@pytest.mark.parametrize("component", ["root", "directory", "path", "lock_path"])
def test_reparse_components_rejected_before_resolve(store, monkeypatch, component):
    write(store)
    target = getattr(store, component)
    original = Path.lstat
    def fake_lstat(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == target:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400, st_nlink=1)
        return info
    monkeypatch.setattr(Path, "lstat", fake_lstat)
    expect_error("path_invalid", store.read)
    expect_error("path_invalid", lambda: Store(store.root, store.home))


def test_symbolic_link_ancestor_rejected_when_available(store, tmp_path):
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(store.root, target_is_directory=True)
    except OSError:
        # The mocked Windows reparse tests above still exercise every component on such hosts.
        return
    expect_error("path_invalid", lambda: Store(alias, store.home))


def test_delete_does_not_leave_old_state_backup(store):
    write(store, goal="private deleted value")
    store.mutate(lambda doc: doc["sessions"].clear())
    assert store.read()["sessions"] == {}
    for path in store.directory.iterdir():
        assert b"private deleted value" not in path.read_bytes()
    assert {item.name for item in store.directory.iterdir()} == {"vas-session-store.json", ".lock"}


def test_abandoned_temp_is_removed_on_next_locked_update(store):
    write(store, goal="before")
    leftover = store.directory / ".sessions-crashed.tmp"
    leftover.write_bytes(b"private old data")
    store.mutate(lambda doc: doc["sessions"].clear())
    assert not leftover.exists()
    assert {item.name for item in store.directory.iterdir()} == {"vas-session-store.json", ".lock"}


def process(store, code):
    prefix = "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from vas_session_store import Store; s=Store(Path(sys.argv[2]), Path(sys.argv[3])); "
    return subprocess.Popen([sys.executable, "-c", prefix + code, str(ROOT / "scripts"),
                             str(store.root), str(store.home)], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True, encoding="utf-8")


def finish(child, expected=0):
    out, err = child.communicate(timeout=30)
    assert child.returncode == expected, err
    return out


def test_new_process_can_resume(store):
    write(store, goal="persisted", revision=1)
    out = finish(process(store, "print(s.read()['sessions']['one']['goal'])"))
    assert out.strip() == "persisted"


def test_concurrent_process_updates_are_not_lost(store):
    write(store, counter=0)
    code = "\nfor _ in range(12):\n s.mutate(lambda doc: doc['sessions']['one'].update(counter=doc['sessions']['one']['counter']+1))"
    children = [process(store, code) for _ in range(4)]
    for child in children:
        finish(child)
    assert store.read()["sessions"]["one"]["counter"] == 48


def test_process_exit_releases_os_lock_and_keeps_previous_state(store):
    write(store, goal="before")
    finish(process(store, "import os; s.mutate(lambda doc: os._exit(23))"), expected=23)
    assert store.read()["sessions"]["one"]["goal"] == "before"
    write(store, goal="after")
    assert store.read()["sessions"]["one"]["goal"] == "after"


def test_contended_lock_reports_busy_without_changing_state(store, monkeypatch):
    write(store, goal="before")
    child = process(store, "s.mutate(lambda doc: (print('locked', flush=True), sys.stdin.readline()))")
    assert child.stdout.readline().strip() == "locked"
    try:
        monkeypatch.setattr(module, "LOCK_TIMEOUT", 0.1)
        expect_error("busy", lambda: write(store, goal="after"))
        assert store.read()["sessions"]["one"]["goal"] == "before"
    finally:
        child.stdin.write("\n")
        child.stdin.flush()
        finish(child)


def test_exit_during_write_keeps_original_and_next_write_cleans_temp(store):
    write(store, goal="before")
    code = "import os; os.fsync=lambda fd: os._exit(29); s.mutate(lambda doc: doc['sessions']['one'].update(goal='after'))"
    finish(process(store, code), expected=29)
    assert store.read()["sessions"]["one"]["goal"] == "before"
    assert list(store.directory.glob(".sessions-*.tmp"))
    store.mutate(lambda doc: doc["sessions"].clear())
    assert not list(store.directory.glob(".sessions-*.tmp"))


def test_default_home_uses_platform_state_location(tmp_path, monkeypatch):
    root = tmp_path / "vas"
    root.mkdir()
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
        expected = tmp_path / "local/VAS/chat-sessions"
    else:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "local"))
        expected = tmp_path / "local/VAS/chat-sessions"
    store = Store(root)
    assert store.home == expected
    assert not store.home.exists()
