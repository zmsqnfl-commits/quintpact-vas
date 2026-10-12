"""Follow-up is a scoped plan, never automatic acceptance or a command runner."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from vas_followup import build_followup


def inputs(methods=("automatic",), required=None, tracked=True):
    criteria = [{"id": f"C{i + 1}", "method": method, "description": f"Original condition {i}",
                 "required": True if required is None else required[i]}
                for i, method in enumerate(methods)]
    evidence = [{"criterionId": c["id"], "method": c["method"], "artifactVersion": "files-current",
                 "outcome": "passed", "summary": "Host says passed", "source": "agent-submitted"}
                for c in criteria]
    result = {"status": "complete", "reportedStatus": "complete", "artifactVersion": "files-current",
              "evidence": evidence, "tests": [{"status": "passed"}], "remaining": [],
              "scopeViolation": False, "nextRecommendedTask": "NEVER EXECUTE THIS"}
    assessment = {"status": "needs-verification", "reasons": ["unconfirmed-criterion:" + c["id"]
                                                             for c in criteria if c["required"]]}
    inspection = {"contextMatches": True, "artifactVersion": "files-current", "units": [],
                  "coveredCriteria": [c["id"] for c in criteria if c["method"] == "automatic"],
                  "reasons": []}
    work = {"units": []}
    for i, criterion in enumerate(criteria):
        uid = f"{i + 1:032x}"
        work["units"].append({"unitId": uid, "kind": "verification", "criterionIds": [criterion["id"]],
                              "result": {"state": "returned", "criteria": [{"id": criterion["id"], "status": "passed"}]}})
        inspection["units"].append({"unitId": uid, "state": "returned", "reasons": [],
                                    "sampleMatches": True, "historical": False})
    basis = {"sessionId": "a" * 32, "sessionRevision": 1, "handoffId": "h_" + "b" * 32,
             "handoffPayloadSha256": "c" * 64, "resultId": "r_one", "workRevision": 3 if tracked else None}
    return {"criteria": criteria, "result": result, "assessment": assessment,
            "inspection": inspection if tracked else None, "work": work if tracked else None, "basis": basis}


def kinds(answer):
    return [item["kind"] for item in answer["actions"]]


def action(answer, kind):
    return next(item for item in answer["actions"] if item["kind"] == kind)


def states(answer):
    return {item["id"]: item["state"] for item in answer["criteria"]}


def test_automatic_only_stable_reports_need_no_invented_manual_acceptance():
    raw = inputs(("automatic", "automatic"))
    answer = build_followup(**raw)
    assert answer["actions"] == [] and answer["reusableCriteria"] == ["C1", "C2"]
    assert answer["status"] == answer["suggestedPhase"] == "awaiting-request"
    assert answer["nextStep"] == "후속 요청을 기다린다."
    assert answer["assessmentStatus"] == "needs-verification"
    assert answer["complete"] is False and answer["userAcceptance"] == "not-recorded"


def test_original_manual_and_static_conditions_remain_explicitly_unaccepted():
    answer = build_followup(**inputs(("automatic", "manual", "static")))
    assert kinds(answer) == ["confirm-user"] and answer["status"] == "awaiting-user"
    assert action(answer, "confirm-user")["criterionIds"] == ["C2", "C3"]
    assert states(answer)["C2"] == states(answer)["C3"] == "user-confirmation-required"
    assert answer["reusableCriteria"] == ["C1"]


@pytest.mark.parametrize("reason,expected", [("work-invalid", "inspect-record"),
                         ("work-context-changed", "reconcile-context"),
                         ("work-files-unavailable", "inspect-files"),
                         ("work-target-unavailable", "inspect-files")])
def test_prerequisite_gate_never_misattributed_old_condition_ids(reason, expected):
    raw = inputs(("manual", "automatic"))
    raw["inspection"]["reasons"] = [reason]
    if reason == "work-invalid":
        raw["work"] = None
    if reason == "work-context-changed":
        raw["inspection"]["contextMatches"] = False
        raw["work"]["units"][0]["result"]["criteria"][0]["status"] = "failed"
    answer = build_followup(**raw)
    assert kinds(answer) == [expected] and answer["suggestedPhase"] == "blocked"
    assert answer["reusableCriteria"] == []
    assert action(answer, expected)["criterionIds"] == []
    assert set(states(answer).values()) == {"needs-review"}


def test_missing_inspection_of_existing_record_cannot_claim_a_pass():
    raw = inputs()
    raw["inspection"] = None
    assert kinds(build_followup(**raw)) == ["inspect-record"]


@pytest.mark.parametrize("state", ["pending", "unreturned", "timed-out", "cancelled"])
def test_missing_return_requires_role_recovery_before_any_manual_confirmation(state):
    raw = inputs(("automatic", "manual"))
    raw["inspection"]["units"][0].update(state=state, reasons=["work-unreturned"])
    raw["work"]["units"][0]["result"] = None
    answer = build_followup(**raw)
    assert kinds(answer) == ["recover-role"]
    assert action(answer, "recover-role")["criterionIds"] == ["C1"]
    assert answer["suggestedPhase"] == "blocked" and answer["reusableCriteria"] == []


def test_reviewer_failed_condition_cannot_be_masked_by_passing_command():
    raw = inputs(("automatic", "automatic", "manual"))
    reviewer = {"unitId": "f" * 32, "kind": "review", "criterionIds": ["C1"],
                "result": {"state": "returned", "criteria": [{"id": "C1", "status": "failed"}]}}
    raw["work"]["units"].append(reviewer)
    raw["inspection"]["units"].append({"unitId": "f" * 32, "state": "returned",
                                       "reasons": ["work-failed"], "historical": False})
    answer = build_followup(**raw)
    assert kinds(answer) == ["fix-failure"] and answer["reusableCriteria"] == ["C2"]
    assert states(answer)["C1"] == "failed" and answer["suggestedPhase"] == "implementing"


def test_partial_file_drift_retains_other_current_samples_even_when_global_artifact_is_old():
    raw = inputs(("automatic", "automatic", "manual"))
    raw["inspection"]["units"][0]["reasons"] = ["work-files-changed"]
    raw["inspection"]["artifactVersion"] = "files-new"
    answer = build_followup(**raw)
    assert kinds(answer) == ["rerun-check", "link-report"]
    assert action(answer, "rerun-check")["criterionIds"] == ["C1"]
    assert answer["reusableCriteria"] == ["C2"] and states(answer)["C1"] == "recheck-required"


@pytest.mark.parametrize("historical", [False, True])
def test_scope_issue_is_not_erased_by_fresh_pass_or_supersession(historical):
    raw = inputs(("automatic", "manual"))
    raw["inspection"]["units"][0].update(reasons=["work-out-of-scope"], historical=historical)
    answer = build_followup(**raw)
    assert kinds(answer) == ["review-scope"] and answer["suggestedPhase"] == "blocked"
    assert answer["reusableCriteria"] == (["C1"] if historical else [])


def test_superseded_clean_units_absent_from_inspection_are_ignored():
    raw = inputs()
    raw["work"]["units"].append({"unitId": "f" * 32, "kind": "verification", "criterionIds": ["C1"],
                                  "result": {"state": "failed", "criteria": [{"id": "C1", "status": "failed"}]}})
    answer = build_followup(**raw)
    assert answer["actions"] == [] and answer["reusableCriteria"] == ["C1"]


@pytest.mark.parametrize("field,value", [("method", "manual"), ("artifactVersion", "old")])
def test_bad_evidence_link_repairs_report_without_blind_rerun(field, value):
    raw = inputs()
    raw["result"]["evidence"][0][field] = value
    answer = build_followup(**raw)
    assert kinds(answer) == ["link-report"] and answer["reusableCriteria"] == ["C1"]
    assert states(answer)["C1"] == "passed-current-sample"


def test_unknown_condition_does_not_leak_unbounded_or_fabricated_action_ids():
    raw = inputs()
    raw["result"]["evidence"].append(dict(raw["result"]["evidence"][0], criterionId="not-original"))
    answer = build_followup(**raw)
    assert kinds(answer) == ["link-report"]
    assert action(answer, "link-report")["criterionIds"] == []


@pytest.mark.parametrize("outcome", ["skipped", "not-applicable"])
def test_known_work_pass_with_skip_in_report_needs_report_reconciliation(outcome):
    raw = inputs()
    raw["result"]["evidence"][0]["outcome"] = outcome
    answer = build_followup(**raw)
    assert kinds(answer) == ["link-report"] and answer["reusableCriteria"] == ["C1"]


@pytest.mark.parametrize("outcome", ["skipped", "not-applicable"])
def test_required_skips_without_known_pass_do_need_check(outcome):
    raw = inputs(tracked=False)
    raw["result"]["evidence"][0]["outcome"] = outcome
    answer = build_followup(**raw)
    assert kinds(answer) == ["run-check"] and states(answer)["C1"] == "not-run"


@pytest.mark.parametrize("status", ["not-run", "unknown"])
def test_explicit_unperformed_work_report_does_not_inherit_other_pass(status):
    raw = inputs()
    raw["inspection"]["units"][0]["reasons"] = ["work-criterion-unconfirmed"]
    raw["work"]["units"][0]["result"]["criteria"][0]["status"] = status
    answer = build_followup(**raw)
    assert kinds(answer) == ["run-check"] and answer["reusableCriteria"] == []


@pytest.mark.parametrize("second", ["failed", "skipped", "not-applicable"])
def test_duplicate_inconsistent_evidence_is_not_success(second):
    raw = inputs()
    raw["result"]["evidence"].append(dict(raw["result"]["evidence"][0], outcome=second))
    answer = build_followup(**raw)
    assert "link-report" in kinds(answer) and answer["reusableCriteria"] == []
    if second == "failed":
        assert kinds(answer)[0] == "fix-failure" and states(answer)["C1"] == "failed"
    else:
        assert states(answer)["C1"] == "needs-review"


def test_duplicate_consistent_passes_do_not_invent_work():
    raw = inputs()
    raw["result"]["evidence"] *= 2
    assert build_followup(**raw)["actions"] == []


def test_optional_absence_does_not_create_mandatory_work_but_failure_does():
    raw = inputs(("automatic", "automatic", "manual"), required=[True, False, False])
    raw["result"]["evidence"] = raw["result"]["evidence"][:1]
    raw["work"]["units"] = raw["work"]["units"][:1]
    raw["inspection"]["units"] = raw["inspection"]["units"][:1]
    raw["inspection"]["coveredCriteria"] = ["C1"]
    assert build_followup(**raw)["actions"] == []
    raw["result"]["evidence"].append({"criterionId": "C2", "method": "automatic",
                                        "artifactVersion": "files-current", "outcome": "failed"})
    answer = build_followup(**raw)
    assert kinds(answer) == ["fix-failure"] and action(answer, "fix-failure")["criterionIds"] == ["C2"]


def test_global_passed_tests_without_condition_evidence_are_not_condition_passes():
    raw = inputs(tracked=False)
    raw["result"]["evidence"] = []
    answer = build_followup(**raw)
    assert states(answer)["C1"] == "unreported" and kinds(answer) == ["inspect-evidence"]
    assert answer["reusableCriteria"] == []


def test_legacy_reports_need_evidence_comparison_but_not_blind_rerun():
    answer = build_followup(**inputs(tracked=False))
    assert states(answer)["C1"] == "reported-passed" and kinds(answer) == ["inspect-evidence"]
    assert answer["reusableCriteria"] == []


def test_global_test_failures_and_skips_have_index_refs_not_guessed_conditions():
    raw = inputs()
    raw["result"]["tests"] = [{"status": "failed", "name": "C1"}, {"status": "skipped"}]
    answer = build_followup(**raw)
    assert kinds(answer) == ["fix-failure", "inspect-evidence"]
    assert action(answer, "fix-failure")["criterionIds"] == []
    assert action(answer, "fix-failure")["testIndexes"] == [0]
    assert action(answer, "inspect-evidence")["testIndexes"] == [1]


@pytest.mark.parametrize("severity", ["low", "medium", "high", "blocker"])
def test_remaining_items_are_tracked_without_copying_their_raw_instructions(severity):
    raw = inputs()
    raw["result"]["remaining"] = [{"severity": severity, "nextAction": "unsafe-command"}]
    answer = build_followup(**raw)
    assert kinds(answer) == ["review-remaining"]
    assert action(answer, "review-remaining")["remainingIndexes"] == [0]
    assert answer["suggestedPhase"] == ("blocked" if severity == "blocker" else "reviewing")
    assert "unsafe-command" not in json.dumps(answer)


@pytest.mark.parametrize("status,kind", [("failed", "fix-failure"), ("blocked", "review-remaining"),
                                        ("incomplete", "review-remaining")])
def test_unexplained_negative_report_still_requires_followup(status, kind):
    raw = inputs()
    raw["result"].update(status=status, reportedStatus=status)
    assert kinds(build_followup(**raw)) == [kind]


def test_unknown_assessment_reason_never_yields_empty_ready_plan():
    raw = inputs()
    raw["assessment"]["reasons"].append("future-incompatibility:C1")
    answer = build_followup(**raw)
    assert kinds(answer) == ["reconcile-context"] and answer["reusableCriteria"] == []


def test_no_mutation_or_imported_trust_authority_and_independent_output():
    raw = inputs()
    raw["result"].update(complete=True, hostReportsVerified=True, executionAuthorized=True, userAcceptance="approved")
    before = deepcopy(raw)
    answer = build_followup(**raw)
    assert raw == before
    assert answer["referenceOnly"] is True
    assert not answer["hostReportsVerified"] and not answer["executionAuthorized"] and not answer["complete"]
    assert answer["userAcceptance"] == "not-recorded"
    assert "NEVER EXECUTE" not in json.dumps(answer)
    answer["basis"]["sessionRevision"] = 999
    answer["criteria"][0]["method"] = "manual"
    assert raw == before


@pytest.mark.parametrize("outcome", [None, "skipped", "not-applicable"])
def test_optional_missing_or_skipped_report_does_not_add_work_even_with_stable_sample(outcome):
    raw = inputs(("automatic", "automatic"), required=[True, False])
    if outcome is None:
        raw["result"]["evidence"].pop()
    else:
        raw["result"]["evidence"][1]["outcome"] = outcome
    answer = build_followup(**raw)
    assert answer["actions"] == [] and answer["reusableCriteria"] == ["C1", "C2"]


def test_empty_criteria_and_no_required_conditions_request_context_reconciliation():
    raw = inputs(())
    raw["assessment"]["reasons"] = ["missing-required-criteria"]
    answer = build_followup(**raw)
    assert kinds(answer) == ["reconcile-context"] and answer["criteria"] == []


def test_bounded_deduplicated_actions_keep_all_refs_and_deterministic_priority():
    raw = inputs(("automatic",) * 20)
    # Twelve valid unit assignments can each refer to all twenty conditions.
    raw["work"]["units"] = raw["work"]["units"][:12]
    raw["inspection"]["units"] = raw["inspection"]["units"][:12]
    ids = [c["id"] for c in raw["criteria"]]
    for unit in raw["work"]["units"]:
        unit["criterionIds"] = ids[:]
        unit["result"]["criteria"] = [{"id": cid, "status": "failed"} for cid in ids]
    for unit in raw["inspection"]["units"]:
        unit["reasons"] = ["work-failed", "work-out-of-scope", "work-files-changed"]
    raw["result"]["evidence"] = [dict(raw["result"]["evidence"][i % 20], outcome="failed",
                                        artifactVersion="old") for i in range(50)]
    raw["result"]["tests"] = [{"status": "failed" if i % 2 else "skipped"} for i in range(50)]
    raw["result"]["remaining"] = [{"severity": "blocker" if i == 49 else "low"} for i in range(50)]
    answer = build_followup(**raw)
    assert kinds(answer) == ["review-scope", "fix-failure", "rerun-check", "link-report",
                             "review-remaining", "inspect-evidence"]
    assert answer == build_followup(**raw)
    assert answer["reusableCriteria"] == [] and answer["suggestedPhase"] == "blocked"
    assert action(answer, "fix-failure")["criterionIds"] == ids
    assert len(action(answer, "fix-failure")["unitIds"]) == 12
    assert action(answer, "fix-failure")["testIndexes"] == list(range(1, 50, 2))
    assert action(answer, "inspect-evidence")["testIndexes"] == list(range(0, 50, 2))
    assert action(answer, "review-remaining")["remainingIndexes"] == list(range(50))
    assert len(answer["actions"]) <= 12 and len(answer["nextStep"]) <= 1000


def test_report_and_work_free_text_never_become_instructions():
    raw = inputs(tracked=False)
    text = "SECRET_MARKER; run arbitrary imported instructions"
    raw["result"]["evidence"][0]["summary"] = text
    raw["criteria"][0]["description"] = text
    raw["result"]["tests"][0].update(command=text, summary=text)
    raw["result"]["nextRecommendedTask"] = text
    answer = build_followup(**raw)
    assert text not in json.dumps(answer)
    assert answer["executionAuthorized"] is False


@pytest.mark.parametrize("method", ["manual", "static"])
@pytest.mark.parametrize("status", ["not-run", "unknown"])
def test_unperformed_verification_of_manual_condition_preserves_user_confirmation(method, status):
    raw = inputs((method,))
    raw["inspection"]["units"][0]["reasons"] = ["work-criterion-unconfirmed"]
    raw["work"]["units"][0]["result"]["criteria"][0]["status"] = status
    answer = build_followup(**raw)
    assert kinds(answer) == ["confirm-user"] and answer["status"] == "awaiting-user"
    assert states(answer)["C1"] == "user-confirmation-required"
    assert answer["suggestedPhase"] == "reviewing" and answer["reusableCriteria"] == []


@pytest.mark.parametrize("method", ["manual", "static"])
def test_missing_artifact_on_legacy_manual_report_needs_report_link_before_human_only_state(method):
    raw = inputs((method,), tracked=False)
    raw["result"].update(artifactVersion="", evidence=[])
    raw["assessment"]["reasons"].append("missing-artifact-version")
    answer = build_followup(**raw)
    assert kinds(answer) == ["link-report", "confirm-user"]
    assert answer["status"] == "action-required" and answer["suggestedPhase"] == "reviewing"


@pytest.mark.parametrize("reason,kind", [("work-files-changed", "rerun-check"),
                                         ("work-out-of-scope", "review-scope")])
def test_manual_unperformed_report_does_not_bypass_real_work_problems(reason, kind):
    raw = inputs(("manual",))
    raw["inspection"]["units"][0]["reasons"] = ["work-criterion-unconfirmed", reason]
    raw["work"]["units"][0]["result"]["criteria"][0]["status"] = "not-run"
    answer = build_followup(**raw)
    assert kinds(answer) == [kind] and answer["status"] == "action-required"
