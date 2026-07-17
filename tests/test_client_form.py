"""내부 신청서와 독립 신청서 빌드 계약을 검사합니다."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class ClientFormTests(unittest.TestCase):
    def read(self, name: str) -> str:
        return (SRC / name).read_text(encoding="utf-8")

    def test_required_files_exist(self):
        names = [
            "client-application.html", "client-form.js", "client-draft.js",
            "client-export.js", "agent-handoff-web.js", "client-application-init.js",
            "agent-contract.js", "handoff-workflow.js", "handoff-context-review.js",
            "ai-result-import.js", "handoff-loop.css",
        ]
        self.assertTrue(all((SRC / name).is_file() for name in names))

    def test_internal_form_links_back_to_hub(self):
        html = self.read("client-application.html")
        self.assertIn('id="hubBackLink"', html)
        self.assertIn('href="vas-hub.html"', html)

    def test_scripts_are_local_and_ordered(self):
        html = self.read("client-application.html")
        scripts = re.findall(r'<script src="([^"]+)"', html)
        self.assertTrue(all(not item.startswith(("http://", "https://")) for item in scripts))
        self.assertLess(scripts.index("storage-utils.js"), scripts.index("theme-state.js"))
        self.assertLess(scripts.index("client-form.js"), scripts.index("client-draft.js"))
        self.assertLess(scripts.index("agent-contract.js"), scripts.index("agent-handoff-web.js"))
        self.assertLess(scripts.index("handoff-workflow.js"), scripts.index("ai-result-import.js"))

    def test_form_navigation_and_validation_exist(self):
        code = self.read("client-form.js")
        for function in ["changeStep", "showDone", "goBackFromDone", "clearForm", "validateCurrentStep"]:
            self.assertIn(f"function {function}", code)

    def test_file_name_rendering_uses_text_nodes(self):
        code = self.read("client-form.js")
        self.assertNotIn("chip.innerHTML", code)
        self.assertIn("document.createTextNode", code)

    def test_draft_excludes_file_fields(self):
        code = self.read("client-draft.js")
        self.assertIn("element.type === 'file'", code)
        self.assertIn("element.name === 'attached_files'", code)
        self.assertIn("VASStorage.remove", code)

    def test_export_collects_metadata_without_file_content(self):
        code = self.read("client-export.js")
        self.assertIn("collectApplicationData", code)
        self.assertIn("attached_files", code)
        self.assertNotIn("readAsDataURL", code)
        self.assertNotIn("arrayBuffer", code)

    def test_common_json_contract_is_used(self):
        code = self.read("agent-handoff-web.js")
        self.assertIn("buildNew", code)
        self.assertIn("VAS-AI-HANDOFF.json", code)
        self.assertIn("baseDocument(projectName, requirements.problem, context, 'new', options)", code)
        self.assertIn("baseDocument(projectName, task, context, 'existing', options)", code)
        self.assertIn("projectStructureInferred: false", code)
        self.assertIn("RBG(Read Before Generate)", code)
        self.assertIn("VAS-AI-RESULT.json", code)
        self.assertIn("schemaVersion: 3", code)

    def test_standalone_builder_removes_internal_modules(self):
        code = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for name in ["runtime-client", "personalization-store", "rag-lite"]:
            self.assertIn(name, code)
        self.assertIn('data-mode="standalone"', code)
        for name in ["agent-contract.js", "handoff-workflow.js", "ai-result-import.js", "handoff-loop.css"]:
            self.assertIn(name, code)

    def test_source_form_is_under_line_limit(self):
        self.assertLessEqual(len(self.read("client-application.html").splitlines()), 500)


if __name__ == "__main__":
    unittest.main(verbosity=2)
