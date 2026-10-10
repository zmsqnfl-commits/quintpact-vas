"""The design screen shares CLI revisions without receiving private bindings."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vas_session import SessionError
from vas_session_web import dispatch
from test_chat_session import layout, settings, manager, run_cli


def request(document, **changes):
    result = {"sessionId": document["sessionId"], "expectedRevision": document["revision"],
              "designScope": {"mode": "new", "scope": "예약 화면"},
              "design": {"profileId": "editorial", "direction": "차분한 화면",
                         "tokens": {"primary": "#123456", "radius": "12px"}}}
    result.update(changes)
    return result


def test_public_reads_hide_binding_and_keep_exact_current_settings(layout, settings):
    service = manager(layout)
    created = service.create(settings, layout[2])["session"]
    listing = dispatch(service, "list", {})
    view = dispatch(service, "get", {"sessionId": created["sessionId"]})
    assert set(view) == {"status", "session", "target"}
    assert view["target"] == {"status": "available"}
    assert view["session"] == created
    assert listing["sessions"][0]["sessionId"] == created["sessionId"]
    combined = json.dumps([view, listing], ensure_ascii=False)
    for private in [str(layout[0]), str(layout[1]), str(layout[2]), '"binding"', '"path"']:
        assert private not in combined


def test_web_design_save_preserves_chat_task_questions_criteria_and_next_step(layout, settings):
    service = manager(layout)
    created = service.create(settings, layout[2])["session"]
    payload = request(created)
    updated = dispatch(service, "design", payload)
    current = manager(layout).resume()["session"]
    assert updated["session"] == current
    assert current["revision"] == created["revision"] + 1
    assert current["settings"]["design"] == payload["design"]
    original = deepcopy(created["settings"])
    original["design"] = payload["design"]
    original["task"]["designScope"] = payload["designScope"]
    assert current["settings"] == original
    assert updated["target"] == {"status": "available"}
    assert not list(layout[2].iterdir())


def test_web_preserve_clears_previous_design_without_changing_requirements(layout, settings):
    settings["project"]["sourceType"] = "existing"
    settings["task"]["designScope"] = {"mode": "redesign", "scope": "전체 화면"}
    service = manager(layout)
    created = service.create(settings, layout[2])["session"]
    updated = dispatch(service, "design", request(created, designScope={"mode": "preserve", "scope": ""}))
    result = updated["session"]["settings"]
    assert result["task"]["designScope"] == {"mode": "preserve", "scope": ""}
    assert result["design"] == {"profileId": "", "direction": "", "tokens": {}}
    assert result["task"]["completionCriteria"] == created["settings"]["task"]["completionCriteria"]


def test_chat_update_conflicts_with_stale_screen_instead_of_losing_new_request(layout, settings):
    service = manager(layout)
    created = service.create(settings, layout[2])["session"]
    changed = deepcopy(created["settings"])
    changed["task"]["request"] = "채팅에서 새롭게 정한 요구사항"
    current = service.save(created["sessionId"], created["revision"], changed)["session"]
    with pytest.raises(SessionError, match="revision_conflict"):
        dispatch(manager(layout), "design", request(created))
    assert manager(layout).resume()["session"] == current


def test_concurrent_cli_save_between_web_read_and_write_uses_store_cas(layout, settings, monkeypatch):
    service = manager(layout)
    created = service.create(settings, layout[2])["session"]
    real_save = service.save
    changed = deepcopy(created["settings"])
    changed["nextStep"] = "CLI가 기록한 다음 단계"

    def racing_save(identifier, revision, raw):
        manager(layout).save(identifier, revision, changed)
        return real_save(identifier, revision, raw)

    monkeypatch.setattr(service, "save", racing_save)
    with pytest.raises(SessionError, match="revision_conflict"):
        dispatch(service, "design", request(created))
    assert manager(layout).resume()["session"]["settings"] == changed


@pytest.mark.parametrize("revision", [True, "1", 1.0, None, 0])
def test_web_revision_requires_json_integer(layout, settings, revision):
    service = manager(layout)
    created = service.create(settings, layout[2])["session"]
    with pytest.raises(SessionError, match="revision_invalid"):
        dispatch(service, "design", request(created, expectedRevision=revision))
    assert service.resume()["session"] == created


@pytest.mark.parametrize("extra", ["target", "binding", "task", "questions", "nextStep", "project", "command"])
def test_web_cannot_change_any_non_design_field(layout, settings, extra):
    service = manager(layout)
    created = service.create(settings, layout[2])["session"]
    with pytest.raises(SessionError):
        dispatch(service, "design", request(created, **{extra: "untrusted"}))
    assert service.resume()["session"] == created


def test_missing_target_is_visible_without_its_path_and_cannot_be_saved(layout, settings):
    service = manager(layout)
    created = service.create(settings, layout[2])["session"]
    layout[2].rmdir()
    view = dispatch(service, "get", {"sessionId": created["sessionId"]})
    assert view["target"] == {"status": "missing"}
    assert view["status"] == "target_unavailable"
    with pytest.raises(SessionError, match="target_unavailable"):
        dispatch(service, "design", request(created))
    assert service.export(created["sessionId"]) == created


def test_web_changes_use_the_same_secret_sanitizer_as_chat(layout, settings):
    service = manager(layout)
    created = service.create(settings, layout[2])["session"]
    payload = request(created)
    payload["design"]["direction"] = 'owner@example.com {"password":"SECRET-WEB-47"}'
    payload["design"]["tokens"]["private"] = str(layout[2])
    saved = dispatch(service, "design", payload)
    raw = json.dumps(saved)
    assert "owner@example.com" not in raw and "SECRET-WEB-47" not in raw
    assert str(layout[2]) not in raw
    assert saved["reviewFields"]


def test_fresh_process_web_cli_returns_public_document_and_rejects_duplicate_keys(layout, settings):
    created = manager(layout).create(settings, layout[2])["session"]
    result = run_cli(layout, "web", "get", data={"sessionId": created["sessionId"]})
    assert result.returncode == 0
    assert json.loads(result.stdout)["target"] == {"status": "available"}
    raw = json.dumps(request(created))[:-1] + ',"expectedRevision":1}'
    rejected = run_cli(layout, "web", "design", raw=raw)
    assert rejected.returncode == 1
    assert json.loads(rejected.stdout)["code"] == "session_duplicate_key"
    assert manager(layout).resume()["session"] == created


@pytest.mark.parametrize("operation,payload", [("forget", {}), ("create", {}), ("get", {}),
                                               ("get", {"sessionId": None}), ("list", {"target": "x"})])
def test_no_implicit_selection_creation_or_deletion(layout, operation, payload):
    with pytest.raises(SessionError):
        dispatch(manager(layout), operation, payload)
