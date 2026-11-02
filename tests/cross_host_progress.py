"""Exchange a synthetic project note between Linux and Windows CI runners."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main(operation, exchange):
    with tempfile.TemporaryDirectory(prefix="vas-connected-") as temp:
        parent = Path(temp)
        project = parent / "원격 메뉴 프로젝트"
        (project / "ui").mkdir(parents=True)
        (project / "src").mkdir()
        for path in ("project-layout.json", "Run-VAS-System.bat", "ui/vas-hub.html"):
            shutil.copyfile(ROOT / path, project / path)
        env = {**os.environ, "PYTHONUTF8": "1", "LOCALAPPDATA": str(parent / "local"),
               "XDG_STATE_HOME": str(parent / "local")}

        def invoke(*args):
            result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/vas.py"),
                                     "--vas-root", str(project), *args], cwd=project, env=env,
                                    encoding="utf-8", capture_output=True, timeout=30, check=True)
            return json.loads(result.stdout)

        if operation == "write":
            result = invoke("finish", "--summary", "메뉴 표시 확인", "--check", "메뉴: 통과",
                            "--next-step", "관리 화면 확인", "--expected-shared-revision", "0")
            assert result["sharedProgress"]["revision"] == 1
            shutil.copytree(project / "vas-state", exchange)
        elif operation == "read":
            shutil.copytree(exchange, project / "vas-state")
            result = invoke("start")
            assert result["session"]["status"] == "none", result
            shared = result["sharedProgress"]
            assert shared["revision"] == 1 and shared["summary"] == "메뉴 표시 확인"
            markdown = (project / shared["markdownPath"]).read_text(encoding="utf-8")
            assert "메뉴 표시 확인" in markdown and "메뉴 · 통과" in markdown
            assert shared["checks"] == [{"name": "메뉴", "status": "passed"}]
            assert shared["nextStep"] == "관리 화면 확인"
            updated = invoke("finish", "--summary", "관리 화면 점검 중", "--check", "권한: 미실행",
                             "--next-step", "권한 확인", "--expected-shared-revision", "1")
            assert updated["sharedProgress"]["revision"] == 2
            assert invoke("start")["sharedProgress"] == updated["sharedProgress"]
        else:
            raise ValueError("Expected write or read")
        assert not (parent / "local").exists(), "A project summary created private state"
        print(f"{sys.platform}: cross-host {operation} passed")


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
