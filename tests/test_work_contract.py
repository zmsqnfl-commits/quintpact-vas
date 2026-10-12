"""Pure reports do not gain authority; schemas bind exact assignments and samples."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vas_ai_contract import canonical
from vas_session import SessionError
import vas_work_contract as contract

NOW = "2026-10-12T01:00:00+00:00"
LATER = "2026-10-12T01:01:00+00:00"
LAST = "2026-10-12T01:02:00+00:00"


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def snapshot(paths=("app.py", "tests/test_app.py"), missing=()):
    files = [{"path": path, "state": "missing" if path in missing else "file",
              "bytes": None if path in missing else 5,
              "sha256": None if path in missing else "f" * 64} for path in sorted(paths)]
    return {"files": files, "sha256": digest(files)}


def work():
    return {"format": "vas-session-work", "schemaVersion": 1, "revision": 1,
            "runId": "1" * 32, "createdAt": NOW, "updatedAt": LAST,
            "context": {"sessionId": "2" * 32, "sessionRevision": 7,
                        "settingsSha256": "a" * 64, "agentResourcesSha256": "b" * 64,
                        "handoffId": "h_" + "c" * 32, "handoffPayloadSha256": "d" * 64,
                        "targetBindingSha256": "e" * 64},
            "criteria": [{"id": "C1", "method": "automatic", "required": True, "sha256": "3" * 64},
                         {"id": "C2", "method": "static", "required": False, "sha256": "4" * 64}],
            "units": []}


def start(**overrides):
    return dict(kind="verification", role="main", mode="direct", label="원본 검사",
                observedFiles=["app.py", "tests/test_app.py"], writableFiles=[],
                criterionIds=["C1"], command="python -m pytest tests/test_app.py",
                supersedes=None, **{}) | overrides


def report(**overrides):
    return {"state": "returned", "hostCallId": "call_fixture-001", "summary": "검사 통과 보고",
            "changedFiles": [], "exitCode": 0,
            "criteria": [{"id": "C1", "status": "passed", "summary": "요구 조건 통과 보고"}]} | overrides


def unit(*, terminal=True, identifier="5" * 32, **overrides):
    value = start() | {"unitId": identifier, "startedAt": NOW,
                       "finishedAt": LATER if terminal else None,
                       "before": snapshot(), "after": snapshot() if terminal else None,
                       "afterError": None, "result": report() if terminal else None}
    return value | overrides


def valid_record():
    value = work()
    value["units"].append(unit())
    return value


def invalid(function, *args):
    with pytest.raises(SessionError) as caught:
        function(*args)
    assert caught.value.code == "work_invalid"


def test_roundtrip_returns_independent_copy_and_no_trust_fields():
    original = valid_record()
    actual = contract.validate_work(original)
    assert actual == original and actual is not original
    actual["units"][0]["result"]["summary"] = "changed"
    assert original["units"][0]["result"]["summary"] == "검사 통과 보고"
    assert "verified" not in canonical(original).decode() and "accepted" not in original


def test_pending_and_unavailable_terminal_are_distinct_valid_records():
    value = work()
    value["units"] = [unit(terminal=False)]
    assert contract.validate_work(value) == value
    value["units"] = [unit(after=None, afterError="work_files_path_invalid")]
    assert contract.validate_work(value) == value


def test_start_defaults_and_sorting_are_canonical_without_mutating_input():
    raw = {"kind": "implementation", "role": "implementer", "mode": "delegated",
           "label": "기능 구현", "observedFiles": ["tests/test_app.py", "app.py"]}
    before = deepcopy(raw)
    value, review = contract.normalize_start(raw, work())
    assert raw == before and not review
    assert value == start(kind="implementation", role="implementer", mode="delegated",
                          label="기능 구현", criterionIds=[], command="")
    value, _ = contract.normalize_start(start(criterionIds=["C2", "C1"]), work())
    assert value["criterionIds"] == ["C1", "C2"]


def test_free_text_redaction_reports_fields_but_does_not_execute_commands():
    raw = start(label="연락 person@example.com", command="pytest /tmp/private-test.py")
    normalized, review = contract.normalize_start(raw, work())
    assert review == ["label", "command"]
    assert "person@example.com" not in str(normalized) and "/tmp/private-test.py" not in str(normalized)
    finish = report(summary="password=fixture-private", criteria=[{"id": "C1", "status": "passed",
                                                                  "summary": "문서 /home/fixture/report"}])
    normalized, review = contract.normalize_finish(finish, unit())
    assert set(review) == {"summary", "criteria[0].summary"}
    assert "fixture-private" not in str(normalized) and "/home/fixture" not in str(normalized)


@pytest.mark.parametrize("field,value", [
    ("kind", "execute"), ("kind", []), ("role", "admin"), ("mode", "sandbox"),
    ("label", ""), ("label", 1), ("label", "x" * 201),
    ("observedFiles", []), ("observedFiles", ["../app.py"]),
    ("observedFiles", ["app.py", "APP.py"]), ("observedFiles", [".env"]),
    ("observedFiles", ["/home/private.py"]), ("observedFiles", ["app.py "]),
    ("writableFiles", ["app.py"]), ("criterionIds", []), ("criterionIds", ["C99"]),
    ("criterionIds", ["C1", "C1"]), ("criterionIds", [True]),
    ("command", ""), ("command", "```python\nsecret```"), ("command", "x" * 501),
    ("supersedes", "unknown"), ("rawLog", "not allowed"), ("userApproved", True),
], ids=lambda value: str(value)[:30])
def test_start_rejects_invalid_shape_scope_or_privacy_selector(field, value):
    invalid(contract.normalize_start, start(**{field: value}), work())


@pytest.mark.parametrize("kind", ["implementation", "review"])
def test_non_verification_may_have_no_command_or_criteria(kind):
    normalized, _ = contract.normalize_start(start(kind=kind, command="", criterionIds=[]), work())
    assert normalized["command"] == "" and normalized["criterionIds"] == []


def test_implementation_cannot_claim_writes_outside_observed_files():
    invalid(contract.normalize_start, start(kind="implementation", writableFiles=["other.py"]), work())
    normalized, _ = contract.normalize_start(start(kind="implementation", writableFiles=["app.py"]), work())
    assert normalized["writableFiles"] == ["app.py"]


def test_reviewer_cannot_acquire_writable_scope_using_implementation_kind():
    invalid(contract.normalize_start, start(kind="implementation", role="reviewer", writableFiles=["app.py"]), work())


@pytest.mark.parametrize("state,code", [("returned", 0), ("failed", 1), ("failed", None),
                                       ("timed-out", None), ("unreturned", None), ("cancelled", None)])
def test_report_states_remain_host_reports(state, code):
    criteria = [{"id": "C1", "status": "passed" if state == "returned" else "not-run", "summary": "실제 보고"}]
    expected = report(state=state, exitCode=code, criteria=criteria)
    actual, changes = contract.normalize_finish(expected, unit())
    assert actual == expected and not changes


@pytest.mark.parametrize("field,value", [
    ("state", "complete"), ("state", []), ("hostCallId", ""),
    ("hostCallId", "person@example.com"), ("hostCallId", "sk-" + "a" * 24),
    ("hostCallId", "run with spaces"), ("hostCallId", "x" * 161),
    ("summary", ""), ("summary", "x" * 1001), ("summary", True),
    ("exitCode", True), ("exitCode", 0.0), ("exitCode", "0"), ("exitCode", None),
    ("exitCode", 1), ("criteria", []),
    ("criteria", [{"id": "C2", "status": "passed", "summary": "unassigned"}]),
    ("criteria", [{"id": "C1", "status": "complete", "summary": "bad status"}]),
    ("criteria", [{"id": "C1", "status": "passed", "summary": ""}]),
    ("changedFiles", [".env"]), ("rawLog", "not allowed"), ("approved", True),
], ids=lambda value: str(value)[:30])
def test_report_rejects_impossible_success_unknown_keys_and_sensitive_ids(field, value):
    invalid(contract.normalize_finish, report(**{field: value}), unit())


@pytest.mark.parametrize("state,code", [("failed", 0), ("timed-out", 1), ("unreturned", 0), ("cancelled", -1)])
def test_report_state_and_exit_must_agree(state, code):
    invalid(contract.normalize_finish, report(state=state, exitCode=code, criteria=[]), unit())


@pytest.mark.parametrize("state", ["failed", "timed-out", "unreturned", "cancelled"])
def test_non_returned_cannot_claim_any_passed_criterion(state):
    invalid(contract.normalize_finish, report(state=state, exitCode=None), unit())


def test_semantic_failure_can_follow_successful_command_exit():
    actual, _ = contract.normalize_finish(report(criteria=[{"id": "C1", "status": "failed",
                                                            "summary": "출력 의미가 조건과 다름"}]), unit())
    assert actual["state"] == "returned" and actual["exitCode"] == 0
    assert actual["criteria"][0]["status"] == "failed"


def test_reported_out_of_scope_files_are_retained_for_inspection_not_hidden():
    actual, review = contract.normalize_finish(report(changedFiles=["outside.py", "app.py"]), unit())
    assert actual["changedFiles"] == ["app.py", "outside.py"] and not review


def test_implementation_return_may_have_null_exit_and_partial_criteria():
    assigned = unit(kind="implementation", writableFiles=["app.py"])
    actual, _ = contract.normalize_finish(report(exitCode=None, criteria=[]), assigned)
    assert actual["exitCode"] is None


def test_duplicate_criteria_reports_are_rejected_and_order_normalizes():
    invalid(contract.normalize_finish, report(criteria=report()["criteria"] * 2), unit())
    reports = [{"id": identifier, "status": "passed", "summary": "검사 보고"} for identifier in ["C2", "C1"]]
    actual, _ = contract.normalize_finish(report(criteria=reports), unit(criterionIds=["C1", "C2"]))
    assert [item["id"] for item in actual["criteria"]] == ["C1", "C2"]


@pytest.mark.parametrize("path,value", [
    (("format",), "other"), (("schemaVersion",), True), (("revision",), 0),
    (("revision",), 1.0), (("runId",), "A" * 32), (("createdAt",), "2026-10-12"),
    (("createdAt",), "2026-10-12T10:00:00+09:00"), (("updatedAt",), "2026-10-11T00:00:00+00:00"),
    (("context", "sessionRevision"), True), (("context", "sessionId"), "x" * 32),
    (("context", "settingsSha256"), "x" * 64), (("context", "targetBindingSha256"), "private"),
    (("context", "handoffId"), "h_wrong"), (("context", "path"), "C:/Users/private"),
    (("criteria", 0, "required"), 1), (("criteria", 0, "id"), "C0"),
    (("criteria", 0, "method"), "user-direct"), (("criteria", 0, "sha256"), "short"),
    (("units", 0, "unitId"), "bad"), (("units", 0, "startedAt"), LAST),
    (("units", 0, "finishedAt"), None), (("units", 0, "afterError"), "work_files_unavailable"),
    (("units", 0, "result", "summary"), "password=fixture-private"),
    (("units", 0, "before", "sha256"), "0" * 64), (("units", 0, "command"), " python -m pytest "),
    (("units", 0, "result", "approved"), True),
], ids=lambda value: str(value)[:50])
def test_stored_record_rejects_invalid_or_noncanonical_fields(path, value):
    current = valid_record()
    target = current
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value
    invalid(contract.validate_work, current)


def test_duplicate_units_criteria_and_cross_sample_coverage_are_rejected():
    duplicate = valid_record()
    duplicate["units"].append(deepcopy(duplicate["units"][0]))
    invalid(contract.validate_work, duplicate)
    duplicate = valid_record()
    duplicate["criteria"].append(deepcopy(duplicate["criteria"][0]))
    invalid(contract.validate_work, duplicate)
    for key in ("before", "after"):
        candidate = valid_record()
        candidate["units"][0][key] = snapshot(["other.py"])
        invalid(contract.validate_work, candidate)


def test_pending_terminal_shapes_cannot_be_mixed():
    for key, value in [("after", snapshot()), ("afterError", "work_files_unavailable"), ("finishedAt", LATER)]:
        candidate = work()
        candidate["units"] = [unit(terminal=False, **{key: value})]
        invalid(contract.validate_work, candidate)
    candidate = valid_record()
    candidate["units"][0]["after"] = None
    invalid(contract.validate_work, candidate)
    candidate["units"][0]["afterError"] = "/home/private/error"
    invalid(contract.validate_work, candidate)


def test_retry_is_identical_assignment_but_new_identity_and_later_observation():
    candidate = valid_record()
    retry = unit(identifier="6" * 32, supersedes="5" * 32, startedAt=LATER,
                 finishedAt=LAST, label="실패 검사 다시 확인")
    candidate["units"].append(retry)
    assert contract.validate_work(candidate) == candidate
    # Reports before the retry's own start cannot be relabelled into new execution.
    candidate["units"][1]["startedAt"] = NOW
    invalid(contract.validate_work, candidate)


@pytest.mark.parametrize("change", ["pending", "different-kind", "different-command", "different-files", "different-criteria", "second-successor"])
def test_supersedes_requires_terminal_unreplaced_exact_assignment(change):
    candidate = valid_record()
    payload = start(supersedes="5" * 32)
    if change == "pending":
        candidate["units"] = [unit(terminal=False)]
    elif change == "different-kind":
        payload["kind"] = "review"
    elif change == "different-command":
        payload["command"] = "python -m pytest other.py"
    elif change == "different-files":
        payload["observedFiles"] = ["app.py"]
    elif change == "different-criteria":
        payload["criterionIds"] = ["C2"]
    else:
        candidate["units"].append(unit(identifier="6" * 32, supersedes="5" * 32, startedAt=LATER))
    invalid(contract.normalize_start, payload, candidate)


def test_units_and_union_file_limits_apply_across_separate_assignments():
    candidate = work()
    candidate["units"] = [unit(identifier=f"{index:032x}") for index in range(13)]
    invalid(contract.validate_work, candidate)
    candidate["units"] = []
    for index, count in enumerate((33, 32)):
        paths = [f"part{index}/file{number}.py" for number in range(count)]
        paths.sort()
        candidate["units"].append(unit(identifier=f"{index:032x}", observedFiles=paths,
                                        before=snapshot(paths), after=snapshot(paths)))
    invalid(contract.validate_work, candidate)


def test_full_record_byte_cap_is_distinct_for_new_vs_stored_data():
    candidate = work()
    long_paths = [("x" * 250) + f"{index:02}.py" for index in range(64)]
    for index in range(4):
        candidate["units"].append(unit(identifier=f"{index:032x}", observedFiles=long_paths,
                                        before=snapshot(long_paths), after=snapshot(long_paths)))
    assert len(canonical(candidate)) > contract.MAX_BYTES
    with pytest.raises(SessionError) as caught:
        contract.bounded(candidate)
    assert caught.value.code == "work_too_large"
    invalid(contract.validate_work, candidate)


def test_malformed_nested_types_never_echo_private_data_or_escape_as_python_errors():
    for path, value in [(("units",), [None]), (("criteria",), ["private"]),
                        (("context",), []), (("units", 0, "result"), "private"),
                        (("units", 0, "before"), ["private"])]:
        candidate = valid_record()
        owner = candidate
        for part in path[:-1]:
            owner = owner[part]
        owner[path[-1]] = value
        invalid(contract.validate_work, candidate)
