"""Behavioral checks for private chat settings, safe resume and the fresh-process CLI."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vas_session import SessionError, SessionManager


@pytest.fixture
def layout(tmp_path):
    root = tmp_path / "VAS"
    (root / "src").mkdir(parents=True)
    (root / "Run-VAS-System.bat").write_text("@echo off", encoding="utf-8")
    (root / "src" / "vas-hub.html").write_text("<title>VAS</title>", encoding="utf-8")
    target = root / "workspace" / "reservations"
    target.mkdir(parents=True)
    return root, tmp_path / "private-state", target


@pytest.fixture
def settings():
    return {"project": {"name": "예약 앱", "sourceType": "new"},
            "task": {"request": "예약 내역을 CSV로 저장", "constraints": ["로그인 기능 제외"],
                     "designScope": {"mode": "new", "scope": "예약 화면"},
                     "completionCriteria": [{"description": "CSV의 한글과 쉼표 보존",
                                             "method": "automatic", "required": True}]},
            "design": {"profileId": "editorial", "direction": "차분한 예약 화면",
                       "tokens": {"color": "#102030", "radius": "8px"}},
            "questions": ["관리자만 사용하는 앱인가요?"], "nextStep": "예약 입력 항목 확인"}


def manager(layout):
    return SessionManager(layout[0], state_home=layout[1])


def session_id(view):
    return view["session"]["sessionId"]


def assert_no_text(value, forbidden):
    def strings(item):
        if isinstance(item, dict):
            return [*item.keys(), *(text for child in item.values() for text in strings(child))]
        if isinstance(item, list):
            return [text for child in item for text in strings(child)]
        return [item] if isinstance(item, str) else []
    text = "\n".join(strings(value))
    for item in forbidden:
        assert item not in text, f"Public data retained {item!r}"


def run_cli(layout, *arguments, data=None, raw=None):
    command = [sys.executable, "-B", str(ROOT / "scripts" / "vas-session.py"),
               "--vas-root", str(layout[0]), "--state-home", str(layout[1]), *arguments]
    if raw is None and data is not None:
        raw = json.dumps(data, ensure_ascii=False)
    return subprocess.run(command, input=raw, text=True, encoding="utf-8", capture_output=True,
                          env={**os.environ, "PYTHONUTF8": "1"}, timeout=30)


def successful_cli(layout, *arguments, **kwargs):
    result = run_cli(layout, *arguments, **kwargs)
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def test_settings_survive_a_new_manager_without_losing_tokens_or_questions(layout, settings):
    created = manager(layout).create(settings, target=layout[2])
    document = created["session"]
    assert document["format"] == "vas-chat-session"
    assert document["schemaVersion"] == 1
    assert re.fullmatch(r"[a-f0-9]{32}", document["sessionId"])
    assert type(document["revision"]) is int and document["revision"] >= 1
    assert document["updatedAt"].endswith(("Z", "+00:00"))
    resumed = manager(layout).resume()
    assert resumed["status"] == "resumed"
    assert resumed["session"] == document
    assert Path(resumed["target"]["path"]) == layout[2].resolve()
    assert resumed["target"]["status"] == "available"
    restored = resumed["session"]["settings"]
    assert restored["design"]["tokens"] == settings["design"]["tokens"]
    assert restored["questions"] == settings["questions"]
    assert restored["nextStep"] == settings["nextStep"]
    criterion = restored["task"]["completionCriteria"][0]
    assert {k: criterion[k] for k in ("description", "method", "required")} == settings["task"]["completionCriteria"][0]


def test_updates_require_current_revision_and_do_not_partially_apply(layout, settings):
    service = manager(layout)
    first = service.create(settings, target=layout[2])["session"]
    changed = deepcopy(settings)
    changed["task"]["request"] = "예약 내역에 날짜 필터 추가"
    changed["questions"] = []
    second = service.save(first["sessionId"], first["revision"], changed)["session"]
    assert second["revision"] == first["revision"] + 1
    assert second["settings"]["task"]["request"] == changed["task"]["request"]
    with pytest.raises((SessionError, ValueError)):
        service.save(first["sessionId"], first["revision"], settings)
    assert manager(layout).resume(session_id=first["sessionId"])["session"] == second


def test_resaved_normalized_settings_do_not_accumulate_generated_guidance(layout, settings):
    service = manager(layout)
    first = service.create(settings, target=layout[2])["session"]
    second = service.save(first["sessionId"], first["revision"], deepcopy(first["settings"]))["session"]
    assert second["settings"] == first["settings"]
    assert second["settings"]["task"]["constraints"] == settings["task"]["constraints"]


def test_empty_multiple_and_explicit_selection_never_pick_an_unrelated_app(layout, settings):
    service = manager(layout)
    assert service.resume()["status"] == "empty"
    assert service.list() == []
    first = service.create(settings, target=layout[2])
    other_target = layout[0].parent / "other-app"
    other_target.mkdir()
    other = deepcopy(settings)
    other["project"]["name"] = "재고 앱"
    second = service.create(other, target=other_target)
    selection = service.resume()
    assert selection["status"] == "selection_required"
    assert len(selection["sessions"]) == 2
    assert service.resume(target=layout[2])["session"] == first["session"]
    assert service.resume(session_id=session_id(second))["session"] == second["session"]
    assert_no_text(service.list(), [str(layout[2]), str(other_target)])
    assert_no_text(selection, [str(layout[2]), str(other_target)])


def test_duplicate_target_is_rejected_without_replacing_original(layout, settings):
    first = manager(layout).create(settings, target=layout[2])
    settings["project"]["name"] = "동일 폴더 다른 앱"
    with pytest.raises((SessionError, ValueError)):
        manager(layout).create(settings, target=layout[2])
    assert manager(layout).resume()["session"] == first["session"]


@pytest.mark.parametrize("location", ["vas", "ancestor", "src", "docs", "missing", "file"])
def test_rejects_product_ancestors_and_non_directory_targets(layout, settings, location):
    root, _, _ = layout
    (root / "docs").mkdir()
    target = {"vas": root, "ancestor": root.parent, "src": root / "src",
              "docs": root / "docs", "missing": root.parent / "absent-app",
              "file": root / "Run-VAS-System.bat"}[location]
    with pytest.raises((SessionError, ValueError)):
        manager(layout).create(settings, target=target)
    assert not (root.parent / "absent-app").exists()
    assert manager(layout).list() == []


def test_external_target_is_supported_and_session_never_edits_app(layout, settings):
    target = layout[0].parent / "external-app"
    target.mkdir()
    original = target / "AGENTS.md"
    original.write_text("Keep this app's conventions.", encoding="utf-8")
    before = original.read_bytes()
    result = manager(layout).create(settings, target=target)
    assert Path(result["target"]["path"]) == target.resolve()
    assert original.read_bytes() == before
    assert list(target.iterdir()) == [original]


def test_missing_or_replaced_target_is_not_silently_rebound(layout, settings):
    service = manager(layout)
    first = service.create(settings, target=layout[2])
    original = layout[2]
    moved = original.with_name("moved-reservations")
    original.rename(moved)
    missing = service.resume(session_id=session_id(first))
    assert missing["status"] == "target_unavailable"
    assert missing["target"]["status"] == "missing"
    with pytest.raises((SessionError, ValueError)):
        service.save(session_id(first), first["session"]["revision"], settings)
    assert missing["session"] == first["session"]
    original.mkdir()
    replaced = service.resume(session_id=session_id(first))
    assert replaced["status"] == "target_unavailable"
    assert replaced["target"]["status"] in {"changed", "unsafe"}
    rebound = service.rebind(session_id(first), first["session"]["revision"], moved)
    assert Path(rebound["target"]["path"]) == moved.resolve()
    assert rebound["session"]["revision"] > first["session"]["revision"]
    assert manager(layout).resume(session_id=session_id(first))["target"]["status"] == "available"


def test_rebind_obeys_target_and_revision_rules(layout, settings):
    service = manager(layout)
    first = service.create(settings, target=layout[2])["session"]
    other_target = layout[0].parent / "other-app"
    other_target.mkdir()
    service.create(settings, target=other_target)
    for revision, target in [(first["revision"], layout[0]),
                             (first["revision"] - 1, other_target),
                             (first["revision"], other_target)]:
        with pytest.raises((SessionError, ValueError)):
            service.rebind(first["sessionId"], revision, target)
    assert service.resume(session_id=first["sessionId"])["session"] == first


def test_forget_clears_settings_without_removing_app_or_leaking_deleted_content(layout, settings):
    service = manager(layout)
    settings["task"]["request"] = "UNIQUE-DELETED-REQUEST-47"
    first = service.create(settings, target=layout[2])["session"]
    with pytest.raises((SessionError, ValueError)):
        service.forget(first["sessionId"], first["revision"] + 1)
    result = service.forget(first["sessionId"], first["revision"])
    assert_no_text(result, ["UNIQUE-DELETED-REQUEST-47", str(layout[2])])
    assert layout[2].is_dir()
    assert service.list() == []
    assert manager(layout).resume()["status"] == "empty"
    for file in layout[1].rglob("*"):
        if file.is_file():
            assert b"UNIQUE-DELETED-REQUEST-47" not in file.read_bytes()


def test_another_vas_installation_does_not_restore_this_installations_settings(layout, settings):
    manager(layout).create(settings, target=layout[2])
    other = layout[0].parent / "VAS-copy"
    (other / "src").mkdir(parents=True)
    (other / "Run-VAS-System.bat").write_text("@echo off", encoding="utf-8")
    (other / "src" / "vas-hub.html").write_text("VAS", encoding="utf-8")
    assert SessionManager(other, state_home=layout[1]).resume()["status"] == "empty"


def test_private_input_is_redacted_before_persistence_and_public_export(layout, settings):
    secrets = ["sk-proj-abcdefghijklmnopqrstuvwx", "owner@example.com", "010-1234-5678",
               "SecretFixturePassword_47", r"C:\Users\someone\private\file.txt"]
    settings["task"]["request"] = " ".join(secrets[:3]) + ' {"password":"' + secrets[3] + '"} ' + secrets[4]
    settings["questions"] = ["연락처 owner@example.com 확인"]
    settings["design"]["direction"] = "api_key=sk-proj-abcdefghijklmnopqrstuvwx"
    service = manager(layout)
    first = service.create(settings, target=layout[2])
    exported = service.export(session_id(first))
    assert_no_text(first["session"], secrets)
    assert_no_text(exported, [*secrets, str(layout[2]), str(layout[0])])
    assert "target" not in exported and "binding" not in exported
    for file in layout[1].rglob("*"):
        if file.is_file():
            raw = file.read_bytes()
            for secret in secrets:
                assert secret.encode() not in raw


def test_known_posix_paths_are_private_but_http_reference_paths_are_preserved(layout, settings):
    private_paths = [f"/{root}/private-fixture/config.json" for root in
                     ("opt", "tmp", "srv", "private", "media", "run", "root", "proc", "data",
                      "home", "Users", "var", "etc", "mnt", "volume1")]
    reference_urls = [f"https://docs.example.invalid/{root}/reference" for root in ("opt", "tmp", "srv", "home")]
    settings["task"]["request"] = " ".join([*private_paths, *reference_urls])
    settings["design"]["tokens"]["reference"] = "/opt/private-fixture/design.json"
    settings["questions"] = ["/srv/private-fixture/assets 확인"]
    service = manager(layout)
    created = service.create(settings, target=layout[2])
    exported = service.export(session_id(created))
    assert_no_text(exported, [*private_paths, "/opt/private-fixture/design.json", "/srv/private-fixture/assets"])
    restored = manager(layout).resume()["session"]
    assert restored == exported
    for url in reference_urls:
        assert url in restored["settings"]["task"]["request"]
    for file in layout[1].rglob("*.json"):
        assert_no_text(json.loads(file.read_text(encoding="utf-8")), private_paths)


def test_existing_design_preserve_clears_stale_design_tokens(layout, settings):
    settings["project"]["sourceType"] = "existing"
    settings["task"]["designScope"] = {"mode": "preserve", "scope": "ignored"}
    saved = manager(layout).create(settings, target=layout[2])["session"]["settings"]
    assert saved["task"]["designScope"] == {"mode": "preserve", "scope": ""}
    assert not saved["design"].get("tokens")
    assert not saved["design"].get("direction")


def test_new_app_transition_to_existing_preserve_stays_stable_on_repeated_save(layout, settings):
    service = manager(layout)
    first = service.create(settings, target=layout[2])["session"]
    transition = deepcopy(first["settings"])
    transition["project"]["sourceType"] = "existing"
    transition["task"]["designScope"] = {"mode": "preserve", "scope": "stale new-app scope"}
    second = service.save(first["sessionId"], first["revision"], transition)["session"]
    assert second["settings"]["project"]["sourceType"] == "existing"
    assert second["settings"]["design"] == {"profileId": "", "direction": "", "tokens": {}}
    assert second["settings"]["task"]["designScope"] == {"mode": "preserve", "scope": ""}
    assert second["settings"]["task"]["completionCriteria"] == first["settings"]["task"]["completionCriteria"]
    third = service.save(first["sessionId"], second["revision"], deepcopy(second["settings"]))["session"]
    assert third["settings"] == second["settings"]
    assert third["revision"] == first["revision"] + 2
    assert manager(layout).resume()["session"] == third


@pytest.mark.parametrize("path,value", [
    (("extra",), "unsupported"), (("project", "path"), "/home/private"),
    (("project", "sourceType"), "registered"), (("project", "name"), 4),
    (("task", "request"), True), (("task", "constraints"), "not a list"),
    (("task", "completionCriteria"), None), (("task", "completionCriteria"), 42),
    (("task", "completionCriteria"), "invalid"),
    (("task", "designScope", "mode"), "unknown"),
    (("task", "designScope", "unknown"), "unsupported"),
    (("task", "completionCriteria", 0, "required"), 1),
    (("task", "completionCriteria", 0, "method"), False),
    (("task", "completionCriteria", 0, "method"), "skip"),
    (("task", "completionCriteria", 0, "description"), ""),
    (("task", "completionCriteria", 0, "unexpected"), True),
    (("design", "tokens"), []), (("questions",), [42]), (("nextStep",), False),
])
def test_invalid_types_and_unknown_fields_fail_without_modifying_saved_state(layout, settings, path, value):
    service = manager(layout)
    first = service.create(settings, target=layout[2])["session"]
    raw = deepcopy(settings)
    parent = raw
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    with pytest.raises((SessionError, ValueError)):
        service.save(first["sessionId"], first["revision"], raw)
    assert service.resume(session_id=first["sessionId"])["session"] == first


@pytest.mark.parametrize("revision", [True, "1", 1.0, None])
def test_revision_is_a_strict_integer(layout, settings, revision):
    service = manager(layout)
    first = service.create(settings, target=layout[2])["session"]
    with pytest.raises((SessionError, ValueError)):
        service.save(first["sessionId"], revision, settings)
    assert service.resume(session_id=first["sessionId"])["session"] == first


@pytest.mark.parametrize("identifier", ["", False, 0, "../other-session", "f" * 31])
def test_explicit_invalid_selector_is_not_treated_as_automatic_resume(layout, settings, identifier):
    service = manager(layout)
    service.create(settings, target=layout[2])
    with pytest.raises((SessionError, ValueError)):
        service.resume(session_id=identifier)


def test_cli_settings_survive_separate_processes_and_explicit_forget(layout, settings):
    first = successful_cli(layout, "create", "--target", str(layout[2]), data=settings)["session"]
    identifier = first["sessionId"]
    resumed = successful_cli(layout, "resume", "--session", identifier)
    assert resumed["status"] == "resumed" and resumed["session"] == first
    settings["nextStep"] = "관리자 CSV 버튼 구현"
    updated = successful_cli(layout, "save", "--session", identifier,
                             "--expected-revision", str(first["revision"]), data=settings)["session"]
    assert updated["revision"] == first["revision"] + 1
    assert updated["settings"]["nextStep"] == settings["nextStep"]
    stale = run_cli(layout, "save", "--session", identifier,
                    "--expected-revision", str(first["revision"]), data=settings)
    assert stale.returncode != 0
    assert json.loads(stale.stdout)["code"] == "revision_conflict"
    assert "Traceback" not in stale.stderr
    assert_no_text(json.loads(stale.stdout), [str(layout[2]), str(layout[0])])
    exported = successful_cli(layout, "export", "--session", identifier)
    assert_no_text(exported, [str(layout[2]), str(layout[0])])
    summaries = successful_cli(layout, "list")["sessions"]
    assert len(summaries) == 1 and summaries[0]["sessionId"] == identifier
    moved = layout[2].with_name("renamed-reservations")
    layout[2].rename(moved)
    assert successful_cli(layout, "resume", "--session", identifier)["status"] == "target_unavailable"
    rebound = successful_cli(layout, "rebind", "--session", identifier,
                             "--expected-revision", str(updated["revision"]), "--target", str(moved))
    assert rebound["target"]["status"] == "available"
    successful_cli(layout, "forget", "--session", identifier,
                   "--expected-revision", str(rebound["session"]["revision"]))
    assert successful_cli(layout, "resume")["status"] == "empty"


@pytest.mark.parametrize("raw", [
    '{"project":{"name":"a","name":"b","sourceType":"new"}}',
    '{"project":{"name":"a","sourceType":"new"},"nextStep":NaN}',
    '[]', 'null', '{broken', '{"nextStep":"' + "x" * 65536 + '"}',
], ids=["duplicate-key", "nonfinite", "array", "null", "malformed", "oversized"])
def test_cli_rejects_duplicate_nonfinite_malformed_and_oversized_input(layout, raw):
    result = run_cli(layout, "create", "--target", str(layout[2]), raw=raw)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr + result.stdout
    assert manager(layout).list() == []
