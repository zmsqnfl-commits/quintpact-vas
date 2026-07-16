"""End-to-end smoke test for the extracted Windows release."""

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request
import zipfile
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
ARCHIVE = BASE / "dist" / "VAS-2.6.1-windows.zip"
POWERSHELL = shutil.which("powershell.exe")


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class RuntimeClient:
    def __init__(self, runtime):
        self.base = runtime["baseUrl"]
        self.token = runtime["token"]

    def request(self, path, method="GET", data=None):
        body = None if data is None else json.dumps(data).encode("utf-8")
        headers = {"X-VAS-Token": self.token, "Origin": self.base}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode("utf-8"))


def start_release(root, state):
    command = [
        POWERSHELL, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(root / "scripts" / "Start-VAS.ps1"), "-NoBrowser", "-RootPath", str(root),
        "-StateRoot", str(state), "-Port", str(free_port()), "-IdleTimeoutSeconds", "120",
    ]
    result = subprocess.run(command, capture_output=True, timeout=30)
    if result.returncode:
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        raise AssertionError(f"release launcher failed: {output}")
    deadline = time.time() + 10
    while time.time() < deadline:
        for path in state.glob("runtime-2.6.1-*.json"):
            try:
                return json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                pass
        time.sleep(0.1)
    raise AssertionError("release runtime state was not created")


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "Windows PowerShell is required")
class ReleaseRuntimeFlowTests(unittest.TestCase):
    def test_extract_import_index_and_rollback_in_korean_space_path(self):
        self.assertTrue(ARCHIVE.is_file(), "run the release builder first")
        with tempfile.TemporaryDirectory(prefix="vas-release-flow-") as temporary:
            base = Path(temporary) / "한글 경로 with spaces"
            base.mkdir()
            with zipfile.ZipFile(ARCHIVE) as bundle:
                bundle.extractall(base)
            root = base / "VAS-2.6.1-windows"
            state = base / "상태 저장소"
            source = base / "기존 결제 프로그램"
            source.mkdir()
            (source / "README.md").write_text(
                "# 결제 시스템\n기존 결제 흐름과 업그레이드 규칙\n", encoding="utf-8"
            )
            (source / "app.js").write_text(
                "function payOrder() { return 'payment-ready'; }\n", encoding="utf-8"
            )
            (source / ".env").write_text("API_KEY=release-secret-value\n", encoding="utf-8")
            runtime = start_release(root, state)
            client = RuntimeClient(runtime)
            try:
                status, selected = client.request(
                    "/api/folder/select", "POST", {"path": str(source)}
                )
                self.assertEqual(status, 200)
                selection_id = selected["selection"]["selectionId"]

                status, report = client.request(
                    "/api/migrations/analyze", "POST", {"selectionId": selection_id}
                )
                self.assertEqual(status, 200)
                self.assertGreaterEqual(report["fileCount"], 2)

                status, imported = client.request(
                    "/api/migrations/import", "POST", {
                        "selectionId": selection_id, "projectName": "가져온 프로젝트",
                        "createIndex": True, "goal": "upgrade",
                    },
                )
                self.assertEqual(status, 201)
                self.assertEqual(imported["status"], "ready")
                job_id = imported["jobId"]
                project_id = imported["project"]["projectId"]

                _, projects = client.request("/api/projects")
                project = next(item for item in projects["projects"] if item["projectId"] == job_id)
                self.assertEqual(project["goal"], "upgrade")
                self.assertTrue(project["indexEnabled"])

                _, knowledge = client.request(f"/api/knowledge/projects?projectId={project_id}")
                serialized = json.dumps(knowledge, ensure_ascii=False)
                self.assertIn("결제", serialized)
                self.assertIn("payOrder", serialized)
                self.assertNotIn("release-secret-value", serialized)

                status, rolled_back = client.request(
                    "/api/migrations/rollback", "POST", {"jobId": job_id}
                )
                self.assertEqual(status, 200)
                self.assertEqual(rolled_back["status"], "rolled_back")
                self.assertTrue(source.is_dir())
                self.assertFalse((root / "workspace" / "projects" / "가져온 프로젝트").exists())
                index_path = root / "workspace" / ".vas" / "project-knowledge.json"
                after = json.loads(index_path.read_text(encoding="utf-8"))
                self.assertNotIn("payOrder", json.dumps(after, ensure_ascii=False))
            finally:
                try:
                    client.request("/api/shutdown", "POST", {})
                except Exception:
                    pass
                time.sleep(0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
