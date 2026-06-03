import os
import glob

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def test_html_files_exist():
    expected_files = [
        os.path.join("src", "vas-hub.html"),
        os.path.join("src", "design-controller.html"),
    ]
    for file in expected_files:
        path = os.path.join(ROOT_DIR, file)
        assert os.path.exists(path), f"Missing essential HTML file: {file}"
        assert os.path.getsize(path) > 0, f"HTML file is empty: {file}"

def test_js_files_exist():
    expected_files = [
        os.path.join("src", "client-form.js"),
    ]
    for file in expected_files:
        path = os.path.join(ROOT_DIR, file)
        assert os.path.exists(path), f"Missing essential JS file: {file}"
        assert os.path.getsize(path) > 0, f"JS file is empty: {file}"

def test_line_limits():
    """Non-data 파일이 500줄 이하인지 확인"""
    html_files = (
        glob.glob(os.path.join(ROOT_DIR, "*.html"))
        + glob.glob(os.path.join(ROOT_DIR, "src", "*.html"))
        + glob.glob(os.path.join(ROOT_DIR, "final", "src", "*.html"))
    )
    for file_path in html_files:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = len(f.readlines())
            assert lines <= 500, f"File {os.path.basename(file_path)} exceeds 500 lines ({lines} lines)"

    js_files = glob.glob(os.path.join(ROOT_DIR, "*.js")) + glob.glob(os.path.join(ROOT_DIR, "src", "*.js"))
    for file_path in js_files:
        if os.path.basename(file_path).endswith('-data.js'):
            continue  # 데이터 전용 파일 제외
        with open(file_path, "r", encoding="utf-8") as f:
            lines = len(f.readlines())
            assert lines <= 500, f"File {os.path.basename(file_path)} exceeds 500 lines ({lines} lines)"

def test_html_structure():
    """HTML 파일이 정상적으로 닫혀 있는지 확인 (절단 버그 방지)"""
    html_files = glob.glob(os.path.join(ROOT_DIR, "*.html")) + glob.glob(os.path.join(ROOT_DIR, "src", "*.html"))
    for file_path in html_files:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        name = os.path.basename(file_path)
        assert '</body>' in content, f"{name}: </body> 태그 없음 — 파일이 절단되었을 수 있음"
        assert '</html>' in content, f"{name}: </html> 태그 없음 — 파일이 절단되었을 수 있음"

def test_md_files_nonempty():
    """필수 MD 파일이 존재하고 비어 있지 않은지 확인"""
    required_md = [
        os.path.join("docs", "HANDOFF.md"),
        os.path.join(".agents", "CONTEXT.md"),
        os.path.join("docs", "index.md"),
        os.path.join("docs", "log.md")
    ]
    for file in required_md:
        path = os.path.join(ROOT_DIR, file)
        assert os.path.exists(path), f"Missing required MD file: {file}"
        assert os.path.getsize(path) > 0, f"Required MD file is empty: {file}"

if __name__ == "__main__":
    tests = [
        test_html_files_exist,
        test_js_files_exist,
        test_line_limits,
        test_html_structure,
        test_md_files_nonempty
    ]
    passed = 0
    failed = 0
    print("=" * 60)
    print("  Running tests/test_html_syntax.py directly")
    print("=" * 60)
    for t in tests:
        try:
            t()
            print(f"  [PASS] {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {t.__name__}: {e}")
            failed += 1
    print("-" * 60)
    print(f"  TOTAL: {passed+failed} | PASS: {passed} | FAIL: {failed}")
    import sys
    sys.exit(0 if failed == 0 else 1)
