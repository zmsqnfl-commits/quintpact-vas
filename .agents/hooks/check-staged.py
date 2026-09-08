"""Inspect Git's staged blob bytes; portable alongside either pre-commit hook."""
import json
import os
import re
import subprocess
import sys

SENSITIVE = re.compile(rb"(password|secret|api_key|private_key)\s*=", re.I)
OID = re.compile(rb"[a-f0-9]{40}(?:[a-f0-9]{24})?\Z")


def git(*args):
    result = subprocess.run(["git", *args], capture_output=True, check=True)
    return result.stdout


def check():
    records = git("diff", "--cached", "--raw", "-z", "--no-abbrev",
                  "--no-renames", "--no-ext-diff", "--no-textconv", "--").split(b"\0")
    if records.pop() != b"" or len(records) % 2:
        raise ValueError("Invalid staged diff")
    found = []
    for header, path in zip(records[::2], records[1::2]):
        fields = header.split()
        if len(fields) != 5 or not fields[0].startswith(b":"):
            raise ValueError("Invalid staged entry")
        _, mode, _, oid, status = fields
        if status == b"D":
            continue
        if status not in {b"A", b"M", b"T"} or not OID.fullmatch(oid):
            raise ValueError("Unmerged or invalid staged entry")
        if mode == b"160000":  # Submodule commit, not a file blob.
            continue
        if mode not in {b"100644", b"100755", b"120000"}:
            raise ValueError("Unsupported staged file mode")
        content = git("cat-file", "blob", oid.decode("ascii"))
        if content.startswith((b"\xff\xfe", b"\xfe\xff")):
            content = content.decode("utf-16").encode("utf-8")
        if SENSITIVE.search(content):
            found.append(os.fsdecode(path))
    if found:
        print("[WARNING] Sensitive assignments in staged files:")
        for path in found:
            print("  " + json.dumps(path, ensure_ascii=True))
        if os.environ.get("SKIP_SENSITIVE") != "1":
            print("Review the staged content; explicit override: SKIP_SENSITIVE=1")
            return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(check())
    except (OSError, ValueError, UnicodeError, subprocess.CalledProcessError):
        print("[BLOCKED] Could not inspect staged content.", file=sys.stderr)
        sys.exit(2)
