"""Run real VAS checks and explicitly scoped file-write preflight checks."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Keep mapped-drive paths for npm on Windows; check_write resolves security boundaries.
ROOT = Path(__file__).absolute().parents[1]
WRITE_ROOTS = {
    "architect": {"docs"},
    "designer": {"src", "docs"},
    "implementer": {"src", "scripts", "tests", "docs"},
    "reviewer": set(),
    "tester": {"tests"},
    "security": {"docs"},
}
PROTECTED = {"workspace", "dist", "node_modules", ".git", ".vas_backups", ".temp data", "logs", "backups"}
WRITE_TOOLS = {"write", "edit", "write_to_file", "replace_file_content", "multi_replace_file_content"}


def check_write(root: Path, role: str, value: str) -> tuple[bool, str]:
    if role not in WRITE_ROOTS or not value:
        return False, "known role and explicit target path required"
    base = root.resolve()
    target = (base / value).resolve()
    try:
        relative = target.relative_to(base)
    except ValueError:
        return False, "target is outside the project"
    parts = {part.casefold() for part in relative.parts}
    if not relative.parts or parts & PROTECTED:
        return False, "protected target"
    if any(re.search(r"(?i)(^\.env(?:\.|$)|^(?:credentials?|secrets?|tokens?)(?:[._-]|$)|\.pem$|\.key$)", part) for part in relative.parts):
        return False, "sensitive target"
    if relative.parts[0] not in WRITE_ROOTS[role]:
        return False, "target is outside this role's file scope"
    return True, "file scope allowed; host permissions still apply"


def check_after(root: Path, role: str, value: str) -> tuple[bool, str]:
    allowed, reason = check_write(root, role, value)
    if not allowed:
        return allowed, reason
    path = (root / value).resolve()
    if not path.is_file():
        return False, "output file does not exist"
    if path.suffix.lower() in {".py", ".js", ".ts", ".html", ".css", ".ps1", ".md"}:
        if len(path.read_text(encoding="utf-8-sig").splitlines()) > 500:
            return False, "output exceeds 500 lines"
    return True, "output checked"


def run(command: list[str]) -> int:
    print("Running: " + " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def npm_script(name: str) -> int:
    # Run npm's JS entry directly: avoid cmd.exe parsing and network downloads.
    node = shutil.which("node")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not node or not npm:
        print("Node.js/npm is required", file=sys.stderr)
        return 2
    npm_path = Path(npm).resolve()
    entry = npm_path.parent / "node_modules/npm/bin/npm-cli.js" if os.name == "nt" else npm_path
    if not entry.is_file():
        print("npm entrypoint unavailable", file=sys.stderr)
        return 2
    command = [node, str(entry), "run", name]
    if name == "test:browser":
        output = tempfile.mkdtemp(prefix="vas-agent-browser-")
        command += ["--", "--workers=2", "--reporter=line", "--output", output]
    return run(command)


def tracked_boundary() -> int:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=False)
    if result.returncode:
        print("Git tracked-file boundary could not be checked", file=sys.stderr)
        return result.returncode
    unsafe = []
    for raw in result.stdout.decode("utf-8").split("\0"):
        if not raw:
            continue
        path = Path(raw)
        if {part.casefold() for part in path.parts} & PROTECTED or path.name.startswith(".env") or path.suffix in {".pem", ".key"}:
            unsafe.append(raw)
    if unsafe:
        print(f"Tracked-file boundary failed: {len(unsafe)} forbidden path(s)", file=sys.stderr)
        return 1
    print("Tracked-file boundary passed (file names only)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["path", "after", "before", "tests", "security"])
    parser.add_argument("--role", default=os.environ.get("AGENT_ROLE", "implementer"))
    parser.add_argument("--path", default=os.environ.get("TARGET_PATH", ""))
    args = parser.parse_args()
    if args.action in {"path", "before", "after"}:
        if args.action == "before" and os.environ.get("TOOL_NAME", "").lower() not in WRITE_TOOLS:
            print("Explicit file-write tool required; shell/tool permissions belong to the host", file=sys.stderr)
            return 1
        check = check_after if args.action == "after" else check_write
        allowed, reason = check(ROOT, args.role, args.path)
        print(reason)
        return 0 if allowed else 1
    if args.action == "tests":
        for script in ("test:python", "test:browser"):
            code = npm_script(script)
            if code:
                return code
        return 0
    code = tracked_boundary()
    if code:
        return code
    if not (ROOT / "dist/release-manifest.json").is_file():
        print("Release artifacts missing; run npm run test:package first", file=sys.stderr)
        return 1
    # Verify actual ZIP contents and compare packaged source hashes to this checkout.
    checks = ("windows_zip_manifest_entrypoint_and_safety", "standalone_form_is_self_contained",
              "release_manifest_and_checksums_match_artifacts", "pages_contains_only_safe_local_files")
    code = run([sys.executable, "tests/test_release_package.py"]
               + ["ReleasePackageTests.test_" + name for name in checks])
    if code:
        return code
    import json
    import zipfile
    import hashlib
    from build_release import FULL_DIRS, allowed, version
    expected = {
        path.relative_to(ROOT).as_posix()
        for directory in FULL_DIRS for path in (ROOT / directory).rglob("*")
        if path.is_file() and allowed(path.relative_to(ROOT))
    }
    expected.update(f"{host}/agents/vas_{role}{suffix}"
                    for host, suffix in ((".codex", ".toml"), (".claude", ".md"))
                    for role in ("implementer", "designer", "reviewer"))
    with zipfile.ZipFile(ROOT / f"dist/VAS-{version()}-windows.zip") as archive:
        manifest = json.loads(archive.read(f"VAS-{version()}-windows/manifest.json"))
        packaged = {item["path"] for item in manifest["files"]
                    if item["path"].startswith(("src/", "scripts/", "docs/", ".agents/", ".codex/agents/", ".claude/agents/"))}
        if packaged != expected:
            print("Release file list is stale; rebuild the package", file=sys.stderr)
            return 1
        for item in manifest["files"]:
            if item["path"] in expected:
                path = ROOT / item["path"]
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                    print("Release source is stale; rebuild the package", file=sys.stderr)
                    return 1
    print("Release boundary and source hashes passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
