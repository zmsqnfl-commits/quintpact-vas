"""Bounded, explicit file observations; never execution or whole-project proof."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import unicodedata

from vas_ai_contract import canonical, clean, safe_relative, sensitive_key
from vas_session import SessionError, require, safe_directory

MAX_FILES = 64
MAX_FILE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
HASH = re.compile(r"[a-f0-9]{64}")
RESERVED = re.compile(r"(?:con|prn|aux|nul|conin\$|conout\$|clock\$|com[1-9¹²³]|lpt[1-9¹²³])(?:\..*)?", re.I)
PRIVATE_PARTS = {".git", ".ssh", ".aws", ".azure", ".kube", ".vas-session",
                 "credentials", "secrets", "keys", "vas-session-store.json",
                 ".npmrc", ".pypirc", ".netrc", "_netrc", ".git-credentials", "service-account.json"}
PRIVATE_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
PRIVATE_NAME = re.compile(
    r"(?:^|[-_.])(?:credentials?|passwords?|private[-_.]?keys?|secrets?|api[-_.]?keys?)"
    r"(?:$|[-_.])", re.I)


def _check(condition, kind="invalid"):
    require(condition, "work_files_" + kind)


def _private_part(part):
    value = unicodedata.normalize("NFKC", part).casefold()
    return (value in PRIVATE_PARTS or value == ".env" or value.startswith(".env.")
            or Path(value).suffix in PRIVATE_SUFFIXES
            or re.fullmatch(r"id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?", value)
            or PRIVATE_NAME.search(value) or sensitive_key(Path(value).stem))


def normalize_paths(raw, *, allow_empty=False):
    """Accept exact relative names; never redirect a path by redacting its text."""
    _check(isinstance(raw, list) and int(not allow_empty) <= len(raw) <= MAX_FILES)
    seen = set()
    for value in raw:
        _check(isinstance(value, str), "path_invalid")
        try:
            _check(safe_relative(value) == value and clean(value, 300) == value,
                   "path_invalid")
            _check(not any(unicodedata.category(char).startswith("C") for char in value),
                   "path_invalid")
            value.encode("utf-8")
            for part in value.split("/"):
                _check(not part.endswith((".", " ")) and not part.startswith(" ")
                       and not RESERVED.fullmatch(part) and not _private_part(part)
                       and not re.search(r'[<>"|?*]', part), "path_invalid")
        except (TypeError, ValueError, UnicodeError) as error:
            if isinstance(error, SessionError):
                raise
            raise SessionError("work_files_path_invalid") from None
        _check(value.casefold() not in seen, "path_invalid")
        seen.add(value.casefold())
    return sorted(raw)


def _reparse(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _identity(info):
    return info.st_dev, info.st_ino


def _signature(info):
    # Windows path stat can report creation time as ctime while fstat reports
    # change time. Compare birthtime across APIs and ctime within one open handle.
    timestamp = getattr(info, "st_birthtime_ns", None) if os.name == "nt" else info.st_ctime_ns
    return (_identity(info), info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, timestamp, getattr(info, "st_file_attributes", 0))


def _root(target, expected_identity):
    _check(isinstance(target, Path) and target.is_absolute(), "path_invalid")
    _check(isinstance(expected_identity, (list, tuple)) and len(expected_identity) == 2
           and all(type(item) is int and item >= 0 for item in expected_identity)
           and expected_identity[1] != 0, "invalid")
    try:
        checked = safe_directory(target)
        _check(checked == target and _identity(checked.stat()) == tuple(expected_identity),
               "target_changed")
    except SessionError as error:
        if error.code.startswith("work_files_"):
            raise
        raise SessionError("work_files_target_changed") from None
    return checked


def _inspect(root, relative):
    """Inspect every original component before opening, including missing paths."""
    path, parents = root, []
    parts = relative.split("/")
    for index, part in enumerate(parts):
        path = path / part
        try:
            info = path.lstat()
        except FileNotFoundError:
            return None, tuple(parents)
        _check(not _reparse(info), "path_invalid")
        if index < len(parts) - 1:
            _check(stat.S_ISDIR(info.st_mode), "path_invalid")
            parents.append(_identity(info))
        else:
            _check(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_ino != 0,
                   "path_invalid")
            return info, tuple(parents)
    raise SessionError("work_files_path_invalid")


def _read(root, relative, before, parents, used):
    _check(before.st_size <= MAX_FILE_BYTES and used + before.st_size <= MAX_TOTAL_BYTES,
           "too_large")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_BINARY", 0)
    fd = os.open(root / relative, flags)
    try:
        opened = os.fstat(fd)
        _check(not _reparse(opened) and stat.S_ISREG(opened.st_mode)
               and opened.st_nlink == 1, "path_invalid")
        _check(_signature(opened) == _signature(before), "changed")
        current, ancestry = _inspect(root, relative)
        _check(current is not None and _signature(current) == _signature(opened)
               and ancestry == parents, "changed")
        digest, length = hashlib.sha256(), 0
        while True:
            data = os.read(fd, min(65536, MAX_FILE_BYTES - length + 1,
                                   MAX_TOTAL_BYTES - used - length + 1))
            if not data:
                break
            length += len(data)
            _check(length <= MAX_FILE_BYTES and used + length <= MAX_TOTAL_BYTES, "too_large")
            digest.update(data)
        finished = os.fstat(fd)
        _check(length == before.st_size and _signature(finished) == _signature(before)
               and finished.st_ctime_ns == opened.st_ctime_ns, "changed")
        current, ancestry = _inspect(root, relative)
        _check(current is not None and _signature(current) == _signature(before)
               and ancestry == parents, "changed")
        return {"path": relative, "state": "file", "bytes": length,
                "sha256": digest.hexdigest()}
    finally:
        os.close(fd)


def capture(target, expected_identity, paths):
    """Read selected bytes only. Recheck common races; no atomic tree snapshot claim."""
    paths = normalize_paths(paths)
    try:
        root = _root(target, expected_identity)
        files, observations, used = [], [], 0
        for relative in paths:
            before, ancestry = _inspect(root, relative)
            if before is None:
                entry = {"path": relative, "state": "missing", "bytes": None, "sha256": None}
            else:
                entry = _read(root, relative, before, ancestry, used)
                used += entry["bytes"]
            files.append(entry)
            observations.append((relative, before, ancestry))
        # Earlier files must not change while later files are being sampled.
        for relative, before, ancestry in observations:
            after, after_ancestry = _inspect(root, relative)
            _check(ancestry == after_ancestry and
                   ((before is None and after is None) or
                    (before is not None and after is not None and
                     _signature(before) == _signature(after))), "changed")
        _root(target, expected_identity)
        return {"files": files, "sha256": hashlib.sha256(canonical(files)).hexdigest()}
    except OSError:
        raise SessionError("work_files_unavailable") from None


def validate_snapshot(snapshot):
    """Validate stored observations without accessing an app or trusting a summary."""
    _check(isinstance(snapshot, dict) and set(snapshot) == {"files", "sha256"})
    files = snapshot["files"]
    _check(isinstance(files, list) and 1 <= len(files) <= MAX_FILES)
    _check(isinstance(snapshot["sha256"], str) and HASH.fullmatch(snapshot["sha256"]))
    paths, used = [], 0
    for entry in files:
        _check(isinstance(entry, dict) and set(entry) == {"path", "state", "bytes", "sha256"})
        paths.append(entry["path"])
        _check(entry["state"] in ("file", "missing"))
        if entry["state"] == "missing":
            _check(entry["bytes"] is None and entry["sha256"] is None)
        else:
            _check(type(entry["bytes"]) is int and 0 <= entry["bytes"] <= MAX_FILE_BYTES)
            _check(isinstance(entry["sha256"], str) and HASH.fullmatch(entry["sha256"]))
            used += entry["bytes"]
    _check(normalize_paths(paths) == paths and used <= MAX_TOTAL_BYTES)
    _check(hashlib.sha256(canonical(files)).hexdigest() == snapshot["sha256"])
    return snapshot


def compare(before, after, allowed_changes=()):
    """Only compare the same explicit coverage; do not infer unobserved changes."""
    before, after = validate_snapshot(before), validate_snapshot(after)
    old = {entry["path"]: entry for entry in before["files"]}
    new = {entry["path"]: entry for entry in after["files"]}
    _check(old.keys() == new.keys(), "coverage_mismatch")
    _check(isinstance(allowed_changes, (list, tuple)))
    allowed = set(normalize_paths(list(allowed_changes), allow_empty=True))
    _check(allowed <= old.keys(), "coverage_mismatch")
    changed = sorted(path for path in old if old[path] != new[path])
    return {"changedFiles": changed, "outOfScopeFiles": [path for path in changed if path not in allowed]}
