"""Windows token files: ACL-before-write, output minimization, safe failure/reuse."""
import base64
import contextlib
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import time

import pytest

from test_windows_runtime import RuntimeClient

BASE = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell.exe")
pytestmark = pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="Windows PowerShell required")


def ps(script, **paths):
    environment = dict(os.environ, **{f"VAS_TEST_{key}": str(value) for key, value in paths.items()})
    source = "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; "
    source += ". './scripts/VAS.Runtime.State.ps1'; " + script
    encoded = base64.b64encode(source.encode("utf-16-le")).decode("ascii")
    return subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
                          cwd=BASE, env=environment, capture_output=True, timeout=30)


def json_ps(script, **paths):
    result = ps(script, **paths)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    return json.loads(result.stdout.decode("utf-8-sig"))


def launch(root, state, port, session=None):
    command = [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               str(BASE / "scripts/Start-VAS.ps1"), "-NoBrowser", "-RootPath", str(root),
               "-StateRoot", str(state), "-Port", str(port), "-IdleTimeoutSeconds", "60"]
    if session:
        command += ["-SessionId", session]
    return subprocess.run(command, capture_output=True, timeout=25)


@pytest.fixture
def live(tmp_path):
    root = tmp_path / "product"
    state = tmp_path / "state"
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "src/vas-hub.html").write_text("VAS", encoding="utf-8")
    state.mkdir()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    result = launch(root, state, port)
    assert result.returncode == 0, (result.stdout + result.stderr).decode("utf-8", errors="replace")
    path = next(state.glob("runtime-*.json"))
    runtime = json.loads(path.read_text(encoding="utf-8-sig"))
    try:
        yield root, state, path, runtime, result
    finally:
        try:
            RuntimeClient(runtime).request("/api/shutdown", "POST", {})
        except OSError:
            pass
        for _ in range(50):
            if not path.exists():
                break
            time.sleep(0.1)


@contextlib.contextmanager
def locked(path):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                   wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), 0x80000000, 0, None, 3, 0, None)
    assert handle != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    try:
        yield
    finally:
        kernel.CloseHandle(handle)


def test_private_creation_precedes_token_bytes_and_preserves_parent_permissions(tmp_path):
    path = tmp_path / "private.tmp"
    result = json_ps(r"""
$parent = Split-Path -Parent $env:VAS_TEST_PATH
$acl = [IO.Directory]::GetAccessControl($parent)
$world = New-Object Security.Principal.SecurityIdentifier('S-1-1-0')
$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($world, 'ReadAndExecute', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
[IO.Directory]::SetAccessControl($parent, $acl)
$before = [IO.Directory]::GetAccessControl($parent).Sddl
$stream = New-VASRuntimeSecureStream $env:VAS_TEST_PATH
try {
    $emptyLength = $stream.Length
    $security = [IO.File]::GetAccessControl($env:VAS_TEST_PATH)
    $safe = Test-VASRuntimeSecurity $security
    $bytes = [Text.Encoding]::UTF8.GetBytes('synthetic-token')
    $stream.Write($bytes, 0, $bytes.Length)
} finally { $stream.Dispose() }
@{emptyLength=$emptyLength; safe=$safe; protected=$security.AreAccessRulesProtected;
  inherited=@($security.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | Where-Object {$_.IsInherited}).Count;
  principals=@($security.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {$_.IdentityReference.Value});
  user=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value; before=$before;
  after=[IO.Directory]::GetAccessControl($parent).Sddl} | ConvertTo-Json -Compress
""", PATH=path)
    assert result["emptyLength"] == 0 and result["safe"]
    assert result["protected"] and result["inherited"] == 0
    assert set(result["principals"]) == {result["user"], "S-1-5-18", "S-1-5-32-544"}
    assert result["before"] == result["after"]
    assert path.read_text(encoding="utf-8") == "synthetic-token"


def test_atomic_replacement_restricts_legacy_file_without_changing_parent(tmp_path):
    path = tmp_path / "runtime.json"
    path.write_text('{"token":"old-synthetic"}', encoding="utf-8")
    result = json_ps(r"""
$parent = Split-Path -Parent $env:VAS_TEST_PATH
$before = [IO.Directory]::GetAccessControl($parent).Sddl
Save-VASRuntimeState $env:VAS_TEST_PATH @{token='new-synthetic'}
@{safe=(Test-VASRuntimeSecurity ([IO.File]::GetAccessControl($env:VAS_TEST_PATH)));
  before=$before; after=[IO.Directory]::GetAccessControl($parent).Sddl} | ConvertTo-Json -Compress
""", PATH=path)
    assert result["safe"] and result["before"] == result["after"]
    assert json.loads(path.read_text()) == {"token": "new-synthetic"}
    assert not list(tmp_path.glob(".runtime-*.tmp"))


def test_no_browser_output_has_no_token_and_reuses_healthy_runtime(live):
    root, state, path, runtime, first = live
    result = launch(root, state, runtime["port"])
    assert result.returncode == 0
    assert json.loads(path.read_text()) == runtime
    for run in (first, result):
        output = run.stdout + run.stderr
        assert runtime["token"].encode() not in output
        assert b"vasToken" not in output
        assert f"VAS_READY http://127.0.0.1:{runtime['port']}/src/vas-hub.html".encode() in output
    assert json_ps("(Test-VASRuntimeSecurity ([IO.File]::GetAccessControl($env:VAS_TEST_PATH))) | ConvertTo-Json", PATH=path)


def test_legacy_live_runtime_acl_is_tightened_before_reuse(live):
    root, state, path, runtime, _ = live
    result = json_ps(r"""
$rootBefore = [IO.Directory]::GetAccessControl($env:VAS_TEST_STATE).Sddl
$parentBefore = [IO.Directory]::GetAccessControl((Split-Path -Parent $env:VAS_TEST_STATE)).Sddl
$acl = [IO.File]::GetAccessControl($env:VAS_TEST_PATH)
$acl.SetAccessRuleProtection($false, $true)
$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier('S-1-1-0')), 'Read', 'Allow')))
[IO.File]::SetAccessControl($env:VAS_TEST_PATH, $acl)
@{root=$rootBefore; parent=$parentBefore} | ConvertTo-Json -Compress
""", PATH=path, STATE=state)
    launch_result = launch(root, state, runtime["port"])
    assert launch_result.returncode == 0
    assert json.loads(path.read_text()) == runtime
    after = json_ps(r"""
@{root=[IO.Directory]::GetAccessControl($env:VAS_TEST_STATE).Sddl;
parent=[IO.Directory]::GetAccessControl((Split-Path -Parent $env:VAS_TEST_STATE)).Sddl;
safe=(Test-VASRuntimeSecurity ([IO.File]::GetAccessControl($env:VAS_TEST_PATH)))} | ConvertTo-Json -Compress
""", PATH=path, STATE=state)
    assert after.pop("safe") and result == after


def test_locked_runtime_read_fails_without_deleting_or_duplicate_launch(live):
    root, state, path, runtime, _ = live
    before = path.read_bytes()
    with locked(path):
        result = launch(root, state, runtime["port"])
        assert result.returncode != 0
    assert path.read_bytes() == before
    output = result.stdout + result.stderr
    assert b"VAS_RUNTIME_STATE_UNSAFE" in output and runtime["token"].encode() not in output
    assert RuntimeClient(runtime).request("/api/heartbeat", "POST", {})[0] == 200
    assert not list(state.glob(".runtime-*.tmp"))


def test_failed_replacement_preserves_existing_content_and_cleans_private_temp(tmp_path):
    path = tmp_path / "runtime.json"
    path.write_text('{"token":"original-synthetic"}', encoding="utf-8")
    before = path.read_bytes()
    with locked(path):
        result = ps("Save-VASRuntimeState $env:VAS_TEST_PATH @{token='replacement-synthetic'}", PATH=path)
        assert result.returncode != 0
    assert path.read_bytes() == before
    assert not list(tmp_path.glob(".runtime-*.tmp"))
    assert b"replacement-synthetic" not in result.stdout + result.stderr


def test_session_launch_retains_design_destination_without_output_token(live):
    root, state, _, runtime, _ = live
    session = "a" * 32
    result = launch(root, state, runtime["port"], session)
    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert f"/src/design-controller.html?session={session}".encode() in output
    assert b"vasToken" not in output and runtime["token"].encode() not in output


def test_browser_launch_receives_authentication_but_output_does_not(tmp_path):
    # Invoke the production launcher with only Start-Process replaced: observe the
    # OS browser handoff without opening a real browser or exposing a real token.
    root = tmp_path / "root"
    state = tmp_path / "state"
    root.mkdir()
    state.mkdir()
    script = (BASE / "scripts/Start-VAS.ps1").read_text(encoding="utf-8-sig")
    functions = script[script.index("function Get-VASLaunchUrl"):script.index("if ($Server) {")]
    result = ps(r"""
$SessionId='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'; $NoBrowser=$false
function Start-Process { param([string]$FilePath); [IO.File]::WriteAllText($env:VAS_TEST_CAPTURE, $FilePath) }
""" + functions + "Open-VASBrowser @{port=41725;token='synthetic-launch-secret'}", CAPTURE=tmp_path / "capture.txt")
    assert result.returncode == 0, result.stderr
    assert b"synthetic-launch-secret" not in result.stdout + result.stderr
    captured = (tmp_path / "capture.txt").read_text()
    assert "design-controller.html?session=" + "b" * 32 in captured
    assert "&vasToken=synthetic-launch-secret" in captured


@pytest.mark.parametrize("path", [r"\\localhost\share\state", r"\\?\C:\state", r"C:\state:ads"])
def test_unsupported_state_paths_fail_without_echoing_a_token(tmp_path, path):
    result = launch(tmp_path, path, 41725)
    assert result.returncode != 0
    assert b"VAS_START_ERROR" in result.stdout + result.stderr
    assert b"VAS_READY" not in result.stdout + result.stderr


@pytest.mark.parametrize("location", ["runtime-file", "state-ancestor"])
def test_launcher_rejects_junctions_without_touching_external_state(tmp_path, location):
    root = tmp_path / "product"
    state = tmp_path / "state"
    outside = tmp_path / "outside"
    for directory in (root, state, outside):
        directory.mkdir()
    marker = outside / "preserved.json"
    marker.write_text('{"token":"synthetic-outside-token"}', encoding="utf-8")
    before = marker.read_bytes()
    if location == "runtime-file":
        canonical = str(root.resolve()).rstrip("\\").upper().encode("utf-8")
        runtime_id = "2.9.1-" + hashlib.sha256(canonical).hexdigest()[:16]
        junction = state / f"runtime-{runtime_id}.json"
    else:
        junction = tmp_path / "linked-ancestor"
        state = junction / "state"
    created = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
                             capture_output=True, timeout=10)
    assert created.returncode == 0, created.stderr
    try:
        result = launch(root, state, 41725)
        assert result.returncode != 0
        assert b"VAS_READY" not in result.stdout + result.stderr
        assert b"synthetic-outside-token" not in result.stdout + result.stderr
        assert marker.read_bytes() == before
        assert sorted(p.name for p in outside.iterdir()) == ["preserved.json"]
    finally:
        # Remove only the known junction directory entry, never its target.
        assert junction.parent.resolve().is_relative_to(tmp_path.resolve())
        assert junction.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
        os.rmdir(junction)
