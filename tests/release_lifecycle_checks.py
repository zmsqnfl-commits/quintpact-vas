"""Exercise the public chat commands and the app's own entry point in an extracted kit."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def check_target_anchor(test, before, bound_tree, directories, expected_directories):
    added = set(bound_tree) - set(before)
    test.assertEqual(len(added), 1)
    anchor, = added
    test.assertRegex(anchor, r"^vas-state/target-identity/[0-9a-f]{32}$")
    test.assertEqual(bound_tree, {**before, anchor: hashlib.sha256(b"").hexdigest()})
    test.assertEqual(directories, expected_directories)


def verify_chat_lifecycle(app: Path, scratch: Path):
    private = scratch / "lifecycle-private"
    env = {**os.environ, "PYTHONUTF8": "1", "LOCALAPPDATA": str(private),
           "XDG_STATE_HOME": str(private)}

    def invoke(script, *args, data=None):
        run = subprocess.run([sys.executable, "-B", "scripts/" + script, *args], cwd=app, env=env,
                             input=None if data is None else json.dumps(data, ensure_ascii=False),
                             capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert run.returncode == 0, (args, run.stdout, run.stderr)
        return json.loads(run.stdout)

    before = invoke("vas.py", "start")
    assert before["app"]["state"] == "empty" and before["session"]["status"] == "none"
    assert not private.exists()
    prompt = invoke("vas-project-prompt.py", "save", data={
        "expectedRevision": 0, "prompt": "메뉴 이름과 가격을 표시한다."})
    settings = {"project": {"name": "Menu", "sourceType": "new"}, "task": {
        "request": "Show the menu price.",
        "completionCriteria": [{"description": "The menu prints the agreed price.",
                                "method": "automatic", "required": True}]}}
    created = invoke("vas-session.py", "create", "--target", ".", data=settings)["session"]
    sel = ["--session", created["sessionId"], "--expected-revision", str(created["revision"])]
    prepared = invoke("vas-session.py", "prepare", *sel)
    assert prepared["status"] == "prepared"
    handoff = prepared["handoff"]
    assert handoff["context"]["projectPrompt"] == prompt
    app_file = "src/menu.py"
    opened = invoke("vas-session.py", "work", "open", *sel, "--expected-work-revision", "0")

    def work(action, revision, extra=(), data=None):
        return invoke("vas-session.py", "work", action, *sel, "--expected-work-revision",
                      str(revision), *extra, data=data)

    unit = work("start", opened["work"]["revision"], data={
        "kind": "implementation", "role": "main", "mode": "direct", "label": "Build menu",
        "observedFiles": [app_file], "writableFiles": [app_file], "criterionIds": []})
    (app / app_file).write_text("print('김밥 4000원')\n", encoding="utf-8")
    receipt = work("finish", unit["work"]["revision"], ["--unit", unit["unitId"]], {
        "state": "returned", "summary": "Created menu", "changedFiles": [app_file],
        "hostCallId": "package-write", "criteria": []})
    command = "python -B menu.py"
    verify = work("start", receipt["work"]["revision"], data={
        "kind": "verification", "role": "main", "mode": "direct", "label": "Run menu",
        "observedFiles": [app_file], "writableFiles": [], "criterionIds": ["C1"], "command": command})

    def run_app(directory):
        output = subprocess.check_output([sys.executable, "-B", "menu.py"], cwd=directory, env=env,
                                         encoding="utf-8", timeout=20)
        assert output.strip() == "김밥 4000원"

    run_app(app / "src")
    work("finish", verify["work"]["revision"], ["--unit", verify["unitId"]], {
        "state": "returned", "summary": "Checked menu output", "changedFiles": [], "exitCode": 0,
        "hostCallId": "package-app-run", "criteria": [{"id": "C1", "status": "passed", "summary": "Price matches"}]})
    evidence = invoke("vas-session.py", "work", "inspect", *sel)
    assert evidence["coveredCriteria"] == ["C1"]
    artifact = evidence["artifactVersion"]
    report = {"format": "vas-ai-result", "schemaVersion": 1, "resultId": "r_menu_0123456789abcdef",
              "handoffId": handoff["workflow"]["handoffId"], "handoffPayloadSha256": handoff["integrity"]["payloadSha256"],
              "sourceType": "new", "iteration": 1, "status": "complete", "artifactVersion": artifact,
              "tests": [{"name": "Run menu", "command": command, "status": "passed", "summary": "Price matches"}],
              "evidence": [{"criterionId": "C1", "method": "automatic", "outcome": "passed",
                            "artifactVersion": artifact, "summary": "Menu printed the agreed price"}],
              "remaining": [], "safety": {"absolutePathsExcluded": True, "secretsExcluded": True,
                                          "rawCommandOutputExcluded": True}}
    payload = {"result": report, "progress": {"summary": "Verified the menu price.", "changedFiles": [app_file]}}
    closed = invoke("vas.py", "finish", *sel, "--expected-progress-revision", "0",
                    "--expected-project-prompt-revision", str(prompt["revision"]), data=payload)
    assert closed["status"] == "checkpointed"
    shared = closed["sharedProgress"]
    assert shared["scope"]["objective"] == settings["task"]["request"]
    assert shared["scope"]["criteria"] == ["The menu prints the agreed price."]
    markdown = (app / shared["markdownPath"]).read_text(encoding="utf-8")
    assert "The menu prints the agreed price." in markdown
    after = invoke("vas.py", "start")
    assert after["session"]["status"] == "resumed" and after["app"]["state"] == "nonempty"
    resumed = invoke("vas-session.py", "resume", "--target", ".")
    assert resumed["progress"]["record"]["summary"]["summary"] == payload["progress"]["summary"]
    assert resumed["progress"]["record"]["summary"]["checks"][0]["status"] == "passed"
    independent = scratch / "app-only"
    shutil.copytree(app / "src", independent)
    run_app(independent)
