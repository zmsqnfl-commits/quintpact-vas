"""Deterministic, secret-aware RAG index for registered VAS projects."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = 1
MAX_FILE_BYTES = 256 * 1024
MAX_PROJECT_BYTES = 2 * 1024 * 1024
MAX_CHUNK_CHARS = 1400
MAX_INDEX_BYTES = 16 * 1024 * 1024
ALLOWED_SUFFIXES = {
    ".md", ".txt", ".html", ".css", ".js", ".ts", ".jsx", ".tsx",
    ".py", ".ps1", ".json", ".yaml", ".yml", ".toml",
}
EXCLUDED_DIRS = {
    ".cache", ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".ssh", ".tox", ".venv", "__pycache__", "build", "cache", "caches",
    "coverage", "credentials", "dist", "keys", "node_modules", "out",
    "private", "secrets", "target", "vendor", "venv",
}
SECRET_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}
SECRET_BASENAMES = {
    ".env", "brief.json", "credentials.json", "id_ed25519", "id_rsa", "secrets.json",
    "service-account.json",
}
SENSITIVE_NAME = re.compile(
    r"(?:^|[-_.])(?:api[-_.]?keys?|credentials?|passwords?|private[-_.]?keys?|secrets?|tokens?)(?:$|[-_.])",
    re.I,
)
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|api[_ -]?key|access[_ -]?token|authorization|"
    r"client[_ -]?secret|database[_ -]?url|db[_ -]?(?:url|password|pass)|"
    r"aws[_ -]?(?:access[_ -]?key[_ -]?id|secret[_ -]?access[_ -]?key|session[_ -]?token)|"
    r"google[_ -]?(?:api[_ -]?key|application[_ -]?credentials)|"
    r"github[_ -]?(?:token|pat))([\"']?\s*[:=]\s*[\"']?)([^\s,;\"']+)"
)
CREDENTIAL_VALUE = re.compile(
    r"(?ix)(?:"
    r"\bbearer\s+[a-z0-9._~-]{10,}|"
    r"\b(?:sk-(?:proj-)?[a-z0-9_-]{16,}|gh[pousr]_[a-z0-9_]{16,}|"
    r"github_pat_[a-z0-9_]{16,}|(?:AKIA|ASIA)[A-Z0-9]{16}|"
    r"AIza[a-z0-9_-]{20,}|xox[baprs]-[a-z0-9-]{10,})\b|"
    r"\beyJ[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\b|"
    r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|mssql)://[^\s\"'<>]+"
    r")"
)
PRIVATE_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----", re.S
)
WINDOWS_PATH = re.compile(r"(?i)(?:file:/+)?[a-z]:[\\/][^\s\"'<>`]+")
UNC_PATH = re.compile(r"\\\\[^\s\"'<>`]+[\\/][^\s\"'<>`]+")
POSIX_PATH = re.compile(r"(?<![\w:])/(?:home|Users|var|tmp|etc|opt|root|mnt|Volumes)/[^\s\"'<>`]+")
TOKEN = re.compile(r"[가-힣]{2,}|[a-z0-9]{2,}", re.I)
STOP_WORDS = {
    "and", "are", "for", "from", "how", "the", "this", "with",
    "그리고", "대한", "에서", "으로", "있는", "하는", "합니다",
}


class KnowledgeError(RuntimeError):
    """Raised when the project registry or index cannot be handled safely."""


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_reparse(path: Path, item_stat: os.stat_result | None = None) -> bool:
    try:
        value = item_stat or path.lstat()
    except OSError:
        return True
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(getattr(value, "st_file_attributes", 0) & marker)


def _sensitive_name(name: str) -> bool:
    lower = name.casefold()
    return (
        lower in SECRET_BASENAMES
        or lower.startswith(".env.")
        or Path(lower).suffix in SECRET_SUFFIXES
        or bool(SENSITIVE_NAME.search(lower))
    )


def _safe_project_id(value: Any, relative: str) -> str:
    candidate = str(value or "")[:100]
    if re.fullmatch(r"[A-Za-z0-9._-]+", candidate):
        return candidate
    return hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]


def registered_projects(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    projects_root = (root / "workspace" / "projects").resolve(strict=False)
    registry = root / "workspace" / ".vas" / "projects.json"
    if not registry.exists():
        return []
    try:
        payload = json.loads(registry.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise KnowledgeError("프로젝트 레지스트리를 읽을 수 없습니다.") from error
    records = payload.get("projects", []) if isinstance(payload, dict) else []
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        raise KnowledgeError("프로젝트 레지스트리 형식이 올바르지 않습니다.")
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or not record.get("path"):
            continue
        if record.get("createIndex") is not True:
            continue
        if str(record.get("status", "ready")).casefold() in {"deleted", "removed", "rolled_back"}:
            continue
        raw_path = Path(str(record["path"]))
        project = (raw_path if raw_path.is_absolute() else root / raw_path).resolve(strict=False)
        if not project.is_dir() or _is_reparse(project) or not _is_relative_to(project, projects_root):
            continue
        relative_path = project.relative_to(projects_root)
        if not relative_path.parts:
            continue
        identity = str(project).casefold()
        if identity in seen:
            continue
        seen.add(identity)
        relative = relative_path.as_posix()
        output.append({
            "id": _safe_project_id(record.get("projectId") or record.get("jobId"), relative),
            "path": project,
            "relative": relative,
        })
    return sorted(output, key=lambda item: (item["relative"].casefold(), item["id"]))


def _candidate_files(project: Path) -> list[tuple[str, Path, int]]:
    output: list[tuple[str, Path, int]] = []
    pending = [project]
    while pending:
        folder = pending.pop()
        try:
            entries = sorted(os.scandir(folder), key=lambda item: item.name.casefold())
        except OSError:
            continue
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(project).as_posix()
            try:
                item_stat = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if _is_reparse(path, item_stat):
                continue
            lower = entry.name.casefold()
            if entry.is_dir(follow_symlinks=False):
                if lower not in EXCLUDED_DIRS and not _sensitive_name(entry.name):
                    pending.append(path)
            elif entry.is_file(follow_symlinks=False):
                if (
                    path.suffix.casefold() in ALLOWED_SUFFIXES
                    and not _sensitive_name(entry.name)
                    and item_stat.st_size <= MAX_FILE_BYTES
                ):
                    output.append((relative, path, item_stat.st_size))
    return sorted(output, key=lambda item: item[0].casefold())


def _decode_text(data: bytes) -> str | None:
    sample = data[:8192]
    if b"\x00" in sample:
        return None
    controls = sum(byte < 9 or 13 < byte < 32 for byte in sample)
    if sample and controls / len(sample) > 0.01:
        return None
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def redact_text(text: str, project: Path) -> str:
    for value in {str(project), project.as_posix()}:
        if value:
            text = re.sub(re.escape(value), "[path]", text, flags=re.I)
    text = PRIVATE_BLOCK.sub("[redacted]", text)
    text = WINDOWS_PATH.sub("[path]", text)
    text = UNC_PATH.sub("[path]", text)
    text = POSIX_PATH.sub("[path]", text)
    text = CREDENTIAL_VALUE.sub("[redacted]", text)
    text = SECRET_ASSIGNMENT.sub(lambda match: match.group(1) + match.group(2) + "[redacted]", text)
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)


def chunks(text: str, maximum: int = MAX_CHUNK_CHARS) -> list[tuple[int, str]]:
    output: list[tuple[int, str]] = []
    current: list[str] = []
    current_length = 0
    start_line = 1

    def flush() -> None:
        nonlocal current, current_length
        value = "\n".join(current).strip()
        if value:
            output.append((start_line, value))
        current, current_length = [], 0

    for line_number, line in enumerate(text.splitlines(), 1):
        pieces = [line[index:index + maximum] for index in range(0, len(line), maximum)] or [""]
        for piece in pieces:
            added = len(piece) + (1 if current else 0)
            if current and current_length + added > maximum:
                flush()
            if not current:
                start_line = line_number
            current.append(piece)
            current_length += len(piece) + (1 if len(current) > 1 else 0)
    flush()
    return output


def _title(path: Path, text: str) -> str:
    heading = re.search(r"(?m)^\s*#{1,6}\s+(.+?)\s*$", text)
    if heading:
        return re.sub(r"[*_`]", "", heading.group(1)).strip()[:180]
    html_title = re.search(r"(?is)<title[^>]*>(.*?)</title>", text)
    if html_title:
        return re.sub(r"\s+", " ", html_title.group(1)).strip()[:180]
    return path.stem.replace("-", " ").replace("_", " ")[:180]


def _keywords(title: str, text: str) -> list[str]:
    output: list[str] = []
    for token in TOKEN.findall(title + " " + text):
        lower = token.casefold()
        if lower not in STOP_WORDS and lower not in output:
            output.append(lower)
        if len(output) == 24:
            break
    return output


def _project_entries(project: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    entries: list[dict[str, Any]] = []
    used = 0
    source_count = 0
    prefix = "workspace/projects/" + project["relative"]
    for relative, path, expected_size in _candidate_files(project["path"]):
        if used + expected_size > MAX_PROJECT_BYTES:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) > MAX_FILE_BYTES or used + len(data) > MAX_PROJECT_BYTES:
            continue
        text = _decode_text(data)
        if text is None:
            continue
        text = redact_text(text, project["path"])
        pieces = chunks(text)
        if not pieces:
            continue
        used += len(data)
        source_count += 1
        source = prefix + "/" + relative
        title = _title(path, text)
        for chunk_number, (line_number, value) in enumerate(pieces, 1):
            identity = f"{source}:{line_number}:{chunk_number}:{value}"
            entries.append({
                "id": hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16],
                "projectId": project["id"],
                "source": source,
                "title": title,
                "line": line_number,
                "text": value,
                "keywords": _keywords(title, value),
                "rank": 1.1,
            })
    return entries, source_count


def build_index(root: Path) -> dict[str, Any]:
    root = root.resolve()
    projects = registered_projects(root)
    generated: list[dict[str, Any]] = []
    for project in projects:
        project_entries, _ = _project_entries(project)
        generated.extend(project_entries)
    generated.sort(key=lambda item: (item["source"].casefold(), item["line"], item["id"]))

    reserve = min(64 * 1024, max(512, MAX_INDEX_BYTES // 16))
    entry_budget = max(0, MAX_INDEX_BYTES - reserve)
    entries: list[dict[str, Any]] = []
    entry_bytes = 0
    for entry in generated:
        encoded = json.dumps(
            entry, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        cost = len(encoded) + (1 if entries else 0)
        if entry_bytes + cost > entry_budget:
            break
        entries.append(entry)
        entry_bytes += cost

    def make_index(selected: list[dict[str, Any]]) -> dict[str, Any]:
        compact = json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        all_project_ids = {entry["projectId"] for entry in generated}
        selected_project_ids = {entry["projectId"] for entry in selected}
        skipped_chunks = len(generated) - len(selected)
        skipped_projects = len(all_project_ids - selected_project_ids)
        warnings = []
        if skipped_chunks:
            warnings.append(
                f"전체 색인 16MB 제한으로 프로젝트 {skipped_projects}개, "
                f"청크 {skipped_chunks}개를 건너뛰었습니다."
            )
        sources = {entry["source"] for entry in selected}
        return {
            "schema": SCHEMA,
            "digest": hashlib.sha256(compact.encode("utf-8")).hexdigest(),
            "projectCount": len(projects),
            "sourceCount": len(sources),
            "stats": {
                "registeredProjects": len(projects),
                "indexedProjects": len(selected_project_ids),
                "entryCount": len(selected),
                "generatedChunks": len(generated),
                "skippedProjects": skipped_projects,
                "skippedChunks": skipped_chunks,
                "maxIndexBytes": MAX_INDEX_BYTES,
            },
            "warnings": warnings,
            "entries": selected,
        }

    index = make_index(entries)
    while entries and len(render_index(index).encode("utf-8")) > MAX_INDEX_BYTES:
        entries.pop()
        index = make_index(entries)
    if len(render_index(index).encode("utf-8")) > MAX_INDEX_BYTES:
        raise KnowledgeError("프로젝트 지식 색인 메타데이터가 크기 제한을 초과했습니다.")
    return index


def render_index(index: dict[str, Any]) -> str:
    return json.dumps(index, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def index_path(root: Path) -> Path:
    return root.resolve() / "workspace" / ".vas" / "project-knowledge.json"


def write_index(root: Path) -> tuple[Path, dict[str, Any]]:
    output = index_path(root)
    index = build_index(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=output.parent,
            prefix=".project-knowledge-", suffix=".tmp", delete=False,
        ) as handle:
            handle.write(render_index(index))
            temporary = Path(handle.name)
        os.replace(temporary, output)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return output, index


def check_index(root: Path, index: dict[str, Any] | None = None) -> bool:
    output = index_path(root)
    return output.is_file() and output.read_text(encoding="utf-8") == render_index(index or build_index(root))
