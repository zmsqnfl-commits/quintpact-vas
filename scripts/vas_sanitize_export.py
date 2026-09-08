"""Apply the canonical privacy policy to a staged compatibility handoff."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from vas_ai_contract import sanitize


def sanitize_export(directory: Path) -> None:
    root = directory.resolve(strict=True)
    for name in ("project.json", "requirements.json", "design-tokens.json", "rag-context.json"):
        path = root / name
        if path.is_symlink() or path.resolve(strict=True).parent != root or path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("unsafe_export_input")
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        path.write_text(json.dumps(sanitize(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        sanitize_export(args.directory)
    except (OSError, ValueError, RecursionError):
        raise SystemExit("VAS_EXPORT_SANITIZATION_FAILED") from None
