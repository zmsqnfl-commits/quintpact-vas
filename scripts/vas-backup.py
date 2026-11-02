"""VAS 코어 체크포인트를 만들고 최신 10개만 보관합니다."""
from __future__ import annotations

import datetime as dt
import sys
import tempfile
import zipfile
from pathlib import Path

from build_release import is_link, starter_files

ROOT = Path(__file__).resolve().parents[1]
BACKUPS = ROOT / ".vas_backups"


def prune(limit: int = 10) -> None:
    backups = sorted(BACKUPS.glob("checkpoint_*.zip"), key=lambda item: item.stat().st_mtime)
    for old in backups[:-limit]:
        old.unlink()
        print(f"Removed old backup: {old.name}")


def create_backup() -> Path:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    if is_link(BACKUPS):
        raise ValueError("Linked VAS backup directory")
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output = BACKUPS / f"checkpoint_{stamp}.zip"
    with tempfile.NamedTemporaryFile(dir=BACKUPS, prefix="checkpoint-", suffix=".tmp", delete=False) as file:
        temporary = Path(file.name)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for relative, source in starter_files():
                archive.write(source, relative.as_posix())
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    prune()
    print(f"VAS checkpoint saved: {output}")
    return output


if __name__ == "__main__":
    try:
        create_backup()
    except Exception as error:
        print(f"Backup failed: {error}", file=sys.stderr)
        raise SystemExit(1)
