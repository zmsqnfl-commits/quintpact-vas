"""Import distinguishes use of secrets from carrying their values into a new app."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vas_import_policy import (ASSET_LIMIT, TEXT_LIMIT, content_reason, file_limit, name_reason,
                               safe_display_path, source_name_blocked)


@pytest.mark.parametrize("source", [
    'password = os.environ.get("MENUBOARD_ADMIN_PASSWORD", "")',
    'password = os.getenv("MENUBOARD_ADMIN_PASSWORD") or config.get("adminPassword", "")',
    '"""Set MENUBOARD_ADMIN_PASSWORD to use remote administration."""',
    'if (getPassword()) { setPassword(""); }',
    'const form = {secretKey: field.value.trim(), password: getPassword()};',
    'headers = {"Authorization": "Bearer " + token}',
    'read_from = obj["accessKey"]; export const apiKey = process.env.TOSS_KEY;',
    'const settings = {"password": "${MENUBOARD_ADMIN_PASSWORD}"};',
    'config = {"adminPassword": "..."}',
])
def test_safe_names_references_and_empty_values_do_not_block_source(source):
    assert content_reason("app.js", source.encode()) is None


@pytest.mark.parametrize("name, source", [
    ("app.py", 'password = "a-small-real-value"'),
    ("app.py", "password = '''a\\nmultiline value'''"),
    ("app.py", 'password = r"fixed-value"'),
    ("app.js", 'const x = {secretKey: "fixed-value"};'),
    ("app.ts", r'const x = {password\u003a "literal-value"};'),
    ("app.py", 'secret = os.getenv("TOSS_SECRET_KEY", "nonempty fallback")'),
    ("app.js", 'const value = process.env.TOSS_SECRET_KEY || "fallback";'),
    ("app.js", 'let password = config.password ?? "hardcoded";'),
    ("app.sh", 'val="${ADMIN_PASSWORD:-nonempty-fallback}"'),
    ("app.js", 'setPassword("literal-value");'),
    ("app.py", 'value = "live_sk_" + "ABF9186df12345678"'),
    ("app.py", 'endpoint = "https://someuser:sample_secret@localhost/example"'),
    ("app.md", 'Authorization: Bearer abcDEF0123456789'),
    ("app.py", '# -----BEGIN PRIVATE KEY-----\nfixture\n-----END PRIVATE KEY-----'),
])
def test_literal_credentials_are_hard_exclusions(name, source):
    assert content_reason(name, source.encode()) == "credential"


@pytest.mark.parametrize("value", ["", "${TOSS_SECRET_KEY}", "<your key>", "YOUR_API_KEY", "여기에 가맹점 Access Key 입력"])
def test_template_placeholders_are_allowed_and_real_values_excluded(value):
    import json
    data = {"nested": [{"secretKey": value}], "port": 8080}
    assert content_reason("toss-config.example.json", json.dumps(data).encode()) is None
    data["nested"][0]["secretKey"] = "actual operational value"
    assert content_reason("toss-config.example.json", json.dumps(data).encode()) == "credential"


def test_ambiguous_literals_require_review_while_public_lockfile_integrities_are_allowed():
    encoded = "bG9uZ1JhbmRvbUV4YW1wbGVDcmVkZW50aWFsYmFzZTY0"
    assert content_reason("demo.js", f'const unknown = "{encoded}";'.encode()) == "review"
    assert content_reason("package-lock.json", f'{{"integrity":"sha512-{encoded}"}}'.encode()) is None
    assert content_reason("deploy.sh", b'export ADMIN_PASSWORD=unverified') == "review"
    assert content_reason("README.md", b'Contact admin@example.invalid') == "review"


@pytest.mark.parametrize("path,reason", [
    ("board-settings.js", "operational"), ("toss-config.json", "operational"),
    ("server-config.json", "operational"), ("sessions", "operational"),
    (".env.local", "credentialFile"), ("ops-admin.key", "credentialFile"),
    ("private-key.txt", "credentialFile"), ("output.pyc", "generated"),
    (".gitkeep", "generated"), ("vendor", "generated"),
    ("start.cmd", None), ("deploy.ps1", None), ("app.sh", None), ("README.md", None),
    ("font-license.txt", None), ("toss-config.example.json", None), ("Dockerfile", None),
])
def test_names_are_classified_before_opening_data(tmp_path, path, reason):
    target = tmp_path / path
    if path in {"sessions", "vendor"}:
        target.mkdir()
    else:
        target.touch()
    assert name_reason(path, target.stat()) == reason


@pytest.mark.parametrize("path,data", [
    ("font.woff", b"wOFF\x00sample"), ("font.woff2", b"wOF2\x00sample"),
    ("font.ttf", b"\x00\x01\x00\x00sample"), ("font.otf", b"OTTO\x00sample"),
    ("icon.png", b"\x89PNG\r\n\x1a\nsample"), ("icon.JPG", b"\xff\xd8\xffsample"),
    ("icon.jpeg", b"\xff\xd8\xffsample"), ("image.webp", b"RIFF\x00\x00\x00\x00WEBPsample"),
    ("icon.gif", b"GIF89asample"), ("icon.ico", b"\x00\x00\x01\x00sample"),
    ("icon.svg", b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'),
])
def test_supported_asset_signatures_and_specific_cap(path, data):
    assert file_limit(path) == ASSET_LIMIT and TEXT_LIMIT < ASSET_LIMIT
    assert content_reason(path, data) is None
    assert content_reason(path, b"renamed unrelated payload") == "unsupportedContent"


def test_asset_metadata_and_windows_text_still_checked():
    assert content_reason("large.png", b'\x89PNG\r\n\x1a\nnote password="fixed-value"') == "credential"
    assert content_reason("start.bat", "@echo 서버 시작\r\n".encode("cp949")) is None
    assert content_reason("start.ps1", 'Write-Output "Ready"'.encode("utf-16")) is None
    assert content_reason("start.ps1", '$apiKey = "fixed-value"'.encode("utf-16")) == "credential"
    assert content_reason("toss-config.example.json", b"{bad json") == "unsupportedContent"


def test_disposition_names_never_echo_secret_literals_or_absolute_paths():
    for n in (".env", "board-settings.js", "toss-config.json", ".gitkeep", "docs/실행 방법.md"):
        assert safe_display_path(n) == n
    for n in ("file/../app.js", r"C:\Users\member\app.js", "tmp/a\nb.js",
              "ghp_abcdefghijklmnop.js", "live_sk_123456789012.js", "admin@example.invalid.md"):
        assert safe_display_path(n) is None


def test_boundary_only_uses_selected_basename():
    assert not source_name_blocked("src")
    assert source_name_blocked(".ssh") and source_name_blocked("sessions")
