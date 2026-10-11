"""Windows local-state paths reject existing links before reading or mutation."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess

import pytest

from test_memory_policy import error, event, launched, seed
from test_windows_runtime import POWERSHELL

pytestmark = pytest.mark.skipif(
    os.name != "nt" or not shutil.which("powershell.exe"), reason="Windows PowerShell required",
)
ROOT = Path(__file__).resolve().parents[1]
MANAGED = ["memory.json", "memory-consent.json", "memory.previous.json",
           "memory.corrupt-synthetic.json", ".memory-" + "a" * 32 + ".tmp",
           ".consent-" + "b" * 32 + ".tmp"]
OPERATIONS = ["Initialize", "Status", "Events", "Export", "ConsentOff", "Clear",
              "Pause", "Add", "Import", "Remove", "Update"]


def powershell(script, *arguments):
    result = subprocess.run([
        POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *map(str, arguments),
    ], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    return result.stdout.decode("utf-8-sig").strip()


@pytest.fixture
def runner(tmp_path):
    script = tmp_path / "memory-paths.ps1"
    script.write_text(r"""param([string]$ModulePath, [string]$StateRoot)
$ErrorActionPreference = 'Stop'
Import-Module $ModulePath -Force
$results = @()
foreach ($operation in @('Initialize','Status','Events','Export','ConsentOff','Clear','Pause','Add','Import','Remove','Update')) {
    try {
        $event = @{type='fixture';payload=@{note='synthetic'}}
        $value = switch ($operation) {
            'Initialize' { Initialize-VASMemoryStore $StateRoot }
            'Status' { Get-VASMemoryStatus $StateRoot }
            'Events' { Get-VASMemoryEvents $StateRoot }
            'Export' { Export-VASMemory $StateRoot }
            'ConsentOff' { Set-VASMemoryConsent -Root $StateRoot -Consent $false }
            'Clear' { Clear-VASMemory $StateRoot }
            'Pause' { Set-VASMemoryPaused -Root $StateRoot -Paused $true }
            'Add' { Add-VASMemoryEvent -Root $StateRoot -InputObject $event }
            'Import' { Import-VASMemory -Root $StateRoot -InputObject @{events=@()} -Mode replace }
            'Remove' { Remove-VASMemoryEvent -Root $StateRoot -Id ('0' * 32) }
            'Update' { Set-VASMemoryEvent -Root $StateRoot -Id ('0' * 32) -InputObject $event }
        }
        $results += @{operation=$operation; rejected=$false}
    } catch { $results += @{operation=$operation; rejected=$true; message=$_.Exception.Message} }
}
ConvertTo-Json -InputObject @($results) -Compress
""", encoding="utf-8-sig")
    return script


def assert_all_rejected(runner, state):
    results = json.loads(powershell(runner, ROOT / "scripts/VAS.Memory.psm1", state))
    assert [item["operation"] for item in results] == OPERATIONS
    assert all(item["rejected"] and item["message"] == "VAS_MEMORY_PATH_INVALID" for item in results), results


def junction(tmp_path, link, target):
    script = tmp_path / "junction.ps1"
    script.write_text("param([string]$Link,[string]$Target)\nNew-Item -ItemType Junction -Path $Link -Target $Target -ErrorAction Stop | Out-Null", encoding="utf-8-sig")
    powershell(script, link, target)
    assert os.lstat(link).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT


def remove_junction(link, tmp_path):
    assert Path(os.path.abspath(link)).is_relative_to(tmp_path.resolve())
    assert os.lstat(link).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    os.rmdir(link)  # Verified junction only, never recursive target deletion.


def snapshot(directory):
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


@pytest.mark.parametrize("location", ["root", "ancestor", "missing-descendant", "dangling"])
def test_state_root_and_ancestors_reject_junctions_without_touching_target(tmp_path, runner, location):
    target = tmp_path / "external"
    target.mkdir()
    seed(target / "nested" if location == "ancestor" else target, [event()])
    link = tmp_path / "linked"
    junction(tmp_path, link, target)
    state = link / "nested" if location == "ancestor" else link
    if location == "missing-descendant":
        state = link / "never-created" / "state"
    if location == "dangling":
        # Move the owned directory to make the junction dangling without deleting data.
        saved = tmp_path / "saved"
        target.rename(saved)
        target = saved
    before = snapshot(target)
    try:
        assert_all_rejected(runner, state)
        assert snapshot(target) == before
        assert not (target / "never-created").exists()
    finally:
        remove_junction(link, tmp_path)


@pytest.mark.parametrize("name", MANAGED)
def test_managed_directory_junction_rejected_before_any_change(tmp_path, runner, name):
    state, target = tmp_path / "state", tmp_path / "external"
    seed(state, [event()])
    target.mkdir()
    (target / "preserve.txt").write_text("EXTERNAL_SYNTHETIC_CONTENT")
    link = state / name
    link.unlink(missing_ok=True)
    before = {path.name: path.read_bytes() for path in state.iterdir() if path.is_file()}
    junction(tmp_path, link, target)
    try:
        assert_all_rejected(runner, state)
        assert snapshot(target) == {"preserve.txt": b"EXTERNAL_SYNTHETIC_CONTENT"}
        assert {path.name: path.read_bytes() for path in state.iterdir() if path.is_file()} == before
    finally:
        remove_junction(link, tmp_path)


@pytest.mark.parametrize("name", MANAGED)
def test_directory_in_managed_file_position_fails_without_changes(tmp_path, runner, name):
    state = tmp_path / "state"
    seed(state, [event()])
    path = state / name
    path.unlink(missing_ok=True)
    path.mkdir()
    (path / "keep.txt").write_text("synthetic original")
    before = snapshot(state)
    assert_all_rejected(runner, state)
    assert snapshot(state) == before


def test_file_in_state_ancestor_position_is_rejected(tmp_path, runner):
    ancestor = tmp_path / "file"
    ancestor.write_bytes(b"original")
    assert_all_rejected(runner, ancestor / "state")
    assert_all_rejected(runner, ancestor)
    assert ancestor.read_bytes() == b"original"


@pytest.mark.parametrize("dangling", [False, True])
def test_file_symlinks_rejected_when_windows_privilege_available(tmp_path, runner, dangling):
    state, target = tmp_path / "state", tmp_path / "external.json"
    seed(state, [event()])
    target.write_text('{"version":1,"consent":true}')
    link = state / "memory-consent.json"
    link.unlink()
    try:
        link.symlink_to(target)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows file-symlink privilege unavailable; junction cases still execute")
        raise
    if dangling:
        target.unlink()
    try:
        assert_all_rejected(runner, state)
        assert target.exists() is (not dangling)
        if not dangling:
            assert target.read_text() == '{"version":1,"consent":true}'
    finally:
        assert link.is_symlink()
        link.unlink()


def test_generic_helper_accepts_missing_leaf_without_creating_it(tmp_path):
    script = tmp_path / "helper.ps1"
    script.write_text("param([string]$Helper,[string]$Path)\n$ErrorActionPreference='Stop'\n. $Helper\n$result=@(Assert-VASLocalStatePath -Path $Path -ExpectedType File)\nif ($result.Count -ne 0) { throw 'non-void helper' }", encoding="utf-8-sig")
    path = tmp_path / "missing" / "runtime.json"
    powershell(script, ROOT / "scripts/VAS.LocalState.ps1", path)
    assert not path.parent.exists()


@pytest.mark.parametrize("path", [r"\\server\share\state", r"\\?\C:\state", r"C:\state:stream",
                                 r"C:\state\CON.json", r"C:\NUL\state", r"C:\state\LPT1.tmp",
                                 r"C:\state\trailing.", "C:\\state\\trailing "])
def test_nonlocal_device_and_ambiguous_paths_rejected(tmp_path, path):
    script = tmp_path / "reject.ps1"
    script.write_text("param([string]$Helper,[string]$Path)\n$ErrorActionPreference='Stop'\n. $Helper\ntry { Assert-VASLocalStatePath -Path $Path; throw 'accepted' } catch { if ($_.Exception.Message -ne 'VAS_LOCAL_STATE_PATH_INVALID') { throw } }", encoding="utf-8-sig")
    powershell(script, ROOT / "scripts/VAS.LocalState.ps1", path)


def test_http_path_replacement_is_rejected_and_safe_path_can_recover(tmp_path):
    with launched(tmp_path / "runtime", before_start=lambda path: seed(path, [event()])) as (client, state):
        target = tmp_path / "external"
        target.mkdir()
        (target / "original.json").write_bytes(b"EXTERNAL_SYNTHETIC_ORIGINAL")
        link = state / "memory-consent.json"
        consent = link.read_bytes()
        live = (state / "memory.json").read_bytes()
        link.unlink()
        junction(tmp_path, link, target)
        try:
            for route, method, body in [
                ("/api/memory/status", "GET", None),
                ("/api/memory/events", "GET", None),
                ("/api/memory/export", "GET", None),
                ("/api/memory/consent", "POST", {"consent": False}),
                ("/api/memory/events", "DELETE", None),
            ]:
                error(client, route, method, body, 503, "memory_path_invalid")
                assert snapshot(target) == {"original.json": b"EXTERNAL_SYNTHETIC_ORIGINAL"}
                assert (state / "memory.json").read_bytes() == live
        finally:
            remove_junction(link, tmp_path)
            link.write_bytes(consent)
        assert client.request("/api/memory/consent", "POST", {"consent": False})[1]["consent"] is False
        assert len(client.request("/api/memory/events")[1]["events"]) == 1
        assert len(client.request("/api/memory/export")[1]["events"]) == 1
        client.request("/api/memory/events", "DELETE")
        assert client.request("/api/memory/status")[1]["count"] == 0
