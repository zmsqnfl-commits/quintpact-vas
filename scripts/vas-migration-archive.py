#!/usr/bin/env python3
"""Backward-compatible wrapper for the VAS 2.6.4 migration engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vas_project_import import MigrationError, MigrationManager


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VAS 2.6.4 마이그레이션 호환 명령")
    parser.add_argument("source", help="원래 프로젝트가 있는 폴더")
    parser.add_argument("--dry-run", action="store_true", help="읽기 전용 분석만 수행")
    parser.add_argument("--delete-source", action="store_true",
                        help="검증 후 원본 삭제(프로젝트명 확인 필요)")
    parser.add_argument("--confirm-name", help="원본 삭제 확인용 프로젝트명")
    parser.add_argument("--name", help="가져올 프로젝트명")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    manager = MigrationManager(args.root)
    try:
        if args.dry_run:
            result = manager.analyze(args.source)
        else:
            result = manager.import_project(args.source, args.name)
            if args.delete_source and result["status"] != "source_deleted":
                confirmation = args.confirm_name
                if confirmation is None:
                    if not sys.stdin.isatty():
                        raise MigrationError("--delete-source에는 --confirm-name이 필요합니다.")
                    confirmation = input("원본 삭제 확인을 위해 프로젝트명을 입력하세요: ").strip()
                result = manager.delete_source(result["job_id"], confirmation)
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        elif args.dry_run:
            print(f"[DRY-RUN] {result['project_name']}: {result['file_count']}개 파일")
            print(f"대상 제안: {result['suggested_target']}")
        else:
            print(f"마이그레이션 완료: {result['target']}")
            print(f"작업 ID: {result['job_id']}")
            if result.get("idempotent"):
                print("이미 완료된 동일 작업입니다.")
        return 0
    except MigrationError as error:
        if args.json:
            print(json.dumps({"error": type(error).__name__, "message": str(error)}, ensure_ascii=False))
        else:
            print(f"오류: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
