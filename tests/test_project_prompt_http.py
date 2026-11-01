"""The real authenticated Windows hub saves only its containing project's prompt."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell.exe")
pytestmark = pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="Windows PowerShell required")


class Client:
    def __init__(self, value):
        self.base, self.token = value["baseUrl"], value["token"]

    def call(self, method="GET", body=None, *, raw=None, auth=True, origin=None, query=""):
        headers = {"Content-Type": "application/json"}
        if auth:
            headers.update({"X-VAS-Token": self.token, "Origin": origin or self.base})
        if body is not None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(self.base + "/api/project-prompt" + query,
                                         data=raw, headers=headers, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response), response.headers


@pytest.fixture
def live(tmp_path):
    app = tmp_path / "나의 재고 앱"
    engine = app / ".vas"
    (app / "src").mkdir(parents=True)
    (app / "src/app.js").write_text("unchanged app", encoding="utf-8")
    (engine / "src").mkdir(parents=True)
    (engine / "src/vas-hub.html").write_text("VAS", encoding="utf-8")
    (engine / "Run-VAS-System.bat").write_text("fixture", encoding="utf-8")
    (engine / "project-layout.json").write_text('{"layout":"vas-project","version":1}', encoding="utf-8")
    before = {p.relative_to(engine): p.read_bytes() for p in engine.rglob("*") if p.is_file()}
    state = tmp_path / "pc-state"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen([
        POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(ROOT / "scripts/Start-VAS.ps1"), "-Server", "-NoBrowser",
        "-RootPath", str(engine), "-StateRoot", str(state), "-Port", str(port),
        "-IdleTimeoutSeconds", "120",
    ], env={**os.environ, "VAS_PYTHON": sys.executable, "LOCALAPPDATA": str(tmp_path / "local"),
            "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"},
       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    client = None
    try:
        end = time.monotonic() + 20
        while time.monotonic() < end:
            paths = list(state.glob("runtime-*.json"))
            if paths:
                try:
                    client = Client(json.loads(paths[0].read_text(encoding="utf-8-sig")))
                    break
                except (OSError, ValueError):
                    pass
            assert process.poll() is None, "isolated project runtime exited"
            time.sleep(.1)
        assert client is not None
        yield client, app, engine
        assert {p.relative_to(engine): p.read_bytes() for p in engine.rglob("*") if p.is_file()} == before
        assert (app / "src/app.js").read_text(encoding="utf-8") == "unchanged app"
    finally:
        if client and process.poll() is None:
            try:
                request = urllib.request.Request(client.base + "/api/shutdown", data=b"{}", method="POST",
                    headers={"X-VAS-Token": client.token, "Origin": client.base, "Content-Type": "application/json"})
                urllib.request.urlopen(request, timeout=5).close()
            except OSError:
                pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        process.communicate(timeout=5)


def test_save_without_session_is_read_back_and_stale_tab_cannot_replace_it(live):
    client, app, _ = live
    status, read, headers = client.call()
    assert (status, read) == (200, {"revision": 0, "prompt": ""})
    assert headers["Cache-Control"] == "no-store"
    assert not (app / "VAS-PROJECT-PROMPT.json").exists()
    _, first, _ = client.call("PUT", {"expectedRevision": 0, "prompt": "재고 목록만 만들고 결제는 제외하세요."})
    assert first["revision"] == 1
    assert client.call()[1] == first
    raw = (app / "VAS-PROJECT-PROMPT.json").read_bytes()
    status, error, _ = client.call("PUT", {"expectedRevision": 0, "prompt": "오래된 탭"})
    assert (status, error["code"]) == (409, "project_prompt_conflict")
    assert (app / "VAS-PROJECT-PROMPT.json").read_bytes() == raw
    status, cleared, _ = client.call("PUT", {"expectedRevision": 1, "prompt": ""})
    assert status == 200 and cleared == {"revision": 2, "prompt": ""}
    assert str(app) not in json.dumps([read, first, cleared])


def test_auth_origin_query_and_body_validation_precede_any_write(live):
    client, app, _ = live
    good = {"expectedRevision": 0, "prompt": "한국어 유지"}
    for method, body in [("GET", None), ("PUT", good)]:
        assert client.call(method, body, auth=False)[0] == 401
        assert client.call(method, body, origin="https://evil.invalid")[0] == 403
    assert client.call("PUT", raw=b"x" * 70000, auth=False)[0] == 401
    assert client.call("PUT", raw=b"x" * 70000)[0] == 413
    assert client.call(query="?root=other")[0] == 400
    assert client.call("DELETE")[0] == 405
    for raw in [b'{"expectedRevision":0,"expectedRevision":0,"prompt":"a"}',
                b'{"expectedRevision":true,"prompt":"a"}', b'{"expectedRevision":"0","prompt":"a"}',
                b'{"expectedRevision":0,"prompt":"a","path":"src/app.js"}', b'\xff']:
        assert client.call("PUT", raw=raw)[0] == 400
    assert not (app / "VAS-PROJECT-PROMPT.json").exists()


def test_sensitive_input_and_corrupt_existing_file_are_never_overwritten(live):
    client, app, _ = live
    status, error, _ = client.call("PUT", {"expectedRevision": 0, "prompt": "api_key=sk-live-secret-canary-12345"})
    assert status == 400 and error["code"] == "project_prompt_sensitive"
    assert "canary" not in json.dumps(error)
    record = app / "VAS-PROJECT-PROMPT.json"
    record.write_bytes(b'{"broken":true}')
    assert client.call()[0] == 409
    assert client.call("PUT", {"expectedRevision": 0, "prompt": "replacement"})[0] == 409
    assert record.read_bytes() == b'{"broken":true}'
