"""The bundled design-craft skill reaches every host entry point without adding scope or approvals."""
import importlib.util
import json
from pathlib import Path
import re
import sys
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vas_ai_contract import clean
from vas_session import SessionManager
from vas_session_execution import prepare


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = load_module("craft_resource_builder", "build-agent-resources.py")
BUILD = load_module("craft_release_builder", "build_release.py")
SKILL = Path(".agents/skills/design-craft")
CLAUDE_COPY = Path(".claude/skills/design-craft")
SKILL_PATH = ".agents/skills/design-craft/SKILL.md"
ENTRYPOINTS = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules", ".windsurfrules")
WORKFLOW_RULE = "디자인 계획 → 실제 내용으로 구도 확인 → 적용 → 보내기 전 실제 화면 검수"


def skill_body():
    return GENERATOR.body((SKILL / "SKILL.md").as_posix())


def skill_files(location):
    return {path.relative_to(location): path.read_bytes() for path in location.rglob("*") if path.is_file()}


def resources():
    return json.loads((ROOT / ".agents/agent-resources.json").read_text(encoding="utf-8"))


def test_skill_is_discoverable_bounded_and_keeps_user_decisions_first():
    raw = (ROOT / SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert raw.startswith("---\nname: design-craft\ndescription: ")
    description = raw.splitlines()[2]
    # Hosts pick skills by description, so the trigger must not depend on the word "design".
    assert "화면" in description and "말이 없어도" in description
    body = skill_body()
    for required in ("다시 묻지 않", "기능을 추가하거나 디자인 변경 범위를 넓히는 근거가 아니다",
                     "새 스타일을 만들지 않는다", "시각 검수 미실행", "DESIGN.md"):
        assert required in body, required
    for path in (ROOT / SKILL).rglob("*.md"):
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 500, path.name
    names = {path.as_posix() for path in skill_files(ROOT / SKILL)}
    assert names == {"SKILL.md", "references/copy.md", "references/design-record.md",
                     "references/korean-text.md", "references/review.md", "references/typography.md"}


def test_relative_links_resolve_inside_the_skill_and_claude_copy_matches():
    assert skill_files(ROOT / CLAUDE_COPY) == skill_files(ROOT / SKILL)
    generated = {relative.as_posix() for relative, _ in BUILD.host_skill_files()}
    assert ".claude/skills/design-craft/SKILL.md" in generated
    assert ".claude/skills/design-analysis/SKILL.md" in generated
    for location in (ROOT / SKILL, ROOT / CLAUDE_COPY):
        linked = set()
        for path in location.rglob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                target = link.split("#", 1)[0]
                if target and "://" not in target:
                    resolved = (path.parent / target).resolve()
                    assert resolved.is_relative_to(location.resolve())
                    assert resolved.is_file(), (path.name, target)
                    linked.add(resolved.relative_to(location.resolve()).as_posix())
        # Every reference is reachable from the core file, so nothing is bundled unread.
        assert linked == {"references/copy.md", "references/design-record.md",
                          "references/korean-text.md", "references/review.md", "references/typography.md"}


def test_every_host_entry_point_routes_screen_work_to_the_skill():
    template = (ROOT / ".agents/PROJECT-ROOT.md").read_text(encoding="utf-8")
    assert SKILL_PATH in template and "말이 없어도" in template
    # The existing reference-analysis route stays in place next to the new one.
    assert ".agents/skills/design-analysis/SKILL.md" in template
    for name in ENTRYPOINTS:
        assert (ROOT / name).read_text(encoding="utf-8") == template, name
    assert SKILL_PATH in (ROOT / ".agents/BOOTSTRAP.md").read_text(encoding="utf-8")


def test_handoff_workflow_and_portable_roles_carry_the_order_without_vas_only_paths():
    current = resources()
    assert current == json.loads(GENERATOR.outputs()[".agents/agent-resources.json"])
    assert WORKFLOW_RULE in current["workflow"]
    marks = {"designer": "가장 약한 세 곳", "implementer": "보내기 전 실제 화면 검수",
             "reviewer": "디자인 통과로 판정하지 않는다"}
    for role, mark in marks.items():
        portable = current["portableRoles"][role]
        assert mark in portable, role
        # Portable role text is pasted into other apps, where VAS skill folders do not exist.
        assert ".agents/skills/design-craft" not in portable, role
        assert ".agents/skills/design-craft" in current["roles"][role], role
    # The full skill is not inlined into shared resources; prompts stay within their size limit.
    assert skill_body() not in current["workflow"]
    for name in ("ui/agent-resources.js", ".agents/agent-resources.json"):
        assert len(GENERATOR.outputs()[name].splitlines()) <= 500


def test_native_designer_has_the_full_skill_once_and_other_roles_do_not():
    for role in ("implementer", "designer", "reviewer"):
        codex = tomllib.loads((ROOT / f".codex/agents/vas_{role}.toml").read_text(encoding="utf-8"))
        claude = (ROOT / f".claude/agents/vas_{role}.md").read_text(encoding="utf-8")
        expected = 1 if role == "designer" else 0
        assert codex["developer_instructions"].count(skill_body()) == expected, role
        assert claude.count(skill_body()) == expected, role
        if role == "designer":
            assert codex["developer_instructions"].count("[DESIGN CRAFT]") == 1
            assert codex["developer_instructions"].index("[DESIGN ANALYSIS]") < codex[
                "developer_instructions"].index("[DESIGN CRAFT]")


@pytest.fixture(scope="module")
def packaged_project(tmp_path_factory):
    stage = tmp_path_factory.mktemp("craft-package")
    built = BUILD.build_windows(stage)
    return built.rename(stage / "화면 디자인 프로젝트")


def test_renamed_project_bundles_the_skill_and_ships_no_design_record(packaged_project):
    source_files = skill_files(ROOT / SKILL)
    for location in (packaged_project / SKILL, packaged_project / CLAUDE_COPY):
        assert skill_files(location) == source_files
    manifest = json.loads((packaged_project / "manifest.json").read_text(encoding="utf-8"))
    paths = {item["path"] for item in manifest["files"]}
    for relative in (SKILL_PATH, ".claude/skills/design-craft/SKILL.md",
                     ".claude/skills/design-craft/references/review.md", "docs/DESIGN-CRAFT.md"):
        assert relative in paths, relative
    # DESIGN.md belongs to the user's app and is written by the host, never shipped by VAS.
    assert list((packaged_project / "src").iterdir()) == [packaged_project / "src/.gitkeep"]
    assert not {"DESIGN.md", "src/DESIGN.md"} & paths
    assert (packaged_project / "AGENTS.md").read_text(encoding="utf-8").count(SKILL_PATH) == 1


@pytest.mark.parametrize("mode", ["new", "preserve"])
def test_prepared_handoff_carries_the_order_for_new_and_preserved_designs(tmp_path, mode):
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
        # A beginner request names a feature only; no design wording and no design selection.
        "task": {"request": "품목과 수량을 적는 재고 앱 만들기",
                 "designScope": {"mode": mode, "scope": ""},
                 "completionCriteria": [{"description": "등록한 품목과 수량 표시",
                                         "method": "automatic", "required": True}]},
    }
    session = manager.create(settings, app)["session"]
    result = prepare(manager, session["sessionId"], session["revision"])
    prompt = result["handoff"]["assistantGuide"]["pasteText"]
    assert result["status"] == "prepared"
    assert clean(WORKFLOW_RULE, 32000) in prompt
    assert "기존 유지 범위에는 새 스타일을 만들지 않는다" in prompt
    assert len(prompt) <= 32000
    # Preparing never writes the app, so no design record appears before the host works.
    assert sorted(path.name for path in app.iterdir()) == ["existing.txt"]


def test_release_build_moves_a_zip_left_by_another_version_aside(tmp_path):
    # An older build left in the output folder may be the only copy of that version.
    output = tmp_path / "out"
    (output / "pages").mkdir(parents=True)
    (output / "pages" / "old.html").write_text("old", encoding="utf-8")
    (output / "SHA256SUMS.txt").write_text("old", encoding="utf-8")
    (output / "VAS-0.0.1-windows.zip").write_bytes(b"the only copy of an older build")
    moved = BUILD.clear_output(output)
    assert moved == [tmp_path / "out-previous" / "VAS-0.0.1-windows.zip"] and not list(output.iterdir())
    assert moved[0].read_bytes() == b"the only copy of an older build"
    # A second build with the same name left behind never overwrites the first.
    (output / "VAS-0.0.1-windows.zip").write_bytes(b"a different build with the same name")
    again = BUILD.clear_output(output)
    assert again == [tmp_path / "out-previous" / "VAS-0.0.1-windows.1.zip"]
    assert moved[0].read_bytes() == b"the only copy of an older build"


def test_a_new_screen_with_nothing_decided_asks_once_for_a_reference():
    skill = (ROOT / ".agents/skills/design-craft/SKILL.md").read_text(encoding="utf-8")
    assert "한 번만 묻는다" in skill and "참고할 사이트·이미지" in skill and "다시 묻지 않는다" in skill
    assert "보지 않은 것을 본 것처럼 따라 하지 않는다" in skill
    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules", ".windsurfrules", ".agents/HANDOFF-WORKFLOW.md"):
        assert "한 번만 묻고" in (ROOT / name).read_text(encoding="utf-8"), name
    # No sample artwork, font or proof app ships, and nothing still points at them.
    assert not (ROOT / "ui/assets").exists() and not (ROOT / "ui/proof-app").exists()
    for path in list((ROOT / "ui").glob("*.css")) + list((ROOT / "ui").glob("design-*.js")):
        text = path.read_text(encoding="utf-8")
        assert "assets/" not in text and "@font-face" not in text, path.name
