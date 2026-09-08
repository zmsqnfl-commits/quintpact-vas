"""Synthetic regressions for handoff confidentiality, deletion and local fonts."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
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
    if case.get('control'):
        assert case['control'] in text
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


@pytest.mark.parametrize('name,original', [
    ('config.json', '{ "tokens": {"primary": "#123abc"}, "reference": "https://example.com/home/design" }\n'),
    ('config.py', 'config["theme"] = "bento"\n'),
    ('config.xml', '<tokens><primary>#123abc</primary></tokens>\n'),
])
def test_safe_json_source_keeps_exact_excerpt_bytes(tmp_path, name, original):
    assert clean(original) == original.strip()
    (tmp_path / name).write_text(original, encoding="utf-8")
    target = tmp_path.parent / (tmp_path.name + "-safe.zip")
    export_package({"source":str(tmp_path),"task":{"request":"review config"},"format":"source-zip","approvedFiles":[name],"output":str(target)})
    with zipfile.ZipFile(target) as archive:
        assert archive.read("excerpts/0001.txt") == ("[Lines 1-1]\n" + original).encode()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_project_knowledge_strips_whole_credentials_before_chunking(case, tmp_path):
    from vas_project_knowledge import redact_text, chunks
    text = redact_text(case['input'], tmp_path)
    output = json.dumps(chunks(text))
    assert case['marker'] not in output
    if case.get('control'):
        assert case['control'] in text
    # Embedded object assignments intentionally fail closed as a whole string.
    assert redact_text('Preserve React and #123abc', tmp_path) == 'Preserve React and #123abc'


def test_document_search_excludes_archived_operating_instructions(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location('index_builder', ROOT / 'scripts/build-knowledge-index.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    for name in ['docs/OPERATIONS.md', 'docs/log-archive-2025.md', 'docs/releases/2.0.md', 'docs/verification/README.md']:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('# Instructions\nExample', encoding='utf-8')
    assert [p.relative_to(tmp_path).as_posix() for p in builder.source_files(tmp_path)] == ['docs/OPERATIONS.md']


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


def test_windows_memory_filters_shared_credentials_on_write_and_legacy_export(runtime):
    client, state, _ = runtime
    client.request('/api/memory/events', 'DELETE')
    client.request('/api/memory/pause', 'POST', {'paused': False})
    for case in CASES:
        _, result, _ = client.request('/api/memory/events', 'POST', {
            'type': 'theme_selected', 'payload': {'preset': 'bento', 'note': case['input']}})
        assert case['marker'] not in json.dumps(result), case['name']
        assert result['event']['payload']['preset'] == 'bento'
    # A historical store is read through the same boundary before it can be shared.
    store = json.loads((state / 'memory.json').read_text(encoding='utf-8-sig'))
    for event, case in zip(store['events'], CASES):
        event['payload']['note'] = case['input']
        event['source'] = 'sk-' + 'MetadataCanary' * 2
        event['projectId'] = 'sk-' + 'MetadataCanary' * 2
    (state / 'memory.json').write_text(json.dumps(store), encoding='utf-8-sig')
    _, exported, _ = client.request('/api/memory/export')
    raw = json.dumps(exported)
    assert 'MetadataCanary' not in raw
    for case in CASES:
        assert case['marker'] not in raw, case['name']
    assert 'bento' in raw
    client.request('/api/memory/events', 'DELETE')


def test_windows_memory_private_keys_and_portable_id_merge(runtime):
    client, state, _ = runtime
    client.request('/api/memory/events', 'DELETE')
    client.request('/api/memory/pause', 'POST', {'paused': False})
    keys = json.loads((ROOT / 'tests/fixtures/private-memory-keys.json').read_text())
    payload = {'preset': 'bento', 'nested': [{key: 'value' for key in keys}]}
    payload.update({key: 'value' for key in keys})
    ids = ['7a43c52f-45a2-4ee8-b88f-0aba339aff67', 'event-legacy-1']
    data = {'schema': 1, 'events': [{'id': id, 'type': 'theme_selected', 'payload': payload} for id in ids]}
    expected_ids = [ids[0].replace('-', ''), hashlib.sha256(('vas-memory-id:' + ids[1]).encode()).hexdigest()[:32]]
    for _ in range(2):
        _, imported, _ = client.request('/api/memory/import', 'POST', {'data': data})
        assert imported['total'] == 2
    _, exported, _ = client.request('/api/memory/export')
    assert exported['schema'] == exported['version'] == 1
    assert [event['id'] for event in exported['events']] == expected_ids
    for event in exported['events']:
        assert event['payload'] == {'preset': 'bento', 'nested': [{}]}
        client.request('/api/memory/events/' + event['id'], 'PUT', {'type': 'theme_selected', 'payload': {'preset': 'linear'}})
    # Real Windows export merges back into the original browser-side identities.
    code = '''
const fs = require('fs'); require(process.argv[1]);
(async () => {
 const [original, windows] = JSON.parse(fs.readFileSync(0, 'utf8'));
 await VASPersonalization.consent(true); await VASPersonalization.import(original);
 await VASPersonalization.import(windows); await VASPersonalization.import(windows);
 console.log((await VASPersonalization.list()).length);
})().catch(error => { console.error(error); process.exit(1); });
'''
    result = subprocess.run(['node', '-e', code, str(ROOT / 'src/personalization-store.js')], input=json.dumps([data, exported]), text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '2'
    # A seeded historical key receives the same filtering at the export boundary.
    store = json.loads((state / 'memory.json').read_text(encoding='utf-8-sig'))
    for event in store['events']: event['payload'] = payload
    (state / 'memory.json').write_text(json.dumps(store), encoding='utf-8-sig')
    _, historical, _ = client.request('/api/memory/export')
    for event in historical['events']:
        assert event['payload'] == {'preset': 'bento', 'nested': [{}]}
        client.request('/api/memory/events/' + event['id'], 'DELETE')
    _, status, _ = client.request('/api/memory/status')
    assert status['count'] == 0


@pytest.mark.skipif(os.name != 'nt', reason='Windows PowerShell required')
def test_memory_dictionary_and_psobject_preserve_arrays_and_filter_keys(tmp_path):
    script = tmp_path / 'privacy.ps1'
    script.write_text('''
. $env:VAS_PRIVACY_SOURCE
$keys = Get-Content -LiteralPath $env:VAS_PRIVATE_KEYS -Raw | ConvertFrom-Json
$dictionary = [ordered]@{ preset = 'bento'; count = 2; enabled = $true; empty = $null; list = @('linear'); many = @(1, 2) }
foreach ($key in $keys) { $dictionary[$key] = 'value' }
$object = $dictionary | ConvertTo-Json -Depth 10 | ConvertFrom-Json
@((ConvertTo-VASSafeValue $dictionary), (ConvertTo-VASSafeValue $object)) | ConvertTo-Json -Depth 10 -Compress
''', encoding='utf-8-sig')
    env = dict(os.environ, VAS_PRIVACY_SOURCE=str(ROOT / 'scripts/VAS.Memory.Privacy.ps1'), VAS_PRIVATE_KEYS=str(ROOT / 'tests/fixtures/private-memory-keys.json'))
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    control = {'preset': 'bento', 'count': 2, 'enabled': True, 'empty': None, 'list': ['linear'], 'many': [1, 2]}
    assert json.loads(result.stdout) == [control, control]
