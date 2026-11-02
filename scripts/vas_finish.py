"""Close an agent turn without treating a saved report as proof of execution."""
import hashlib
from pathlib import Path

from vas_ai_contract import canonical, validate_result
from vas_project_layout import is_project_engine, project_directory
from vas_project_prompt import read_project_prompt
from vas_session import SessionError, SessionManager, require
from vas_session_execution import assess_with_result
from vas_session_progress import checkpoint, normalize_progress
from vas_session_store import SessionStoreError


def _check_counts(tests):
    counts = []
    for status in ("failed", "skipped", "passed"):
        count = sum(test["status"] == status for test in tests)
        if count:
            counts.append({"name": "Reported tests", "status": status, "summary": f"{count} {status}"})
    return counts


def _report_progress(progress, report, followup):
    draft = dict(progress)
    draft.setdefault("phase", followup["suggestedPhase"])
    draft.setdefault("nextStep", followup["nextStep"])
    if followup["actions"]:
        require(draft["phase"] != "awaiting-request", "finish_followup_pending")
    explicit = draft.get("checks")
    if explicit is not None:
        require(isinstance(explicit, list) and all(isinstance(item, dict) for item in explicit),
                "progress_invalid")
        missing = []
        for item in report["tests"]:
            matches = [check for check in explicit if check.get("name") == item["name"]
                       and check.get("command", "") == item["command"]]
            require(not matches or any(check.get("status") == item["status"] for check in matches),
                    "finish_check_conflict")
            if not matches and item["status"] != "passed":
                missing.append(item)
        if len(explicit) + len(missing) > 10:
            missing = _check_counts(missing)
        require(len(explicit) + len(missing) <= 10, "finish_checks_summary_required")
        draft["checks"] = explicit + missing
    if "checks" not in draft:
        tests = report["tests"]
        draft["checks"] = tests if len(tests) <= 10 else _check_counts(tests)
    if "remaining" not in draft:
        issues = [" ".join(filter(None, (item["summary"], item["nextAction"])))
                  for item in report["remaining"]]
        actions = [item["message"] for item in followup["actions"]]
        items = list(dict.fromkeys(issues + actions))
        if len(items) > 10:
            omitted = len(items) - 9
            items = items[:9] + [f"추가 미해결 항목 {omitted}건은 원래 보고서와 followUp에서 확인하세요."]
        draft["remaining"] = items
    return draft


def _input_hash(progress, report):
    # Match a retry only to the same normalized host input, never retain a raw result.
    draft = {"phase": "paused", "nextStep": "unspecified", **progress}
    normalized, _ = normalize_progress(draft)
    return hashlib.sha256(canonical([sorted(progress), normalized, report])).hexdigest()


def _write_shared(output, root, cursor, progress):
    from vas_portable_progress import append_shared_progress, SharedProgressError
    try:
        output["sharedProgress"] = append_shared_progress(root, cursor, progress)
    except (SharedProgressError, OSError) as error:
        output.update(status="partial" if output["privateCheckpoint"] == "confirmed" else "not-recorded",
                      sharedProgress=None, sharedError=getattr(error, "code", "shared_progress_unavailable"))
    return output


def finish(manager, session_id, expected_revision, expected_progress_revision, raw,
           expected_project_prompt_revision=None, expected_shared_revision=None):
    require(type(raw) is dict and set(raw) == {"result", "progress"} and
            type(raw["progress"]) is dict, "finish_input_invalid")
    require(type(expected_revision) is int and expected_revision >= 1, "revision_invalid")
    require(type(expected_progress_revision) is int and expected_progress_revision >= 0,
            "progress_revision_invalid")
    require(expected_shared_revision is None or type(expected_shared_revision) is int and
            expected_shared_revision >= 0, "shared_revision_invalid")
    view = manager.resume(session_id=session_id)
    require(view["status"] == "resumed", "target_unavailable")
    require(Path(view["target"]["path"]) == manager.project_root == manager.root, "finish_target_mismatch")
    prompt = read_project_prompt(manager.root)
    if expected_project_prompt_revision is not None or prompt["revision"]:
        require(type(expected_project_prompt_revision) is int and
                expected_project_prompt_revision == prompt["revision"], "project_prompt_conflict")
    decision = None
    replayed = view["session"]["revision"] != expected_revision
    if replayed:
        progress_view = view.get("progress", {})
        record = progress_view.get("record", {})
        require(view["session"]["revision"] == expected_revision + 1 and
                progress_view.get("status") == "available" and
                record.get("revision") == expected_progress_revision + 1 and
                record.get("basedOn", {}).get("sessionRevision") == expected_revision and
                "finish" in record, "revision_conflict")
        source = view["session"]["settings"]["project"]["sourceType"]
        try:
            report = validate_result(raw["result"], source) if raw["result"] is not None else None
        except ValueError:
            raise SessionError("execution_result_invalid") from None
        receipt = record["finish"]
        require(receipt["inputSha256"] == _input_hash(raw["progress"], report), "revision_conflict")
        saved = view
    else:
        work_revision = view["work"]["revision"] if "work" in view else 0
        require(type(work_revision) is int, "work_invalid")
        progress = raw["progress"]
        report = None
        if raw["result"] is None:
            require(progress.get("phase") in ("paused", "blocked"), "finish_result_required")
        else:
            decision, report = assess_with_result(manager, session_id, expected_revision, raw["result"])
            require(decision["assessment"]["status"] != "invalid", "execution_result_invalid")
            require(decision["followUp"]["basis"]["workRevision"] == (work_revision or None),
                    "work_revision_conflict")
            progress = _report_progress(progress, report, decision["followUp"])
        receipt = {"inputSha256": _input_hash(raw["progress"], report),
                   "assessmentStatus": decision["assessment"]["status"] if decision else None,
                   "reportedStatus": decision["reportedStatus"] if decision else None}
        saved = checkpoint(manager, session_id, expected_revision, expected_progress_revision, progress,
                           prompt["revision"], expected_work_revision=work_revision,
                           expected_project_prompt=prompt, finish_receipt=receipt)

    output = {"sessionId": session_id, "revision": saved["session"]["revision"],
              "progressRevision": saved["progress"]["revision"], "projectPromptRevision": prompt["revision"],
              "replayed": replayed, "complete": False, "userAcceptance": "not-recorded"}
    try:
        resumed = manager.resume(session_id=session_id)
        require(resumed["status"] == "resumed" and resumed["session"] == saved["session"]
                and resumed.get("progress") == saved["progress"]
                and resumed["progress"]["status"] == "available", "finish_readback_conflict")
    except (OSError, SessionStoreError, SessionError) as error:
        return dict(output, status="partial", privateCheckpoint="saved-unconfirmed", sharedProgress=None,
                    code=getattr(error, "code", "finish_readback_unavailable"))
    summary = resumed["progress"]["record"]["summary"]
    output.update(status="checkpointed", privateCheckpoint="confirmed", progress=summary,
                  nextStep=summary["nextStep"], assessment=decision["assessment"] if decision else None,
                  assessmentStatus=receipt["assessmentStatus"], reportedStatus=receipt["reportedStatus"],
                  followUp=decision["followUp"] if decision else None, reviewFields=saved.get("progressReviewFields", []))
    return _write_shared(output, manager.root, expected_shared_revision, summary)


def quick_finish(root, state_home, summary, checks, next_step, expected_shared_revision=None):
    require(".." not in Path(root).parts, "vas_root_invalid")
    root = Path(root).absolute()
    require(project_directory(root) == root and is_project_engine(root), "vas_root_invalid")
    output = {"status": "not-recorded", "privateCheckpoint": "not-written", "assessment": None,
              "sharedProgress": None, "complete": False, "userAcceptance": "not-recorded"}
    try:
        manager = SessionManager(root, state_home)
        current = manager.resume(target=root, allow_empty=True)
        output["privateSession"] = {"resumed": "available", "empty": "none"}.get(current["status"], "unavailable")
        if current["status"] == "target_unavailable":
            output["privateError"] = "target_unavailable"
    except (SessionError, SessionStoreError, OSError) as error:
        output.update(privateSession="unavailable", privateError=getattr(error, "code", "session_unavailable"))
    if summary is None:
        require(not checks and next_step is None and expected_shared_revision is None, "finish_summary_required")
        return output
    checks = checks or []
    require(isinstance(summary, str) and summary.strip() and len(checks) <= 10, "finish_input_invalid")
    statuses = {"통과": "passed", "실패": "failed", "미실행": "not-run", "건너뜀": "skipped",
                "passed": "passed", "failed": "failed", "not-run": "not-run", "skipped": "skipped"}
    reported = []
    for value in checks:
        name, separator, outcome = value.rpartition(":")
        status = statuses.get(outcome.strip().lower())
        require(separator and name.strip() and status, "finish_check_invalid")
        reported.append({"name": name.strip(), "status": status, "summary": "호스트 직접 보고"})
    draft = {"phase": "testing" if any(c["status"] != "passed" for c in reported) else "reviewing",
             "summary": summary, "checks": reported,
             "nextStep": "다음 행동 미지정" if next_step is None else next_step}
    progress, review = normalize_progress(draft)
    output.update(status="recorded", nextStep=progress["nextStep"], reviewFields=review)
    return _write_shared(output, root, expected_shared_revision, progress)
