"""Public, design-only bridge to the same private conversation session store."""
from __future__ import annotations

from copy import deepcopy

from vas_session import SESSION_ID, fields, require


def public_view(view):
    """Allowlist fields; a local binding path must never reach an HTTP response."""
    result = {"status": view["status"], "session": deepcopy(view["session"]),
              "target": {"status": view["target"]["status"]}}
    if "reviewFields" in view:
        result["reviewFields"] = list(view["reviewFields"])
    return result


def dispatch(manager, operation, payload):
    if operation == "list":
        fields(payload, set())
        return {"sessions": manager.list()}
    if operation == "get":
        fields(payload, {"sessionId"}, {"sessionId"})
        require(isinstance(payload["sessionId"], str) and SESSION_ID.fullmatch(payload["sessionId"]),
                "session_id_invalid")
        return public_view(manager.resume(session_id=payload["sessionId"]))
    require(operation == "design", "session_operation_invalid")
    fields(payload, {"sessionId", "expectedRevision", "designScope", "design"},
           {"sessionId", "expectedRevision", "designScope", "design"})
    require(isinstance(payload["sessionId"], str) and SESSION_ID.fullmatch(payload["sessionId"]),
            "session_id_invalid")
    require(type(payload["expectedRevision"]) is int and payload["expectedRevision"] >= 1,
            "revision_invalid")
    current = manager.resume(session_id=payload["sessionId"])
    require(current["session"]["revision"] == payload["expectedRevision"], "revision_conflict")
    require(current["status"] == "resumed", "target_unavailable")
    # Keep task text, criteria, questions and next step from the exact revision read.
    settings = deepcopy(current["session"]["settings"])
    settings["task"]["designScope"] = deepcopy(payload["designScope"])
    settings["design"] = deepcopy(payload["design"])
    # save rechecks the revision while holding the store lock, including CLI races.
    return public_view(manager.save(payload["sessionId"], payload["expectedRevision"], settings))
