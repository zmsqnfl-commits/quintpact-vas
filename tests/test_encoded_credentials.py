"""Detection-only encoded credentials at handoff and both memory boundaries."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from vas_ai_contract import clean, credential_view, sanitize

CASES = [case for case in json.loads((ROOT / 'tests/fixtures/secret-redaction-cases.json').read_text(encoding='utf-8'))
         if case['name'].startswith('encoded boundary ')]
KEYS = [r'pass\u0077ord', r'pass\x77ord', 'pass%77ord', 'pass%2577ord', 'pass&#119;ord',
        'pass&amp;#119;ord', 'ｐａｓｓｗｏｒｄ', 'pass\u200bword']
CONTROLS = ['design%3aminimal; retryCount=3', r'label\u003aOcean', 'heading&#58;Hello',
            'label&colon;Ocean', 'ｔｏｋｅｎｓ: blue', '설명\u200b문자',
            "'hello' /* 'ignored' */ + 'world'", '{ "tokens": { "primary": "#123abc" } }',
            'https://example.com/?q=design%3Aminimal', 'label%FF &#x110000; &#999999999999999999999;',
            'API support%3a requested\r\nKeep calendar', 'label=&quot;Ocean blue&quot;',
            'label=%22Ocean blue%22', r'label=\u0022Ocean blue\u0022',
            "sample = 'hello' r'world'", "sample = br'hello' RB'world'", "sample = f'hello {name}' r'world'"]
MEMORY_CONTROLS = CONTROLS[:8] + CONTROLS[11:]  # Existing memory policy excludes URLs/file-like strings.
PATH_CONTROL = 'Keep calendar\nunc=' + r'\\server\share\customer.txt' + '\nwindows=' + r'C:\Users\alice\settings.json' + '\nKeep keyboard navigation'


def key_payload():
    return {'preset': 'bento', 'tokens': {'primary': '#123abc'}, 'nested': [{key: 'KeyCanaryEncodedStage4' for key in KEYS}],
            **{key: 'KeyCanaryEncodedStage4' for key in KEYS}}


def test_python_decoding_is_bounded_and_preserves_public_originals():
    assert credential_view('design%253aOcean') == 'design:Ocean'
    assert credential_view('design%25253aOcean') == 'design%3aOcean'
    for value in CONTROLS:
        assert clean(value) == value.replace('\r\n', '\n')
    assert sanitize(key_payload()) == {'preset': 'bento', 'tokens': {'primary': '#123abc'}, 'nested': [{}]}
    for case in CASES:
        assert case['marker'] not in clean(case['input']), case['name']
        assert clean(clean(case['input'])) == clean(case['input'])


def test_unc_paths_are_masked_without_discarding_unrelated_requirements():
    assert credential_view(r'\\server\share\customer.txt') == r'\\server\share\customer.txt'
    expected = 'Keep calendar\nunc=[absolute-path]\nwindows=[absolute-path]\nKeep keyboard navigation'
    assert clean(PATH_CONTROL) == expected
    code = 'global.window=globalThis; require(process.argv[1]); process.stdout.write(VASAgentContract.clean(process.argv[2]));'
    output = subprocess.run(['node', '-e', code, str(ROOT / 'src/agent-contract.js'), PATH_CONTROL],
                            capture_output=True, text=True, check=True)
    assert output.stdout == expected


@pytest.mark.parametrize('value', ['password%253aEncodedCanaryStage4Sensitive',
                                  'password=&#34;alpha beta EncodedCanaryStage4Sensitive&#34;',
                                  'password=&amp;quot;EncodedCanaryStage4Sensitive&amp;quot;',
                                  "sample = 'sk-' r'EncodedCanaryStage4Sensitive'"])
def test_cli_export_strips_encoded_credentials_and_keeps_unrelated_requirements(tmp_path, value):
    source = tmp_path / 'source'
    source.mkdir()
    output = tmp_path / 'handoff.json'
    request = {'source': str(source), 'output': str(output), 'format': 'json', 'inputReviewAcknowledged': True,
               'task': {'request': value,
                        'constraints': ['Keep calendar keyboard navigation.']}}
    request_file = tmp_path / 'request.json'
    request_file.write_text(json.dumps(request), encoding='utf-8')
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/vas_agent_handoff.py'), 'export', '--request', str(request_file)],
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
    raw = output.read_text(encoding='utf-8')
    assert 'EncodedCanaryStage4Sensitive' not in raw
    document = json.loads(raw)
    assert 'Keep calendar keyboard navigation.' in document['assistantGuide']['pasteText']
    assert document['task']['request'] == '[redacted]'


def test_javascript_cleaner_and_memory_handle_encoded_values_and_keys():
    code = r'''
const fs = require('fs'); global.window = globalThis;
require(process.argv[1] + '/src/agent-contract.js');
require(process.argv[1] + '/src/personalization-store.js');
(async () => {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  await VASPersonalization.consent(true);
  const records = [];
  for (const value of input.values.concat(input.memoryControls)) {
    records.push(await VASPersonalization.record('theme_selected', { preset: 'bento', note: value }));
  }
  const keyed = await VASPersonalization.record('theme_selected', input.keys);
  process.stdout.write(JSON.stringify({
    clean: input.values.map(value => VASAgentContract.clean(value)),
    controls: input.controls.map(value => VASAgentContract.clean(value)),
    keys: VASAgentContract.sanitize(input.keys), records, keyed
  }));
})().catch(error => { console.error(error); process.exit(1); });
'''
    payload = {'values': [case['input'] for case in CASES], 'controls': CONTROLS,
               'memoryControls': MEMORY_CONTROLS, 'keys': key_payload()}
    result = subprocess.run(['node', '-e', code, str(ROOT)], input=json.dumps(payload), text=True,
                            encoding='utf-8', capture_output=True, check=True)
    output = json.loads(result.stdout)
    assert output['controls'] == [clean(value) for value in CONTROLS]
    assert output['keys'] == sanitize(key_payload())
    assert 'KeyCanaryEncodedStage4' not in json.dumps(output['keyed'])
    for case, handoff, memory in zip(CASES, output['clean'], output['records']):
        assert case['marker'] not in json.dumps([handoff, memory]), case['name']
        assert memory['payload']['preset'] == 'bento'
    for value, memory in zip(MEMORY_CONTROLS, output['records'][len(CASES):]):
        assert memory['payload']['note'] == value


@pytest.mark.skipif(os.name != 'nt' or not shutil.which('powershell.exe'), reason='Windows PowerShell required')
def test_windows_memory_dictionary_object_and_string_boundaries():
    code = '''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
. (Join-Path $env:VAS_ENCODED_ROOT 'scripts/VAS.Memory.Privacy.ps1')
$inputData = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:VAS_ENCODED_INPUT)) | ConvertFrom-Json
$dictionary = [ordered]@{ preset = 'bento'; count = 2 }
foreach ($key in $inputData.keys) { $dictionary[$key] = 'KeyCanaryEncodedStage4' }
$object = $dictionary | ConvertTo-Json | ConvertFrom-Json
@{ values = @($inputData.values | ForEach-Object { ConvertTo-VASSafeValue $_ });
   controls = @($inputData.controls | ForEach-Object { ConvertTo-VASSafeValue $_ });
   keys = @((ConvertTo-VASSafeValue $dictionary), (ConvertTo-VASSafeValue $object)) } | ConvertTo-Json -Depth 10 -Compress
'''
    payload = {'values': [case['input'] for case in CASES], 'controls': MEMORY_CONTROLS, 'keys': KEYS}
    env = dict(os.environ, VAS_ENCODED_ROOT=str(ROOT),
               VAS_ENCODED_INPUT=base64.b64encode(json.dumps(payload).encode()).decode())
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', base64.b64encode(code.encode('utf-16-le')).decode()],
                            env=env, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output['keys'] == [{'preset': 'bento', 'count': 2}] * 2
    assert output['controls'] == MEMORY_CONTROLS
    for case, value in zip(CASES, output['values']):
        assert case['marker'] not in value, case['name']
