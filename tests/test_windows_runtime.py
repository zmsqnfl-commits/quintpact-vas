"""Windows PowerShell 5.1 VAS localhost runtime integration tests."""

import json
import hashlib
import http.server
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


BASE = Path(__file__).resolve().parents[1]
START_SCRIPT = BASE / "scripts" / "Start-VAS.ps1"
POWERSHELL = shutil.which("powershell.exe")


def run_launcher(root, state, port, idle=30):
    command = [
        POWERSHELL,
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(START_SCRIPT),
        "-NoBrowser",
        "-RootPath",
        str(root),
        "-StateRoot",
        str(state),
        "-Port",
        str(port),
        "-IdleTimeoutSeconds",
        str(idle),
    ]
    result = subprocess.run(command, capture_output=True, timeout=20)
    if result.returncode:
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        raise AssertionError(f"VAS launcher failed ({result.returncode}): {output}")
    deadline = time.time() + 5
    runtime_path = None
    while time.time() < deadline and runtime_path is None:
        for candidate in Path(state).glob("runtime-2.6.0-*.json"):
            try:
                value = json.loads(candidate.read_text(encoding="utf-8-sig"))
                if Path(value.get("rootPath", "")) == Path(root):
                    runtime_path = candidate
                    break
            except (OSError, ValueError):
                pass
        time.sleep(0.05)
    if runtime_path is None:
        raise AssertionError("root-scoped runtime file was not created")
    return json.loads(runtime_path.read_text(encoding="utf-8-sig"))


class RuntimeClient:
    def __init__(self, runtime):
        self.base = f"http://127.0.0.1:{runtime['port']}"
        self.token = runtime["token"]

    def request(self, path, method="GET", data=None, auth=True, origin=None):
        body = None if data is None else json.dumps(data).encode("utf-8")
        headers = {}
        if auth:
            headers["X-VAS-Token"] = self.token
            headers["Origin"] = self.base if origin is None else origin
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
            value = json.loads(raw.decode("utf-8")) if "json" in content_type else raw
            return response.status, value, response.headers


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "Windows PowerShell is required")
class WindowsRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="vas-runtime-test-")
        cls.root = Path(cls.temp.name) / "root with spaces"
        cls.state = Path(cls.temp.name) / "state with spaces"
        (cls.root / "src").mkdir(parents=True)
        (cls.root / "docs").mkdir()
        (cls.root / "workspace" / ".vas").mkdir(parents=True)
        (cls.root / "src" / "vas-hub.html").write_text(
            "<!doctype html><html><body>VAS runtime</body></html>", encoding="utf-8"
        )
        (cls.root / "docs" / "guide.md").write_bytes(b"# Guide\n")
        knowledge = {
            "version": 1,
            "entries": [{"id": "project-a", "title": "Project A"}],
            "padding": "x" * 6_000_000,
        }
        (cls.root / "workspace" / ".vas" / "project-knowledge.json").write_text(
            json.dumps(knowledge), encoding="utf-8"
        )
        cls.source_project = Path(cls.temp.name) / "legacy-project"
        cls.source_project.mkdir()
        (cls.source_project / "README.md").write_text("# Legacy\n", encoding="utf-8")

        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        cls.preferred_port = blocker.getsockname()[1]
        try:
            cls.runtime = run_launcher(cls.root, cls.state, cls.preferred_port)
        finally:
            blocker.close()
        cls.client = RuntimeClient(cls.runtime)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.request("/api/shutdown", "POST", {})
        except Exception:
            pass
        time.sleep(0.5)
        cls.temp.cleanup()

    def test_01_preferred_port_falls_back_and_server_reuses(self):
        self.assertNotEqual(self.runtime["port"], self.preferred_port)
        self.assertLessEqual(self.runtime["port"], self.preferred_port + 9)
        self.assertEqual(Path(self.runtime["rootPath"]), self.root)
        reused = run_launcher(self.root, self.state, self.preferred_port)
        self.assertEqual(reused["pid"], self.runtime["pid"])
        self.assertEqual(reused["token"], self.runtime["token"])

    def test_02_health_static_content_and_headers(self):
        status, health, headers = self.client.request("/health", auth=False)
        self.assertEqual((status, health["service"]), (200, "VAS"))
        status, page, headers = self.client.request("/src/vas-hub.html", auth=False)
        self.assertEqual(status, 200)
        self.assertIn(b"VAS runtime", page)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])

    def test_02b_two_vas_copies_run_independently(self):
        second_root = Path(self.temp.name) / "second-copy"
        (second_root / "src").mkdir(parents=True)
        (second_root / "docs").mkdir()
        (second_root / "src" / "vas-hub.html").write_text("SECOND", encoding="utf-8")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            second_port = probe.getsockname()[1]
        second = run_launcher(second_root, self.state, second_port)
        second_client = RuntimeClient(second)
        try:
            self.assertNotEqual(second["pid"], self.runtime["pid"])
            self.assertNotEqual(second["token"], self.runtime["token"])
            self.assertGreaterEqual(len(list(self.state.glob("runtime-2.6.0-*.json"))), 2)
            _, page, _ = second_client.request("/src/vas-hub.html", auth=False)
            self.assertIn(b"SECOND", page)
            _, health, _ = self.client.request("/health", auth=False)
            self.assertEqual(health["service"], "VAS")
            self.client.request("/api/memory/events", "DELETE")
            clients = [self.client, second_client]

            def add_event(index):
                return clients[index % 2].request(
                    "/api/memory/events",
                    "POST",
                    {"type": "concurrency.test", "payload": {"index": index}},
                )[1]["accepted"]

            with ThreadPoolExecutor(max_workers=8) as pool:
                self.assertTrue(all(pool.map(add_event, range(20))))
            _, shared, _ = self.client.request("/api/memory/events?type=concurrency.test")
            self.assertEqual(len(shared["events"]), 20)
            self.client.request("/api/memory/events", "DELETE")
        finally:
            second_client.request("/api/shutdown", "POST", {})

    def test_02c_stale_runtime_cannot_reuse_another_service(self):
        forged_root = Path(self.temp.name) / "forged-runtime-copy"
        (forged_root / "src").mkdir(parents=True)
        (forged_root / "docs").mkdir()
        (forged_root / "src" / "vas-hub.html").write_text("REAL", encoding="utf-8")
        canonical = str(forged_root.resolve()).rstrip("\\").upper().encode("utf-8")
        runtime_id = "2.6.0-" + hashlib.sha256(canonical).hexdigest()[:16]

        class ForgedHealth(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = json.dumps(
                    {"service": "VAS", "version": "2.6.0", "runtimeId": "wrong", "port": self.server.server_port}
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format, *_args):
                pass

        forged_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ForgedHealth)
        thread = threading.Thread(target=forged_server.serve_forever, daemon=True)
        thread.start()
        stale = {
            "service": "VAS", "version": "2.6.0", "runtimeId": runtime_id,
            "rootPath": str(forged_root), "pid": 999999, "port": forged_server.server_port,
            "token": "stale-token",
        }
        stale_path = self.state / f"runtime-{runtime_id}.json"
        stale_path.write_text(json.dumps(stale), encoding="utf-8")
        actual = None
        try:
            actual = run_launcher(forged_root, self.state, forged_server.server_port)
            self.assertEqual(actual["runtimeId"], runtime_id)
            self.assertNotEqual(actual["token"], "stale-token")
            self.assertNotEqual(actual["port"], forged_server.server_port)
        finally:
            if actual:
                RuntimeClient(actual).request("/api/shutdown", "POST", {})
            forged_server.shutdown()
            forged_server.server_close()
            thread.join(timeout=2)

    def test_03_api_requires_token_and_same_origin(self):
        with self.assertRaises(urllib.error.HTTPError) as missing:
            self.client.request("/api/memory/status", auth=False)
        self.assertEqual(missing.exception.code, 401)
        missing.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as cross_origin:
            self.client.request("/api/memory/status", origin="http://evil.invalid")
        self.assertEqual(cross_origin.exception.code, 403)
        cross_origin.exception.close()

    def test_04_traversal_and_static_writes_are_blocked(self):
        with self.assertRaises(urllib.error.HTTPError) as traversal:
            self.client.request("/src/..%2fdocs%2fguide.md", auth=False)
        self.assertEqual(traversal.exception.code, 404)
        traversal.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as write_attempt:
            self.client.request("/src/vas-hub.html", method="POST", data={}, auth=False)
        self.assertEqual(write_attempt.exception.code, 405)
        write_attempt.exception.close()

    def test_05_read_only_file_and_fixed_knowledge_endpoints(self):
        query = urllib.parse.urlencode({"scope": "docs", "path": "guide.md"})
        status, result, _ = self.client.request(f"/api/files/read?{query}")
        self.assertEqual(status, 200)
        self.assertEqual(result["content"], "# Guide\n")
        status, result, _ = self.client.request("/api/knowledge/projects")
        self.assertEqual(result["entries"][0]["id"], "project-a")
        _, runtime_status, _ = self.client.request("/api/status")
        self.assertIsInstance(runtime_status["capabilities"]["projectImport"]["available"], bool)
        self.assertIn(runtime_status["capabilities"]["projectImport"]["reason"], (None, "python-unavailable", "python-version-unsupported", "migration-module-unavailable"))
        self.assertIsInstance(runtime_status["capabilities"]["python"]["available"], bool)

    def test_06_memory_crud_pause_export_import_and_redaction(self):
        event = {
            "type": "form.complete",
            "source": "client",
            "projectId": "p1",
            "payload": {
                "choice": "linear",
                "password": "should-not-store",
                "note": r"see C:\Users\demo\secret.txt",
                "attachment": "brief.pdf",
                "comment": "please review brief.pdf before export",
                "database": "postgresql://user:pass@localhost/app",
                "cloud": "AWS_ACCESS_KEY_ID=" + "AKIA" + "1234567890ABCDEF",
                "github": "github_" + "pat_abcdefghijklmnopqrstuvwxyz123456",
                "google": "AI" + "zaSyA1234567890abcdefghijklmn",
                "slack": "xox" + "b-1234567890-abcdefghijklmnopqrstuvwxyz",
                "jwt": "e" + "yJabcdefghijk." + "eyJabcdefghijkl.mnopqrstuvwxyz",
            },
        }
        status, created, _ = self.client.request("/api/memory/events", "POST", event)
        self.assertEqual(status, 201)
        self.assertTrue(created["accepted"])
        saved = created["event"]
        self.assertNotIn("password", saved["payload"])
        self.assertEqual(saved["payload"]["note"], "[redacted]")
        self.assertEqual(saved["payload"]["attachment"], "[redacted]")
        self.assertEqual(saved["payload"]["comment"], "[redacted]")
        for key in ("database", "cloud", "github", "google", "slack", "jwt"):
            self.assertEqual(saved["payload"][key], "[redacted]", key)

        updated = dict(event)
        updated["payload"] = {"choice": "vercel"}
        status, result, _ = self.client.request(f"/api/memory/events/{saved['id']}", "PUT", updated)
        self.assertEqual(result["event"]["payload"]["choice"], "vercel")

        self.client.request("/api/memory/pause", "POST", {"paused": True})
        _, skipped, _ = self.client.request("/api/memory/events", "POST", event)
        self.assertFalse(skipped["accepted"])
        _, exported, _ = self.client.request("/api/memory/export")
        self.assertEqual(exported["format"], "vas-personalization-memory")
        exported["events"][0]["payload"] = {
            "choice": "vercel",
            "note": r"migration source is C:\Users\demo\legacy\app.js",
        }
        self.client.request("/api/memory/events", "DELETE")
        _, empty, _ = self.client.request("/api/memory/events")
        self.assertEqual(empty["events"], [])
        self.client.request("/api/memory/pause", "POST", {"paused": False})
        _, imported, _ = self.client.request(
            "/api/memory/import", "POST", {"mode": "replace", "data": exported}
        )
        self.assertEqual(imported["total"], 1)
        _, imported_events, _ = self.client.request("/api/memory/events")
        self.assertEqual(imported_events["events"][0]["payload"]["note"], "[redacted]")
        _, memory_status, _ = self.client.request("/api/memory/status")
        self.assertEqual(memory_status["retention"], "until-explicit-delete")

        memory_path = self.state / "memory.json"
        memory_path.write_text("{broken-json", encoding="utf-8")
        _, recovered, _ = self.client.request("/api/memory/status")
        self.assertEqual(recovered["count"], 0)
        self.assertTrue(recovered["recoveredFrom"].startswith("memory.corrupt-"))
        self.assertTrue(list(self.state.glob("memory.corrupt-*.json")))

    def test_07_folder_selection_returns_opaque_id_when_module_exists(self):
        status, result, _ = self.client.request(
            "/api/folder/select", "POST", {"path": str(self.source_project)}
        )
        if status == 200:
            self.assertFalse(result["cancelled"])
            self.assertRegex(result["selection"]["selectionId"], r"^[a-f0-9]{32}$")

    def test_07b_new_project_is_created_and_registered_atomically(self):
        request = {
            "name": "새 프로젝트",
            "brief": {
                "goal": "부드러운 사용자 흐름",
                "_meta": {"themeTokens": {"primary": "#3451ff", "radius": "8px"}},
            },
        }
        status, result, _ = self.client.request("/api/projects/create", "POST", request)
        self.assertEqual(status, 201)
        project = result["project"]
        self.assertEqual(project["sourceType"], "new")
        self.assertEqual(project["status"], "ready")
        self.assertFalse(project["indexEnabled"])
        target = self.root / "workspace" / "projects" / "새 프로젝트"
        self.assertEqual(Path(project["path"]), target)
        self.assertEqual(
            json.loads((target / "brief.json").read_text(encoding="utf-8-sig"))["goal"],
            "부드러운 사용자 흐름",
        )
        self.assertIn("brief.json", (target / "README.md").read_text(encoding="utf-8-sig"))
        self.assertEqual(
            json.loads((target / "design-tokens.json").read_text(encoding="utf-8-sig"))["primary"],
            "#3451ff",
        )
        _, projects, _ = self.client.request("/api/projects")
        self.assertIn(project["projectId"], [item["projectId"] for item in projects["projects"]])
        self.assertTrue(all("path" not in item and "source" not in item for item in projects["projects"]))

        try:
            self.client.request("/api/projects/create", "POST", request)
            self.fail("duplicate project must fail")
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 409)
            payload = json.loads(error.read().decode("utf-8"))
            error.close()
        self.assertEqual(payload["code"], "project_conflict")

        try:
            self.client.request(
                "/api/projects/create",
                "POST",
                {"name": "unsafe", "path": r"C:\outside", "brief": {}},
            )
            self.fail("client supplied path must fail")
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 400)
            payload = json.loads(error.read().decode("utf-8"))
            error.close()
        self.assertEqual(payload["code"], "project_path_forbidden")
        self.assertFalse((self.root / "workspace" / "projects" / "unsafe").exists())

    def test_08_heartbeat(self):
        status, result, _ = self.client.request("/api/heartbeat", "POST", {})
        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])

    def test_09_migration_errors_are_actionable_and_path_safe(self):
        try:
            self.client.request(
                "/api/migrations/analyze", "POST", {"selectionId": "0" * 32}
            )
            self.fail("invalid selection must fail")
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 400)
            payload = json.loads(error.read().decode("utf-8"))
            error.close()
        self.assertEqual(payload["code"], "selection_invalid")
        self.assertIn("다시 선택", payload["error"])
        self.assertNotIn(str(self.temp.name), json.dumps(payload, ensure_ascii=False))

        try:
            self.client.request(
                "/api/migrations/import",
                "POST",
                {"selectionId": "0" * 32, "createIndex": "yes"},
            )
            self.fail("non-boolean createIndex must fail")
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 400)
            payload = json.loads(error.read().decode("utf-8"))
            error.close()
        self.assertEqual(payload["code"], "invalid_create_index")


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "Windows PowerShell is required")
class WindowsRuntimeIdleTest(unittest.TestCase):
    def test_idle_server_stops_and_removes_runtime_file(self):
        with tempfile.TemporaryDirectory(prefix="vas-idle-test-") as temp:
            root = Path(temp) / "root"
            state = Path(temp) / "state"
            (root / "src").mkdir(parents=True)
            (root / "docs").mkdir()
            (root / "src" / "vas-hub.html").write_text("VAS", encoding="utf-8")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            runtime = run_launcher(root, state, port, idle=2)
            deadline = time.time() + 7
            while time.time() < deadline and list(state.glob("runtime-2.6.0-*.json")):
                time.sleep(0.2)
            self.assertFalse(
                list(state.glob("runtime-2.6.0-*.json")),
                f"idle runtime {runtime['pid']} did not stop",
            )


class WindowsRuntimeSourceTests(unittest.TestCase):
    def test_runtime_files_are_bounded_and_launcher_has_fallback(self):
        for relative in (
            "scripts/Start-VAS.ps1",
            "scripts/VAS.Server.psm1",
            "scripts/VAS.Memory.psm1",
            "tests/test_windows_runtime.py",
        ):
            lines = (BASE / relative).read_text(encoding="utf-8-sig").splitlines()
            self.assertLessEqual(len(lines), 500, relative)
        launcher = (BASE / "Run-VAS-System.bat").read_text(encoding="utf-8-sig")
        self.assertIn(":fallback", launcher)
        self.assertIn("src\\vas-hub.html", launcher)

    @unittest.skipUnless(os.name == "nt" and POWERSHELL, "Windows PowerShell is required")
    def test_conflict_mapping_never_echoes_source_path(self):
        command = (
            "Import-Module '.\\scripts\\VAS.Server.psm1' -Force; "
            "& (Get-Module VAS.Server) { "
            "Get-VASMigrationError 'target already exists: C:\\Users\\demo\\secret' | "
            "ConvertTo-Json -Compress }"
        )
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=BASE,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        mapped = json.loads(result.stdout.decode("utf-8-sig"))
        self.assertEqual(mapped["status"], 409)
        self.assertEqual(mapped["code"], "project_conflict")
        self.assertNotIn("C:\\Users", json.dumps(mapped))


if __name__ == "__main__":
    unittest.main(verbosity=2)
