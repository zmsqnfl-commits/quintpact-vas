#!/usr/bin/env python3
"""Build or verify the registered-project RAG index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vas_project_knowledge import KnowledgeError, build_index, check_index, write_index


def _summary(status: str, index: dict) -> dict:
    return {
        "status": status,
        "path": "workspace/.vas/project-knowledge.json",
        "digest": index["digest"],
        "projectCount": index["projectCount"],
        "sourceCount": index["sourceCount"],
        "entryCount": len(index["entries"]),
        "stats": index["stats"],
        "warnings": index["warnings"],
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("command", choices=("build", "check"))
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            index = build_index(args.root)
            current = check_index(args.root, index)
            result = _summary("current" if current else "stale", index)
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print("프로젝트 지식 색인 최신" if current else "프로젝트 지식 색인이 최신이 아닙니다.")
            return 0 if current else 1
        _, index = write_index(args.root)
        result = _summary("built", index)
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"프로젝트 지식 색인 생성: {len(index['entries'])}개 청크")
        return 0
    except (KnowledgeError, OSError) as error:
        message = "프로젝트 지식 색인을 처리할 수 없습니다."
        if args.json:
            print(json.dumps({"status": "error", "message": message}, ensure_ascii=False))
        else:
            print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
