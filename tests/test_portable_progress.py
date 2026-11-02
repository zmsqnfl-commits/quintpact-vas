"""The portable journal stays outside Git and survives distinct host state stores."""
import errno
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vas_portable_progress as journal


@pytest.fixture
def project(tmp_path):
    app = tmp_path / "원격 메뉴판"
    (app / "src").mkdir(parents=True)
    (app / "ui").mkdir()
    (app / "ui/vas-hub.html").write_text("tool")
    (app / "Run-VAS-System.bat").write_text("tool")
    (app / "project-layout.json").write_bytes((ROOT / "project-layout.json").read_bytes())
    return app


def note(summary="Menu price verified"):
    return {"phase": "paused", "summary": summary, "nextStep": "Check the admin view",
            "changedFiles": ["src/menu.py"], "checks": [
                {"name": "Menu view", "status": "passed", "command": "private command must stay local"}]}


def test_revisions_redaction_no_raw_data_and_optimistic_conflicts(project):
    assert journal.read_shared_progress(project) is None
    assert not (project / "vas-state").exists()
    first = journal.append_shared_progress(project, 0, note("Sent a note to canary@example.com"))
    assert first["revision"] == 1 and "canary@example" not in first["summary"]
    assert first["checks"] == [{"name": "Menu view", "status": "passed"}]
    assert set(first) == {"revision", "summary", "nextStep", "phase", "checks", "markdownPath"}
    assert journal.append_shared_progress(project, 0, note("Sent a note to canary@example.com")) == first
    with pytest.raises(journal.SharedProgressError, match="conflict"):
        journal.append_shared_progress(project, 0, note("Stale update"))
    second = journal.append_shared_progress(project, 1, note("New note"))
    assert journal.read_shared_progress(project) == second and second["revision"] == 2
    contents = (project / "vas-state/progress/000001.json").read_text(encoding="utf-8")
    assert "private command" not in contents and "src/menu.py" not in contents


def test_shared_volume_note_preserves_container_syntax_and_redacts_host_path(project):
    first = journal.append_shared_progress(project, 0, note("Volume ./assets:/app:ro from /sessions/private_host/src"))
    assert journal.read_shared_progress(project) == first
    for suffix in ("json", "md"):
        text = (project / f"vas-state/progress/000001.{suffix}").read_text(encoding="utf-8")
        assert "./assets:/app:ro" in text and "private_host" not in text


def test_create_only_remote_and_interrupted_writer(project, monkeypatch):
    real_open = os.open
    def create_only(path, flags, *args, **kwargs):
        assert not flags & os.O_TRUNC, "remote refuses replacement of existing files"
        if Path(path).suffix == ".json" and flags & os.O_WRONLY:
            assert flags & os.O_EXCL
        return real_open(path, flags, *args, **kwargs)
    def forbidden(*args, **kwargs):
        raise PermissionError("Remote connection does not allow delete or replace")
    monkeypatch.setattr(os, "open", create_only)
    for op in ("unlink", "remove", "rename", "replace"):
        monkeypatch.setattr(os, op, forbidden)
    first = journal.append_shared_progress(project, 0, note())
    with monkeypatch.context() as failure:
        failure.setattr(os, "fsync", forbidden)
        with pytest.raises(journal.SharedProgressError, match="unavailable"):
            journal.append_shared_progress(project, 1, note("Interrupted"))
    assert journal.read_shared_progress(project) == first
    retry = journal.append_shared_progress(project, 1, note("Recovered"))
    assert retry["revision"] == 3 and journal.read_shared_progress(project) == retry


def test_separate_processes_cannot_both_advance_the_same_cursor(project):
    script = ("import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
              "from vas_portable_progress import append_shared_progress; "
              "append_shared_progress(Path(sys.argv[2]), 0, "
              "{'summary':sys.argv[3],'phase':'paused','nextStep':'Check menu'})")
    processes = [subprocess.Popen([sys.executable, "-B", "-c", script, str(ROOT / "scripts"), str(project), text],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) for text in ("First", "Second")]
    for child in processes:
        child.communicate(timeout=15)
    assert sorted(child.returncode for child in processes) == [0, 1]
    assert journal.read_shared_progress(project)["revision"] == 1


def test_tamper_does_not_become_an_empty_or_successful_record(project):
    journal.append_shared_progress(project, 0, note())
    path = project / "vas-state/progress/000001.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["record"]["summary"] = "Tampered"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(journal.SharedProgressError, match="invalid"):
        journal.read_shared_progress(project)
    with pytest.raises(journal.SharedProgressError, match="invalid"):
        journal.append_shared_progress(project, 1, note("Override"))


def test_reader_rejects_duplicate_fields_and_unredacted_nonstandard_absolute_path(project):
    record = journal.append_shared_progress(project, 0, note("See /department/client/hidden"))
    assert "/department/" not in record["summary"]
    path = project / "vas-state/progress/000001.json"
    raw = path.read_bytes().replace(b'"summary":', b'"summary":"ignored duplicate","summary":')
    path.write_bytes(raw)
    with pytest.raises(journal.SharedProgressError, match="invalid"):
        journal.read_shared_progress(project)

def test_markdown_is_a_verified_readable_view_of_one_revision(project):
    data = {**note(), "scope": {"objective": "메뉴를 표시한다", "criteria": ["가격이 보인다"]},
            "decisions": ["기존 화면 유지"], "remaining": ["모바일 확인"]}
    record = journal.append_shared_progress(project, 0, data)
    view = project / record["markdownPath"]
    md = view.read_text(encoding="utf-8")
    for value in ("메뉴를 표시한다", "가격이 보인다", "기존 화면 유지", "모바일 확인", "Menu view · 통과"):
        assert value in md
    assert journal.append_shared_progress(project, 0, data) == record
    view.write_text("forged summary", encoding="utf-8")
    with pytest.raises(journal.SharedProgressError, match="invalid"):
        journal.read_shared_progress(project)


def test_legacy_record_without_markdown_remains_readable(project):
    data = journal.append_shared_progress(project, 0, note())
    md = project / data.pop("markdownPath")
    md.unlink()
    digest = journal.hashlib.sha256(journal.canonical(data)).hexdigest()
    (project / "vas-state/progress/000001.json").write_bytes(journal.canonical({"record": data, "sha256": digest}))
    assert journal.read_shared_progress(project) == data

def unsupported_lock(monkeypatch, code):
    def fail(*_):
        raise OSError(code, "simulated network file system")
    if os.name == "nt":
        import msvcrt
        monkeypatch.setattr(msvcrt, "locking", fail)
    else:
        import fcntl
        monkeypatch.setattr(fcntl, "lockf", fail)


@pytest.mark.parametrize("error", [errno.ENOSYS, errno.EOPNOTSUPP])
def test_fresh_lockless_mount_advances_and_accepts_ordinary_host(project, monkeypatch, error):
    with monkeypatch.context() as mounted:
        unsupported_lock(mounted, error)
        first = journal.append_shared_progress(project, 0, note())
        assert journal.append_shared_progress(project, 0, note()) == first
    directory = project / "vas-state/progress"
    assert (directory / "writer.lock").is_dir()
    # A v2.13.0 writer must open writer.lock as a regular file. It cannot ignore
    # this election and fast-forward over an in-flight owner's successor.
    with pytest.raises(OSError):
        os.close(os.open(directory / "writer.lock", os.O_RDWR))
    second = journal.append_shared_progress(project, 1, note("Ordinary host"))
    with pytest.raises(journal.SharedProgressError, match="conflict"):
        journal.append_shared_progress(project, 1, note("Different host"))
    assert second["revision"] == 2 and journal.read_shared_progress(project) == second


def test_legacy_journal_cannot_switch_under_an_unsupported_writer(project, monkeypatch):
    first = journal.append_shared_progress(project, 0, note())
    directory = project / "vas-state/progress"
    assert (directory / "writer.lock").is_file()
    original = {file.name: file.read_bytes() for file in directory.iterdir()}
    with monkeypatch.context() as mounted:
        unsupported_lock(mounted, errno.EOPNOTSUPP)
        with pytest.raises(journal.SharedProgressError, match="lock_unsupported"):
            journal.append_shared_progress(project, 1, note("Unsafe upgrade"))
    assert original == {file.name: file.read_bytes() for file in directory.iterdir()}
    assert journal.read_shared_progress(project) == first


def test_legacy_first_writer_wins_the_mode_election(project, monkeypatch):
    lock = project / "vas-state/progress/writer.lock"

    def competing_writer(_fd):
        if not lock.exists():
            lock.touch(exist_ok=False)  # 2.13.0 first writer, between our probe and mkdir.
        return "unsupported"

    monkeypatch.setattr(journal, "lock_attempt", competing_writer)
    with pytest.raises(journal.SharedProgressError, match="lock_unsupported"):
        journal.append_shared_progress(project, 0, note())
    assert lock.is_file() and journal.read_shared_progress(project) is None


def test_transient_lock_failure_or_contention_never_downgrades(project, monkeypatch):
    directory = project / "vas-state/progress"
    with monkeypatch.context() as mounted:
        unsupported_lock(mounted, errno.ENOLCK)
        with pytest.raises(journal.SharedProgressError, match="lock_unavailable"):
            journal.append_shared_progress(project, 0, note())
    assert not (directory / "writer.lock").exists()
    with monkeypatch.context() as mounted:
        unsupported_lock(mounted, errno.EAGAIN)
        ticks = iter([0, 3])
        mounted.setattr(journal.time, "monotonic", lambda: next(ticks))
        with pytest.raises(journal.SharedProgressError, match="busy"):
            journal.append_shared_progress(project, 0, note())
    assert (directory / "writer.lock").is_file() and not list(directory.glob("*.ok"))


def test_exact_retry_helps_an_intact_lockless_successor_but_never_skips_a_partial(project, monkeypatch):
    directory = project / "vas-state/progress"
    unsupported_lock(monkeypatch, errno.ENOSYS)
    first = journal.append_shared_progress(project, 0, note())

    with monkeypatch.context() as stopped:
        write_once = journal._Journal.write_once

        def stop_before_view(self, revision, suffix, content, exclusive):
            if suffix == "md":
                raise OSError(errno.EIO, "stopped")
            return write_once(self, revision, suffix, content, exclusive)

        stopped.setattr(journal._Journal, "write_once", stop_before_view)
        with pytest.raises(journal.SharedProgressError, match="unavailable"):
            journal.append_shared_progress(project, 1, note("Intact record"))
    assert journal.read_shared_progress(project) == first
    with pytest.raises(journal.SharedProgressError, match="pending"):
        journal.append_shared_progress(project, 1, note("Different record"))
    assert not (directory / "000003.json").exists()
    second = journal.append_shared_progress(project, 1, note("Intact record"))
    assert second["revision"] == 2 and journal.read_shared_progress(project) == second

    prefix = b'{"record":'
    (directory / "000003.json").write_bytes(prefix)
    with pytest.raises(journal.SharedProgressError, match="pending"):
        journal.append_shared_progress(project, 2, note("Cannot replace a partial"))
    assert (directory / "000003.json").read_bytes() == prefix
    assert not (directory / "000004.json").exists() and journal.read_shared_progress(project) == second


def test_ordinary_writer_observes_pending_fallback_writer_in_separate_process(project):
    code = """
import errno, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import vas_portable_progress as journal
journal.lock_attempt = lambda fd: "unsupported"
original = journal._Journal.write_once
def stop(self, revision, suffix, data, exclusive):
    original(self, revision, suffix, data, exclusive)
    if suffix == "json":
        print("reserved", flush=True)
        assert sys.stdin.readline() == "continue\\n"
journal._Journal.write_once = stop
journal.append_shared_progress(Path(sys.argv[2]), 0,
    {"phase": "paused", "summary": "First remote note", "nextStep": "Check menu"})
"""
    proc = subprocess.Popen([sys.executable, "-B", "-c", code, str(ROOT / "scripts"), str(project)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8")
    try:
        assert proc.stdout.readline().strip() == "reserved"
        with pytest.raises(journal.SharedProgressError, match="pending"):
            journal.append_shared_progress(project, 0, note("Cannot overtake"))
        assert not (project / "vas-state/progress/000002.json").exists()
        assert journal.read_shared_progress(project) is None
        out, err = proc.communicate("continue\n", timeout=15)
        assert proc.returncode == 0, (out, err)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
    assert journal.read_shared_progress(project)["summary"] == "First remote note"
    with pytest.raises(journal.SharedProgressError, match="conflict"):
        journal.append_shared_progress(project, 0, note("Cannot overwrite"))



def test_lockless_host_can_start_and_read_saved_prompt_without_unlocking_writes(project, tmp_path, monkeypatch):
    from vas_project_prompt import read_project_prompt, save_project_prompt, ProjectPromptError
    from vas_start import start
    saved = save_project_prompt(project, 0, "Read the menu source")
    unsupported_lock(monkeypatch, errno.EOPNOTSUPP)
    if os.name != "nt":
        import fcntl
        def unsupported(*_):
            raise OSError(errno.EOPNOTSUPP, "unsupported advisory lock")
        monkeypatch.setattr(fcntl, "flock", unsupported)
    first = journal.append_shared_progress(project, 0, note())
    view = start(project, tmp_path / "new-host")
    assert view["status"] == "ok" and view["session"]["status"] == "none"
    assert view["projectPrompt"] == saved and view["sharedProgress"] == first
    assert read_project_prompt(project) == saved
    with pytest.raises(ProjectPromptError, match="unavailable"):
        save_project_prompt(project, 1, "Must use a real write lock")
    assert read_project_prompt(project) == saved


def test_ordinary_first_writer_joins_winning_exclusive_mode(project, monkeypatch):
    lock = project / "vas-state/progress/writer.lock"
    def simultaneous_fallback(_fd):
        lock.mkdir(exist_ok=True)
        return "acquired"
    monkeypatch.setattr(journal, "lock_attempt", simultaneous_fallback)
    record = journal.append_shared_progress(project, 0, note())
    assert lock.is_dir() and journal.read_shared_progress(project) == record


def test_cli_finish_preserves_last_record_and_explains_legacy_lock_failure(project, tmp_path, monkeypatch):
    from vas_finish import quick_finish
    first = journal.append_shared_progress(project, 0, note())
    unsupported_lock(monkeypatch, errno.EOPNOTSUPP)
    result = quick_finish(project, tmp_path / "second-host", "Changed menu", [], "Recheck", 1)
    assert result["status"] == "not-recorded"
    assert result["sharedError"] == "shared_progress_lock_unsupported"
    assert "start" in result["nextAction"]
    assert journal.read_shared_progress(project) == first
