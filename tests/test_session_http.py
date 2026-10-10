"""Real Windows HTTP bridge: auth, public data, CAS and design-only writes."""
from copy import deepcopy
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
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vas_session import SessionManager

POWERSHELL = shutil.which("powershell.exe")
pytestmark = pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="Windows PowerShell required")


class Client:
    def __init__(self, runtime):
        self.base = runtime["baseUrl"]
        self.token = runtime["token"]

    def request(self, path, method="GET", data=None, raw=None, auth=True, origin=None):
        if data is not None:
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["X-VAS-Token"] = self.token
            headers["Origin"] = self.base if origin is None else origin
        request = urllib.request.Request(self.base + path, data=raw, headers=headers, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read().decode("utf-8")), response.headers


@pytest.fixture(scope="module")
def runtime(tmp_path_factory):
    temp = tmp_path_factory.mktemp("chat http 한국어")
    root = temp / "VAS copy"
    (root / "src").mkdir(parents=True)
    (root / "src/vas-hub.html").write_text("VAS", encoding="utf-8")
    (root / "Run-VAS-System.bat").write_text("@echo off", encoding="utf-8")
    memory = temp / "runtime"
    local = temp / "local"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen([
        POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(ROOT / "scripts/Start-VAS.ps1"), "-Server", "-NoBrowser", "-RootPath", str(root),
        "-StateRoot", str(memory), "-Port", str(port), "-IdleTimeoutSeconds", "180",
    ], env={**os.environ, "LOCALAPPDATA": str(local), "VAS_PYTHON": sys.executable,
            "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    client = None
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            candidates = list(memory.glob("runtime-*.json"))
            if candidates:
                try:
                    client = Client(json.loads(candidates[0].read_text(encoding="utf-8-sig")))
                    break
                except (OSError, ValueError):
                    pass
            if process.poll() is not None:
                raise AssertionError("Session HTTP fixture server did not start")
            time.sleep(0.1)
        assert client is not None, "Session HTTP fixture server startup timed out"
        service = SessionManager(root, local / "VAS/chat-sessions")
        yield client, service, root
    finally:
        if client is not None and process.poll() is None:
            try:
                client.request("/api/shutdown", "POST", {})
            except OSError:
                pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.communicate(timeout=5)


@pytest.fixture
def active(runtime):
    client, service, root = runtime
    target = root / "workspace" / uuid.uuid4().hex
    target.mkdir(parents=True)
    (target / "existing.txt").write_text("App is untouched", encoding="utf-8")
    settings = {"project": {"name": "테스트 예약 앱", "sourceType": "new"},
                "task": {"request": "CSV 저장", "designScope": {"mode": "new", "scope": "화면"},
                         "completionCriteria": [{"description": "CSV 한글 보존", "method": "automatic", "required": True}]},
                "questions": ["예약 종류 확인"], "nextStep": "필수 항목 구현"}
    created = service.create(settings, target)["session"]
    yield client, service, created, target


def payload(created):
    return {"sessionId": created["sessionId"], "expectedRevision": created["revision"],
            "designScope": {"mode": "new", "scope": "예약 화면"},
            "design": {"profileId": "editorial", "direction": "차분한 예약 화면",
                       "tokens": {"primary": "#123456"}}}


def test_http_same_store_roundtrip_is_private_and_leaves_app_untouched(active):
    client, service, created, target = active
    status, listing, headers = client.request("/api/chat/sessions")
    assert status == 200 and headers["Cache-Control"] == "no-store"
    assert created["sessionId"] in [item["sessionId"] for item in listing["sessions"]]
    status, read, _ = client.request("/api/chat/session?sessionId=" + created["sessionId"])
    assert status == 200 and read["session"] == created
    assert read["target"] == {"status": "available"}
    status, saved, _ = client.request("/api/chat/session/design", "POST", payload(created))
    assert status == 200
    assert saved["session"]["revision"] == created["revision"] + 1
    assert service.resume(session_id=created["sessionId"])["session"] == saved["session"]
    assert saved["session"]["settings"]["questions"] == ["예약 종류 확인"]
    combined = json.dumps([listing, read, saved], ensure_ascii=False)
    assert str(target) not in combined and '"binding"' not in combined and '"path"' not in combined
    assert list(target.iterdir()) == [target / "existing.txt"]
    assert (target / "existing.txt").read_text(encoding="utf-8") == "App is untouched"


def test_http_auth_and_origin_guard_reads_and_writes(active):
    client, service, created, _ = active
    for route, method, data in [("/api/chat/sessions", "GET", None),
                                ("/api/chat/session/design", "POST", payload(created))]:
        assert client.request(route, method, data, auth=False)[0] == 401
        assert client.request(route, method, data, origin="https://evil.invalid")[0] == 403
    assert service.export(created["sessionId"]) == created


def test_http_rejects_old_revision_after_chat_save_without_losing_chat_change(active):
    client, service, created, _ = active
    changed = deepcopy(created["settings"])
    changed["nextStep"] = "채팅에서 바꾼 다음 단계"
    current = service.save(created["sessionId"], created["revision"], changed)["session"]
    status, failed, _ = client.request("/api/chat/session/design", "POST", payload(created))
    assert (status, failed["code"]) == (409, "revision_conflict")
    assert service.export(created["sessionId"]) == current


@pytest.mark.parametrize("revision", [True, "1", 1.0])
def test_http_json_number_types_are_not_coerced(active, revision):
    client, service, created, _ = active
    data = payload(created)
    data["expectedRevision"] = revision
    status, failed, _ = client.request("/api/chat/session/design", "POST", data)
    assert (status, failed["code"]) == (400, "revision_invalid")
    assert service.export(created["sessionId"]) == created


def test_http_raw_duplicate_oversize_and_unknown_fields_never_save(active):
    client, service, created, _ = active
    original = payload(created)
    duplicate = json.dumps(original)[:-1] + ',"expectedRevision":1}'
    status, failed, _ = client.request("/api/chat/session/design", "POST", raw=duplicate.encode())
    assert (status, failed["code"]) == (400, "session_duplicate_key")
    for data in [{**original, "target": "C:\\private"}, {**original, "task": {"request": "replace"}}]:
        assert client.request("/api/chat/session/design", "POST", data)[0] == 400
    assert client.request("/api/chat/session/design", "POST", raw=b"{" + b" " * 65536)[0] == 413
    assert service.export(created["sessionId"]) == created


def test_http_has_no_target_selection_creation_forget_or_app_execution_routes(active):
    client, service, created, _ = active
    for suffix in ["create", "forget", "rebind", "execute", "target"]:
        assert client.request("/api/chat/session/" + suffix, "POST", payload(created))[0] == 404
    assert client.request("/api/chat/session")[0] == 400
    assert service.export(created["sessionId"]) == created
