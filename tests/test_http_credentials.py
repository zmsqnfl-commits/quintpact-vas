"""Shared HTTP credential boundary with ordinary references as controls."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from vas_ai_contract import clean
from vas_sanitize_export import sanitize_export

CONTROLS = [
    'https://example.com/home/design',
    'https://example.com/@icons/name',
    'https://example.com/?q=user@localhost',
    'Preserve React and #123abc; Authorization support is required.',
    '{ "tokens": {"primary": "#123abc"}, "reference": "https://example.com/design" }',
    '{"reference":"https://example.com","label":"user@localhost"}',
    '{"reference":"https://example.com","theme":"@botanical"}',
]


@pytest.mark.parametrize('value', CONTROLS)
def test_public_content_retains_exact_bytes(value):
    assert clean(value) == value
    code = 'global.window=globalThis; require(process.argv[1]); process.stdout.write(VASAgentContract.clean(process.argv[2]));'
    output = subprocess.run(['node', '-e', code, str(ROOT / 'src/agent-contract.js'), value], capture_output=True, text=True, check=True)
    assert output.stdout == value


def test_empty_header_preserves_following_requirement_in_both_cleaners():
    value = 'Authorization:\nFeature: calendar'
    assert clean(value) == '[redacted]\nFeature: calendar'
    code = 'global.window=globalThis; require(process.argv[1]); process.stdout.write(VASAgentContract.clean(process.argv[2]));'
    assert subprocess.run(['node', '-e', code, str(ROOT / 'src/agent-contract.js'), value], capture_output=True, text=True, check=True).stdout == clean(value)


def test_compatibility_staging_removes_all_http_variants(tmp_path):
    cases = json.loads((ROOT / 'tests/fixtures/secret-redaction-cases.json').read_text(encoding='utf-8'))
    selected = [case for case in cases if case['name'].startswith(('HTTP ', 'URI '))]
    payload = {'inputs': [case['input'] for case in selected], 'reference': CONTROLS[0], 'tokens': {'primary': '#123abc'}}
    names = ['project.json', 'requirements.json', 'design-tokens.json', 'rag-context.json']
    for name in names:
        (tmp_path / name).write_text(json.dumps(payload), encoding='utf-8')
    sanitize_export(tmp_path)
    for name in names:
        raw = (tmp_path / name).read_text(encoding='utf-8')
        for case in selected:
            assert case['marker'] not in raw, case['name']
        assert 'ResponseCanary987654321' not in raw
        safe = json.loads(raw)
        assert safe['reference'] == CONTROLS[0]
        assert safe['tokens']['primary'] == '#123abc'
