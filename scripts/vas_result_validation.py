"""Strict result shape validation; imported evidence always remains agent submitted."""
from __future__ import annotations
from typing import Any, Callable
import re


class ResultValidationError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.error_codes = [code]


def json_integer(value: Any, minimum: int, maximum: int) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and minimum <= value <= maximum and value == int(value)


def validate(raw: Any, expected: str | None, clean: Callable, safe_relative: Callable) -> dict:
    def fail(code):
        raise ResultValidationError(code)

    def obj(value, code):
        if not isinstance(value, dict):
            fail(code)
        return value

    def array(owner, key, maximum, item_type):
        if key not in owner:
            return []
        value = owner[key]
        if not isinstance(value, list):
            fail("invalid_" + key + "_list")
        if len(value) > maximum:
            fail("too_many_" + key)
        if any(not isinstance(item, item_type) for item in value):
            fail("invalid_" + key + "_item")
        return value

    def text(owner, key, maximum, required=False):
        if key not in owner:
            if required:
                fail("invalid_" + key)
            return ""
        value = owner[key]
        if not isinstance(value, str):
            fail("invalid_" + key)
        if len(value.encode("utf-16-le", errors="surrogatepass")) // 2 > maximum:
            fail("too_long_" + key)
        safe = clean(value, maximum)
        if required and not safe:
            fail("invalid_" + key)
        return safe

    def relative(value, code):
        safe = safe_relative(value) if isinstance(value, str) else None
        if not safe:
            fail(code)
        return safe

    def strings(owner, key, maximum):
        return [value for value in (text({"value": item}, "value", 4000) for item in array(owner, key, maximum, str)) if value]

    if not isinstance(raw, dict) or raw.get("format") != "vas-ai-result" or not json_integer(raw.get("schemaVersion"), 1, 1):
        fail("invalid_result_format")
    if not isinstance(raw.get("resultId"), str) or not re.fullmatch(r"r_[a-z0-9_-]{16,64}", raw["resultId"], re.I | re.ASCII):
        fail("invalid_result_id")
    if not isinstance(raw.get("handoffId"), str) or not re.fullmatch(r"h_[a-f0-9]{32}", raw["handoffId"], re.I | re.ASCII):
        fail("invalid_handoff_id")
    if not isinstance(raw.get("handoffPayloadSha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", raw["handoffPayloadSha256"], re.I):
        fail("invalid_handoff_hash")
    if not json_integer(raw.get("iteration"), 1, 9999):
        fail("invalid_iteration")
    source_type = raw.get("sourceType")
    if source_type not in ("new", "existing", "registered"):
        fail("invalid_source_type")
    if expected and source_type != expected and not (expected == "existing" and source_type == "registered"):
        fail("source_type_mismatch")
    status = raw.get("status")
    if status not in ("complete", "incomplete", "blocked", "failed"):
        fail("invalid_result_status")
    readback = obj(raw.get("readback", {}), "invalid_readback")
    changes = obj(raw.get("changes", {}), "invalid_changes")
    generated_by = obj(raw.get("generatedBy", {}), "invalid_generatedBy")
    safety = obj(raw.get("safety", {}), "invalid_safety_confirmation")
    checked_files = [relative(item, "unsafe_readback_path") for item in array(readback, "checkedFiles", 100, str)]
    confirmed_rules = strings(readback, "confirmedRules", 50)
    entrypoints = [relative(item, "unsafe_entrypoint_path") for item in array(readback, "confirmedEntrypoints", 50, str)]
    commands = [{"kind": text(item, "kind", 20), "command": text(item, "command", 500),
                 "source": None if item.get("source") in (None, "") else relative(item["source"], "unsafe_command_source")}
                for item in array(readback, "commands", 50, dict)]
    facts, assumptions = strings(readback, "facts", 50), strings(readback, "assumptions", 50)
    files = []
    for item in array(changes, "relativeFiles", 100, dict):
        path = relative(item.get("path"), "unsafe_result_path")
        if item.get("action") not in ("created", "modified", "deleted", "renamed"):
            fail("unsafe_result_path")
        files.append({"path": path, "action": item["action"], "fromPath": None if item.get("fromPath") in (None, "") else relative(item["fromPath"], "unsafe_result_path")})
    tests = []
    for item in array(raw, "tests", 50, dict):
        if item.get("status") not in ("passed", "failed", "skipped"):
            fail("invalid_test_status")
        tests.append({"name": text(item, "name", 200) or "검증", "command": text(item, "command", 500),
                      "status": item["status"], "summary": text(item, "summary", 1000)})
    if status == "complete" and any(item["status"] == "failed" for item in tests):
        status = "incomplete"
    remaining = []
    for item in array(raw, "remaining", 50, dict):
        if "severity" in item and item["severity"] not in ("blocker", "high", "medium", "low"):
            fail("invalid_remaining_severity")
        value = {"severity": item.get("severity", "medium"), "summary": text(item, "summary", 1000), "nextAction": text(item, "nextAction", 1000)}
        if not value["summary"] and not value["nextAction"]:
            fail("invalid_remaining_item")
        remaining.append(value)
    artifact_version = text(raw, "artifactVersion", 160)
    evidence = []
    for item in array(raw, "evidence", 50, dict):
        if item.get("method") not in ("automatic", "manual", "static"):
            fail("invalid_evidence_method")
        if item.get("outcome") not in ("passed", "failed", "skipped", "not-applicable"):
            fail("invalid_evidence_outcome")
        evidence.append({"criterionId": text(item, "criterionId", 80, True), "artifactVersion": text(item, "artifactVersion", 160, True),
                         "method": item["method"], "outcome": item["outcome"], "summary": text(item, "summary", 1000), "source": "agent-submitted"})
    if "scopeViolation" in raw and not isinstance(raw["scopeViolation"], bool):
        fail("invalid_scopeViolation")
    if any(safety.get(key) is not True for key in ("absolutePathsExcluded", "secretsExcluded", "rawCommandOutputExcluded")):
        fail("invalid_safety_confirmation")
    return {
        "format": "vas-ai-result", "schemaVersion": 1, "resultId": raw["resultId"], "handoffId": raw["handoffId"],
        "handoffPayloadSha256": raw["handoffPayloadSha256"], "iteration": int(raw["iteration"]), "sourceType": source_type,
        "status": status, "reportedStatus": raw["status"], "generatedBy": {"tool": text(generated_by, "tool", 80) or "other"},
        "readback": {"checkedFiles": checked_files, "confirmedRules": confirmed_rules, "confirmedEntrypoints": entrypoints,
                     "commands": commands, "facts": facts, "assumptions": assumptions},
        "changes": {"summary": text(changes, "summary", 8000), "relativeFiles": files}, "tests": tests, "remaining": remaining,
        "artifactVersion": artifact_version, "evidence": evidence, "scopeViolation": raw.get("scopeViolation", False),
        "nextRecommendedTask": text(raw, "nextRecommendedTask", 4000),
        "safety": {"absolutePathsExcluded": True, "secretsExcluded": True, "rawCommandOutputExcluded": True},
    }
