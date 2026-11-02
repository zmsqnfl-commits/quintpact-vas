"""Bundled visual analysis reaches host roles and real handoffs without expanding scope."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import sys
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vas_agent_handoff import build_preview
from vas_ai_contract import build_prompt, clean
from vas_session import SessionManager
from vas_session_execution import prepare


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = load_module("analysis_resource_builder", "build-agent-resources.py")
BUILD = load_module("analysis_release_builder", "build_release.py")
SKILL = Path(".agents/skills/design-analysis")


def skill_body():
    return GENERATOR.body((SKILL / "SKILL.md").as_posix())


def resources():
    return json.loads((ROOT / ".agents/agent-resources.json").read_text(encoding="utf-8"))


def test_generated_skill_body_is_available_without_changing_generic_role_activation():
    outputs = GENERATOR.outputs()
    current = resources()
    expected = json.loads(outputs[".agents/agent-resources.json"])
    assert current == expected
    assert current["designAnalysis"] == skill_body()
    assert current["designAnalysis"] not in current["workflow"]
    assert current["designAnalysis"] not in current["roles"]["designer"]
    assert "designAnalysis" in outputs["ui/agent-resources.js"]
    for name in ("ui/agent-resources.js", ".agents/agent-resources.json"):
        assert len(outputs[name].splitlines()) <= 500


def test_native_designer_has_full_skill_with_host_limits_preserved():
    for role in ("implementer", "designer", "reviewer"):
        codex = tomllib.loads((ROOT / f".codex/agents/vas_{role}.toml").read_text(encoding="utf-8"))
        claude = (ROOT / f".claude/agents/vas_{role}.md").read_text(encoding="utf-8")
        assert "model" not in codex
        if role == "designer":
            assert codex["developer_instructions"].count(skill_body()) == 1
            assert claude.count(skill_body()) == 1
        else:
            assert skill_body() not in codex["developer_instructions"]
            assert skill_body() not in claude
        if role == "reviewer":
            assert codex["sandbox_mode"] == "read-only"
            assert "tools: Read, Grep, Glob, WebFetch, WebSearch" in claude


@pytest.fixture(scope="module")
def packaged_project(tmp_path_factory):
    stage = tmp_path_factory.mktemp("analysis-package")
    built = BUILD.build_windows(stage)
    return built.rename(stage / "참고 이미지 프로젝트")


def test_renamed_project_bundles_discoverable_skill_and_resolvable_references(packaged_project):
    canonical = ROOT / SKILL
    source_files = {p.relative_to(canonical): p.read_bytes() for p in canonical.rglob("*") if p.is_file()}
    assert Path("SKILL.md") in source_files
    for location in (packaged_project / SKILL,
                     packaged_project / ".claude/skills/design-analysis"):
        copied = {p.relative_to(location): p.read_bytes() for p in location.rglob("*") if p.is_file()}
        assert copied == source_files
        for path in location.rglob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                target = link.split("#", 1)[0]
                if target and "://" not in target:
                    resolved = (path.parent / target).resolve()
                    assert resolved.is_relative_to(location.resolve())
                    assert resolved.is_file(), (path.name, target)
    assert list((packaged_project / "src").iterdir()) == [packaged_project / "src/.gitkeep"]
    assert not (packaged_project / ".vas").exists()
    manifest = json.loads((packaged_project / "manifest.json").read_text(encoding="utf-8"))
    paths = {item["path"] for item in manifest["files"]}
    for relative in (".agents/skills/design-analysis/SKILL.md", ".claude/skills/design-analysis/SKILL.md"):
        assert relative in paths


def session_fixture(tmp_path, mode):
    engine = tmp_path / "tool"
    (engine / "src").mkdir(parents=True)
    (engine / "src/vas-hub.html").write_text("VAS", encoding="utf-8")
    (engine / "Run-VAS-System.bat").write_text("@echo off", encoding="utf-8")
    app = tmp_path / "app"
    app.mkdir()
    (app / "existing.txt").write_text("unchanged", encoding="utf-8")
    manager = SessionManager(engine, tmp_path / "private")
    settings = {
        "project": {"name": "재고 관리", "sourceType": "new" if mode == "new" else "existing"},
        "task": {"request": "참고 이미지를 활용해 품목 목록을 읽기 쉽게 만들기",
                 "constraints": ["요청한 재고 기능과 기존 데이터 유지"],
                 "designScope": {"mode": mode, "scope": "품목 목록의 제목과 여백" if mode == "partial" else ""},
                 "completionCriteria": [{"description": "등록한 품목과 수량 표시", "method": "automatic", "required": True}]},
        "design": {"profileId": "curatedSaas", "preset": "stripe", "basePreset": "stripe",
                   "tokens": {"fontFamily": "Local Font", "colors": {"primary": "#125678"}},
                   "direction": "참고 이미지의 제목과 본문 대비를 사용"},
    }
    session = manager.create(settings, app)["session"]
    return manager, session, app


@pytest.mark.parametrize("mode", ["new", "partial", "preserve"])
def test_session_prepare_routes_analysis_only_within_current_design_scope(tmp_path, mode):
    manager, session, app = session_fixture(tmp_path, mode)
    before = deepcopy(manager.store.read())
    result = prepare(manager, session["sessionId"], session["revision"])
    handoff = result["handoff"]
    prompt = handoff["assistantGuide"]["pasteText"]
    assert handoff["task"]["request"] == session["settings"]["task"]["request"]
    assert handoff["task"]["completionCriteria"] == session["settings"]["task"]["completionCriteria"]
    assert handoff["task"]["designScope"] == session["settings"]["task"]["designScope"]
    if mode == "preserve":
        assert handoff["context"]["design"] == {"included": False}
        assert clean(skill_body(), 32000) not in prompt
    else:
        assert prompt.count(clean(skill_body(), 32000)) == 1
        assert handoff["context"]["design"]["tokens"] == session["settings"]["design"]["tokens"]
        assert "Local Font" in prompt and "#125678" in prompt
    assert manager.store.read() == before
    assert (app / "existing.txt").read_text(encoding="utf-8") == "unchanged"
    assert len(list(app.iterdir())) == 1


@pytest.mark.parametrize("inline_skill", [False, True])
def test_python_handoff_includes_analysis_once_without_inventing_image_observations(tmp_path, inline_skill):
    direction = "Apply the confirmed type hierarchy."
    if inline_skill:
        direction += "\n\n[DESIGN ANALYSIS]\n" + skill_body()
    result = build_preview({
        "source": str(tmp_path), "projectName": "재고 목록",
        "task": {"request": "목록 화면 수정", "designScope": {"mode": "partial", "scope": "목록 제목"}},
        "context": {"requirements": {"included": True, "value": {
            "attachments": {"count": 1, "contentsIncluded": False, "namesIncluded": False}}},
            "design": {"included": True, "direction": direction,
                       "tokens": {"colors": {"primary": "#125678"}}}},
    })
    handoff = result["document"]
    assert result["pasteText"].count(clean(skill_body(), 32000)) == 1
    assert handoff["context"]["design"]["direction"] == direction
    assert handoff["context"]["requirements"]["value"]["attachments"]["contentsIncluded"] is False
    assert "analysis" not in handoff["context"]["design"]
    assert handoff["task"]["request"] == "목록 화면 수정"
    assert "#125678" in result["pasteText"]


def test_direct_legacy_prompt_does_not_deduplicate_against_truncated_away_skill():
    document = {"project": {"sourceType": "new"},
                "task": {"request": "재고 목록 만들기", "designScope": {"mode": "new", "scope": ""}},
                "context": {"design": {"included": True, "direction": "X" * 12000 + skill_body()}}}
    before = deepcopy(document)
    prompt = build_prompt(document)
    assert prompt.count(clean(skill_body(), 32000)) == 1
    assert document == before
