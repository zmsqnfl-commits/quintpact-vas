"""Regressions for real agent checks and privacy-safe handoff details."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import agent_checks
from vas_ai_contract import build_prompt, clean
from vas_agent_handoff import build_preview


def test_public_references_and_private_paths():
    for url in ("https://example.com/design", "https://example.com/home/design", "http://example.com/x"):
        assert clean(url) == url
    for private in (r"C:\private\file", "path:C:/private/file", "/home/private/file", "file:///home/private/file", r"\\nas\private\file"):
        assert "private" not in clean(private)


def test_python_prompt_preserves_selections_and_tokens():
    document = {"project": {"sourceType": "new"}, "task": {"request": "sample"}, "context": {
        "requirements": {"value": {"reference": "https://example.com/home/design", "platforms": ["mobile"], "deadline": "90 days", "budget": "enterprise", "attachments": {"files": ["reference.png"], "contentsIncluded": False}}},
        "design": {"included": True, "tokens": {"colors": {"primary": "#123abc"}}}}}
    prompt = build_prompt(document)
    for marker in ("https://example.com/home/design", "mobile", "90 days", "enterprise", "reference.png", "#123abc", "별도로 첨부"):
        assert marker in prompt


def test_python_preview_keeps_design_tokens_and_complete_multiline_skill():
    direction = "Layout rule\n" * 700 + "[OUTPUT CONTRACT]\nCompare the actual screen."
    with tempfile.TemporaryDirectory() as directory:
        result = build_preview({"source": directory, "task": {"request": "Apply design"}, "context": {
            "design": {"included": True, "tokens": {"colors": {"primary": "#123abc"}, "api_key": "fixture-private"}, "direction": direction},
            "tokens": {"secret": "fixture-private"}}})
    design = result["document"]["context"]["design"]
    assert design["tokens"] == {"colors": {"primary": "#123abc"}}
    assert design["direction"] == direction
    assert direction in result["pasteText"]
    assert "#123abc" in result["pasteText"]
    assert "fixture-private" not in json.dumps(result["document"])


def test_path_checks_reject_escape_protected_and_wrong_roles():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name in ("src", "tests", "workspace"):
            (root / name).mkdir()
        assert agent_checks.check_write(root, "implementer", "src/ui.js")[0]
        assert agent_checks.check_write(root, "designer", "src/design-tokens.json")[0]
        assert agent_checks.check_write(root, "implementer", "tests/test_tokens.py")[0]
        for role, target in (("reviewer", "src/ui.js"), ("tester", "src/ui.js"), ("implementer", "../escape.js"), ("implementer", "workspace/data.json"), ("implementer", "src/.env.local"), ("designer", "src/secrets/design-tokens.json")):
            assert not agent_checks.check_write(root, role, target)[0]
        outside = root.parent / "outside-agent-check"
        try:
            (root / "src/link").symlink_to(outside, target_is_directory=True)
        except OSError:
            pass
        else:
            assert not agent_checks.check_write(root, "implementer", "src/link/out.js")[0]


def test_postcheck_and_exit_status_are_real():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "src").mkdir()
        target = root / "src/ui.js"
        target.write_text("line\n" * 501, encoding="utf-8")
        assert not agent_checks.check_after(root, "implementer", "src/ui.js")[0]
        target.write_text("valid\n", encoding="utf-8")
        assert agent_checks.check_after(root, "implementer", "src/ui.js")[0]
    assert agent_checks.run([sys.executable, "-c", "raise SystemExit(7)"]) == 7
    with patch.object(sys, "argv", ["agent_checks.py", "tests"]), patch.object(agent_checks, "npm_script", return_value=9) as runner:
        assert agent_checks.main() == 9
        runner.assert_called_once_with("test:python")


def test_generated_agent_resources_and_native_configs():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/build-agent-resources.py"), "--check"], cwd=ROOT, capture_output=True)
    assert result.returncode == 0, result.stdout.decode()
    resource = json.loads((ROOT / ".agents/agent-resources.json").read_text(encoding="utf-8"))
    assert len(resource["profiles"]) == 17
    assert set(resource["roles"]) == {"implementer", "designer", "reviewer"}
    for role, instructions in resource["roles"].items():
        raw = (ROOT / f".agents/skills/{role}/SKILL.md").read_text(encoding="utf-8")
        assert instructions == raw.split("---", 2)[2].strip()
        assert f"[ROLE INSTRUCTIONS: {role}]\n{instructions}" in resource["workflow"]
    for profile in resource["profiles"].values():
        body = (ROOT / profile["source"]).read_text(encoding="utf-8")
        assert profile["rules"] == [line[2:] for line in body.splitlines() if line.startswith("- ")]
    for role in ("implementer", "designer", "reviewer"):
        config = tomllib.loads((ROOT / f".codex/agents/vas_{role}.toml").read_text(encoding="utf-8"))
        assert config["name"] == f"vas_{role}"
        assert "model" not in config
        assert config["developer_instructions"]
        claude = (ROOT / f".claude/agents/vas_{role}.md").read_text(encoding="utf-8")
        assert f"name: vas-{role}\n" in claude
        assert "allowed_tools" not in claude


def test_windows_before_hook_fails_for_protected_target():
    if os.name != "nt":
        return
    env = dict(os.environ, TOOL_NAME="Write", AGENT_ROLE="implementer", TARGET_PATH="workspace/data.json")
    result = subprocess.run(["powershell", "-NoProfile", "-File", str(ROOT / ".agents/skills/implementer/scripts/before_tool.ps1")], env=env, capture_output=True)
    assert result.returncode != 0
