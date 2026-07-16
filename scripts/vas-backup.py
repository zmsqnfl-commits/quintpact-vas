"""VAS 코어 체크포인트를 만들고 최신 10개만 보관합니다."""
from __future__ import annotations

import datetime as dt
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUPS = ROOT / ".vas_backups"
EXCLUDED = {
    ".git", ".vas_backups", ".temp data", "workspace", "dist", "final",
    "node_modules", "__pycache__", ".pytest_cache", "test-results",
    "playwright-report", ".vscode", ".idea",
}


def ignore(_path: str, names: list[str]) -> set[str]:
    return {name for name in names if name in EXCLUDED}


def prune(limit: int = 10) -> None:
    backups = sorted(BACKUPS.glob("checkpoint_*.zip"), key=lambda item: item.stat().st_mtime)
    for old in backups[:-limit]:
        old.unlink()
        print(f"Removed old backup: {old.name}")


def create_backup() -> Path:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output = BACKUPS / f"checkpoint_{stamp}.zip"
    with tempfile.TemporaryDirectory(prefix="vas-checkpoint-") as temporary:
        staged = Path(temporary) / ROOT.name
        shutil.copytree(ROOT, staged, ignore=ignore)
        archive = Path(shutil.make_archive(str(output.with_suffix("")), "zip", staged))
    prune()
    print(f"VAS checkpoint saved: {archive}")
    return archive


if __name__ == "__main__":
    try:
        create_backup()
    except Exception as error:
        print(f"Backup failed: {error}", file=sys.stderr)
        raise SystemExit(1)
