"""Real project prompt CAS, privacy rejection, process locks and failed-write retention."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vas_project_prompt as store


@pytest.fixture
def engine(tmp_path):
    result = tmp_path / "이름 바꾼 재고 앱" / ".vas"
    (result / "src").mkdir(parents=True)
    (result.parent / "src").mkdir()
    (result / "Run-VAS-System.bat").write_text("@echo off\n")
    (result / "src/vas-hub.html").write_text("VAS")
    (result / "project-layout.json").write_text('{"layout":"vas-project","version":1}', encoding="utf-8")
    return result


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def call(engine, operation, payload=None):
    return subprocess.run([sys.executable, "-B", str(ROOT / "scripts/vas-project-prompt.py"),
                           "--vas-root", str(engine), operation],
                          input=json.dumps(payload).encode() if payload is not None else None,
                          capture_output=True, timeout=10)


def test_get_is_read_only_and_saved_text_clears_without_erasing_revision(engine):
    before = tree(engine.parent)
    assert store.read_project_prompt(engine) == {"revision": 0, "prompt": ""}
    assert tree(engine.parent) == before
    value = store.save_project_prompt(engine, 0, "  재고 목록\r\n  합계 표시\t유지  ")
    assert value == {"revision": 1, "prompt": "재고 목록\n  합계 표시 유지"}
    assert store.read_project_prompt(engine) == value
    assert store.save_project_prompt(engine, 1, "") == {"revision": 2, "prompt": ""}
    assert tree(engine) == {key[5:]: raw for key, raw in before.items() if key.startswith(".vas/")}
    assert {p.name for p in engine.parent.iterdir()} == {".vas", "src", store.FILE_NAME}


def test_stale_revision_does_not_overwrite_latest_prompt(engine):
    store.save_project_prompt(engine, 0, "최신 지시")
    original = tree(engine.parent)
    with pytest.raises(store.ProjectPromptError, match="project_prompt_conflict"):
        store.save_project_prompt(engine, 0, "오래된 탭")
    assert tree(engine.parent) == original


@pytest.mark.parametrize("value", [
    "api_key=sk-proj-FakeCanary123456789", "Contact test@example.com",
    "Read C:\\Users\\demo\\private.txt", "Read /home/demo/private.txt", "Read /tmp/private",
    "password%3DEncodedCanary", '"password":"NotARealSecret"', "전화 010-1234-5678",
])
def test_sensitive_input_is_rejected_without_any_partial_write_or_echo(engine, value):
    store.save_project_prompt(engine, 0, "Keep stock table")
    before = tree(engine.parent)
    with pytest.raises(store.ProjectPromptError, match="^project_prompt_sensitive$"):
        store.save_project_prompt(engine, 1, value)
    result = call(engine, "save", {"expectedRevision": 1, "prompt": value})
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"status": "error", "code": "project_prompt_sensitive"}
    assert value.encode() not in result.stdout + result.stderr
    assert tree(engine.parent) == before


@pytest.mark.parametrize("value,code", [
    ("x" * 4001, "too_large"), (["task"], "invalid"), ("task\x00secret", "invalid"),
    ("\ud800", "invalid"),
])
def test_bad_text_is_rejected(engine, value, code):
    before = tree(engine.parent)
    with pytest.raises(store.ProjectPromptError, match="project_prompt_" + code):
        store.save_project_prompt(engine, 0, value)
    assert tree(engine.parent) == before


@pytest.mark.parametrize("revision", [True, False, 1.0, "0", -1, store.MAX_REVISION])
def test_revision_is_a_bounded_integer(engine, revision):
    with pytest.raises(store.ProjectPromptError, match="project_prompt_invalid"):
        store.save_project_prompt(engine, revision, "safe")
    assert not (engine.parent / store.FILE_NAME).exists()


@pytest.mark.parametrize("raw", [
    b"{", b'{"revision":1}', b'{"format":"unknown","schemaVersion":1,"revision":1,"prompt":"a"}',
    b'{"format":"vas-project-prompt","schemaVersion":1,"revision":true,"prompt":"a"}',
    b'{"format":"vas-project-prompt","schemaVersion":1,"revision":1,"revision":2,"prompt":"a"}',
    b'{"format":"vas-project-prompt","schemaVersion":1,"revision":1,"prompt":" secret "}',
    b'{"format":"vas-project-prompt","schemaVersion":1,"revision":1,"prompt":"password=secret"}',
])
def test_existing_invalid_document_is_not_repaired_or_returned(engine, raw):
    path = engine.parent / store.FILE_NAME
    path.write_bytes(raw)
    for action in (lambda: store.read_project_prompt(engine), lambda: store.save_project_prompt(engine, 0, "new")):
        with pytest.raises(store.ProjectPromptError, match="project_prompt_corrupt"):
            action()
        assert path.read_bytes() == raw


def test_oversized_existing_document_is_bounded_and_preserved(engine):
    path = engine.parent / store.FILE_NAME
    raw = b"x" * (store.MAX_BYTES + 1)
    path.write_bytes(raw)
    with pytest.raises(store.ProjectPromptError, match="project_prompt_too_large"):
        store.read_project_prompt(engine)
    assert path.read_bytes() == raw


@pytest.mark.parametrize("boundary", ["fsync", "replace"])
def test_failed_commit_preserves_previous_instruction_and_cleans_temp(engine, monkeypatch, boundary):
    store.save_project_prompt(engine, 0, "old")
    before = tree(engine.parent)
    def fail(*args, **kwargs):
        raise OSError("do not expose this path or secret")
    monkeypatch.setattr(store.os, boundary, fail)
    with pytest.raises(store.ProjectPromptError, match="^project_prompt_unavailable$"):
        store.save_project_prompt(engine, 1, "new")
    assert tree(engine.parent) == before


@pytest.mark.parametrize("reserved", [store.FILE_NAME, store.TEMP_NAME])
def test_preplanted_hardlink_never_rewrites_or_deletes_its_other_name(engine, tmp_path, reserved):
    outside = tmp_path / "outside.txt"
    outside.write_text("keep outside")
    path = engine.parent / reserved
    os.link(outside, path)
    with pytest.raises(store.ProjectPromptError, match="project_prompt_unsafe"):
        store.save_project_prompt(engine, 0, "new")
    assert outside.read_text() == "keep outside" and path.is_file()


def test_two_actual_cli_writers_have_exactly_one_winner(engine):
    writers = []
    for value in ("first", "second"):
        child = subprocess.Popen([sys.executable, "-B", str(ROOT / "scripts/vas-project-prompt.py"),
                                  "--vas-root", str(engine), "save"],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        child.stdin.write(json.dumps({"expectedRevision": 0, "prompt": value}).encode())
        child.stdin.close()
        writers.append(child)
    results = []
    for child in writers:
        child.wait(timeout=10)
        results.append((child.returncode, json.loads(child.stdout.read())))
        child.stdout.close()
        child.stderr.close()
    assert sorted(code for code, _ in results) == [0, 1]
    assert next(value for code, value in results if code == 1)["code"] == "project_prompt_conflict"
    winner = next(value for code, value in results if code == 0)
    assert store.read_project_prompt(engine) == winner and winner["revision"] == 1


def test_killed_writer_releases_os_lock_and_next_save_recovers_staging(engine):
    store.save_project_prompt(engine, 0, "before")
    script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from vas_project_prompt import _Project, _pin, _locked, TEMP_NAME
p=_Project(Path(sys.argv[2]))
with _pin(p), _locked(p):
    (p.root/TEMP_NAME).write_bytes(b'partial abandoned stage')
    print('ready',flush=True)
    sys.stdin.buffer.read()
"""
    child = subprocess.Popen([sys.executable, "-B", "-c", script, str(ROOT / "scripts"), str(engine)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert child.stdout.readline().strip() == b"ready"
        child.kill()
        child.wait(timeout=10)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        child.stdin.close()
        child.stdout.close()
        child.stderr.close()
    assert store.read_project_prompt(engine) == {"revision": 1, "prompt": "before"}
    assert store.save_project_prompt(engine, 1, "after") == {"revision": 2, "prompt": "after"}
    assert not (engine.parent / store.TEMP_NAME).exists()


def test_cli_rejects_arbitrary_file_selector_and_uses_no_private_session_store(engine, tmp_path):
    result = call(engine, "save", {"expectedRevision": 0, "prompt": "safe", "path": str(tmp_path / "other")})
    assert result.returncode == 1 and json.loads(result.stdout)["code"] == "project_prompt_invalid"
    result = call(engine, "get")
    assert result.returncode == 0 and json.loads(result.stdout) == {"revision": 0, "prompt": ""}
    assert not (tmp_path / "other").exists()


@pytest.mark.parametrize("change", ["missing", "invalid", "outer"])
def test_only_real_embedded_engine_is_accepted(engine, change):
    marker = engine / "project-layout.json"
    if change == "missing":
        marker.unlink()
    elif change == "invalid":
        marker.write_text('{"layout":"vas-project","version":false}')
    else:
        engine = engine.parent
    before = tree(engine)
    with pytest.raises(store.ProjectPromptError, match="project_prompt_layout"):
        store.read_project_prompt(engine)
    assert tree(engine) == before


def test_junction_or_symlink_parent_cannot_redirect_writes(engine, tmp_path):
    alias = tmp_path / "alias"
    if os.name == "nt":
        result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(alias), str(engine.parent)], capture_output=True)
        assert result.returncode == 0
    else:
        alias.symlink_to(engine.parent, target_is_directory=True)
    try:
        with pytest.raises(store.ProjectPromptError, match="project_prompt_layout"):
            store.save_project_prompt(alias / ".vas", 0, "no")
        assert not (engine.parent / store.FILE_NAME).exists()
    finally:
        if os.name == "nt":
            alias.rmdir()
        else:
            alias.unlink()
