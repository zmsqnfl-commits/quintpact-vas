"""package.json을 기준으로 VAS 릴리스 버전 표기가 맞는지 확인합니다."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]

REQUIRED = {
    "package-lock.json": f'"version": "{VERSION}"',
    "src/vas-config.js": f"version: '{VERSION}'",
    "scripts/Start-VAS.ps1": f'"{VERSION}-$rootHash"',
    "scripts/VAS.Server.psm1": f"version = '{VERSION}'",
    "Run-VAS-System.bat": f"title VAS {VERSION}",
    "scripts/build_release.py": f"VAS {VERSION} 재현 가능한",
}


def main() -> int:
    failures: list[str] = []
    for relative, marker in REQUIRED.items():
        content = (ROOT / relative).read_text(encoding="utf-8-sig")
        if marker not in content:
            failures.append(f"{relative}: {marker!r} 없음")
    if failures:
        print("\n".join(failures))
        return 1
    print(f"VAS version sync OK: {VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
