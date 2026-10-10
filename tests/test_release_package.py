from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PACKAGE = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
CONFIG_TEXT = (ROOT / "src" / "vas-config.js").read_text(encoding="utf-8")
CONFIG_VERSION = re.search(r"version\s*:\s*['\"]([^'\"]+)", CONFIG_TEXT).group(1)
VERSION = PACKAGE["version"]
WINDOWS_NAME = f"VAS-{VERSION}-windows"
CLIENT_NAME = f"VAS-Client-Form-{VERSION}"
WINDOWS_ZIP = DIST / f"{WINDOWS_NAME}.zip"
CLIENT_ZIP = DIST / f"{CLIENT_NAME}.zip"

BLOCKED_PARTS = {
    ".git", ".github", ".pytest_cache", ".temp data", ".vas_backups",
    "__pycache__", "build", "coverage", "dist", "node_modules", "output",
    "playwright-report", "test-results", "tests", "workspace", ".vas-session",
}
BLOCKED_NAMES = {
    ".env", ".env.local", ".env.production", "credentials.json",
    "secrets.json", "service-account.json", "vas-session-store.json",
}
INTERNAL_DOCUMENT_NAMES = {
    "task.md", "codex_report.md", "current_context.md", "decisions.md",
    "questions_for_chatgpt.md", "handoff_full_context.md",
}
SECRET_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}

spec = importlib.util.spec_from_file_location("vas_build_release", ROOT / "scripts" / "build_release.py")
BUILD = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(BUILD)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def assert_safe_relative(test: unittest.TestCase, value: str) -> None:
    test.assertNotIn("\\", value, f"ZIP 경로는 POSIX 형식이어야 합니다: {value}")
    path = PurePosixPath(value)
    test.assertFalse(path.is_absolute(), f"절대 경로 금지: {value}")
    test.assertNotIn("..", path.parts, f"상위 경로 금지: {value}")
    lowered = {part.casefold() for part in path.parts}
    test.assertFalse(lowered & BLOCKED_PARTS, f"금지 경로 포함: {value}")
    name = path.name.casefold()
    test.assertNotIn(name, INTERNAL_DOCUMENT_NAMES, f"내부 상태 문서 포함: {value}")
    test.assertNotIn(name, BLOCKED_NAMES, f"시크릿 파일 포함: {value}")
    test.assertFalse(name.startswith(".env."), f"환경 파일 포함: {value}")
    test.assertNotIn(path.suffix.casefold(), SECRET_SUFFIXES, f"시크릿 키 포함: {value}")
    test.assertFalse(name.endswith((".pyc", ".pyo", ".log")), f"캐시/로그 포함: {value}")


def tree_fingerprints(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*")) if path.is_file()
    }


class ReleasePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not all(path.exists() for path in (
            WINDOWS_ZIP, CLIENT_ZIP, DIST / "release-manifest.json",
            DIST / "SHA256SUMS.txt", DIST / "pages" / "index.html",
        )):
            BUILD.build(DIST)

    def read_and_verify_zip(self, path: Path, root_name: str, target: str,
                            entrypoints: list[str]) -> tuple[dict, dict[str, bytes]]:
        with zipfile.ZipFile(path) as archive:
            self.assertIsNone(archive.testzip(), f"손상된 ZIP: {path.name}")
            names = [item.filename for item in archive.infolist() if not item.is_dir()]
            self.assertEqual(len(names), len(set(names)), "중복 ZIP 항목")
            self.assertEqual(len(names), len({name.casefold() for name in names}), "대소문자 충돌 ZIP 항목")
            for name in names:
                self.assertTrue(name.startswith(root_name + "/"), f"잘못된 ZIP 루트: {name}")
                assert_safe_relative(self, name[len(root_name) + 1:])
            manifest_name = f"{root_name}/manifest.json"
            self.assertIn(manifest_name, names)
            manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
            payload = {
                name[len(root_name) + 1:]: archive.read(name)
                for name in names if name != manifest_name
            }

        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["version"], VERSION)
        self.assertEqual(manifest["target"], target)
        self.assertEqual(manifest["entrypoints"], entrypoints)
        records = manifest["files"]
        record_paths = [item["path"] for item in records]
        self.assertEqual(len(record_paths), len(set(record_paths)), "manifest 중복 경로")
        self.assertEqual(set(record_paths), set(payload))
        for item in records:
            assert_safe_relative(self, item["path"])
            value = payload[item["path"]]
            self.assertEqual(item["size"], len(value), item["path"])
            self.assertEqual(item["sha256"], sha256_bytes(value), item["path"])
        for entrypoint in entrypoints:
            self.assertIn(entrypoint, payload)
        return manifest, payload

    def test_version_and_expected_release_files(self) -> None:
        self.assertEqual(VERSION, CONFIG_VERSION)
        self.assertFalse({name.casefold() for name in BUILD.ROOT_FILES} & INTERNAL_DOCUMENT_NAMES)
        self.assertFalse(
            {path.name.casefold() for path in ROOT.iterdir() if path.is_file()} & INTERNAL_DOCUMENT_NAMES,
            "내부 작업 문서는 별도 VAS-handoff 저장소에서 관리합니다.",
        )
        expected_zips = {WINDOWS_ZIP.name, CLIENT_ZIP.name}
        self.assertEqual({path.name for path in DIST.glob("*.zip")}, expected_zips)
        for path in (WINDOWS_ZIP, CLIENT_ZIP, DIST / "release-manifest.json",
                     DIST / "SHA256SUMS.txt"):
            self.assertTrue(path.is_file(), str(path))

    def test_windows_zip_manifest_entrypoint_and_safety(self) -> None:
        manifest, payload = self.read_and_verify_zip(
            WINDOWS_ZIP, WINDOWS_NAME, "windows", ["Run-VAS-System.bat"]
        )
        self.assertIn("src/vas-hub.html", payload)
        for resource in ("src/agent-resources.js", ".agents/agent-resources.json", ".agents/HANDOFF-WORKFLOW.md"):
            self.assertIn(resource, payload)
        self.assertIn(f"docs/releases/{VERSION}.md", payload)
        for host, suffix in ((".codex", ".toml"), (".claude", ".md")):
            for role in ("implementer", "designer", "reviewer"):
                self.assertIn(f"{host}/agents/vas_{role}{suffix}", payload)
        launcher_bytes = payload["Run-VAS-System.bat"]
        self.assertIn(b"\r\n", launcher_bytes)
        self.assertNotIn(b"\n", launcher_bytes.replace(b"\r\n", b""))
        launcher = launcher_bytes.decode("utf-8", errors="replace")
        launcher_paths = set(re.findall(r"(?:src|scripts)[\\/][A-Za-z0-9_.-]+", launcher, re.I))
        self.assertTrue(launcher_paths, "실행 BAT의 로컬 진입 대상이 없습니다.")
        for reference in launcher_paths:
            self.assertIn(reference.replace("\\", "/"), payload, f"실행 BAT 누락 대상: {reference}")
        recipient_readme = payload["README.md"].decode("utf-8")
        quick_start = payload["00-처음-사용하기.txt"].decode("utf-8")
        self.assertIn(f"VAS {VERSION} — 처음에는 이것만 하세요", quick_start)
        for marker in ("기존 디자인 유지", "부분 디자인 수정", "완료조건", "인계 자료 준비 완료", "전달 내용 다시 준비"):
            self.assertIn(marker, quick_start)
        self.assertIn("Run-VAS-System.bat", quick_start)
        self.assertIn("기존 프로그램 AI로 연결", quick_start)
        self.assertIn("VAS-AI-HANDOFF.json", quick_start)
        self.assertIn("폴더 위치 선택", quick_start)
        self.assertIn("전체 압축 해제", recipient_readme)
        self.assertIn("폴더 위치만 프롬프트에", recipient_readme)
        self.assertIn("프롬프트", recipient_readme)
        self.assertIn("저장은 선택입니다", recipient_readme)
        self.assertNotIn("npm.cmd", recipient_readme)
        release = json.loads((DIST / "release-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["commit"], release["commit"])

    def test_windows_chat_start_instructions_and_links_match_source(self) -> None:
        _, payload = self.read_and_verify_zip(
            WINDOWS_ZIP, WINDOWS_NAME, "windows", ["Run-VAS-System.bat"]
        )
        entrypoints = {"AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules", ".windsurfrules"}
        guides = {
            ".agents/ENTRYPOINT.md", ".agents/CONTEXT.md", ".agents/BOOTSTRAP.md",
            ".agents/DEVELOPMENT.md", ".agents/SESSION.md", ".agents/EXECUTION.md",
            "docs/CHAT-START.md", "docs/CHAT-STATE.md", "docs/CHAT-DESIGN.md", "docs/CHAT-EXECUTION.md",
        }
        session_scripts = {
            "scripts/vas-session.py", "scripts/vas_session.py", "scripts/vas_session_store.py",
            "scripts/vas_session_web.py", "scripts/VAS.Session.psm1", "scripts/VAS.Server.Session.ps1",
            "scripts/vas_session_execution.py",
            "src/chat-design-sync.js", "src/chat-design-sync.css",
        }
        for relative in sorted(entrypoints | guides | session_scripts):
            with self.subTest(packaged_instruction=relative):
                self.assertIn(relative, payload)
                self.assertEqual(payload[relative], (ROOT / relative).read_bytes(),
                                 f"배포 시작 지침이 원본과 다릅니다: {relative}")
        for relative in sorted(entrypoints):
            text = payload[relative].decode("utf-8")
            references = set(re.findall(r"\.agents/[A-Za-z0-9_.-]+\.md", text))
            self.assertTrue(references, f"시작 지침 연결이 없습니다: {relative}")
            for reference in references:
                self.assertIn(reference, payload, f"누락된 시작 지침: {relative}: {reference}")
        for relative in sorted(entrypoints | guides | {"README.md"}):
            text = payload[relative].decode("utf-8")
            for reference in re.findall(r"\[[^\]]+\]\(([^)\s]+)\)", text):
                parsed = urlsplit(reference)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                target = posixpath.normpath(str(PurePosixPath(relative).parent / unquote(parsed.path)))
                assert_safe_relative(self, target)
                self.assertIn(target, payload, f"배포 문서의 누락 링크: {relative}: {reference}")
        recipient_readme = payload["README.md"].decode("utf-8")
        for marker in ("첫 요청", "실제 작업 폴더", "VAS 2.9.0 대화형 작업 흐름", "Python 3.10", "공통 설정 저장", "다음 대화 이어가기",
                       "PC 전용 연결 정보", "공유 JSON에는 넣지 않습니다", "대화 설정에 저장", "편집 중 충돌은 덮어쓰지 않습니다",
                       "[대화로 시작하기](docs/CHAT-START.md)", "[설정 저장과 이어가기](docs/CHAT-STATE.md)",
                       "[대화와 디자인 연결](docs/CHAT-DESIGN.md)", "[저장 설정으로 구현·검증](docs/CHAT-EXECUTION.md)",
                       "prepare·assess 명령은 앱을 실행하지 않습니다"):
            self.assertIn(marker, recipient_readme)

    def test_extracted_windows_zip_can_prepare_and_assess_session(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vas-release-execution-") as temporary:
            base = Path(temporary)
            with zipfile.ZipFile(WINDOWS_ZIP) as archive:
                archive.extractall(base)
            vas = base / WINDOWS_NAME
            self.assertFalse((vas / "package.json").exists())
            app = base / "app"
            app.mkdir()
            (app / "sentinel.txt").write_text("unchanged", encoding="utf-8")
            before = tree_fingerprints(app)
            command = [sys.executable, "-B", str(vas / "scripts/vas-session.py"),
                       "--state-home", str(base / "state")]

            def invoke(arguments, payload=None):
                completed = subprocess.run(command + arguments, cwd=app, input=(
                    json.dumps(payload, ensure_ascii=False) if payload is not None else ""),
                    text=True, encoding="utf-8", capture_output=True, timeout=30,
                    env={**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"})
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                return json.loads(completed.stdout)

            settings = {"project": {"name": "CSV fixture", "sourceType": "existing"},
                        "task": {"request": "Fix CSV export", "designScope": {"mode": "preserve"},
                                 "completionCriteria": [{"description": "CSV round trip",
                                                         "method": "automatic", "required": True}]}}
            session = invoke(["create", "--target", str(app)], settings)["session"]
            selector = ["--session", session["sessionId"], "--expected-revision", "1"]
            prepared = invoke(["prepare"] + selector)
            self.assertEqual(prepared["status"], "prepared")
            handoff = prepared["handoff"]
            self.assertEqual(handoff["generatedBy"]["version"], VERSION)
            self.assertNotIn(str(app), json.dumps(handoff, ensure_ascii=False))
            result = {"format": "vas-ai-result", "schemaVersion": 1,
                      "resultId": "r_packaged_execution_001", "status": "complete",
                      "handoffId": handoff["workflow"]["handoffId"],
                      "handoffPayloadSha256": handoff["integrity"]["payloadSha256"],
                      "sourceType": "existing", "iteration": 1, "artifactVersion": "fixture-v1",
                      "tests": [], "evidence": [], "remaining": [],
                      "safety": {"absolutePathsExcluded": True, "secretsExcluded": True,
                                 "rawCommandOutputExcluded": True}}
            assessed = invoke(["assess"] + selector, result)
            self.assertEqual(assessed["reportedStatus"], "complete")
            self.assertEqual(assessed["assessment"]["status"], "needs-verification")
            self.assertEqual(tree_fingerprints(app), before)

    def test_standalone_form_is_self_contained(self) -> None:
        _, payload = self.read_and_verify_zip(
            CLIENT_ZIP, CLIENT_NAME, "client-form", ["index.html"]
        )
        html = payload["index.html"].decode("utf-8")
        self.assertIn('<body data-mode="standalone">', html)
        self.assertIn("agent-resources.js", payload)
        self.assertIn("design-reference.js", payload)
        self.assertIn('src="design-reference.js"', html)
        self.assertLess(html.index('src="agent-resources.js"'), html.index('src="design-taste-pack.js"'))
        self.assertNotIn('id="hubBackLink"', html)
        self.assertNotIn("personalization-store.js", html)
        self.assertNotIn("rag-lite.js", html)
        for unused in ("handoff-workflow.js", "handoff-context-review.js", "ai-result-import.js", "handoff-loop.css"):
            self.assertNotIn(unused, payload)
        self.assertNotIn('data-setup-settings>설정', html)
        self.assertIn("전체 압축 해제", payload["README.md"].decode("utf-8"))
        for legal in ("LICENSE", "AUTHORS.md", "NOTICE.md", "USE_POLICY.md"):
            self.assertIn(legal, payload)
        for reference in re.findall(r"(?:src|href)\s*=\s*['\"]([^'\"]+)", html, re.I):
            parsed = urlsplit(reference)
            if parsed.scheme == "data" or not parsed.path:
                continue
            self.assertFalse(parsed.scheme, f"외부 URL 금지: {reference}")
            local = unquote(parsed.path).lstrip("./")
            self.assertIn(local, payload, f"독립 신청서 누락 링크: {reference}")

    def test_release_manifest_and_checksums_match_artifacts(self) -> None:
        release = json.loads((DIST / "release-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(release["schemaVersion"], 1)
        self.assertEqual(release["version"], VERSION)
        artifacts = {item["name"]: item for item in release["artifacts"]}
        self.assertEqual(set(artifacts), {WINDOWS_ZIP.name, CLIENT_ZIP.name})
        for path in (WINDOWS_ZIP, CLIENT_ZIP):
            self.assertEqual(artifacts[path.name]["size"], path.stat().st_size)
            self.assertEqual(artifacts[path.name]["sha256"], sha256_file(path))
        checksum_lines = (DIST / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
        checksums = dict(line.split("  ", 1)[::-1] for line in checksum_lines)
        self.assertEqual(checksums, {path.name: sha256_file(path) for path in (WINDOWS_ZIP, CLIENT_ZIP)})

    def test_pages_contains_only_safe_local_files(self) -> None:
        pages = DIST / "pages"
        files = [path for path in pages.rglob("*") if path.is_file()]
        relatives = {path.relative_to(pages).as_posix() for path in files}
        self.assertIn("index.html", relatives)
        self.assertIn(".nojekyll", relatives)
        self.assertIn("src/vas-hub.html", relatives)
        self.assertIn(f"docs/releases/{VERSION}.md", relatives)
        for path in pages.rglob("*"):
            self.assertFalse(path.is_symlink(), f"Pages 링크 금지: {path}")
            assert_safe_relative(self, path.relative_to(pages).as_posix())
        for html_path in (path for path in files if path.suffix.casefold() == ".html"):
            html = html_path.read_text(encoding="utf-8")
            for reference in re.findall(r"(?:src|href)\s*=\s*['\"]([^'\"]+)", html, re.I):
                parsed = urlsplit(reference)
                if parsed.scheme == "data" or not parsed.path:
                    continue
                self.assertFalse(parsed.scheme or parsed.netloc, f"Pages 외부 URL 금지: {reference}")
                target = (html_path.parent / unquote(parsed.path)).resolve()
                self.assertTrue(target.is_relative_to(pages.resolve()), f"Pages 경로 이탈: {reference}")
                self.assertTrue(target.exists(), f"Pages 누락 링크: {html_path}: {reference}")

        # Exercise copy filtering and fail-closed ZIP checks with actual injected files.
        # Expected names are independent of the builder's denylist.
        with tempfile.TemporaryDirectory(prefix="vas-internal-document-test-") as temporary:
            source = Path(temporary) / "source"
            target = Path(temporary) / "filtered"
            preserved = {
                f"docs/releases/{VERSION}.md",
                ".agents/HANDOFF-WORKFLOW.md", ".agents/skills/reviewer/SKILL.md",
                ".codex/agents/vas_reviewer.toml",
            }
            blocked = {
                f"docs/{name}" for name in INTERNAL_DOCUMENT_NAMES
            } | {
                f"docs/nested/{name.upper()}" for name in INTERNAL_DOCUMENT_NAMES
            }
            for relative in preserved | blocked:
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")
            BUILD.copy_tree(source, target)
            self.assertEqual(set(tree_fingerprints(target)), preserved)
            for relative in sorted(blocked):
                with self.subTest(internal_document=relative):
                    self.assertFalse(BUILD.allowed(Path(relative)))
                    archive_path = Path(temporary) / "injected.zip"
                    with zipfile.ZipFile(archive_path, "w") as archive:
                        archive.writestr(f"VAS-fixture/{relative}", "fixture\n")
                    with self.assertRaisesRegex(RuntimeError, "내부 상태 문서 포함"):
                        BUILD.verify_zip(archive_path)
            for relative in sorted(preserved):
                with self.subTest(runtime_or_release_document=relative):
                    self.assertTrue(BUILD.allowed(Path(relative)))

    def test_build_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vas-release-test-") as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            BUILD.build(first)
            BUILD.build(second)
            self.assertEqual(tree_fingerprints(first), tree_fingerprints(second))


class SessionPrivacyBoundaryTests(unittest.TestCase):
    def test_copied_session_state_is_excluded_from_release_backup_and_project_scan(self) -> None:
        scripts = str(ROOT / "scripts")
        sys.path.insert(0, scripts)
        self.addCleanup(sys.path.remove, scripts)
        from vas_agent_handoff import build_preview
        from vas_project_import import MigrationManager
        from vas_project_knowledge import _candidate_files
        backup_spec = importlib.util.spec_from_file_location("vas_backup", ROOT / "scripts" / "vas-backup.py")
        backup = importlib.util.module_from_spec(backup_spec)
        assert backup_spec.loader is not None
        backup_spec.loader.exec_module(backup)
        with tempfile.TemporaryDirectory(prefix="vas-session-boundary-") as temporary:
            base = Path(temporary)
            source = base / "source"
            preserved = {"README.md", "src/app.js"}
            blocked = {
                ".vas-session/sessions.json", "docs/.VAS-SESSION/private.json",
                "vas-session-store.json", "docs/VAS-SESSION-STORE.JSON",
            }
            for relative in preserved | blocked:
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("private-session-canary" if relative in blocked else "safe fixture", encoding="utf-8")
            before = tree_fingerprints(source)
            BUILD.copy_tree(source, base / "release")
            shutil.copytree(source, base / "backup", ignore=backup.ignore)
            self.assertEqual(set(tree_fingerprints(base / "release")), preserved)
            self.assertEqual(set(tree_fingerprints(base / "backup")), preserved)
            self.assertEqual({item[0] for item in _candidate_files(source)}, preserved)
            scanned, _ = MigrationManager(base / "vas")._walk(source)
            self.assertEqual({item[0] for item in scanned}, preserved)
            preview = build_preview({"source": str(source), "task": {"request": "review app"}})
            self.assertEqual({item["path"] for item in preview["candidateFiles"]}, preserved)
            self.assertEqual(tree_fingerprints(source), before, "Privacy scans changed source files")
            for relative in sorted(blocked):
                with self.subTest(copied_session_state=relative):
                    self.assertFalse(BUILD.allowed(Path(relative)))
                    archive_path = base / "injected.zip"
                    with zipfile.ZipFile(archive_path, "w") as archive:
                        archive.writestr(f"VAS-fixture/{relative}", "private-session-canary")
                    with self.assertRaisesRegex(RuntimeError, "금지 경로 포함|비밀 파일 포함"):
                        BUILD.verify_zip(archive_path)


class WorkflowContractTests(unittest.TestCase):
    def test_workflows_cover_main_pages_release_without_stress(self) -> None:
        workflows = ROOT / ".github" / "workflows"
        ci = (workflows / "ci.yml").read_text(encoding="utf-8")
        pages = (workflows / "pages.yml").read_text(encoding="utf-8")
        release = (workflows / "release.yml").read_text(encoding="utf-8")
        combined = "\n".join((ci, pages, release))
        self.assertIn("branches: [main]", ci)
        self.assertIn("branches: [main]", pages)
        for command in ("npm run test:python", "npm run test:browser", "npm run test:package"):
            self.assertIn(command, ci)
        self.assertIn("runs-on: windows-latest", ci)
        self.assertIn("python tests/test_windows_runtime.py", ci)
        self.assertIn("path: dist/pages", pages)
        self.assertIn("include-hidden-files: true", pages)
        self.assertIn('tags:\n      - "v*"', release)
        self.assertRegex(release, r'(?m)^  release:\n    needs: windows\n')
        self.assertIn('runs-on: windows-latest', release)
        self.assertIn('tests/integrated-runtime.spec.js', release)
        self.assertIn('python tests/test_release_runtime_flow.py', release)
        for filename in ("VAS-${version}-windows.zip", "VAS-Client-Form-${version}.zip",
                         "release-manifest.json", "SHA256SUMS.txt"):
            self.assertIn(filename, release)
        self.assertNotIn("run_10x", combined)
        self.assertNotIn("test:release", combined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
