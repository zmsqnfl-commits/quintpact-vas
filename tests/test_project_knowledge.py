from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vas_project_knowledge as knowledge  # noqa: E402
from vas_project_knowledge import (  # noqa: E402
    ALLOWED_SUFFIXES,
    MAX_CHUNK_CHARS,
    MAX_FILE_BYTES,
    KnowledgeError,
    build_index,
    check_index,
    index_path,
    write_index,
)


class ProjectKnowledgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="vas-project-knowledge-")
        self.base = Path(self.temporary.name)
        self.root = self.base / "vas"
        self.projects = self.root / "workspace" / "projects"
        self.state = self.root / "workspace" / ".vas"
        self.projects.mkdir(parents=True)
        self.state.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def register(self, *projects: Path, extra: list[dict] | None = None) -> None:
        records = [
            {
                "projectId": f"project-{number}", "name": project.name,
                "path": str(project), "status": "ready", "createIndex": True,
            }
            for number, project in enumerate(projects, 1)
        ]
        records.extend(extra or [])
        (self.state / "projects.json").write_text(
            json.dumps({"version": 1, "projects": records}, ensure_ascii=False), encoding="utf-8"
        )

    def test_only_registered_allowlisted_safe_text_is_indexed(self) -> None:
        project = self.projects / "registered"
        unregistered = self.projects / "not-registered"
        project.mkdir()
        unregistered.mkdir()
        expected: set[str] = set()
        for number, suffix in enumerate(sorted(ALLOWED_SUFFIXES)):
            relative = f"src/file-{number}{suffix}"
            path = project / relative
            path.parent.mkdir(exist_ok=True)
            path.write_text(f"safe searchable content {number}", encoding="utf-8")
            expected.add("workspace/projects/registered/" + relative)
        (unregistered / "ignored.md").write_text("must not appear", encoding="utf-8")
        for folder in (".git", "node_modules", "vendor", "build", "dist", "cache", "secrets"):
            path = project / folder
            path.mkdir()
            (path / "ignored.js").write_text("must not appear", encoding="utf-8")
        for name in (".env.js", "secret-config.json", "credentials.json", "private.key"):
            (project / name).write_text("must not appear", encoding="utf-8")
        (project / "binary.js").write_bytes(b"function ok(){}\x00binary")
        (project / "too-large.txt").write_bytes(b"x" * (MAX_FILE_BYTES + 1))
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "outside.md").write_text("must not appear", encoding="utf-8")
        opted_out = self.projects / "opted-out"
        opted_out.mkdir()
        (opted_out / "private.md").write_text("must not appear", encoding="utf-8")
        self.register(project, extra=[
            {"projectId": "outside", "path": str(outside), "status": "ready", "createIndex": True},
            {"projectId": "opted-out", "path": str(opted_out), "status": "ready", "createIndex": False},
        ])

        index = build_index(self.root)
        sources = {entry["source"] for entry in index["entries"]}
        self.assertEqual(index["projectCount"], 1)
        self.assertEqual(index["sourceCount"], len(ALLOWED_SUFFIXES))
        self.assertEqual(sources, expected)
        self.assertNotIn(str(self.root), json.dumps(index, ensure_ascii=False))
        self.assertTrue(all("\\" not in source for source in sources))

    def test_per_project_budget_and_chunk_limit(self) -> None:
        project = self.projects / "budget"
        project.mkdir()
        for number in range(9):
            (project / f"file-{number:02}.txt").write_bytes((str(number).encode() * (250 * 1024)))
        self.register(project)
        index = build_index(self.root)
        sources = {entry["source"] for entry in index["entries"]}
        self.assertEqual(index["sourceCount"], 8)
        self.assertEqual(len(sources), 8)
        self.assertNotIn("workspace/projects/budget/file-08.txt", sources)
        self.assertTrue(all(0 < len(entry["text"]) <= MAX_CHUNK_CHARS for entry in index["entries"]))

    def test_absolute_paths_and_secret_values_are_redacted(self) -> None:
        project = self.projects / "redaction"
        project.mkdir()
        github_classic = "ghp_" + "abcdefghijklmnopqrstuvwxyz"
        aws_key = "AKIA" + "ABCDEFGHIJKLMNOP"
        google_key = "AI" + "zaabcdefghijklmnopqrstuvwxyz123456789"
        github_fine_grained = "github_" + "pat_abcdefghijklmnopqrstuvwxyz123456"
        jwt = "e" + "yJabcdefghijk." + "eyJmnopqrstuvwxyz.abcdefghijklmnop"
        private_begin = "-" * 5 + "BEGIN RSA " + "PRIVATE KEY" + "-" * 5
        private_end = "-" * 5 + "END RSA " + "PRIVATE KEY" + "-" * 5
        content = f"""# Configuration
project={project}
windows=C:\\Users\\alice\\private\\settings.json
unc=\\\\server\\share\\customer.txt
unix=/home/alice/private/settings.json
password: hunter2
api_key = "super-secret-api-value"
Authorization: Bearer abcdefghijklmnopqrstuvwxyz
token={github_classic}
DATABASE_URL=postgresql://alice:db-password@db.example/app
AWS_ACCESS_KEY_ID={aws_key}
AWS_SECRET_ACCESS_KEY=aws-secret-value-1234567890
GOOGLE_API_KEY={google_key}
GITHUB_TOKEN={github_fine_grained}
jwt={jwt}
{private_begin}
private-material
{private_end}
"""
        (project / "config.md").write_text(content, encoding="utf-8")
        self.register(project)
        index = build_index(self.root)
        combined = "\n".join(entry["text"] for entry in index["entries"])
        serialized = json.dumps(index, ensure_ascii=False)
        for forbidden in (
            str(project), "C:\\Users\\alice", "server\\share", "/home/alice",
            "hunter2", "super-secret-api-value", "abcdefghijklmnopqrstuvwxyz", "private-material",
            "db-password", aws_key, "aws-secret-value",
            "AI" + "za", "github_" + "pat_", "e" + "yJabcdefghijk",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertIn("[path]", combined)
        self.assertIn("[redacted]", combined)
        self.assertEqual(index["entries"][0]["source"], "workspace/projects/redaction/config.md")

    def test_atomic_deterministic_build_and_cli_check(self) -> None:
        project = self.projects / "deterministic"
        project.mkdir()
        (project / "README.md").write_text("# Stable\nsearch content", encoding="utf-8")
        self.register(project)
        output, first = write_index(self.root)
        first_bytes = output.read_bytes()
        _, second = write_index(self.root)
        self.assertEqual(first, second)
        self.assertEqual(first_bytes, output.read_bytes())
        self.assertTrue(check_index(self.root))
        self.assertFalse(list(output.parent.glob(".project-knowledge-*.tmp")))

        cli = SCRIPTS / "vas-project-knowledge.py"
        command = [sys.executable, str(cli), "--root", str(self.root), "--json"]
        current = subprocess.run(command + ["check"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(current.returncode, 0, current.stderr)
        before = output.read_bytes()
        (project / "README.md").write_text("# Changed\nnew content", encoding="utf-8")
        stale = subprocess.run(command + ["check"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(stale.returncode, 1)
        self.assertEqual(output.read_bytes(), before, "check 명령은 색인을 변경하면 안 됩니다.")
        built = subprocess.run(command + ["build"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertEqual(json.loads(built.stdout)["status"], "built")
        self.assertTrue(check_index(self.root))

    def test_global_cap_is_deterministic_and_reports_skips(self) -> None:
        projects = []
        for project_number in range(3):
            project = self.projects / f"project-{project_number}"
            project.mkdir()
            for file_number in range(2):
                content = (f"project {project_number} file {file_number} searchable content\n" * 1500)
                (project / f"notes-{file_number}.md").write_text(content, encoding="utf-8")
            projects.append(project)
        self.register(*projects)

        with mock.patch.object(knowledge, "MAX_INDEX_BYTES", 12_000):
            output, first = knowledge.write_index(self.root)
            first_bytes = output.read_bytes()
            _, second = knowledge.write_index(self.root)
            self.assertEqual(first, second)
            self.assertEqual(first_bytes, output.read_bytes())
            self.assertLessEqual(len(first_bytes), 12_000)
            self.assertGreater(first["stats"]["skippedChunks"], 0)
            self.assertGreater(first["stats"]["skippedProjects"], 0)
            self.assertEqual(first["stats"]["entryCount"], len(first["entries"]))
            self.assertTrue(first["warnings"])
        self.assertFalse(list(output.parent.glob(".project-knowledge-*.tmp")))

    def test_corrupt_registry_does_not_replace_last_good_index(self) -> None:
        project = self.projects / "safe"
        project.mkdir()
        (project / "README.md").write_text("safe index", encoding="utf-8")
        self.register(project)
        output, _ = write_index(self.root)
        previous = output.read_bytes()
        (self.state / "projects.json").write_text("{broken", encoding="utf-8")
        with self.assertRaises(KnowledgeError):
            write_index(self.root)
        self.assertEqual(output.read_bytes(), previous)


class PowerShellKnowledgeHookTests(unittest.TestCase):
    @staticmethod
    def shell() -> str | None:
        return shutil.which("powershell.exe") or shutil.which("pwsh") or shutil.which("powershell")

    def run_hook_flow(self, break_output: bool = False, create_index: bool = True) -> dict:
        shell = self.shell()
        if not shell:
            self.skipTest("PowerShell이 없습니다.")
        with tempfile.TemporaryDirectory(prefix="vas-project-hook-") as temporary:
            base = Path(temporary)
            root = base / "vas"
            source = base / "legacy"
            root.mkdir()
            source.mkdir()
            (source / "README.md").write_text("# Legacy\npayment migration", encoding="utf-8")
            if break_output:
                (root / "workspace" / ".vas" / "project-knowledge.json").mkdir(parents=True)
            quote = lambda value: str(value).replace("'", "''")
            module = SCRIPTS / "VAS.Migration.psm1"
            if break_output:
                tail = (
                    "$warning=if($j.PSObject.Properties['warning']){$j.warning}else{$null};"
                    "$exists=Test-Path -LiteralPath $j.target -PathType Container;"
                    f"$registered=@(Get-VASProjects -Root '{quote(root)}')[0].createIndex;"
                    "[pscustomobject]@{status=$j.status;warning=$warning;targetExists=$exists;createIndex=[bool]$registered}|ConvertTo-Json -Compress"
                )
            else:
                tail = (
                    f"$before=(Get-Content -LiteralPath '{quote(root / 'workspace' / '.vas' / 'project-knowledge.json')}' -Raw|ConvertFrom-Json).entries.Count;"
                    f"$registered=@(Get-VASProjects -Root '{quote(root)}')[0].createIndex;"
                    f"$u=Undo-VASProjectImport -Root '{quote(root)}' -JobId $j.jobId;"
                    f"$after=(Get-Content -LiteralPath '{quote(root / 'workspace' / '.vas' / 'project-knowledge.json')}' -Raw|ConvertFrom-Json).entries.Count;"
                    "[pscustomobject]@{status=$j.status;before=$before;undo=$u.status;after=$after;createIndex=[bool]$registered}|ConvertTo-Json -Compress"
                )
            enabled = "$true" if create_index else "$false"
            command = (
                f"Import-Module '{quote(module)}' -Force;"
                f"$s=Select-VASProjectFolder -Root '{quote(root)}' -Path '{quote(source)}';"
                f"$j=Import-VASProject -Root '{quote(root)}' -SelectionId $s.selectionId -CreateIndex {enabled};" + tail
            )
            arguments = [shell, "-NoProfile", "-NonInteractive"]
            if Path(shell).name.casefold() == "powershell.exe":
                arguments += ["-ExecutionPolicy", "Bypass"]
            result = subprocess.run(
                arguments + ["-Command", command], capture_output=True, text=True, encoding="utf-8"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout.strip().splitlines()[-1])

    def test_import_builds_index_and_undo_rebuilds_it(self) -> None:
        result = self.run_hook_flow()
        self.assertEqual(
            result,
            {"status": "ready", "before": 1, "undo": "rolled_back", "after": 0, "createIndex": True},
        )

    def test_import_without_opt_in_does_not_index_content(self) -> None:
        result = self.run_hook_flow(create_index=False)
        self.assertEqual(result["before"], 0)
        self.assertFalse(result["createIndex"])
        self.assertEqual(result["after"], 0)

    def test_index_failure_warns_without_rolling_back_import(self) -> None:
        result = self.run_hook_flow(break_output=True)
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["targetExists"])
        self.assertTrue(result["createIndex"])
        self.assertIn("RAG", result["warning"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
