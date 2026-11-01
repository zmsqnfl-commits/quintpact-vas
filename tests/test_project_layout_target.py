"""Renamed starter folder is the app target; its embedded tool stays out of app work."""
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from vas_session import SessionError, SessionManager
from vas_session_execution import prepare
from vas_session_store import SessionStoreError
from vas_session_work import finish_work, inspect_work, open_work, start_work

MARKER = '{"layout":"vas-project","version":1}'
SETTINGS = {"project": {"name": "Ledger", "sourceType": "new"},
            "task": {"request": "Track stock", "completionCriteria": [
                {"description": "Can list stock", "method": "automatic", "required": True}]}}


@pytest.fixture
def kit(tmp_path):
    app = tmp_path / "재고 관리"
    engine = app / ".vas"
    (app / "src").mkdir(parents=True)
    (engine / "src").mkdir(parents=True)
    (engine / "workspace/unrelated").mkdir(parents=True)
    (engine / "Run-VAS-System.bat").write_text("fixture")
    (engine / "src/vas-hub.html").write_text("engine content")
    (engine / "project-layout.json").write_text(MARKER, encoding="utf-8")
    return app, engine, SessionManager(engine, tmp_path / "private")


def test_target_is_project_root_and_prompt_remains_bound_to_it(kit, tmp_path):
    app, engine, manager = kit
    session = manager.create(SETTINGS, app)["session"]
    sid = session["sessionId"]
    result = prepare(manager, sid, 1)
    assert result["status"] == "prepared" and result["target"]["path"] == str(app)
    assert result["handoff"]["context"]["execution"]["projectLayout"] == "vas-project"
    prompt = result["handoff"]["assistantGuide"]["pasteText"]
    assert "앱 코드는 루트의 src/" in prompt and ".vas/는 VAS 도구 전용" in prompt
    assert "빈 폴더" not in prompt and str(app) not in prompt
    for invalid in (tmp_path, app / "src", engine, engine / "src", engine / "workspace/unrelated"):
        with pytest.raises(SessionError, match="target_is_vas"):
            manager.rebind(sid, 1, invalid)
    assert manager.resume(target=app)["session"] == session
    # An explicitly selected external project remains eligible under legacy semantics.
    outside = tmp_path / "standalone"
    outside.mkdir()
    manager.rebind(sid, 1, outside)
    result = prepare(manager, sid, 2)
    assert "projectLayout" not in result["handoff"]["context"]["execution"]


@pytest.mark.parametrize("marker", [None, "{", "x" * 257,
                                    '{"layout":"vas-project","version":true}',
                                    '{"layout":"vas-project","version":1,"version":1}',
                                    '{"layout":"vas-project","version":1,"extra":1}'])
def test_changed_layout_does_not_reuse_an_earlier_binding(kit, marker):
    app, engine, manager = kit
    sid = manager.create(SETTINGS, app)["session"]["sessionId"]
    before = manager.store.path.read_bytes()
    flag = engine / "project-layout.json"
    if marker is None:
        flag.unlink()
    else:
        flag.write_text(marker)
    assert manager.resume(session_id=sid)["status"] == "target_unavailable"
    with pytest.raises(SessionError, match="target_unavailable"):
        prepare(manager, sid, 1)
    with pytest.raises(SessionError, match="target_is_vas"):
        manager.create(SETTINGS, app)
    with pytest.raises(SessionError, match="target_is_vas"):
        manager.create(SETTINGS, app / "src")
    assert manager.store.path.read_bytes() == before


def test_private_state_cannot_be_placed_in_app_sources(kit):
    app, engine, _ = kit
    with pytest.raises(SessionStoreError, match="session_store_path_invalid"):
        SessionManager(engine, app / "src/private")
    assert not (app / "src/private").exists()


@pytest.mark.parametrize("marker", [MARKER, "{", None])
def test_external_installation_cannot_treat_the_packaged_engine_as_a_user_app(kit, tmp_path, marker):
    _, engine, _ = kit
    if marker is None:
        (engine / "project-layout.json").unlink()
    else:
        (engine / "project-layout.json").write_text(marker)
    other = tmp_path / "legacy-tool"
    (other / "src").mkdir(parents=True)
    (other / "Run-VAS-System.bat").write_text("fixture")
    (other / "src/vas-hub.html").write_text("fixture")
    manager = SessionManager(other, tmp_path / "private")
    with pytest.raises(SessionError, match="target_is_vas"):
        manager.create(SETTINGS, engine / "src")


@pytest.mark.parametrize("marker", [MARKER, "invalid", None])
def test_project_with_coincidentally_named_app_file_cannot_be_a_legacy_installation(kit, tmp_path, marker):
    app, engine, _ = kit
    (app / "Run-VAS-System.bat").write_text("wrapper")
    (app / "src/vas-hub.html").write_text("user app")
    if marker is None:
        (engine / "project-layout.json").unlink()
    else:
        (engine / "project-layout.json").write_text(marker)
    with pytest.raises(SessionError, match="vas_root_invalid"):
        SessionManager(app, tmp_path / "private")


def test_engine_cannot_be_observed_written_or_hidden_in_a_successful_work_report(kit):
    app, engine, manager = kit
    sid = manager.create(SETTINGS, app)["session"]["sessionId"]
    open_work(manager, sid, 1, 0)
    start = {"kind": "implementation", "role": "main", "mode": "direct", "label": "Implement"}
    before = manager.store.path.read_bytes()
    for item in (".vas/src/vas-hub.html", ".VAS/missing", ".vas"):
        with pytest.raises(SessionError, match="work_files_path_invalid"):
            start_work(manager, sid, 1, 1, dict(start, observedFiles=[item], writableFiles=[item]))
    assert manager.store.path.read_bytes() == before
    unit = start_work(manager, sid, 1, 1, dict(start, observedFiles=["src/app.py"],
                                               writableFiles=["src/app.py"]))["unitId"]
    (app / "src/app.py").write_text("inventory = {}")
    finish_work(manager, sid, 1, 2, unit, {"state": "returned", "hostCallId": "fixture",
                "summary": "Host also reports an out-of-scope change",
                "changedFiles": ["src/app.py", ".vas/src/vas-hub.html"], "exitCode": 0})
    inspected = inspect_work(manager, sid, 1)
    assert inspected["units"][0]["reportedOutOfScopeFiles"] == [".vas/src/vas-hub.html"]
    assert any(s.startswith("work-out-of-scope:") for s in inspected["reasons"])
    assert (engine / "src/vas-hub.html").read_text() == "engine content"


def test_src_link_into_engine_is_not_a_writable_app_target(kit):
    app, engine, manager = kit
    src = app / "src"
    sid = manager.create(SETTINGS, app)["session"]["sessionId"]
    src.rmdir()
    if sys.platform == "win32":
        result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(src), str(engine / "src")],
                                capture_output=True)
        assert result.returncode == 0, "Windows junction fixture unavailable"
    else:
        src.symlink_to(engine / "src", target_is_directory=True)
    assert manager.resume(session_id=sid)["status"] == "target_unavailable"
    with pytest.raises(SessionError, match="target_unsafe"):
        manager.create(SETTINGS, app)
    assert (engine / "src/vas-hub.html").read_text() == "engine content"
