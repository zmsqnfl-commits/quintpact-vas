"""Bounded reference summaries, conservative freshness and privacy regression tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vas_session_progress as progress
from vas_ai_contract import canonical
from vas_session import SessionError, SessionManager
from vas_session_web import dispatch


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "vas"
    (root / "src").mkdir(parents=True)
    (root / "src/vas-hub.html").write_text("VAS", encoding="utf-8")
    (root / "Run-VAS-System.bat").write_text("@echo off", encoding="utf-8")
    target = tmp_path / "app"
    target.mkdir()
    (target / "sentinel.txt").write_text("unchanged", encoding="utf-8")
    manager = SessionManager(root, tmp_path / "state")
    session = manager.create({"project": {"name": "진행 요약", "sourceType": "new"},
                              "task": {"request": "예약 조회", "designScope": {"mode": "new"}},
                              "nextStep": "구현"}, target)["session"]
    return manager, session, target


def payload():
    return {"phase": "testing", "summary": "조회 구현 후 검사 중",
            "decisions": [{"decision": "로컬 목록 사용", "reason": "현재 요청 범위"}],
            "changedFiles": ["src/list.js", "tests/list.test.js"],
            "checks": [{"name": "목록 검사", "command": "node tests/list.test.js", "status": "passed",
                        "exitCode": 0, "summary": "자동 검사 통과 보고"}],
            "remaining": ["사용자 화면 확인"], "nextStep": "화면 확인 후 남은 요청 대조"}


def checkpoint(setup, raw=None, revision=1, progress_revision=0):
    manager, session, _ = setup
    return progress.checkpoint(manager, session["sessionId"], revision, progress_revision,
                               payload() if raw is None else raw)


def corrupt(setup, mutate):
    manager, session, _ = setup
    manager.store.mutate(lambda data: mutate(data["sessions"][session["sessionId"]]))


def test_legacy_session_keeps_optional_progress_absent(setup):
    manager, session, _ = setup
    before = manager.store.path.read_bytes()
    assert "progress" not in manager.resume(session_id=session["sessionId"])
    assert "progress" not in manager.export(session["sessionId"])
    assert progress.clear_progress(manager, session["sessionId"], 1)["session"] == session
    assert manager.store.path.read_bytes() == before


def test_roundtrip_pairs_settings_hashes_and_never_verifies_files(setup):
    manager, original, target = setup
    saved = checkpoint(setup)
    doc, view = saved["session"], saved["progress"]
    record = view["record"]
    assert saved["status"] == "resumed" and doc["revision"] == 2
    assert view["status"] == "available" and view["revision"] == 1
    assert view["referenceOnly"] is True and view["filesVerified"] is False
    assert view["staleReasons"] == []
    assert record["basedOn"] == {"sessionRevision": 1,
                                 "settingsSha256": hashlib.sha256(canonical(original["settings"])).hexdigest()}
    assert record["savedFor"] == {"sessionRevision": 2,
                                  "settingsSha256": hashlib.sha256(canonical(doc["settings"])).hexdigest()}
    assert doc["settings"]["nextStep"] == payload()["nextStep"]
    assert progress.validate_record(record) == record
    resumed = SessionManager(manager.root, manager.store.home).resume(session_id=original["sessionId"])
    assert resumed == saved
    assert list(target.iterdir()) == [target / "sentinel.txt"]
    assert (target / "sentinel.txt").read_text(encoding="utf-8") == "unchanged"
    (target / "sentinel.txt").write_text("changed by host", encoding="utf-8")
    unchanged_view = manager.resume(session_id=original["sessionId"])["progress"]
    assert unchanged_view == view and unchanged_view["filesVerified"] is False


def test_repeated_identical_checkpoint_still_advances_both_revisions(setup):
    first = checkpoint(setup)
    second = checkpoint(setup, revision=2, progress_revision=1)
    assert second["session"]["revision"] == 3 and second["progress"]["revision"] == 2
    assert second["progress"]["record"]["basedOn"] == first["progress"]["record"]["savedFor"]


@pytest.mark.parametrize("action", ["save", "same-settings", "web-design", "rebind"])
def test_any_settings_commit_or_rebind_makes_previous_summary_stale(setup, tmp_path, action):
    manager, session, _ = setup
    saved = checkpoint(setup)
    settings = deepcopy(saved["session"]["settings"])
    if action == "rebind":
        replacement = tmp_path / "replacement"
        replacement.mkdir()
        manager.rebind(session["sessionId"], 2, replacement)
    elif action == "web-design":
        dispatch(manager, "design", {"sessionId": session["sessionId"], "expectedRevision": 2,
                 "designScope": {"mode": "new", "scope": "새 목록"},
                 "design": {"profileId": "bentoStudio", "direction": "여백 확장"}})
    else:
        if action == "save":
            settings["task"]["request"] = "바뀐 요청"
        manager.save(session["sessionId"], 2, settings)
    view = manager.resume(session_id=session["sessionId"])["progress"]
    assert view["status"] == "stale" and view["record"] == saved["progress"]["record"]
    assert "session-revision-changed" in view["staleReasons"]
    assert ("settings-changed" in view["staleReasons"]) == (action in {"save", "web-design"})
    assert view["filesVerified"] is False


def test_freshness_compares_hash_even_if_revision_matches(setup):
    saved = checkpoint(setup)
    doc = deepcopy(saved["session"])
    doc["settings"]["task"]["request"] = "same revision but different settings"
    view = progress.progress_view(saved["progress"]["record"], doc)
    assert view["status"] == "stale" and view["staleReasons"] == ["settings-changed"]


@pytest.mark.parametrize("phase", sorted(progress.PHASES))
def test_phases_and_default_lists_are_canonical(phase):
    normalized, changes = progress.normalize_progress({"phase": phase, "summary": "요약", "nextStep": "다음"})
    assert normalized == {"phase": phase, "summary": "요약", "nextStep": "다음",
                          "decisions": [], "changedFiles": [], "checks": [], "remaining": []}
    assert changes == []


@pytest.mark.parametrize("field", ["approved", "evidence", "logs", "code", "binding", "status", "history"])
def test_unknown_fields_are_rejected_without_storing_input(setup, field):
    manager, _, _ = setup
    before = manager.store.path.read_bytes()
    raw = dict(payload(), **{field: "do not store"})
    with pytest.raises(SessionError, match="^progress_invalid$"):
        checkpoint(setup, raw)
    assert manager.store.path.read_bytes() == before


@pytest.mark.parametrize("raw", [None, [], True, {}, {"phase": "testing"},
    {"phase": "complete", "summary": "x", "nextStep": "x"},
    {"phase": [], "summary": "x", "nextStep": "x"},
    {"phase": "testing", "summary": " ", "nextStep": "x"},
    {"phase": "testing", "summary": "x", "nextStep": False},
    {"phase": "testing", "summary": "```python\nprint('raw')\n```", "nextStep": "x"}])
def test_required_fields_are_strict(raw):
    with pytest.raises(SessionError, match="^progress_invalid$"):
        progress.normalize_progress(raw)


@pytest.mark.parametrize("key,value", [
    ("summary", "x" * 1001), ("nextStep", "x" * 1001), ("summary", "😀" * 501),
    ("decisions", [{}] * 9), ("decisions", [{"decision": "x" * 301, "reason": "y"}]),
    ("decisions", [{"decision": "x", "reason": "y" * 501}]),
    ("decisions", [{"decision": "x"}]), ("decisions", [{"decision": "x", "reason": "y", "approved": True}]),
    ("changedFiles", ["src/a.js"] * 41), ("changedFiles", ["a" * 301]),
    ("checks", [{}] * 11), ("checks", [{"name": "x", "status": "passed"}]),
    ("checks", [{"name": "x" * 121, "status": "passed", "summary": "x"}]),
    ("checks", [{"name": "x", "status": "passed", "summary": "x" * 501}]),
    ("checks", [{"name": "x", "status": "passed", "summary": "x", "command": "x" * 501}]),
    ("checks", [{"name": "x", "status": "passed", "summary": "x", "output": "raw"}]),
    ("remaining", ["x"] * 11), ("remaining", ["x" * 501]),
    ("decisions", {}), ("checks", None), ("remaining", [False])])
def test_each_field_and_collection_limit(key, value):
    with pytest.raises(SessionError, match="^progress_invalid$"):
        progress.normalize_progress(dict(payload(), **{key: value}))


@pytest.mark.parametrize("status,code", [("passed", 0), ("failed", 1), ("failed", -9),
                                         ("passed", None), ("failed", None), ("skipped", None), ("not-run", None)])
def test_check_status_is_agent_report_only(status, code):
    raw = dict(payload(), checks=[{"name": "검사", "status": status, "exitCode": code, "summary": "보고"}])
    normalized, _ = progress.normalize_progress(raw)
    assert normalized["checks"][0] == dict(raw["checks"][0], command="")


@pytest.mark.parametrize("status,code", [("passed", 1), ("failed", 0), ("skipped", 0),
                                         ("not-run", 1), ("unknown", None), ("passed", True),
                                         ("failed", 1.0), ("passed", "0")])
def test_contradictory_or_coerced_exit_codes_rejected(status, code):
    raw = dict(payload(), checks=[{"name": "검사", "status": status, "exitCode": code, "summary": "보고"}])
    with pytest.raises(SessionError, match="^progress_invalid$"):
        progress.normalize_progress(raw)


@pytest.mark.parametrize("path", ["/unusual/private.txt", "C:\\private\\a.txt", "\\\\server\\share\\a",
                                  "../a", "src/../a", "src//a", "src/./a", "src/a\x00.js", "C:a", 1, ""])
def test_unsafe_changed_paths_are_rejected(path):
    with pytest.raises(SessionError, match="^progress_invalid$"):
        progress.normalize_progress(dict(payload(), changedFiles=[path]))


def test_every_free_text_field_redacts_credentials_contacts_and_absolute_paths(setup):
    secret = 'password="fixture-secret" email=alice@example.test /unusual/private/file C:\\local\\data'
    raw = payload()
    raw.update(summary=secret, nextStep=secret, remaining=[secret],
               decisions=[{"decision": secret, "reason": secret}],
               checks=[{"name": secret, "command": secret, "status": "failed", "summary": secret}])
    saved = checkpoint(setup, raw)
    encoded = json.dumps(saved["progress"], ensure_ascii=False)
    stored_progress = setup[0].store.read()["sessions"][setup[1]["sessionId"]]["progress"]
    assert json.dumps(stored_progress, ensure_ascii=False) in encoded
    for text in ("fixture-secret", "alice@example.test", "unusual", "local\\\\data"):
        assert text not in encoded
    assert set(saved["progressReviewFields"]) == {
        "summary", "nextStep", "remaining[0]", "decisions[0].decision", "decisions[0].reason",
        "checks[0].name", "checks[0].command", "checks[0].summary"}
    assert progress.validate_record(stored_progress) == stored_progress


def test_public_urls_relative_paths_and_human_text_survive():
    raw = dict(payload(), summary="설계 참고 https://docs.example.test/reference/guide 보존",
               changedFiles=["src\\list.js", "src/ordinary-file.js"])
    normalized, changes = progress.normalize_progress(raw)
    assert normalized["summary"] == raw["summary"]
    assert normalized["changedFiles"] == ["src/list.js", "src/ordinary-file.js"]
    assert changes == ["changedFiles[0]"]
    assert progress.normalize_progress(normalized) == (normalized, [])


@pytest.mark.parametrize("text", ["작업 폴더:/unusual/private", "보고: /custom/private/result", "run --cwd=/custom/app"])
def test_generic_absolute_posix_paths_are_redacted_after_labels(text):
    normalized, review = progress.normalize_progress(dict(payload(), summary=text))
    assert "private" not in normalized["summary"] and "/custom" not in normalized["summary"]
    assert "[absolute-path]" in normalized["summary"] and "summary" in review


@pytest.mark.parametrize("path", ["./tests/test_booking.py", "../shared/tests/check.js", "../../shared/check.js"])
def test_commands_and_next_steps_preserve_relative_paths(setup, path):
    raw = payload()
    raw["checks"][0]["command"] = "python " + path
    raw["nextStep"] = "Review " + path
    saved = checkpoint(setup, raw)
    summary = saved["progress"]["record"]["summary"]
    assert summary["checks"][0]["command"] == raw["checks"][0]["command"]
    assert summary["nextStep"] == saved["session"]["settings"]["nextStep"] == raw["nextStep"]
    assert "progressReviewFields" not in saved
    assert progress.normalize_progress(summary) == (summary, [])


@pytest.mark.parametrize("absolute", ["/custom/private/app", "cwd=/custom/private/app", "폴더:/custom/private/app"])
def test_command_and_next_step_keep_relative_reference_but_redact_absolute_paths(setup, absolute):
    raw = payload()
    text = "python ./tests/check.py " + absolute
    raw["checks"][0]["command"] = raw["nextStep"] = text
    saved = checkpoint(setup, raw)
    summary = saved["progress"]["record"]["summary"]
    for value in (summary["checks"][0]["command"], summary["nextStep"]):
        assert "./tests/check.py" in value and "[absolute-path]" in value
        assert "custom" not in value and "private" not in value
    assert set(saved["progressReviewFields"]) == {"checks[0].command", "nextStep"}


@pytest.mark.parametrize("path", [".env", ".env.production", "config/credentials.json", "secrets.json",
                                  "keys/id_rsa", "keys/server.pem", "src/alice@example.test.txt"])
def test_sensitive_filenames_are_omitted_with_review_marker(path):
    normalized, review = progress.normalize_progress(dict(payload(), changedFiles=[path, "src/a.js"]))
    assert normalized["changedFiles"] == ["src/a.js"]
    assert review == ["changedFiles[0]"]
    assert path not in json.dumps(normalized)


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(revision=True), lambda r: r.update(schemaVersion=True),
    lambda r: r.update(revision=0), lambda r: r.update(approved=True),
    lambda r: r.update(recordedAt="2026-10-12T12:00:00"),
    lambda r: r.update(recordedAt="2026-10-12T12:00:00+09:00"),
    lambda r: r["basedOn"].update(sessionRevision=True),
    lambda r: r["savedFor"].update(sessionRevision=1),
    lambda r: r["savedFor"].update(settingsSha256="invalid"),
    lambda r: r["summary"].pop("remaining"),
    lambda r: r["summary"].update(summary="  altered whitespace  "),
    lambda r: r["summary"].update(summary="password=not-for-output"),
    lambda r: r["summary"].update(changedFiles=[".env"]),
    lambda r: r["summary"]["checks"][0].pop("exitCode"),
])
def test_tampering_and_newly_sensitive_records_fail_closed_but_allow_recovery(setup, mutate):
    manager, session, target = setup
    checkpoint(setup)
    corrupt(setup, lambda record: mutate(record["progress"]))
    before = manager.store.path.read_bytes()
    view = manager.resume(session_id=session["sessionId"])
    assert view["progress"] == {"status": "invalid", "revision": None, "referenceOnly": True,
                                 "filesVerified": False, "staleReasons": []}
    assert manager.export(session["sessionId"])["revision"] == 2
    assert manager.list()[0]["sessionId"] == session["sessionId"]
    assert manager.store.path.read_bytes() == before
    with pytest.raises(SessionError, match="^progress_invalid$"):
        checkpoint(setup, revision=2, progress_revision=1)
    assert manager.store.path.read_bytes() == before
    (target / "sentinel.txt").unlink()
    target.rmdir()
    cleared = progress.clear_progress(manager, session["sessionId"], 2)
    assert cleared["session"]["revision"] == 3 and "progress" not in cleared
    assert cleared["status"] == "target_unavailable"


def test_invalid_progress_does_not_break_another_session(setup, tmp_path):
    manager, session, _ = setup
    checkpoint(setup)
    corrupt(setup, lambda record: record.update(progress={"raw": "hidden"}))
    other_target = tmp_path / "other"
    other_target.mkdir()
    other = manager.create(session["settings"], other_target)["session"]
    assert manager.resume(session_id=other["sessionId"])["session"] == other
    assert len(manager.list()) == 2
    assert manager.save(other["sessionId"], 1, other["settings"])["session"]["revision"] == 2


@pytest.mark.parametrize("expected,code", [(True, "invalid"), ("0", "invalid"), (-1, "invalid"),
                                         (None, "invalid"), (1, "conflict")])
def test_progress_revision_is_strict_and_conflicts_preserve_bytes(setup, expected, code):
    before = setup[0].store.path.read_bytes()
    with pytest.raises(SessionError, match="^progress_revision_" + code + "$"):
        checkpoint(setup, progress_revision=expected)
    assert setup[0].store.path.read_bytes() == before


def test_each_revision_guard_prevents_lost_summary(setup):
    checkpoint(setup)
    before = setup[0].store.path.read_bytes()
    with pytest.raises(SessionError, match="^revision_conflict$"):
        checkpoint(setup, revision=1, progress_revision=1)
    with pytest.raises(SessionError, match="^progress_revision_conflict$"):
        checkpoint(setup, revision=2, progress_revision=0)
    with pytest.raises(SessionError, match="^revision_conflict$"):
        progress.clear_progress(setup[0], setup[1]["sessionId"], 1)
    assert setup[0].store.path.read_bytes() == before


def test_existing_privacy_review_must_be_resolved_before_checkpoint(setup):
    corrupt(setup, lambda record: record["document"]["settings"]["task"].update(request="password=older-secret"))
    before = setup[0].store.path.read_bytes()
    with pytest.raises(SessionError, match="^session_review_required$"):
        checkpoint(setup)
    assert setup[0].store.path.read_bytes() == before


def test_checkpoint_rejects_missing_target_without_storage_change(setup):
    manager, _, target = setup
    (target / "sentinel.txt").unlink()
    target.rmdir()
    before = manager.store.path.read_bytes()
    with pytest.raises(SessionError, match="^target_unavailable$"):
        checkpoint(setup)
    assert manager.store.path.read_bytes() == before


def test_record_byte_cap_rejects_valid_individual_fields_atomically(setup):
    raw = payload()
    raw.update(summary="요" * 1000, nextStep="다" * 1000,
               decisions=[{"decision": "결" * 300, "reason": "이" * 500}] * 8,
               remaining=["남" * 500] * 10)
    progress.normalize_progress(raw)
    before = setup[0].store.path.read_bytes()
    with pytest.raises(SessionError, match="^progress_too_large$"):
        checkpoint(setup, raw)
    assert setup[0].store.path.read_bytes() == before
