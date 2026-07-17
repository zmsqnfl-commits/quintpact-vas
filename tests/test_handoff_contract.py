"""VAS handoff v3 and AI result v1 contract tests."""
from __future__ import annotations

import copy
import re

import pytest

from scripts.vas_ai_contract import (
    approved_rag,
    build_prompt,
    finalize_handoff,
    normalize_handoff,
    validate_result,
)


def base_document() -> dict:
    return {
        "format": "vas-ai-handoff",
        "schemaVersion": 3,
        "generatedBy": {"name": "VAS", "version": "2.6.4"},
        "project": {"name": "demo", "sourceType": "existing", "goal": "modify", "summary": "fix"},
        "task": {"request": "fix", "constraints": [], "acceptanceCriteria": []},
        "context": {
            "requirements": {"included": True, "value": {"request": "fix"}},
            "design": {"included": True, "preset": "awwwards"},
            "rag": {"included": False, "items": []},
            "preferences": {"included": False, "items": []},
            "continuation": {"included": False},
        },
        "workflow": {"handoffId": "", "iteration": 1, "parentResultId": None, "status": "ready"},
        "assistantGuide": {"target": "codex", "pasteText": ""},
        "integrity": {"payloadSha256": None},
    }


def prompt(document: dict) -> str:
    return f"{document['workflow']['handoffId']}:{document['integrity']['payloadSha256']}"


def result_document(**updates: object) -> dict:
    result = {
        "format": "vas-ai-result",
        "schemaVersion": 1,
        "resultId": "r_1234567890abcdef",
        "handoffId": "h_1234567890abcdef1234567890abcdef",
        "handoffPayloadSha256": "a" * 64,
        "iteration": 1,
        "sourceType": "existing",
        "status": "complete",
        "generatedBy": {"tool": "test"},
        "readback": {"checkedFiles": ["src/app.js"], "confirmedRules": [], "confirmedEntrypoints": [], "commands": [], "facts": [], "assumptions": []},
        "changes": {"summary": "수정 완료", "relativeFiles": [{"path": "src/app.js", "action": "modified", "fromPath": None}]},
        "tests": [{"name": "unit", "status": "passed", "summary": "통과"}],
        "remaining": [],
        "nextRecommendedTask": "배포 확인",
        "safety": {"absolutePathsExcluded": True, "secretsExcluded": True, "rawCommandOutputExcluded": True},
    }
    result.update(updates)
    return result


def test_finalize_is_deterministic_and_non_circular() -> None:
    first = finalize_handoff(base_document(), prompt)
    second = finalize_handoff(base_document(), prompt)
    assert first == second
    assert re.fullmatch(r"h_[a-f0-9]{32}", first["workflow"]["handoffId"])
    assert re.fullmatch(r"[a-f0-9]{64}", first["integrity"]["payloadSha256"])
    assert first["workflow"]["handoffId"] in first["assistantGuide"]["pasteText"]


def test_default_prompt_is_one_shot_and_keeps_rbg() -> None:
    text = build_prompt(base_document(), "codex")
    assert "RBG(Read Before Generate)" in text
    assert "실제 파일" in text
    for hidden in ("VAS-AI-RESULT.json", "handoffId", "payloadSha256", "승인된 작업 기억", "이전 작업 연결"):
        assert hidden not in text


def test_only_explicitly_approved_rag_is_exported() -> None:
    value = {"items": [
        {"sourceId": "one", "title": "포함", "summary": "안전 요약", "userApproved": True},
        {"sourceId": "two", "title": "제외", "summary": "미승인", "userApproved": False},
        {"sourceId": "three", "title": "경로", "summary": r"C:\Users\name\secret.txt", "userApproved": True},
    ]}
    output = approved_rag(value)
    assert len(output["items"]) == 2
    assert all(item["userApproved"] for item in output["items"])
    assert "C:\\Users" not in str(output)


def test_v2_normalization_requires_rag_reapproval() -> None:
    legacy = base_document()
    legacy["schemaVersion"] = 2
    legacy.pop("workflow")
    legacy["context"]["rag"] = {"included": True, "items": [{"excerpt": "old"}]}
    converted = normalize_handoff(legacy, prompt)
    assert converted["schemaVersion"] == 3
    assert converted["workflow"]["legacySourceSchema"] == 2
    assert converted["context"]["rag"] == {"included": False, "items": []}
    assert converted["qualityGate"]["ragReviewed"] is False


def test_result_contract_normalizes_failed_complete() -> None:
    raw = result_document(tests=[{"name": "unit", "status": "failed", "summary": "1 failed"}])
    result = validate_result(raw, "existing")
    assert result["status"] == "incomplete"
    assert result["changes"]["relativeFiles"][0]["path"] == "src/app.js"


@pytest.mark.parametrize("path", ["../secret.txt", r"C:\secret.txt", "/etc/passwd"])
def test_result_contract_rejects_unsafe_paths(path: str) -> None:
    raw = result_document()
    raw["changes"]["relativeFiles"][0]["path"] = path
    with pytest.raises(ValueError, match="unsafe_result_path"):
        validate_result(raw, "existing")


def test_result_contract_rejects_wrong_source_type() -> None:
    with pytest.raises(ValueError, match="source_type_mismatch"):
        validate_result(result_document(sourceType="new"), "existing")


def test_result_contract_requires_hash_action_and_safety() -> None:
    with pytest.raises(ValueError, match="invalid_handoff_hash"):
        validate_result(result_document(handoffPayloadSha256=""), "existing")
    unsafe_action = result_document()
    unsafe_action["changes"]["relativeFiles"][0]["action"] = "executed"
    with pytest.raises(ValueError, match="unsafe_result_path"):
        validate_result(unsafe_action, "existing")
    with pytest.raises(ValueError, match="invalid_safety_confirmation"):
        validate_result(result_document(safety={}), "existing")
