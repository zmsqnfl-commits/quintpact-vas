"""Recognize the packaged engine without granting a generic ancestor exception."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat


MARKER = "project-layout.json"


def _real(info, directory=False):
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    return (kind(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400)
            and (directory or info.st_nlink == 1))


def _unique(items):
    if len(dict(items)) != len(items):
        raise ValueError("duplicate key")
    return dict(items)


def ui_directory(root: Path) -> Path:
    return root / ("src" if root.name.casefold() == ".vas" else "ui")


def project_directory(engine: Path) -> Path:
    return engine.parent if engine.name.casefold() == ".vas" else engine


def reserves_engine(root: Path) -> bool:
    """A marker or engine fingerprint reserves this tree even when layout validation fails."""
    legacy = root.name.casefold() == ".vas"
    try:
        info = root.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            return legacy
        if not stat.S_ISDIR(info.st_mode):
            return False
        try:
            (root / MARKER).lstat()
            return True
        except FileNotFoundError:
            pass
        # Recognize an engine with a deleted marker. Never follow a linked src/.
        (root / "Run-VAS-System.bat").lstat()
        ui = ui_directory(root)
        if not _real(ui.lstat(), directory=True):
            return True
        (ui / "vas-hub.html").lstat()
        return True
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError:
        return True


def is_project_engine(root: Path) -> bool:
    """Check original components, known engine files and the bounded regular marker."""
    ui = ui_directory(root)
    try:
        if not all(_real(p.lstat(), directory=True) for p in (*root.parents, root, ui)):
            return False
        if not all(_real(p.lstat()) for p in (root / "Run-VAS-System.bat", ui / "vas-hub.html")):
            return False
        marker = root / MARKER
        original = marker.lstat()
        if not _real(original) or not 1 <= original.st_size <= 256:
            return False
        flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                 | getattr(os, "O_BINARY", 0))
        with os.fdopen(os.open(marker, flags), "rb") as handle:
            current = os.fstat(handle.fileno())
            if not _real(current) or not os.path.samestat(original, current):
                return False
            payload = handle.read(257)
            if len(payload) > 256 or not os.path.samestat(current, marker.lstat()):
                return False
        data = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique)
        return (type(data) is dict and set(data) == {"layout", "version"}
                and data["layout"] == "vas-project" and type(data["version"]) is int
                and data["version"] == (1 if root.name.casefold() == ".vas" else 2))
    except (OSError, ValueError, RecursionError):
        return False
