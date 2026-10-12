#!/usr/bin/env python3
"""Local settings and progress summaries; the web bridge only reads and saves design."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vas_session import MAX_INPUT, SessionError, SessionManager
from vas_session_store import SessionStoreError
from vas_session_web import dispatch
from vas_session_execution import assess, prepare


def read_input():
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise SessionError("session_input_too_large")
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise SessionError("session_duplicate_key")
            value[key] = item
        return value
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(SessionError("session_invalid")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vas-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--state-home", type=Path, help="isolated local test storage, outside VAS")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("list")
    web = commands.add_parser("web", help="public response for the authenticated local design UI")
    web.add_argument("operation", choices=("list", "get", "design"))
    resume = commands.add_parser("resume")
    selector = resume.add_mutually_exclusive_group()
    selector.add_argument("--session")
    selector.add_argument("--target", type=Path)
    create = commands.add_parser("create")
    create.add_argument("--target", type=Path, required=True)
    for action in ("save", "rebind", "forget", "export", "prepare", "assess",
                   "checkpoint", "clear-progress"):
        command = commands.add_parser(action)
        command.add_argument("--session", required=True)
        if action != "export":
            command.add_argument("--expected-revision", required=True, type=int)
        if action == "rebind":
            command.add_argument("--target", required=True, type=Path)
        if action == "checkpoint":
            command.add_argument("--expected-progress-revision", required=True, type=int)
        if action == "forget":
            command.add_argument("--expected-work-revision", type=int)
    work = commands.add_parser("work", help="local work receipts and explicit read-only file samples")
    operations = work.add_subparsers(dest="work_action", required=True)
    for action in ("open", "start", "finish", "inspect", "clear"):
        operation = operations.add_parser(action)
        operation.add_argument("--session", required=True)
        operation.add_argument("--expected-revision", required=True, type=int)
        if action != "inspect":
            operation.add_argument("--expected-work-revision", required=True, type=int)
        if action == "finish":
            operation.add_argument("--unit", required=True)
    args = parser.parse_args()
    try:
        manager = SessionManager(args.vas_root, args.state_home)
        if args.action == "web":
            result = dispatch(manager, args.operation, read_input())
        elif args.action == "work":
            from vas_session_work import open_work, start_work, finish_work, inspect_work, clear_work
            base = (manager, args.session, args.expected_revision)
            if args.work_action == "inspect":
                result = inspect_work(*base)
            else:
                base += (args.expected_work_revision,)
                if args.work_action == "finish":
                    result = finish_work(*base, args.unit, read_input())
                elif args.work_action == "start":
                    result = start_work(*base, read_input())
                else:
                    result = (open_work if args.work_action == "open" else clear_work)(*base)
        elif args.action == "prepare":
            result = prepare(manager, args.session, args.expected_revision)
        elif args.action == "assess":
            result = assess(manager, args.session, args.expected_revision, read_input())
        elif args.action == "create":
            result = manager.create(read_input(), args.target)
        elif args.action == "save":
            result = manager.save(args.session, args.expected_revision, read_input())
        elif args.action == "checkpoint":
            result = manager.checkpoint(args.session, args.expected_revision,
                                        args.expected_progress_revision, read_input())
        elif args.action == "clear-progress":
            result = manager.clear_progress(args.session, args.expected_revision)
        elif args.action == "rebind":
            result = manager.rebind(args.session, args.expected_revision, args.target)
        elif args.action == "forget":
            result = manager.forget(args.session, args.expected_revision, args.expected_work_revision)
        elif args.action == "export":
            result = manager.export(args.session)
        elif args.action == "resume":
            result = manager.resume(args.session, args.target)
        else:
            result = {"sessions": manager.list()}
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (SessionError, SessionStoreError, ValueError, TypeError, OSError, RecursionError):
        error = sys.exc_info()[1]
        print(json.dumps({"status": "error", "code": getattr(error, "code", "session_invalid")}))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
