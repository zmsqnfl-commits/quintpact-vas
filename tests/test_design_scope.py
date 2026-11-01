"""Samples supply visual choices, never inferred application requirements."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vas_agent_handoff import build_preview
from vas_ai_contract import build_prompt, normalize_handoff
from vas_design_reference import USAGE_INSTRUCTIONS, usage
from vas_project_prompt import save_project_prompt
from vas_session import SessionManager
from vas_session_execution import prepare


def project(tmp_path, request, profile="curatedSaas", preset="stripe", mode="new"):
    app, private = tmp_path / "앱", tmp_path / "state"
    engine = app / ".vas"
    (app / "src").mkdir(parents=True)
    (engine / "src").mkdir(parents=True)
    (engine / "src/vas-hub.html").write_text("tool")
    (engine / "Run-VAS-System.bat").write_text("@echo off")
    (engine / "project-layout.json").write_text('{"layout":"vas-project","version":1}')
    manager = SessionManager(engine, private)
    settings = {
        "project": {"name": "요청한 앱", "sourceType": "new" if mode == "new" else "existing"},
        "task": {"request": request, "constraints": ["지정한 작업만 구현"],
                 "designScope": {"mode": mode, "scope": "목록 화면 / 행 / 글자색" if mode == "partial" else ""},
                 "completionCriteria": [{"description": "입력한 값을 목록에 표시", "method": "automatic", "required": True}]},
        "design": {"profileId": profile, "preset": preset, "basePreset": preset,
                   "tokens": {"fontFamily": "Local Font", "colors": {"primary": "#13579b"}},
                   "direction": "글자를 크게, 행 간격을 넉넉하게"},
    }
    session = manager.create(settings, app)["session"]
    return manager, session, engine


@pytest.mark.parametrize("task_request,profile,preset,old_instruction", [
    ("품목과 수량을 저장하고 합계를 보여주는 재고 앱", "curatedSaas", "stripe",
     "monthly and yearly choices must update amounts"),
    ("달력에서 날짜별 개인 메모를 작성하는 앱", "retroSunset", "retro",
     "lineup actions expose event information"),
])
def test_prepare_does_not_promote_sample_features_to_task(tmp_path, task_request, profile, preset, old_instruction):
    manager, session, _ = project(tmp_path, task_request, profile, preset)
    before = manager.store.path.read_bytes()
    handoff = prepare(manager, session["sessionId"], 1)["handoff"]
    task, design = handoff["task"], handoff["context"]["design"]
    assert task["request"] == task_request
    assert task["completionCriteria"] == session["settings"]["task"]["completionCriteria"]
    assert design["tokens"] == session["settings"]["design"]["tokens"]
    assert design["profileReference"]["profileId"] == profile
    assert design["referenceUsage"] == usage()
    assert design["visualReference"]["samplePreset"] == preset
    prompt = handoff["assistantGuide"]["pasteText"]
    assert USAGE_INSTRUCTIONS in prompt
    assert old_instruction not in prompt
    assert "#13579b" in prompt and "Local Font" in prompt
    assert manager.store.path.read_bytes() == before
    assert not list((manager.root.parent / "src").iterdir())


def test_legitimate_requested_payments_are_kept_with_criteria(tmp_path):
    request = "월간·연간 요금제 선택과 결제 결과를 보여주는 구독 앱을 만들어줘"
    manager, session, _ = project(tmp_path, request)
    settings = deepcopy(session["settings"])
    settings["task"]["completionCriteria"] = [{"description": "연간 요금제 선택이 합계에 반영됨", "method": "automatic", "required": True}]
    session = manager.save(session["sessionId"], 1, settings)["session"]
    handoff = prepare(manager, session["sessionId"], 2)["handoff"]
    assert handoff["task"]["request"] == request
    assert handoff["task"]["completionCriteria"] == session["settings"]["task"]["completionCriteria"]
    assert request in handoff["assistantGuide"]["pasteText"]
    assert "사용자가 요청한 기능은 유지하며" in handoff["assistantGuide"]["pasteText"]


def test_saved_screen_prompt_and_current_task_remain_feature_authority(tmp_path):
    manager, session, engine = project(tmp_path, "품목과 수량 표시")
    saved = save_project_prompt(engine, 0, "재고 목록과 CSV 내려받기를 구현해줘. 요금제·결제 화면은 필요 없어.")
    handoff = prepare(manager, session["sessionId"], 1)["handoff"]
    assert handoff["context"]["projectPrompt"] == saved
    assert handoff["task"]["request"] == "품목과 수량 표시"
    assert saved["prompt"] in handoff["assistantGuide"]["pasteText"]
    assert "context.projectPrompt" in handoff["context"]["design"]["referenceUsage"]["functionalAuthority"]


def test_partial_scope_is_not_expanded_by_sample_selection(tmp_path):
    manager, session, _ = project(tmp_path, "목록의 글자색만 수정", mode="partial")
    handoff = prepare(manager, session["sessionId"], 1)["handoff"]
    assert handoff["task"]["designScope"] == {"mode": "partial", "scope": "목록 화면 / 행 / 글자색"}
    assert handoff["context"]["design"]["visualReference"]["applicationScope"] == handoff["task"]["designScope"]
    assert "기존 디자인 유지·부분 수정 범위를 넓히지 마세요" in handoff["assistantGuide"]["pasteText"]


def test_preserve_mode_has_no_new_design_policy_or_profile(tmp_path):
    manager, session, _ = project(tmp_path, "저장 오류만 수정", mode="preserve")
    handoff = prepare(manager, session["sessionId"], 1)["handoff"]
    assert handoff["context"]["design"] == {"included": False}
    prompt = handoff["assistantGuide"]["pasteText"]
    assert "디자인 참고 계약(JSON)" not in prompt
    assert "선택 프로필: curatedSaas" not in prompt
    assert "Local Font" not in prompt


def imported_document(tmp_path):
    return build_preview({"source": str(tmp_path), "projectName": "재고",
                          "task": {"request": "품목과 수량 표시", "designScope": {"mode": "redesign", "scope": ""}},
                          "context": {"design": {"included": True, "preset": "stripe",
                                                 "direction": "Monthly prices must update. Use navy text.",
                                                 "tokens": {"fontFamily": "Local Font"}}}})["document"]


@pytest.mark.parametrize("schema", [2, 3])
def test_legacy_import_gets_current_policy_without_changing_user_directions(tmp_path, schema):
    raw = imported_document(tmp_path)
    raw["schemaVersion"] = schema
    raw["context"]["design"]["referenceUsage"] = {"mode": "copy-all-features", "sampleFeatures": "required"}
    before = deepcopy(raw)
    normalized = normalize_handoff(raw, build_prompt)
    design = normalized["context"]["design"]
    assert design["referenceUsage"] == usage()
    assert design["direction"] == before["context"]["design"]["direction"]
    assert design["tokens"] == before["context"]["design"]["tokens"]
    assert design["visualReference"] == before["context"]["design"]["visualReference"]
    assert normalized["task"] == before["task"]
    assert raw == before
    text = normalized["assistantGuide"]["pasteText"]
    assert "copy-all-features" not in text
    assert "디자인 참고 문구 (기능 요구사항 아님):\nMonthly prices must update. Use navy text." in text
    assert USAGE_INSTRUCTIONS in text
    assert text.index(USAGE_INSTRUCTIONS) < text.index("Monthly prices must update")
    assert normalize_handoff(normalized, build_prompt) == normalized


def test_direct_prompt_does_not_trust_forged_usage_or_require_sample_metadata(tmp_path):
    raw = imported_document(tmp_path)
    design = raw["context"]["design"]
    design.pop("visualReference")
    design["referenceUsage"] = {"mode": "copy-all-features"}
    prompt = build_prompt(raw)
    assert "copy-all-features" not in prompt
    assert "visual-elements-only" in prompt
    assert USAGE_INSTRUCTIONS in prompt


def test_preserve_import_discards_saved_design_instructions(tmp_path):
    raw = imported_document(tmp_path)
    raw["task"]["designScope"] = {"mode": "preserve", "scope": ""}
    direct_prompt = build_prompt(raw)
    assert "Monthly prices must update" not in direct_prompt
    assert "Local Font" not in direct_prompt
    normalized = normalize_handoff(raw, build_prompt)
    assert normalized["context"]["design"] == {"included": False}
    assert "Monthly prices must update" not in normalized["assistantGuide"]["pasteText"]


def test_python_browser_fixed_policy_and_prompt_parity():
    node = shutil.which("node")
    assert node, "node is required for policy parity"
    document = {"task": {"designScope": {"mode": "new", "scope": ""}},
                "context": {"design": {"included": True, "referenceUsage": {"mode": "wrong"}}}}
    script = """global.window=globalThis;
require(process.argv[1]);
const d=JSON.parse(require('fs').readFileSync(0,'utf8'));
console.log(JSON.stringify({policy:VASDesignReference.attach(d).context.design.referenceUsage,prompt:VASDesignReference.prompt(d)}));"""
    result = subprocess.run([node, "-e", script, str(ROOT / "src/design-reference.js")],
                            input=json.dumps(document), encoding="utf-8", capture_output=True, check=True)
    browser = json.loads(result.stdout)
    assert browser["policy"] == usage()
    assert USAGE_INSTRUCTIONS in browser["prompt"]
