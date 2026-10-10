"""Private, bounded, atomic chat-session persistence (Python 3.10+)."""
from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

MAX_BYTES = 2 * 1024 * 1024
MAX_SESSIONS = 64
LOCK_TIMEOUT = 10.0


class SessionStoreError(RuntimeError):
    """A stable diagnostic code without private filesystem paths."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _fail(kind: str) -> None:
    raise SessionStoreError("session_store_" + kind)


def _reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _check_path(path: Path, *, directory: bool = False) -> None:
    """Check the original spelling before resolve can hide a link."""
    for item in (*reversed(path.parents), path):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            _fail("unavailable")
        if _reparse(info):
            _fail("path_invalid")
        if item != path or directory:
            if not stat.S_ISDIR(info.st_mode):
                _fail("path_invalid")
        elif not stat.S_ISREG(info.st_mode) or getattr(info, "st_nlink", 1) > 1:
            _fail("path_invalid")


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    value: dict = {}
    for key, child in pairs:
        if key in value:
            _fail("invalid")
        value[key] = child
    return value


def _constant(_value: str) -> None:
    _fail("invalid")


def _open_file(path: Path, flags: int, mode: int = 0o600) -> int:
    _check_path(path)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags, mode)
    try:
        info = os.fstat(fd)
        if _reparse(info) or not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
            _fail("path_invalid")
        _check_path(path)
        current = path.lstat()
        if flags & (os.O_CREAT | os.O_RDWR | os.O_WRONLY) and (
                info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
            _fail("path_invalid")
        return fd
    except BaseException:
        os.close(fd)
        raise


class Store:
    """One VAS installation's sessions, outside the product directory."""

    def __init__(self, vas_root: Path, state_home: Path | None = None):
        try:
            source = Path(os.path.abspath(vas_root))
            _check_path(source, directory=True)
            self.root = source.resolve(strict=True)
            if not self.root.is_dir():
                _fail("path_invalid")
            if state_home is None:
                if os.name == "nt":
                    local = os.environ.get("LOCALAPPDATA")
                    if not local:
                        _fail("unavailable")
                    home = Path(local)
                else:
                    home = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
                state_home = home / "VAS/chat-sessions"
            if not Path(state_home).is_absolute():
                _fail("path_invalid")
            self.home = Path(os.path.abspath(state_home))
            _check_path(self.home, directory=True)
            self.home = self.home.resolve(strict=False)
            if _inside(self.home, self.root):
                _fail("path_invalid")
            self.root_key = hashlib.sha256(os.path.normcase(str(self.root)).encode("utf-8")).hexdigest()
            self.directory = self.home / self.root_key
            self.path = self.directory / "vas-session-store.json"
            self.lock_path = self.directory / ".lock"
            self._check()
        except (OSError, ValueError, RuntimeError) as error:
            if isinstance(error, SessionStoreError):
                raise
            _fail("unavailable")

    def _check(self) -> None:
        _check_path(self.root, directory=True)
        if not self.root.is_dir():
            _fail("path_invalid")
        _check_path(self.directory, directory=True)
        if _inside(self.directory.resolve(strict=False), self.root):
            _fail("path_invalid")
        _check_path(self.path)
        _check_path(self.lock_path)

    def _empty(self) -> dict:
        return {"format": "vas-chat-store", "schemaVersion": 1,
                "rootKey": self.root_key, "sessions": {}}

    def _validate(self, value: Any) -> dict:
        if (not isinstance(value, dict)
                or set(value) != {"format", "schemaVersion", "rootKey", "sessions"}
                or value.get("format") != "vas-chat-store"
                or type(value.get("schemaVersion")) is not int
                or value["schemaVersion"] != 1 or value.get("rootKey") != self.root_key
                or not isinstance(value.get("sessions"), dict)):
            _fail("invalid")
        if len(value["sessions"]) > MAX_SESSIONS:
            _fail("too_large")
        if any(not isinstance(key, str) or not isinstance(item, dict)
               for key, item in value["sessions"].items()):
            _fail("invalid")
        return value

    def read(self) -> dict:
        """Read a complete old/new snapshot without creating any files."""
        try:
            self._check()
            try:
                fd = _open_file(self.path, os.O_RDONLY)
            except FileNotFoundError:
                return self._empty()
            with os.fdopen(fd, "rb") as handle:
                raw = handle.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                _fail("too_large")
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
            return self._validate(value)
        except (UnicodeError, ValueError, RecursionError):
            _fail("invalid")
        except OSError:
            _fail("unavailable")

    def _prepare(self) -> None:
        self._check()
        # Only newly created directories are chmodded; user-owned parents keep their permissions.
        missing = []
        cursor = self.directory
        while not cursor.exists():
            missing.append(cursor)
            cursor = cursor.parent
        for directory in reversed(missing):
            _check_path(directory, directory=True)
            try:
                directory.mkdir(mode=0o700)
                if os.name != "nt":
                    directory.chmod(0o700)
            except FileExistsError:
                _check_path(directory, directory=True)
        self._check()
        if os.name != "nt":
            self.directory.chmod(0o700)

    @contextmanager
    def _lock(self):
        try:
            self._prepare()
            fd = _open_file(self.lock_path, os.O_RDWR | os.O_CREAT)
        except OSError:
            _fail("unavailable")
        locked = False
        try:
            if os.fstat(fd).st_size > 1:
                _fail("path_invalid")
            if os.name != "nt":
                os.fchmod(fd, 0o600)
            # Byte-range locking on Windows also covers this byte when the file is initially empty.
            deadline = time.monotonic() + LOCK_TIMEOUT
            while True:
                try:
                    if os.name == "nt":
                        import msvcrt
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                    break
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        _fail("unavailable")
                    if time.monotonic() >= deadline:
                        _fail("busy")
                    time.sleep(0.05)
            self._check()
            yield
        finally:
            try:
                if locked:
                    if os.name == "nt":
                        import msvcrt
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def mutate(self, callback: Callable[[dict], Any]) -> Any:
        """Serialize read-modify-replace; callback exceptions never commit."""
        with self._lock():
            # A process killed during writing cannot execute finally. These names belong
            # exclusively to this store, and no active writer exists while its lock is held.
            try:
                for abandoned in self.directory.glob(".sessions-*.tmp"):
                    _check_path(abandoned)
                    abandoned.unlink()
            except OSError:
                _fail("write_failed")
            value = self.read()
            result = callback(value)
            self._validate(value)
            try:
                raw = (json.dumps(value, ensure_ascii=False, allow_nan=False,
                                  separators=(",", ":")) + "\n").encode("utf-8")
            except (TypeError, ValueError, RecursionError, UnicodeError):
                _fail("invalid")
            if len(raw) > MAX_BYTES:
                _fail("too_large")
            # JSON coerces numeric mapping keys to strings; reject resulting duplicates.
            json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
            temporary: Path | None = None
            try:
                self._check()
                fd, name = tempfile.mkstemp(prefix=".sessions-", suffix=".tmp", dir=self.directory)
                temporary = Path(name)
                with os.fdopen(fd, "wb") as handle:
                    if os.name != "nt":
                        os.fchmod(handle.fileno(), 0o600)
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                self._check()
                _check_path(temporary)
                os.replace(temporary, self.path)
                temporary = None
            except OSError:
                _fail("write_failed")
            finally:
                if temporary is not None:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        _fail("write_failed")
            return result
