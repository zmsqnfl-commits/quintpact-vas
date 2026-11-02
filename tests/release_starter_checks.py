"""Build from a populated disposable app and verify all public/backup outputs."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

from release_lifecycle_checks import verify_chat_lifecycle
from pathlib import Path


def check_app_isolation(test, builder):
    with tempfile.TemporaryDirectory(prefix="vas-flat-boundary-") as temporary:
        root = Path(temporary) / "Renamed app"
        for relative, source in builder.starter_files():
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        app = root / "src"
        app.mkdir()
        canary = b"private-user-app-sentinel"
        for path in (app / "main.js", root / "VAS-PROJECT-PROMPT.json", root / "app-notes.txt"):
            path.write_bytes(canary)
        refused = subprocess.run([sys.executable, "-B", str(root / "scripts/build_release.py"),
                                  "--output", str(app)], cwd=root, capture_output=True)
        test.assertNotEqual(refused.returncode, 0)
        test.assertEqual((app / "main.js").read_bytes(), canary)
        output = Path(temporary) / "output"
        subprocess.run([sys.executable, "-B", str(root / "scripts/build_release.py"),
                        "--output", str(output)], cwd=root, check=True)
        subprocess.run([sys.executable, "-B", str(root / "scripts/vas-backup.py")], cwd=root, check=True)
        test.assertEqual([p.name for p in app.iterdir()], ["main.js"])
        test.assertEqual((app / "main.js").read_bytes(), canary)
        archives = [*output.glob("*.zip"), *root.glob(".vas_backups/*.zip")]
        test.assertEqual(len(archives), 3)
        for file in archives:
            with zipfile.ZipFile(file) as archive:
                for name in archive.namelist():
                    test.assertNotIn("main.js", name)
                    test.assertNotIn("VAS-PROJECT-PROMPT.json", name)
                    test.assertNotIn(canary, archive.read(name), name)
        pages = output / "pages"
        test.assertTrue((pages / "src/vas-hub.html").is_file())
        test.assertFalse((pages / "src/main.js").exists())
        test.assertFalse(any(canary in p.read_bytes() for p in pages.rglob("*") if p.is_file()))


def verify_git_archive():
    """Smoke-test GitHub's source download layout from the exact committed tree."""
    repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="vas-source-archive-") as temporary:
        base = Path(temporary)
        archive = base / "source.zip"
        subprocess.run(["git", "archive", "--format=zip", "-o", str(archive), "HEAD"], cwd=repo, check=True)
        app = base / "Renamed project"
        with zipfile.ZipFile(archive) as bundle:
            names = {name for name in bundle.namelist() if not name.endswith("/")}
            if {name for name in names if name.startswith("src/")} != {"src/.gitkeep"}:
                raise ValueError("The source download must start with an empty app")
            if any(name.startswith(".vas/") for name in names):
                raise ValueError("The source download contains the legacy tool directory")
            bundle.extractall(app)
        expected = json.loads((app / "project-layout.json").read_text(encoding="utf-8"))
        if expected != {"layout": "vas-project", "version": 2} or not (app / "ui/vas-hub.html").is_file():
            raise ValueError("Invalid flat starter layout")
        environment = {**os.environ, "LOCALAPPDATA": str(base / "private"), "XDG_STATE_HOME": str(base / "private")}
        run = subprocess.run([sys.executable, "-B", "scripts/vas-project-prompt.py", "get"], cwd=app,
                             env=environment, check=True, capture_output=True)
        if json.loads(run.stdout) != {"revision": 0, "prompt": ""}:
            raise ValueError("The source download failed read-only project intake")
        verify_chat_lifecycle(app, base)
    print("Git source download opened as a renamed VAS project.")


if __name__ == "__main__":
    verify_git_archive()
