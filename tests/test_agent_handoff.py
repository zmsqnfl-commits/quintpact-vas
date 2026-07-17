"""Safety and compatibility tests for VAS 2.6.3 AI handoff packages."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from vas_agent_handoff import (  # noqa: E402
    SourceChangedError,
    UnsafeSelectionError,
    build_preview,
    export_package,
)


class AgentHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.source = self.base / "기존 프로그램"
        (self.source / "src").mkdir(parents=True)
        (self.source / "tests").mkdir()
        (self.source / ".git").mkdir()
        (self.source / "node_modules").mkdir()
        (self.source / "src" / "main.ts").write_text("export const answer = 42;\n", encoding="utf-8")
        (self.source / "tests" / "main.test.ts").write_text("// safe test\n", encoding="utf-8")
        (self.source / "README.md").write_text("# 한글 프로젝트\n", encoding="utf-8")
        (self.source / "package.json").write_text(json.dumps({
            "scripts": {"test": "vitest", "build": "vite build"},
            "dependencies": {"react": "^19.0.0"},
        }), encoding="utf-8")
        (self.source / ".env").write_text("API_KEY=never-export-this\n", encoding="utf-8")
        (self.source / ".git" / "config").write_text("private remote\n", encoding="utf-8")
        (self.source / "node_modules" / "large.js").write_text("ignored\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def request(self, **extra: object) -> dict[str, object]:
        request: dict[str, object] = {
            "source": str(self.source),
            "projectName": "기존 프로그램",
            "sourceType": "existing",
            "task": {"request": "C:\\Users\\person\\secret 프로젝트를 고쳐 주세요. contact@example.com 010-1234-5678"},
            "context": {
                "rag": {"included": True, "items": [{"title": f"항목 {index}", "excerpt": "x" * 1200} for index in range(8)]},
                "preferences": {"included": False, "items": []},
            },
        }
        request.update(extra)
        return request

    def test_preview_detects_stack_without_git_secret_or_absolute_path(self) -> None:
        result = build_preview(self.request())
        document = result["document"]
        encoded = json.dumps(document, ensure_ascii=False)
        paths = [item["path"] for item in document["inventory"]["files"]]
        self.assertIn("JavaScript/TypeScript", document["analysis"]["stacks"])
        self.assertIn("React", [name.title() for name in document["analysis"]["frameworks"]])
        self.assertFalse(any(path.startswith(".git/") or path.startswith("node_modules/") for path in paths))
        self.assertNotIn(".env", paths)
        self.assertNotIn(str(self.source), encoded)
        self.assertNotIn("never-export-this", encoded)
        self.assertNotIn("contact@example.com", encoded)
        self.assertNotIn("010-1234-5678", encoded)
        self.assertIn("[absolute-path]", document["task"]["request"])
        self.assertEqual(len(document["context"]["rag"]["items"]), 5)
        self.assertLessEqual(len(document["context"]["rag"]["items"][0]["excerpt"]), 800)
        self.assertTrue(document["security"]["sourceUnchanged"])
        self.assertFalse(document["security"]["projectCodeExecuted"])

    def test_malformed_manifest_is_warning_free_and_analysis_continues(self) -> None:
        (self.source / "package.json").write_text("{broken", encoding="utf-8")
        result = build_preview(self.request())
        self.assertIn("package.json", result["document"]["analysis"]["manifests"])
        self.assertEqual(result["document"]["analysis"]["dependencies"], [])

    def test_cp949_reviewed_zip_is_deterministic_and_verifiable(self) -> None:
        legacy = self.source / "src" / "legacy.txt"
        legacy.write_bytes("한글 레거시 문서\n둘째 줄\n".encode("cp949"))
        preview = build_preview(self.request())
        output_a = self.base / "a.zip"
        output_b = self.base / "b.zip"
        common = self.request(mode="reviewed-source", format="reviewed-zip", snapshotId=preview["snapshotId"], approvedFiles=["src/legacy.txt"])
        export_package(dict(common, output=str(output_a)))
        export_package(dict(common, output=str(output_b)))
        self.assertEqual(output_a.read_bytes(), output_b.read_bytes())
        with zipfile.ZipFile(output_a) as archive:
            names = set(archive.namelist())
            self.assertEqual(names, {"START-HERE.md", "PROMPT.md", "VAS-AI-HANDOFF.json", "manifest.json", "excerpts/0001.txt", "SHA256SUMS.txt"})
            self.assertIn("한글 레거시", archive.read("excerpts/0001.txt").decode("utf-8"))
            for line in archive.read("SHA256SUMS.txt").decode("utf-8").splitlines():
                digest, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)

    def test_source_change_after_preview_is_rejected(self) -> None:
        preview = build_preview(self.request())
        (self.source / "src" / "main.ts").write_text("export const changed = true;\n", encoding="utf-8")
        with self.assertRaises(SourceChangedError):
            export_package(self.request(output=str(self.base / "handoff.json"), format="json", snapshotId=preview["snapshotId"]))

    def test_selected_source_with_secret_content_is_rejected(self) -> None:
        secret = self.source / "src" / "unsafe.txt"
        secret.write_text("api_key=sk-1234567890abcdefghijklmnop\n", encoding="utf-8")
        preview = build_preview(self.request())
        with self.assertRaises(UnsafeSelectionError):
            export_package(self.request(output=str(self.base / "unsafe.zip"), mode="reviewed-source", format="reviewed-zip", snapshotId=preview["snapshotId"], approvedFiles=["src/unsafe.txt"]))

    def test_json_export_has_common_name_and_no_source_contents(self) -> None:
        preview = build_preview(self.request())
        output = self.base / "handoff.json"
        result = export_package(self.request(output=str(output), format="json", snapshotId=preview["snapshotId"]))
        document = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(result["fileName"].endswith("-VAS-AI-HANDOFF.json"))
        self.assertEqual(document["format"], "vas-ai-handoff")
        self.assertNotIn("export const answer", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
