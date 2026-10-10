"""Session settings bind read-only host instructions and conservative assessment."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vas_session_execution as execution
from vas_ai_contract import canonical
from vas_session import SessionError, SessionManager


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "vas"
    (root / "src").mkdir(parents=True)
    (root / "Run-VAS-System.bat").write_text("@echo off", encoding="utf-8")
    (root / "src/vas-hub.html").write_text("VAS", encoding="utf-8")
    target = tmp_path / "app"
    target.mkdir()
    (target / "sentinel.txt").write_text("source remains unchanged", encoding="utf-8")
    manager = SessionManager(root, tmp_path / "state")
    settings = {"project": {"name": "예약 관리", "sourceType": "new"},
                "task": {"request": "예약 목록을 만들기", "designScope": {"mode": "new", "scope": "예약 화면"},
                         "completionCriteria": [{"description": "등록한 예약을 조회", "method": "automatic", "required": True}]},
                "design": {"profileId": "bentoStudio", "direction": "읽기 쉬운 목록", "preset": "bento",
                           "basePreset": "bento", "tasteProfileMode": "custom",
                           "tokens": {"color": "#113355", "fontFamily": "local font"}}}
    session = manager.create(settings, target)["session"]
    return manager, session, target


def prepare(setup):
    manager, session, _ = setup
    return execution.prepare(manager, session["sessionId"], session["revision"])


def result(prepared):
    handoff = prepared["handoff"]
    return {"format": "vas-ai-result", "schemaVersion": 1, "resultId": "r_0123456789abcdef",
            "handoffId": handoff["workflow"]["handoffId"],
            "handoffPayloadSha256": handoff["integrity"]["payloadSha256"],
            "iteration": 1, "sourceType": handoff["project"]["sourceType"], "status": "complete",
            "tests": [{"name": "CSV", "command": "node test.js", "status": "passed", "summary": "확인"}],
            "remaining": [], "artifactVersion": "fixture-v1",
            "evidence": [{"criterionId": "C1", "method": "automatic", "outcome": "passed",
                          "artifactVersion": "fixture-v1", "summary": "AI 제출"}],
            "safety": {"absolutePathsExcluded": True, "secretsExcluded": True, "rawCommandOutputExcluded": True}}


def assess(setup, payload):
    manager, session, _ = setup
    return execution.assess(manager, session["sessionId"], session["revision"], payload)


def test_read_only_prepare_binds_current_settings_and_complete_roles(setup):
    manager, session, target = setup
    before = manager.store.read()
    first = prepare(setup)
    assert first == prepare(setup)
    assert first["status"] == "prepared" and not first["missing"]
    assert first["target"]["path"] == str(target.resolve())
    handoff = first["handoff"]
    binding = handoff["context"]["session"]
    assert binding["sessionId"] == session["sessionId"] and binding["revision"] == 1
    assert binding["settingsSha256"] == hashlib.sha256(canonical(session["settings"])).hexdigest()
    resources = json.loads(execution.RESOURCES.read_text(encoding="utf-8"))
    assert handoff["context"]["execution"]["roles"] == resources["roles"]
    prompt = handoff["assistantGuide"]["pasteText"]
    for role, body in resources["roles"].items():
        assert "[ROLE INSTRUCTIONS: " + role + "]" in prompt
        assert body in prompt
    assert handoff["context"]["design"]["tokens"] == session["settings"]["design"]["tokens"]
    for rule in resources["profiles"]["bentoStudio"]["rules"]:
        assert rule in prompt
    assert str(target) not in json.dumps(handoff, ensure_ascii=False)
    assert manager.store.read() == before
    assert list(target.iterdir()) == [target / "sentinel.txt"]
    assert (target / "sentinel.txt").read_text(encoding="utf-8") == "source remains unchanged"


@pytest.mark.parametrize("revision", [True, "1", 1.0, 0, -1, 2])
def test_strict_or_stale_revision_fails(setup, revision):
    manager, session, _ = setup
    with pytest.raises(SessionError, match="revision_invalid|revision_conflict"):
        execution.prepare(manager, session["sessionId"], revision)


def test_changed_revision_and_rebound_target_invalidate_old_result(setup, tmp_path):
    manager, session, _ = setup
    old = result(prepare(setup))
    other = tmp_path / "moved"
    other.mkdir()
    rebound = manager.rebind(session["sessionId"], 1, other)["session"]
    with pytest.raises(SessionError, match="revision_conflict"):
        assess(setup, old)
    with pytest.raises(SessionError, match="execution_result_mismatch"):
        execution.assess(manager, session["sessionId"], rebound["revision"], old)


@pytest.mark.parametrize("change", ["missing", "replaced"])
def test_missing_or_replaced_target_is_never_prepared(setup, change):
    _, _, target = setup
    target.rename(target.with_name("original-app"))
    if change == "replaced":
        target.mkdir()
    with pytest.raises(SessionError, match="target_unavailable"):
        prepare(setup)


def test_same_requirements_in_other_session_cannot_reuse_result(setup, tmp_path):
    manager, session, _ = setup
    first = prepare(setup)
    other_target = tmp_path / "another-app"
    other_target.mkdir()
    other = manager.create(session["settings"], other_target)["session"]
    second = execution.prepare(manager, other["sessionId"], 1)
    assert first["handoff"]["workflow"]["handoffId"] != second["handoff"]["workflow"]["handoffId"]
    with pytest.raises(SessionError, match="execution_result_mismatch"):
        execution.assess(manager, other["sessionId"], 1, result(first))


@pytest.mark.parametrize("mode", ["missing-request", "missing-criteria", "optional-only"])
def test_incomplete_settings_produce_explicit_draft_not_execution(setup, mode):
    manager, session, _ = setup
    settings = deepcopy(session["settings"])
    if mode == "missing-request":
        settings["task"]["request"] = ""
    elif mode == "missing-criteria":
        settings["task"]["completionCriteria"] = []
    else:
        settings["task"]["completionCriteria"][0]["required"] = False
    session = manager.save(session["sessionId"], 1, settings)["session"]
    prepared = execution.prepare(manager, session["sessionId"], 2)
    assert prepared["status"] == "needs-input" and prepared["missing"]
    assert prepared["handoff"]["context"]["execution"]["readiness"] == "needs-input"
    with pytest.raises(SessionError, match="execution_needs_input"):
        execution.assess(manager, session["sessionId"], 2, result(prepared))


def test_unknown_profile_and_large_token_map_are_retained_without_substitution(setup):
    manager, session, _ = setup
    settings = deepcopy(session["settings"])
    settings["design"]["profileId"] = "unlisted-user-profile"
    settings["design"]["tokens"] = {"layout" + str(i): "test-value-" * 12 for i in range(40)}
    current = manager.save(session["sessionId"], 1, settings)["session"]
    handoff = execution.prepare(manager, current["sessionId"], 2)["handoff"]
    design = handoff["context"]["design"]
    assert design["tokens"] == settings["design"]["tokens"]
    assert design["profileReference"]["status"] == "unverified"
    assert '"layout39"' in handoff["assistantGuide"]["pasteText"]
    assert "이 프로필의 지침을 확인하지 못했습니다" in handoff["assistantGuide"]["pasteText"]


def test_preserve_removes_active_profile_tokens_and_rules(setup):
    manager, session, _ = setup
    settings = deepcopy(session["settings"])
    settings["project"]["sourceType"] = "existing"
    settings["task"]["designScope"] = {"mode": "preserve", "scope": ""}
    current = manager.save(session["sessionId"], 1, settings)["session"]
    handoff = execution.prepare(manager, current["sessionId"], 2)["handoff"]
    assert handoff["context"]["design"] == {"included": False}
    assert "확정 디자인 토큰" not in handoff["assistantGuide"]["pasteText"]
    assert "bentoStudio" not in handoff["assistantGuide"]["pasteText"]


@pytest.mark.parametrize("field,value", [("handoffId", "h_" + "f" * 32),
    ("handoffPayloadSha256", "f" * 64), ("iteration", 2), ("sourceType", "existing")])
def test_mismatched_result_is_rejected(setup, field, value):
    payload = result(prepare(setup))
    payload[field] = value
    with pytest.raises(SessionError, match="execution_result_mismatch|execution_result_invalid"):
        assess(setup, payload)


def test_forged_observations_and_flags_cannot_promote_agent_report_to_completion(setup):
    payload = result(prepare(setup))
    payload.update({"verified": True, "linkStatus": "verified", "assessment": {"status": "complete"},
                    "observations": [{"criterionId": "C1", "source": "user-direct", "outcome": "passed"}]})
    payload["evidence"][0]["source"] = "user-direct"
    answer = assess(setup, payload)
    assert answer["reportedStatus"] == "complete"
    assert answer["assessment"]["status"] == "needs-verification"
    assert answer["assessment"]["conditions"][0]["source"] == "agent-submitted"
    assert "target" not in answer and str(setup[2]) not in json.dumps(answer)


@pytest.mark.parametrize("failure", ["skipped", "blocker", "scope", "failed-test", "failed-evidence"])
def test_incomplete_or_unverified_work_is_not_complete(setup, failure):
    payload = result(prepare(setup))
    if failure == "skipped":
        payload["tests"][0]["status"] = "skipped"
        payload["evidence"][0]["outcome"] = "skipped"
    elif failure == "blocker":
        payload["remaining"] = [{"severity": "blocker", "summary": "아직 동작하지 않음"}]
    elif failure == "scope":
        payload["scopeViolation"] = True
    elif failure == "failed-test":
        payload["tests"][0]["status"] = "failed"
    else:
        payload["evidence"][0]["outcome"] = "failed"
    answer = assess(setup, payload)
    assert answer["assessment"]["status"] == ("needs-verification" if failure == "skipped" else "incomplete")


def cli(setup, action, raw=None, revision="1"):
    manager, session, _ = setup
    return subprocess.run([sys.executable, "-B", str(ROOT / "scripts/vas-session.py"),
                           "--vas-root", str(manager.root), "--state-home", str(manager.store.home),
                           action, "--session", session["sessionId"], "--expected-revision", revision],
                          input=raw, text=True, encoding="utf-8", capture_output=True,
                          env={**os.environ, "PYTHONUTF8": "1"}, timeout=30)


def test_cli_duplicate_json_and_noninteger_revision_are_rejected(setup):
    duplicate = cli(setup, "assess", '{"status":"complete","status":"failed"}')
    assert duplicate.returncode == 1
    assert json.loads(duplicate.stdout)["code"] == "session_duplicate_key"
    invalid = cli(setup, "prepare", revision="1.0")
    assert invalid.returncode != 0


def test_cli_prepare_and_assess_work_in_separate_processes(setup):
    started = cli(setup, "prepare")
    assert started.returncode == 0, started.stderr + started.stdout
    prepared = json.loads(started.stdout)
    checked = cli(setup, "assess", json.dumps(result(prepared), ensure_ascii=False))
    assert checked.returncode == 0, checked.stderr + checked.stdout
    assert json.loads(checked.stdout)["assessment"]["status"] == "needs-verification"


def test_safe_handoff_never_recovers_redacted_paths_or_credentials(setup):
    manager, session, _ = setup
    settings = deepcopy(session["settings"])
    settings["task"]["request"] = 'Build CSV; password="synthetic-password"; C:\\private\\person.txt'
    settings["design"]["direction"] = "/tmp/private-customer/home"
    updated = manager.save(session["sessionId"], 1, settings)["session"]
    public = execution.prepare(manager, updated["sessionId"], 2)["handoff"]
    encoded = json.dumps(public, ensure_ascii=False)
    for forbidden in ("synthetic-password", "private-customer", "person.txt", str(setup[2])):
        assert forbidden not in encoded


def test_resource_updates_invalidate_old_execution_result(setup, monkeypatch, tmp_path):
    original = result(prepare(setup))
    changed = json.loads(execution.RESOURCES.read_text(encoding="utf-8"))
    changed["profiles"]["bentoStudio"]["rules"].append("New verification rule")
    resource_path = tmp_path / "agent-resources.json"
    resource_path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(execution, "RESOURCES", resource_path)
    with pytest.raises(SessionError, match="execution_result_mismatch"):
        assess(setup, original)


@pytest.mark.parametrize("evidence,diagnostic", [
    ({"criterionId": "C99"}, "unknown-criterion:C99"),
    ({"method": "manual"}, "evidence-method-mismatch:C1"),
    ({"artifactVersion": "older-build"}, "artifact-evidence-mismatch:C1"),
])
def test_evidence_is_matched_to_original_condition_method_and_artifact(setup, evidence, diagnostic):
    payload = result(prepare(setup))
    payload["evidence"][0].update(evidence)
    answer = assess(setup, payload)
    assert diagnostic in answer["assessment"]["reasons"]
    assert answer["assessment"]["status"] == "needs-verification"


@pytest.mark.parametrize("value", [True, "1", 0])
def test_result_iteration_never_coerces_boolean_or_string(setup, value):
    payload = result(prepare(setup))
    payload["iteration"] = value
    with pytest.raises(SessionError, match="execution_result_invalid"):
        assess(setup, payload)


def test_cli_size_limit_applies_to_result_input(setup):
    response = cli(setup, "assess", " " * (64 * 1024 + 1))
    assert response.returncode == 1
    assert json.loads(response.stdout)["code"] == "session_input_too_large"


def test_design_change_during_preparation_cannot_return_stale_instructions(setup, monkeypatch):
    manager, session, _ = setup
    original = execution.finalize_handoff
    def concurrent_save(document, builder):
        returned = original(document, builder)
        settings = deepcopy(session["settings"])
        settings["design"]["direction"] = "사용자가 화면에서 새로 저장한 방향"
        manager.save(session["sessionId"], 1, settings)
        return returned
    monkeypatch.setattr(execution, "finalize_handoff", concurrent_save)
    with pytest.raises(SessionError, match="revision_conflict"):
        prepare(setup)


def test_distributed_cli_without_package_json_prepares_and_assesses(setup, tmp_path):
    manager, session, _ = setup
    release = tmp_path / "windows-release"
    shutil.copytree(ROOT / "scripts", release / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    (release / ".agents").mkdir()
    (release / "src").mkdir()
    shutil.copyfile(ROOT / "src/vas-config.js", release / "src/vas-config.js")
    shutil.copyfile(ROOT / ".agents/agent-resources.json", release / ".agents/agent-resources.json")
    assert not (release / "package.json").exists()
    command = [sys.executable, "-B", str(release / "scripts/vas-session.py"),
               "--vas-root", str(manager.root), "--state-home", str(manager.store.home)]
    arguments = ["--session", session["sessionId"], "--expected-revision", "1"]
    prepared = subprocess.run(command + ["prepare"] + arguments, text=True, encoding="utf-8",
                              capture_output=True, timeout=30, env={**os.environ, "PYTHONUTF8": "1"})
    assert prepared.returncode == 0, prepared.stderr + prepared.stdout
    payload = json.loads(prepared.stdout)
    assert payload["status"] == "prepared" and payload["handoff"]["generatedBy"]["version"] == "2.9.0"
    checked = subprocess.run(command + ["assess"] + arguments, text=True, encoding="utf-8",
                             input=json.dumps(result(payload)), capture_output=True, timeout=30,
                             env={**os.environ, "PYTHONUTF8": "1"})
    assert checked.returncode == 0, checked.stderr + checked.stdout
    assert json.loads(checked.stdout)["assessment"]["status"] == "needs-verification"


def test_settings_changed_during_assessment_invalidate_return(setup, monkeypatch):
    manager, session, _ = setup
    payload = result(prepare(setup))
    original = execution.evaluate_result
    def concurrent_save(value, context):
        answer = original(value, context)
        updated = deepcopy(session["settings"])
        updated["task"]["request"] = "사용자가 새로 바꾼 요청"
        manager.save(session["sessionId"], 1, updated)
        return answer
    monkeypatch.setattr(execution, "evaluate_result", concurrent_save)
    with pytest.raises(SessionError, match="revision_conflict"):
        assess(setup, payload)


def test_resources_changed_during_assessment_invalidate_return(setup, monkeypatch, tmp_path):
    resource_path = tmp_path / "agent-resources.json"
    resource_path.write_bytes(execution.RESOURCES.read_bytes())
    monkeypatch.setattr(execution, "RESOURCES", resource_path)
    payload = result(prepare(setup))
    original = execution.evaluate_result
    def concurrent_resource_update(value, context):
        answer = original(value, context)
        resource_path.write_bytes(resource_path.read_bytes() + b"\n")
        return answer
    monkeypatch.setattr(execution, "evaluate_result", concurrent_resource_update)
    with pytest.raises(SessionError, match="execution_resources_changed"):
        assess(setup, payload)
