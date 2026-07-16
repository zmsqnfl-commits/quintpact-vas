"""VAS 2.6.0 재현 가능한 Windows/독립 신청서/Pages 배포 빌더."""
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
]
FULL_DIRS = ["src", "docs", "scripts", ".agents"]
BLOCKED_PARTS = {
    ".git", "node_modules", "__pycache__", ".pytest_cache", ".vas_backups",
    ".temp data", "workspace", "dist", "test-results", "playwright-report",
}
BLOCKED_NAMES = {".env", ".env.local", ".env.production"}
BLOCKED_NAMES.update({"credentials.json", "secrets.json", "service-account.json"})
SECRET_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}
CLIENT_ASSETS = [
    "client-application.html", "client-style.css", "client-components.css",
    "client-print.css", "client-i18n.js", "client-form.js", "client-draft.js",
    "client-export.js", "client-application-init.js", "vas-config.js",
    "storage-utils.js", "theme-state.js",
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


def build_windows(stage: Path) -> Path:
    name = f"VAS-{version()}-windows"
    root = stage / name
    root.mkdir(parents=True)
    for filename in ROOT_FILES:
        shutil.copy2(ROOT / filename, root / filename)
    for dirname in FULL_DIRS:
        copy_tree(ROOT / dirname, root / dirname)
    (root / "README.md").write_text(
        """# VAS 2.6.0 Windows 실행본

## 시작

먼저 `00-처음-사용하기.txt`를 읽어주세요.

1. ZIP을 새 폴더에 **전체 압축 해제**합니다.
2. `Run-VAS-System.bat`를 더블클릭합니다.
3. 허브에서 새 프로젝트를 만들거나 **기존 프로그램 가져오기**를 선택합니다.

Windows 10/11과 PowerShell 5.1 이상을 사용합니다. 기존 프로그램 가져오기에는 Python 3.10 이상이 필요하며, 준비되지 않은 경우 화면에서 설치 안내가 표시됩니다. 신청서·디자인·내부 문서 검색은 Python 없이도 사용할 수 있습니다.

프로젝트는 이 폴더의 `workspace/projects/`에 생성됩니다. 가져오기 전에는 원본을 읽기만 하고, 승인 후 백업·복제·검증한 사본을 등록합니다. 원본 삭제는 자동으로 실행하지 않습니다.

개인화 메모리와 프로젝트 RAG는 사용자가 동의한 경우에만 이 기기에서 작동합니다. 비밀 후보와 절대 경로는 제외하거나 가리며 VAS가 외부 서비스로 자동 전송하지 않습니다. RAG 맥락을 넣어 복사한 프롬프트를 외부 AI에 붙여넣으면 그 맥락도 전달될 수 있습니다.

문제가 생기면 BAT 창의 안내를 확인한 뒤 다시 실행하세요. 사용하지 않으면 로컬 서버는 기본 30분 뒤 자동 종료됩니다.
""",
        encoding="utf-8",
    )
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
            html = re.sub(r'\s*<button[^>]+id="createProjectButton".*?</button>', "", html)
            html = re.sub(r'\s*<a[^>]+id="createdProjectNext".*?</a>', "", html)
            html = re.sub(r'\s*<script src="(?:runtime-client|personalization-store|rag-lite)\.js"></script>', "", html)
            target.write_text(html, encoding="utf-8")
        else:
            shutil.copy2(source, target)
    for filename in ("LICENSE", "AUTHORS.md", "NOTICE.md", "USE_POLICY.md"):
        shutil.copy2(ROOT / filename, root / filename)
    (root / "README.md").write_text(
        "# VAS Client Form\n\nZIP을 새 폴더에 전체 압축 해제한 뒤 `index.html`을 여세요. 작성 결과는 JSON으로 저장되며 파일 내용은 업로드되지 않습니다. 초안은 복구를 위해 이 브라우저에 저장되며 화면에서 자동 저장을 끌 수 있고 JSON 저장 뒤 삭제됩니다.\n",
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
