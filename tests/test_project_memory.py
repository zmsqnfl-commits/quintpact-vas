"""Project memory lives in the project folder only, as text a person or any host can edit."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vas_memory


@pytest.fixture
def kit(tmp_path):
    app = tmp_path / "재고 앱"
    (app / "ui").mkdir(parents=True)
    (app / "src").mkdir()
    (app / "Run-VAS-System.bat").write_text("test")
    (app / "ui/vas-hub.html").write_text("helper")
    (app / "project-layout.json").write_text('{"layout":"vas-project","version":2}')
    return app, tmp_path / "private-must-stay-unused"


def cli(kit, *arguments):
    app, state = kit
    run = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/vas.py"), "--vas-root", str(app),
                          "--state-home", str(state), *arguments],
                         text=True, encoding="utf-8", capture_output=True, timeout=30)
    assert not run.stderr, run.stderr
    return run.returncode, json.loads(run.stdout)


def test_plan_and_done_write_one_place_and_start_reads_it_back(kit):
    app, state = kit
    code, planned = cli(kit, "plan", "--request", "재고 앱을 만들어줘", "--target", "새 앱, src",
                        "--criterion", "목록이 보인다 (화면에서 확인)", "--criterion", "추가가 된다 (직접 눌러 봄)",
                        "--decision", "표로 보여 준다 (사용자)", "--by", "claude")
    assert code == 0 and planned == {"status": "planned", "revision": 1, "path": "vas-state/now.md"}
    code, done = cli(kit, "done", "--summary", "목록을 표로 만들고 좁은 화면에서 확인", "--title", "목록 화면",
                     "--why", "한눈에 보이게", "--check", "390px 화면:통과", "--check", "키보드 조작:미실행",
                     "--file", "src/index.html", "--failed", "카드 배치는 글이 잘려서 버림",
                     "--criterion", "C1", "--tag", "화면", "--next-step", "추가 버튼 만들기", "--by", "claude")
    assert code == 0 and done["status"] == "recorded" and done["record"] == {
        "number": 1, "path": "vas-state/log/0001.md", "files": ["src/index.html"],
        "fingerprinted": 0}
    # One call is one write of the page, and a file that is not there is pointed out.
    assert done["unverified"] == ["키보드 조작"] and done["now"]["revision"] == 2
    assert done["missingFiles"] == ["src/index.html"]

    now = (app / "vas-state/now.md").read_text(encoding="utf-8")
    assert "- [x] C1 목록이 보인다" in now and "- [ ] C2 추가가 된다" in now
    assert "추가 버튼 만들기" in now and "390px 화면 → 통과" in now and "표로 보여 준다" in now
    record = (app / "vas-state/log/0001.md").read_text(encoding="utf-8")
    assert "카드 배치는 글이 잘려서 버림" in record and '"src/index.html"' in record
    index = (app / "vas-state/index.md").read_text(encoding="utf-8")
    assert "- 0001 | " in index and "목록 화면" in index and "#화면" in index
    # One place only: nothing was written outside the project folder.
    assert not state.exists()

    code, view = cli(kit, "start")
    memory = view["memory"]
    assert code == 0 and memory["status"] == "available" and memory["recordCount"] == 1
    assert memory["now"]["sections"]["요청"] == "재고 앱을 만들어줘" and "목록 화면" in memory["recent"][0]
    assert memory["indexPath"] == "vas-state/index.md"


def test_memory_follows_a_renamed_or_copied_folder(kit):
    app, state = kit
    cli(kit, "plan", "--request", "가격표를 고쳐줘")
    cli(kit, "done", "--summary", "가격 단위를 원으로 통일")
    moved = app.parent / "다른 이름"
    shutil.copytree(app, moved)
    code, view = cli((moved, state), "start")
    assert code == 0 and view["memory"]["now"]["sections"]["요청"] == "가격표를 고쳐줘"
    assert view["memory"]["recordCount"] == 1


def test_start_never_creates_memory_and_an_empty_project_says_so(kit):
    app, state = kit
    code, view = cli(kit, "start")
    assert code == 0 and view["memory"]["status"] == "empty"
    assert not (app / "vas-state").exists() and not state.exists()


def test_hand_written_and_damaged_files_are_read_as_far_as_possible(kit):
    app, _ = kit
    log = app / "vas-state/log"
    log.mkdir(parents=True)
    (app / "vas-state/now.md").write_text("## 요청\n메뉴판을 고쳐줘\n\n## 내가 만든 칸\n메모\n", encoding="utf-8")
    (log / "0003-손으로-쓴-기록.md").write_text(
        "---\ndate: 2026-11-01\ntitle: 손으로 쓴 기록\nsummary: 따옴표 없이 씀\ntags: [화면, 메뉴]\n"
        "files: [src/menu.html]\n---\n## 한 일\n메뉴 고침\n", encoding="utf-8")
    (log / "0004.md").write_bytes(b"\xff\xfe not text at all")
    (log / "notes.txt").write_text("ignored", encoding="utf-8")
    view = vas_memory.read_memory(app)
    assert view["now"]["revision"] == 0 and view["now"]["sections"]["내가 만든 칸"] == "메모"
    assert [item["number"] for item in view["records"]] == [3, 4]
    first = view["records"][0]
    assert first["title"] == "손으로 쓴 기록" and first["tags"] == ["화면", "메뉴"] and first["files"] == ["src/menu.html"]
    # A later tool write keeps the hand-made section and continues the numbering.
    vas_memory.update_now(app, {"다음 할 일": "가격 확인"}, "codex")
    assert "## 내가 만든 칸" in (app / "vas-state/now.md").read_text(encoding="utf-8")
    assert vas_memory.write_record(app, "가격 확인", "가격을 다시 확인", "codex", {})["number"] == 5


def test_a_busy_file_is_retried_and_a_stale_index_never_loses_the_record(kit, monkeypatch):
    app, _ = kit
    real, calls = os.replace, []
    def busy_twice(source, target):
        calls.append(target)
        if len(calls) <= 2:
            raise PermissionError(5, "busy")
        return real(source, target)
    monkeypatch.setattr(vas_memory.os, "replace", busy_twice)
    assert vas_memory.update_now(app, {"요청": "바쁜 파일"}, "host")["revision"] == 1 and len(calls) == 3
    def always_busy(source, target):
        raise PermissionError(5, "busy")
    monkeypatch.setattr(vas_memory.os, "replace", always_busy)
    monkeypatch.setattr(vas_memory.time, "sleep", lambda seconds: None)
    saved = vas_memory.write_record(app, "색인이 막힘", "기록은 남는다", "host", {})
    assert saved["indexStale"] is True and (app / saved["path"]).is_file()
    monkeypatch.setattr(vas_memory.os, "replace", real)
    assert [entry["title"] for entry in vas_memory.rebuild_index(app)] == ["색인이 막힘"]
    assert not list((app / "vas-state").glob(".vas-*.tmp"))


def test_secrets_and_machine_paths_never_reach_the_project_folder(kit):
    app, _ = kit
    secret = "sk-" + "a" * 40
    code, done = cli(kit, "done", "--summary", f"키 {secret} 를 C:\\Users\\me\\secret.txt 에서 읽음",
                     "--file", "src/app.js")
    assert code == 0
    stored = "".join(path.read_text(encoding="utf-8") for path in (app / "vas-state").rglob("*.md"))
    assert secret not in stored and "Users" not in stored and "[redacted]" in stored
    for outside in ("C:\\Users\\me\\a.txt", "/etc/passwd", "../other/a.txt"):
        code, error = cli(kit, "done", "--summary", "경로 시험", "--file", outside)
        assert code == 1 and error["code"] == "memory_file_path_invalid" and "상대 경로" in error["hint"]
    assert len(list((app / "vas-state/log").glob("*.md"))) == 1


def test_a_stale_plan_and_an_unknown_criterion_are_refused_with_a_next_step(kit):
    cli(kit, "plan", "--request", "첫 요청", "--criterion", "화면이 뜬다")
    code, error = cli(kit, "plan", "--request", "늦게 온 요청", "--expected-revision", "0")
    assert code == 1 and error["code"] == "memory_conflict" and "start" in error["hint"]
    code, error = cli(kit, "done", "--summary", "없는 조건", "--criterion", "C9")
    assert code == 1 and error["code"] == "memory_criterion_unknown"
    assert not list((kit[0] / "vas-state/log").glob("*.md"))
    code, error = cli(kit, "plan")
    assert code == 1 and error["code"] == "memory_invalid"


def test_hosts_finishing_together_each_keep_their_own_record(kit):
    app, _ = kit
    def finish(number):
        return vas_memory.write_record(app, f"작업 {number}", f"요약 {number}", "host", {"한 일": str(number)})
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(finish, range(24)))
    numbers = sorted(result["number"] for result in results)
    assert numbers == list(range(1, 25))
    entries = vas_memory.rebuild_index(app)
    assert len(entries) == 24 and {entry["title"] for entry in entries} == {f"작업 {n}" for n in range(24)}


def test_many_records_do_not_make_the_start_view_longer(kit):
    app, _ = kit
    for number in range(200):
        vas_memory.write_record(app, f"작업 {number}", "요약 " + "가" * 150, "host", {"한 일": "x"})
    code, view = cli(kit, "start")
    memory = view["memory"]
    assert code == 0 and memory["recordCount"] == 200 and len(memory["recent"]) == 5
    assert memory["recent"][-1].startswith("0200 ") and len(json.dumps(memory, ensure_ascii=False)) < 2500


def test_a_linked_memory_folder_is_refused(kit):
    app, _ = kit
    outside = app.parent / "outside"
    outside.mkdir()
    try:
        os.symlink(outside, app / "vas-state", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable here")
    with pytest.raises(vas_memory.ProjectMemoryError, match="memory_unsafe"):
        vas_memory.update_now(app, {"요청": "x"}, "host")
    assert not list(outside.iterdir())


def test_recall_finds_the_records_that_bear_on_a_request_and_start_continues_from_memory(kit):
    app, _ = kit
    cli(kit, "plan", "--request", "메뉴판 앱", "--next-step", "가격표 고치기")
    cli(kit, "done", "--summary", "가격표를 카드 세 장으로 바꿈", "--title", "가격표 화면", "--file", "src/price.html",
        "--tag", "화면", "--failed", "표 배치는 좁은 화면에서 잘려서 버림")
    cli(kit, "done", "--summary", "로그인 오류 문구를 고침", "--title", "로그인 문구", "--file", "src/login.js")
    cli(kit, "done", "--summary", "가격 단위를 원으로 통일", "--title", "단위 정리", "--file", "src/price.html")
    code, found = cli(kit, "recall", "가격표 화면 다시 고쳐줘")
    assert code == 0 and found["recordCount"] == 3
    assert [item["number"] for item in found["matches"]] == [1] and found["matches"][0]["matched"] == ["가격표", "화면"]
    assert "잘려서 버림" in found["matches"][0]["failed"]
    code, found = cli(kit, "recall", "price.html")
    assert [item["number"] for item in found["matches"]] == [3, 1]
    code, found = cli(kit, "recall", "결제 모듈")
    assert code == 0 and found["matches"] == [] and "index.md" in found["message"]
    code, error = cli(kit, "recall", "?")
    assert code == 1 and error["code"] == "memory_invalid"
    code, view = cli(kit, "start")
    assert view["nextAction"]["code"] == "continue" and "다음 할 일" in view["nextAction"]["message"]
    assert view["memory"]["now"]["sections"]["다음 할 일"] == "가격표 고치기"


def test_a_file_changed_after_its_record_is_reported_at_the_next_start(kit):
    app, _ = kit
    (app / "src/list.html").write_bytes(b"<ul>\n<li>one</li>\n</ul>\n")
    (app / "src/sum.js").write_text("total = 1")
    _, done = cli(kit, "done", "--summary", "목록과 합계", "--check", "목록 표시:통과", "--check", "합계:통과",
               "--file", "src/list.html", "--file", "src/sum.js", "--file", "src/gone.css", "--tag", "목록")
    assert done["record"]["fingerprinted"] == 2 and done["missingFiles"] == ["src/gone.css"]
    record = (app / "vas-state/log/0001.md").read_text(encoding="utf-8")
    assert 'fingerprints: {"src/list.html": "' in record and "gone.css\": \"" not in record
    assert str(app) not in record  # a fingerprint is a short hash, never a path on this machine

    # Nothing changed, and a different line ending is the same file.
    memory = cli(kit, "start")[1]["memory"]
    assert "changedSinceRecord" not in memory
    (app / "src/list.html").write_bytes(b"<ul>\r\n<li>one</li>\r\n</ul>\r\n")
    assert "changedSinceRecord" not in cli(kit, "start")[1]["memory"]

    (app / "src/sum.js").write_text("total = 2")
    memory = cli(kit, "start")[1]["memory"]
    assert memory["changedSinceRecord"] == ["src/sum.js (기록 0001 뒤 바뀜)"]
    assert "지금 결과로 쓰지 말고" in memory["message"] and "그 파일에 걸린 확인만" in memory["message"]
    (app / "src/list.html").unlink()
    assert "src/list.html (기록 0001 뒤 없어짐)" in cli(kit, "start")[1]["memory"]["changedSinceRecord"]

    # The newest record that names a file is the one that counts.
    cli(kit, "done", "--summary", "합계 수정", "--check", "합계:통과", "--file", "src/sum.js")
    assert cli(kit, "start")[1]["memory"]["changedSinceRecord"] == ["src/list.html (기록 0001 뒤 없어짐)"]


def test_a_hand_written_record_is_counted_as_not_compared_and_odd_files_get_no_fingerprint(kit):
    app, _ = kit
    log = app / "vas-state/log"
    log.mkdir(parents=True)
    (app / "src/a.txt").write_text("a")
    (log / "0001.md").write_text('---\ntitle: 손으로 쓴 기록\nfiles: [src/a.txt]\nfingerprints: 지어낸 값\n---\n\n## 한 일\n\n직접 씀\n',
                                 encoding="utf-8")
    memory = cli(kit, "start")[1]["memory"]
    assert memory["notCompared"] == 1 and "changedSinceRecord" not in memory
    check = vas_memory.changed_since_records(app)
    assert check == {"compared": 0, "changed": [], "notCompared": [{"file": "src/a.txt", "record": 1}]}

    (app / "src/big.bin").write_bytes(b"0" * (vas_memory.MAX_PRINT_FILE + 1))
    assert vas_memory._fingerprint(app, "src/big.bin") is None and vas_memory._fingerprint(app, "src") is None
    outside = app.parent / "outside.txt"
    outside.write_text("secret")
    try:
        os.symlink(outside, app / "src/link.txt")
    except OSError:
        return
    assert vas_memory._fingerprint(app, "src/link.txt") is None


def test_multi_ai_guide_keeps_one_writer_and_does_not_promise_vas_calls_other_ais():
    root = Path(__file__).resolve().parents[1]
    guide = (root / "docs/MULTI-AI.md").read_text(encoding="utf-8")
    assert "주 작업자 하나만" in guide and "그대로 쓰지 않습니다" in guide
    assert "VAS가 다른 AI를 대신 부르지는 않습니다" in guide
    assert "꼭 따라야 하는 절차는 아닙니다" in guide
    assert "(MULTI-AI.md)" in (root / "docs/index.md").read_text(encoding="utf-8")
