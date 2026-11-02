"""End-to-end smoke test for the extracted Windows release."""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from runtime_install import install_runtime


BASE = Path(__file__).resolve().parents[1]
ARCHIVE = BASE / "dist" / "VAS-2.13.2-windows.zip"
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
            payload = response.read()
            if "json" in response.headers.get("Content-Type", ""):
                payload = json.loads(payload.decode("utf-8"))
            return response.status, payload


def start_release(root, state, *, launcher=None):
    command = [
        POWERSHELL, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(launcher or root / "scripts" / "Start-VAS.ps1"), "-NoBrowser", "-RootPath", str(root),
        "-StateRoot", str(state), "-Port", str(free_port()), "-IdleTimeoutSeconds", "120",
    ]
    result = subprocess.run(command, capture_output=True, timeout=30, env={
        **os.environ, "LOCALAPPDATA": str(state.parent / "local-data"), "VAS_PYTHON": sys.executable,
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1",
    })
    if result.returncode:
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        raise AssertionError(f"release launcher failed: {output}")
    deadline = time.time() + 10
    while time.time() < deadline:
        for path in state.glob("runtime-2.13.2-*.json"):
            try:
                return json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                pass
        time.sleep(0.1)
    raise AssertionError("release runtime state was not created")


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "Windows PowerShell is required")
class ReleaseRuntimeFlowTests(unittest.TestCase):
    def test_checkout_launcher_serves_the_same_project_screen_as_the_archive(self):
        with tempfile.TemporaryDirectory(prefix="vas-source-runtime-") as temporary:
            runtime = start_release(BASE, Path(temporary) / "private-state")
            client = RuntimeClient(runtime)
            try:
                self.assertTrue(Path(runtime["rootPath"]).samefile(BASE))
                self.assertEqual(client.request("/api/status")[1]["layout"], "project")
                self.assertEqual(client.request("/src/vas-hub.html")[1], (BASE / "ui/vas-hub.html").read_bytes())
                self.assertEqual(client.request("/api/chat/sessions")[0], 200)
            finally:
                client.request("/api/shutdown", "POST", {})
                time.sleep(.5)

    def test_renamed_project_serves_only_engine_and_refuses_legacy_workspace(self):
        self.assertTrue(ARCHIVE.is_file(), "run the release builder first")
        with tempfile.TemporaryDirectory(prefix="vas-release-flow-") as temporary:
            base = Path(temporary)
            with zipfile.ZipFile(ARCHIVE) as bundle:
                bundle.extractall(base)
            project = base / "우리 앱 & 재고"
            (base / "VAS-2.13.2-windows").rename(project)
            self.assertFalse((project / ".vas").exists())
            state = base / "pc-state"
            sentinel = project / "src" / "inventory.txt"
            sentinel.write_bytes(b"private-sample-app-data")
            (project / "src/vas-hub.html").write_bytes(b"private app homepage")
            runtime = start_release(project, state)
            client = RuntimeClient(runtime)
            try:
                # Windows runners may expose TEMP through its equivalent 8.3 alias.
                self.assertTrue(Path(runtime["rootPath"]).samefile(project))
                hub = (project / "ui/vas-hub.html").read_bytes()
                self.assertEqual(client.request("/")[1], hub)
                self.assertEqual(client.request("/src/vas-hub.html")[1], hub)
                self.assertEqual(client.request("/api/files/read?scope=src&path=vas-hub.html")[1]["content"], hub.decode("utf-8-sig"))
                for url in ["/src/inventory.txt", "/api/files/read?scope=src&path=inventory.txt",
                            "/scripts/Start-VAS.ps1", "/src/..%2fsrc%2finventory.txt"]:
                    with self.subTest(url=url), self.assertRaises(urllib.error.HTTPError) as refused:
                        client.request(url)
                    self.assertEqual(refused.exception.code, 404)
                    refused.exception.close()
                _, info = client.request("/api/status")
                self.assertEqual(info["layout"], "project")
                self.assertEqual(info["capabilities"]["projectImport"],
                                 {"available": False, "reason": "project-root-layout"})
                self.assertEqual(client.request("/api/projects")[1]["projects"], [])
                self.assertEqual(client.request("/api/chat/sessions")[0], 200)
                for url, method in [("/api/projects/create", "POST"), ("/api/migrations/select", "POST"),
                                    ("/api/migrations/import", "POST"), ("/api/knowledge/projects", "GET"),
                                    ("/api/handoffs/preview", "POST")]:
                    with self.subTest(url=url), self.assertRaises(urllib.error.HTTPError) as refused:
                        client.request(url, method, {"name": "unwanted", "path": str(project)} if method == "POST" else None)
                    self.assertEqual(refused.exception.code, 409)
                    with refused.exception as response:
                        self.assertEqual(json.load(response)["code"], "project_root_layout")
                self.assertEqual(sentinel.read_bytes(), b"private-sample-app-data")
                self.assertFalse((project / "workspace").exists())
            finally:
                client.request("/api/shutdown", "POST", {})
                time.sleep(0.5)
            # Never bind HTTP to app/src or create private state inside the app.
            for wrong_root, wrong_state, reason in [
                (project / "src", base / "wrong-root-state", b"Check the extracted project folder"),
                (project, project / "state", b"Private local state is unavailable"),
            ]:
                failed = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                         str(project / "scripts/Start-VAS.ps1"), "-Server", "-NoBrowser",
                                         "-RootPath", str(wrong_root), "-StateRoot", str(wrong_state),
                                         "-Port", str(free_port()), "-IdleTimeoutSeconds", "2"],
                                        capture_output=True, timeout=8)
                self.assertNotEqual(failed.returncode, 0)
                self.assertIn(reason, failed.stderr)
                self.assertFalse(wrong_state.exists())
            # Damaged metadata cannot turn the app's same-named src/ page into VAS UI.
            (project / "project-layout.json").unlink()
            with self.assertRaisesRegex(AssertionError, "Check the extracted project folder"):
                start_release(project, base / "invalid-layout-state")
            self.assertFalse((base / "invalid-layout-state").exists())

    def test_other_host_progress_is_readable_without_a_local_session(self):
        with tempfile.TemporaryDirectory(prefix="vas-progress-runtime-") as temporary:
            base = Path(temporary)
            with zipfile.ZipFile(ARCHIVE) as bundle:
                bundle.extractall(base)
            project = base / "VAS-2.13.2-windows"
            cli = [sys.executable, "-B", "scripts/vas.py", "--state-home"]
            env = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
            def run(state, *command):
                result = subprocess.run(cli + [str(state), *command], cwd=project, env=env,
                                        capture_output=True, encoding="utf-8", timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return json.loads(result.stdout)
            first, second = base / "remote-agent", base / "other-host"
            self.assertEqual(run(first, "start")["session"]["status"], "none")
            run(first, "finish", "--summary", "메뉴판 제목 수정", "--check", "메뉴판 표시: 통과",
                "--next-step", "다음 변경 확인")
            self.assertEqual(run(second, "start")["session"]["status"], "none")
            runtime = start_release(project, base / "windows-state")
            client = RuntimeClient(runtime)
            try:
                self.assertEqual(client.request("/api/status")[1]["layout"], "project")
                status, data = client.request("/api/project-progress")
                self.assertEqual(status, 200)
                self.assertEqual(data["progress"]["summary"], "메뉴판 제목 수정")
                self.assertEqual(data["progress"]["nextStep"], "다음 변경 확인")
                self.assertEqual(data["progress"]["checks"], [{"name":"메뉴판 표시", "status":"passed"}])
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(client.base + "/api/project-progress", timeout=8)
                self.assertEqual(denied.exception.code, 401)
            finally:
                client.request("/api/shutdown", "POST", {})
                time.sleep(.5)

    def test_legacy_tool_import_index_and_rollback_still_work(self):
        with tempfile.TemporaryDirectory(prefix="vas-release-legacy-") as temporary:
            base = Path(temporary) / "한글 경로 with spaces"
            base.mkdir()
            root = base / "도구"
            root.mkdir()
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
            runtime = start_release(root, state, launcher=install_runtime(root))
            client = RuntimeClient(runtime)
            try:
                self.assertEqual(client.request("/api/status")[1]["layout"], "tool")
                status, selected = client.request(
                    "/api/migrations/select", "POST", {"path": str(source)}
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
