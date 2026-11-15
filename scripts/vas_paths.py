"""Path-boundary checks shared by the modules that walk user folders."""
from __future__ import annotations

import os
import stat
from pathlib import Path


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def is_reparse(path: Path, item_stat: os.stat_result | None = None) -> bool:
    """True for a symlink, a Windows reparse point, or anything that cannot be inspected."""
    try:
        data = item_stat or path.lstat()
    except OSError:
        return True
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(getattr(data, "st_file_attributes", 0) & marker)
