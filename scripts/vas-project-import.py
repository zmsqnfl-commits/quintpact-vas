#!/usr/bin/env python3
"""Command-line interface for the VAS project migration engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from vas_project_import import MigrationError, MigrationManager


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VAS 2.6.3 기존 프로그램 가져오기")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent),
                        help="VAS 루트 경로")
    parser.add_argument("--large-file-mb", type=int, default=50,
                        help="대용량 파일 경고 기준(MB)")
    commands = parser.add_subparsers(dest="command", required=True)

    analyze = commands.add_parser("analyze", help="원본을 변경하지 않고 분석")
    analyze.add_argument("source")
    analyze.add_argument("--json", action="store_true")

    importer = commands.add_parser("import", help="백업·검증 후 프로젝트 가져오기")
    importer.add_argument("source")
    importer.add_argument("--name", help="목적지 프로젝트명")
    importer.add_argument("--delete-source", action="store_true",
                          help="고급 옵션: 재검증 후 원본 삭제")
    importer.add_argument("--confirm-name", help="원본 삭제 확인용 프로젝트명")
    importer.add_argument("--json", action="store_true")

    rollback = commands.add_parser("rollback", help="가져오기 롤백")
    rollback.add_argument("job_id")
    rollback.add_argument("--json", action="store_true")
    return parser


def _emit(value: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False))
        return
    if "job_id" in value:
        print(f"작업 ID: {value['job_id']}")
        print(f"상태: {value['status']}")
        print(f"대상: {value['target']}")
        print(f"백업: {value['archive']}")
        if value.get("git_bundle"):
            print(f"Git bundle: {value['git_bundle']}")
        if value.get("idempotent"):
            print("이미 완료된 동일 작업을 확인했습니다.")
        return
    print(f"프로젝트: {value['project_name']}")
    print(f"파일: {value['file_count']}개 / {value['total_size']} bytes")
    print(f"스택: {', '.join(value['stacks']) or '알 수 없음'}")
    print(f"진입점: {', '.join(value['entrypoints']) or '감지되지 않음'}")
    print(f"Git: {'있음' if value['git']['present'] else '없음'}")
    print(f"시크릿 후보: {len(value['secret_files'])}개 (값은 표시하지 않음)")
    print(f"대용량 파일: {len(value['large_files'])}개")
    print(f"제외 항목: {len(value['skipped'])}개")
    print(f"대상 제안: {value['suggested_target']}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manager = MigrationManager(args.root, args.large_file_mb)
    as_json = bool(getattr(args, "json", False))
    try:
        if args.command == "analyze":
            result = manager.analyze(args.source)
        elif args.command == "rollback":
            result = manager.rollback(args.job_id)
        else:
            result = manager.import_project(args.source, args.name)
            if args.delete_source and result["status"] != "source_deleted":
                confirmation = args.confirm_name
                if confirmation is None:
                    if not sys.stdin.isatty():
                        raise MigrationError("--delete-source에는 --confirm-name이 필요합니다.")
                    confirmation = input("원본 삭제 확인을 위해 프로젝트명을 입력하세요: ").strip()
                result = manager.delete_source(result["job_id"], confirmation)
        _emit(result, as_json)
        return 0
    except MigrationError as error:
        if as_json:
            print(json.dumps({"error": type(error).__name__, "message": str(error)}, ensure_ascii=False))
        else:
            print(f"오류: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
