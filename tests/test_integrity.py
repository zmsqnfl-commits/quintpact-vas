"""VAS 2.6.3 단일 무결성 검사: 핵심 시스템 경계를 한 번 확인합니다."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def local_reference(owner: Path, value: str) -> Path | None:
    clean = value.split("?", 1)[0].split("#", 1)[0]
    if not clean or clean.startswith(("#", "data:", "mailto:", "javascript:", "http://", "https://", "/")):
        return None
    return owner.parent / clean


html_files = sorted(SRC.glob("*.html"))
css_files = sorted(SRC.glob("*.css"))
js_files = sorted(SRC.glob("*.js"))
package = json.loads(text(ROOT / "package.json"))
config = text(SRC / "vas-config.js")

check("01 package version", package.get("version") == "2.6.3")
check("02 runtime version", "version: '2.6.3'" in config or 'version: "2.6.3"' in config)
check("03 public entrypoints", all((ROOT / item).exists() for item in [
    "Run-VAS-System.bat", "src/vas-hub.html", "src/client-application.html",
]))
check("04 connected screens", all((SRC / item).exists() for item in [
    "project-import.html", "design-controller.html", "setup-tools.js", "setup-design.js",
]))

missing_scripts: list[str] = []
missing_styles: list[str] = []
broken_links: list[str] = []
for html in html_files:
    content = text(html)
    for value in re.findall(r'<script[^>]+src=["\']([^"\']+)', content, re.I):
        target = local_reference(html, value)
        if target and not target.exists():
            missing_scripts.append(f"{html.name}:{value}")
    for value in re.findall(r'<link[^>]+href=["\']([^"\']+)', content, re.I):
        target = local_reference(html, value)
        if target and not target.exists():
            missing_styles.append(f"{html.name}:{value}")
    for value in re.findall(r'<a[^>]+href=["\']([^"\']+)', content, re.I):
        target = local_reference(html, value)
        if target and not target.exists():
            broken_links.append(f"{html.name}:{value}")
check("05 HTML script references", not missing_scripts, ", ".join(missing_scripts))
check("06 HTML stylesheet references", not missing_styles, ", ".join(missing_styles))
check("07 local navigation links", not broken_links, ", ".join(broken_links))

source_text = "\n".join(text(path) for path in html_files + css_files + js_files)
web_urls = [url for url in re.findall(r'https?://[^\s"\'<>]+', source_text) if "w3.org/2000/svg" not in url]
check("08 no remote runtime URL", not web_urls, ", ".join(web_urls[:5]))
check("09 no remote font or import", not re.search(r"fonts\.googleapis|fonts\.gstatic|@import\s+url\(\s*['\"]?https?", source_text, re.I))

storage = text(SRC / "storage-utils.js")
check("10 resilient storage API", all(token in storage for token in ["readJson", "writeJson", "readText", "writeText", "normalizeFontFamily", "normalizeTheme"]))
theme = text(SRC / "theme-state.js")
check("11 legacy theme compatibility", all(key in source_text for key in [
    "vasFavorites", "vasThemeHistory", "vasThemeTokens", "vasCurrentPreset",
]))
personalization = text(SRC / "personalization-store.js")
check("12 consent controlled memory", all(token in personalization for token in ["consent", "record", "delete", "clear", "export", "pause"]))
rag = text(SRC / "rag-lite.js")
check("13 local RAG contract", all(token in rag for token in ["retrieve", "recommend", "augmentPrompt"]))
check("14 generated knowledge index", (SRC / "knowledge-index.js").exists())

runtime_pages = ["project-import.html", "knowledge-search.html", "memory-center.html"]
hub = text(SRC / "vas-hub.html")
check("15 setup and compatibility wiring", all("runtime-client.js" in text(SRC / page) for page in runtime_pages)
      and "runtime-client.js" not in hub and hub.count('class="start-card') == 2)
check("16 migration engine files", all((ROOT / item).exists() for item in [
    "scripts/vas_project_import.py", "scripts/vas-project-import.py", "scripts/VAS.Migration.psm1",
]))
check("17 runtime server files", all((ROOT / item).exists() for item in [
    "scripts/Start-VAS.ps1", "scripts/VAS.Server.psm1", "scripts/VAS.Memory.psm1",
]))
check("18 required documentation", all((ROOT / item).exists() for item in [
    "docs/index.md", "docs/OPERATIONS.md", "docs/MIGRATION.md", "docs/import-existing-project.md", "docs/HANDOFF.md",
]))
check("19 GitHub workflows", all((ROOT / ".github" / "workflows" / item).exists() for item in ["ci.yml", "pages.yml", "release.yml"]))

scripts = package.get("scripts", {})
check("20 package command roles", scripts.get("test:python") and scripts.get("test:browser") and scripts.get("test:release") and "run_10x_stress.py" in scripts["test:release"])
check("21 generated final mirror removed", not (ROOT / "final").exists())

oversized: list[str] = []
for base in [SRC, ROOT / "scripts", ROOT / "tests"]:
    for path in base.rglob("*"):
        if not path.is_file() or any(part in {"node_modules", "__pycache__"} for part in path.parts):
            continue
        if path.suffix.lower() not in {".html", ".css", ".js", ".py", ".ps1", ".psm1", ".md"}:
            continue
        count = len(text(path).splitlines())
        if count > 500:
            oversized.append(f"{path.relative_to(ROOT)}:{count}")
check("22 500 line limit", not oversized, ", ".join(oversized))

syntax_errors: list[str] = []
for path in sorted((ROOT / "scripts").glob("*.py")) + sorted((ROOT / "tests").glob("*.py")):
    try:
        ast.parse(text(path), filename=str(path))
    except SyntaxError as error:
        syntax_errors.append(f"{path.name}:{error.lineno}")
html_ok = all("<!doctype html" in text(path).lower() and "</html>" in text(path).lower() for path in html_files)
check("23 Python and HTML syntax", not syntax_errors and html_ok, ", ".join(syntax_errors))

project_context = text(SRC / "project-context.js")
project_module = text(ROOT / "scripts" / "VAS.Projects.psm1")
server = text(ROOT / "scripts" / "VAS.Server.psm1")
check("24 project context contract", all(token in project_context for token in ["projectId", "sourceType", "goal", "stage", "vasProjectContext"]))
check("25 project scoped RAG", "projectId=" in personalization and "Where-Object { $_.projectId -eq $projectId }" in server)
check("26 safe handoff allowlist", all(token in project_module for token in ["project.json", "requirements.json", "design-tokens.json", "rag-context.json", "SHA256SUMS.txt"]))
check("27 Windows PowerShell encoding", all(text(ROOT / item) for item in ["scripts/VAS.Server.psm1", "scripts/VAS.Projects.psm1"]) and all((ROOT / item).read_bytes().startswith(b"\xef\xbb\xbf") for item in ["scripts/VAS.Server.psm1", "scripts/VAS.Projects.psm1"]))

failed = [(name, detail) for name, passed, detail in results if not passed]
for name, passed, detail in results:
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f" - {detail}" if detail and not passed else ""))
print(f"TOTAL: {len(results)} | PASS: {len(results) - len(failed)} | FAIL: {len(failed)}")
raise SystemExit(1 if failed else 0)
