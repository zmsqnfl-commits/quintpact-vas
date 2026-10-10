"""A partially sent HttpListener response must not terminate the local server."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell.exe")
pytestmark = pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="Windows PowerShell required")

RUNNER = r"""
param([string]$ModulePath, [string]$RootPath, [string]$MemoryPath, [string]$ReadyPath, [int]$Port)
$ErrorActionPreference = 'Stop'
$module = Import-Module $ModulePath -Force -PassThru
# Inject only the request handler in this isolated process. The listener,
# response writer, error writer and request loop are the actual product code.
& $module {
    function script:Invoke-VASStaticRequest {
        param([Net.HttpListenerContext]$Context, $State)
        switch ($Context.Request.Url.AbsolutePath) {
            '/fixture/after-headers' {
                $bytes = [Text.Encoding]::UTF8.GetBytes('partial')
                $Context.Response.ContentLength64 = 100
                $Context.Response.OutputStream.Write($bytes, 0, $bytes.Length)
                $Context.Response.OutputStream.Flush()
                throw 'injected failure after response headers were sent'
            }
            '/fixture/before-headers' { throw 'injected handler failure before response headers' }
            '/fixture/stop' {
                $State.Shutdown = $true
                Write-VASResponse $Context 200 @{ stopped = $true }
            }
        }
    }
}
$state = New-VASServerState -RootPath $RootPath -MemoryRoot $MemoryPath -PreferredPort $Port -RuntimeId 'response-fixture'
try {
    [IO.File]::WriteAllText($ReadyPath, (@{ baseUrl = $state.BaseUrl; port = $state.Port } | ConvertTo-Json))
    Start-VASRequestLoop -State $state -IdleTimeoutSeconds 60
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
"""


@pytest.fixture
def server(tmp_path):
    runner = tmp_path / "response-runner.ps1"
    runner.write_text(RUNNER, encoding="utf-8-sig")
    ready = tmp_path / "ready.json"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen([
        POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(runner),
        "-ModulePath", str(ROOT / "scripts/VAS.Server.psm1"), "-RootPath", str(tmp_path),
        "-MemoryPath", str(tmp_path / "memory"), "-ReadyPath", str(ready), "-Port", str(port),
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    runtime = None
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if ready.exists():
                try:
                    runtime = json.loads(ready.read_text(encoding="utf-8-sig"))
                    break
                except ValueError:
                    pass
            assert process.poll() is None, "Isolated response fixture failed to start"
            time.sleep(0.05)
        assert runtime, "Isolated response fixture startup timed out"
        yield process, runtime
    finally:
        if runtime and process.poll() is None:
            try:
                with urllib.request.urlopen(runtime["baseUrl"] + "/fixture/stop", timeout=2):
                    pass
            except OSError:
                pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        process.communicate(timeout=3)


def assert_healthy(process, runtime):
    assert process.poll() is None, "One failed response terminated the HTTP server"
    with urllib.request.urlopen(runtime["baseUrl"] + "/health", timeout=5) as response:
        assert response.status == 200
        assert json.loads(response.read())["service"] == "VAS"


def test_failure_after_sent_headers_aborts_only_that_response(server):
    process, runtime = server
    assert_healthy(process, runtime)
    with socket.create_connection(("127.0.0.1", runtime["port"]), timeout=5) as client:
        client.sendall((f"GET /fixture/after-headers HTTP/1.1\r\nHost: 127.0.0.1:{runtime['port']}\r\n"
                        "Connection: close\r\n\r\n").encode("ascii"))
        fragments = []
        while True:
            try:
                chunk = client.recv(4096)
            except ConnectionResetError:
                break
            if not chunk:
                break
            fragments.append(chunk)
    partial = b"".join(fragments)
    assert b"HTTP/1.1 200" in partial and b"partial" in partial
    assert_healthy(process, runtime)


def test_normal_handler_failure_still_returns_500_and_server_continues(server):
    process, runtime = server
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(runtime["baseUrl"] + "/fixture/before-headers", timeout=5)
    with caught.value as response:
        assert response.code == 500
        payload = json.loads(response.read().decode("utf-8"))
        assert payload["code"] == "request_failed"
        assert "injected" not in payload["error"]
    assert_healthy(process, runtime)
