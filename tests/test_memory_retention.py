"""Preserve recovery originals and bound Windows memory-owned history."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import pytest

from test_memory_policy import event, error, launched, seed
from test_windows_runtime import POWERSHELL

pytestmark = pytest.mark.skipif(
    os.name != "nt" or not shutil.which("powershell.exe"), reason="Windows PowerShell required",
)
ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 * 1024


def owned_files(state):
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in state.iterdir()
        if path.is_file() and path.name.startswith(("memory", ".memory", ".consent"))
    }


def recovery_file(state, index, size=16):
    path = state / f"memory.corrupt-20261011-000000-{index:032x}.json"
    path.write_bytes(b"x" * size)
    return path


def temp_file(state, index, size=28, prefix="consent", hours=0):
    path = state / f".{prefix}-{index:032x}.tmp"
    path.write_bytes(b"x" * size)
    stamp = time.time() - hours * 3600
    os.utime(path, (stamp, stamp))
    return path


def test_startup_cleans_only_expired_guid_temps(tmp_path):
    def prepare(state):
        seed(state, [event()])
        temp_file(state, 1, prefix="consent", hours=25)
        temp_file(state, 2, prefix="memory", hours=25)
        temp_file(state, 3, hours=23)
        unknown = state / ".consent-not-a-guid.tmp"
        unknown.write_bytes(b"unknown")
        stamp = time.time() - 48 * 3600
        os.utime(unknown, (stamp, stamp))
        (state / "notes.txt").write_bytes(b"unrelated")
        recovery_file(state, 1)
        (state / "memory.previous.json").write_bytes(b"previous")

    with launched(tmp_path / "cleanup", before_start=prepare) as (client, state):
        assert not (state / f".consent-{1:032x}.tmp").exists()
        assert not (state / f".memory-{2:032x}.tmp").exists()
        assert (state / f".consent-{3:032x}.tmp").exists()
        assert (state / ".consent-not-a-guid.tmp").read_bytes() == b"unknown"
        status = client.request("/api/memory/status")[1]
        assert status["count"] == 1 and status["history"]["tempCount"] == 2
        assert status["history"]["corruptCount"] == 1
        assert status["history"]["backupBytes"] == 8
        client.request("/api/memory/consent", "POST", {"consent": False})
        client.request("/api/memory/events", "DELETE")
        assert not list(state.glob(".*.tmp"))
        assert not list(state.glob("memory.corrupt-*.json"))
        assert not (state / "memory.previous.json").exists()
        assert (state / "notes.txt").read_bytes() == b"unrelated"


@pytest.mark.parametrize("kind", ["backup_bytes", "corrupt_bytes", "corrupt_count", "temp_bytes", "temp_count"])
def test_excess_history_preserves_data_and_leaves_management_available(tmp_path, kind):
    def prepare(state):
        seed(state, [event()])
        if kind == "backup_bytes":
            (state / "memory.previous.json").write_bytes(b"x" * (8 * MIB + 1))
        elif kind == "corrupt_bytes":
            recovery_file(state, 1, 8 * MIB)
            recovery_file(state, 2, 8 * MIB + 1)
        elif kind == "corrupt_count":
            for index in range(11):
                recovery_file(state, index)
        elif kind == "temp_bytes":
            temp_file(state, 1, 8 * MIB + 1)
        else:
            for index in range(33):
                temp_file(state, index)

    with launched(tmp_path / kind, before_start=prepare) as (client, state):
        before = owned_files(state)
        status = client.request("/api/memory/status")[1]
        assert status["count"] == 1 and status["recoveryRequired"] is False
        assert status["history"]["overLimit"] is True
        assert client.request("/api/memory/events")[1]["events"][0]["id"] == event()["id"]
        assert len(client.request("/api/memory/export")[1]["events"]) == 1
        for path, method, body in [
            ("/api/memory/events", "POST", event(1)),
            ("/api/memory/events/" + event()["id"], "PUT", event()),
            ("/api/memory/import", "POST", {"data": {"events": [event(1)]}}),
            ("/api/memory/pause", "POST", {"paused": True}),
        ]:
            error(client, path, method, body, 413, "memory_history_limit_exceeded")
            assert owned_files(state) == before
        client.request("/api/memory/consent", "POST", {"consent": False})
        assert client.request("/api/memory/status")[1]["consent"] is False
        client.request("/api/memory/events", "DELETE")
        after = client.request("/api/memory/status")[1]
        assert after["count"] == 0 and after["consent"] is False
        assert after["history"]["overLimit"] is False
        assert after["history"]["corruptCount"] == after["history"]["tempCount"] == 0


def test_exact_history_count_limits_still_allow_writes(tmp_path):
    def prepare(state):
        seed(state)
        for index in range(10):
            recovery_file(state, index)
        for index in range(32):
            temp_file(state, index)

    with launched(tmp_path / "inclusive", before_start=prepare) as (client, _):
        assert client.request("/api/memory/events", "POST", event())[1]["accepted"] is True
        history = client.request("/api/memory/status")[1]["history"]
        assert history["corruptCount"] == 10 and history["tempCount"] == 32
        assert history["overLimit"] is False
        assert history["limits"]["maxTotalBytes"] == 40 * MIB
        assert history["limits"]["maxTransientBytes"] == 48 * MIB


@pytest.mark.parametrize("kind", ["count", "bytes"])
def test_unreadable_store_at_history_limit_can_start_opt_out_and_clear(tmp_path, kind):
    def prepare(state):
        seed(state)
        (state / "memory.json").write_bytes(b"{synthetic malformed original")
        if kind == "count":
            for index in range(10):
                recovery_file(state, index)
        else:
            recovery_file(state, 1, 8 * MIB)
            recovery_file(state, 2, 8 * MIB)

    with launched(tmp_path / kind, before_start=prepare) as (client, state):
        before = owned_files(state)
        status = client.request("/api/memory/status")[1]
        assert status["recoveryRequired"] is True
        assert status["recoveryReason"] == "VAS_MEMORY_HISTORY_LIMIT_EXCEEDED"
        error(client, "/api/memory/events", "POST", event(), 413, "memory_history_limit_exceeded")
        assert owned_files(state) == before
        client.request("/api/memory/consent", "POST", {"consent": False})
        assert (state / "memory.json").read_bytes() == b"{synthetic malformed original"
        client.request("/api/memory/events", "DELETE")
        status = client.request("/api/memory/status")[1]
        assert status["count"] == 0 and status["recoveryRequired"] is False
        assert status["consent"] is False
        assert not list(state.glob("memory.corrupt-*.json"))


def test_recovery_retains_two_distinct_originals_in_one_second(tmp_path):
    runner = tmp_path / "recover.ps1"
    runner.write_text(r"""param([string]$ModulePath, [string]$StateRoot)
$ErrorActionPreference = 'Stop'
Import-Module $ModulePath -Force
[IO.Directory]::CreateDirectory($StateRoot) | Out-Null
while ([DateTime]::UtcNow.Millisecond -gt 50) { Start-Sleep -Milliseconds 2 }
$times = @(); $names = @()
foreach ($label in @('FIRST_SYNTHETIC', 'SECOND_SYNTHETIC')) {
    [IO.File]::WriteAllText((Join-Path $StateRoot 'memory.json'), $label)
    $times += [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
    $names += (Initialize-VASMemoryStore $StateRoot).recoveredFrom
}
[ordered]@{ times=$times; names=$names } | ConvertTo-Json -Compress
""", encoding="utf-8-sig")
    result = subprocess.run([
        POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(runner),
        "-ModulePath", str(ROOT / "scripts/VAS.Memory.psm1"), "-StateRoot", str(tmp_path / "state"),
    ], capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    data = json.loads(result.stdout.decode("utf-8-sig"))
    assert len(set(data["times"])) == 1, "Fixture did not exercise the same-second recovery window"
    assert len(set(data["names"])) == 2
    assert [(tmp_path / "state" / name).read_text() for name in data["names"]] == [
        "FIRST_SYNTHETIC", "SECOND_SYNTHETIC",
    ]


@pytest.mark.parametrize("locked_name", ["memory.json", "memory.previous.json"])
def test_failed_delete_reports_failure_and_preserves_unremoved_history(tmp_path, locked_name):
    with launched(tmp_path / "locked", before_start=lambda p: seed(p, [event()])) as (client, state):
        (state / "memory.previous.json").write_bytes(b"previous original")
        recovery_file(state, 1)
        before = owned_files(state)
        locker = tmp_path / "lock.ps1"
        locker.write_text(r"""param([string]$Path)
$ErrorActionPreference = 'Stop'
$stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
try { [Console]::WriteLine('LOCKED'); [Console]::ReadLine() | Out-Null } finally { $stream.Dispose() }
""", encoding="utf-8-sig")
        process = subprocess.Popen([
            POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(locker),
            "-Path", str(state / locked_name),
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            assert process.stdout.readline().strip() == b"LOCKED"
            error(client, "/api/memory/events", "DELETE", None, 500)
            # Detect an already-held lock before committing or deleting anything.
            assert owned_files(state) == before
        finally:
            process.communicate(b"\n", timeout=10)
        client.request("/api/memory/events", "DELETE")
        assert client.request("/api/memory/status")[1]["count"] == 0
        assert not list(state.glob("memory.corrupt-*.json"))
        assert not (state / "memory.previous.json").exists()


def test_locked_expired_temp_never_blocks_opt_out_or_reads(tmp_path):
    with launched(tmp_path / "locked-temp", before_start=lambda p: seed(p, [event()])) as (client, state):
        orphan = temp_file(state, 1, hours=25)
        locker = tmp_path / "lock-temp.ps1"
        locker.write_text(r"""param([string]$Path)
$stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
try { [Console]::WriteLine('LOCKED'); [Console]::ReadLine() | Out-Null } finally { $stream.Dispose() }
""", encoding="utf-8-sig")
        process = subprocess.Popen([
            POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(locker), "-Path", str(orphan),
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            assert process.stdout.readline().strip() == b"LOCKED"
            assert client.request("/api/memory/consent", "POST", {"consent": False})[1]["consent"] is False
            status = client.request("/api/memory/status")[1]
            assert status["consent"] is False and status["history"]["tempCount"] == 1
            assert len(client.request("/api/memory/events")[1]["events"]) == 1
            assert len(client.request("/api/memory/export")[1]["events"]) == 1
            assert orphan.exists()
        finally:
            process.communicate(b"\n", timeout=10)
        assert client.request("/api/memory/status")[1]["history"]["tempCount"] == 0
        assert not orphan.exists()


def test_linked_state_is_rejected_before_runtime_or_memory_access(tmp_path):
    directory = tmp_path / "junction"
    directory.mkdir()
    target = directory / "owned-target"
    seed(target, [event()])
    (target / "memory.previous.json").write_bytes(b"recovery original")
    state_link = directory / "state"
    link_script = tmp_path / "junction.ps1"
    link_script.write_text("param([string]$Link,[string]$Target)\nNew-Item -ItemType Junction -Path $Link -Target $Target -ErrorAction Stop | Out-Null", encoding="utf-8-sig")
    subprocess.run([
        POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(link_script),
        "-Link", str(state_link), "-Target", str(target),
    ], check=True, capture_output=True, timeout=10)
    assert state_link.resolve() == target.resolve()
    assert target.resolve().is_relative_to(tmp_path.resolve())
    try:
        before = owned_files(target)
        with pytest.raises(AssertionError, match="VAS launcher failed"):
            with launched(directory):
                pytest.fail("Linked state must not start a runtime")
        assert owned_files(target) == before
        assert not list(target.glob("runtime-*.json"))
    finally:
        assert state_link.resolve() == target.resolve()
        os.rmdir(state_link)  # Remove only this verified junction, never its target tree.
    assert (target / "memory.previous.json").read_bytes() == b"recovery original"
