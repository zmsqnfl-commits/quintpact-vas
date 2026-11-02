"""File and credential rules for a user-selected application transfer."""
from __future__ import annotations

import json
import math
from pathlib import PurePosixPath
import re
import stat
import unicodedata

from vas_ai_contract import ASSIGNMENT, CREDENTIAL_VALUE, URI_USERINFO, credential_view, sensitive_key
from vas_project_import import EXCLUDED_DIRS, EXCLUDED_FILES

TEXT_LIMIT = 512 * 1024
ASSET_LIMIT = 2 * 1024 * 1024
CODE = {".py", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".css", ".scss", ".html",
        ".vue", ".svelte", ".go", ".rs", ".java", ".kt", ".cs", ".swift", ".c", ".cpp", ".h", ".hpp"}
SCRIPTS = {".bat", ".cmd", ".ps1", ".sh"}
DOCS = {".md", ".txt"}
ASSETS = {".woff", ".woff2", ".ttf", ".otf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico"}
MANIFESTS = {"package.json", "package-lock.json", "pyproject.toml", "requirements.txt", "cargo.toml",
             "cargo.lock", "go.mod", "go.sum", "dockerfile", "compose.yaml", "compose.yml",
             "docker-compose.yml", "docker-compose.yaml"}
GENERATED = EXCLUDED_DIRS | {"vendor", "generated", ".git", ".hg", ".svn"}
OPERATIONAL = {"logs", "log", "data", "database", "storage", "uploads", "backup", "backups", "fixtures",
               "records", "sessions", "userdata", "vas-state"}
KEY_DIRS = {".ssh", ".aws", ".azure", ".kube", ".gnupg", ".docker", "keys", "secrets", "credentials"}
KEY_SUFFIXES = {".key", ".pem", ".pfx", ".p12", ".jks", ".kdbx"}
KEY_NAME = re.compile(r"(?:^|[-_. ])(?:private[-_]?key|secret(?:s|[-_]?key)?|api[-_]?key|"
                      r"(?:access|refresh)[-_]?(?:key|token)|token|credential[s]?|passw(?:or)?d|"
                      r"id_(?:rsa|dsa|ecdsa|ed25519)|service[-_]account)(?:$|[-_. ])", re.I)
PREFIXED_TOKEN = re.compile(r"\b(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|AIza|xox[baprs]-)[a-z0-9_-]{12,}", re.I)
CONTACT = re.compile(r"[A-Z0-9._%+-]{1,64}@[A-Z0-9.-]{1,190}\.[A-Z]{2,24}\b|"
                     r"(?:\+?82[- ]?0?1[016789]|01[016789])[- ]?\d{3,4}[- ]?\d{4}\b", re.I)
TOSS_TOKEN = re.compile(r"\b(?:test|live)_g?[cs]k_[A-Za-z0-9_-]{8,}", re.I)
PAYMENT_TOKEN = re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{8,}", re.I)
LITERAL = r"""(?:"((?:\\.|[^"\\\r\n])*)"|'((?:\\.|[^'\\\r\n])*)'|\x60((?:\\.|[^\x60\\\r\n])*)\x60)"""
QUOTED = re.compile(r"(?:[rubf]{0,2})?(?:" + r'"{3}([\s\S]*?)"{3}' +
                    r"|'{3}([\s\S]*?)'{3}|" + LITERAL + r")", re.I)
SETTER = re.compile(r"\bset(?:Password|ApiKey|AccessToken|SecretKey)\s*\(\s*" + LITERAL, re.I)
VALUE_FALLBACK = re.compile(r"[\w.$?]+(?:\(\))?\s*(?:\|\||\?\?|\bor\b|-or)\s*" + LITERAL)

ASSIGN = re.compile(r"""(?<![\w-])['"]?([A-Za-z_][\w-]{0,100})['"]?\s*(?:\])?\s*(?::(?!:)|=(?!=|>))\s*""")
LOOKUP_DEFAULT = re.compile(r"""(?:\bgetenv|\.\s*get)\s*\(\s*['"]([\w-]+)['"]\s*,\s*""" + LITERAL)
ENV_FALLBACK = re.compile(r"""(?:process\.env\.|\$env:)([\w-]+)\s*(?:\|\||\?\?|-or)\s*""" + LITERAL, re.I)
SHELL_FALLBACK = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*):?[-=]([^}\r\n]+)\}")
PLACEHOLDER = re.compile(r"""(?ix)(?:\$\{[\w.]+\}|\$[\w.]+|%[A-Z_][A-Z0-9_]*%|
    <[\w .-]+>|(?:your|example|sample|placeholder|replace|insert|change)[-_ ](?:[\w -]{1,80})|
    change[-_]?me|placeholder|redacted|\[redacted\]|[x*]{3,}|\.{3}|여기에\s+[\w ()-]{1,65})""")
RANDOM_LITERAL = re.compile(r"""(?:^|["'\x60])([a-zA-Z0-9+/=_-]{32,128})(?=["'\x60]|$)""")
SVG_START = re.compile(r"^(?:<\?xml[^?]*\?>\s*)?(?:<!--[\s\S]*?-->\s*)*<svg\b", re.I)


def file_limit(relative):
    return ASSET_LIMIT if PurePosixPath(relative).suffix.casefold() in ASSETS else TEXT_LIMIT


def source_name_blocked(name):
    name = unicodedata.normalize("NFKC", name).casefold()
    return (name.startswith(".") or name in GENERATED | OPERATIONAL | KEY_DIRS
            or KEY_NAME.search(name) is not None)


def name_reason(relative, info):
    """Check the selected entry before opening it, never the names of mount ancestors."""
    name = unicodedata.normalize("NFKC", PurePosixPath(relative).name).casefold()
    suffix = PurePosixPath(name).suffix
    if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400 or
            (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)):
        return "linked"
    if name.startswith(".env") or name in KEY_DIRS or name in {".netrc", ".npmrc", ".pypirc", ".git-credentials"} or suffix in KEY_SUFFIXES:
        return "credentialFile"
    if name in GENERATED or name in EXCLUDED_FILES or name.startswith(".") or suffix in {".pyc", ".pyo"}:
        return "generated"
    if name in OPERATIONAL:
        return "operational"
    if stat.S_ISDIR(info.st_mode):
        return "credentialFile" if KEY_NAME.search(name) else None
    if not stat.S_ISREG(info.st_mode):
        return "unsupported"
    example = name.endswith(".example.json")
    if name not in MANIFESTS and not example:
        if "settings" in name or suffix in {".db", ".sqlite", ".sqlite3", ".json", ".log"}:
            return "operational"
        if KEY_NAME.search(name) and suffix not in CODE | SCRIPTS:
            return "credentialFile"
    if not example and name not in MANIFESTS and suffix not in CODE | SCRIPTS | DOCS | ASSETS:
        return "unsupported"
    return "size" if info.st_size > file_limit(relative) else None


def _sensitive(name):
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).casefold()
    if re.search(r"(?:^|_)(?:require|enable|disable|use|check|has)_(?:admin_)?password$", snake):
        return False
    return sensitive_key(snake) or snake.endswith(("secret_key", "secretkey", "accesskey", "apikey"))


def _placeholder(value):
    return not value.strip() or PLACEHOLDER.fullmatch(value.strip()) is not None


def _strong(source):
    if "PRIVATE KEY-----" in source or PREFIXED_TOKEN.search(source) or TOSS_TOKEN.search(source) or PAYMENT_TOKEN.search(source):
        return True
    if "://" in source and "@" in source and URI_USERINFO.search(source):
        return True
    # A database URL with no embedded user/password is an endpoint reference.
    return any("://" not in match.group() for match in CREDENTIAL_VALUE.finditer(source))


def safe_display_path(relative):
    """Return a relative diagnostic name, withholding sensitive/unsafe filename text."""
    if not isinstance(relative, str) or len(relative) > 300:
        return None
    normalized = credential_view(relative)
    for name in (relative, normalized):
        if (name.startswith(("/", "\\")) or "\\" in name or ":" in name
                or any(part in ("", ".", "..") for part in name.split("/"))
                or any(unicodedata.category(ch).startswith("C") for ch in name)):
            return None
        if _strong(name) or CONTACT.search(name) or ASSIGNMENT.search(name):
            return None
        for token in re.findall(r"(?<![A-Za-z0-9])[A-Za-z0-9_-]{32,}(?![A-Za-z0-9])", name):
            if any(ch.isdigit() for ch in token) and _entropy(token) >= 4.5:
                return None
    return relative


def _decoded(data, suffix):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeError:
        if suffix in {".bat", ".cmd", ".ps1", ".md", ".txt"}:
            return data.decode("cp949")
        raise


def _binary_header(suffix, data):
    patterns = {".woff": b"wOFF", ".woff2": b"wOF2", ".ttf": (b"\0\1\0\0", b"true"),
                ".otf": b"OTTO", ".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8\xff",
                ".jpeg": b"\xff\xd8\xff", ".gif": (b"GIF87a", b"GIF89a"), ".ico": b"\0\0\1\0"}
    if suffix == ".webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return data.startswith(patterns[suffix])


def _value(match, start=1):
    return next((val for val in match.groups()[start:] if val is not None), "")


def _explicit_literals(text):
    # Lookup names are references. A nonempty embedded fallback is still a credential.
    for pattern in (LOOKUP_DEFAULT, ENV_FALLBACK):
        for match in pattern.finditer(text):
            if _sensitive(match[1]) and not _placeholder(_value(match)):
                return True
    for match in SHELL_FALLBACK.finditer(text):
        if _sensitive(match[1]) and not _placeholder(match[2]):
            return True
    for match in SETTER.finditer(text):
        if not _placeholder(_value(match, 0)):
            return True
    for match in ASSIGN.finditer(text):
        if not _sensitive(match[1]):
            continue
        literal = QUOTED.match(text, match.end())
        if literal:
            value = _value(literal, 0)
            if match[1].lower() == "authorization" and re.fullmatch(
                    r"(?:Bearer|Basic)\s*(?:\$?\{[\w.$]+\})?", value, re.I):
                continue
            if not _placeholder(value):
                return True
        fallback = VALUE_FALLBACK.match(text, match.end())
        if fallback and not _placeholder(_value(fallback, 0)):
            return True
    return False


def _template(value, depth=0):
    if depth > 25:
        return "unsupportedContent"
    if isinstance(value, dict):
        for name, item in value.items():
            if _sensitive(name) and item is not None and not isinstance(item, bool):
                if not isinstance(item, str) or not _placeholder(item):
                    return "credential"
            reason = _template(item, depth + 1)
            if reason:
                return reason
    elif isinstance(value, list):
        for item in value:
            reason = _template(item, depth + 1)
            if reason:
                return reason
    return None


def _entropy(value):
    return -sum((n / len(value)) * math.log2(n / len(value)) for n in
                (value.count(ch) for ch in set(value)))


def _ambiguous(text, suffix):
    if ("@" in text or re.search(r"\b(?:01[016789]|\+82)", text)) and CONTACT.search(text):
        return True
    for match in RANDOM_LITERAL.finditer(text):
        value = match[1]
        if (not value.lower().startswith(("sha256-", "sha384-", "sha512-"))
                and any(ch.isalpha() for ch in value) and any(ch.isdigit() for ch in value)
                and _entropy(value) >= 4.5):
            return True
    # Unquoted password settings in scripts/config may be input values. Source-code
    # identifiers or calls (including JS form reads) are ordinary references.
    if suffix in SCRIPTS | {".yaml", ".yml", ".toml", ".txt", ".md"}:
        for match in ASSIGN.finditer(text):
            if _sensitive(match[1]):
                word = re.match(r"[\w.-]+", text[match.end():])
                if word and not _placeholder(word[0]):
                    return True
    return False


def content_reason(relative, data):
    suffix = PurePosixPath(relative).suffix.casefold()
    if suffix in ASSETS - {".svg"}:
        if not _binary_header(suffix, data):
            return "unsupportedContent"
        # Scan human-readable metadata without decoding megabytes of compressed pixels.
        for match in re.finditer(rb"[\x20-\x7e]{8,}", data):
            chunk = match[0].decode("ascii")
            if _strong(chunk) or _explicit_literals(chunk):
                return "credential"
        return None
    try:
        source = _decoded(data, suffix)
    except UnicodeError:
        return "unsupportedContent"
    if any(ord(ch) < 32 and ch not in "\r\n\t\f" for ch in source):
        return "unsupportedContent"
    if suffix == ".svg" and SVG_START.match(source.lstrip()) is None:
        return "unsupportedContent"
    if PurePosixPath(relative).name.casefold().endswith(".example.json"):
        try:
            reason = _template(json.loads(source))
        except (ValueError, RecursionError):
            return "unsupportedContent"
        if reason:
            return reason
    view = credential_view(source)
    if _strong(view) or _explicit_literals(view):
        return "credential"
    return "review" if _ambiguous(view, suffix) else None
