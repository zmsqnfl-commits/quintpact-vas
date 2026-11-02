"""Explicit migration never expands the selected app source into secrets or tool files."""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/vas.py"
sys.path.insert(0, str(ROOT / "scripts"))
import vas_import as transfer
from vas_session import SessionError


@pytest.fixture
def projects(tmp_path):
    app = tmp_path / "새 프로젝트"
    (app / "ui").mkdir(parents=True)
    (app / "src").mkdir()
    (app / "src/.gitkeep").write_bytes(b"")
    (app / "ui/vas-hub.html").write_text("helper")
    (app / "Run-VAS-System.bat").write_text("launcher")
    (app / "project-layout.json").write_text('{"layout":"vas-project","version":2}')
    old = tmp_path / "예전 앱" / "src"
    old.mkdir(parents=True)
    return app, old


def run(projects, *args, source=None):
    app, old = projects
    result = subprocess.run([sys.executable, "-B", str(CLI), "--vas-root", str(app), "import",
                             "--from", source or str(old), *args], cwd=app,
                            capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.stderr == "", result.stderr
    return result.returncode, json.loads(result.stdout)


def tree(root):
    return {path.relative_to(root): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in root.rglob("*") if path.is_file()}


def test_review_and_apply_only_vetted_code_then_retry_without_writes(projects):
    app, old = projects
    (old / "client").mkdir()
    (old / "client/main.ts").write_text("export const menu = () => 1;", encoding="utf-8")
    (old / "compose.yaml").write_text("services: {}")
    manifests = b'{"name":"portable-app","private":true}'
    (old / "package.json").write_bytes(manifests)
    hidden = {"secret-key.txt": "operational-key", ".env": "V=secret", "board-settings.js": "operational-flag",
              "database.json": "operational-data", "menu-photo.jpg": "opaque-bytes",
              "unremarkable.ts": "const a = 'live_sk_1234567890ABCDEFGHIJ';",
              "encoded.ts": "const x = {password\\u003a 'not for transfer'}"}
    for name, body in hidden.items():
        (old / name).write_text(body, encoding="utf-8")
    (old / "uploads").mkdir()
    (old / "uploads/row.ts").write_text("order data")
    before, before_old = tree(app), tree(old)
    rel = os.path.relpath(old, app)
    code, preview = run(projects, source=rel)
    assert code == 0 and preview["status"] == "planned" and preview["copied"] == 0
    assert {item["path"] for item in preview["files"]} == {"client/main.ts", "compose.yaml", "package.json"}
    assert preview["applyCommand"].endswith("--apply --expected-plan " + preview["planSha256"])
    assert tree(app) == before and tree(old) == before_old
    assert all(name not in str(preview) for name in hidden)
    code, receipt = run(projects, *preview["addArguments"])
    assert code == 0 and receipt["copied"] == 3
    assert not (app / "compose.yaml").exists() and (app / "src/package.json").read_bytes() == manifests
    assert (app / "src/client/main.ts").read_bytes() == (old / "client/main.ts").read_bytes()
    assert tree(old) == before_old and all(not (app / "src" / name).exists() for name in hidden)
    copied = tree(app)
    assert run(projects, *preview["addArguments"])[1]["copied"] == 0 and tree(app) == copied


def test_changed_source_never_applies_under_reviewed_digest(projects):
    app, old = projects
    path = old / "app.py"
    path.write_text("print('first')")
    preview = run(projects)[1]
    path.write_text("print('changed')")
    code, data = run(projects, *preview["addArguments"])
    assert code == 1 and data["code"] == "import_plan_changed"
    assert not (app / "src/app.py").exists()


@pytest.mark.parametrize("other", [True, False])
def test_existing_src_is_not_overwritten_or_merged_out_of_scope(projects, other):
    app, old = projects
    (old / "a.py").write_text("A")
    (old / "z.py").write_text("Z")
    (app / "src" / ("extra.py" if other else "z.py")).write_text("KEEP")
    before = tree(app)
    code, status = run(projects)
    assert code == 1 and status["status"] == "blocked" and status["code"] == "import_destination_conflict"
    assert tree(app) == before


def test_interrupted_copy_can_resume_already_published_identical_files(projects, monkeypatch):
    app, old = projects
    (old / "a.py").write_text("print('A')")
    (old / "b.py").write_text("print('B')")
    plan = transfer.import_app(app, str(old))["planSha256"]
    original = transfer.write_candidate
    def interrupt(dest, name, data):
        if name == "b.py":
            raise OSError("simulated interruption")
        return original(dest, name, data)
    monkeypatch.setattr(transfer, "write_candidate", interrupt)
    result = transfer.import_app(app, str(old), True, plan)
    assert result["status"] == "partial" and result["pending"] == "b.py" and result["copied"] == 1
    assert (app / "src/a.py").is_file() and not (app / "src/b.py").exists()
    monkeypatch.setattr(transfer, "write_candidate", original)
    result = transfer.import_app(app, str(old), True, plan)
    assert result["matched"] == result["copied"] == 1


def test_delete_rename_and_overwrite_denied_mount_writes_only_new_files(projects, monkeypatch):
    app, old = projects
    (old / "page").mkdir()
    (old / "page/app.py").write_bytes(b"print('hello')")
    before = tree(old)
    plan = transfer.import_app(app, str(old))["planSha256"]
    def denied(*args, **kwargs):
        pytest.fail("import tried to delete, rename or replace")
    original_open = os.open
    def create_only(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_TRUNC):
            assert flags & os.O_CREAT and flags & os.O_EXCL and not (flags & os.O_TRUNC)
            assert args[0] == 0o666  # inherit the app project's normal umask/Windows ACL
        return original_open(path, flags, *args, **kwargs)
    with monkeypatch.context() as mounted:
        for name in ("unlink", "rename", "replace", "remove", "rmdir"):
            mounted.setattr(os, name, denied)
        mounted.setattr(os, "open", create_only)
        assert transfer.import_app(app, str(old), True, plan)["copied"] == 1
        assert transfer.import_app(app, str(old), True, plan)["matched"] == 1
    assert tree(old) == before
    assert (app / "src/page/app.py").read_bytes() == (old / "page/app.py").read_bytes()


def test_incomplete_file_is_preserved_and_retry_requires_a_fresh_destination(projects, monkeypatch):
    app, old = projects
    (old / "app.py").write_bytes(b"print('kept')")
    assert run(projects, "--apply") == (1, {"status": "error", "code": "import_plan_required"})
    plan = transfer.import_app(app, str(old))["planSha256"]
    def interrupted(stream, data):
        stream.write(data[:3])
        raise OSError("connector stopped")
    with monkeypatch.context() as failing:
        failing.setattr(transfer, "write_content", interrupted)
        result = transfer.import_app(app, str(old), True, plan)
    assert result["status"] == "partial" and result["copied"] == 0
    before = tree(app)
    assert (app / "src/app.py").read_bytes() == b"pri"
    assert transfer.import_app(app, str(old), True, plan)["status"] == "blocked"
    assert tree(app) == before


def test_boundaries_tool_fingerprints_and_hard_links(projects):
    app, old = projects
    for invalid in (app, app.parent, app / "src", app / "ui"):
        assert run(projects, "--apply", source=str(invalid))[0] != 0
    (old / "vas-hub.html").write_text("tool")
    assert run(projects)[1]["code"] == "import_tool_source"
    (old / "vas-hub.html").unlink()
    outside = old.parent / "outside.py"
    outside.write_text("outside")
    os.link(outside, old / "innocent.py")
    code, preview = run(projects)
    assert code == 0 and preview["files"] == [] and preview["skipped"]["linked"] == 1


def junction(path, target):
    if os.name == "nt":
        subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(path), str(target)], check=True, capture_output=True)
    else:
        path.symlink_to(target, target_is_directory=True)


def unlink_directory_link(path):
    if os.name == "nt":
        path.rmdir()
    else:
        path.unlink()


def test_linked_source_subtrees_are_skipped_and_destination_links_refused(projects):
    app, old = projects
    external = old.parent / "private dir"
    external.mkdir()
    (external / "private.py").write_text("outside")
    junction(old / "vendor-link", external)
    (old / "pages").mkdir()
    (old / "pages/menu.ts").write_text("export {};")
    try:
        preview = run(projects)[1]
        assert [item["path"] for item in preview["files"]] == ["pages/menu.ts"]
        junction(app / "src/pages", external)
        try:
            assert run(projects, *preview["addArguments"])[0] == 1
            assert not (external / "menu.ts").exists() and (external / "private.py").read_text() == "outside"
        finally:
            unlink_directory_link(app / "src/pages")
        assert run(projects, source=str(old / "vendor-link"))[0] == 1
    finally:
        unlink_directory_link(old / "vendor-link")


def test_two_competing_sources_cannot_mix(projects):
    app, a = projects
    b = a.parent.parent / "other" / "src"
    b.mkdir(parents=True)
    (a / "alpha.py").write_text("a")
    (b / "beta.py").write_text("b")
    with concurrent.futures.ThreadPoolExecutor() as pool:
        plans = [run((app, p))[1]["addArguments"] for p in (a, b)]
        outcomes = list(pool.map(lambda pair: run((app, pair[0]), *pair[1]), zip((a, b), plans)))
    assert sorted(code for code, _ in outcomes) == [0, 1]
    assert len(set(p.name for p in (app / "src").iterdir()) & {"alpha.py", "beta.py"}) == 1
