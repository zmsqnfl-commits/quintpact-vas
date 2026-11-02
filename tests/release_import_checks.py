"""Verify a reviewed import from a remote-style mount and run the copied app alone."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def verify_imported_entrypoint(starter_archive, prefix):
    with tempfile.TemporaryDirectory(prefix="vas-remote-import-") as temp:
        scratch = Path(temp)
        with starter_archive as archive:
            archive.extractall(scratch)
        app = scratch / prefix
        old = scratch / "sessions/opaque/mnt/OldMenu/src"
        old.mkdir(parents=True)
        files = {
            "server.py": (
                "import os\nfrom pathlib import Path\n"
                "admin_password = os.environ.get('MENUBOARD_ADMIN_PASSWORD', '')\n"
                "for name in ('admin.js', 'fonts/menu.ttf', 'README.md', 'serve.bat', 'server-config.example.json'):\n"
                "    assert Path(name).is_file(), name\nprint('menu ready')\n"),
            "admin.js": 'function setPassword(value) { return value; }\nsetPassword("");\n',
            "serve.bat": "@echo off\r\npython server.py\r\n",
            "README.md": "Launch the menu using python server.py. Set MENUBOARD_ADMIN_PASSWORD in your environment.\n",
            "server-config.example.json": '{"port": 8787, "adminPassword": ""}',
            "board-settings.js": "window.settings = {};",
            "server-config.json": '{"adminPassword":"fixture-private-only"}',
            "toss-config.json": '{"merchantId":"fixture-private-only"}',
        }
        for name, value in files.items():
            (old / name).write_bytes(value.encode("utf-8"))
        (old / "fonts").mkdir()
        # Real licensed font above the text-file cap, under the binary asset cap.
        font = app / "ui/assets/fonts/CormorantGaramond.ttf"
        shutil.copyfile(font, old / "fonts/menu.ttf")
        env = {**os.environ, "PYTHONUTF8": "1", "LOCALAPPDATA": str(scratch / "state"),
               "XDG_STATE_HOME": str(scratch / "state")}

        def cli(*args):
            run = subprocess.run([sys.executable, "-B", "scripts/vas.py", *args], cwd=app, env=env,
                                 encoding="utf-8", capture_output=True, timeout=40, check=True)
            assert "fixture-private-only" not in run.stdout
            return json.loads(run.stdout)

        plan = cli("import", "--from", str(old))
        assert plan["status"] == "planned" and list((app / "src").iterdir()) == [app / "src/.gitkeep"]
        excluded = {item["path"] for item in plan["excluded"]}
        assert {"board-settings.js", "server-config.json", "toss-config.json"} == excluded
        applied = cli("import", "--from", str(old), *plan["addArguments"])
        assert applied["status"] == "applied"
        assert not any((app / "src" / item).exists() for item in excluded)
        standalone = scratch / "standalone"
        shutil.copytree(app / "src", standalone)
        output = subprocess.check_output([sys.executable, "-B", "server.py"], cwd=standalone, env=env,
                                         encoding="utf-8", timeout=15)
        assert output.strip() == "menu ready"
        saved = cli("finish", "--summary", "Ran the imported menu entry point",
                    "--check", "Menu starts: passed", "--next-step", "Review deployment settings")
        assert saved["sharedProgress"]["checks"] == [{"name": "Menu starts", "status": "passed"}]
