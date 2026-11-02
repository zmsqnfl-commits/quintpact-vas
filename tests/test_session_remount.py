"""Fresh remote shells can mount the same starter on a different device."""
from concurrent.futures import ThreadPoolExecutor
import os
import shutil

import pytest

from test_project_prompt_handoff import SETTINGS, report
import vas_session as session
import vas_work_files as files
from vas_finish import finish
from vas_session_execution import assess, prepare
from vas_session_work import finish_work, inspect_work, open_work, start_work


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "Menu"
    (root / "ui").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "ui/vas-hub.html").write_text("tool")
    (root / "Run-VAS-System.bat").write_text("tool")
    (root / "project-layout.json").write_text('{"layout":"vas-project","version":2}')
    return root


def test_independent_remounts_keep_session_and_observed_work_bound(project, tmp_path, monkeypatch):
    inode = project.stat().st_ino
    mounted = 44
    native_id, native_file_id = session.identity, files._identity
    monkeypatch.setattr(session, "identity", lambda path:
                        [mounted, inode] if path == project else native_id(path))
    monkeypatch.setattr(files, "_identity", lambda info:
                        (mounted, inode) if info.st_ino == inode else native_file_id(info))

    def host():
        nonlocal mounted
        mounted += 1
        return session.SessionManager(project, tmp_path / "private")

    sid = host().create(SETTINGS, project)["session"]["sessionId"]
    assert host().resume(session_id=sid)["target"]["status"] == "available"
    handoff = prepare(host(), sid, 1)
    assert handoff["status"] == "prepared"
    (project / "src/menu.py").write_text("menu = 1")
    opened = open_work(host(), sid, 1, 0)
    binding_digest = opened["work"]["record"]["context"]["targetBindingSha256"]
    unit = start_work(host(), sid, 1, 1, {
        "kind": "verification", "role": "main", "mode": "direct", "label": "Check menu",
        "command": "python -m unittest", "observedFiles": ["src/menu.py"], "criterionIds": ["C1"]})
    finish_work(host(), sid, 1, 2, unit["unitId"], {
        "state": "returned", "hostCallId": "test-host", "summary": "Host checked menu", "exitCode": 0,
        "criteria": [{"id": "C1", "status": "passed", "summary": "Menu verified"}]})
    verified = inspect_work(host(), sid, 1)
    assert verified["contextMatches"] and verified["coveredCriteria"] == ["C1"]
    assert verified["artifactVersion"] and not verified["reasons"]
    response = report(handoff)
    response["artifactVersion"] = response["evidence"][0]["artifactVersion"] = verified["artifactVersion"]
    assessed = assess(host(), sid, 1, response)
    assert assessed["status"] == "assessed" and assessed["workChecks"]["reasons"] == []
    assert assessed["assessment"]["reasons"] == ["unconfirmed-criterion:C1"]
    closed = finish(host(), sid, 1, 0, {"result": response, "progress": {"summary": "Verified"}},
                    expected_shared_revision=0)
    assert closed["status"] == "checkpointed" and closed["sharedProgress"]["revision"] == 1
    after = host().resume(session_id=sid)
    assert after["session"]["revision"] == 2  # Only the explicit finish advances the session.
    assert after["work"]["record"]["context"]["targetBindingSha256"] == binding_digest


def test_replacement_with_same_root_inode_and_copied_project_marker_is_rejected(project, tmp_path, monkeypatch):
    manager = session.SessionManager(project, tmp_path / "private")
    sid = manager.create(SETTINGS, project)["session"]["sessionId"]
    previous = manager.store.read()["sessions"][sid]["binding"]
    original = tmp_path / "original"
    project.rename(original)
    shutil.copytree(original, project)
    # Even copying the project-specific filename doesn't copy the witness inode.
    monkeypatch.setattr(session, "identity", lambda _: [99, previous["identity"][1]])
    stored = manager.store.path.read_bytes()
    assert manager.resume(session_id=sid)["target"]["status"] == "changed"
    with pytest.raises(session.SessionError, match="target_unavailable"):
        prepare(manager, sid, 1)
    assert manager.store.path.read_bytes() == stored


def test_no_adoption_or_repair_when_known_proof_disappears_or_is_linked(project, tmp_path):
    manager = session.SessionManager(project, tmp_path / "private")
    sid = manager.create(SETTINGS, project)["session"]["sessionId"]
    anchor, = (project / "vas-state/target-identity").iterdir()
    anchor.rename(tmp_path / "removed")
    assert manager.resume(session_id=sid)["target"]["status"] == "changed"
    assert not anchor.exists()
    os.link(tmp_path / "removed", anchor)
    assert manager.resume(session_id=sid)["target"]["status"] == "changed"
    assert (tmp_path / "removed").read_bytes() == b""


def test_old_and_external_bindings_stay_strict_and_only_explicit_rebind_upgrades(project, tmp_path):
    manager = session.SessionManager(project, tmp_path / "private")
    sid = manager.create(SETTINGS, project)["session"]["sessionId"]
    def legacy(data):
        binding = data["sessions"][sid]["binding"]
        del binding["anchor"]
    manager.store.mutate(legacy)
    assert manager.resume(session_id=sid)["target"]["status"] == "available"
    def remount(data):
        data["sessions"][sid]["binding"]["identity"][0] += 1
    manager.store.mutate(remount)
    stored = manager.store.path.read_bytes()
    assert manager.resume(session_id=sid)["target"]["status"] == "changed"
    assert manager.store.path.read_bytes() == stored
    manager.rebind(sid, 1, project)
    assert manager.resume(session_id=sid)["session"]["revision"] == 2
    assert "anchor" in manager.store.read()["sessions"][sid]["binding"]
    external = tmp_path / "external"
    external.mkdir()
    manager.rebind(sid, 2, external)
    manager.store.mutate(remount)
    assert manager.resume(session_id=sid)["target"]["status"] == "changed"
    assert not any(external.iterdir())


def test_simultaneous_first_bindings_from_two_hosts(project, tmp_path):
    def bind(number):
        manager = session.SessionManager(project, tmp_path / str(number))
        sid = manager.create(SETTINGS, project)["session"]["sessionId"]
        return manager, sid

    with ThreadPoolExecutor(2) as pool:
        bindings = list(pool.map(bind, [1, 2]))
    for manager, sid in bindings:
        for _ in range(2):
            assert manager.resume(session_id=sid)["target"]["status"] == "available"
