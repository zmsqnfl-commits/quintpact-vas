"""Reference-only starter prompt context; no session or project writes."""
from pathlib import Path
import hashlib

from vas_ai_contract import canonical


def project_snapshot(manager, target_path, available=True):
    if Path(target_path) != manager.project_root:
        return None
    if not available:
        raise ValueError("project_prompt_unavailable")
    from vas_project_prompt import read_project_prompt
    return read_project_prompt(manager.root)


def snapshot_hash(snapshot):
    # No prompt file retains the previous handoff/record contract.
    if snapshot is None or snapshot == {"revision": 0, "prompt": ""}:
        return None
    return hashlib.sha256(canonical(snapshot)).hexdigest()


def current_hash(manager, target_path, available=True):
    try:
        return snapshot_hash(project_snapshot(manager, target_path, available))
    except (OSError, ValueError):
        return "unavailable"


def stale_reason(recorded, current):
    if current == "unavailable":
        return "project-prompt-unavailable"
    return "project-prompt-changed" if recorded != current else None
