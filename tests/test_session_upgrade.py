"""A stricter privacy filter must not strand an otherwise canonical saved session."""
from copy import deepcopy
import json

import pytest

from test_chat_session import layout, settings, manager, run_cli, successful_cli
from test_session_execution import result
from vas_session import SessionError
from vas_session_execution import prepare, assess
from vas_session_web import dispatch

CANARY = "Stage5UpgradeCanary47"
LEGACY_REQUEST = "password%3a" + CANARY


@pytest.fixture
def legacy(layout, settings):
    service = manager(layout)
    first = service.create(settings, target=layout[2])["session"]
    other_target = layout[0].parent / "second-app"
    other_target.mkdir()
    second = service.create(settings, target=other_target)["session"]
    data = service.store.read()
    # Canonical f3f1168 settings: the earlier filter preserved an encoded colon.
    data["sessions"][first["sessionId"]]["document"]["settings"]["task"]["request"] = LEGACY_REQUEST
    service.store.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return service, first, second


def snapshot(service):
    return {str(path.relative_to(service.store.home)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in service.store.home.rglob("*") if path.is_file()}


def test_upgrade_reads_safe_views_without_writes_or_blocking_other_sessions(legacy, layout):
    service, first, second = legacy
    before = snapshot(service)
    identifier = first["sessionId"]
    summaries = successful_cli(layout, "list")["sessions"]
    assert len(summaries) == 2
    assert next(item for item in summaries if item["sessionId"] == identifier)["reviewFields"]
    for arguments in [("resume", "--session", identifier), ("export", "--session", identifier),
                      ("prepare", "--session", identifier, "--expected-revision", "1")]:
        view = successful_cli(layout, *arguments)
        assert CANARY not in json.dumps(view)
    resumed = successful_cli(layout, "resume", "--session", identifier)
    assert resumed["session"]["settings"]["task"]["request"] == "[redacted]"
    assert resumed["reviewFields"] and resumed["session"]["revision"] == 1
    public = successful_cli(layout, "web", "get", data={"sessionId": identifier})
    assert public["reviewFields"] and CANARY not in json.dumps(public)
    assert "path" not in public["target"]
    prepared = prepare(service, identifier, 1)
    assert prepared["status"] == "needs-input" and "settings.review" in prepared["missing"]
    assert CANARY not in json.dumps(prepared)
    assert service.resume(session_id=second["sessionId"])["session"] == second
    assert snapshot(service) == before


def test_unrelated_save_create_and_forget_preserve_legacy_record(legacy, settings):
    service, first, second = legacy
    original = deepcopy(service.store.read()["sessions"][first["sessionId"]])
    settings["nextStep"] = "Check CSV download"
    saved = service.save(second["sessionId"], 1, settings)["session"]
    assert saved["revision"] == 2
    target = service.root.parent / "third-app"
    target.mkdir()
    third = service.create(settings, target)["session"]
    service.forget(second["sessionId"], 2)
    assert service.store.read()["sessions"][first["sessionId"]] == original
    assert service.resume(session_id=third["sessionId"])["session"] == third
    service.forget(first["sessionId"], 1)
    assert CANARY not in service.store.path.read_text(encoding="utf-8")


def test_reviewed_save_refreshes_only_selected_session_and_invalidates_old_result(legacy, layout):
    service, first, second = legacy
    identifier = first["sessionId"]
    safe = service.resume(session_id=identifier)["session"]["settings"]
    other = deepcopy(service.store.read()["sessions"][second["sessionId"]])
    pending = prepare(service, identifier, 1)
    with pytest.raises(SessionError, match="execution_needs_input"):
        assess(service, identifier, 1, result(pending))
    saved = successful_cli(layout, "save", "--session", identifier,
                           "--expected-revision", "1", data=safe)["session"]
    assert saved["revision"] == 2 and CANARY not in service.store.path.read_text(encoding="utf-8")
    assert service.store.read()["sessions"][second["sessionId"]] == other
    assert not service.resume(session_id=identifier).get("reviewFields")
    assert prepare(service, identifier, 2)["status"] == "prepared"
    with pytest.raises(SessionError, match="revision_conflict"):
        prepare(service, identifier, 1)
    with pytest.raises(SessionError, match="execution_result_mismatch"):
        assess(service, identifier, 2, result(pending))


def test_browser_design_save_cannot_accept_unreviewed_legacy_task(legacy):
    service, first, _ = legacy
    before = snapshot(service)
    with pytest.raises(SessionError, match="session_review_required"):
        dispatch(service, "design", {"sessionId": first["sessionId"], "expectedRevision": 1,
                 "designScope": first["settings"]["task"]["designScope"],
                 "design": first["settings"]["design"]})
    assert snapshot(service) == before


def test_web_save_rechecks_privacy_review_inside_store_lock(layout, settings, monkeypatch):
    service = manager(layout)
    first = service.create(settings, layout[2])["session"]
    real_save = service.save

    def changed_before_save(identifier, revision, raw, **kwargs):
        data = service.store.read()
        data["sessions"][identifier]["document"]["settings"]["task"]["request"] = LEGACY_REQUEST
        service.store.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return real_save(identifier, revision, raw, **kwargs)

    monkeypatch.setattr(service, "save", changed_before_save)
    with pytest.raises(SessionError, match="session_review_required"):
        dispatch(service, "design", {"sessionId": first["sessionId"], "expectedRevision": 1,
                 "designScope": first["settings"]["task"]["designScope"],
                 "design": first["settings"]["design"]})
    assert service.store.read()["sessions"][first["sessionId"]]["document"]["revision"] == 1
    assert service.resume(session_id=first["sessionId"])["reviewFields"]


@pytest.mark.parametrize("path,value", [
    (("settings", "extra"), True), (("settings", "task", "request"), False),
    (("settings", "task", "completionCriteria", 0, "required"), 1),
    (("settings", "task", "completionCriteria", 0, "id"), "C7"),
    (("settings", "task", "completionCriteria", 0, "method"), "skip"),
    (("settings", "design", "tokens", "__proto__"), {"polluted": True}),
    (("settings", "task", "designScope", "extra"), "unsupported"),
    (("settings", "questions"), "not-a-list"), (("revision",), True),
    (("settings", "project", "sourceType"), "registered"),
    (("settings", "nextStep"), " noncanonical whitespace "),
])
def test_privacy_upgrade_keeps_strict_structure_and_types(legacy, layout, path, value):
    service, first, _ = legacy
    data = service.store.read()
    parent = data["sessions"][first["sessionId"]]["document"]
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    service.store.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    before = snapshot(service)
    response = run_cli(layout, "resume", "--session", first["sessionId"])
    assert response.returncode != 0 and json.loads(response.stdout)["status"] == "error"
    assert CANARY not in response.stdout + response.stderr
    assert snapshot(service) == before


@pytest.mark.parametrize("path,value", [
    (("project", "name"), LEGACY_REQUEST), (("task", "constraints", 0), LEGACY_REQUEST),
    (("task", "completionCriteria", 0, "description"), LEGACY_REQUEST),
    (("task", "designScope", "scope"), LEGACY_REQUEST),
    (("design", "profileId"), LEGACY_REQUEST), (("design", "direction"), LEGACY_REQUEST),
    (("design", "tokens", "value"), LEGACY_REQUEST),
    (("design", "tokens", "pass%77ord"), CANARY),
    (("questions", 0), LEGACY_REQUEST), (("nextStep",), LEGACY_REQUEST),
])
def test_upgrade_sanitizes_all_supported_setting_text_surfaces(legacy, path, value):
    service, first, _ = legacy
    data = service.store.read()
    parent = data["sessions"][first["sessionId"]]["document"]["settings"]
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    service.store.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    before = snapshot(service)
    view = service.resume(session_id=first["sessionId"])
    assert view["reviewFields"] and CANARY not in json.dumps(view)
    assert CANARY not in json.dumps(service.list())
    assert CANARY not in json.dumps(service.export(first["sessionId"]))
    assert snapshot(service) == before
