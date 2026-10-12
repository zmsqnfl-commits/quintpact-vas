"""Read-only comparison of selected files and unverified host return reports."""
from copy import deepcopy

from vas_session import SessionError, require
from vas_session_work import digest, prepared_context, target


def _empty(revision=None):
    return {"status": "inspected", "revision": revision, "contextMatches": False,
            "hostReportsVerified": False, "complete": False, "artifactVersion": None,
            "units": [], "reasons": [], "coveredCriteria": [], "missingCriteria": []}


def _recheck(manager, session_id, expected_revision, original):
    latest = manager._record(manager._records(manager.store.read()), session_id)
    manager._revision(latest, expected_revision)
    require(latest["document"] == original["document"] and latest["binding"] == original["binding"],
            "revision_conflict")
    require(latest.get("work") == original.get("work"), "work_revision_conflict")


def _subset(snapshot, paths):
    files = [item for item in snapshot["files"] if item["path"] in paths]
    return {"files": files, "sha256": digest(files)}


def _unit(unit, current):
    from vas_work_files import compare
    result = unit["result"]
    reasons = []
    view = {"unitId": unit["unitId"], "kind": unit["kind"], "role": unit["role"],
            "mode": unit["mode"], "state": result["state"] if result else "pending",
            "historical": False, "supersededBy": None,
            "reasons": reasons, "observedChangedFiles": [], "reportedOutOfScopeFiles": [],
            "observedOutOfScopeFiles": [], "changedSinceReturn": [], "sampleMatches": False}
    if not result:
        reasons.append("work-unreturned")
        return view
    if result["state"] != "returned":
        reasons.append("work-" + result["state"])
    view["reportedOutOfScopeFiles"] = sorted(set(result["changedFiles"]) - set(unit["writableFiles"]))
    if unit["after"] is None:
        reasons.append("work-target-unavailable" if unit["afterError"] in
                       {"work_target_changed", "work_target_unavailable"} else "work-files-unavailable")
    else:
        delta = compare(unit["before"], unit["after"], unit["writableFiles"])
        view["observedChangedFiles"] = delta["changedFiles"]
        view["observedOutOfScopeFiles"] = delta["outOfScopeFiles"]
        if current is not None:
            drift = compare(unit["after"], _subset(current, unit["observedFiles"]))
            view["changedSinceReturn"] = drift["changedFiles"]
        if unit["kind"] in {"review", "verification"}:
            if delta["changedFiles"]:
                reasons.append("work-inputs-changed")
            if view["changedSinceReturn"]:
                reasons.append("work-files-changed")
            view["sampleMatches"] = current is not None and not delta["changedFiles"] and not view["changedSinceReturn"]
    if view["reportedOutOfScopeFiles"] or view["observedOutOfScopeFiles"]:
        reasons.append("work-out-of-scope")
    if current is None:
        reasons.append("work-files-unavailable")
    # A successful tool return can still report a failed acceptance condition.
    # Another passing command must not silently erase that review finding.
    if any(item["status"] == "failed" for item in result["criteria"]):
        reasons.append("work-failed")
    if unit["kind"] == "verification" and result["state"] == "returned":
        if result["exitCode"] != 0:
            reasons.append("work-failed")
        if any(item["status"] != "passed" for item in result["criteria"]):
            reasons.append("work-criterion-unconfirmed")
    view["reasons"] = list(dict.fromkeys(reasons))
    return view


def inspect_work(manager, session_id, expected_revision):
    from vas_work_contract import validate_work
    from vas_work_files import capture
    record = manager._record(manager._records(manager.store.read()), session_id)
    manager._revision(record, expected_revision)
    require("work" in record, "work_not_found")
    original = deepcopy(record)
    try:
        work = validate_work(record["work"])
    except SessionError:
        _recheck(manager, session_id, expected_revision, original)
        return dict(_empty(), reasons=["work-invalid"])
    view = _empty(work["revision"])
    reasons = view["reasons"]
    prepared = None
    try:
        prepared = prepared_context(manager, session_id, expected_revision, record["binding"])
        view["contextMatches"] = prepared == (work["context"], work["criteria"])
    except (SessionError, OSError, ValueError):
        pass
    if not view["contextMatches"]:
        reasons.append("work-context-changed")
    paths = sorted({path for unit in work["units"] for path in unit["observedFiles"]})
    current = None
    try:
        require(digest(record["binding"]) == work["context"]["targetBindingSha256"],
                "work_target_unavailable")
        selected = target(manager, record["binding"])
        if paths:
            current = capture(selected, record["binding"]["identity"], paths)
            view["artifactVersion"] = "vas-files-" + current["sha256"]
    except (SessionError, OSError) as error:
        reasons.append("work-target-unavailable" if getattr(error, "code", "") ==
                       "work_target_unavailable" else "work-files-unavailable")
    superseded = {unit["supersedes"]: unit["unitId"] for unit in work["units"] if unit["supersedes"]}
    covered = set()
    automatic = {item["id"] for item in work["criteria"] if item["method"] == "automatic"}
    for unit in work["units"]:
        inspection = _unit(unit, current)
        if unit["unitId"] in superseded:
            # A fresh check can replace failure or stale-input evidence, but it
            # cannot erase a prior write outside the assignment. Keep that event
            # until an explicitly reopened run starts after reviewing the state.
            if inspection["reportedOutOfScopeFiles"] or inspection["observedOutOfScopeFiles"]:
                inspection.update(historical=True, supersededBy=superseded[unit["unitId"]],
                                  reasons=["work-out-of-scope"], sampleMatches=False,
                                  changedSinceReturn=[])
                view["units"].append(inspection)
                reasons.append("work-out-of-scope:" + unit["unitId"])
            continue
        view["units"].append(inspection)
        reasons.extend(reason + ":" + unit["unitId"] for reason in inspection["reasons"])
        if (unit["kind"] == "verification" and inspection["state"] == "returned" and
                inspection["sampleMatches"] and not inspection["reasons"]):
            covered.update(item["id"] for item in unit["result"]["criteria"]
                           if item["status"] == "passed" and item["id"] in automatic)
    # A concurrent write never turns the previously read snapshot into success.
    _recheck(manager, session_id, expected_revision, original)
    try:
        final = prepared_context(manager, session_id, expected_revision, record["binding"])
    except (SessionError, OSError, ValueError):
        final = None
    if final != prepared or final != (work["context"], work["criteria"]):
        view["contextMatches"] = False
        if "work-context-changed" not in reasons:
            reasons.append("work-context-changed")
    _recheck(manager, session_id, expected_revision, original)
    if not view["contextMatches"]:
        covered.clear()
    view["coveredCriteria"] = [item["id"] for item in work["criteria"] if item["id"] in covered]
    view["missingCriteria"] = [item["id"] for item in work["criteria"] if item["required"] and
                               item["method"] == "automatic" and item["id"] not in covered]
    reasons.extend("work-check-missing:" + item for item in view["missingCriteria"])
    view["reasons"] = list(dict.fromkeys(reasons))
    return view
