#!/usr/bin/env python3
"""VAS 내부 문서를 한글·영문 키워드로 검색합니다."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

TOKEN = re.compile(r"[가-힣]{2,}|[a-z0-9]{2,}", re.I)
STOP_WORDS = {"and", "are", "for", "from", "how", "the", "this", "with", "그리고", "대한", "에서", "으로", "있는", "하는", "합니다"}


def load_builder(script_dir: Path):
    path = script_dir / "build-knowledge-index.py"
    spec = importlib.util.spec_from_file_location("vas_knowledge_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("지식 인덱스 생성기를 불러올 수 없습니다.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tokens(value: str) -> list[str]:
    output: list[str] = []
    for word in TOKEN.findall(value.lower()[:200]):
        if word not in STOP_WORDS and word not in output:
            output.append(word)
        if re.fullmatch(r"[가-힣]{3,}", word):
            for index in range(len(word) - 1):
                pair = word[index:index + 2]
                if pair not in output:
                    output.append(pair)
    return output


def count(text: str, term: str) -> int:
    return min(text.count(term), 4)


def search(entries: list[dict], query: str, limit: int) -> list[dict]:
    terms = tokens(query)
    if not terms:
        return []
    phrase = " ".join(query.lower().split())
    results: list[dict] = []
    for entry in entries:
        title = entry["title"].lower()
        text = entry["text"].lower()
        keywords = " ".join(entry.get("keywords", [])).lower()
        score = sum(count(title, term) * 5 + count(keywords, term) * 3 + count(text, term) * 2 for term in terms)
        if len(phrase) >= 3 and (phrase in title or phrase in text):
            score += 8
        score = round(score * max(0.1, float(entry.get("rank", 1))), 2)
        if score > 0:
            results.append({
                "source": entry["source"],
                "line": entry["line"],
                "title": entry["title"],
                "text": re.sub(r"\s+", " ", entry["text"]).strip()[:300],
                "score": score,
            })
    results.sort(key=lambda item: (-item["score"], item["source"].lower(), item["line"], item["title"]))
    return results[:limit]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    root = (args.root or Path(__file__).resolve().parents[1]).resolve()
    builder = load_builder(Path(__file__).resolve().parent)
    results = search(builder.build_index(root)["entries"], args.query, max(1, min(20, args.limit)))
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif not results:
        print("검색 결과가 없습니다.")
    else:
        for result in results:
            print(f"[{result['score']:.2f}] {result['source']}:{result['line']} — {result['title']}")
            print(f"  {result['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
