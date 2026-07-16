"""Safe, offline migration engine for existing VAS projects."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
EXCLUDED_DIRS = {
    ".cache", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".staging",
    ".tox", ".vas_backups", ".venv", ".vs", ".vscode", "__pycache__",
    "bower_components", "build", "coverage", "dist", "env", "node_modules",
    "out", "target", "test-results", "venv",
}
EXCLUDED_FILES = {".coverage", ".ds_store", "desktop.ini", "thumbs.db"}
SECRET_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}
ENTRYPOINT_NAMES = {
    "app.py", "application.py", "index.html", "main.go", "main.py", "main.rs",
    "manage.py", "server.js", "server.py", "src/main.ts", "src/main.tsx",
    "src/index.js", "src/index.ts", "src/index.tsx",
}
STACK_SENTINELS = {
    "angular.json": "Angular", "cargo.toml": "Rust", "composer.json": "PHP",
    "go.mod": "Go", "package.json": "JavaScript/TypeScript", "pom.xml": "Java",
    "pyproject.toml": "Python", "requirements.txt": "Python",
    "vite.config.js": "Vite", "vite.config.ts": "Vite",
}


class MigrationError(RuntimeError):
    """Base migration error."""


class VerificationError(MigrationError):
    """Raised when source, archive, or destination verification fails."""


class TargetExistsError(MigrationError):
    """Raised rather than overwriting an existing destination."""

    def __init__(self, target: Path, suggestion: Path):
        self.target = target
        self.suggestion = suggestion
        super().__init__(f"대상이 이미 존재합니다: {target} (제안: {suggestion.name})")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_reparse(path: Path, item_stat: os.stat_result | None = None) -> bool:
    try:
        data = item_stat or path.lstat()
    except OSError:
        return True
    attrs = getattr(data, "st_file_attributes", 0)
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attrs & marker)


def _safe_name(value: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")[:80]
    if not name or name in {".", ".."}:
        raise MigrationError("유효한 프로젝트 이름이 필요합니다.")
    if re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", name.upper()):
        name = f"_{name}"
    return name


def _secret_kind(relative_path: str) -> str | None:
    name = Path(relative_path).name.lower()
    if name == ".env" or (name.startswith(".env.") and not any(
        token in name for token in ("example", "sample", "template")
    )):
        return "environment"
    if Path(name).suffix in SECRET_SUFFIXES:
        return "private-key"
    if re.search(r"(^|[-_.])(credentials?|secrets?|service[-_.]?account)([-_.]|$)", name):
        return "credentials"
    if name in {"id_rsa", "id_ed25519", "known_hosts"}:
        return "ssh"
    return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MigrationManager:
    """Analyze, archive, import, delete, and roll back local projects safely."""

    def __init__(self, root: str | os.PathLike[str], large_file_mb: int = 50):
        self.root = Path(root).resolve()
        self.workspace = self.root / "workspace"
        self.projects = self.workspace / "projects"
        self.staging = self.workspace / ".staging"
        self.backups = self.root / ".vas_backups" / "migrations"
        self.large_file_bytes = max(1, large_file_mb) * 1024 * 1024

    def _validate_source(self, source: Path, must_exist: bool = True) -> Path:
        source = source.expanduser().resolve(strict=False)
        if must_exist and not source.is_dir():
            raise MigrationError(f"원본 폴더가 존재하지 않습니다: {source}")
        if source.exists() and _is_reparse(source):
            raise MigrationError("심볼릭 링크 또는 리파스 포인트를 원본으로 사용할 수 없습니다.")
        if source == self.root or _is_relative_to(self.root, source) or _is_relative_to(source, self.root):
            raise MigrationError("VAS 루트와 그 내부 또는 상위 폴더는 가져올 수 없습니다.")
        for protected in (self.projects, self.staging, self.backups):
            if _is_relative_to(source, protected):
                raise MigrationError(f"관리 경로 내부는 다시 가져올 수 없습니다: {protected}")
        return source

    def _validate_target(self, target: Path) -> Path:
        target = target.resolve(strict=False)
        if target.parent != self.projects.resolve(strict=False):
            raise MigrationError("프로젝트 관리 경로 밖의 대상은 사용할 수 없습니다.")
        return target

    def _walk(self, source: Path) -> tuple[list[tuple[str, Path, int]], list[dict[str, str]]]:
        files: list[tuple[str, Path, int]] = []
        skipped: list[dict[str, str]] = []
        pending = [source]
        while pending:
            folder = pending.pop()
            try:
                entries = sorted(os.scandir(folder), key=lambda item: item.name.casefold())
            except OSError as error:
                raise MigrationError(f"폴더를 읽을 수 없습니다: {folder}: {error}") from error
            for entry in entries:
                path = Path(entry.path)
                rel = path.relative_to(source).as_posix()
                try:
                    item_stat = entry.stat(follow_symlinks=False)
                except OSError as error:
                    raise MigrationError(f"항목을 읽을 수 없습니다: {rel}: {error}") from error
                if _is_reparse(path, item_stat):
                    skipped.append({"path": rel, "reason": "reparse-point"})
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.casefold() in EXCLUDED_DIRS:
                        skipped.append({"path": rel, "reason": "dependency-or-cache"})
                    else:
                        pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    lower = entry.name.casefold()
                    if lower in EXCLUDED_FILES or lower.endswith((".pyc", ".pyo")):
                        skipped.append({"path": rel, "reason": "cache-file"})
                    else:
                        files.append((rel, path, item_stat.st_size))
        files.sort(key=lambda item: item[0].casefold())
        skipped.sort(key=lambda item: item["path"].casefold())
        return files, skipped

    def _suggest_target(self, project_name: str) -> Path:
        candidate = self.projects / project_name
        if not candidate.exists():
            return candidate
        index = 2
        while (self.projects / f"{project_name}-{index}").exists():
            index += 1
        return self.projects / f"{project_name}-{index}"

    def analyze(self, source: str | os.PathLike[str]) -> dict[str, Any]:
        source_path = self._validate_source(Path(source))
        files, skipped = self._walk(source_path)
        paths = {relative.casefold() for relative, _, _ in files}
        extensions: dict[str, int] = {}
        stacks: set[str] = set()
        entrypoints: list[str] = []
        secrets: list[dict[str, str]] = []
        large: list[dict[str, Any]] = []
        for relative, _, size in files:
            lower = relative.casefold()
            suffix = Path(lower).suffix or "(none)"
            extensions[suffix] = extensions.get(suffix, 0) + 1
            if lower in STACK_SENTINELS:
                stacks.add(STACK_SENTINELS[lower])
            if lower in ENTRYPOINT_NAMES or Path(lower).name in ENTRYPOINT_NAMES:
                entrypoints.append(relative)
            secret_kind = _secret_kind(relative)
            if secret_kind:
                secrets.append({"path": relative, "kind": secret_kind})
            if size >= self.large_file_bytes:
                large.append({"path": relative, "size": size})
        if any(Path(path).suffix in {".py", ".pyw"} for path in paths):
            stacks.add("Python")
        if any(Path(path).suffix in {".js", ".jsx", ".ts", ".tsx"} for path in paths):
            stacks.add("JavaScript/TypeScript")
        if any(Path(path).suffix in {".html", ".css"} for path in paths):
            stacks.add("Web")
        name = _safe_name(source_path.name)
        git_marker = source_path / ".git"
        return {
            "schema": SCHEMA_VERSION,
            "source": str(source_path),
            "project_name": name,
            "suggested_target": str(self._suggest_target(name)),
            "file_count": len(files),
            "total_size": sum(item[2] for item in files),
            "stacks": sorted(stacks),
            "entrypoints": sorted(entrypoints)[:50],
            "extensions": dict(sorted(extensions.items(), key=lambda item: (-item[1], item[0]))),
            "git": {
                "present": git_marker.exists(),
                "kind": "directory" if git_marker.is_dir() else "file" if git_marker.is_file() else None,
                "bundle_available": bool(shutil.which("git")),
            },
            "secret_files": secrets,
            "large_files": large,
            "skipped": skipped,
        }

    def _manifest_for_tree(self, source: Path) -> list[dict[str, Any]]:
        files, _ = self._walk(source)
        return [
            {"path": relative, "size": size, "sha256": _sha256_file(path)}
            for relative, path, size in files
        ]

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise MigrationError(f"상태 파일을 읽을 수 없습니다: {path}") from error
        if not isinstance(value, dict):
            raise MigrationError(f"잘못된 상태 파일입니다: {path}")
        return value

    def _verify_tree(self, root: Path, manifest: dict[str, Any]) -> None:
        if not root.is_dir() or _is_reparse(root):
            raise VerificationError(f"검증할 폴더가 없습니다: {root}")
        actual = self._manifest_for_tree(root)
        if actual != manifest.get("files"):
            raise VerificationError(f"파일 해시 또는 목록이 일치하지 않습니다: {root}")

    @staticmethod
    def _verify_archive(archive: Path, manifest: dict[str, Any]) -> None:
        expected = manifest.get("files", [])
        expected_paths = [item["path"] for item in expected]
        try:
            with zipfile.ZipFile(archive, "r") as bundle:
                names = [info.filename for info in bundle.infolist() if not info.is_dir()]
                if names != expected_paths:
                    raise VerificationError("ZIP 파일 목록이 manifest와 일치하지 않습니다.")
                for item in expected:
                    digest = hashlib.sha256()
                    with bundle.open(item["path"], "r") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(chunk)
                    if digest.hexdigest() != item["sha256"]:
                        raise VerificationError(f"ZIP 해시가 일치하지 않습니다: {item['path']}")
        except (OSError, zipfile.BadZipFile, KeyError) as error:
            raise VerificationError(f"ZIP을 검증할 수 없습니다: {archive}") from error

    @staticmethod
    def _extract_archive(archive: Path, destination: Path, manifest: dict[str, Any]) -> None:
        destination.mkdir(parents=True, exist_ok=False)
        base = destination.resolve()
        with zipfile.ZipFile(archive, "r") as bundle:
            for item in manifest["files"]:
                target = destination / Path(item["path"])
                resolved = target.resolve(strict=False)
                if not _is_relative_to(resolved, base):
                    raise VerificationError(f"안전하지 않은 ZIP 경로: {item['path']}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(item["path"], "r") as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)

    def _create_archive(self, source: Path, job_dir: Path, job_id: str,
                        project_name: str) -> tuple[Path, Path, dict[str, Any]]:
        job_dir.mkdir(parents=True, exist_ok=False)
        archive = job_dir / "project.zip"
        files, skipped = self._walk(source)
        records: list[dict[str, Any]] = []
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as bundle:
            for relative, path, _ in files:
                source_stat = path.stat()
                stamp = time.localtime(max(source_stat.st_mtime, 315532800))[:6]
                info = zipfile.ZipInfo(relative, stamp)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (source_stat.st_mode & 0xFFFF) << 16
                digest = hashlib.sha256()
                size = 0
                with path.open("rb") as handle, bundle.open(info, "w") as output:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                        size += len(chunk)
                        output.write(chunk)
                records.append({"path": relative, "size": size, "sha256": digest.hexdigest()})
        manifest = {
            "schema": SCHEMA_VERSION,
            "job_id": job_id,
            "project_name": project_name,
            "source": str(source),
            "created_at": _utc_now(),
            "files": records,
            "skipped": skipped,
        }
        manifest_path = job_dir / "manifest.json"
        self._write_json(manifest_path, manifest)
        self._verify_archive(archive, manifest)
        self._verify_tree(source, manifest)
        return archive, manifest_path, manifest

    @staticmethod
    def _make_git_bundle(source: Path, destination: Path) -> Path | None:
        if not (source / ".git").exists() or not shutil.which("git"):
            return None
        command = [
            "git", "-c", f"safe.directory={source}", "-C", str(source),
            "bundle", "create", str(destination), "--all",
        ]
        try:
            result = subprocess.run(command, capture_output=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0 or not destination.is_file():
            destination.unlink(missing_ok=True)
            return None
        return destination

    def _state_paths(self) -> Iterable[Path]:
        if not self.backups.is_dir():
            return []
        return sorted(self.backups.glob("*/state.json"), reverse=True)

    def _load_state(self, job_id: str) -> tuple[Path, dict[str, Any]]:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", job_id):
            raise MigrationError("잘못된 작업 ID입니다.")
        path = self.backups / job_id / "state.json"
        if not path.is_file():
            raise MigrationError(f"마이그레이션 작업을 찾을 수 없습니다: {job_id}")
        return path, self._read_json(path)

    def _find_idempotent(self, source: Path, target: Path) -> dict[str, Any] | None:
        for state_path in self._state_paths():
            state = self._read_json(state_path)
            if state.get("source") != str(source) or state.get("target") != str(target):
                continue
            if state.get("status") not in {"ready", "source_deleted"}:
                continue
            manifest = self._read_json(Path(state["manifest"]))
            try:
                self._verify_archive(Path(state["archive"]), manifest)
                self._verify_tree(target, manifest)
                if source.exists():
                    self._verify_tree(source, manifest)
                elif state.get("status") != "source_deleted":
                    continue
            except VerificationError:
                continue
            return self._result(state, idempotent=True)
        return None

    @staticmethod
    def _result(state: dict[str, Any], idempotent: bool = False) -> dict[str, Any]:
        return {
            "job_id": state["job_id"], "status": state["status"],
            "source": state["source"], "target": state["target"],
            "archive": state["archive"], "manifest": state["manifest"],
            "git_bundle": state.get("git_bundle"), "idempotent": idempotent,
        }

    def import_project(self, source: str | os.PathLike[str], project_name: str | None = None) -> dict[str, Any]:
        source_path = self._validate_source(Path(source), must_exist=False)
        name = _safe_name(project_name or source_path.name)
        target = self.projects / name
        existing = self._find_idempotent(source_path, target) if target.exists() else None
        if existing:
            return existing
        if not source_path.is_dir():
            raise MigrationError(f"원본 폴더가 존재하지 않습니다: {source_path}")
        self._validate_source(source_path)
        if target.exists():
            raise TargetExistsError(target, self._suggest_target(name))
        job_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        job_dir = self.backups / job_id
        stage_job = self.staging / job_id
        state_path = job_dir / "state.json"
        state: dict[str, Any] = {
            "schema": SCHEMA_VERSION, "job_id": job_id, "status": "archiving",
            "source": str(source_path), "project_name": name, "target": str(target),
            "created_at": _utc_now(), "updated_at": _utc_now(),
        }
        try:
            archive, manifest_path, manifest = self._create_archive(source_path, job_dir, job_id, name)
            state.update({"archive": str(archive), "manifest": str(manifest_path)})
            git_bundle = self._make_git_bundle(source_path, job_dir / "project.bundle")
            state["git_bundle"] = str(git_bundle) if git_bundle else None
            state["status"] = "staging"
            self._write_json(state_path, state)
            stage_project = stage_job / name
            stage_job.mkdir(parents=True, exist_ok=False)
            self._extract_archive(archive, stage_project, manifest)
            self._verify_tree(stage_project, manifest)
            self.projects.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise TargetExistsError(target, self._suggest_target(name))
            os.rename(stage_project, target)
            self._verify_tree(target, manifest)
            state.update({"status": "ready", "updated_at": _utc_now()})
            self._write_json(state_path, state)
            return self._result(state)
        except Exception as error:
            if job_dir.exists():
                state.update({"status": "failed", "updated_at": _utc_now(), "error": type(error).__name__})
                self._write_json(state_path, state)
            raise
        finally:
            shutil.rmtree(stage_job, ignore_errors=True)

    def delete_source(self, job_id: str, confirmation: str) -> dict[str, Any]:
        state_path, state = self._load_state(job_id)
        if state.get("status") == "source_deleted" and not Path(state["source"]).exists():
            return self._result(state, idempotent=True)
        if state.get("status") != "ready":
            raise MigrationError("준비 완료된 작업만 원본을 정리할 수 있습니다.")
        if confirmation != state["project_name"]:
            raise MigrationError("원본 삭제 확인 문자열이 프로젝트명과 일치하지 않습니다.")
        source = self._validate_source(Path(state["source"]))
        target = self._validate_target(Path(state["target"]))
        manifest = self._read_json(Path(state["manifest"]))
        self._verify_archive(Path(state["archive"]), manifest)
        self._verify_tree(source, manifest)
        self._verify_tree(target, manifest)
        shutil.rmtree(source)
        state.update({"status": "source_deleted", "source_deleted_at": _utc_now(), "updated_at": _utc_now()})
        self._write_json(state_path, state)
        return self._result(state)

    def rollback(self, job_id: str) -> dict[str, Any]:
        state_path, state = self._load_state(job_id)
        if state.get("status") == "rolled_back":
            return self._result(state, idempotent=True)
        if state.get("status") not in {"ready", "source_deleted"}:
            raise MigrationError("완료된 작업만 롤백할 수 있습니다.")
        source = self._validate_source(Path(state["source"]), must_exist=False)
        target = self._validate_target(Path(state["target"]))
        archive = Path(state["archive"])
        manifest = self._read_json(Path(state["manifest"]))
        self._verify_archive(archive, manifest)
        if target.exists():
            self._verify_tree(target, manifest)
        if not source.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            restore = source.parent / f".{source.name}.vas-restore-{job_id}"
            if restore.exists():
                shutil.rmtree(restore)
            self._extract_archive(archive, restore, manifest)
            self._verify_tree(restore, manifest)
            if source.exists():
                raise MigrationError(f"복원 대상이 이미 존재합니다: {source}")
            os.rename(restore, source)
            self._verify_tree(source, manifest)
        if target.exists():
            shutil.rmtree(target)
        state.update({"status": "rolled_back", "rolled_back_at": _utc_now(), "updated_at": _utc_now()})
        self._write_json(state_path, state)
        return self._result(state)
