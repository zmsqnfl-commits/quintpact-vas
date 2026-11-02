"""A bounded, append-only project summary shared by hosts. All records are reference data."""
from contextlib import ExitStack, contextmanager
import hashlib
import html
import json
import os
import re
import stat
import threading
import time

from vas_ai_contract import canonical
from vas_project_prompt import ProjectPromptError, _Project, _pin, _regular
from vas_session_progress import CHECK_STATUSES, PHASES, _text as progress_text

MAX_SLOTS = 2048
MAX_BYTES = 32 * 1024
MAX_MARKDOWN_BYTES = 64 * 1024
THREAD_WRITER = threading.Lock()
ENTRY = re.compile(r"([0-9]{6})\.(json|md|ok)$")


class SharedProgressError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise SharedProgressError("shared_progress_" + code)


def _text(value, limit):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit, "invalid")
    try:
        return progress_text(value, limit, "shared", [])
    except (TypeError, ValueError):
        raise SharedProgressError("shared_progress_invalid") from None


def shared_summary(raw):
    """Deliberately exclude commands, raw reports, private bindings, and changed file paths."""
    require(isinstance(raw, dict) and raw.get("phase") in PHASES, "invalid")
    checks = raw.get("checks", [])
    require(isinstance(checks, list) and len(checks) <= 10, "invalid")
    result = []
    for check in checks:
        require(isinstance(check, dict) and check.get("status") in CHECK_STATUSES, "invalid")
        result.append({"name": _text(check.get("name"), 120), "status": check["status"]})
    data = {"phase": raw["phase"], "summary": _text(raw.get("summary"), 1000),
            "nextStep": _text(raw.get("nextStep"), 1000), "checks": result}
    if "scope" in raw:
        scope = raw["scope"]
        require(isinstance(scope, dict) and set(scope) == {"objective", "criteria"}, "invalid")
        data["scope"] = {"objective": _text(scope["objective"], 1000),
                         "criteria": _texts(scope["criteria"], 20)}
    for key, limit in (("decisions", 8), ("remaining", 10)):
        if key in raw:
            data[key] = _texts(raw[key], limit)
    return data


def _texts(values, limit):
    require(isinstance(values, list) and len(values) <= limit, "invalid")
    return [_text(value, 300) for value in values]


def _markdown(record):
    # Literalize user-provided text so reading a note never embeds a remote image or HTML.
    def literal(value):
        value = " ".join(value.splitlines())
        return re.sub(r"([\\\`*_{\[\]()<>#~!|}])", r"\\\1", html.escape(value, quote=False))

    def items(values):
        return ["- " + literal(value) for value in values] or ["- 기록 없음"]

    lines = [f"# VAS 프로젝트 인계 · {record['revision']}회",
             "", "확인한 프로젝트 기록입니다. 현재 파일과 대화에서 정한 범위를 대조하세요.",
             "", "## 마지막으로 합의한 목표와 완료조건"]
    scope = record.get("scope")
    if scope:
        lines += [literal(scope["objective"]), "", *items(scope["criteria"])]
    else:
        lines.append("저장된 합의 없음")
    labels = {"passed": "통과", "failed": "실패", "skipped": "건너뜀", "not-run": "미실행"}
    lines += ["", "## 결정 사항", *items(record.get("decisions", [])),
              "", "## 작업 요약", literal(record["summary"]), "", "## 보고된 검사",
              *items([f"{check['name']} · {labels[check['status']]}" for check in record["checks"]]),
              "", "## 남은 일", *items(record.get("remaining", [])),
              "", "## 다음 행동", literal(record["nextStep"])]
    return ("\n".join(lines) + "\n").encode("utf-8")


@contextmanager
def _directory(root, create):
    """Pin the marked project and both real child directories during all operations."""
    project = _Project(root)
    require(project.root == project.engine, "layout")
    with ExitStack() as stack:
        stack.enter_context(_pin(project))
        path, parent_fd = project.root, project.dir_fd
        dirs = []
        for name in ("vas-state", "progress"):
            path = path / name
            dirs.append(path)
            relative = name if parent_fd is not None else path
            if create:
                try:
                    os.mkdir(relative, dir_fd=parent_fd)
                except FileExistsError:
                    pass
            try:
                info = os.stat(relative, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                if create:
                    raise
                yield None
                return
            require(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "unsafe")
            if os.name == "nt":
                stack.enter_context(_pin(project, tuple(dirs)))
            else:
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY, dir_fd=parent_fd)
                stack.callback(os.close, child)
                require(os.path.samestat(info, os.fstat(child)), "unsafe")
                parent_fd = child
        yield _Journal(path, parent_fd)
        require(os.path.samestat(info, path.lstat()), "unsafe")


class _Journal:
    def __init__(self, path, fd):
        self.path, self.fd = path, fd

    @contextmanager
    def file(self, name, flags):
        relative = name if self.fd is not None else self.path / name
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(relative, flags, 0o666, dir_fd=self.fd)
        try:
            current = os.stat(relative, dir_fd=self.fd, follow_symlinks=False)
            opened = os.fstat(fd)
            require(_regular(opened) and _regular(current) and os.path.samestat(opened, current), "unsafe")
            yield fd
        finally:
            os.close(fd)

    def bounds(self):
        last_slot = last_commit = 0
        with os.scandir(self.fd if self.fd is not None else self.path) as entries:
            for count, entry in enumerate(entries, 1):
                require(count <= 3 * MAX_SLOTS + 1, "full")
                if entry.name == "writer.lock":
                    continue
                match = ENTRY.fullmatch(entry.name)
                require(match is not None, "invalid")
                revision = int(match[1])
                require(0 < revision <= MAX_SLOTS, "invalid")
                last_slot = max(last_slot, revision)
                if match[2] == "ok":
                    last_commit = max(last_commit, revision)
        return last_slot, last_commit

    def read(self, revision):
        if not revision:
            return None
        with self.file(f"{revision:06d}.ok", os.O_RDONLY) as fd:
            require(os.fstat(fd).st_size == 0, "invalid")
        with self.file(f"{revision:06d}.json", os.O_RDONLY) as fd:
            require(0 < os.fstat(fd).st_size <= MAX_BYTES, "invalid")
            raw = os.read(fd, MAX_BYTES + 1)
        try:
            envelope = json.loads(raw.decode("utf-8"))
            require(raw == canonical(envelope), "invalid")
            record = envelope["record"]
            require(envelope == {"record": record, "sha256": hashlib.sha256(canonical(record)).hexdigest()}, "invalid")
            require(type(record.get("revision")) is int and record["revision"] == revision, "invalid")
            normalized = {"revision": revision, **shared_summary(record)}
            if "markdownPath" in record:
                normalized["markdownPath"] = f"vas-state/progress/{revision:06d}.md"
                expected = _markdown(normalized)
                with self.file(f"{revision:06d}.md", os.O_RDONLY) as fd:
                    require(os.fstat(fd).st_size == len(expected) and len(expected) <= MAX_MARKDOWN_BYTES,
                            "invalid")
                    require(os.read(fd, len(expected) + 1) == expected, "invalid")
            require(record == normalized, "invalid")
            return record
        except (KeyError, AttributeError, TypeError, UnicodeError, ValueError, RecursionError):
            raise SharedProgressError("shared_progress_invalid") from None

    def write(self, revision, data):
        record = {"revision": revision, **data, "markdownPath": f"vas-state/progress/{revision:06d}.md"}
        raw = canonical({"record": record, "sha256": hashlib.sha256(canonical(record)).hexdigest()})
        require(len(raw) <= MAX_BYTES, "full")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        markdown = _markdown(record)
        require(len(markdown) <= MAX_MARKDOWN_BYTES, "full")
        for suffix, content in (("json", raw), ("md", markdown)):
            with self.file(f"{revision:06d}.{suffix}", flags) as fd:
                with os.fdopen(fd, "wb", closefd=False) as out:
                    out.write(content)
                    out.flush()
                    os.fsync(fd)
        # Readers only consume slots with a complete publication marker.
        with self.file(f"{revision:06d}.ok", flags):
            pass
        return self.read(revision)

    @contextmanager
    def writer(self):
        with ExitStack() as stack:
            require(THREAD_WRITER.acquire(timeout=2), "busy")
            stack.callback(THREAD_WRITER.release)
            # Windows can byte-lock a read-only handle; POSIX lockf needs write access.
            access = os.O_RDONLY if os.name == "nt" else os.O_RDWR
            try:
                fd = stack.enter_context(self.file("writer.lock", access | os.O_CREAT | os.O_EXCL))
            except FileExistsError:
                fd = stack.enter_context(self.file("writer.lock", access))
            deadline = time.monotonic() + 2
            if os.name == "nt":
                import msvcrt
                def acquire():
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                def acquire():
                    fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, 1)
            while True:
                try:
                    acquire()
                    break
                except (BlockingIOError, PermissionError):
                    require(time.monotonic() < deadline, "busy")
                    time.sleep(0.025)
            # The OS releases this advisory byte-range lock when the handle closes.
            yield


def read_shared_progress(root):
    try:
        with _directory(root, create=False) as journal:
            return journal.read(journal.bounds()[1]) if journal else None
    except (OSError, ProjectPromptError):
        raise SharedProgressError("shared_progress_unavailable") from None


def append_shared_progress(root, expected_revision, summary):
    data = shared_summary(summary)
    require(expected_revision is None or type(expected_revision) is int and expected_revision >= 0, "invalid")
    try:
        with _directory(root, create=True) as journal, journal.writer():
            last_slot, current = journal.bounds()
            latest = journal.read(current)
            if latest and shared_summary(latest) == data:
                return latest
            require(current == (expected_revision or 0), "conflict")
            require(last_slot < MAX_SLOTS, "full")
            return journal.write(last_slot + 1, data)
    except FileExistsError:
        raise SharedProgressError("shared_progress_conflict") from None
    except (OSError, ProjectPromptError):
        raise SharedProgressError("shared_progress_unavailable") from None
