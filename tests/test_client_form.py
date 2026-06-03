"""
tests/test_client_form.py
client-application.html + client-form.js + client-export.js 湲곕뒫 寃利?BeautifulSoup 湲곕컲 援ъ“ ?뚯뒪??+ ?듭떖 ?⑥닔 議댁옱 ?뺤씤
"""
import os
import re
try:
    import pytest
except ImportError:
    pytest = None


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HTML_FILE = os.path.join(ROOT, "src", "client-application.html")
FORM_JS = os.path.join(ROOT, "src", "client-form.js")
EXPORT_JS = os.path.join(ROOT, "src", "client-export.js")
I18N_JS = os.path.join(ROOT, "src", "client-i18n.js")
NAS_DIR = os.path.join(ROOT, "final", "nas-client-form")
NAS_INDEX = os.path.join(NAS_DIR, "index.html")


# ????????????????????????????????????????????
# ?뚯씪 議댁옱 寃利?# ????????????????????????????????????????????
def test_all_files_exist():
    """遺꾨━??JS ?뚯씪 3媛쒓? 紐⑤몢 議댁옱?댁빞 ?쒕떎."""
    for f in [HTML_FILE, FORM_JS, EXPORT_JS, I18N_JS]:
        assert os.path.exists(f), f"?뚯씪 ?놁쓬: {f}"


def test_html_line_count():
    """client-application.html?€ 500以??댄븯?ъ빞 ?쒕떎."""
    with open(HTML_FILE, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    assert len(lines) <= 500, f"줄수 초과: {len(lines)}줄 (제한: 500줄)"


# ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
# HTML 援ъ“ 寃€利?# ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
def test_html_references_js_files():
    """HTML???몃? JS ?뚯씪??紐⑤몢 李몄“?댁빞 ?쒕떎."""
    with open(HTML_FILE, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    for js in ["client-i18n.js", "client-form.js", "client-export.js"]:
        assert js in content, f"HTML?먯꽌 {js} 李몄“ ?놁쓬"


def test_html_has_clear_button():
    """珥덇린??踰꾪듉(clearForm)??HTML??議댁옱?댁빞 ?쒕떎."""
    with open(HTML_FILE, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    assert "clearForm()" in content, "珥덇린??踰꾪듉 clearForm() ?놁쓬"


def test_html_has_back_button():
    """DONE ?붾㈃ ?ㅻ줈媛€湲?goBackFromDone)媛€ HTML??議댁옱?댁빞 ?쒕떎."""
    with open(HTML_FILE, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    assert "goBackFromDone()" in content, "諛?踰꾪듉 goBackFromDone() ?놁쓬"


def test_external_form_does_not_link_back_to_hub():
    """External client form should not expose the internal hub link."""
    with open(HTML_FILE, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    assert 'href="vas-hub.html"' not in content, "external form exposes hub link"


def test_html_has_done_screen():
    """doneScreen ?붿냼媛€ HTML??議댁옱?댁빞 ?쒕떎."""
    with open(HTML_FILE, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    assert 'id="doneScreen"' in content, "doneScreen ?붿냼 ?놁쓬"


def test_no_inline_i18n():
    """HTML ?뚯씪 ?덉뿉 ?몃씪??i18n 媛앹껜媛€ ?놁뼱???쒕떎 (遺꾨━ ?꾨즺 寃€利?."""
    with open(HTML_FILE, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    # ?몃씪??i18n ?€?ъ쟾???놁뼱????    assert "heroMeta:" not in content, "?몃씪??i18n 媛앹껜媛€ HTML???⑥븘?덉쓬 (遺꾨━ 誘몄셿猷?"


# ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
# client-form.js ?⑥닔 寃€利?# ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
def test_form_js_has_key_functions():
    """client-form.js???듭떖 ?⑥닔媛€ 紐⑤몢 議댁옱?댁빞 ?쒕떎."""
    with open(FORM_JS, encoding="utf-8") as f:
        content = f.read()
    required = ["function changeStep", "function showDone", "function goBackFromDone",
                "function clearForm",
                "function updateUI", "function setLang"]
    for fn in required:
        assert fn in content, f"client-form.js??{fn} ?놁쓬"


def test_form_js_crash_guard():
    """loadForm??cur > total ?щ옒??諛⑹뼱 肄붾뱶媛€ ?덉뼱???쒕떎."""
    with open(FORM_JS, encoding="utf-8") as f:
        content = f.read()
    assert "cur > total" in content, "JS ?щ옒??諛⑹뼱 肄붾뱶 ?놁쓬"


def test_file_chip_uses_safe_dom_rendering():
    """Uploaded file names must not be interpolated through innerHTML."""
    with open(FORM_JS, encoding="utf-8") as f:
        content = f.read()
    assert "chip.innerHTML" not in content, "file chip rendering must avoid innerHTML"
    assert "document.createTextNode" in content, "file chip text node rendering missing"


# ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
# client-export.js ?⑥닔 寃€利?# ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
def test_export_js_has_key_functions():
    """client-export.js???듭떖 ?대낫?닿린 ?⑥닔媛€ 紐⑤몢 議댁옱?댁빞 ?쒕떎."""
    with open(EXPORT_JS, encoding="utf-8") as f:
        content = f.read()
    for fn in ["function exportJson"]:
        assert fn in content, f"client-export.js에 {fn} 없음"


# ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
# client-i18n.js 寃€利?# ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€
def test_i18n_js_has_both_languages():
    """i18n.js??ko/en ???몄뼱媛€ 紐⑤몢 ?덉뼱???쒕떎."""
    with open(I18N_JS, encoding="utf-8") as f:
        content = f.read()
    assert "ko:" in content, "?쒓뎅??ko) ?놁쓬"
    assert "en:" in content, "?곸뼱(en) ?놁쓬"


def test_i18n_js_has_clear_key():
    """i18n??btnClear ?ㅺ? ?덉뼱???쒕떎."""
    with open(I18N_JS, encoding="utf-8") as f:
        content = f.read()
    assert "btnClear" in content, "i18n.btnClear ???놁쓬"


def test_external_copy_avoids_false_submit_and_upload_claims():
    """External copy must match the local JSON-save-only flow."""
    with open(I18N_JS, encoding="utf-8") as f:
        content = f.read()
    assert 'btnSubmit: "Submit"' not in content
    assert "AI agent" not in content
    assert "AI 에이전트" not in content
    assert "File contents are not uploaded" in content
    assert "파일 내용은 업로드되지 않습니다" in content
    assert "March 2024" not in content
    assert "2024년 3월" not in content


def test_nas_client_form_package_files():
    """NAS package must contain only the standalone client form files."""
    expected = {
        "index.html",
        "README.md",
        "client-application-init.js",
        "client-form.js",
        "client-export.js",
        "client-i18n.js",
        "client-style.css",
        "client-components.css",
        "client-print.css",
    }
    actual = set(os.listdir(NAS_DIR))
    assert expected == actual, f"NAS package mismatch: {actual}"


def test_nas_client_form_index_references_local_assets():
    """NAS index.html should load only local Client Form assets."""
    with open(NAS_INDEX, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    for asset in [
        "client-style.css",
        "client-i18n.js",
        "client-form.js",
        "client-export.js",
        "client-application-init.js",
    ]:
        assert asset in content, f"NAS index missing {asset}"
    forbidden = ["vas-hub.html", "design-controller.html", "tests/", "handoff"]
    for item in forbidden:
        assert item not in content, f"NAS index contains forbidden reference: {item}"


def test_nas_client_form_readme_explains_no_upload():
    """NAS README should explain JSON handoff and no real file upload."""
    readme = os.path.join(NAS_DIR, "README.md")
    with open(readme, encoding="utf-8") as f:
        content = f.read()
    assert "index.html" in content
    assert "JSON 파일" in content
    assert "자동 업로드되지 않습니다" in content
    assert "서버 저장" in content


if __name__ == "__main__":
    if pytest is not None:
        pytest.main([__file__, "-v"])
    else:
        tests = [
            test_all_files_exist,
            test_html_line_count,
            test_html_references_js_files,
            test_html_has_clear_button,
            test_html_has_back_button,
            test_external_form_does_not_link_back_to_hub,
            test_html_has_done_screen,
            test_no_inline_i18n,
            test_form_js_has_key_functions,
            test_form_js_crash_guard,
            test_file_chip_uses_safe_dom_rendering,
            test_export_js_has_key_functions,
            test_i18n_js_has_both_languages,
            test_i18n_js_has_clear_key,
            test_external_copy_avoids_false_submit_and_upload_claims,
            test_nas_client_form_package_files,
            test_nas_client_form_index_references_local_assets,
            test_nas_client_form_readme_explains_no_upload
        ]
        passed = 0
        failed = 0
        print("=" * 60)
        print("  Running tests/test_client_form.py (Fallback Mode - No pytest)")
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

