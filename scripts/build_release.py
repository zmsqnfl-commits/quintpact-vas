"""VAS 2.11.0 재현 가능한 Windows/독립 설정 폼/Pages 배포 빌더."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CONFIG = ROOT / "src" / "vas-config.js"
ROOT_FILES = [
    "Run-VAS-System.bat", "README.md", "00-처음-사용하기.txt", "LICENSE", "AUTHORS.md",
    "NOTICE.md", "USE_POLICY.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md",
    ".cursorrules", ".windsurfrules",
]
FULL_DIRS = ["src", "docs", "scripts", ".agents"]
LEGAL_FILES = ("LICENSE", "AUTHORS.md", "NOTICE.md", "USE_POLICY.md")
HOST_GUIDES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules", ".windsurfrules")
PROJECT_SKILLS = ("design-analysis",)
SKILL_HOSTS = (".agents", ".claude")
BLOCKED_PARTS = {
    ".git", "node_modules", "__pycache__", ".pytest_cache", ".vas_backups",
    ".temp data", "workspace", "dist", "test-results", "playwright-report", ".vas-session",
}
INTERNAL_DOCUMENT_NAMES = {
    name.casefold() for name in (
        "TASK.md", "CODEX_REPORT.md", "CURRENT_CONTEXT.md", "DECISIONS.md",
        "QUESTIONS_FOR_CHATGPT.md", "HANDOFF_FULL_CONTEXT.md",
    )
}
# Copying and ZIP verification use the same case-insensitive filename boundary.
BLOCKED_NAMES = {
    name.casefold() for name in (
        ".env", ".env.local", ".env.production",
        "credentials.json", "secrets.json", "service-account.json", "vas-session-store.json",
        "VAS-PROJECT-PROMPT.json", ".VAS-PROJECT-PROMPT.tmp",
    )
} | INTERNAL_DOCUMENT_NAMES
SECRET_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}
CLIENT_ASSETS = [
    "client-application.html", "client-style.css", "client-components.css",
    "client-print.css", "client-form.js", "client-draft.js",
    "client-export.js", "client-application-init.js", "vas-config.js",
    "storage-utils.js", "theme-state.js", "editorial-shell.css",
    "editorial-theme.js", "setup-tools.css", "setup-tools.js",
    "design-presets.js", "agent-resources.js", "design-taste-pack.js", "setup-design.js",
    "agent-contract.js", "agent-handoff-web.js", "task-policy.js", "task-inputs.js", "task-inputs.css", "design-reference.js",
]


def version() -> str:
    text = CONFIG.read_text(encoding="utf-8")
    match = re.search(r"version\s*:\s*['\"]([^'\"]+)", text)
    if not match:
        raise RuntimeError("src/vas-config.js 버전을 찾지 못했습니다.")
    return match.group(1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def allowed(path: Path) -> bool:
    if {part.casefold() for part in path.parts} & {part.casefold() for part in BLOCKED_PARTS}:
        return False
    name = path.name.casefold()
    if name in BLOCKED_NAMES or name.startswith(".env.") or path.suffix.casefold() in SECRET_SUFFIXES:
        return False
    return not name.endswith((".pyc", ".log"))


def is_link(path: Path) -> bool:
    try:
        attrs = getattr(path.lstat(), "st_file_attributes", 0)
        return path.is_symlink() or bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return True


def copy_tree(source: Path, target: Path) -> None:
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if is_link(path):
            raise RuntimeError(f"배포 원본에 링크가 포함되어 있습니다: {relative}")
        if not allowed(relative):
            continue
        destination = target / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "-c", "safe.directory=*", "rev-parse", "HEAD"],
            cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def manifest_for(root: Path, target: str, entrypoints: list[str]) -> dict:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "manifest.json":
            continue
        files.append({
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256(path),
        })
    return {
        "schemaVersion": 1,
        "version": version(),
        "target": target,
        "commit": git_commit(),
        "entrypoints": entrypoints,
        "files": files,
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def zip_directory(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(path.relative_to(source.parent).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def native_project_role(relative: Path) -> bytes:
    """Keep the maintained role and host-specific tool limits in project coordinates."""
    source = (ROOT / relative).read_text(encoding="utf-8")
    old = "Use AGENTS.md, which includes the startup procedure from .agents/BOOTSTRAP.md."
    if source.count(old) != 1:
        raise RuntimeError(f"Unrecognized host role preamble: {relative}")
    source = source.replace(old, "Follow the project root AGENTS.md. App code belongs in src/. "
                            "Do not edit the bundled .vas engine. Use the app's own checks.")
    # The generated role contains both prose and commands; never relocate an app's src/.
    source = re.sub(r"(?<![\w./])(?=(?:\.agents|docs|scripts)/)", ".vas/", source)
    return source.encode("utf-8")


def build_windows(stage: Path) -> Path:
    subprocess.run([sys.executable, str(ROOT / "scripts/build-agent-resources.py"), "--check"], check=True)
    root = stage / f"VAS-{version()}-windows"
    engine = root / ".vas"
    engine.mkdir(parents=True)
    for filename in ROOT_FILES:
        shutil.copy2(ROOT / filename, engine / filename)
    for dirname in FULL_DIRS:
        copy_tree(ROOT / dirname, engine / dirname)
    (engine / "project-layout.json").write_bytes(b'{ "layout": "vas-project", "version": 1 }\n')
    (root / "src").mkdir()
    (root / "src/.gitkeep").write_bytes(b"")
    for filename in LEGAL_FILES:
        shutil.copy2(ROOT / filename, root / filename)
    for filename in HOST_GUIDES:
        shutil.copy2(engine / ".agents/PROJECT-ROOT.md", root / filename)
    # Hosts can discover the bundled skill without scanning the private engine.
    # All copies come from the maintained source; relative references stay intact.
    for skill in PROJECT_SKILLS:
        for host in SKILL_HOSTS:
            copy_tree(engine / ".agents/skills" / skill, root / host / "skills" / skill)
    for host, suffix in ((".codex", ".toml"), (".claude", ".md")):
        for role in ("implementer", "designer", "reviewer"):
            relative = Path(host) / "agents" / ("vas_" + role + suffix)
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(native_project_role(relative))
    # pushd supports UNC folders. CALL only a constant relative path: it reparses arguments.
    launcher = ["@echo off", "setlocal DisableDelayedExpansion", 'pushd "%~dp0.vas" || exit /b 1',
                'if not exist ".\\Run-VAS-System.bat" goto :missing', 'call ".\\Run-VAS-System.bat"',
                'set "vasLaunchResult=%ERRORLEVEL%"', "popd", "exit /b %vasLaunchResult%", ":missing",
                "echo Missing .vas\\Run-VAS-System.bat. Extract the entire project ZIP.", "popd", "exit /b 1"]
    (root / "Run-VAS-System.bat").write_bytes(("\r\n".join(launcher) + "\r\n").encode("ascii"))
    # Keep the root quick start independent of the installation folder's name.
    start = f"""# VAS {version()} 프로젝트 시작

ZIP을 새 위치에 **전체 압축 해제**한 뒤, Run-VAS-System.bat과 src가 있는 폴더의 이름을 프로젝트 이름으로 바꾸세요.
그 폴더 자체를 코딩 AI에서 열고 “재고 관리 앱을 만들어줘”처럼 요청합니다. 앱 소스는 src/에 작성됩니다.
.vas/는 함께 제공되는 도구입니다. 앱 코드를 여기에 넣거나 도구 파일을 수정하지 마세요.
이후 같은 위치에서 작업을 재개하려면 먼저 폴더 이름을 정한 뒤 첫 대화를 시작하세요.

화면으로 설정하려면 프로젝트 루트의 Run-VAS-System.bat을 더블클릭합니다.
Windows PowerShell 5.1 이상, 대화형 세션에는 Python 3.10 이상이 필요합니다.
프로젝트 설정과 다음 작업 안내: [프로젝트 사용법](.vas/docs/PROJECT-ROOT.md).
"""
    (root / "README.md").write_text(start, encoding="utf-8", newline="\n")
    (root / "00-처음-사용하기.txt").write_text(start, encoding="utf-8", newline="\n")
    write_json(root / "manifest.json", manifest_for(root, "windows", ["Run-VAS-System.bat"]))
    return root


def build_client(stage: Path) -> Path:
    name = f"VAS-Client-Form-{version()}"
    root = stage / name
    root.mkdir(parents=True)
    for filename in CLIENT_ASSETS:
        source = ROOT / "src" / filename
        target = root / ("index.html" if filename == "client-application.html" else filename)
        if filename == "client-application.html":
            html = source.read_text(encoding="utf-8")
            html = html.replace("<body>", '<body data-mode="standalone">', 1)
            html = re.sub(r'<a class="back-link" id="hubBackLink".*?</a>', '<div class="back-link external-note">공유받은 신청서입니다</div>', html)
            html = re.sub(
                r'<a class="design-reference-link"[^>]*>.*?</a>\s*<p>.*?</p>',
                '<p>선택한 디자인 방향이 JSON에 반영됩니다.</p>',
                html,
            )
            html = re.sub(r'\s*<button[^>]+id="createProjectButton".*?</button>', "", html)
            html = re.sub(r'\s*<a[^>]+id="createdProjectNext".*?</a>', "", html)
            html = re.sub(r'\s*<a[^>]+id="createdProjectHandoff".*?</a>', "", html)
            html = re.sub(r'\s*<script src="(?:runtime-client|personalization-store|memory-identity|memory-browser-adapter|rag-lite)\.js"></script>', "", html)
            html = re.sub(r'\s*<button[^>]*data-setup-settings[^>]*>.*?</button>', "", html)
            target.write_text(html, encoding="utf-8")
        else:
            shutil.copy2(source, target)
    for filename in ("LICENSE", "AUTHORS.md", "NOTICE.md", "USE_POLICY.md"):
        shutil.copy2(ROOT / filename, root / filename)
    (root / "README.md").write_text(
        "# VAS Setup Form\n\nZIP을 새 폴더에 전체 압축 해제한 뒤 `index.html`을 여세요. 요구사항과 디자인을 확인하면 `VAS-AI-HANDOFF.json`이 만들어집니다. 파일 내용과 연락처는 포함하지 않으며 초안은 JSON 저장 뒤 삭제됩니다.\n",
        encoding="utf-8",
    )
    write_json(root / "manifest.json", manifest_for(root, "client-form", ["index.html"]))
    return root


def build_pages(output: Path) -> Path:
    pages = output / "pages"
    copy_tree(ROOT / "src", pages / "src")
    copy_tree(ROOT / "docs", pages / "docs")
    (pages / ".nojekyll").write_text("", encoding="utf-8")
    (pages / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>VAS</title>'
        '<script>location.replace("src/vas-hub.html"+location.search+location.hash)</script>'
        '<a href="src/vas-hub.html">Open VAS</a>\n', encoding="utf-8",
    )
    return pages


def verify_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():
            raise RuntimeError(f"손상된 ZIP: {path.name}")
        for name in archive.namelist():
            parts = Path(name).parts
            lowered = {part.casefold() for part in parts}
            filename = Path(name).name.casefold()
            if ".." in parts or lowered & {part.casefold() for part in BLOCKED_PARTS}:
                raise RuntimeError(f"금지 경로 포함: {name}")
            if filename in INTERNAL_DOCUMENT_NAMES:
                raise RuntimeError(f"내부 상태 문서 포함: {name}")
            if filename in BLOCKED_NAMES or filename.startswith(".env.") or Path(filename).suffix in SECRET_SUFFIXES:
                raise RuntimeError(f"비밀 파일 포함: {name}")


def build(output: Path) -> list[Path]:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build-knowledge-index.py")], cwd=ROOT, check=True)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="vas-release-") as temporary:
        stage = Path(temporary)
        windows = build_windows(stage)
        client = build_client(stage)
        artifacts = [output / f"{windows.name}.zip", output / f"{client.name}.zip"]
        zip_directory(windows, artifacts[0])
        zip_directory(client, artifacts[1])
    build_pages(output)
    for artifact in artifacts:
        verify_zip(artifact)
    release = {
        "schemaVersion": 1,
        "version": version(),
        "commit": git_commit(),
        "artifacts": [{"name": item.name, "size": item.stat().st_size, "sha256": sha256(item)} for item in artifacts],
    }
    write_json(output / "release-manifest.json", release)
    (output / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(item)}  {item.name}\n" for item in artifacts), encoding="utf-8",
    )
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DIST)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        for path in sorted(args.output.glob("*.zip")):
            verify_zip(path)
        print("VAS release artifacts verified")
        return 0
    artifacts = build(args.output.resolve())
    print("Built:", ", ".join(item.name for item in artifacts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
