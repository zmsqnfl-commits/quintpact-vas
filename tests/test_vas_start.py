"""The host's first command only observes this starter and its matching private state."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vas_project_prompt import save_project_prompt
from vas_session import SessionManager


@pytest.fixture
def kit(tmp_path):
    app = tmp_path / "메뉴 보드"
    ui = app / "ui"
    ui.mkdir(parents=True)
    (app / "src").mkdir()
    (app / "src/.gitkeep").write_bytes(b"")
    (app / "Run-VAS-System.bat").write_text("test")
    (ui / "vas-hub.html").write_text("helper")
    (app / "project-layout.json").write_text('{"layout":"vas-project","version":2}')
    shutil.copytree(ROOT / "scripts", app / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return app, tmp_path / "private"


def snapshot(directory):
    return {p.relative_to(directory).as_posix(): (p.stat().st_mtime_ns, p.read_bytes())
            for p in directory.rglob("*") if p.is_file()}


def cli(kit, operation="start", *extra):
    app, state = kit
    # Exercise callers which did not know to pass -B; even these must leave no caches.
    result = subprocess.run([sys.executable, str(app / "scripts/vas.py"), "--state-home", str(state),
                             operation, *extra], cwd=app, text=True, encoding="utf-8",
                            capture_output=True, timeout=15)
    assert not result.stderr, result.stderr
    if operation == "start":
        assert len(result.stdout.splitlines()) <= 30
    return result.returncode, json.loads(result.stdout)


def settings(name="Menu"):
    return {"project": {"name": name, "sourceType": "new"},
            "task": {"request": "Display the menu", "completionCriteria": [
                {"description": "Menu items are visible", "method": "automatic", "required": True}]},
            "nextStep": "Build list"}


def test_first_index_is_read_only_and_does_not_assume_migration(kit):
    app, state = kit
    before = snapshot(app)
    first = cli(kit)
    assert first == cli(kit)
    code, data = first
    assert code == 0 and data["status"] == "ok"
    assert data["app"]["directory"] == "src" and data["app"]["state"] == "empty"
    assert data["app"]["interpretation"] == "새 앱 자리" and data["sharedProgress"] is None
    assert data["nextAction"]["sessionCommand"].endswith("create --target .")
    assert "command" not in data["nextAction"] and "quick finish" in data["nextAction"]["lightweight"]
    assert data["projectPrompt"] == {"revision": 0, "prompt": ""}
    assert data["session"] == {"status": "none"}
    assert data["nextAction"]["code"] == "clarify-scope"
    assert ".vas/" not in str(data)
    assert snapshot(app) == before and not state.exists()


@pytest.mark.parametrize("name", ["app.py", ".env", "CLAUDE.md"])
def test_only_categorize_src_and_never_read_or_return_app_entries(kit, name):
    app, _ = kit
    (app / "src" / name).write_text("secret-canary", encoding="utf-8")
    code, data = cli(kit)
    assert code == 0 and data["app"]["state"] == "nonempty"
    output = str(data)
    assert "secret-canary" not in output and name not in output and str(app) not in output


def test_current_session_and_prompt_become_visible_without_other_bindings(kit):
    app, state = kit
    manager = SessionManager(app, state)
    other = app.parent / "External"
    other.mkdir()
    manager.create(settings("Do not reveal me"), other)
    assert cli(kit)[1]["session"] == {"status": "none"}
    session = manager.create(settings(), app)["session"]
    saved = save_project_prompt(app, 0, "재고와 가격을 보여주세요.")
    before = snapshot(state)
    code, data = cli(kit)
    assert code == 0 and data["projectPrompt"] == saved
    assert data["session"]["sessionId"] == session["sessionId"]
    assert data["session"]["revision"] == 1 and data["session"]["nextStep"] == "Build list"
    assert data["nextAction"]["code"] == "resume"
    assert data["nextAction"]["command"].endswith("prepare --session " + session["sessionId"] + " --expected-revision 1")
    assert data["nextAction"]["finishCommand"].endswith("--expected-project-prompt-revision 1 --expected-shared-revision 0")
    assert "Do not reveal me" not in str(data) and str(app) not in str(data)
    assert snapshot(state) == before
    code, hook = cli(kit, "start", "--claude-hook")
    assert code == 0 and hook["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    context = hook["hookSpecificOutput"]["additionalContext"]
    assert '"promptRevision": 1' in context and '"sessionStatus": "resumed"' in context
    assert "재고와 가격" not in context and "Build list" not in context and str(app) not in context


def test_ambiguous_existing_records_never_look_like_an_empty_project(kit):
    app, state = kit
    manager = SessionManager(app, state)
    other = app.parent / "Another"
    other.mkdir()
    manager.create(settings(), app)
    second = manager.create(settings(), other)["session"]["sessionId"]
    def duplicate(data):
        data["sessions"][second]["binding"]["path"] = str(app)
    manager.store.mutate(duplicate)
    before = manager.store.path.read_bytes()
    code, data = cli(kit)
    assert code != 0 and data == {"status": "error", "code": "session_target_ambiguous"}
    assert manager.store.path.read_bytes() == before


def test_corrupt_or_unsafe_private_state_does_not_trigger_new_project_setup(kit):
    app, state = kit
    manager = SessionManager(app, state)
    manager.create(settings(), app)
    manager.store.path.write_bytes(b"{bad")
    code, data = cli(kit)
    assert code == 1 and data["status"] == "partial" and data["code"] == "session_store_invalid"
    assert data["session"]["status"] == "unavailable"
    assert manager.store.path.read_bytes() == b"{bad"
    code, data = cli((app, app / "src/private"))
    assert code == 1 and data["status"] == "partial" and data["code"] == "session_store_path_invalid"
    assert not (app / "src/private").exists()


@pytest.mark.parametrize("bad_marker", ['{}', '{"layout":"vas-project","version":3}', None])
def test_invalid_or_missing_marker_fails_closed(kit, bad_marker):
    app, state = kit
    marker = app / "project-layout.json"
    if bad_marker is None:
        marker.unlink()
    else:
        marker.write_text(bad_marker)
    assert cli(kit) == (1, {"status": "error", "code": "vas_root_invalid"})
    assert not state.exists()


def test_unsafe_src_is_not_enumerated_and_link_contents_are_never_returned(kit):
    app, state = kit
    src = app / "src"
    external = app.parent / "External"
    external.mkdir()
    (external / "private-file").write_bytes(b"canary")
    (src / ".gitkeep").unlink()
    src.rmdir()
    if os.name == "nt":
        subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(src), str(external)], check=True, capture_output=True)
    else:
        src.symlink_to(external, target_is_directory=True)
    try:
        code, data = cli(kit)
        assert code == 1 and data["status"] == "error" and "private-file" not in str(data)
        assert not state.exists()
    finally:
        if os.name == "nt":
            src.rmdir()
        else:
            src.unlink()


def test_changed_target_is_not_reported_as_session_absence(kit):
    app, state = kit
    manager = SessionManager(app, state)
    sid = manager.create(settings(), app)["session"]["sessionId"]
    manager.store.mutate(lambda data: data["sessions"][sid]["binding"].update(identity=[123, 456]))
    assert cli(kit) == (1, {"status": "error", "code": "target_unavailable"})

def test_long_project_prompt_is_marked_as_excerpt_with_explicit_reader(kit):
    app, _ = kit
    value = save_project_prompt(app, 0, "간결한 요구사항 " * 90)
    code, data = cli(kit)
    assert code == 0 and data["projectPrompt"]["revision"] == value["revision"]
    assert data["projectPrompt"]["truncated"] and len(data["projectPrompt"]["prompt"]) <= 500
    assert data["projectPrompt"]["readCommand"] == "python -B scripts/vas-project-prompt.py get"


def test_existing_private_checkpoint_returns_phase_and_usable_current_cursors(kit):
    app, state = kit
    manager = SessionManager(app, state)
    sid = manager.create(settings(), app)["session"]["sessionId"]
    manager.checkpoint(sid, 1, 0, {"phase": "paused", "summary": "실행기 재확인", "nextStep": "메뉴 테스트"})
    code, data = cli(kit)
    assert code == 0 and data["session"]["progress"] == {
        "status": "available", "revision": 1, "phase": "paused", "summary": "실행기 재확인"}
    assert data["session"]["nextStep"] == "메뉴 테스트"
    assert "--expected-revision 2 --expected-progress-revision 1" in data["nextAction"]["finishCommand"]


def test_malformed_prompt_file_cannot_be_treated_as_absent(kit):
    app, state = kit
    (app / "VAS-PROJECT-PROMPT.json").write_bytes(b"{bad")
    code, data = cli(kit)
    assert code == 1 and data["code"] == "project_prompt_corrupt"
    assert not state.exists()


def test_another_host_can_read_shared_progress_without_a_private_session(kit):
    app, first_home = kit
    from vas_portable_progress import append_shared_progress
    shared = append_shared_progress(app, 0, {"phase": "paused", "summary": "메뉴판 초안을 확인함",
        "checks": [{"name": "가격 표기", "status": "passed"}], "nextStep": "모바일 화면에서 다시 검토"})
    first = SessionManager(app, first_home)
    first.create(settings(), app)
    second_home = first_home.parent / "new-host-without-private-records"
    before = snapshot(app)
    code, data = cli((app, second_home))
    assert code == 0 and data["sharedProgress"] == shared and data["session"] == {"status": "none"}
    assert data["nextAction"]["code"] == "review-shared" and not second_home.exists()
    assert snapshot(app) == before

    damaged_home = first_home.parent / "broken-store-file"
    damaged_home.write_text("existing private store cannot be opened")
    code, partial = cli((app, damaged_home))
    assert code == 1 and partial["status"] == "partial"
    assert partial["session"] == {"status": "unavailable"} and partial["sharedProgress"] == shared
    assert snapshot(app) == before


def test_shared_snapshot_is_never_silently_treated_as_missing_on_invalid_data(kit):
    app, state = kit
    from vas_portable_progress import append_shared_progress
    append_shared_progress(app, 0, {"phase": "paused", "summary": "점검", "checks": [], "nextStep": "재개"})
    # Refuse damaged portable reports without modifying any app or private records.
    file = next((app / "vas-state/progress").glob("*.json"))
    file.write_bytes(b"not-json")
    code, data = cli(kit)
    assert code == 1 and data["status"] == "error" and data["code"].startswith("shared_progress_")
    assert file.read_bytes() == b"not-json" and not state.exists()

def test_large_shared_scope_is_a_short_preview_with_a_readable_full_note():
    from vas_start import shared_brief
    record = {"revision": 2, "phase": "paused", "summary": "A" * 600, "nextStep": "Continue",
              "checks": [], "markdownPath": "vas-state/progress/000002.md",
              "scope": {"objective": "Show the price", "criteria": [f"Condition {i}" for i in range(10)]},
              "remaining": ["first", "second", "third"]}
    preview = shared_brief(record)
    assert preview["truncated"] and len(preview["scope"]["criteria"]) == 3
    assert preview["remaining"] == ["first", "second"] and preview["markdownPath"] == record["markdownPath"]
    assert len(record["scope"]["criteria"]) == 10 and len(preview["summary"]) <= 240
