import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


class WindowsRuntimeSourceTests(unittest.TestCase):
    def test_runtime_files_are_bounded_and_launcher_has_fallback(self):
        for relative in (
            "scripts/Start-VAS.ps1",
            "scripts/VAS.Server.psm1",
            "scripts/VAS.Memory.psm1",
            "scripts/VAS.Projects.psm1",
            "scripts/VAS.AgentHandoff.psm1",
            "scripts/VAS.AgentHandoff.Core.ps1",
            "scripts/VAS.Server.Handoff.ps1",
            "scripts/vas_agent_handoff.py",
            "tests/test_windows_runtime.py",
        ):
            lines = (BASE / relative).read_text(encoding="utf-8-sig").splitlines()
            self.assertLessEqual(len(lines), 500, relative)
        launcher_bytes = (BASE / "Run-VAS-System.bat").read_bytes()
        self.assertIn(b"\r\n", launcher_bytes)
        self.assertNotIn(b"\n", launcher_bytes.replace(b"\r\n", b""))
        self.assertIn("*.bat -text", (BASE / ".gitattributes").read_text(encoding="utf-8"))
        launcher = launcher_bytes.decode("utf-8-sig")
        self.assertIn(":fallback", launcher)
        self.assertIn("src\\vas-hub.html", launcher)

    def test_folder_picker_starts_from_this_pc_with_a_real_path(self):
        source = (BASE / "scripts" / "VAS.Migration.psm1").read_text(encoding="utf-8-sig")
        self.assertIn("RootFolder = [Environment+SpecialFolder]::MyComputer", source)
        self.assertIn("$dialog.SelectedPath = $initialPath", source)

    @unittest.skipUnless(os.name == "nt" and POWERSHELL, "Windows PowerShell is required")
    def test_conflict_mapping_never_echoes_source_path(self):
        command = (
            "Import-Module '.\\scripts\\VAS.Server.psm1' -Force; "
            "& (Get-Module VAS.Server) { "
            "Get-VASMigrationError 'target already exists: C:\\Users\\demo\\secret' | "
            "ConvertTo-Json -Compress }"
        )
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=BASE,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        mapped = json.loads(result.stdout.decode("utf-8-sig"))
        self.assertEqual(mapped["status"], 409)
        self.assertEqual(mapped["code"], "project_conflict")
        self.assertNotIn("C:\\Users", json.dumps(mapped))


if __name__ == "__main__":
    unittest.main(verbosity=2)
