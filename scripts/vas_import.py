"""Plan a bounded, opt-in transfer of app-owned text code into the starter's src."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import hashlib
import os
from pathlib import Path
import re
import stat
import unicodedata

from vas_ai_contract import SECRET, canonical, credential_view, redact_credentials
from vas_project_import import EXCLUDED_DIRS
from vas_project_layout import reserves_engine
from vas_project_prompt import ProjectPromptError, _Project, _locked, _pin, _pin_windows, _regular
from vas_session import SessionError
from vas_work_files import _signature, normalize_paths


MAX_ENTRIES, MAX_DEPTH, MAX_FILES = 1500, 16, 250
MAX_FILE_BYTES, MAX_TOTAL_BYTES = 512 * 1024, 8 * 1024 * 1024
CODE = {".py", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".css", ".scss", ".html",
        ".vue", ".svelte", ".go", ".rs", ".java", ".kt", ".cs", ".swift", ".c", ".cpp", ".h", ".hpp"}
MANIFESTS = {"package.json", "package-lock.json", "pyproject.toml", "requirements.txt", "cargo.toml",
             "cargo.lock", "go.mod", "go.sum", "dockerfile", "compose.yaml", "compose.yml",
             "docker-compose.yml", "docker-compose.yaml"}
EXCLUDED = EXCLUDED_DIRS | {"vendor", "logs", "log", "data", "database", "storage", "uploads", "backup",
                            "backups", "fixtures", "records", "sessions", "generated", "vas-state"}
PRIVATE_NAME = re.compile(r"(key|token|secret|password|passwd|credential|private|settings|session|userdata|"
                          r"비밀번호|인증키|비밀키|토스키|환경설정)", re.I)


def check(value, code):
    if not value:
        raise SessionError("import_" + code)


class Directory:
    """Children are opened relative to real directory handles, or pinned Windows paths."""
    def __init__(self, path, fd=None):
        self.path, self.fd = path, fd

    def key(self, name):
        return self.path / name if self.fd is None else name

    def stat(self, name):
        return os.stat(self.key(name), dir_fd=self.fd, follow_symlinks=False)

    def entries(self):
        return os.scandir(self.path if self.fd is None else self.fd)

    @contextmanager
    def child(self, name, create=False):
        if create:
            try:
                os.mkdir(self.key(name), dir_fd=self.fd)
            except FileExistsError:
                pass
        path = self.path / name
        if os.name == "nt":
            with _pin_windows([path]):
                yield Directory(path)
            return
        fd = os.open(name, os.O_DIRECTORY | os.O_RDONLY | os.O_NOFOLLOW, dir_fd=self.fd)
        try:
            check(os.path.samestat(os.fstat(fd), self.stat(name)), "changed")
            yield Directory(path, fd)
            check(os.path.samestat(os.fstat(fd), self.stat(name)), "changed")
        finally:
            os.close(fd)


@contextmanager
def opened_root(path):
    if os.name == "nt":
        with _pin_windows((*reversed(path.parents), path)):
            yield Directory(path)
        return
    with ExitStack() as stack:
        dir_fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
        stack.callback(os.close, dir_fd)
        current = Directory(Path(path.anchor), dir_fd)
        for name in path.parts[1:]:
            current = stack.enter_context(current.child(name))
        yield current


def read_file(directory, name, before):
    check(_regular(before) and before.st_size <= MAX_FILE_BYTES, "file_invalid")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(directory.key(name), flags, dir_fd=directory.fd)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(fd)
        check(_regular(info) and _signature(before) == _signature(info), "changed")
        data = stream.read(MAX_FILE_BYTES + 1)
        check(len(data) == before.st_size and _signature(info) == _signature(os.fstat(fd))
              and _signature(before) == _signature(directory.stat(name)), "changed")
    return data


def private_text(data):
    try:
        source = data.decode("utf-8-sig")
    except UnicodeError:
        return True
    view = credential_view(source)
    return ("\0" in source or SECRET.search(view) is not None
            or re.search(r"\b(?:test|live)_g?[cs]k_[A-Za-z0-9_-]{8,}", view, re.I) is not None
            or redact_credentials(source) != source)


def excluded(relative, info):
    name = relative.rsplit("/", 1)[-1].casefold()
    if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
            or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)):
        return "linked"
    if name.startswith(".") or PRIVATE_NAME.search(name) or name in EXCLUDED:
        return "privateOrGenerated"
    try:
        normalize_paths([relative])
    except SessionError:
        return "privateOrGenerated"
    if stat.S_ISDIR(info.st_mode):
        return None
    if not stat.S_ISREG(info.st_mode) or (name not in MANIFESTS and Path(name).suffix not in CODE):
        return "other"
    if info.st_size > MAX_FILE_BYTES:
        return "size"
    return None


def candidates(source):
    files, skipped, visited = {}, {}, 0
    byte_count, aliases = 0, set()

    def visit(directory, parts):
        nonlocal visited, byte_count
        check(len(parts) <= MAX_DEPTH, "limit")
        with directory.entries() as entries:
            for entry in entries:
                visited += 1
                check(visited <= MAX_ENTRIES, "limit")
                relative = "/".join((*parts, entry.name))
                info = directory.stat(entry.name)
                reason = excluded(relative, info)
                if reason:
                    skipped[reason] = skipped.get(reason, 0) + 1
                    continue
                alias = unicodedata.normalize("NFKC", relative).casefold()
                check(alias not in aliases, "name_collision")
                aliases.add(alias)
                if stat.S_ISDIR(info.st_mode):
                    with directory.child(entry.name) as child:
                        if reserves_engine(child.path):
                            skipped["tool"] = skipped.get("tool", 0) + 1
                        else:
                            visit(child, (*parts, entry.name))
                    continue
                byte_count += info.st_size
                check(byte_count <= MAX_TOTAL_BYTES, "limit")
                data = read_file(directory, entry.name, info)
                if private_text(data):
                    skipped["privateOrUnsupported"] = skipped.get("privateOrUnsupported", 0) + 1
                else:
                    check(len(files) < MAX_FILES, "limit")
                    files[relative] = data

    visit(source, ())
    return files, skipped


def planned_parents(files):
    return {str(parent.as_posix()) for path in files for parent in Path(path).parents if str(parent) != "."}


def existing_files(target, files):
    matching, allowed_dirs = set(), planned_parents(files)
    def visit(directory, parts):
        with directory.entries() as entries:
            for entry in entries:
                name = entry.name
                relative = "/".join((*parts, name))
                info = directory.stat(name)
                if relative == ".gitkeep" and _regular(info) and info.st_size == 0:
                    continue
                if relative in allowed_dirs and stat.S_ISDIR(info.st_mode):
                    with directory.child(name) as child:
                        visit(child, (*parts, name))
                else:
                    check(relative in files and _regular(info) and info.st_size == len(files[relative]), "conflict")
                    check(read_file(directory, name, info) == files[relative], "conflict")
                    matching.add(relative)
    visit(target, ())
    return matching


def write_content(stream, data):
    check(stream.write(data) == len(data), "partial_file")
    stream.flush()
    os.fsync(stream.fileno())


def write_candidate(destination, name, data):
    """The connector may allow creation and deny every rename, overwrite and deletion."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(destination.key(name), flags, 0o666, dir_fd=destination.fd)
    except FileExistsError:
        check(read_file(destination, name, destination.stat(name)) == data, "conflict")
        return False
    # A short write must remain as-is; an unknown future writer must never be
    # mistaken for this attempt. Only byte-identical complete files can be reused.
    with os.fdopen(fd, "wb") as stream:
        info = os.fstat(fd)
        check(_regular(info) and os.path.samestat(info, destination.stat(name)), "changed")
        write_content(stream, data)
    check(read_file(destination, name, destination.stat(name)) == data, "changed")
    return True


def source_boundary(source, root):
    check(not source.is_relative_to(root) and not root.is_relative_to(source), "overlap")
    for parent in (source, *source.parents):
        if reserves_engine(parent) or reserves_engine(parent / ".vas"):
            check(parent.name.casefold() != ".vas" and source == parent / "src", "tool_source")
    for name in ("vas-hub.html", "vas-session.py", "Run-VAS-System.bat", "project-layout.json"):
        try:
            (source / name).lstat()
        except FileNotFoundError:
            continue
        raise SessionError("import_tool_source")


def import_app(root, raw_source, apply=False, expected_plan=None):
    root = Path(os.path.abspath(root))
    check(isinstance(raw_source, str) and raw_source.strip() and
          not any(ord(c) < 32 for c in raw_source), "source_invalid")
    source = Path(os.path.abspath(raw_source))
    check(source.parent != source, "source_invalid")
    check(not any(part.startswith(".") or part.casefold() in EXCLUDED
                  for part in source.parts), "private_source")
    check(not PRIVATE_NAME.search(source.name), "private_source")
    project = _Project(root)
    check(project.root == project.engine, "layout")
    if apply:
        check(expected_plan is not None, "plan_required")
    try:
        with _pin(project, (root / "src",)), _locked(project), opened_root(source) as old:
            source_boundary(source, root)
            files, skipped = candidates(old)
            manifest = [{"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                        for path, data in sorted(files.items())]
            plan = hashlib.sha256(canonical(manifest)).hexdigest()
            check(expected_plan is None or plan == expected_plan, "plan_changed")
            home = Directory(root, project.dir_fd)
            with home.child("src") as target:
                try:
                    matching = existing_files(target, files)
                except (SessionError, ProjectPromptError, OSError):
                    return {"status": "blocked", "code": "import_destination_conflict", "copied": 0,
                            "planSha256": plan, "recovery": "대상에 기존·부분·확인 불가 파일이 있습니다. "
                            "파일을 그대로 보존합니다. 새 빈 프로젝트에서 다시 계획하거나 직접 대조하세요."}
                copied = 0
                if apply:
                    for relative in sorted(files.keys() - matching):
                        try:
                            with ExitStack() as stack:
                                directory = target
                                parts = relative.split("/")
                                for name in parts[:-1]:
                                    directory = stack.enter_context(directory.child(name, create=True))
                                copied += int(write_candidate(directory, parts[-1], files[relative]))
                        except (OSError, SessionError, ProjectPromptError):
                            return {"status": "partial", "code": "import_copy_interrupted", "copied": copied,
                                    "pending": relative, "planSha256": plan,
                                    "recovery": "이미 완전히 복사한 동일 파일은 재시도할 수 있습니다. "
                                    "부분 파일은 보존되며 재시도가 막히면 새 빈 프로젝트를 사용하세요."}
                    try:
                        check(existing_files(target, files) == files.keys(), "changed")
                    except (OSError, SessionError, ProjectPromptError):
                        return {"status": "partial", "code": "import_readback_failed", "copied": copied,
                                "planSha256": plan, "recovery": "대상이 달라졌습니다. 기존 파일을 보존하고 다시 계획하세요."}
            result = {"status": "applied" if apply else "planned", "files": manifest, "skipped": skipped,
                      "matched": len(matching), "copied": copied, "planSha256": plan}
            if not apply:
                result["addArguments"] = ["--apply", "--expected-plan", plan]
                shown = Path(raw_source).as_posix()
                if not Path(raw_source).is_absolute() and re.fullmatch(r"[\w .,()/\-]{1,200}", shown):
                    result["applyCommand"] = (f'python -B scripts/vas.py import --from "{shown}" '
                                              f'--apply --expected-plan {plan}')
            return result
    except (ProjectPromptError, OSError):
        raise SessionError("import_unavailable") from None
