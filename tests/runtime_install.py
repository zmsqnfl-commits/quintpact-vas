"""Install real VAS scripts in an isolated Windows fixture before binding a listener."""
from pathlib import Path
import shutil
import sys


def install_runtime(root, *, legacy=True):
    source = Path(__file__).resolve().parents[1]
    if not (root / "scripts").is_dir():
        shutil.copytree(source / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(source / ".agents", root / ".agents")
    if legacy:
        (root / "src").mkdir(exist_ok=True)
        hub = root / "src/vas-hub.html"
        if not hub.exists():
            hub.write_text("<title>Legacy VAS fixture</title>", encoding="utf-8")
        (root / "package.json").write_text('{"name":"quintpact-vas","version":"2.11.0"}', encoding="utf-8")
    return root / "scripts/Start-VAS.ps1"


if __name__ == "__main__":
    # Connected browser tests also need real UI files in their isolated historical tool.
    # shutil preserves non-ASCII destinations on the Windows Node 22 runners.
    project = Path(sys.argv[1])
    source = Path(__file__).resolve().parents[1]
    shutil.copytree(source / "ui", project / "src")
    install_runtime(project)
    shutil.copyfile(source / "Run-VAS-System.bat", project / "Run-VAS-System.bat")
    (project / "docs").mkdir(exist_ok=True)
