#!/usr/bin/env python3
"""활성 VAS 문서를 결정적 브라우저 검색 인덱스로 변환합니다."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = 1
EXCLUDED_PARTS = {
    ".git", ".temp data", "node_modules", "backups", "secrets",
    "credentials", "private", "__pycache__",
}
EXCLUDED_NAMES = {"log.md"}
SENSITIVE_NAME = re.compile(r"(?:secret|credential|password|private[-_ ]?key|api[-_ ]?key)", re.I)
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|api[_ -]?key|access[_ -]?token|authorization)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
CREDENTIAL_VALUE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._~-]{12,}|(?:sk|ghp|github_pat)-?[a-z0-9_-]{12,}|"
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----)"
)
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TOKEN = re.compile(r"[가-힣]{2,}|[a-z0-9]{2,}", re.I)
STOP_WORDS = {"and", "are", "for", "from", "how", "the", "this", "with", "그리고", "대한", "에서", "으로", "있는", "하는", "합니다"}
MAX_SECTION_CHARS = 1400


def is_allowed(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    lowered = {part.lower() for part in relative.parts}
    if lowered & EXCLUDED_PARTS or path.name.lower() in EXCLUDED_NAMES or SENSITIVE_NAME.search(path.name):
        return False
    if path.suffix.lower() != ".md":
        return False
    return True


def source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    docs = root / "docs"
    agents = root / ".agents"
    if docs.exists():
        files.extend(docs.rglob("*.md"))
    if agents.exists():
        files.extend(path for path in [agents / "CONTEXT.md", agents / "access-control.md"] if path.exists())
        files.extend((agents / "workflows").glob("*.md"))
        files.extend((agents / "skills").glob("*/SKILL.md"))
        files.extend((agents / "skills").glob("*/TASTE-RULES.md"))
    files = [path for path in files if is_allowed(path, root)]
    return sorted(set(files), key=lambda path: path.relative_to(root).as_posix().lower())


def redact_line(line: str) -> str:
    line = SENSITIVE_ASSIGNMENT.sub(lambda match: match.group(1) + match.group(2) + "[redacted]", line)
    return CREDENTIAL_VALUE.sub("[redacted]", line)


def clean_markdown(lines: list[str]) -> str:
    cleaned: list[str] = []
    blank = False
    for raw in lines:
        line = redact_line(raw.rstrip())
        if not line.strip():
            if cleaned and not blank:
                cleaned.append("")
            blank = True
            continue
        blank = False
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def chunks(text: str, maximum: int = MAX_SECTION_CHARS) -> list[str]:
    if len(text) <= maximum:
        return [text] if text else []
    output: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        while len(paragraph) > maximum:
            cut = paragraph.rfind(" ", 0, maximum)
            if cut < maximum // 2:
                cut = maximum
            piece, paragraph = paragraph[:cut].strip(), paragraph[cut:].strip()
            if current:
                output.append(current)
                current = ""
            output.append(piece)
        candidate = paragraph if not current else current + "\n\n" + paragraph
        if len(candidate) > maximum:
            output.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        output.append(current)
    return output


def make_keywords(title: str, text: str) -> list[str]:
    # Python 문자열에는 JS의 normalize 메서드가 없으므로 unicodedata를 사용하지 않아도
    # UTF-8 원문과 정규식 결과의 결정성은 유지됩니다.
    output: list[str] = []
    for token in TOKEN.findall(title + " " + text):
        lowered = token.lower()
        if lowered not in STOP_WORDS and lowered not in output:
            output.append(lowered)
        if len(output) >= 24:
            break
    return output


def document_rank(relative: str) -> float:
    name = Path(relative).name.lower()
    return 0.35 if name in {"log.md", "history.md", "lessons.md"} else 1.0


def parse_document(path: Path, root: Path) -> list[dict]:
    relative = path.relative_to(root).as_posix()
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    sections: list[tuple[str, int, list[str]]] = []
    title = path.stem.replace("-", " ")
    start_line = 1
    body: list[str] = []
    in_fence = False
    for line_number, raw in enumerate(lines, 1):
        if raw.strip().startswith("```"):
            in_fence = not in_fence
        match = HEADING.match(raw) if not in_fence else None
        if match:
            content = clean_markdown(body)
            if content:
                sections.append((title, start_line, body))
            title = re.sub(r"[*_`]", "", match.group(2)).strip()
            start_line = line_number
            body = []
        else:
            body.append(raw)
    if clean_markdown(body):
        sections.append((title, start_line, body))

    entries: list[dict] = []
    rank = document_rank(relative)
    for section_title, line_number, section_lines in sections:
        text = clean_markdown(section_lines)
        for chunk_number, text_chunk in enumerate(chunks(text), 1):
            identity = f"{relative}:{line_number}:{chunk_number}:{section_title}"
            entries.append({
                "id": hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16],
                "source": relative,
                "title": section_title,
                "line": line_number,
                "text": text_chunk,
                "keywords": make_keywords(section_title, text_chunk),
                "rank": rank,
            })
    return entries


def build_index(root: Path) -> dict:
    entries: list[dict] = []
    sources = source_files(root)
    for path in sources:
        entries.extend(parse_document(path, root))
    entries.sort(key=lambda item: (item["source"].lower(), item["line"], item["id"]))
    payload = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    return {
        "schema": SCHEMA,
        "digest": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "sourceCount": len(sources),
        "entries": entries,
    }


def render_index(index: dict) -> str:
    payload = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    return (
        "/** scripts/build-knowledge-index.py로 생성된 결정적 문서 인덱스입니다. */\n"
        "(function(global){'use strict';\n"
        f"global.VASKnowledgeIndex=Object.freeze({payload});\n"
        "})(typeof window!=='undefined'?window:globalThis);\n"
    )


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output or root / "src" / "knowledge-index.js"
    index = build_index(root)
    rendered = render_index(index)
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            print(f"지식 인덱스가 최신이 아닙니다: {output}", file=sys.stderr)
            return 1
        print(f"지식 인덱스 최신: {output}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8", newline="\n")
    temporary.replace(output)
    print(f"지식 인덱스 생성: {len(index['entries'])}개 섹션")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
