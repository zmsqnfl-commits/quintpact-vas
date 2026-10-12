"""Fresh-process resume and execution boundaries for host-reported progress."""
from copy import deepcopy
import json

import pytest

from test_chat_session import layout, settings, manager, successful_cli, run_cli
from test_session_execution import result
from test_session_web import request
from vas_session_web import dispatch


def progress(**changes):
    value = {
        "phase": "paused",
        "summary": "ProgressOnlyMarker: 예약 구현 후 검사 전에 중단했다",
        "decisions": [{"decision": "반열린 예약 구간 사용", "reason": "인접 예약을 허용하기 위해"}],
        "changedFiles": ["booking.py"],
        "checks": [{"name": "예약 단위 검사", "command": "python -m unittest -v",
                    "status": "not-run", "exitCode": None, "summary": "사용자 요청에 따라 아직 실행하지 않음"}],
        "remaining": ["예약 경계와 실패 시 목록 보존을 확인한다"],
        "nextStep": "현재 구현을 읽고 남은 예약 단위 검사를 실행한다",
    }
    value.update(changes)
    return value


def checkpoint(layout, identifier, revision, progress_revision, value):
    return successful_cli(layout, "checkpoint", "--session", identifier,
                          "--expected-revision", str(revision),
                          "--expected-progress-revision", str(progress_revision), data=value)


def test_new_process_continues_paused_work_then_preserves_assessment_revision(layout, settings):
    service = manager(layout)
    created = service.create(settings, layout[2])
    identifier = created["session"]["sessionId"]
    assert "progress" not in created
    # The host owns the implementation; the CLI only receives a compact report.
    target = layout[2] / "booking.py"
    target.write_text("def reserve():\n    return []\n", encoding="utf-8")
    original_code = target.read_bytes()
    saved = checkpoint(layout, identifier, 1, 0, progress())
    assert saved["status"] == "resumed" and saved["session"]["revision"] == 2
    resumed = successful_cli(layout, "resume", "--session", identifier)
    assert resumed["progress"]["revision"] == 1
    assert resumed["progress"]["record"]["summary"]["checks"][0]["status"] == "not-run"
    assert resumed["progress"]["record"]["basedOn"]["sessionRevision"] == 1
    assert resumed["progress"]["record"]["savedFor"]["sessionRevision"] == 2
    assert resumed["session"]["settings"]["nextStep"] == progress()["nextStep"]
    assert target.read_bytes() == original_code

    prepared = successful_cli(layout, "prepare", "--session", identifier, "--expected-revision", "2")
    report = result(prepared)
    before = service.store.path.read_bytes()
    assessment = successful_cli(layout, "assess", "--session", identifier,
                                "--expected-revision", "2", data=report)
    assert assessment["assessment"]["status"] == "needs-verification"
    assert service.store.path.read_bytes() == before
    completed = progress(phase="awaiting-request", summary="예약 검사 통과를 보고했다",
                         remaining=[], nextStep="후속 요청을 기다린다",
                         checks=[{"name": "예약 단위 검사", "command": "python -m unittest -v",
                                  "status": "passed", "exitCode": 0, "summary": "에이전트 보고 5개 통과"}])
    checkpoint(layout, identifier, 2, 1, completed)
    final = successful_cli(layout, "resume", "--session", identifier)
    assert final["session"]["revision"] == 3 and final["progress"]["revision"] == 2
    assert final["progress"]["record"]["basedOn"]["sessionRevision"] == 2
    assert final["progress"]["record"]["summary"] == completed
    replay = run_cli(layout, "assess", "--session", identifier, "--expected-revision", "3", data=report)
    assert replay.returncode == 1
    assert json.loads(replay.stdout)["code"] == "execution_result_mismatch"
    assert target.read_bytes() == original_code


def test_progress_is_local_resume_context_not_automatic_shared_handoff_or_web_content(layout, settings):
    service = manager(layout)
    identifier = service.create(settings, layout[2])["session"]["sessionId"]
    checkpoint(layout, identifier, 1, 0, progress())
    shared = [
        successful_cli(layout, "export", "--session", identifier),
        successful_cli(layout, "prepare", "--session", identifier, "--expected-revision", "2"),
        dispatch(service, "get", {"sessionId": identifier}),
        dispatch(service, "list", {}),
    ]
    for view in shared:
        text = json.dumps(view, ensure_ascii=False)
        assert "ProgressOnlyMarker" not in text
        assert "반열린 예약 구간 사용" not in text
        assert "booking.py" not in text
        assert "progress" not in view
    current = service.resume(session_id=identifier)
    assert current["progress"]["status"] == "available"
    assert current["progress"]["referenceOnly"] is True
    assert current["progress"]["filesVerified"] is False
    before = service.store.path.read_bytes()
    (layout[2] / "changed-after-check.txt").write_text("different implementation", encoding="utf-8")
    reread = service.resume(session_id=identifier)
    assert reread["progress"]["filesVerified"] is False
    assert service.store.path.read_bytes() == before


def test_public_design_save_marks_private_progress_stale_without_exposing_it(layout, settings):
    service = manager(layout)
    identifier = service.create(settings, layout[2])["session"]["sessionId"]
    view = checkpoint(layout, identifier, 1, 0, progress())
    public = dispatch(service, "design", request(view["session"]))
    assert "progress" not in public
    assert "ProgressOnlyMarker" not in json.dumps(public)
    resumed = successful_cli(layout, "resume", "--session", identifier)
    assert resumed["progress"]["status"] == "stale"
    assert resumed["progress"]["staleReasons"]
    assert resumed["progress"]["record"] == view["progress"]["record"]


def test_old_privacy_settings_require_review_before_checkpoint(layout, settings):
    service = manager(layout)
    identifier = service.create(settings, layout[2])["session"]["sessionId"]
    raw = service.store.read()
    raw["sessions"][identifier]["document"]["settings"]["task"]["request"] = "password%3aProgressLegacyCanary42"
    service.store.path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    before = service.store.path.read_bytes()
    blocked = run_cli(layout, "checkpoint", "--session", identifier, "--expected-revision", "1",
                      "--expected-progress-revision", "0", data=progress())
    assert blocked.returncode == 1
    assert json.loads(blocked.stdout)["code"] == "session_review_required"
    assert "ProgressLegacyCanary42" not in blocked.stdout
    assert service.store.path.read_bytes() == before
    safe = successful_cli(layout, "resume", "--session", identifier)
    assert safe["reviewFields"]
    successful_cli(layout, "save", "--session", identifier, "--expected-revision", "1", data=safe["session"]["settings"])
    checkpoint(layout, identifier, 2, 0, progress())
    assert b"ProgressLegacyCanary42" not in service.store.path.read_bytes()


@pytest.mark.parametrize("raw,code", [
    ('{"phase":"paused","phase":"testing"}', "session_duplicate_key"),
    ("{" + " " * (64 * 1024) + "}", "session_input_too_large"),
    ('{"phase":"paused","summary":"report","nextStep":"wait","approved":true}', "progress_invalid"),
], ids=["duplicate-key", "oversized", "unknown-field"])
def test_bad_cli_input_preserves_existing_state(layout, settings, raw, code):
    service = manager(layout)
    identifier = service.create(settings, layout[2])["session"]["sessionId"]
    before = service.store.path.read_bytes()
    response = run_cli(layout, "checkpoint", "--session", identifier, "--expected-revision", "1",
                       "--expected-progress-revision", "0", raw=raw)
    assert response.returncode == 1
    assert json.loads(response.stdout)["code"] == code
    assert service.store.path.read_bytes() == before


def test_explicit_progress_clear_keeps_settings_and_prevents_stale_forget(layout, settings):
    service = manager(layout)
    identifier = service.create(settings, layout[2])["session"]["sessionId"]
    saved = checkpoint(layout, identifier, 1, 0, progress())
    old_settings = deepcopy(saved["session"]["settings"])
    cleared = successful_cli(layout, "clear-progress", "--session", identifier, "--expected-revision", "2")
    assert "progress" not in cleared
    assert cleared["session"]["revision"] == 3
    assert cleared["session"]["settings"] == old_settings
    stale = run_cli(layout, "forget", "--session", identifier, "--expected-revision", "2")
    assert stale.returncode == 1 and json.loads(stale.stdout)["code"] == "revision_conflict"
    assert "ProgressOnlyMarker" not in service.store.path.read_text(encoding="utf-8")
    assert successful_cli(layout, "resume", "--session", identifier)["session"]["settings"] == old_settings
