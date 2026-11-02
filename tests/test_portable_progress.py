"""The portable journal stays outside Git and survives distinct host state stores."""
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
