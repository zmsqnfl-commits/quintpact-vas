"""Check the folder-intake instructions delivered in the Windows project ZIP."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def check_folder_intake(test, archive_path, root_name, fingerprints):
    with tempfile.TemporaryDirectory(prefix="vas-intake-") as temporary:
        base = Path(temporary)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(base)
        app = (base / root_name).rename(base / "사용자 프로젝트")
        guide = (app / "AGENTS.md").read_text(encoding="utf-8")
        # The other four host guides are already checked against the same template.
        test.assertIn("이 폴더를 프로젝트로 지정하고 색인해줘", guide)
        test.assertIn("색인 결과만 알려줘", guide)
        private = base / "isolated-pc"
        env = {**os.environ, "LOCALAPPDATA": str(private), "XDG_STATE_HOME": str(private), "PYTHONUTF8": "1"}

        for existing in (False, True):
            with test.subTest(existing_app=existing):
                brief = {"revision": 0, "prompt": ""}
                if existing:
                    (app / "src/app.py").write_text("print('existing app')", encoding="utf-8")
                    brief = {"revision": 1, "prompt": "기존 출력 형식 유지"}
                    (app / "VAS-PROJECT-PROMPT.json").write_text(json.dumps({
                        "format": "vas-project-prompt", "schemaVersion": 1, **brief,
                    }), encoding="utf-8")
                before = fingerprints(app)
                for command, code, expected in (
                    ("-B scripts/vas-project-prompt.py get", 0, brief),
                    ("-B scripts/vas-session.py resume --target .", 1, {"status": "error", "code": "session_not_found"}),
                ):
                    test.assertIn(f"`python {command}`", guide)
                    run = subprocess.run([sys.executable, *command.split()], cwd=app, env=env,
                                         capture_output=True, encoding="utf-8", timeout=20)
                    test.assertEqual(run.returncode, code, run.stdout + run.stderr)
                    test.assertEqual(json.loads(run.stdout), expected)
                test.assertEqual(fingerprints(app), before)
                test.assertFalse(private.exists(), "Read-only intake created private session state")
