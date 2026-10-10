"""Real HTTP regressions for server-owned memory consent, bounds and idleness."""
import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
from contextlib import contextmanager

import pytest

from test_windows_runtime import POWERSHELL, RuntimeClient, run_launcher

pytestmark = pytest.mark.skipif(
    os.name != "nt" or not shutil.which("powershell.exe"),
    reason="Windows PowerShell required",
)
MAX_EVENTS = 10_000
MAX_BYTES = 8_388_608
STAMP = "2026-10-11T00:00:00.0000000Z"


def event(index=0, payload=None):
    return {
        "v": 1, "id": f"{index:032x}", "type": "policy.fixture",
        "source": "vas", "projectId": "", "timestamp": STAMP,
        "payload": payload or {"note": "Synthetic control"}, "feedback": None,
    }


def seed(state, events=(), consent=True, paused=False, omit_consent=False):
    state.mkdir(parents=True, exist_ok=True)
    store = {
        "version": 1, "paused": paused, "updatedAt": STAMP,
        "retention": "until-explicit-delete", "events": list(events),
    }
    raw = json.dumps(store, ensure_ascii=False, separators=(",", ":")).encode()
    (state / "memory.json").write_bytes(raw)
    control = state / "memory-consent.json"
    if omit_consent:
        control.unlink(missing_ok=True)
    else:
        control.write_text(json.dumps({"version": 1, "consent": consent}), encoding="utf-8")
    return raw


@contextmanager
def launched(directory, idle=120, before_start=None):
    root, state = directory / "root", directory / "state"
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(exist_ok=True)
    (root / "src/vas-hub.html").write_text("<!doctype html><title>Policy fixture</title>")
    if before_start:
        before_start(state)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    client = RuntimeClient(run_launcher(root, state, port, idle=idle))
    try:
        yield client, state
    finally:
        try:
            client.request("/api/shutdown", "POST", {})
        except (urllib.error.URLError, OSError):
            pass


@pytest.fixture(scope="module")
def runtime(tmp_path_factory):
    with launched(tmp_path_factory.mktemp("memory-policy")) as instance:
        yield instance


def error(client, path, method, data, status, code=None):
    with pytest.raises(urllib.error.HTTPError) as failure:
        client.request(path, method, data)
    with failure.value as response:
        assert response.code == status
        payload = json.loads(response.read())
    if code:
        assert payload["code"] == code


def memory_files(state):
    """Compare current, backup, quarantine and temp files after rejected writes."""
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in state.iterdir()
        if p.is_file() and (p.name.startswith("memory") or p.name.startswith(".memory"))
    }


def test_new_store_defaults_off_and_reports_server_limits(tmp_path):
    with launched(tmp_path / "fresh") as (client, state):
        error(client, "/api/memory/events", "POST", event(), 403, "memory_consent_required")
        _, status, _ = client.request("/api/memory/status")
        assert status["consent"] is False
        assert status["count"] == 0
        assert status["recoveryRequired"] is False
        assert status["limits"] == {"maxEvents": MAX_EVENTS, "maxBytes": MAX_BYTES}
        control = state / "memory-consent.json"
        if control.exists():
            assert json.loads(control.read_text("utf-8-sig"))["consent"] is False


@pytest.mark.parametrize("consent,omit", [(None, True), ("true", False), (1, False), (None, False)])
def test_missing_or_non_boolean_control_never_authorizes_writes(runtime, consent, omit):
    client, state = runtime
    seed(state, [event()], consent=consent, omit_consent=omit)
    _, status, _ = client.request("/api/memory/status")
    assert status["consent"] is False
    before = memory_files(state)
    for path, method, body in [
        ("/api/memory/events", "POST", event(1)),
        ("/api/memory/events/" + event()["id"], "PUT", event()),
        ("/api/memory/import", "POST", {"mode": "replace", "data": {"events": [event(1)]}}),
    ]:
        error(client, path, method, body, 403, "memory_consent_required")
    assert memory_files(state) == before


def test_legacy_embedded_true_cannot_authorize_without_separate_control(runtime):
    client, state = runtime
    seed(state, [event()], omit_consent=True)
    path = state / "memory.json"
    store = json.loads(path.read_text())
    store["consent"] = True
    path.write_text(json.dumps(store), encoding="utf-8")
    before = memory_files(state)
    assert client.request("/api/memory/status")[1]["consent"] is False
    error(client, "/api/memory/events", "POST", event(1), 403, "memory_consent_required")
    error(client, "/api/memory/import", "POST", {"data": {"events": [event(1)]}},
          403, "memory_consent_required")
    assert memory_files(state) == before


@pytest.mark.parametrize("raw", [
    b"{", b"[]", b'{"consent":true}', b'{"version":2,"consent":true}',
    b'{"version":1,"consent":true,"note":"' + b"x" * 1024 + b'"}',
], ids=["broken", "array", "missing-version", "wrong-version", "oversized"])
def test_malformed_consent_control_fails_closed_and_explicit_enable_repairs(runtime, raw):
    client, state = runtime
    original = seed(state, [event()])
    control = state / "memory-consent.json"
    control.write_bytes(raw)
    assert client.request("/api/memory/status")[1]["consent"] is False
    before = memory_files(state)
    error(client, "/api/memory/events", "POST", event(1), 403, "memory_consent_required")
    assert memory_files(state) == before
    client.request("/api/memory/consent", "POST", {"consent": True})
    assert json.loads(control.read_text("utf-8-sig")) == {"version": 1, "consent": True}
    assert (state / "memory.json").read_bytes() == original
    assert client.request("/api/memory/events", "POST", event(1))[1]["accepted"] is True


@pytest.mark.parametrize("value", ["true", "false", 1, 0, None, [], {}])
def test_consent_endpoint_rejects_non_boolean_without_mutation(runtime, value):
    client, state = runtime
    seed(state, consent=False)
    before = memory_files(state)
    error(client, "/api/memory/consent", "POST", {"consent": value}, 400)
    assert memory_files(state) == before


def test_persisted_consent_revocation_blocks_direct_writes_but_allows_control(runtime):
    client, state = runtime
    seed(state, consent=False)
    client.request("/api/memory/consent", "POST", {"consent": True})
    assert json.loads((state / "memory-consent.json").read_text("utf-8-sig"))["consent"] is True
    _, created, _ = client.request("/api/memory/events", "POST", event())
    assert created["accepted"] is True
    event_id = created["event"]["id"]
    client.request("/api/memory/consent", "POST", {"consent": False})
    before = memory_files(state)
    for path, method, body in [
        ("/api/memory/events", "POST", event(1)),
        ("/api/memory/events/" + event_id, "PUT", event()),
        ("/api/memory/import", "POST", {"data": {"events": [event(1)]}}),
    ]:
        error(client, path, method, body, 403, "memory_consent_required")
    assert memory_files(state) == before
    assert client.request("/api/memory/events")[1]["events"][0]["id"] == event_id
    assert client.request("/api/memory/export")[1]["events"][0]["id"] == event_id
    assert client.request("/api/memory/events/" + event_id, "DELETE")[1]["removed"] is True
    client.request("/api/memory/events", "DELETE")
    assert client.request("/api/memory/status")[1]["count"] == 0


def test_pause_stops_automatic_add_but_allows_explicit_consented_import(runtime):
    client, state = runtime
    seed(state, consent=True, paused=True)
    before = memory_files(state)
    _, result, _ = client.request("/api/memory/events", "POST", event())
    assert result["accepted"] is False and result["paused"] is True
    assert memory_files(state) == before
    _, imported, _ = client.request("/api/memory/import", "POST", {"data": {"events": [event()]}})
    assert imported["total"] == 1
    assert client.request("/api/memory/status")[1]["paused"] is True


def test_cumulative_count_limit_preserves_files_and_allows_duplicate_merge(runtime):
    client, state = runtime
    seed(state, (event(i) for i in range(MAX_EVENTS)))
    (state / "memory.previous.json").write_bytes(b"Synthetic prior state")
    (state / "memory.corrupt-fixture.json").write_bytes(b"Synthetic quarantine")
    (state / ".memory-fixture.tmp").write_bytes(b"Synthetic temporary history")
    before = memory_files(state)
    error(client, "/api/memory/events", "POST", event(MAX_EVENTS), 413, "memory_limit_exceeded")
    error(client, "/api/memory/import", "POST", {"data": {"events": [event(MAX_EVENTS)]}},
          413, "memory_limit_exceeded")
    assert memory_files(state) == before
    _, result, _ = client.request("/api/memory/import", "POST", {"data": {"events": [event(0)]}})
    assert result["total"] == MAX_EVENTS


def test_replace_over_count_limit_does_not_purge_existing_history(runtime):
    client, state = runtime
    seed(state, [event()])
    (state / "memory.previous.json").write_bytes(b"Synthetic prior state")
    (state / "memory.corrupt-fixture.json").write_bytes(b"Synthetic quarantine")
    (state / ".memory-fixture.tmp").write_bytes(b"Synthetic temporary history")
    before = memory_files(state)
    incoming = [{"id": f"{i:032x}", "type": "policy.fixture"} for i in range(MAX_EVENTS + 1)]
    body = {"mode": "replace", "data": {"events": incoming}}
    assert len(json.dumps(body).encode()) < 2_097_152
    error(client, "/api/memory/import", "POST", body, 413, "memory_limit_exceeded")
    assert memory_files(state) == before


@pytest.mark.parametrize("method", ["add", "update", "merge"])
def test_utf8_serialized_byte_limit_precedes_any_history_changes(runtime, method):
    client, state = runtime
    # Below the byte limit on disk, with each individual string below the 4K trim.
    old = event(0, {"notes": ["가" * 3900] * 670})
    original = seed(state, [old])
    assert len(original) < MAX_BYTES
    (state / "memory.previous.json").write_bytes(b"Synthetic prior state")
    (state / "memory.corrupt-fixture.json").write_bytes(b"Synthetic quarantine")
    (state / ".memory-fixture.tmp").write_bytes(b"Synthetic temporary history")
    before = memory_files(state)
    extra = event(1, {"notes": ["가" * 3900] * 50})
    if method == "add":
        path, verb, body = "/api/memory/events", "POST", extra
    elif method == "update":
        # Preserve the large prior event and grow another event via PUT.
        original = seed(state, [old, event(1)])
        assert len(original) < MAX_BYTES
        before = memory_files(state)
        path, verb, body = "/api/memory/events/" + event(1)["id"], "PUT", extra
    else:
        # A small merge request exercises stored bytes, not the HTTP request cap.
        path, verb, body = "/api/memory/import", "POST", {"data": {"events": [extra]}}
    assert len(json.dumps(body).encode()) < 2_097_152
    error(client, path, verb, body, 413, "memory_limit_exceeded")
    assert memory_files(state) == before


@pytest.mark.parametrize("kind", ["bytes", "count"])
def test_oversized_legacy_store_starts_without_quarantine_and_can_be_cleared(tmp_path, kind):
    original = None

    def prepare(state):
        nonlocal original
        if kind == "bytes":
            original = seed(state, [event(0, {"notes": ["가" * 3900] * 730})])
            assert len(original) > MAX_BYTES
        else:
            original = seed(state, (event(i) for i in range(MAX_EVENTS + 1)))

    with launched(tmp_path / kind, before_start=prepare) as (client, state):
        _, status, _ = client.request("/api/memory/status")
        assert status["consent"] is False and status["paused"] is True
        assert status["count"] is None and status["recoveryRequired"] is True
        before = memory_files(state)
        for path in ["/api/memory/events", "/api/memory/export"]:
            error(client, path, "GET", None, 413, "memory_limit_exceeded")
        error(client, "/api/memory/consent", "POST", {"consent": True}, 413, "memory_limit_exceeded")
        assert memory_files(state) == before
        assert (state / "memory.json").read_bytes() == original
        assert not list(state.glob("memory.corrupt-*.json"))
        # Revocation must remain available even when reading events is refused.
        client.request("/api/memory/consent", "POST", {"consent": False})
        assert (state / "memory.json").read_bytes() == original
        assert {k: v for k, v in memory_files(state).items() if k != "memory-consent.json"} == {
            k: v for k, v in before.items() if k != "memory-consent.json"
        }
        for path, method, body in [
            ("/api/memory/events", "POST", event(1)),
            ("/api/memory/events/" + event()["id"], "PUT", event()),
            ("/api/memory/import", "POST", {"data": {"events": [event(1)]}}),
        ]:
            error(client, path, method, body, 403, "memory_consent_required")
        client.request("/api/memory/events", "DELETE")
        _, cleared, _ = client.request("/api/memory/status")
        assert cleared["consent"] is False and cleared["count"] == 0
        assert cleared["recoveryRequired"] is False
        assert not (state / "memory.previous.json").exists()
        assert not list(state.glob("memory.corrupt-*.json"))


def test_exact_byte_boundary_can_revoke_without_rewriting_event_store(runtime, tmp_path):
    client, state = runtime
    seed(state, [event(0, {"note": ""})])
    # Match PowerShell's actual serialized representation, not padded whitespace.
    # An embedded true -> false rewrite would add one byte at this exact boundary.
    helper = tmp_path / "exact-memory-size.ps1"
    helper.write_text("""param([string]$Path, [int]$Target)
$ErrorActionPreference = 'Stop'
$store = [IO.File]::ReadAllText($Path) | ConvertFrom-Json
$store | Add-Member -NotePropertyName consent -NotePropertyValue $true
$json = $store | ConvertTo-Json -Depth 20
$remaining = $Target - [Text.Encoding]::UTF8.GetByteCount($json)
$store.events[0].payload.note = 'x' * $remaining
$json = $store | ConvertTo-Json -Depth 20
if ([Text.Encoding]::UTF8.GetByteCount($json) -ne $Target) { throw 'Fixture byte mismatch' }
[IO.File]::WriteAllText($Path, $json, (New-Object Text.UTF8Encoding($false)))
""", encoding="utf-8")
    subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(helper),
                    "-Path", str(state / "memory.json"), "-Target", str(MAX_BYTES)],
                   check=True, capture_output=True, timeout=20)
    assert (state / "memory.json").stat().st_size == MAX_BYTES
    before = memory_files(state)
    _, result, _ = client.request("/api/memory/consent", "POST", {"consent": False})
    assert result["consent"] is False
    after = memory_files(state)
    assert {k: v for k, v in after.items() if k != "memory-consent.json"} == {
        k: v for k, v in before.items() if k != "memory-consent.json"
    }
    error(client, "/api/memory/events", "POST", event(1), 403, "memory_consent_required")
    assert memory_files(state) == after


def test_consent_grant_and_revocation_survive_runtime_restart(tmp_path):
    directory = tmp_path / "restart"
    with launched(directory) as (first, state):
        first.request("/api/memory/consent", "POST", {"consent": True})
        first.request("/api/memory/events", "POST", event())
    with launched(directory) as (second, _):
        assert second.request("/api/memory/status")[1]["consent"] is True
        assert second.request("/api/memory/status")[1]["count"] == 1
        original = (state / "memory.json").read_bytes()
        second.request("/api/memory/consent", "POST", {"consent": False})
        assert (state / "memory.json").read_bytes() == original
    with launched(directory) as (third, _):
        assert third.request("/api/memory/status")[1]["consent"] is False
        assert third.request("/api/memory/status")[1]["count"] == 1
        error(third, "/api/memory/events", "POST", event(1), 403, "memory_consent_required")
        assert (state / "memory.json").read_bytes() == original


def test_public_and_rejected_requests_cannot_keep_runtime_alive(tmp_path):
    with launched(tmp_path / "public-idle", idle=3) as (client, _):
        client.request("/api/heartbeat", "POST", {})
        deadline = time.monotonic() + 8
        stopped = False
        while time.monotonic() < deadline:
            try:
                client.request("/health", auth=False)
                client.request("/src/vas-hub.html", auth=False)
                for kwargs in [{"auth": False}, {"origin": "https://foreign.example"}]:
                    try:
                        client.request("/api/heartbeat", "POST", {}, **kwargs)
                    except urllib.error.HTTPError as denied:
                        assert denied.code in (401, 403)
                        denied.close()
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                stopped = True
                break
            time.sleep(0.15)
        assert stopped, "Public traffic or rejected credentials extended the idle deadline"


def test_authenticated_heartbeat_keeps_runtime_alive_until_it_stops(tmp_path):
    with launched(tmp_path / "authenticated-idle", idle=3) as (client, _):
        started = time.monotonic()
        while time.monotonic() - started < 4:
            assert client.request("/api/heartbeat", "POST", {})[0] == 200
            time.sleep(0.3)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                client.request("/health", auth=False)
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                break
            time.sleep(0.15)
        else:
            pytest.fail("Runtime did not expire after authenticated activity stopped")
