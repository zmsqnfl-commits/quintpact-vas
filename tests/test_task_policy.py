"""Scope, criteria and truthful quality metadata in the Python generator."""
import json
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vas_agent_handoff import build_preview, export_package, UnsafeSelectionError


def test_existing_preserves_and_exports_criteria_with_compatible_instructions(tmp_path):
    request = {"source": str(tmp_path), "projectName": "example", "task": {"request": "CSV 수정", "completionCriteria": [
        {"description": "한글과 합계가 원본과 일치", "method": "manual", "required": True}]},
        "context": {"design": {"included": True, "direction": "REPLACE ALL COLORS", "tokens": {"radius": "30px"}}}}
    document = build_preview(request)["document"]
    assert document["context"]["design"] == {"included": False}
    assert document["task"]["completionCriteria"][0]["id"] == "C1"
    assert "[C1 · 필수 · 수동 확인]" in document["assistantGuide"]["pasteText"]
    assert "REPLACE ALL COLORS" not in document["assistantGuide"]["pasteText"]
    assert document["qualityGate"]["requirementsConfirmed"] is False
    assert document["qualityGate"]["privacyChecked"] is False
    assert document["qualityGate"]["independentSecurityVerification"]["status"] == "not-performed"


@pytest.mark.parametrize("task", [
    {"completionCriteria": [{"description": "x" * 501, "method": "static", "required": True}]},
    {"completionCriteria": [None]}, {"completionCriteria": [{}] * 21},
    {"designScope": {"mode": "partial", "scope": ""}},
    {"designScope": {"mode": "partial", "scope": "x" * 1001}},
])
def test_bad_conditions_and_scope_are_rejected_without_truncation(tmp_path, task):
    with pytest.raises(ValueError):
        build_preview({"source": str(tmp_path), "task": task})


def test_changed_input_requires_explicit_review_for_export(tmp_path):
    request = {"source": str(tmp_path), "task": {"request": "contact@example.com 표기 수정"}, "output": str(tmp_path / "handoff.json")}
    preview = build_preview(request)["document"]
    assert preview["inputReview"]["required"] is True
    assert "contact@example.com" not in json.dumps(preview)
    with pytest.raises(UnsafeSelectionError):
        export_package(request)
    request["inputReviewAcknowledged"] = True
    export_package(request)
    exported = json.loads(Path(request["output"]).read_text(encoding="utf-8"))
    assert exported["inputReview"]["acknowledged"] is True
    assert exported["qualityGate"]["privacyChecked"] is False


def test_legacy_criteria_and_partial_scope_keep_meaning(tmp_path):
    document = build_preview({"source": str(tmp_path), "task": {"acceptanceCriteria": ["버튼 문구 대조"],
        "designScope": {"mode": "partial", "scope": "주문 화면 / 결제 버튼 / 배경색"}},
        "context": {"design": {"included": True, "direction": "선택한 배경색을 적용"}}})["document"]
    assert document["task"]["completionCriteria"] == []
    assert document["task"]["acceptanceCriteria"] == ["버튼 문구 대조"]
    assert "나머지 기존 디자인은 유지" in document["assistantGuide"]["pasteText"]


REJECTIONS = json.loads((ROOT / 'tests/fixtures/task-policy-rejections.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', REJECTIONS, ids=lambda case: case['name'])
def test_browser_and_python_reject_coerced_scope_and_method_types(tmp_path, case):
    with pytest.raises(ValueError):
        build_preview({'source': str(tmp_path), 'projectName': 'synthetic', 'task': {'request': 'Header', **case['task']}})
    script = """
global.window=globalThis;
const path=require('path');
for(const name of ['agent-contract.js','task-policy.js','agent-handoff-web.js']) require(path.join(process.argv[1],'src',name));
const options=JSON.parse(require('fs').readFileSync(0,'utf8'));
VASAgentHandoffWeb.buildExisting('synthetic','Header',{design:{included:true,direction:'REPLACE ALL COLORS'}},options)
  .then(()=>process.stdout.write('accepted'),()=>process.stdout.write('rejected'));
"""
    node = shutil.which('node')
    assert node, 'Node is required to check browser/Python scope parity'
    completed = subprocess.run([node, '-e', script, str(ROOT)], input=json.dumps(case['task']),
                               capture_output=True, text=True, encoding='utf-8', check=True)
    assert completed.stdout == 'rejected'
