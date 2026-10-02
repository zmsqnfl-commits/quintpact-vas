"""Reference semantics, browser/Python parity, and handoff v3 round trips."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from vas_agent_handoff import build_preview, export_package
from vas_ai_contract import build_prompt, finalize_handoff, normalize_handoff
from vas_design_reference import SAMPLE_KEYS, reference


def request(tmp_path, preset='bento', base=None, mode='partial'):
    design = {'included': True, 'preset': preset, 'tokens': {'fontFamily': 'system-ui', 'colors': {'primary': '#123abc'}}, 'direction': 'Use confirmed values'}
    if base:
        design['basePreset'] = base
    return {'source': str(tmp_path), 'projectName': 'synthetic', 'task': {'request': 'Change the action background',
            'designScope': {'mode': mode, 'scope': '주문 화면 / 확인 버튼 / 배경색' if mode == 'partial' else ''}},
            'context': {'design': design}}


@pytest.mark.parametrize('preset', sorted(SAMPLE_KEYS))
def test_known_sample_is_version_labelled_not_marked_inspected(tmp_path, preset):
    document = build_preview(request(tmp_path, preset))['document']
    design = document['context']['design']
    ref = design['visualReference']
    version = document['generatedBy']['version']
    assert ref['samplePreset'] == preset
    assert ref['status'] == 'unverified'
    assert ref['vasVersion'] == version
    assert ref['sourceRef'] == 'v' + version
    assert f'/blob/v{version}/src/design-sample.html' in ref['versionedSourceUrl']
    assert ref['liveSampleUrl'].endswith('?preset=' + preset)
    assert ref['liveSampleVersion'] == 'not-verified'
    text = document['assistantGuide']['pasteText']
    assert ref['liveSampleUrl'] in text
    assert '시각 참조 미확인' in text
    assert '외부 CDN·원격 폰트를 추가하지 마세요' in text
    assert 'fontFamily' in text
    assert document['inputReview']['required'] is False


def test_custom_base_scope_and_values_survive_export_and_normalization(tmp_path):
    values = request(tmp_path, 'custom', 'bento')
    document = build_preview(values)['document']
    design = document['context']['design']
    assert design['visualReference']['userModified'] is True
    assert design['visualReference']['samplePreset'] == 'bento'
    assert design['visualReference']['applicationScope'] == document['task']['designScope']
    assert design['tokens']['colors']['primary'] == '#123abc'
    assert '샘플과 달라도 확정 디자인 토큰을 따르세요' in document['assistantGuide']['pasteText']
    restored = normalize_handoff(copy.deepcopy(document), build_prompt)
    assert restored['context']['design'] == design
    assert restored['integrity']['payloadSha256'] == document['integrity']['payloadSha256']
    values['output'] = str(tmp_path / 'handoff.json')
    export_package(values)
    exported = json.loads(Path(values['output']).read_text(encoding='utf-8'))
    assert exported['context']['design'] == design
    changed = copy.deepcopy(document)
    changed['context']['design']['visualReference']['sourceRef'] = 'v0.0.1'
    finalize_handoff(changed, build_prompt)
    assert changed['integrity']['payloadSha256'] != document['integrity']['payloadSha256']


def test_preserve_has_no_new_style_instructions_or_sample(tmp_path):
    document = build_preview(request(tmp_path, 'custom', 'bento', mode='preserve'))['document']
    assert document['context']['design'] == {'included': False}
    text = document['assistantGuide']['pasteText']
    assert '기존 디자인 유지' in text
    for unwanted in ['Use confirmed values', '디자인 시각 참조', '확정 디자인 토큰', 'design-sample.html']:
        assert unwanted not in text


@pytest.mark.parametrize('preset,base', [('custom', None), ('custom', 'unknown'), ('vercel', None), ('unknown', None)])
def test_unknown_samples_do_not_invent_links(tmp_path, preset, base):
    document = build_preview(request(tmp_path, preset, base))['document']
    ref = document['context']['design']['visualReference']
    assert ref['samplePreset'] is None
    assert ref['versionedSourceUrl'] is None
    assert ref['liveSampleUrl'] is None
    assert '다른 스타일의 샘플로 대체하지 말고' in document['assistantGuide']['pasteText']


def test_browser_python_reference_parity_without_auto_network():
    node = shutil.which('node')
    assert node, 'node is required for reference parity'
    cases = [{'design': {'included': True, 'preset': key}, 'scope': {'mode': 'new', 'scope': ''}, 'version': '2.8.0'} for key in sorted(SAMPLE_KEYS)]
    cases.extend([
        {'design': {'included': True, 'preset': 'custom', 'basePreset': 'bento'}, 'scope': {'mode': 'partial', 'scope': '버튼 배경'}, 'version': '2.8.0'},
        {'design': {'included': True, 'preset': 'custom'}, 'scope': {'mode': 'redesign', 'scope': ''}, 'version': '2.8.0'},
        {'design': {'included': True, 'preset': 'unknown'}, 'scope': {'mode': 'new', 'scope': ''}, 'version': '2.8.0'},
        {'design': {'included': True, 'preset': 'bento'}, 'scope': {'mode': 'preserve', 'scope': ''}, 'version': '2.8.0'},
        {'design': {'included': False}, 'scope': {'mode': 'new', 'scope': ''}, 'version': '2.8.0'},
        {'design': {'included': True, 'preset': 'bento'}, 'scope': {'mode': 'new', 'scope': ''}, 'version': 'unversioned'},
    ])
    script = """global.window=globalThis;
require(process.argv[1]);
const cases=JSON.parse(require('fs').readFileSync(0,'utf8'));
console.log(JSON.stringify(cases.map(c=>VASDesignReference.reference(c.design,c.scope,c.version))));"""
    result = subprocess.run([node, '-e', script, str(ROOT / 'src/design-reference.js')], input=json.dumps(cases, ensure_ascii=False),
                            encoding='utf-8', capture_output=True, check=True)
    assert json.loads(result.stdout) == [reference(case['design'], case['scope'], case['version']) for case in cases]


def test_reference_metadata_reuse_does_not_trigger_sanitizer_review(tmp_path):
    values = request(tmp_path, 'custom', 'bento')
    first = build_preview(values)['document']
    values['context']['design'] = copy.deepcopy(first['context']['design'])
    second = build_preview(values)['document']
    assert second['context']['design'] == first['context']['design']
    assert second['inputReview']['required'] is False
