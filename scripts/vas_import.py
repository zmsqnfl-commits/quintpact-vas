"""Plan a bounded, opt-in transfer of app-owned code and assets into the starter's src."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager, nullcontext
import errno
import hashlib
import os
from pathlib import Path
import re
import stat
import unicodedata

from vas_ai_contract import canonical, safe_relative
from vas_import_policy import content_reason, file_limit, name_reason, safe_display_path, source_name_blocked
from vas_project_layout import reserves_engine
from vas_project_prompt import ProjectPromptError, _Project, _locked, _pin, _pin_windows, _regular
from vas_session import SessionError
from vas_work_files import RESERVED, _signature


MAX_ENTRIES, MAX_DEPTH, MAX_FILES = 1500, 16, 250
MAX_TOTAL_BYTES = 8 * 1024 * 1024
# Only reserve credential and tool stores in *ancestors*. Mounts may legitimately live under
# /sessions/<id>/mnt, .work, backup, or data. Inside the selected root the full policy applies.
RESERVED_ANCESTORS = {".ssh", ".git", ".hg", ".svn", ".aws", ".azure", ".kube", ".gnupg", ".docker", ".vas",
                      "vas-state", "keys", "secrets", "credentials"}
REASONS = {
    "linked": "링크 또는 하드 링크입니다.",
    "generated": "생성물·캐시 또는 숨김 항목입니다.",
    "operational": "운영 설정·데이터입니다. 앱 코드 이전과 별도로 관리하세요.",
    "credentialFile": "키·비밀번호 등 비밀 정보를 보관할 수 있는 파일입니다.",
    "unsupported": "지원하는 앱 소스·자산·설정 형식에 해당하지 않습니다.",
    "unsupportedContent": "지원하는 파일 내용이나 인코딩을 확인할 수 없습니다.",
    "credential": "실제 자격 증명으로 보이는 값이 있습니다.",
    "review": "코드와 민감한 값의 구분을 직접 확인해야 합니다.",
    "size": "이 파일 형식의 크기 한도를 초과했습니다.",
    "tool": "VAS 도구 폴더입니다.",
    "unsafePath": "이름을 안전한 상대 경로로 표시하거나 복사할 수 없습니다.",
}

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


def import_signature(info):
    signature = _signature(info)
    if os.name == "nt":
        # Windows path stat infers executable bits from suffixes such as .bat;
        # an open descriptor has no filename. Preserve every other identity field.
        return (signature[0], signature[1] & ~0o111, *signature[2:])
    return signature


def read_file(directory, name, before):
    limit = file_limit(name)
    check(_regular(before) and before.st_size <= limit, "file_invalid")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(directory.key(name), flags, dir_fd=directory.fd)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(fd)
        check(_regular(info) and import_signature(before) == import_signature(info), "changed")
        data = stream.read(limit + 1)
        check(len(data) == before.st_size and import_signature(info) == import_signature(os.fstat(fd))
              and import_signature(before) == import_signature(directory.stat(name)), "changed")
    return data


def portable_path(path):
    if safe_display_path(path) != path:
        return False
    for value in (path, unicodedata.normalize("NFKC", path)):
        if safe_relative(value) != value:
            return False
        for part in value.split("/"):
            if (part.startswith(" ") or part.endswith((" ", ".")) or RESERVED.fullmatch(part)
                    or re.search(r'[<>"|?*]', part)):
                return False
    return True


def candidates(source, include):
    files, excluded, reviewable = {}, [], set()
    visited = byte_count = 0
    aliases = set()

    def skip(path, reason, info):
        shown = safe_display_path(path)
        excluded.append({"path": shown, "category": reason, "reason": REASONS[reason],
                         "kind": "directory" if stat.S_ISDIR(info.st_mode) else "file",
                         "canInclude": reason == "review" and shown is not None})

    def visit(directory, parts):
        nonlocal visited, byte_count
        check(len(parts) <= MAX_DEPTH, "limit")
        with directory.entries() as entries:
            for entry in entries:
                visited += 1
                check(visited <= MAX_ENTRIES, "limit")
                relative = "/".join((*parts, entry.name))
                info = directory.stat(entry.name)
                reason = name_reason(relative, info)
                if not portable_path(relative):
                    reason = "unsafePath"
                if reason:
                    skip(relative, reason, info)
                    continue
                alias = unicodedata.normalize("NFKC", relative).casefold()
                check(alias not in aliases, "name_collision")
                aliases.add(alias)
                if stat.S_ISDIR(info.st_mode):
                    with directory.child(entry.name) as child:
                        if reserves_engine(child.path):
                            skip(relative, "tool", info)
                        else:
                            visit(child, (*parts, entry.name))
                    continue
                if info.st_size > file_limit(relative):
                    skip(relative, "size", info)
                    continue
                byte_count += info.st_size
                check(byte_count <= MAX_TOTAL_BYTES, "limit")
                data = read_file(directory, entry.name, info)
                reason = content_reason(relative, data)
                if reason == "review":
                    reviewable.add(relative)
                if reason and not (reason == "review" and relative in include):
                    skip(relative, reason, info)
                    continue
                check(len(files) < MAX_FILES, "limit")
                files[relative] = data

    visit(source, ())
    check(include <= reviewable, "include_not_reviewable")
    excluded.sort(key=lambda item: (item["path"] or "", item["category"], item["kind"]))
    return files, excluded


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


def import_app(root, raw_source, apply=False, expected_plan=None, include=()):
    root = Path(os.path.abspath(root))
    check(isinstance(raw_source, str) and raw_source.strip() and
          not any(ord(c) < 32 for c in raw_source), "source_invalid")
    source = Path(os.path.abspath(raw_source))
    check(source.parent != source, "source_invalid")
    check(not source_name_blocked(source.name) and
          not any(unicodedata.normalize("NFKC", part).casefold() in RESERVED_ANCESTORS
                  for part in source.parts[:-1]), "private_source")
    check(isinstance(include, (tuple, list)) and len(include) <= MAX_FILES and
          all(isinstance(path, str) for path in include), "include_invalid")
    include = {path.replace("\\", "/") for path in include}
    check(all(portable_path(path) for path in include), "include_invalid")
    project = _Project(root)
    check(project.root == project.engine, "layout")
    if apply:
        check(expected_plan is not None, "plan_required")
    try:
        # Preview only observes the filesystem. The writer lock is for applying a transfer.
        with _pin(project, (root / "src",)), (_locked(project) if apply else nullcontext()), opened_root(source) as old:
            source_boundary(source, root)
            files, excluded = candidates(old, include)
            skipped = {}
            for item in excluded:
                key = item["category"]
                skipped[key] = skipped.get(key, 0) + 1
            manifest = [{"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                        for path, data in sorted(files.items())]
            decisions = {"files": manifest, "excluded": excluded, "include": sorted(include)}
            plan = hashlib.sha256(canonical(decisions)).hexdigest()
            report = {**decisions, "skipped": skipped, "planSha256": plan,
                      "appVerification": {"status": "not-run",
                                          "nextStep": "복사 뒤 격리된 앱 폴더에서 실제 진입점을 실행하고 필요한 기능을 확인하세요."}}
            check(expected_plan is None or plan == expected_plan, "plan_changed")
            home = Directory(root, project.dir_fd)
            with home.child("src") as target:
                try:
                    matching = existing_files(target, files)
                except (SessionError, ProjectPromptError, OSError):
                    return {**report, "status": "blocked", "code": "import_destination_conflict", "copied": 0,
                            "recovery": "대상에 기존·부분·확인 불가 파일이 있습니다. "
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
                            return {**report, "status": "partial", "code": "import_copy_interrupted", "copied": copied,
                                    "pending": relative,
                                    "recovery": "이미 완전히 복사한 동일 파일은 재시도할 수 있습니다. "
                                    "부분 파일은 보존되며 재시도가 막히면 새 빈 프로젝트를 사용하세요."}
                    try:
                        check(existing_files(target, files) == files.keys(), "changed")
                    except (OSError, SessionError, ProjectPromptError):
                        return {**report, "status": "partial", "code": "import_readback_failed", "copied": copied,
                                "recovery": "대상이 달라졌습니다. 기존 파일을 보존하고 다시 계획하세요."}
            result = {**report, "status": "applied" if apply else "planned",
                      "matched": len(matching), "copied": copied}
            if not apply:
                result["addArguments"] = ["--apply", "--expected-plan", plan]
                shown = Path(raw_source).as_posix()
                visible_parts = "/".join(part for part in Path(raw_source).parts if part not in {".", ".."})
                if (not Path(raw_source).is_absolute() and safe_display_path(visible_parts) and re.fullmatch(r"[\w .,()/\-]{1,200}", shown)
                        and all(re.fullmatch(r"[\w .()/\-]{1,300}", path) for path in include)):
                    options = "".join(f' --include "{path}"' for path in sorted(include))
                    result["applyCommand"] = (f'python -B scripts/vas.py import --from "{shown}"{options} '
                                              f'--apply --expected-plan {plan}')
            return result
    except OSError as error:
        if error.errno in (errno.ENOSYS, errno.EOPNOTSUPP, errno.ENOLCK):
            raise SessionError("import_filesystem_unavailable") from None
        raise SessionError("import_unavailable") from None
    except ProjectPromptError:
        raise SessionError("import_unavailable") from None
