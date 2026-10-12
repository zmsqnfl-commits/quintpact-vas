"""Explicit bounded file observations, privacy boundaries and common race rejection."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vas_work_files as files
from vas_ai_contract import canonical
from vas_session import SessionError, identity


@pytest.fixture
def project(tmp_path):
    target = tmp_path / "app"
    target.mkdir()
    (target / "main.py").write_text("private body fixture", encoding="utf-8")
    (target / "tests").mkdir()
    (target / "tests/check.py").write_text("test fixture", encoding="utf-8")
    return target


def take(target, paths=None):
    return files.capture(target, identity(target), paths or ["main.py", "tests/check.py"])


def hashed(entries):
    return {"files": entries, "sha256": hashlib.sha256(canonical(entries)).hexdigest()}


def test_sorted_readonly_capture_exposes_hashes_but_no_body_or_absolute_path(project):
    before = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    snapshot = take(project, ["tests/check.py", "main.py", "future/new.py"])
    assert [entry["path"] for entry in snapshot["files"]] == ["future/new.py", "main.py", "tests/check.py"]
    assert snapshot["files"][0] == {"path": "future/new.py", "state": "missing", "bytes": None, "sha256": None}
    assert files.validate_snapshot(snapshot) == snapshot
    assert snapshot["files"][1]["sha256"] == hashlib.sha256(b"private body fixture").hexdigest()
    serialized = json.dumps(snapshot)
    assert "private body fixture" not in serialized and str(project) not in serialized
    assert before == {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}


def test_compare_modified_created_deleted_and_explicit_allowed_scope(project):
    paths = ["main.py", "tests/check.py", "new.py"]
    before = take(project, paths)
    (project / "main.py").write_text("updated", encoding="utf-8")
    (project / "tests/check.py").unlink()
    (project / "new.py").write_text("new", encoding="utf-8")
    after = take(project, paths)
    assert files.compare(before, after, ["main.py", "new.py"]) == {
        "changedFiles": ["main.py", "new.py", "tests/check.py"], "outOfScopeFiles": ["tests/check.py"]}
    assert files.compare(after, after) == {"changedFiles": [], "outOfScopeFiles": []}


def test_mtime_only_change_between_observations_keeps_content_identity(project):
    before = take(project)
    target = project / "main.py"
    info = target.stat()
    os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
    assert take(project) == before


def test_unobserved_files_are_not_scanned_or_claimed_covered(project):
    (project / ".env").write_text("password=fixture-secret", encoding="utf-8")
    before = take(project, ["main.py"])
    (project / ".env").write_text("password=changed-secret", encoding="utf-8")
    (project / "outside.py").write_text("unobserved change", encoding="utf-8")
    assert take(project, ["main.py"]) == before
    assert len(before["files"]) == 1


@pytest.mark.parametrize("raw", [None, {}, "main.py", (), [], [False], [1], [None],
    ["main.py", "MAIN.py"], ["main.py", "main.py"]],
    ids=["null", "mapping", "string", "tuple", "empty", "bool", "int", "null-path", "case-alias", "duplicate"])
def test_paths_require_bounded_distinct_string_list(raw):
    with pytest.raises(SessionError, match="^work_files_"):
        files.normalize_paths(raw)


@pytest.mark.parametrize("path", ["../secret", "src/../main.py", "src//main.py", "src/./main.py",
    "/home/user/main.py", "C:/main.py", "C:main.py", "\\\\share\\main.py", "src\\main.py",
    "main.py/", " main.py", "main.py ", "src /main.py", "src./main.py", "main.py.",
    "src/NUL.py", "AUX", "COM1.txt", "lpt9", "COM¹.txt", "CONIN$", "CONOUT$", "src/a:stream", "src/a\n.py",
    "src/a\u200b.py", "a?b.py", "a*b.py", 'a"b.py', "a<b.py", "a|b.py", "x" * 301,
    ".git/config", ".ssh/config", ".aws/config", ".env", ".env.local", "src/.env.production",
    "private-key.json", "secrets.json", "credentials/account.json", "keys/foo.txt", "api_key.txt",
    "id_rsa", "id_ed25519.pub", "cert.pem", "cert.key", "cert.p12", "cert.pfx",
    "vas-session-store.json", ".npmrc", "service-account.json",
    "src/ghp_abcdefghijklmnopqrst.py", "person@example.com.py"])
def test_unsafe_and_private_paths_are_rejected_without_rewriting(path):
    with pytest.raises(SessionError, match="^work_files_path_invalid$"):
        files.normalize_paths([path])


def test_valid_paths_remain_exact_and_empty_only_when_requested():
    assert files.normalize_paths(["한글 파일.py", ".agents/rules.md", "src/app.test.js"]) == [
        ".agents/rules.md", "src/app.test.js", "한글 파일.py"]
    assert files.normalize_paths([], allow_empty=True) == []


def test_file_count_and_byte_limits(project, monkeypatch):
    with pytest.raises(SessionError, match="^work_files_invalid$"):
        files.normalize_paths([f"{i}.py" for i in range(65)])
    monkeypatch.setattr(files, "MAX_FILE_BYTES", 8)
    with pytest.raises(SessionError, match="^work_files_too_large$"):
        take(project)
    monkeypatch.setattr(files, "MAX_FILE_BYTES", 64)
    monkeypatch.setattr(files, "MAX_TOTAL_BYTES", 25)
    with pytest.raises(SessionError, match="^work_files_too_large$"):
        take(project)


def test_exact_byte_limit_and_empty_file(project, monkeypatch):
    (project / "main.py").write_bytes(b"1234")
    (project / "tests/check.py").write_bytes(b"")
    monkeypatch.setattr(files, "MAX_FILE_BYTES", 4)
    monkeypatch.setattr(files, "MAX_TOTAL_BYTES", 4)
    snapshot = take(project)
    assert [entry["bytes"] for entry in snapshot["files"]] == [4, 0]
    assert files.validate_snapshot(snapshot) == snapshot


def test_hardlink_and_directory_are_rejected(project, tmp_path):
    os.link(project / "main.py", tmp_path / "alias.py")
    with pytest.raises(SessionError, match="^work_files_path_invalid$"):
        take(project, ["main.py"])
    with pytest.raises(SessionError, match="^work_files_path_invalid$"):
        take(project, ["tests"])


def test_real_external_symlink_or_windows_junction_is_rejected(project, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.py").write_text("external body", encoding="utf-8")
    alias, junction = project / "alias", False
    try:
        alias.symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            pytest.skip("Host does not permit symbolic links; reparse simulation is tested separately")
        import _winapi
        try:
            _winapi.CreateJunction(str(outside), str(alias))
            junction = True
        except (AttributeError, OSError):
            pytest.skip("Host does not permit symbolic links or junctions; reparse simulation is tested separately")
    try:
        with pytest.raises(SessionError, match="^work_files_path_invalid$"):
            take(project, ["alias/private.py"])
    finally:
        # Remove only this link, without recursive traversal into its target.
        if junction:
            alias.rmdir()
        else:
            alias.unlink()
    assert (outside / "private.py").read_text(encoding="utf-8") == "external body"


@pytest.mark.parametrize("component", ["root", "parent", "file", "missing-parent"])
def test_reparse_flag_at_every_component_fails_before_read(project, monkeypatch, component):
    selected = {"root": project, "parent": project / "tests", "file": project / "tests/check.py",
                "missing-parent": project / "tests"}[component]
    real = Path.lstat
    def spoof(path, *args, **kwargs):
        info = real(path, *args, **kwargs)
        if path == selected:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info
    monkeypatch.setattr(Path, "lstat", spoof)
    monkeypatch.setattr(files.os, "read", lambda *_args: pytest.fail("unsafe file was read"))
    with pytest.raises(SessionError, match="^work_files_(path_invalid|target_changed)$"):
        take(project, ["tests/missing.py" if component == "missing-parent" else "tests/check.py"])


def test_target_identity_mismatch_and_replacement_are_rejected(project, monkeypatch):
    expected = identity(project)
    with pytest.raises(SessionError, match="^work_files_target_changed$"):
        files.capture(project, [expected[0], expected[1] + 1], ["main.py"])
    real = files._read
    def replaced(*args):
        entry = real(*args)
        previous = project.with_name("previous")
        project.rename(previous)
        project.mkdir()
        (project / "main.py").write_bytes((previous / "main.py").read_bytes())
        return entry
    monkeypatch.setattr(files, "_read", replaced)
    with pytest.raises(SessionError, match="^work_files_(changed|target_changed)$"):
        files.capture(project, expected, ["main.py"])


def test_replaced_between_stat_and_open_is_rejected_without_reading(project, monkeypatch):
    real = files.os.open
    def swapped(path, flags, *args):
        (project / "main.py").unlink()
        (project / "main.py").write_text("replacement body", encoding="utf-8")
        return real(path, flags, *args)
    monkeypatch.setattr(files.os, "open", swapped)
    monkeypatch.setattr(files.os, "read", lambda *_args: pytest.fail("replacement was read"))
    with pytest.raises(SessionError, match="^work_files_changed$"):
        take(project, ["main.py"])


@pytest.mark.parametrize("growth", [False, True])
def test_file_changes_during_read_are_rejected(project, monkeypatch, growth):
    real = files.os.read
    changed = False
    def mutate(fd, count):
        nonlocal changed
        block = real(fd, count)
        if not changed:
            changed = True
            target = project / "main.py"
            info = target.stat()
            with target.open("ab" if growth else "r+b") as handle:
                handle.write(b"changed")
            os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
        return block
    monkeypatch.setattr(files.os, "read", mutate)
    with pytest.raises(SessionError, match="^work_files_changed$"):
        take(project, ["main.py"])


def test_earlier_file_changes_while_later_file_is_read_are_rejected(project, monkeypatch):
    real = files._read
    def mutate(root, relative, *args):
        result = real(root, relative, *args)
        if relative == "tests/check.py":
            (root / "main.py").write_text("changed after sampling", encoding="utf-8")
        return result
    monkeypatch.setattr(files, "_read", mutate)
    with pytest.raises(SessionError, match="^work_files_changed$"):
        take(project)


def test_missing_file_creation_during_capture_is_rejected(project, monkeypatch):
    real = files._read
    def create_missing(*args):
        result = real(*args)
        (project / "first.py").write_text("appeared", encoding="utf-8")
        return result
    monkeypatch.setattr(files, "_read", create_missing)
    with pytest.raises(SessionError, match="^work_files_changed$"):
        take(project, ["first.py", "main.py"])


def test_os_error_has_stable_message_without_private_path(project, monkeypatch):
    def denied(*_args):
        raise PermissionError("C:/Users/private/secret.py")
    monkeypatch.setattr(files.os, "open", denied)
    with pytest.raises(SessionError, match="^work_files_unavailable$") as error:
        take(project)
    assert "private" not in str(error.value)


def test_nonregular_file_is_rejected_before_reading(project, monkeypatch):
    real = Path.lstat
    def special(path, *args, **kwargs):
        info = real(path, *args, **kwargs)
        if path == project / "main.py":
            return SimpleNamespace(st_mode=stat.S_IFIFO, st_file_attributes=0)
        return info
    monkeypatch.setattr(Path, "lstat", special)
    monkeypatch.setattr(files.os, "read", lambda *_args: pytest.fail("nonregular file was read"))
    with pytest.raises(SessionError, match="^work_files_path_invalid$"):
        take(project, ["main.py"])


def test_hardlink_created_between_stat_and_open_is_rejected(project, tmp_path, monkeypatch):
    real = files.os.open
    def linked(path, flags, *args):
        os.link(path, tmp_path / "late-alias.py")
        return real(path, flags, *args)
    monkeypatch.setattr(files.os, "open", linked)
    monkeypatch.setattr(files.os, "read", lambda *_args: pytest.fail("newly hardlinked file was read"))
    with pytest.raises(SessionError, match="^work_files_path_invalid$"):
        take(project, ["main.py"])


def test_growth_past_bound_is_limited_while_streaming(project, monkeypatch):
    target = project / "main.py"
    target.write_bytes(b"1234")
    monkeypatch.setattr(files, "MAX_FILE_BYTES", 4)
    real = files.os.read
    def growing(fd, count):
        with target.open("ab") as handle:
            handle.write(b"x")
        return real(fd, count)
    monkeypatch.setattr(files.os, "read", growing)
    with pytest.raises(SessionError, match="^work_files_too_large$"):
        take(project, ["main.py"])


@pytest.mark.parametrize("mutation", ["unknown", "digest", "missing-fields", "bool-bytes",
    "negative-bytes", "bad-file-hash", "extra-entry", "unsorted", "duplicate", "private-path"])
def test_stored_snapshot_validation_rejects_tampering_without_app_reads(project, monkeypatch, mutation):
    snapshot = deepcopy(take(project))
    entry = snapshot["files"][0]
    if mutation == "unknown": snapshot["approved"] = True
    elif mutation == "digest": snapshot["sha256"] = "0" * 64
    elif mutation == "missing-fields": entry["state"] = "missing"
    elif mutation == "bool-bytes": entry["bytes"] = True
    elif mutation == "negative-bytes": entry["bytes"] = -1
    elif mutation == "bad-file-hash": entry["sha256"] = "no"
    elif mutation == "extra-entry": entry["body"] = "must not persist"
    elif mutation == "unsorted": snapshot["files"].reverse()
    elif mutation == "duplicate": snapshot["files"].append(deepcopy(entry))
    elif mutation == "private-path": entry["path"] = ".env"
    if mutation != "digest": snapshot["sha256"] = hashlib.sha256(canonical(snapshot["files"])).hexdigest()
    monkeypatch.setattr(files.os, "open", lambda *_args: pytest.fail("validation read app"))
    with pytest.raises(SessionError, match="^work_files_"):
        files.validate_snapshot(snapshot)


def test_snapshot_total_limit_and_missing_nulls():
    entries = [{"path": f"{index:02}.py", "state": "file", "bytes": files.MAX_FILE_BYTES,
                "sha256": "0" * 64} for index in range(17)]
    with pytest.raises(SessionError, match="^work_files_invalid$"):
        files.validate_snapshot(hashed(entries))
    good = [{"path": "empty.py", "state": "missing", "bytes": None, "sha256": None}]
    assert files.validate_snapshot(hashed(good)) == hashed(good)


def test_compare_cannot_drop_coverage_or_allow_an_unobserved_path(project):
    before = take(project)
    with pytest.raises(SessionError, match="^work_files_coverage_mismatch$"):
        files.compare(before, take(project, ["main.py"]))
    with pytest.raises(SessionError, match="^work_files_coverage_mismatch$"):
        files.compare(before, before, ["unobserved.py"])
