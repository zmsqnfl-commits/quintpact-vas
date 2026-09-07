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
    "scripts/vas_agent_handoff.py": f'VAS_VERSION = "{VERSION}"',
    "scripts/VAS.Projects.psm1": f"vasVersion = '{VERSION}'",
    "src/agent-handoff-web.js": f"VASConfig.version : '{VERSION}'",
    "src/theme-state.js": f"global.VASConfig.version : '{VERSION}'",
    "README.md": f"# VAS {VERSION}",
    ".agents/CONTEXT.md": f"# VAS {VERSION}",
    "docs/INSTRUCTIONS.md": f"# VAS {VERSION}",
    f"docs/releases/{VERSION}.md": f"# VAS {VERSION}",
}
for page in ("vas-hub", "client-application", "project-import", "design-controller", "knowledge-search", "memory-center"):
    REQUIRED[f"src/{page}.html"] = f"<title>VAS {VERSION}"


def main() -> int:
    failures: list[str] = []
    lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
    if lock.get("version") != VERSION or lock.get("packages", {}).get("", {}).get("version") != VERSION:
        failures.append("package-lock.json: 루트 패키지 버전 불일치")
    for relative, marker in REQUIRED.items():
        if not (ROOT / relative).is_file():
            failures.append(f"{relative}: 파일 없음")
            continue
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
