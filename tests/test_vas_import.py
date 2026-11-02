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
    assert preview["appVerification"]["status"] == "not-run"
    excluded = {row["path"]: row for row in preview["excluded"]}
    assert set(hidden) <= set(excluded) and excluded["uploads"]["kind"] == "directory"
    assert all(row["reason"] for row in excluded.values())
    assert all(body not in json.dumps(preview) for body in hidden.values())
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

@pytest.mark.parametrize("prefix", [("sessions", "id", "mnt"), ("data", "backup", "logs"), (".work", "mnt")])
def test_remote_mount_ancestors_do_not_change_the_selected_app_policy(projects, tmp_path, prefix):
    app, _ = projects
    source = tmp_path.joinpath(*prefix, "Desktop--Old", "src")
    source.mkdir(parents=True)
    (source / "app.py").write_bytes(b"print('menu')\n")
    (source / "server-config.json").write_bytes(b'{"setting":"local data"}')
    before = tree(app)
    code, plan = run((app, source))
    assert code == 0 and tree(app) == before
    assert [item["path"] for item in plan["files"]] == ["app.py"]
    assert [(row["path"], row["category"]) for row in plan["excluded"]] == [("server-config.json", "operational")]


@pytest.mark.parametrize("prefix", [".ssh", ".git", ".aws", ".vas", "credentials"])
def test_credential_and_tool_stores_cannot_be_selected_through_a_subdirectory(projects, tmp_path, prefix):
    app, _ = projects
    source = tmp_path / prefix / "src"
    source.mkdir(parents=True)
    (source / "menu.py").write_text("print(1)")
    assert run((app, source)) == (1, {"status": "error", "code": "import_private_source"})


def test_old_vas_app_source_allowed_but_engine_and_new_app_helper_rejected(projects):
    app, old = projects
    engine = old.parent / ".vas"
    (engine / "src").mkdir(parents=True)
    (engine / "project-layout.json").write_text('{"layout":"vas-project","version":1}')
    (engine / "Run-VAS-System.bat").write_text("helper")
    (engine / "src/vas-hub.html").write_text("helper")
    (old / "app.py").write_text("print(1)")
    assert [f["path"] for f in run((app, old))[1]["files"]] == ["app.py"]
    assert run((app, engine / "src"))[0] == 1
    assert run((app, app / "ui"))[0] == 1


def test_decisions_and_implementation_are_bound_to_the_reviewed_plan(projects, monkeypatch):
    app, old = projects
    (old / "server.py").write_text("print('menu')")
    (old / "review.js").write_text("const unknown = 5;")
    (old / "server-config.json").write_text('{"test":"ignored"}')
    classify = transfer.content_reason
    monkeypatch.setattr(transfer, "content_reason", lambda p, data: "review" if p == "review.js" else classify(p, data))
    plan = transfer.import_app(app, str(old))
    review = next(row for row in plan["excluded"] if row["path"] == "review.js")
    assert review["canInclude"] and plan["skipped"]["review"] == 1
    approved = transfer.import_app(app, str(old), include=["review.js"])
    assert approved["planSha256"] != plan["planSha256"]
    assert all(f["path"] != "server-config.json" for f in approved["files"])
    with pytest.raises(SessionError, match="import_include_not_reviewable"):
        transfer.import_app(app, str(old), include=["server-config.json"])
    with pytest.raises(SessionError, match="import_plan_changed"):
        transfer.import_app(app, str(old), True, plan["planSha256"], ["review.js"])
    (old / "extra.bin").write_text("a")
    with pytest.raises(SessionError, match="import_plan_changed"):
        transfer.import_app(app, str(old), True, approved["planSha256"], ["review.js"])
    current = transfer.import_app(app, str(old), include=["review.js"])
    result = transfer.import_app(app, str(old), True, current["planSha256"], ["review.js"])
    assert result["copied"] == 2 and result["appVerification"]["status"] == "not-run"
    assert not (app / "src/server-config.json").exists()


def test_preview_does_not_take_an_unsupported_mount_write_lock(projects, monkeypatch):
    app, old = projects
    (old / "menu.py").write_text("print(1)")
    def no_locks(*args, **kwargs):
        raise OSError(transfer.errno.EOPNOTSUPP, "unsupported by connector")
    monkeypatch.setattr(transfer, "_locked", no_locks)
    plan = transfer.import_app(app, str(old))
    assert plan["status"] == "planned"
    with pytest.raises(SessionError, match="import_filesystem_unavailable"):
        transfer.import_app(app, str(old), True, plan["planSha256"])
    assert not (app / "src/menu.py").exists()


def test_secret_in_a_filename_is_hidden_while_ordinary_exclusions_are_named(projects):
    app, old = projects
    secret = "live_sk_1234567890ABCDEFGHIJ"
    (old / f"notes-{secret}.txt").write_text("unused")
    (old / "server-config.json").write_text('{"test":"ignored"}')
    code, preview = run(projects)
    assert code == 0 and preview["excluded"]
    assert secret not in json.dumps(preview) and str(old) not in json.dumps(preview)
    assert any(item["path"] is None and not item["canInclude"] for item in preview["excluded"])
    assert any(item["path"] == "server-config.json" for item in preview["excluded"])

@pytest.mark.skipif(os.name != "nt", reason="Windows synthesizes mode bits for batch-file path stat")
def test_windows_imports_executable_suffix_with_consistent_open_handle_identity(projects):
    app, old = projects
    launcher = old / "start-app.bat"
    launcher.write_bytes(b"@echo off\r\npython server.py\r\n")
    (old / "server.py").write_bytes(b"print('menu')\n")
    code, plan = run(projects)
    assert code == 0 and {item["path"] for item in plan["files"]} == {"server.py", "start-app.bat"}
    code, result = run(projects, *plan["addArguments"])
    assert code == 0 and result["copied"] == 2
    assert (app / "src/start-app.bat").read_bytes() == launcher.read_bytes()

def test_cli_include_only_accepts_a_specific_reviewed_file_and_pins_its_contents(projects):
    app, old = projects
    (old / "sample").mkdir()
    test_literal = "A1bcD2efG3hiJ4klM5noP6qrS7tuV8wxY9zaBcDeFgHi"
    path = "sample/lookup.js"
    (old / path).write_text("const value = '" + test_literal + "';")
    (old / "server-config.json").write_text('{"setting":"disabled"}')
    initial = run(projects)[1]
    assert next(row for row in initial["excluded"] if row["path"] == path)["canInclude"] is True
    assert test_literal not in json.dumps(initial)
    code, approved = run(projects, "--include", path.replace("/", "\\"))
    assert code == 0 and approved["include"] == [path]
    assert approved["planSha256"] != initial["planSha256"]
    assert run(projects, "--include", "server-config.json") == (
        1, {"status": "error", "code": "import_include_not_reviewable"})
    # Authorizing a reviewed path never authorizes its newer, unreviewed contents.
    (old / path).write_text("const value = '" + test_literal[::-1] + "';")
    assert run(projects, "--include", path, *approved["addArguments"]) == (
        1, {"status": "error", "code": "import_plan_changed"})
    current = run(projects, "--include", path)[1]
    assert run(projects, "--include", path, *current["addArguments"])[1]["copied"] == 1
    assert (app / "src" / path).read_bytes() == (old / path).read_bytes()
    assert not (app / "src/server-config.json").exists()


@pytest.mark.parametrize("name", ["CON.py", "dir/aux.txt", "scripts/name?.py", "bad/../ok.js", "name\\s.js"])
def test_nonportable_names_cannot_be_explicitly_included(name):
    assert transfer.portable_path(name) is False
