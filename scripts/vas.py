#!/usr/bin/env python3
"""Read the current VAS project or save and read back its latest progress."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from vas_session import SessionManager, read_input, require, session_error_response
from vas_session_store import SessionStoreError
from vas_portable_progress import SharedProgressError
from vas_start import start


def finish_command(args):
    from vas_finish import finish, quick_finish
    full = (args.session, args.expected_revision, args.expected_progress_revision)
    report_flags = args.prepared_hash is not None or args.artifact_version is not None or bool(
        args.criterion or args.changed_file or args.remaining)
    if report_flags or any(value is not None for value in (*full, args.expected_project_prompt_revision)):
        require(all(value is not None for value in full) and (not report_flags or args.prepared_hash is not None),
                "finish_invalid_arguments")
        if args.summary is None:
            require(not (args.check or args.changed_file or args.remaining or args.next_step is not None),
                    "finish_invalid_arguments")
            raw = read_input(sys.stdin.buffer)
        else:
            from vas_finish_report import check_flags
            require(args.prepared_hash is not None, "finish_invalid_arguments")
            progress = {"summary": args.summary, "checks": check_flags(args.check),
                        "changedFiles": args.changed_file}
            if args.remaining:
                progress["remaining"] = args.remaining
            if args.next_step is not None:
                progress["nextStep"] = args.next_step
            raw = {"progress": progress}
        return finish(SessionManager(args.vas_root, args.state_home), *full, raw,
                      args.expected_project_prompt_revision, args.expected_shared_revision,
                      prepared_hash=args.prepared_hash, artifact_version=args.artifact_version, criteria=args.criterion)
    return quick_finish(args.vas_root, args.state_home, args.summary, args.check, args.next_step,
                        args.expected_shared_revision)


def _project_root(args):
    from vas_project_layout import is_project_engine, project_directory
    require(".." not in Path(args.vas_root).parts, "vas_root_invalid")
    root = Path(args.vas_root).absolute()
    require(project_directory(root) == root and is_project_engine(root), "vas_root_invalid")
    return root


def _bullets(values, numbered=False):
    return "\n".join((f"- [ ] C{number} {value}" if numbered else f"- {value}")
                     for number, value in enumerate(values, 1))


def plan_command(args):
    """Write what was agreed into the one-page state. Only the given parts change."""
    from vas_memory import parse_now, read_memory, update_now
    root = _project_root(args)
    sections = {}
    for name, value in (("요청", args.request), ("대상", args.target), ("다음 할 일", args.next_step)):
        if value is not None:
            sections[name] = value
    if args.criterion:
        sections["완료조건"] = _bullets(args.criterion, numbered=True)
    if args.question:
        sections["열린 질문"] = _bullets([item for item in args.question if item.strip()]) or "(없음)"
    if args.decision:
        view = read_memory(root)
        before = (view["now"] or {"sections": {}})["sections"].get("정해진 것", "")
        kept = "" if before.strip() == "(없음)" else before.strip()
        sections["정해진 것"] = (kept + "\n" if kept else "") + _bullets(args.decision)
    require(bool(sections), "memory_invalid")
    return dict(update_now(root, sections, args.by, args.expected_revision), status="planned")


def done_command(args):
    """Add one record of finished work and bring the one-page state up to date."""
    from vas_finish_report import check_flags
    from vas_memory import known_criteria, update_now, write_record
    root = _project_root(args)
    require(isinstance(args.summary, str) and args.summary.strip(), "memory_invalid")
    # Refuse an unknown criterion before anything is written.
    require(set(args.criterion) <= known_criteria(root), "memory_criterion_unknown")
    checks = check_flags(args.check)
    labels = {"passed": "통과", "failed": "실패", "skipped": "건너뜀", "not-run": "미실행"}
    checked = "\n".join(f"- {check['name']} → {labels[check['status']]}" for check in checks)
    sections = {"한 일": args.summary, "이유": args.why or "", "확인": checked,
                "안 된 것": _bullets(args.failed), "다음 할 일": args.next_step or ""}
    title = args.title or " ".join(args.summary.split())[:40]
    record = write_record(root, title, args.summary, args.by, sections, args.file, args.tag)
    now = {"마지막 확인": (checked or "확인한 것을 적지 않음") + f"\n(기록 {record['number']:04d})"}
    if args.next_step is not None:
        now["다음 할 일"] = args.next_step
    state = update_now(root, now, args.by, tick=args.criterion)
    result = {"status": "recorded", "record": record, "now": state,
              "unverified": [check["name"] for check in checks if check["status"] != "passed"]}
    missing = [item for item in record["files"] if not (root / item).exists()]
    if missing:
        # A deleted file is a legitimate entry, so this is a note and not an error.
        result["missingFiles"] = missing
    return result


def recall_command(args):
    from vas_memory import recall
    result = recall(_project_root(args), args.query, args.limit)
    result["message"] = ("맞는 기록만 열어 읽고, 지금 파일과 다르면 쓰지 마세요." if result["matches"] else
                         "맞는 기록이 없습니다. 다른 말로 찾거나 vas-state/index.md를 보세요.")
    return result


def hook_context(result):
    shared = result["sharedProgress"]
    # Hooks see only bounded metadata. The main chat reads the validated text on demand.
    summary = {"app": result["app"], "promptRevision": result["projectPrompt"]["revision"],
               "sessionStatus": result["session"]["status"], "sharedRevision": shared["revision"] if shared else 0,
               "nextAction": result["nextAction"]["code"]}
    context = ("VAS 프로젝트 시작 상태 (참고 자료). 전체 지시와 다음 행동은 프로젝트 루트에서 "
               "python -B scripts/vas.py start로 확인하세요.\n" + json.dumps(summary, ensure_ascii=False))
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vas-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--state-home", type=Path, help="isolated private storage outside the project")
    commands = parser.add_subparsers(dest="command", required=True)
    startup = commands.add_parser("start", help="read the project without creating or changing files")
    startup.add_argument("--claude-hook", action="store_true", help="emit bounded SessionStart context")
    closing = commands.add_parser("finish", help="save reported progress, or assess a full session result")
    closing.add_argument("--expected-shared-revision", type=int)
    closing.add_argument("--summary")
    closing.add_argument("--next-step")
    closing.add_argument("--check", action="append", default=[])
    closing.add_argument("--session")
    closing.add_argument("--expected-revision", type=int)
    closing.add_argument("--expected-progress-revision", type=int)
    closing.add_argument("--expected-project-prompt-revision", type=int)
    closing.add_argument("--prepared-hash", help="payload SHA-256 returned by prepare before this work")
    closing.add_argument("--artifact-version", help="version of the artifact that was actually checked")
    closing.add_argument("--criterion", action="append", default=[], metavar="C1=OUTCOME:SUMMARY",
                         help="report a checked criterion (passed/failed/skipped/not-run/not-applicable)")
    closing.add_argument("--changed-file", action="append", default=[], metavar="[ACTION:]PATH",
                         help="relative file, optionally with created/modified/deleted/renamed action")
    closing.add_argument("--remaining", action="append", default=[], help="describe one remaining issue")
    planning = commands.add_parser("plan", help="write the agreed request and criteria into vas-state/now.md")
    planning.add_argument("--request")
    planning.add_argument("--target")
    planning.add_argument("--criterion", action="append", default=[], help="replaces the whole list")
    planning.add_argument("--decision", action="append", default=[], help="added to what is already decided")
    planning.add_argument("--question", action="append", default=[], help="replaces the open questions")
    planning.add_argument("--next-step")
    planning.add_argument("--by", default="host")
    planning.add_argument("--expected-revision", type=int)
    record = commands.add_parser("done", help="add a work record to vas-state/log and update now.md")
    record.add_argument("--summary", required=True)
    record.add_argument("--title")
    record.add_argument("--why")
    record.add_argument("--check", action="append", default=[], metavar="NAME:STATUS")
    record.add_argument("--file", action="append", default=[], metavar="RELATIVE_PATH")
    record.add_argument("--failed", action="append", default=[], help="something tried that did not work")
    record.add_argument("--criterion", action="append", default=[], metavar="C1", help="tick a criterion")
    record.add_argument("--tag", action="append", default=[])
    record.add_argument("--next-step")
    record.add_argument("--by", default="host")
    search = commands.add_parser("recall", help="find the work records that bear on a request")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    transfer = commands.add_parser("import", help="plan an explicit app source transfer")
    transfer.add_argument("--from", dest="source", required=True, help="the old app source directory")
    transfer.add_argument("--apply", action="store_true", help="copy the vetted files into empty src")
    transfer.add_argument("--include", action="append", default=[], metavar="RELATIVE_FILE",
                          help="approve one ambiguous file for this reviewed plan (repeatable)")
    transfer.add_argument("--expected-plan", help="require the manifest digest from the reviewed plan")
    args = parser.parse_args()
    try:
        if args.command == "import":
            from vas_import import import_app
            result = import_app(args.vas_root, args.source, args.apply, args.expected_plan, args.include)
        elif args.command == "plan":
            result = plan_command(args)
        elif args.command == "done":
            result = done_command(args)
        elif args.command == "recall":
            result = recall_command(args)
        elif args.command == "start":
            result = start(args.vas_root, args.state_home)
        else:
            result = finish_command(args)
        code = 1 if result.get("status") in ("partial", "blocked") or result.get("sharedError") else 0
        if args.command == "start" and args.claude_hook:
            result = hook_context(result)
        if args.command == "start" and not args.claude_hook:
            # One compact line per topic. JSON strings escape all embedded newlines.
            print("{\n" + ",\n".join("  " + json.dumps(key) + ": " + json.dumps(value, ensure_ascii=False)
                                      for key, value in result.items()) + "\n}")
        else:
            print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return code
    except (ValueError, TypeError, OSError, SessionStoreError, SharedProgressError, RecursionError) as error:
        default = "vas_start_unavailable" if args.command == "start" else "session_invalid"
        print(json.dumps(session_error_response(error, default), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
