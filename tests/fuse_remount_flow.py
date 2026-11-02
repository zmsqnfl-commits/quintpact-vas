"""Exercise the project CLI across actual, deletion-restricted Linux FUSE connections."""
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = {"project": {"name": "Menu", "sourceType": "new"},
            "task": {"request": "Display the menu", "completionCriteria": [
                {"description": "Menu entry point prints Menu", "method": "automatic", "required": True}]}}


def starter(project):
    (project / "src").mkdir(parents=True)
    for name in ("project-layout.json", "Run-VAS-System.bat", "ui/vas-hub.html", "ui/vas-config.js",
                 ".agents/agent-resources.json"):
        target = project / name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copytree(ROOT / "scripts", project / "scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (project / "unlink-probe").touch()


def exercise(connect, state):
    def call(project, script, *args, data=None):
        proc = subprocess.run([sys.executable, "-B", f"scripts/{script}.py", "--state-home", str(state), *args],
                              input=json.dumps(data) if data else None, cwd=project, capture_output=True,
                              encoding="utf-8", timeout=40)
        assert proc.returncode == 0, (args, proc.stdout, proc.stderr)
        return json.loads(proc.stdout)

    with connect() as project:
        assert call(project, "vas", "start")["session"]["status"] == "none"
    with connect() as project:
        session = call(project, "vas-session", "create", "--target", ".", data=SETTINGS)["session"]
        sid = session["sessionId"]
        assert session["revision"] == 1
    with connect() as project:
        resumed = call(project, "vas-session", "resume", "--session", sid)
        assert resumed["status"] == "resumed" and resumed["session"] == session, resumed
    with connect() as project:
        prepared = call(project, "vas-session", "prepare", "--session", sid, "--expected-revision", "1")
        assert prepared["status"] == "prepared", prepared
        finish_args = prepared["finishArguments"]
        (project / "src/menu.py").write_text("print('Menu')\n", encoding="utf-8")
    with connect() as project:
        checked = subprocess.run([sys.executable, "-B", "src/menu.py"], cwd=project, capture_output=True,
                                 text=True, check=True, timeout=10)
        assert checked.stdout.strip() == "Menu"
        result = call(project, "vas", *finish_args, "--summary", "Menu ran", "--check", "Menu output:passed",
                      "--changed-file", "created:src/menu.py", "--artifact-version", "menu-v1",
                      "--criterion", "C1=passed:Printed Menu")
        assert result["status"] == "checkpointed" and result["revision"] == 2, result
    with connect() as project:
        view = call(project, "vas", "start")
        assert view["session"]["sessionId"] == sid and view["session"]["revision"] == 2, view
        assert view["sharedProgress"]["revision"] == 1 and view["sharedProgress"]["summary"] == "Menu ran"
        assert (project / "vas-state/progress/000001.ok").is_file()


def main():
    with tempfile.TemporaryDirectory(prefix="vas-fuse-") as name, ExitStack() as handles:
        parent = Path(name)
        original, mount = parent / "backing", parent / "connection"
        starter(original / "Menu")
        mount.mkdir()
        devices, inodes = set(), set()
        unmount = shutil.which("fusermount3") or shutil.which("fusermount")
        assert unmount, "FUSE unmount helper is required"

        @contextmanager
        def connect():
            subprocess.run(["bindfs", "--no-allow-other", "--delete-deny", original, mount],
                           check=True, timeout=30)
            try:
                # Pin detached connections until the end so the kernel cannot recycle their device numbers.
                handles.callback(os.close, os.open(mount, os.O_RDONLY | os.O_DIRECTORY))
                project = mount / "Menu"
                info = project.stat()
                assert info.st_dev not in devices, "Expected a fresh FUSE device for each host invocation"
                devices.add(info.st_dev)
                inodes.add(info.st_ino)
                assert len(inodes) == 1, "Directory inode changed across FUSE views"
                try:
                    (project / "unlink-probe").unlink()
                except PermissionError:
                    pass
                else:
                    raise AssertionError("Remote fixture unexpectedly allowed deletion")
                yield project
            finally:
                subprocess.run([unmount, "-uz", mount], check=True, timeout=30)

        exercise(connect, parent / "host-state")
        print(f"Remote CLI passed on {len(devices)} distinct FUSE devices {sorted(devices)} with inode {inodes.pop()}")


if __name__ == "__main__":
    main()
