from __future__ import annotations

import hashlib
import importlib.util
import json
import re
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
    "playwright-report", "test-results", "tests", "workspace",
}
BLOCKED_NAMES = {
    ".env", ".env.local", ".env.production", "credentials.json",
    "secrets.json", "service-account.json",
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
        self.assertIn("Run-VAS-System.bat", quick_start)
        self.assertIn("기존 프로그램 AI로 연결", quick_start)
        self.assertIn("workspace\\projects", quick_start)
        self.assertIn("전체 압축 해제", recipient_readme)
        self.assertIn("Python 3.10", recipient_readme)
        self.assertNotIn("npm.cmd", recipient_readme)
        release = json.loads((DIST / "release-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["commit"], release["commit"])

    def test_standalone_form_is_self_contained(self) -> None:
        _, payload = self.read_and_verify_zip(
            CLIENT_ZIP, CLIENT_NAME, "client-form", ["index.html"]
        )
        html = payload["index.html"].decode("utf-8")
        self.assertIn('<body data-mode="standalone">', html)
        self.assertNotIn('id="hubBackLink"', html)
        self.assertNotIn("personalization-store.js", html)
        self.assertNotIn("rag-lite.js", html)
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

    def test_build_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vas-release-test-") as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            BUILD.build(first)
            BUILD.build(second)
            self.assertEqual(tree_fingerprints(first), tree_fingerprints(second))


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
        for filename in ("VAS-${version}-windows.zip", "VAS-Client-Form-${version}.zip",
                         "release-manifest.json", "SHA256SUMS.txt"):
            self.assertIn(filename, release)
        self.assertNotIn("run_10x", combined)
        self.assertNotIn("test:release", combined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
