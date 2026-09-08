"""Synthetic regressions for handoff confidentiality, deletion and local fonts."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import urllib.error
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vas_ai_contract import clean, normalize_handoff, build_prompt
from vas_agent_handoff import build_preview, export_package, UnsafeSelectionError
from test_windows_runtime import run_launcher, RuntimeClient
from test_handoff_contract import base_document

CASES = json.loads((ROOT / "tests/fixtures/secret-redaction-cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_python_handoff_and_source_export_block_json_credentials(case, tmp_path):
    text = clean(case["input"])
    assert case["marker"] not in text
    assert clean(text) == text
    request = {"source": str(tmp_path), "task": {"request": case["input"]}}
    built = build_preview(request)
    assert case["marker"] not in json.dumps(built["document"])
    assert case["marker"] not in built["pasteText"]
    (tmp_path / "config.json").write_text(case["input"], encoding="utf-8")
    with pytest.raises(UnsafeSelectionError):
        export_package({**request, "format": "source-zip", "approvedFiles": ["config.json"], "output": str(tmp_path / "out.zip")})


def test_legacy_normalization_sanitizes_nested_fields_before_hashing():
    document = base_document()
    document["schemaVersion"] = 2
    document["task"]["request"] = 'keep React {"password":"NestedCanarySecret"}'
    document["context"]["design"] = {"tokens": {"colors": {"primary": "#123abc"}, "api_key": "NestedCanarySecret"}}
    document["context"]["requirements"]["value"]["reference"] = "https://example.com/home/design"
    safe = normalize_handoff(document, build_prompt)
    assert "NestedCanarySecret" not in json.dumps(safe)
    assert safe["context"]["design"]["tokens"]["colors"]["primary"] == "#123abc"
    assert safe["context"]["requirements"]["value"]["reference"] == "https://example.com/home/design"
    payload = copy.deepcopy(safe)
    del payload["integrity"]
    payload["assistantGuide"]["pasteText"] = ""
    expected = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert safe["integrity"]["payloadSha256"] == expected


def test_safe_json_source_keeps_exact_excerpt_bytes(tmp_path):
    original = '{ "tokens": {"primary": "#123abc"}, "reference": "https://example.com/home/design" }\n'
    (tmp_path / "config.json").write_text(original, encoding="utf-8")
    target = tmp_path.parent / (tmp_path.name + "-safe.zip")
    export_package({"source":str(tmp_path),"task":{"request":"review config"},"format":"source-zip","approvedFiles":["config.json"],"output":str(target)})
    with zipfile.ZipFile(target) as archive:
        assert archive.read("excerpts/0001.txt") == ("[Lines 1-1]\n" + original).encode()


@pytest.fixture(scope="module")
def runtime(tmp_path_factory):
    if os.name != "nt" or not shutil.which("powershell.exe"):
        pytest.skip("Windows PowerShell required")
    directory = tmp_path_factory.mktemp("privacy-runtime")
    root, state = directory / "root", directory / "state"
    (root / "src/assets").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "src/vas-hub.html").write_text("<!doctype html><title>Fixture</title>", encoding="utf-8")
    font = ROOT / "src/proof-app/assets/BricolageGrotesque.ttf"
    shutil.copy2(font, root / "src/assets/font.ttf")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    details = run_launcher(root, state, port, idle=120)
    client = RuntimeClient(details)
    try:
        yield client, state, font
    finally:
        client.request("/api/shutdown", "POST", {})


@pytest.mark.parametrize("mode", ["single", "all", "replace", "corrupt", "corrupt-single"])
def test_explicit_deletion_removes_all_application_history_copies(runtime, mode):
    client, state, _ = runtime
    client.request("/api/memory/events", "DELETE")
    client.request("/api/memory/pause", "POST", {"paused": False})
    _, created, _ = client.request("/api/memory/events", "POST", {"type":"synthetic.test","payload":{"note":"DeletedHistoryCanary"}})
    _, survivor, _ = client.request("/api/memory/events", "POST", {"type":"synthetic.test","payload":{"note":"SurvivingHistoryControl"}})
    client.request("/api/memory/pause", "POST", {"paused": True})
    raw = (state / "memory.json").read_bytes()
    (state / "memory.corrupt-fixture.json").write_bytes(raw)
    (state / ".memory-fixture.tmp").write_bytes(raw)
    (state / "unrelated.json").write_text("UnrelatedFileControl")
    if mode == "single":
        client.request("/api/memory/events/" + created["event"]["id"], "DELETE")
    elif mode == "replace":
        client.request("/api/memory/import", "POST", {"mode":"replace","data":{"events":[survivor["event"]]}})
    else:
        if mode.startswith("corrupt"):
            (state / "memory.json").write_text('{"broken":"DeletedHistoryCanary"')
        if mode == "corrupt-single":
            with pytest.raises(urllib.error.HTTPError) as missing:
                client.request("/api/memory/events/" + created["event"]["id"], "DELETE")
            assert missing.value.code == 404
            missing.value.close()
        else:
            client.request("/api/memory/events", "DELETE")
    _, status, _ = client.request("/api/memory/status")
    assert status["count"] == (1 if mode in {"single","replace"} else 0)
    if not mode.startswith("corrupt"):
        assert status["paused"] is True
    assert not (state / "memory.previous.json").exists()
    assert not list(state.glob("memory.corrupt-*.json"))
    assert not list(state.glob(".memory-*.tmp"))
    assert "DeletedHistoryCanary" not in (state / "memory.json").read_text(encoding="utf-8-sig")
    assert (state / "unrelated.json").read_text() == "UnrelatedFileControl"
    if mode in {"single","replace"}:
        assert "SurvivingHistoryControl" in (state / "memory.json").read_text(encoding="utf-8-sig")


def test_ttf_is_served_as_font_but_not_readable_as_text(runtime):
    client, _, font = runtime
    status, body, headers = client.request("/src/assets/font.ttf", auth=False)
    assert status == 200 and headers["Content-Type"] == "font/ttf"
    assert hashlib.sha256(body).digest() == hashlib.sha256(font.read_bytes()).digest()
    with pytest.raises(urllib.error.HTTPError) as blocked:
        client.request("/api/files/read?scope=src&path=assets/font.ttf")
    assert blocked.value.code in {400, 404}
    blocked.value.close()


def test_failed_history_cleanup_does_not_report_success_or_replace_live_store(runtime):
    import ctypes
    from ctypes import wintypes

    client, state, _ = runtime
    client.request("/api/memory/events", "DELETE")
    client.request("/api/memory/pause", "POST", {"paused": False})
    client.request("/api/memory/events", "POST", {"type":"synthetic.test","payload":{"note":"CleanupFailureControl"}})
    before = (state / "memory.json").read_bytes()
    backup = state / "memory.previous.json"
    backup.write_bytes(before)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(backup), 0x80000000, 0, None, 3, 0, None)
    assert handle != wintypes.HANDLE(-1).value
    try:
        with pytest.raises(urllib.error.HTTPError) as failed:
            client.request("/api/memory/events", "DELETE")
        assert failed.value.code == 500
        failed.value.close()
        assert (state / "memory.json").read_bytes() == before
    finally:
        kernel.CloseHandle(handle)
    client.request("/api/memory/events", "DELETE")
    assert not backup.exists()
