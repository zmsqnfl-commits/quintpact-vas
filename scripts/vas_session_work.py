"""Local host reports bound to one prepared task and explicit file samples."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import uuid

from vas_ai_contract import canonical
from vas_session import SessionError, identity, require, valid_document


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def revision(record, expected, *, recovery=False):
    """Independent CAS also protects reports added without changing task settings."""
    from vas_work_contract import validate_work
    require(type(expected) is int and expected >= (-1 if recovery else 0), "work_revision_invalid")
    if "work" not in record:
        require(expected == 0, "work_revision_conflict")
        return None
    try:
        work = validate_work(record["work"])
    except SessionError:
        require(recovery and expected == -1, "work_invalid")
        return None
    require(work["revision"] == expected, "work_revision_conflict")
    return work


def target(manager, binding):
    try:
        path = manager._target(binding["path"])
        require(identity(path) == binding["identity"] and bool(binding["identity"][1]),
                "work_target_unavailable")
        return path
    except (OSError, SessionError):
        raise SessionError("work_target_unavailable") from None


def prepared_context(manager, session_id, number, binding):
    from vas_session_execution import prepare
    prepared = prepare(manager, session_id, number)
    require(prepared["status"] == "prepared", "execution_needs_input")
    handoff = prepared["handoff"]
    session = handoff["context"]["session"]
    context = {"sessionId": session_id, "sessionRevision": number,
               "settingsSha256": session["settingsSha256"],
               "agentResourcesSha256": session["agentResourcesSha256"],
               "handoffId": handoff["workflow"]["handoffId"],
               "handoffPayloadSha256": handoff["integrity"]["payloadSha256"],
               "targetBindingSha256": digest(binding)}
    criteria = [{"id": item["id"], "method": item["method"], "required": item["required"],
                 "sha256": digest(item)} for item in handoff["task"]["completionCriteria"]]
    return context, criteria


def work_view(raw, document, binding):
    """Only metadata freshness: this deliberately never prepares or reads app files."""
    from vas_work_contract import validate_work
    view = {"status": "invalid", "revision": None, "hostReportsVerified": False,
            "filesChecked": False, "staleReasons": []}
    try:
        work = validate_work(raw)
    except SessionError:
        return view
    context, reasons = work["context"], []
    comparisons = (("sessionId", document["sessionId"], "session-changed"),
                   ("sessionRevision", document["revision"], "session-revision-changed"),
                   ("settingsSha256", digest(document["settings"]), "settings-changed"),
                   ("targetBindingSha256", digest(binding), "target-changed"))
    for field, current, reason in comparisons:
        if context[field] != current:
            reasons.append(reason)
    try:
        from vas_session_execution import RESOURCES
        if hashlib.sha256(RESOURCES.read_bytes()).hexdigest() != context["agentResourcesSha256"]:
            reasons.append("agent-resources-changed")
    except OSError:
        reasons.append("agent-resources-unavailable")
    return dict(view, status="stale" if reasons else "available", revision=work["revision"],
                record=work, staleReasons=reasons)


def _record(manager, data, session_id, number, expected, *, recovery=False):
    record = manager._record(manager._records(data), session_id)
    manager._revision(record, number)
    return record, revision(record, expected, recovery=recovery)


def _ready_document(record):
    document, changes = valid_document(record["document"])
    require(not changes, "session_review_required")
    return document


def _commit(manager, record, work, review=()):
    from vas_work_contract import bounded, validate_work
    bounded(work)
    record["work"] = validate_work(work)
    view = manager._view(record)
    if review:
        view["workReviewFields"] = review
    return view


def open_work(manager, session_id, expected_revision, expected_work_revision):
    def update(data):
        record, previous = _record(manager, data, session_id, expected_revision, expected_work_revision)
        _ready_document(record)
        require(previous is None or all(unit["result"] is not None for unit in previous["units"]),
                "work_pending")
        context, criteria = prepared_context(manager, session_id, expected_revision, record["binding"])
        now = stamp()
        work = {"format": "vas-session-work", "schemaVersion": 1,
                "revision": (previous["revision"] if previous else 0) + 1,
                "runId": uuid.uuid4().hex, "createdAt": now, "updatedAt": now,
                "context": context, "criteria": criteria, "units": []}
        return _commit(manager, record, work)
    return manager.store.mutate(update)


def start_work(manager, session_id, expected_revision, expected_work_revision, raw):
    from vas_work_contract import normalize_start
    from vas_work_files import capture
    def update(data):
        record, work = _record(manager, data, session_id, expected_revision, expected_work_revision)
        require(work is not None, "work_not_found")
        _ready_document(record)
        context, criteria = prepared_context(manager, session_id, expected_revision, record["binding"])
        require(context == work["context"] and criteria == work["criteria"], "work_context_changed")
        normalized, review = normalize_start(raw, work)
        require(len(work["units"]) < 12, "work_too_large")
        paths = set(normalized["observedFiles"])
        for unit in work["units"]:
            paths.update(unit["observedFiles"])
        require(len(paths) <= 64, "work_too_large")
        before = capture(target(manager, record["binding"]), record["binding"]["identity"],
                         normalized["observedFiles"])
        # An external editor is not locked. Resource/settings changes cannot silently
        # attach the captured sample to another prepared task.
        require(prepared_context(manager, session_id, expected_revision, record["binding"]) ==
                (context, criteria), "work_context_changed")
        unit = dict(normalized, unitId=uuid.uuid4().hex, startedAt=stamp(), finishedAt=None,
                    before=before, after=None, afterError=None, result=None)
        work["units"].append(unit)
        work["revision"] += 1
        work["updatedAt"] = unit["startedAt"]
        view = _commit(manager, record, work, review)
        view["unitId"] = unit["unitId"]
        return view
    return manager.store.mutate(update)


def finish_work(manager, session_id, expected_revision, expected_work_revision, unit_id, raw):
    from vas_work_contract import normalize_finish
    from vas_work_files import capture
    def update(data):
        record, work = _record(manager, data, session_id, expected_revision, expected_work_revision)
        require(work is not None, "work_not_found")
        require(isinstance(unit_id, str), "work_unit_invalid")
        matches = [unit for unit in work["units"] if unit["unitId"] == unit_id]
        require(len(matches) == 1, "work_unit_not_found")
        unit = matches[0]
        require(unit["result"] is None, "work_unit_finished")
        result, review = normalize_finish(raw, unit)
        try:
            require(digest(record["binding"]) == work["context"]["targetBindingSha256"],
                    "work_target_changed")
            after = capture(target(manager, record["binding"]), record["binding"]["identity"],
                            unit["observedFiles"])
            unit.update(after=after, afterError=None)
        except (OSError, SessionError) as error:
            code = getattr(error, "code", "work_files_unavailable")
            if not code.startswith("work_"):
                code = "work_files_unavailable"
            unit.update(after=None, afterError=code)
        unit.update(result=result, finishedAt=stamp())
        work["revision"] += 1
        work["updatedAt"] = unit["finishedAt"]
        return _commit(manager, record, work, review)
    return manager.store.mutate(update)


def inspect_work(manager, session_id, expected_revision):
    from vas_work_inspection import inspect_work as inspect
    return inspect(manager, session_id, expected_revision)


def clear_work(manager, session_id, expected_revision, expected_work_revision):
    def update(data):
        record, _ = _record(manager, data, session_id, expected_revision, expected_work_revision,
                            recovery=True)
        if "work" in record:
            del record["work"]
            record["document"]["revision"] += 1
            manager._stamp(record["document"])
        return manager._view(record)
    return manager.store.mutate(update)
