"""Close an agent turn without treating a saved report as proof of execution."""
import hashlib
from pathlib import Path

from vas_ai_contract import canonical
from vas_finish_report import build_result, check_flags, prepare_draft, result_status
from vas_portable_progress import SharedProgressError, append_shared_progress, read_shared_progress
from vas_project_layout import is_project_engine, project_directory
from vas_project_prompt import read_project_prompt
from vas_session import SessionError, SessionManager, require
from vas_session_execution import assess_with_result, prepare, validate_execution_result
from vas_session_progress import checkpoint, normalize_progress, _text as progress_text
from vas_session_store import SessionStoreError


def _check_counts(tests):
    counts = []
    for status in ("failed", "skipped", "passed"):
        count = sum(test["status"] == status for test in tests)
        if count:
            counts.append({"name": "Reported tests", "status": status, "summary": f"{count} {status}"})
    return counts


def _report_progress(progress, report, followup, *, normalized_checks=None):
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
        candidates = explicit if normalized_checks is None else normalized_checks
        for item in report["tests"]:
            matches = [check for check in candidates if check.get("name") == item["name"]
                       and check.get("command", "") == item["command"]]
            require(not matches or any(result_status(check.get("status")) == item["status"] for check in matches),
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


def _excerpt(value, limit):
    """Redact the complete string before clipping; keep public protocol limits in UTF-16."""
    try:
        cleaned = progress_text(value, len(value.encode("utf-16-le")) // 2, "shared", [])
        encoded = cleaned.encode("utf-16-le")
    except (ValueError, TypeError, UnicodeError):
        raise SharedProgressError("shared_progress_invalid") from None
    if len(encoded) <= 2 * limit:
        return cleaned
    return encoded[:(limit - 1) * 2].decode("utf-16-le", errors="ignore").rstrip() + "…"


def _scope(task):
    if not task or not task["request"].strip():
        return None
    return {"objective": _excerpt(task["request"], 1000),
            "criteria": [_excerpt(row["description"], 300) for row in task["completionCriteria"]]}


def _retain_criterion_issues(progress, evidence):
    # The shared journal has room for ten 300-unit notes. Keep the specific reason
    # when the next host has only the journal and cannot reread the agent's report.
    explicit = progress.get("remaining", [])
    notes = [_excerpt(f"{item['criterionId']} {item['outcome']}: {item['summary']}", 300)
             for item in evidence if item["outcome"] != "passed"]
    notes = [note for note in notes if note not in explicit]
    if not notes:
        return progress
    if len(notes) + len(explicit) > 10:
        packed = []
        for note in notes:
            combined = packed[-1] + "\n" + note if packed else ""
            if packed and len(combined.encode("utf-16-le")) <= 600:
                packed[-1] = combined
            else:
                packed.append(note)
        notes = packed
    require(len(notes) + len(explicit) <= 10, "finish_remaining_summary_required")
    return {**progress, "remaining": notes + explicit}


def _quick_context(progress, previous, task, keep_next):
    if not previous:
        return progress
    latest = previous.get("scope")
    if latest:
        local = _scope(task)
        if local and local != latest:
            raise SharedProgressError("shared_progress_scope_conflict")
    record = dict(progress)
    for key in ("scope", "decisions", "remaining"):
        if key in previous:
            record[key] = previous[key]
    if keep_next:
        record["nextStep"] = previous["nextStep"]
    # A short note about another change must not erase an earlier failed or skipped check.
    seen = {check["name"] for check in record["checks"]}
    pending = [check for check in previous["checks"] if check["status"] != "passed" and check["name"] not in seen]
    if len(pending) + len(record["checks"]) > 10:
        raise SharedProgressError("shared_progress_checks_limit")
    record["checks"] = pending + record["checks"]
    if previous["phase"] == "blocked" and previous.get("remaining"):
        record["phase"] = "blocked"
    elif pending:
        record["phase"] = "testing"
    return record


def _write_shared(output, root, cursor, progress, task, *, quick=False, keep_next=False):
    try:
        if quick:
            previous = read_shared_progress(root)
            if cursor is not None and cursor > (previous["revision"] if previous else 0):
                raise SharedProgressError("shared_progress_conflict")
            record = _quick_context(progress, previous, task, keep_next)
        else:
            record = dict(progress)
            scope = _scope(task)
            if scope:
                record["scope"] = scope
            record["decisions"] = [_excerpt(item["decision"], 300) for item in progress["decisions"]
                                   if item["decision"].strip()]
            record["remaining"] = [_excerpt(item, 300) for item in progress["remaining"] if item.strip()]
        output["sharedProgress"] = append_shared_progress(root, cursor, record)
        output["nextStep"] = output["sharedProgress"]["nextStep"]
    except (SharedProgressError, OSError) as error:
        output.update(status="partial" if output["privateCheckpoint"] == "confirmed" else "not-recorded",
                      sharedProgress=None, sharedError=getattr(error, "code", "shared_progress_unavailable"))
        if output["sharedError"] == "shared_progress_scope_conflict":
            output["nextAction"] = "프로젝트의 공유 범위와 이 PC의 작업 범위를 비교한 뒤 합의한 세션으로 finish 하세요."
        elif output["sharedError"] == "shared_progress_pending":
            output["nextAction"] = "이전 쓰기가 진행 중이면 기다리세요. 중단됐으면 원래 요약과 판본으로 재시도하세요. 부분 파일이 남아 재시도가 막히면 마지막 완료 기록을 보존하고 새 프로젝트 위치에서 이어가세요."
        elif output["sharedError"] == "shared_progress_lock_unsupported":
            output["nextAction"] = "기존 기록은 바이트 범위 잠금을 사용합니다. 현재 기록을 보존하고 잠금을 지원하는 연결에서 start로 최신 판본을 확인한 뒤 finish를 다시 실행하세요."
        elif output["sharedError"] == "shared_progress_lock_unavailable":
            output["nextAction"] = "파일 시스템이 지금 잠금을 제공하지 못합니다. 기록을 보존하고 잠시 뒤 다시 시도하거나 잠금을 지원하는 연결을 사용하세요."
    return output


def finish(manager, session_id, expected_revision, expected_progress_revision, raw,
           expected_project_prompt_revision=None, expected_shared_revision=None, *,
           prepared_hash=None, artifact_version=None, criteria=()):
    require(type(raw) is dict and type(raw.get("progress")) is dict, "finish_input_invalid")
    automatic = prepared_hash is not None
    require(set(raw) == ({"progress"} if automatic else {"result", "progress"}) and
            (automatic or (artifact_version is None and not criteria)), "finish_input_invalid")
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
    progress = raw["progress"]
    draft = None
    input_hash = None
    if automatic:
        progress, draft, input_hash = prepare_draft(progress, prepared_hash, artifact_version, criteria)
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
        if not automatic:
            source = view["session"]["settings"]["project"]["sourceType"]
            report = validate_execution_result(raw["result"], source) if raw["result"] is not None else None
            input_hash = _input_hash(progress, report)
        receipt = record["finish"]
        require(receipt["inputSha256"] == input_hash, "revision_conflict")
        saved = view
    else:
        work_revision = view["work"]["revision"] if "work" in view else 0
        require(type(work_revision) is int, "work_invalid")
        if automatic:
            prepared = prepare(manager, session_id, expected_revision)
            require(prepared["status"] == "prepared", "execution_needs_input")
            result = build_result(prepared["handoff"], draft, input_hash)
        else:
            result = raw["result"]
        report = None
        if result is None:
            require(progress.get("phase") in ("paused", "blocked"), "finish_result_required")
        else:
            decision, report = assess_with_result(manager, session_id, expected_revision, result)
            require(decision["assessment"]["status"] != "invalid", "execution_result_invalid")
            require(decision["followUp"]["basis"]["workRevision"] == (work_revision or None),
                    "work_revision_conflict")
            if automatic:
                progress = _retain_criterion_issues(progress, report["evidence"])
            progress = _report_progress(progress, report, decision["followUp"],
                                        normalized_checks=draft["normalized"]["checks"] if automatic else None)
        receipt = {"inputSha256": input_hash if automatic else _input_hash(raw["progress"], report),
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
    if automatic and not replayed:
        output["result"] = report
    return _write_shared(output, manager.root, expected_shared_revision, summary,
                         resumed["session"]["settings"]["task"])


def quick_finish(root, state_home, summary, checks, next_step, expected_shared_revision=None):
    require(".." not in Path(root).parts, "vas_root_invalid")
    root = Path(root).absolute()
    require(project_directory(root) == root and is_project_engine(root), "vas_root_invalid")
    output = {"status": "not-recorded", "privateCheckpoint": "not-written", "assessment": None,
              "sharedProgress": None, "complete": False, "userAcceptance": "not-recorded"}
    task = None
    try:
        manager = SessionManager(root, state_home)
        current = manager.resume(target=root, allow_empty=True)
        output["privateSession"] = {"resumed": "available", "empty": "none"}.get(current["status"], "unavailable")
        if current["status"] == "resumed" and not current.get("reviewFields"):
            task = current["session"]["settings"]["task"]
        if current["status"] == "target_unavailable":
            output["privateError"] = "target_unavailable"
    except (SessionError, SessionStoreError, OSError) as error:
        output.update(privateSession="unavailable", privateError=getattr(error, "code", "session_unavailable"))
    if summary is None:
        require(not checks and next_step is None and expected_shared_revision is None, "finish_summary_required")
        return output
    checks = checks or []
    require(isinstance(summary, str) and summary.strip() and len(checks) <= 10, "finish_input_invalid")
    reported = check_flags(checks)
    draft = {"phase": "testing" if any(c["status"] != "passed" for c in reported) else "reviewing",
             "summary": summary, "checks": reported,
             "nextStep": "다음 행동 미지정" if next_step is None else next_step}
    progress, review = normalize_progress(draft)
    output.update(status="recorded", nextStep=progress["nextStep"], reviewFields=review)
    return _write_shared(output, root, expected_shared_revision, progress, task,
                         quick=True, keep_next=next_step is None)
