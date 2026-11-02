#!/usr/bin/env python3
"""Read or save the portable prompt of this exact extracted project."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from vas_project_prompt import MAX_BYTES, ProjectPromptError, read_project_prompt, save_project_prompt


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vas-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("operation", choices=("get", "save", "progress"))
    args = parser.parse_args()
    try:
        if args.operation == "progress":
            from vas_portable_progress import read_shared_progress
            result = {"progress": read_shared_progress(args.vas_root)}
        elif args.operation == "get":
            result = read_project_prompt(args.vas_root)
        else:
            raw = sys.stdin.buffer.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ProjectPromptError("project_prompt_too_large")
            data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs)
            if type(data) is not dict or set(data) != {"expectedRevision", "prompt"}:
                raise ProjectPromptError("project_prompt_invalid")
            result = save_project_prompt(args.vas_root, data["expectedRevision"], data["prompt"])
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ProjectPromptError, ValueError, TypeError, OSError, RecursionError) as error:
        print(json.dumps({"status": "error", "code": getattr(error, "code", "project_prompt_invalid")}))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
