"""Assemble result v1 from one bounded host report and its original prepare receipt."""
import hashlib
import re

from vas_ai_contract import canonical, safe_relative
from vas_session import require
from vas_session_progress import _text, normalize_progress


CHANGE_ACTIONS = {"created", "modified", "deleted", "renamed"}
CHECK_STATUS = {"통과": "passed", "실패": "failed", "건너뜀": "skipped", "미실행": "not-run",
                "passed": "passed", "failed": "failed", "skipped": "skipped", "not-run": "not-run"}


def result_status(status):
    return "skipped" if status == "not-run" else status


def check_flags(values):
    require(len(values) <= 10, "finish_input_invalid")
    checks = []
    for value in values:
        name, separator, outcome = value.rpartition(":")
        status = CHECK_STATUS.get(outcome.strip().lower())
        require(separator and name.strip() and status, "finish_check_invalid")
        checks.append({"name": name.strip(), "status": status, "summary": "호스트 직접 보고"})
    return checks


def _changed_files(items):
    require(isinstance(items, list) and len(items) <= 40, "progress_invalid")
    paths, actions = [], {}
    for item in items:
        require(isinstance(item, str), "progress_invalid")
        action, separator, path = item.partition(":")
        if separator and action in CHANGE_ACTIONS:
            relative = safe_relative(path)
            require(relative and relative not in actions, "finish_changed_file_invalid")
            actions[relative] = action
            paths.append(path)
        else:
            paths.append(item)
    return paths, actions


def prepare_draft(progress, prepared_hash, artifact_version, criteria):
    """Normalize once; its digest can be verified on an idempotent retry after the session advances."""
    require(isinstance(prepared_hash, str) and re.fullmatch(r"[a-f0-9]{64}", prepared_hash),
            "finish_prepared_hash_invalid")
    require(isinstance(criteria, (tuple, list)) and len(criteria) <= 20, "finish_criterion_invalid")
    progress = dict(progress)
    paths, actions = _changed_files(progress.get("changedFiles", []))
    if "changedFiles" in progress:
        progress["changedFiles"] = paths
    # Defaults validate optional fields; the actual next step/phase come from assessment.
    normalized, _ = normalize_progress({"phase": "testing", "nextStep": "unspecified", **progress})
    changes = [{"path": path, "action": actions[path]} for path in normalized["changedFiles"] if path in actions]
    version = _text(artifact_version, 160, "artifactVersion", []) if artifact_version is not None else ""
    outcomes = {}
    for value in criteria:
        require(isinstance(value, str), "finish_criterion_invalid")
        match = re.fullmatch(r"(C[1-9][0-9]*)=(passed|failed|skipped|not-run|not-applicable):(.+)", value, re.S)
        require(match and match[1] not in outcomes, "finish_criterion_invalid")
        summary = _text(match[3], 1000, "criterionSummary", [])
        require(summary, "finish_criterion_invalid")
        outcomes[match[1]] = {"outcome": result_status(match[2]), "summary": summary}
    require(not outcomes or version, "finish_artifact_version_required")
    require(all(normalized["remaining"]), "progress_invalid")
    draft = {"preparedHash": prepared_hash, "artifactVersion": version, "outcomes": outcomes,
             "changes": changes, "normalized": normalized, "suppliedFields": sorted(progress)}
    fingerprint = hashlib.sha256(canonical(["vas-finish-draft-v1", draft])).hexdigest()
    return progress, draft, fingerprint


def build_result(handoff, draft, fingerprint):
    require(handoff["integrity"]["payloadSha256"] == draft["preparedHash"], "execution_result_mismatch")
    criteria = {row["id"]: row for row in handoff["task"]["completionCriteria"]}
    outcomes = draft["outcomes"]
    require(outcomes.keys() <= criteria.keys(), "finish_criterion_unknown")
    version = draft["artifactVersion"]
    evidence = [{"criterionId": key, "artifactVersion": version, "method": criteria[key]["method"], **value}
                for key, value in outcomes.items()]
    progress = draft["normalized"]
    tests = [{**{key: check[key] for key in ("name", "command", "summary")},
              "status": result_status(check["status"])} for check in progress["checks"]]
    results = [item["status"] for item in tests] + [item["outcome"] for item in evidence]
    required = [key for key, row in criteria.items() if row["required"]]
    if progress["phase"] == "blocked":
        status = "blocked"
    elif "failed" in results:
        status = "failed"
    elif (not progress["remaining"] and tests and all(test["status"] == "passed" for test in tests)
          and progress["phase"] != "paused" and required
          and all(outcomes.get(key, {}).get("outcome") == "passed" for key in required)):
        status = "complete"  # Host-reported only. Assessment still requires independent evidence.
    else:
        status = "incomplete"
    return {
        "format": "vas-ai-result", "schemaVersion": 1, "resultId": "r_" + fingerprint[:32],
        "handoffId": handoff["workflow"]["handoffId"], "handoffPayloadSha256": draft["preparedHash"],
        "iteration": handoff["workflow"]["iteration"], "sourceType": handoff["project"]["sourceType"],
        "generatedBy": {"tool": "VAS finish"}, "artifactVersion": version, "status": status,
        "changes": {"summary": progress["summary"], "relativeFiles": draft["changes"]},
        "tests": tests, "evidence": evidence,
        "remaining": [{"summary": text} for text in progress["remaining"]],
        "nextRecommendedTask": progress["nextStep"] if "nextStep" in draft["suppliedFields"] else "",
        "safety": {"absolutePathsExcluded": True, "secretsExcluded": True, "rawCommandOutputExcluded": True},
    }
