"""One bounded agent-reported checkpoint; never execution evidence or authority."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import re

from vas_ai_contract import canonical, safe_relative, sensitive_key
from vas_session import LOCAL_POSIX, SessionError, require, valid_document
from vas_task_policy import safe_text

MAX_RECORD_BYTES = 16 * 1024
PHASES = {"planning", "implementing", "testing", "reviewing", "paused", "blocked", "awaiting-request"}
CHECK_STATUSES = {"passed", "failed", "skipped", "not-run"}
PAYLOAD_FIELDS = {"phase", "summary", "decisions", "changedFiles", "checks", "remaining", "nextStep"}
PUBLIC_URL = re.compile(r'''https?://[^\s'"`<>]+''', re.I)
# Dot-prefixed paths remain useful relative references in commands and next steps.
ABSOLUTE_POSIX = re.compile(r'''(?<![\w/.])/(?:[^\s'"`<>\[\]{}()]+)?''')
HASH = re.compile(r"[a-f0-9]{64}")


def _fields(value, allowed, required=None):
    require(isinstance(value, dict), "progress_invalid")
    require(not set(value) - set(allowed) and
            set(allowed if required is None else required) <= set(value), "progress_invalid")


def _local_paths(value):
    # Preserve public URLs, including query paths, after the common credential filter.
    output, cursor = [], 0
    for match in PUBLIC_URL.finditer(value):
        output.append(ABSOLUTE_POSIX.sub("[absolute-path]", value[cursor:match.start()]))
        output.append(match.group())
        cursor = match.end()
    output.append(ABSOLUTE_POSIX.sub("[absolute-path]", value[cursor:]))
    return "".join(output)


def _text(value, maximum, label, changes, *, paths=True):
    try:
        cleaned = safe_text(value, maximum, label, changes)
    except (ValueError, TypeError, UnicodeError):
        raise SessionError("progress_invalid") from None
    # Structured summaries have no raw code/log field. Refuse explicit code blocks.
    require("```" not in cleaned and "~~~" not in cleaned, "progress_invalid")
    if paths:
        safe = _local_paths(LOCAL_POSIX.sub("[absolute-path]", cleaned))
        if safe != cleaned:
            changes.append(label)
        cleaned = safe
    return cleaned


def _items(raw, key, limit):
    values = raw.get(key, [])
    require(isinstance(values, list) and len(values) <= limit, "progress_invalid")
    return values


def _sensitive_path(path):
    for part in path.lower().split("/"):
        stem, _, extension = part.rpartition(".")
        if (part == ".env" or part.startswith(".env.") or
                re.fullmatch(r"id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?", part) or
                extension in {"pem", "key", "p12", "pfx"} or
                sensitive_key(stem or part)):
            return True
    return False


def normalize_progress(raw):
    """Validate a summary allowlist, redact text, and return review field names."""
    _fields(raw, PAYLOAD_FIELDS, {"phase", "summary", "nextStep"})
    changes = []
    phase = _text(raw["phase"], 32, "phase", changes)
    require(phase in PHASES, "progress_invalid")
    summary = _text(raw["summary"], 1000, "summary", changes)
    next_step = _text(raw["nextStep"], 1000, "nextStep", changes)
    require(bool(summary) and bool(next_step), "progress_invalid")
    decisions, paths, checks, remaining = [], [], [], []
    for index, item in enumerate(_items(raw, "decisions", 8)):
        _fields(item, {"decision", "reason"})
        decisions.append({key: _text(item[key], maximum, f"decisions[{index}].{key}", changes)
                          for key, maximum in (("decision", 300), ("reason", 500))})
    for index, item in enumerate(_items(raw, "changedFiles", 40)):
        label = f"changedFiles[{index}]"
        require(isinstance(item, str), "progress_invalid")
        path = safe_relative(item)
        require(path is not None, "progress_invalid")
        cleaned = _text(item, 300, label, changes, paths=False)
        if cleaned != item.strip() or _sensitive_path(path):
            changes.append(label)
            continue
        if path != item:
            changes.append(label)
        paths.append(path)
    for index, item in enumerate(_items(raw, "checks", 10)):
        _fields(item, {"name", "command", "status", "exitCode", "summary"}, {"name", "status", "summary"})
        checked = {key: _text(item.get(key, ""), maximum, f"checks[{index}].{key}", changes)
                   for key, maximum in (("name", 120), ("command", 500), ("status", 16), ("summary", 500))}
        status, code = checked["status"], item.get("exitCode")
        require(status in CHECK_STATUSES and (code is None or type(code) is int), "progress_invalid")
        require(code is None or (status == "passed" and code == 0) or
                (status == "failed" and code != 0), "progress_invalid")
        checked["exitCode"] = code
        checks.append(checked)
    for index, item in enumerate(_items(raw, "remaining", 10)):
        remaining.append(_text(item, 500, f"remaining[{index}]", changes))
    return {"phase": phase, "summary": summary, "decisions": decisions, "changedFiles": paths,
            "checks": checks, "remaining": remaining, "nextStep": next_step}, list(dict.fromkeys(changes))


def _hash(settings):
    return hashlib.sha256(canonical(settings)).hexdigest()


def _context(value):
    _fields(value, {"sessionRevision", "settingsSha256"})
    require(type(value["sessionRevision"]) is int and value["sessionRevision"] >= 1, "progress_invalid")
    require(isinstance(value["settingsSha256"], str) and
            HASH.fullmatch(value["settingsSha256"]), "progress_invalid")


def _bounded(record):
    try:
        size = len(canonical(record))
    except (ValueError, TypeError, RecursionError):
        raise SessionError("progress_invalid") from None
    require(size <= MAX_RECORD_BYTES, "progress_too_large")


def validate_record(record):
    """Stored snapshots must already be canonical: do not repair or reveal tampering."""
    try:
        _fields(record, {"format", "schemaVersion", "revision", "recordedAt", "basedOn", "savedFor", "summary"})
        require(record["format"] == "vas-session-progress" and type(record["schemaVersion"]) is int and
                record["schemaVersion"] == 1, "progress_invalid")
        require(type(record["revision"]) is int and record["revision"] >= 1, "progress_invalid")
        require(isinstance(record["recordedAt"], str), "progress_invalid")
        timestamp = datetime.fromisoformat(record["recordedAt"])
        require(timestamp.utcoffset() == timedelta(0) and timestamp.isoformat() == record["recordedAt"],
                "progress_invalid")
        _context(record["basedOn"])
        _context(record["savedFor"])
        require(record["savedFor"]["sessionRevision"] == record["basedOn"]["sessionRevision"] + 1,
                "progress_invalid")
        normalized, changes = normalize_progress(record["summary"])
        require(normalized == record["summary"] and not changes, "progress_invalid")
        _bounded(record)
        return deepcopy(record)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        raise SessionError("progress_invalid") from None


def progress_view(record, document):
    view = {"status": "invalid", "revision": None, "referenceOnly": True,
            "filesVerified": False, "staleReasons": []}
    try:
        safe = validate_record(record)
    except SessionError:
        return view
    reasons = []
    if safe["savedFor"]["sessionRevision"] != document["revision"]:
        reasons.append("session-revision-changed")
    if safe["savedFor"]["settingsSha256"] != _hash(document["settings"]):
        reasons.append("settings-changed")
    return dict(view, status="stale" if reasons else "available", revision=safe["revision"],
                record=safe, staleReasons=reasons)


def checkpoint(manager, session_id, expected_revision, expected_progress_revision, raw):
    """Atomically pair the latest canonical settings next step and a single summary."""
    def update(data):
        record = manager._record(manager._records(data), session_id)
        manager._revision(record, expected_revision)
        require(type(expected_progress_revision) is int and expected_progress_revision >= 0,
                "progress_revision_invalid")
        previous = validate_record(record["progress"])["revision"] if "progress" in record else 0
        require(previous == expected_progress_revision, "progress_revision_conflict")
        document, changes = valid_document(record["document"])
        require(not changes, "session_review_required")
        require(manager._view(record)["status"] == "resumed", "target_unavailable")
        normalized, review = normalize_progress(raw)
        based_on = {"sessionRevision": document["revision"], "settingsSha256": _hash(document["settings"])}
        document["settings"]["nextStep"] = normalized["nextStep"]
        document["revision"] += 1
        manager._stamp(document)
        progress = {"format": "vas-session-progress", "schemaVersion": 1, "revision": previous + 1,
                    "recordedAt": document["updatedAt"], "basedOn": based_on,
                    "savedFor": {"sessionRevision": document["revision"],
                                 "settingsSha256": _hash(document["settings"])}, "summary": normalized}
        _bounded(progress)
        validate_record(progress)
        record.update(document=document, progress=progress)
        view = manager._view(record)
        if review:
            view["progressReviewFields"] = review
        return view
    return manager.store.mutate(update)


def clear_progress(manager, session_id, expected_revision):
    """Remove even invalid snapshots, retaining settings and their next step."""
    def update(data):
        record = manager._record(manager._records(data), session_id)
        manager._revision(record, expected_revision)
        if "progress" in record:
            del record["progress"]
            record["document"]["revision"] += 1
            manager._stamp(record["document"])
        return manager._view(record)
    return manager.store.mutate(update)
