"""One portable project instruction, independent of private chat-session storage."""
from __future__ import annotations

from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import re
import stat
import time

from vas_ai_contract import clean, credential_view, redact_credentials
from vas_project_layout import is_project_engine, project_directory, ui_directory

FILE_NAME = "VAS-PROJECT-PROMPT.json"
TEMP_NAME = ".VAS-PROJECT-PROMPT.tmp"
MAX_PROMPT = 4000
MAX_BYTES = 64 * 1024
MAX_REVISION = 2**31 - 1
LOCK_TIMEOUT = 2.0
LOCK_OFFSET = 1 << 30  # Beyond buffered marker reads; locking does not extend the file.
LOCAL_POSIX = re.compile(r"""(?<![\w:/])/(?:opt|tmp|srv|private|media|run|root|proc|sys|dev|usr|data)/[^\s'"`]+""")


class ProjectPromptError(ValueError):
    """Stable codes only; no private paths or source text in public errors."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _fail(kind):
    raise ProjectPromptError("project_prompt_" + kind)


def _require(value, kind):
    if not value:
        _fail(kind)


def _regular(info):
    return (stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
            not getattr(info, "st_file_attributes", 0) & 0x400)


def _same(first, second):
    return (os.path.samestat(first, second) and first.st_size == second.st_size
            and first.st_mtime_ns == second.st_mtime_ns)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _text(value):
    _require(isinstance(value, str), "invalid")
    _require(len(value) <= MAX_PROMPT, "too_large")
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ").strip()
    _require(not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value), "invalid")
    try:
        value.encode("utf-8")
    except UnicodeError:
        _fail("invalid")
    _require(redact_credentials(value) == value and not LOCAL_POSIX.search(credential_view(value)),
             "sensitive")
    _require(clean(value, MAX_PROMPT) == value, "sensitive")
    return value


def _decode(raw):
    _require(len(raw) <= MAX_BYTES, "too_large")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        _require(type(data) is dict and set(data) == {"format", "schemaVersion", "revision", "prompt"},
                 "corrupt")
        _require(data["format"] == "vas-project-prompt" and type(data["schemaVersion"]) is int
                 and data["schemaVersion"] == 1 and type(data["revision"]) is int
                 and 1 <= data["revision"] <= MAX_REVISION, "corrupt")
        _require(_text(data["prompt"]) == data["prompt"], "corrupt")
        return {"revision": data["revision"], "prompt": data["prompt"]}
    except (ValueError, TypeError, UnicodeError, RecursionError):
        _fail("corrupt")


class _Project:
    def __init__(self, engine):
        raw = Path(engine)
        _require(".." not in raw.parts, "layout")
        self.engine = Path(os.path.abspath(raw))
        _require(is_project_engine(self.engine), "layout")
        self.root = project_directory(self.engine)
        self.root_info, self.engine_info = self.root.stat(), self.engine.stat()
        self.dir_fd = None

    def guard(self):
        _require(is_project_engine(self.engine), "unsafe")
        _require(os.path.samestat(self.root_info, self.root.lstat()) and
                 os.path.samestat(self.engine_info, self.engine.lstat()), "unsafe")

    def info(self, name):
        try:
            data = (os.stat(name, dir_fd=self.dir_fd, follow_symlinks=False)
                    if self.dir_fd is not None else (self.root / name).lstat())
        except FileNotFoundError:
            return None
        _require(_regular(data), "unsafe")
        return data

    def open(self, name, flags):
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
        before = self.info(name)
        args = {"dir_fd": self.dir_fd} if self.dir_fd is not None else {}
        # This explicit portable instruction inherits the project's Windows ACL.
        # A private-chat 0600 policy can exclude the host's restricted workspace SID.
        mode = 0o666 if os.name == "nt" else 0o600
        fd = os.open(name if self.dir_fd is not None else self.root / name, flags, mode, **args)
        try:
            opened = os.fstat(fd)
            _require(_regular(opened) and (before is None or os.path.samestat(before, opened)), "unsafe")
            current = self.info(name)
            _require(current is not None and os.path.samestat(opened, current), "unsafe")
            return fd
        except BaseException:
            os.close(fd)
            raise

    def unlink(self, name):
        self.guard()
        self.info(name)
        if self.dir_fd is not None:
            os.unlink(name, dir_fd=self.dir_fd)
        else:
            (self.root / name).unlink()

    def replace(self):
        self.guard()
        self.info(TEMP_NAME)
        self.info(FILE_NAME)
        if self.dir_fd is not None:
            os.replace(TEMP_NAME, FILE_NAME, src_dir_fd=self.dir_fd, dst_dir_fd=self.dir_fd)
        else:
            os.replace(self.root / TEMP_NAME, self.root / FILE_NAME)

    def read(self):
        self.guard()
        before = self.info(FILE_NAME)
        if before is None:
            return {"revision": 0, "prompt": ""}, None
        _require(before.st_size <= MAX_BYTES, "too_large")
        with os.fdopen(self.open(FILE_NAME, os.O_RDONLY), "rb") as handle:
            opened = os.fstat(handle.fileno())
            raw = handle.read(MAX_BYTES + 1)
            _require(_same(opened, os.fstat(handle.fileno())), "unsafe")
        after = self.info(FILE_NAME)
        _require(after is not None and _same(before, after) and _same(opened, after), "unsafe")
        self.guard()
        return _decode(raw), raw


@contextmanager
def _pin(project):
    """Pin ancestors on Windows; use directory-relative operations on POSIX."""
    handles = []
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            api = ctypes.WinDLL("kernel32", use_last_error=True)
            api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            api.CreateFileW.restype = wintypes.HANDLE
            api.CloseHandle.argtypes = [wintypes.HANDLE]
            # No FILE_SHARE_DELETE: a pinned ancestor cannot be renamed or replaced.
            for path in (*reversed(project.engine.parents), project.engine, ui_directory(project.engine)):
                handle = api.CreateFileW(str(path), 0, 3, None, 3, 0x02200000, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise ctypes.WinError(ctypes.get_last_error())
                handles.append(handle)
                data = path.lstat()
                _require(stat.S_ISDIR(data.st_mode) and not getattr(data, "st_file_attributes", 0) & 0x400,
                         "unsafe")
        else:
            project.dir_fd = os.open(project.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            _require(os.path.samestat(os.fstat(project.dir_fd), project.root_info), "unsafe")
        project.guard()
        yield
    finally:
        if project.dir_fd is not None:
            os.close(project.dir_fd)
            project.dir_fd = None
        for handle in reversed(handles):
            api.CloseHandle(handle)


@contextmanager
def _locked(project):
    # Lock the existing marker on Windows, the pinned directory on POSIX.
    # The OS releases the lock on a killed process; no stale lock file remains.
    marker = project.engine / "project-layout.json"
    original = marker.lstat()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(marker, flags) if os.name == "nt" else os.dup(project.dir_fd)
    locked = False
    try:
        if os.name == "nt":
            _require(_regular(os.fstat(fd)) and os.path.samestat(original, os.fstat(fd)), "unsafe")
        deadline = time.monotonic() + LOCK_TIMEOUT
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(fd, LOCK_OFFSET, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError as error:
                if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                if time.monotonic() >= deadline:
                    _fail("busy")
                time.sleep(0.02)
        project.guard()
        _require(os.path.samestat(original, marker.lstat()), "unsafe")
        yield
    finally:
        try:
            if locked:
                if os.name == "nt":
                    os.lseek(fd, LOCK_OFFSET, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def read_project_prompt(engine):
    """A missing file means revision zero. Reading creates or changes nothing."""
    try:
        project = _Project(engine)
        with _pin(project), _locked(project):
            return project.read()[0]
    except OSError:
        _fail("unavailable")


def save_project_prompt(engine, expected_revision, prompt):
    """CAS the one instruction file. Failures preserve the previously committed file."""
    _require(type(expected_revision) is int and 0 <= expected_revision < MAX_REVISION, "invalid")
    value = _text(prompt)
    try:
        project = _Project(engine)
        with _pin(project), _locked(project):
            current, original = project.read()
            _require(current["revision"] == expected_revision, "conflict")
            record = {"format": "vas-project-prompt", "schemaVersion": 1,
                      "revision": expected_revision + 1, "prompt": value}
            raw = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            _require(len(raw) <= MAX_BYTES, "too_large")
            # This exact staging name is reserved. A crashed writer may leave it;
            # validate before reclaiming, never follow a link or directory.
            if project.info(TEMP_NAME) is not None:
                project.unlink(TEMP_NAME)
            temporary = False
            try:
                fd = project.open(TEMP_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
                temporary = True
                with os.fdopen(fd, "wb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                # Catch direct edits outside this protocol before the commit.
                _require(project.read()[1] == original, "conflict")
                project.replace()
                temporary = False
            finally:
                if temporary:
                    project.unlink(TEMP_NAME)
            return {"revision": record["revision"], "prompt": value}
    except OSError:
        _fail("unavailable")
