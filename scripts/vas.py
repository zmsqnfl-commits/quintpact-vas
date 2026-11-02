#!/usr/bin/env python3
"""Read the current VAS project or save and read back its latest progress."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from vas_session import SessionManager, read_input, require
from vas_session_store import SessionStoreError
from vas_portable_progress import SharedProgressError
from vas_start import start


def finish_command(args):
    from vas_finish import finish, quick_finish
    full = (args.session, args.expected_revision, args.expected_progress_revision)
    if any(value is not None for value in (*full, args.expected_project_prompt_revision)):
        require(all(value is not None for value in full) and args.summary is None and not args.check
                and args.next_step is None, "finish_invalid_arguments")
        return finish(SessionManager(args.vas_root, args.state_home), *full, read_input(sys.stdin.buffer),
                      args.expected_project_prompt_revision, args.expected_shared_revision)
    return quick_finish(args.vas_root, args.state_home, args.summary, args.check, args.next_step,
                        args.expected_shared_revision)


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
    transfer = commands.add_parser("import", help="plan an explicit app source transfer")
    transfer.add_argument("--from", dest="source", required=True, help="the old app source directory")
    transfer.add_argument("--apply", action="store_true", help="copy the vetted files into empty src")
    transfer.add_argument("--expected-plan", help="require the manifest digest from the reviewed plan")
    args = parser.parse_args()
    try:
        if args.command == "import":
            from vas_import import import_app
            result = import_app(args.vas_root, args.source, args.apply, args.expected_plan)
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
        code = getattr(error, "code", "vas_start_unavailable" if args.command == "start" else "session_invalid")
        print(json.dumps({"status": "error", "code": code}))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
