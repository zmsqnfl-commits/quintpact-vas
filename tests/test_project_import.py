from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
SCRIPTS = BASE / "scripts"
sys.path.insert(0, str(SCRIPTS))

from vas_project_import import (  # noqa: E402
    MigrationError,
    MigrationManager,
    TargetExistsError,
    VerificationError,
)


def make_project(parent: Path, name: str = "legacy-app") -> Path:
    source = parent / name
    (source / "src").mkdir(parents=True)
    (source / "assets").mkdir()
    (source / "node_modules" / "ignored").mkdir(parents=True)
    (source / "__pycache__").mkdir()
    (source / ".git").mkdir()
    (source / "index.html").write_text("<h1>legacy</h1>", encoding="utf-8")
    (source / "src" / "main.ts").write_text("export const ready = true;", encoding="utf-8")
    (source / "assets" / "logo.bin").write_bytes(b"asset")
    (source / ".env").write_text("API_KEY=TOP_SECRET_VALUE", encoding="utf-8")
    (source / "package.json").write_text(
        '{"scripts":{"postinstall":"echo MUST_NOT_RUN"}}', encoding="utf-8"
    )
    (source / ".git" / "config").write_text("[core]\nrepositoryformatversion=0\n", encoding="utf-8")
    (source / "node_modules" / "ignored" / "pkg.js").write_text("ignored", encoding="utf-8")
    (source / "__pycache__" / "main.pyc").write_bytes(b"ignored")
    return source


@pytest.fixture
def setup(tmp_path: Path) -> tuple[MigrationManager, Path, Path]:
    root = tmp_path / "vas"
    root.mkdir()
    source = make_project(tmp_path / "inputs")
    return MigrationManager(root, large_file_mb=1), root, source


def test_analyze_is_read_only_and_redacts_secret_values(setup: tuple[MigrationManager, Path, Path]) -> None:
    manager, root, source = setup
    (source / "large.dat").write_bytes(b"x" * (1024 * 1024))
    before = sorted(path.relative_to(source) for path in source.rglob("*"))
    report = manager.analyze(source)
    after = sorted(path.relative_to(source) for path in source.rglob("*"))

    assert before == after
    assert not (root / "workspace").exists()
    assert "JavaScript/TypeScript" in report["stacks"]
    assert "index.html" in report["entrypoints"]
    assert report["git"] == {
        "present": True, "kind": "directory", "bundle_available": bool(shutil.which("git"))
    }
    assert {item["path"] for item in report["secret_files"]} == {".env"}
    assert "TOP_SECRET_VALUE" not in json.dumps(report)
    assert {item["path"] for item in report["large_files"]} == {"large.dat"}
    assert {item["path"] for item in report["skipped"]} >= {"node_modules", "__pycache__"}
    assert not (source / "MUST_NOT_RUN").exists()


def test_vas_root_ancestors_and_internal_folders_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "vas"
    (root / "src").mkdir(parents=True)
    manager = MigrationManager(root)
    for forbidden in (tmp_path, root, root / "src"):
        with pytest.raises(MigrationError, match="VAS 루트"):
            manager.analyze(forbidden)


def test_reparse_points_are_reported_and_never_followed(setup: tuple[MigrationManager, Path, Path],
                                                         tmp_path: Path) -> None:
    manager, _, source = setup
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.txt").write_text("outside", encoding="utf-8")
    link = source / "linked-outside"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("이 환경에서는 디렉터리 심볼릭 링크를 만들 수 없습니다.")
    report = manager.analyze(source)
    assert {item["path"] for item in report["skipped"]} >= {"linked-outside"}
    result = manager.import_project(source)
    assert not (Path(result["target"]) / "linked-outside").exists()


def test_import_archives_verifies_and_promotes_without_cache(setup: tuple[MigrationManager, Path, Path]) -> None:
    manager, root, source = setup
    result = manager.import_project(source)
    target = root / "workspace" / "projects" / "legacy-app"
    archive = Path(result["archive"])
    manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    manifest_paths = [item["path"] for item in manifest["files"]]

    assert result["status"] == "ready"
    assert Path(result["target"]) == target
    assert (target / ".env").read_text(encoding="utf-8") == "API_KEY=TOP_SECRET_VALUE"
    assert (target / "assets" / "logo.bin").read_bytes() == b"asset"
    assert (target / ".git" / "config").is_file()
    assert not (target / "node_modules").exists()
    assert not (target / "__pycache__").exists()
    assert manifest_paths == sorted(manifest_paths, key=str.casefold)
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.namelist() == manifest_paths
        assert bundle.testzip() is None
    assert not any((root / "workspace" / ".staging").iterdir())
    assert (archive.parent / "state.json").is_file()


def test_korean_project_name_and_spaced_paths_are_supported(tmp_path: Path) -> None:
    root = tmp_path / "VAS root"
    root.mkdir()
    source = make_project(tmp_path / "원본 프로그램 모음", "기존 프로그램")
    (source / "한글 문서.txt").write_text("정상", encoding="utf-8")
    result = MigrationManager(root).import_project(source)
    assert Path(result["target"]).name == "기존 프로그램"
    assert (Path(result["target"]) / "한글 문서.txt").read_text(encoding="utf-8") == "정상"


def test_same_import_is_idempotent_and_conflict_suggests_suffix(setup: tuple[MigrationManager, Path, Path],
                                                                tmp_path: Path) -> None:
    manager, root, source = setup
    first = manager.import_project(source)
    second = manager.import_project(source)
    assert second["job_id"] == first["job_id"]
    assert second["idempotent"] is True

    other = make_project(tmp_path / "other", "legacy-app")
    (other / "index.html").write_text("different", encoding="utf-8")
    with pytest.raises(TargetExistsError) as caught:
        manager.import_project(other)
    assert caught.value.suggestion.name == "legacy-app-2"
    assert (root / "workspace" / "projects" / "legacy-app" / "index.html").read_text(
        encoding="utf-8"
    ) == "<h1>legacy</h1>"


def test_delete_requires_typed_name_and_full_reverification(setup: tuple[MigrationManager, Path, Path]) -> None:
    manager, _, source = setup
    result = manager.import_project(source)
    target = Path(result["target"])
    with pytest.raises(MigrationError, match="확인 문자열"):
        manager.delete_source(result["job_id"], "wrong-name")

    original = (target / "index.html").read_text(encoding="utf-8")
    (target / "index.html").write_text("changed", encoding="utf-8")
    with pytest.raises(VerificationError):
        manager.delete_source(result["job_id"], "legacy-app")
    assert source.exists()
    (target / "index.html").write_text(original, encoding="utf-8")

    deleted = manager.delete_source(result["job_id"], "legacy-app")
    assert deleted["status"] == "source_deleted"
    assert not source.exists()
    assert manager.delete_source(result["job_id"], "anything")["idempotent"] is True


def test_rollback_restores_deleted_source_and_removes_unchanged_target(
    setup: tuple[MigrationManager, Path, Path]
) -> None:
    manager, _, source = setup
    result = manager.import_project(source)
    manager.delete_source(result["job_id"], "legacy-app")
    rolled_back = manager.rollback(result["job_id"])
    assert rolled_back["status"] == "rolled_back"
    assert source.is_dir()
    assert (source / ".env").read_text(encoding="utf-8") == "API_KEY=TOP_SECRET_VALUE"
    assert not Path(result["target"]).exists()
    assert manager.rollback(result["job_id"])["idempotent"] is True


def test_corrupt_archive_blocks_destructive_actions(setup: tuple[MigrationManager, Path, Path]) -> None:
    manager, _, source = setup
    result = manager.import_project(source)
    Path(result["archive"]).write_bytes(b"not-a-zip")
    with pytest.raises(VerificationError):
        manager.delete_source(result["job_id"], "legacy-app")
    with pytest.raises(VerificationError):
        manager.rollback(result["job_id"])
    assert source.is_dir()
    assert Path(result["target"]).is_dir()


def test_git_repository_is_preserved_and_bundled(tmp_path: Path) -> None:
    git = shutil.which("git")
    if not git:
        pytest.skip("git 실행 파일이 없습니다.")
    root = tmp_path / "vas"
    root.mkdir()
    source = tmp_path / "inputs" / "git-app"
    source.mkdir(parents=True)
    (source / "README.md").write_text("git history", encoding="utf-8")
    subprocess.run([git, "init", str(source)], check=True, capture_output=True)
    subprocess.run([git, "-C", str(source), "add", "README.md"], check=True)
    subprocess.run(
        [git, "-C", str(source), "-c", "user.name=VAS Test", "-c",
         "user.email=vas@example.invalid", "commit", "-m", "initial"],
        check=True, capture_output=True,
    )
    result = MigrationManager(root).import_project(source)
    assert (Path(result["target"]) / ".git" / "HEAD").is_file()
    assert result["git_bundle"]
    verify = subprocess.run(
        [git, "-C", result["target"], "bundle", "verify", result["git_bundle"]],
        capture_output=True,
    )
    assert verify.returncode == 0


def test_legacy_wrapper_dry_run_and_delete_rerun_are_idempotent(
    setup: tuple[MigrationManager, Path, Path]
) -> None:
    _, root, source = setup
    wrapper = SCRIPTS / "vas-migration-archive.py"
    dry = subprocess.run(
        [sys.executable, str(wrapper), str(source), "--dry-run", "--root", str(root), "--json"],
        check=False, capture_output=True, text=True, encoding="utf-8",
    )
    assert dry.returncode == 0, dry.stderr
    assert json.loads(dry.stdout)["file_count"] > 0
    assert not (root / ".vas_backups").exists()

    command = [
        sys.executable, str(wrapper), str(source), "--delete-source",
        "--confirm-name", "legacy-app", "--root", str(root), "--json",
    ]
    first = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    second = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert json.loads(first.stdout)["status"] == "source_deleted"
    assert json.loads(second.stdout)["idempotent"] is True


def test_powershell_module_persists_selection_job_and_registry(
    setup: tuple[MigrationManager, Path, Path]
) -> None:
    _, root, source = setup
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        pytest.skip("PowerShell 실행 파일이 없습니다.")
    quote = lambda value: str(value).replace("'", "''")
    module = SCRIPTS / "VAS.Migration.psm1"
    command = (
        f"Import-Module '{quote(module)}' -Force; "
        f"$s=Select-VASProjectFolder -Root '{quote(root)}' -Path '{quote(source)}'; "
        f"$a=Analyze-VASProject -Root '{quote(root)}' -SelectionId $s.selectionId; "
        f"$j=Import-VASProject -Root '{quote(root)}' -SelectionId $s.selectionId -Goal 'redesign'; "
        f"$status=Get-VASMigrationStatus -Root '{quote(root)}' -JobId $j.jobId; "
        f"$p=@(Get-VASProjects -Root '{quote(root)}'); "
        f"$d=Remove-VASSourceAdvanced -Root '{quote(root)}' -JobId $j.jobId -Confirmation 'legacy-app'; "
        f"$u=Undo-VASProjectImport -Root '{quote(root)}' -JobId $j.jobId; "
        f"$after=@(Get-VASProjects -Root '{quote(root)}'); "
        "[pscustomobject]@{selection=$s;analysis=$a;job=$j;status=$status;projects=$p;deleted=$d;undo=$u;after=$after}|ConvertTo-Json -Depth 8 -Compress"
    )
    result = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-Command", command],
        check=False, capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["analysis"]["fileCount"] > 0
    assert payload["job"]["status"] == "ready"
    assert payload["status"]["status"] == "ready"
    assert len(payload["projects"]) == 1
    assert payload["projects"][0]["goal"] == "redesign"
    assert payload["deleted"]["status"] == "source_deleted"
    assert payload["undo"]["status"] == "rolled_back"
    assert payload["after"] == []
    assert (root / "workspace" / ".vas" / "selections.json").is_file()
    assert (root / "workspace" / ".vas" / "jobs" / f"{payload['job']['jobId']}.json").is_file()
    assert (root / "workspace" / ".vas" / "projects.json").is_file()
