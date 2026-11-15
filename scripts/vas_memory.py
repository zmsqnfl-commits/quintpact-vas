"""Project memory kept as plain Markdown inside the project folder.

    vas-state/now.md     the current state, one page
    vas-state/index.md   one line per record, rebuilt from the records
    vas-state/log/       one numbered file per finished piece of work (0012.md)
    vas-state/refs/      reference material the user supplied

A host without Python reads and writes the same files by hand, so every reader here is
lenient and every writer produces text a person can edit. Nothing outside the project
folder is read or written, and no absolute path, credential or host call id is stored.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
from datetime import date
from pathlib import Path

from vas_ai_contract import clean, safe_relative
from vas_paths import is_reparse

# The names live here only, so they can be changed in one place.
STATE = "vas-state"
NOW = "now.md"
INDEX = "index.md"
LOG = "log"
REFS = "refs"

SECTIONS = ("요청", "대상", "완료조건", "정해진 것", "열린 질문", "다음 할 일", "마지막 확인")
RECORD_SECTIONS = ("한 일", "이유", "확인", "안 된 것", "다음 할 일")
MAX_FILE = 256 * 1024
MAX_SECTION = 4_000
MAX_RECORDS = 5_000
INDEX_LINES = 200
RECORD_NAME = re.compile(r"([0-9]{4,})(?:-[^/\\]*)?\.md$")
HEADER = re.compile(r"^판:\s*([0-9]+)")
HEADING = re.compile(r"^##\s+(.+?)\s*$")
CRITERION = re.compile(r"^(\s*-\s*\[)[ xX](\]\s*)(C[1-9][0-9]*)\b")


class ProjectMemoryError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise ProjectMemoryError("memory_" + code)


def _text(value, limit=MAX_SECTION):
    _require(isinstance(value, str), "invalid")
    return clean(value, limit)


def _line(value, limit):
    return " ".join(_text(value, limit).split())


def state_directory(root, *, create=False):
    """Return vas-state after checking that no part of it is a link."""
    root = Path(root)
    path = root / STATE
    for item in (root, path, path / LOG):
        try:
            info = item.lstat()
        except FileNotFoundError:
            if not create:
                return None
            # Two hosts may create the folder at the same moment.
            item.mkdir(exist_ok=True)
            info = item.lstat()
        _require(item.is_dir() and not is_reparse(item, info), "unsafe")
    return path


def _read(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    _require(path.is_file() and not is_reparse(path, info) and info.st_size <= MAX_FILE, "unsafe")
    for attempt in range(40):
        try:
            return path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
        except PermissionError:
            # Windows: another host is swapping this file right now.
            if attempt == 39:
                raise
            time.sleep(0.025)


def _replace(path, text):
    """Write beside the target and swap, so a reader never sees half a file."""
    handle, temporary = tempfile.mkstemp(prefix=".vas-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        for attempt in range(40):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                # Windows refuses the swap while another host is reading or swapping the same file.
                if attempt == 39:
                    raise
                time.sleep(0.025)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def parse_now(text):
    """Split the page into its sections. Unknown sections and hand edits are kept."""
    revision, sections, current, lines = 0, {}, None, []
    for line in (text or "").split("\n"):
        heading = HEADING.match(line)
        if heading:
            if current is not None:
                sections[current] = "\n".join(lines).strip()
            current, lines = heading.group(1), []
        elif current is None:
            found = HEADER.match(line.strip())
            if found:
                revision = int(found.group(1))
        else:
            lines.append(line)
    if current is not None:
        sections[current] = "\n".join(lines).strip()
    return revision, sections


def render_now(revision, sections, by):
    names = list(SECTIONS) + [name for name in sections if name not in SECTIONS]
    body = [f"# 지금 상태", "", f"판: {revision} · 고친 날: {date.today().isoformat()} · 고친 곳: {by}", ""]
    for name in names:
        body += [f"## {name}", "", sections.get(name, "").strip() or "(없음)", ""]
    return "\n".join(body)


def _front(text):
    """Front matter values are JSON so that a title may hold any character."""
    data = {}
    if not text.startswith("---\n"):
        return data, text
    end = text.find("\n---", 4)
    if end < 0:
        return data, text
    for line in text[4:end].split("\n"):
        key, separator, raw = line.partition(":")
        if not separator:
            continue
        raw = raw.strip()
        try:
            value = json.loads(raw)
        except ValueError:
            # A person wrote this line by hand.
            value = ([item.strip() for item in raw[1:-1].split(",") if item.strip()]
                     if raw.startswith("[") and raw.endswith("]") else raw)
        data[key.strip()] = value
    return data, text[end + 4:].lstrip("\n")


def _records(state):
    found = []
    directory = state / LOG
    with os.scandir(directory) as entries:
        for count, entry in enumerate(entries, 1):
            _require(count <= MAX_RECORDS, "full")
            match = RECORD_NAME.fullmatch(entry.name)
            if match and entry.is_file(follow_symlinks=False):
                found.append((int(match.group(1)), entry.name))
    return sorted(found)


def _entry(state, number, name):
    text = _read(state / LOG / name) or ""
    front, _ = _front(text)
    files = front.get("files") if isinstance(front.get("files"), list) else []
    tags = front.get("tags") if isinstance(front.get("tags"), list) else []
    return {"number": number, "path": f"{STATE}/{LOG}/{name}",
            "date": _line(str(front.get("date", "")), 20),
            "title": _line(str(front.get("title", name[:-3])), 120),
            "summary": _line(str(front.get("summary", "")), 200),
            "files": [_line(str(item), 240) for item in files[:20]],
            "tags": [_line(str(item), 40) for item in tags[:10]]}


def _index_line(entry):
    tags = " ".join("#" + tag.replace(" ", "-") for tag in entry["tags"])
    cells = [f"{entry['number']:04d}", entry["date"], entry["title"], entry["summary"],
             ", ".join(entry["files"]), tags]
    return "- " + " | ".join(cell.replace("|", "/") for cell in cells)


def rebuild_index(root):
    """The index is a cache of the records, so it can always be made again."""
    state = state_directory(root, create=True)
    entries = [_entry(state, number, name) for number, name in _records(state)]
    lines = ["# 기록 목차", "", "번호 | 날짜 | 제목 | 한 줄 요약 | 파일 | 태그", ""]
    lines += [_index_line(entry) for entry in entries]
    _replace(state / INDEX, "\n".join(lines) + "\n")
    return entries


def read_memory(root, limit=20):
    """A bounded, read-only view for the start of a conversation."""
    state = state_directory(root)
    if state is None:
        return {"status": "empty", "now": None, "records": [], "recordCount": 0}
    text = _read(state / NOW)
    revision, sections = parse_now(text)
    names = _records(state)
    records = [_entry(state, number, name) for number, name in names[-limit:]]
    view = {"status": "available" if text is not None or names else "empty",
            "now": None if text is None else {"revision": revision, "path": f"{STATE}/{NOW}",
                                              "sections": sections},
            "records": records, "recordCount": len(names)}
    if names:
        view["indexPath"] = f"{STATE}/{INDEX}"
    return view


def _tick(text, criteria):
    wanted, done, lines = set(criteria), set(), []
    for line in text.split("\n"):
        match = CRITERION.match(line)
        if match and match.group(3) in wanted:
            line = CRITERION.sub(lambda m: m.group(1) + "x" + m.group(2) + m.group(3), line, count=1)
            done.add(match.group(3))
        lines.append(line)
    _require(done == wanted, "criterion_unknown")
    return "\n".join(lines)


def known_criteria(root):
    state = state_directory(root)
    text = parse_now(_read(state / NOW))[1].get("완료조건", "") if state else ""
    return {match.group(3) for match in map(CRITERION.match, text.split("\n")) if match}


def update_now(root, sections, by, expected_revision=None, tick=()):
    """Merge the given sections into the page and tick criteria, in one write.

    Sections that are not given stay as they are.
    """
    _require(isinstance(sections, dict) and (sections or tick), "invalid")
    state = state_directory(root, create=True)
    revision, current = parse_now(_read(state / NOW))
    _require(expected_revision is None or expected_revision == revision, "conflict")
    for name, value in sections.items():
        _require(isinstance(name, str) and name.strip() and "\n" not in name, "invalid")
        current[_line(name, 40)] = _text(value)
    if tick:
        current["완료조건"] = _tick(current.get("완료조건", ""), tick)
    _replace(state / NOW, render_now(revision + 1, current, _line(by, 40) or "unknown"))
    return {"revision": revision + 1, "path": f"{STATE}/{NOW}"}


def write_record(root, title, summary, by, sections, files=(), tags=()):
    """Create one record file. Records are only ever added, never rewritten."""
    title, summary = _line(title, 120), _line(summary, 200)
    _require(title and summary, "invalid")
    _require(isinstance(sections, dict) and len(files) <= 40 and len(tags) <= 10, "invalid")
    paths = []
    for item in files:
        relative = safe_relative(item) if isinstance(item, str) else None
        _require(relative, "file_path_invalid")
        paths.append(relative)
    front = {"date": date.today().isoformat(), "title": title, "summary": summary,
             "by": _line(by, 40) or "unknown", "tags": [_line(tag, 40) for tag in tags], "files": paths}
    body = ["---"] + [f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in front.items()]
    body += ["---", ""]
    for name in RECORD_SECTIONS:
        value = _text(sections.get(name, "")) if name in sections else ""
        if value:
            body += [f"## {name}", "", value, ""]
    state = state_directory(root, create=True)
    number = (_records(state) or [(0, "")])[-1][0] + 1
    for _ in range(20):
        # The name is the number alone: it is the same on every system, and an exclusive
        # create gives two hosts that finish together two different numbers.
        name = f"{number:04d}.md"
        try:
            handle = os.open(state / LOG / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            number += 1
            continue
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("\n".join(body))
        result = {"number": number, "path": f"{STATE}/{LOG}/{name}", "files": paths}
        try:
            rebuild_index(root)
        except OSError:
            # The record itself is saved. The index is only a cache and the next write remakes it.
            result["indexStale"] = True
        return result
    raise ProjectMemoryError("memory_busy")


def recall(root, query, limit=5):
    """Find the records that bear on a request, so a host opens only those.

    Matching is by the words of the query: a hit in the title, tags or files counts most,
    then the summary, then the body. Newer records win a tie.
    """
    words = [word for word in re.split(r"[^0-9A-Za-z가-힣]+", _line(query, 400).casefold()) if len(word) >= 2]
    _require(words, "invalid")
    state = state_directory(root)
    if state is None:
        return {"status": "empty", "matches": [], "recordCount": 0}
    names, found = _records(state), []
    for number, name in names:
        entry = _entry(state, number, name)
        front, body = _front(_read(state / LOG / name) or "")
        head = " ".join([entry["title"], *entry["tags"], *entry["files"]]).casefold()
        summary, text = entry["summary"].casefold(), body.casefold()
        hits = {word: 3 if word in head else 2 if word in summary else 1 if word in text else 0 for word in words}
        score = sum(hits.values())
        if score:
            failed = parse_now(body)[1].get("안 된 것", "")
            entry.update(score=score, matched=[word for word, hit in hits.items() if hit])
            if failed:
                entry["failed"] = failed[:300]
            found.append(entry)
    found.sort(key=lambda entry: (-entry["score"], -entry["number"]))
    return {"status": "ok", "matches": found[:max(1, min(limit, 20))], "recordCount": len(names)}
