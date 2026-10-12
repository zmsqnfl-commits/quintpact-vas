"""Bounded, private host-reported work records; no execution or file access."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import re

from vas_ai_contract import canonical
from vas_session import SessionError, require
from vas_session_progress import _text as progress_text
from vas_work_files import normalize_paths, validate_snapshot

MAX_BYTES = 128 * 1024
MAX_UNITS = 12
ID = re.compile(r"[a-f0-9]{32}")
HASH = re.compile(r"[a-f0-9]{64}")
CRITERION = re.compile(r"C[1-9][0-9]*")
CALL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}")
KINDS = {"implementation", "review", "verification"}
ROLES = {"main", "implementer", "designer", "reviewer"}
MODES = {"direct", "delegated"}
STATES = {"returned", "failed", "timed-out", "unreturned", "cancelled"}
OUTCOMES = {"passed", "failed", "not-run", "unknown"}
START_FIELDS = {"kind", "role", "mode", "label", "observedFiles", "writableFiles",
                "criterionIds", "command", "supersedes"}
REPORT_FIELDS = {"state", "hostCallId", "summary", "changedFiles", "exitCode", "criteria"}
WORK_FIELDS = {"format", "schemaVersion", "revision", "runId", "createdAt", "updatedAt",
               "context", "criteria", "units"}
UNIT_FIELDS = START_FIELDS | {"unitId", "startedAt", "finishedAt", "before", "after", "afterError", "result"}
CONTEXT_FIELDS = {"sessionId", "sessionRevision", "settingsSha256", "agentResourcesSha256",
                  "handoffId", "handoffPayloadSha256", "targetBindingSha256"}
SAME_ASSIGNMENT = ("kind", "role", "mode", "observedFiles", "writableFiles", "criterionIds", "command")


def _check(value):
    require(value, "work_invalid")


def _fields(value, allowed, required=None):
    _check(type(value) is dict and not set(value) - set(allowed) and
           set(allowed if required is None else required) <= set(value))


def _matches(value, pattern):
    return type(value) is str and pattern.fullmatch(value) is not None


def _choice(value, choices):
    _check(type(value) is str and value in choices)
    return value


def _text(value, limit, label, review, required=False):
    try:
        result = progress_text(value, limit, label, review)
    except (SessionError, ValueError, TypeError, UnicodeError):
        raise SessionError("work_invalid") from None
    _check(not required or bool(result))
    return result


def _paths(value, allow_empty=False):
    try:
        return normalize_paths(value, allow_empty=allow_empty)
    except (SessionError, ValueError, TypeError, UnicodeError):
        raise SessionError("work_invalid") from None


def _ids(value, known):
    _check(type(value) is list and len(value) <= 20 and
           all(_matches(item, CRITERION) and item in known for item in value))
    _check(len(set(value)) == len(value))
    return sorted(value)


def _timestamp(value):
    _check(type(value) is str and len(value) <= 40)
    try:
        instant = datetime.fromisoformat(value)
        _check(instant.utcoffset() == timedelta(0) and instant.isoformat() == value)
        return instant
    except (ValueError, TypeError, OverflowError):
        raise SessionError("work_invalid") from None


def bounded(work):
    """Check the complete record limit before attempting any persistent mutation."""
    try:
        length = len(canonical(work))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise SessionError("work_invalid") from None
    require(length <= MAX_BYTES, "work_too_large")


def normalize_start(raw, work):
    """Normalize only a caller's assignment, never create observations or IDs."""
    _fields(raw, START_FIELDS, {"kind", "role", "mode", "label", "observedFiles"})
    _check(type(work) is dict and type(work.get("criteria")) is list and type(work.get("units")) is list)
    _check(all(type(item) is dict and _matches(item.get("id"), CRITERION) for item in work["criteria"]))
    _check(all(type(unit) is dict for unit in work["units"]))
    review = []
    output = {"kind": _choice(raw["kind"], KINDS), "role": _choice(raw["role"], ROLES),
              "mode": _choice(raw["mode"], MODES),
              "label": _text(raw["label"], 200, "label", review, True),
              "observedFiles": _paths(raw["observedFiles"]),
              "writableFiles": _paths(raw.get("writableFiles", []), True),
              "criterionIds": _ids(raw.get("criterionIds", []), {item["id"] for item in work["criteria"]}),
              "command": _text(raw.get("command", ""), 500, "command", review),
              "supersedes": raw.get("supersedes")}
    _check(set(output["writableFiles"]) <= set(output["observedFiles"]))
    if output["kind"] != "implementation" or output["role"] == "reviewer":
        _check(not output["writableFiles"])
    if output["kind"] == "verification":
        _check(bool(output["command"]) and bool(output["criterionIds"]))
    previous = output["supersedes"]
    if previous is not None:
        _check(_matches(previous, ID))
        matches = [unit for unit in work["units"] if unit.get("unitId") == previous]
        _check(len(matches) == 1 and matches[0].get("result") is not None
               and matches[0].get("finishedAt") is not None)
        _check(not any(unit.get("supersedes") == previous for unit in work["units"]))
        _check(all(matches[0].get(key) == output[key] for key in SAME_ASSIGNMENT))
    return output, list(dict.fromkeys(review))


def normalize_finish(raw, unit):
    """Accept an explicit host report without promoting it to authenticated proof."""
    _fields(raw, REPORT_FIELDS, {"state", "hostCallId", "summary"})
    _check(type(unit) is dict and type(unit.get("kind")) is str and
           unit["kind"] in KINDS and type(unit.get("criterionIds")) is list)
    review = []
    state = _choice(raw["state"], STATES)
    call = raw["hostCallId"]
    _check(_matches(call, CALL))
    call_changes = []
    _check(_text(call, 160, "hostCallId", call_changes, True) == call and not call_changes)
    code = raw.get("exitCode")
    _check(code is None or type(code) is int)
    if state == "returned":
        _check(code == 0 if unit["kind"] == "verification" else code in (0, None))
    elif state == "failed":
        _check(code is None or code != 0)
    else:
        _check(code is None)
    items = raw.get("criteria", [])
    _check(type(items) is list and len(items) <= 20)
    criteria, seen = [], set()
    for index, item in enumerate(items):
        _fields(item, {"id", "status", "summary"})
        identifier = item["id"]
        _check(_matches(identifier, CRITERION) and identifier in unit["criterionIds"] and identifier not in seen)
        seen.add(identifier)
        status = _choice(item["status"], OUTCOMES)
        _check(status != "passed" or state == "returned")
        criteria.append({"id": identifier, "status": status,
                         "summary": _text(item["summary"], 500, f"criteria[{index}].summary", review, True)})
    if state == "returned" and unit["kind"] == "verification":
        _check(seen == set(unit["criterionIds"]))
    output = {"state": state, "hostCallId": call,
              "summary": _text(raw["summary"], 1000, "summary", review, True),
              "changedFiles": _paths(raw.get("changedFiles", []), True), "exitCode": code,
              "criteria": sorted(criteria, key=lambda item: item["id"])}
    return output, list(dict.fromkeys(review))


def _validate_context(value):
    _fields(value, CONTEXT_FIELDS)
    _check(_matches(value["sessionId"], ID) and type(value["sessionRevision"]) is int
           and value["sessionRevision"] >= 1)
    _check(_matches(value["handoffId"], re.compile(r"h_[a-f0-9]{32}")))
    for key in CONTEXT_FIELDS - {"sessionId", "sessionRevision", "handoffId"}:
        _check(_matches(value[key], HASH))


def _validate_unit(unit, partial, created, updated):
    _fields(unit, UNIT_FIELDS)
    _check(_matches(unit["unitId"], ID))
    _check(not any(previous["unitId"] == unit["unitId"] for previous in partial["units"]))
    started = _timestamp(unit["startedAt"])
    _check(created <= started <= updated)
    raw = {key: unit[key] for key in START_FIELDS}
    normalized, review = normalize_start(raw, partial)
    _check(normalized == raw and not review)
    before = validate_snapshot(unit["before"])
    _check([item["path"] for item in before["files"]] == unit["observedFiles"])
    if unit["supersedes"] is not None:
        previous = next(item for item in partial["units"] if item["unitId"] == unit["supersedes"])
        _check(_timestamp(previous["finishedAt"]) <= started)
    if unit["result"] is None:
        _check(unit["finishedAt"] is None and unit["after"] is None and unit["afterError"] is None)
        return
    finished = _timestamp(unit["finishedAt"])
    _check(started <= finished <= updated)
    normalized, review = normalize_finish(unit["result"], unit)
    _check(normalized == unit["result"] and not review)
    if unit["after"] is None:
        _check(_matches(unit["afterError"], re.compile(r"work_[a-z0-9_]{1,95}")))
    else:
        _check(unit["afterError"] is None)
        after = validate_snapshot(unit["after"])
        _check([item["path"] for item in after["files"]] == unit["observedFiles"])


def validate_work(work):
    """Return a safe copy only for exact, consistent and already canonical data."""
    try:
        _fields(work, WORK_FIELDS)
        _check(work["format"] == "vas-session-work" and type(work["schemaVersion"]) is int
               and work["schemaVersion"] == 1 and type(work["revision"]) is int and work["revision"] >= 1)
        _check(_matches(work["runId"], ID))
        created, updated = _timestamp(work["createdAt"]), _timestamp(work["updatedAt"])
        _check(created <= updated)
        _validate_context(work["context"])
        criteria = work["criteria"]
        _check(type(criteria) is list and len(criteria) <= 20)
        seen = set()
        for item in criteria:
            _fields(item, {"id", "method", "required", "sha256"})
            _check(_matches(item["id"], CRITERION) and item["id"] not in seen)
            seen.add(item["id"])
            _choice(item["method"], {"automatic", "manual", "static"})
            _check(type(item["required"]) is bool and _matches(item["sha256"], HASH))
        _check(type(work["units"]) is list and len(work["units"]) <= MAX_UNITS)
        partial = {"criteria": criteria, "units": []}
        observed = set()
        for unit in work["units"]:
            _validate_unit(unit, partial, created, updated)
            observed.update(unit["observedFiles"])
            partial["units"].append(unit)
        _paths(sorted(observed), True)
        bounded(work)
        return deepcopy(work)
    except (SessionError, ValueError, TypeError, KeyError, UnicodeError, OverflowError, RecursionError):
        raise SessionError("work_invalid") from None
