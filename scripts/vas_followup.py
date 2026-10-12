"""Read-only next-action projection; neither completion nor execution authority."""
from copy import deepcopy


MESSAGES = {
    "inspect-record": "작업 기록의 유효성을 확인하고 복구한 뒤 다시 평가한다.",
    "reconcile-context": "현재 요청·조건·인계와 기록의 차이를 대조한 뒤 다시 평가한다.",
    "inspect-files": "대상 폴더와 선택한 파일을 읽을 수 있는지 확인한 뒤 다시 평가한다.",
    "recover-role": "해당 역할의 실제 종료·반환 상태를 확인하고 정리한 뒤 재시도 여부를 결정한다.",
    "review-scope": "작업 범위 밖의 변경을 원본과 대조하고 처리 방향을 확인한다.",
    "fix-failure": "보고된 실패 원인을 확인해 수정하고 영향받은 항목을 다시 검사한다.",
    "rerun-check": "입력이 달라진 해당 검사·검토만 현재 파일에서 다시 수행한다.",
    "link-report": "실제 검사 자료와 현재 조건·산출물을 대조해 결과 보고의 연결을 바로잡는다.",
    "run-check": "미실행 또는 실행 여부가 불명확한 해당 조건의 검사를 수행한다.",
    "confirm-user": "원래 완료조건에 지정된 수동·정적 확인을 사용자와 진행하고 결과를 구분해 기록한다.",
    "review-remaining": "보고된 미완료 사항과 차단 원인을 확인하고 다음 작업 범위를 정한다.",
    "inspect-evidence": "해당 항목의 실제 실행 자료와 현재 파일을 대조하고 부족한 검사를 확인한다.",
}
PREREQUISITES = {"inspect-record", "reconcile-context", "inspect-files"}
BLOCKING = PREREQUISITES | {"recover-role", "review-scope"}
REASONS = {
    "unconfirmed-criterion", "missing-artifact-version", "missing-required-criteria",
    "artifact-evidence-mismatch", "unknown-criterion", "evidence-method-mismatch",
    "reported-failure", "unresolved-blocker", "failed-test", "scope-violation",
    "failed-criterion", "work-invalid", "work-context-changed", "work-files-unavailable",
    "work-target-unavailable", "work-unreturned", "work-failed", "work-timed-out",
    "work-cancelled", "work-inputs-changed", "work-files-changed", "work-out-of-scope",
    "work-criterion-unconfirmed", "work-check-missing", "work-artifact-mismatch",
}


class _Actions:
    def __init__(self, criteria, work):
        self.criteria = [item["id"] for item in criteria]
        self.units = [unit["unitId"] for unit in (work or {}).get("units", [])]
        self.items = {}

    def add(self, kind, ids=(), units=(), tests=(), remaining=()):
        item = self.items.setdefault(kind, {"criterionIds": set(), "unitIds": set(),
                                           "testIndexes": set(), "remainingIndexes": set()})
        item["criterionIds"].update(set(ids) & set(self.criteria))
        item["unitIds"].update(set(units) & set(self.units))
        item["testIndexes"].update(tests)
        item["remainingIndexes"].update(remaining)

    def output(self):
        return [{"kind": kind, "criterionIds": [c for c in self.criteria if c in item["criterionIds"]],
                 "unitIds": [u for u in self.units if u in item["unitIds"]],
                 "testIndexes": sorted(item["testIndexes"]),
                 "remainingIndexes": sorted(item["remainingIndexes"]), "message": MESSAGES[kind]}
                for kind in MESSAGES if (item := self.items.get(kind)) is not None]


def _finish(criteria, states, actions, reusable, assessment, basis, blocker=False):
    steps = actions.output()
    kinds = set(actions.items)
    phase = ("blocked" if blocker or kinds & BLOCKING else
             "implementing" if "fix-failure" in kinds else
             "testing" if kinds & {"run-check", "rerun-check"} else
             "reviewing" if steps else "awaiting-request")
    return {"format": "vas-session-followup", "schemaVersion": 1, "basis": deepcopy(basis),
            "status": "awaiting-user" if kinds == {"confirm-user"} else
                      "action-required" if steps else "awaiting-request",
            "assessmentStatus": assessment["status"], "referenceOnly": True,
            "executionAuthorized": False, "hostReportsVerified": False, "complete": False,
            "userAcceptance": "not-recorded",
            "criteria": [{"id": item["id"], "method": item["method"], "required": item["required"],
                          "state": states[item["id"]]} for item in criteria],
            "reusableCriteria": [item["id"] for item in criteria if item["id"] in reusable],
            "actions": steps, "suggestedPhase": phase,
            "nextStep": steps[0]["message"] if steps else "후속 요청을 기다린다."}


def _prerequisites(inspection, work, assessment, actions):
    if inspection is not None:
        reasons = {reason.split(":", 1)[0] for reason in inspection.get("reasons", [])}
        if "work-invalid" in reasons or work is None:
            actions.add("inspect-record")
        elif not inspection.get("contextMatches"):
            actions.add("reconcile-context")
        if reasons & {"work-files-unavailable", "work-target-unavailable"}:
            unavailable = [unit["unitId"] for unit in inspection.get("units", [])
                           if set(unit["reasons"]) & {"work-files-unavailable", "work-target-unavailable"}]
            actions.add("inspect-files", units=unavailable)
    elif work is not None:
        actions.add("inspect-record")
    reasons = {reason.split(":", 1)[0] for reason in assessment.get("reasons", [])}
    if reasons - REASONS or "missing-required-criteria" in reasons or assessment["status"] == "invalid":
        actions.add("reconcile-context")
    return bool(set(actions.items) & PREREQUISITES)


def _work_actions(criteria, inspection, work, actions):
    """Return affected sets without treating a report as authenticated evidence."""
    failed, drift, not_run, affected = set(), set(), set(), set()
    automatic = {item["id"] for item in criteria if item["method"] == "automatic"}
    required = {item["id"] for item in criteria if item["required"]} & automatic
    known = {item["id"] for item in criteria}
    units = {unit["unitId"]: unit for unit in (work or {}).get("units", [])}
    for view in (inspection or {}).get("units", []):
        unit = units.get(view["unitId"])
        if unit is None:
            actions.add("inspect-record")
            continue
        uid, reasons = unit["unitId"], set(view["reasons"])
        ids = set(unit["criterionIds"]) & known
        if "work-out-of-scope" in reasons:
            actions.add("review-scope", ids, [uid])
        if view.get("historical"):
            continue
        if reasons:
            # An automatic verification report cannot convert an original
            # manual/static condition into an executable check obligation.
            affected.update(ids & automatic if reasons == {"work-criterion-unconfirmed"} else ids)
        if view["state"] in {"pending", "unreturned", "timed-out", "cancelled"}:
            actions.add("recover-role", ids, [uid])
        report = unit.get("result") or {}
        failures = {item["id"] for item in report.get("criteria", []) if item["status"] == "failed"} & known
        if view["state"] == "failed" or ("work-failed" in reasons and not failures):
            failures.update(ids)
        if failures or "work-failed" in reasons:
            failed.update(failures)
            actions.add("fix-failure", failures, [uid])
        if reasons & {"work-inputs-changed", "work-files-changed"} and unit["kind"] in {"review", "verification"}:
            drift.update(ids)
            actions.add("rerun-check", ids, [uid])
        if unit["kind"] == "verification" and view["state"] == "returned":
            missing = {item["id"] for item in report.get("criteria", [])
                       if item["status"] in {"not-run", "unknown"}} & required
            if missing - failures - drift:
                not_run.update(missing - failures - drift)
                actions.add("run-check", missing - failures - drift, [uid])
    return failed, drift, not_run, affected


def _result_actions(result, actions):
    for index, test in enumerate(result.get("tests", [])):
        if test["status"] == "failed":
            actions.add("fix-failure", tests=[index])
        elif test["status"] == "skipped":
            actions.add("inspect-evidence", tests=[index])
    if result.get("scopeViolation") is True:
        actions.add("review-scope")
    remaining = result.get("remaining", [])
    if remaining:
        actions.add("review-remaining", remaining=range(len(remaining)))
    reported = result.get("reportedStatus", result["status"])
    if reported == "failed" or result["status"] == "failed":
        actions.add("fix-failure")
    # An incomplete report needs an explanation even if its tests all passed.
    elif reported in {"incomplete", "blocked"} and not remaining:
        concrete = {"fix-failure", "recover-role", "review-scope", "rerun-check", "run-check"}
        if not set(actions.items) & concrete:
            actions.add("review-remaining")
    return (reported == "blocked" or result["status"] == "blocked" or
            any(item["severity"] == "blocker" for item in remaining))


def build_followup(criteria, result, assessment, inspection=None, work=None, *, basis):
    """Project validated inputs into bounded references; perform no I/O or writes."""
    actions = _Actions(criteria, work)
    states = {item["id"]: "needs-review" for item in criteria}
    if _prerequisites(inspection, work, assessment, actions):
        return _finish(criteria, states, actions, set(), assessment, basis)
    failed, drift, not_run, affected = _work_actions(criteria, inspection, work, actions)
    if "inspect-record" in actions.items:
        return _finish(criteria, states, actions, set(), assessment, basis)
    reusable = set((inspection or {}).get("coveredCriteria", [])) - affected
    automatic = {item["id"] for item in criteria if item["method"] == "automatic"}
    reusable &= automatic
    blocker = _result_actions(result, actions)
    current_artifact = (inspection or {}).get("artifactVersion")
    artifact_mismatch = inspection is not None and (not current_artifact or result.get("artifactVersion") != current_artifact)
    if artifact_mismatch or not result.get("artifactVersion"):
        actions.add("link-report")
    known = set(states)
    evidence = result.get("evidence", [])
    if any(item["criterionId"] not in known for item in evidence):
        actions.add("link-report")
    manual = []
    for criterion in criteria:
        cid, method, required = criterion["id"], criterion["method"], criterion["required"]
        submitted = [item for item in evidence if item["criterionId"] == cid]
        outcomes = {item["outcome"] for item in submitted}
        mismatched = any(item["method"] != method or item["artifactVersion"] != result.get("artifactVersion")
                         for item in submitted)
        # A stale or contradictory failure is still a finding to resolve, not a pass.
        if "failed" in outcomes:
            failed.add(cid)
            reusable.discard(cid)
            actions.add("fix-failure", [cid])
        if len(outcomes) > 1:
            reusable.discard(cid)
        if mismatched or len(outcomes) > 1:
            actions.add("link-report", [cid])
        if cid in failed:
            states[cid] = "failed"
        elif cid in drift:
            states[cid] = "recheck-required"
        elif cid in not_run:
            states[cid] = "not-run"
        elif cid in affected:
            states[cid] = "needs-review"
        elif method in {"manual", "static"}:
            states[cid] = "user-confirmation-required" if required else "unreported"
            if required:
                manual.append(cid)
        elif cid in reusable:
            states[cid] = "passed-current-sample"
            if required and (not submitted or outcomes != {"passed"}):
                actions.add("link-report", [cid])
        elif submitted and (mismatched or len(outcomes) > 1):
            states[cid] = "needs-review"
        elif outcomes == {"passed"}:
            states[cid] = "reported-passed"
            actions.add("inspect-evidence", [cid])
        elif outcomes & {"skipped", "not-applicable"}:
            states[cid] = "not-run"
            if required:
                actions.add("run-check", [cid])
        else:
            states[cid] = "unreported"
            if required:
                actions.add("inspect-evidence", [cid])
    # Do not ask for acceptance while repairs or new checks may still change the app.
    defer_manual = BLOCKING | {"fix-failure", "run-check", "rerun-check"}
    if manual and not set(actions.items) & defer_manual and not blocker:
        actions.add("confirm-user", manual)
    return _finish(criteria, states, actions, reusable, assessment, basis, blocker)
