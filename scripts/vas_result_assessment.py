"""Assess completion using caller-owned observations, never imported trust flags."""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

METHODS = ("automatic", "manual", "static")
OUTCOMES = ("passed", "failed", "skipped", "not-applicable")


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def criteria_valid(criteria: Any) -> bool:
    if not isinstance(criteria, list) or len(criteria) > 20:
        return False
    valid = all(isinstance(item, dict) and isinstance(item.get("id"), str)
                and re.fullmatch(r"C[1-9][0-9]*", item["id"])
                and _text(item.get("description")) and item.get("method") in METHODS
                and isinstance(item.get("required"), bool) for item in criteria)
    return bool(valid and len({item["id"] for item in criteria}) == len(criteria))


def _valid_result(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    iteration = result.get("iteration")
    if (result.get("format") != "vas-ai-result" or type(result.get("schemaVersion")) not in (int, float)
            or result["schemaVersion"] != 1 or type(iteration) not in (int, float)
            or not 1 <= iteration <= 9999 or iteration != int(iteration)
            or result.get("status") not in ("complete", "incomplete", "blocked", "failed")):
        return False
    for key, field, allowed in (("tests", "status", ("passed", "failed", "skipped")),
                                ("remaining", "severity", ("low", "medium", "high", "blocker"))):
        items = result.get(key)
        if not isinstance(items, list) or len(items) > 50 or any(
                not isinstance(item, dict) or item.get(field) not in allowed for item in items):
            return False
    evidence = result.get("evidence", [])
    return (isinstance(evidence, list) and len(evidence) <= 50 and all(
        isinstance(item, dict) and _text(item.get("criterionId")) and _text(item.get("artifactVersion")) and item.get("method") in METHODS
        and item.get("outcome") in OUTCOMES for item in evidence)
        and ("scopeViolation" not in result or isinstance(result["scopeViolation"], bool)))


def _valid_observation(item: Any, result: dict, criterion: dict) -> bool:
    if not isinstance(item, dict):
        return False
    try:
        timestamp = item.get("observedAt")
        if not _text(timestamp) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", timestamp):
            return False
        parsed = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z") != timestamp:
            return False
    except (ValueError, TypeError):
        return False
    return (item.get("criterionId") == criterion["id"] and item.get("source") == "user-direct"
            and item.get("artifactVersion") == result.get("artifactVersion")
            and item.get("method") in ("manual", "static")
            and (item["method"] == criterion["method"] or item.get("alternativeApproved") is True)
            and item.get("outcome") in OUTCOMES and _text(item.get("summary")))


def evaluate_result(result: Any, context: Any = None) -> dict[str, Any]:
    """context.observations must come from the application's own review store."""
    context = context if isinstance(context, dict) else {}
    answer: dict[str, Any] = {"status": "needs-verification", "reasons": [], "conditions": [],
                              "evidenceSource": "local-user-review"}

    def finish(status: str, reason: str | None = None) -> dict[str, Any]:
        answer["status"] = status
        if reason:
            answer["reasons"].append(reason)
        return answer

    if not _valid_result(result):
        return finish("invalid", "invalid-result")
    if context.get("linkStatus") in ("mismatch", "invalid", "unsupported"):
        return finish("invalid", "handoff-mismatch")
    criteria = context.get("criteria", [])
    if not criteria_valid(criteria):
        return finish("invalid", "invalid-criteria")
    observations = context.get("observations", [])
    observations = observations if isinstance(observations, list) else []
    failures = []
    if result["status"] == "failed":
        failures.append("reported-failure")
    if result["status"] == "blocked" or any(item["severity"] == "blocker" for item in result["remaining"]):
        failures.append("unresolved-blocker")
    if any(item["status"] == "failed" for item in result["tests"]):
        failures.append("failed-test")
    if result.get("scopeViolation") is True:
        failures.append("scope-violation")
    for criterion in criteria:
        matches = [item for item in observations if _valid_observation(item, result, criterion)]
        own = matches[-1] if matches else None
        all_submitted = [item for item in result.get("evidence", []) if item["criterionId"] == criterion["id"]]
        submitted = [item for item in all_submitted if item["artifactVersion"] == result.get("artifactVersion")]
        if len(submitted) != len(all_submitted):
            answer["reasons"].append("artifact-evidence-mismatch:" + criterion["id"])
        failed = (own and own["outcome"] == "failed") or any(item["outcome"] == "failed" for item in submitted)
        if failed:
            failures.append("failed-criterion:" + criterion["id"])
        answer["conditions"].append({"id": criterion["id"], "required": criterion["required"],
                                     "status": "failed" if failed else "confirmed" if own and own["outcome"] == "passed" else "unconfirmed",
                                     "source": ("user-direct" if own and own["outcome"] == "failed" else "agent-submitted") if failed
                                     else "user-direct" if own else "agent-submitted" if submitted else "missing"})
    if failures:
        answer["reasons"] = failures
        return finish("incomplete")
    if context.get("linkStatus") != "verified":
        answer["reasons"].append("handoff-unverified")
    if not any(item["required"] for item in criteria):
        answer["reasons"].append("missing-required-criteria")
    if not _text(result.get("artifactVersion")):
        answer["reasons"].append("missing-artifact-version")
    for item in answer["conditions"]:
        if item["required"] and item["status"] != "confirmed":
            answer["reasons"].append("unconfirmed-criterion:" + item["id"])
    return answer if answer["reasons"] else finish("complete")
