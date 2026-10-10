"""Persist task settings, not execution authority or evidence of completion."""
from __future__ import annotations

import json
import math
import os
import re
import stat
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from vas_ai_contract import sanitize
from vas_task_policy import apply_task, safe_text
from vas_session_store import Store

MAX_INPUT = 64 * 1024
SESSION_ID = re.compile(r"^[a-f0-9]{32}$")
LOCAL_POSIX = re.compile(r'''(?<![\w:/])/(?:opt|tmp|srv|private|media|run|root|proc|data)/[^\s'"`]+''')


class SessionError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code="session_invalid"):
    if not condition:
        raise SessionError(code)


def fields(value, allowed, required=()):
    require(isinstance(value, dict))
    require(not set(value) - set(allowed) and set(required) <= set(value))


def normalize_settings(raw):
    fields(raw, {"project", "task", "design", "questions", "nextStep"}, {"project", "task"})
    project = raw["project"]
    fields(project, {"name", "sourceType"}, {"name", "sourceType"})
    require(project["sourceType"] in ("new", "existing"))
    changes = []
    name = safe_text(project["name"], 120, "project.name", changes)
    require(bool(name))
    task = raw["task"]
    fields(task, {"request", "constraints", "designScope", "completionCriteria"})
    if "designScope" in task:
        fields(task["designScope"], {"mode", "scope"}, {"mode"})
    require(isinstance(task.get("completionCriteria", []), list))
    for criterion in task.get("completionCriteria", []):
        fields(criterion, {"id", "description", "method", "required"}, {"description", "method", "required"})
    document = {"project": {"sourceType": project["sourceType"]}, "context": {}}
    apply_task(document, task, changes)
    normalized_task = document["task"]
    # Derived prompt guidance is rebuilt later, never appended again on each save.
    normalized_task = {key: normalized_task[key] for key in
                       ("request", "constraints", "designScope", "completionCriteria")}
    normalized_task["constraints"] = normalized_task["constraints"][:-1]
    design = raw.get("design", {})
    studio_keys = {"preset", "basePreset", "tasteProfileMode"}
    fields(design, {"profileId", "direction", "tokens"} | studio_keys)
    studio = {}
    for key in sorted(studio_keys & set(design)):
        value = design[key]
        pattern = r"[A-Za-z0-9-]{1,48}" if key == "tasteProfileMode" else r"[a-z0-9-]{1,48}"
        require(isinstance(value, str) and re.fullmatch(pattern, value), "design_metadata_invalid")
        studio[key] = value
    profile = safe_text(design.get("profileId", ""), 100, "design.profileId", changes)
    direction = safe_text(design.get("direction", ""), 12000, "design.direction", changes)
    tokens = design.get("tokens", {})
    require(isinstance(tokens, dict))

    def check_tokens(value, depth=0):
        require(depth <= 4)
        if isinstance(value, dict):
            require(len(value) <= 64)
            for key, child in value.items():
                require(isinstance(key, str) and 0 < len(key) <= 80)
                require(key not in {"__proto__", "prototype", "constructor"})
                check_tokens(child, depth + 1)
        elif isinstance(value, str):
            require(len(value) <= 1000)
        else:
            require(value is None or type(value) in (bool, int, float))
            if type(value) is float:
                require(math.isfinite(value))
    check_tokens(tokens)
    cleaned_tokens = sanitize(tokens)
    if cleaned_tokens != tokens:
        changes.append("design.tokens")
    design = dict({"profileId": profile, "direction": direction, "tokens": cleaned_tokens}, **studio)
    if normalized_task["designScope"]["mode"] == "preserve":
        if profile or direction or tokens or studio:
            changes.append("design.preserve")
        design = {"profileId": "", "direction": "", "tokens": {}}
    questions = raw.get("questions", [])
    require(isinstance(questions, list) and len(questions) <= 10)
    settings = {"project": {"name": name, "sourceType": project["sourceType"]},
                "task": normalized_task, "design": design,
                "questions": [safe_text(item, 500, "questions", changes) for item in questions],
                "nextStep": safe_text(raw.get("nextStep", ""), 1000, "nextStep", changes)}
    def local_paths(value):
        if isinstance(value, str):
            return LOCAL_POSIX.sub("[absolute-path]", value)
        if isinstance(value, list):
            return [local_paths(item) for item in value]
        if isinstance(value, dict):
            return {local_paths(key): local_paths(item) for key, item in value.items()}
        return value
    safe = local_paths(settings)
    if safe != settings:
        changes.append("local-path")
    settings = safe
    require(len(json.dumps(settings, ensure_ascii=False).encode("utf-8")) <= MAX_INPUT,
            "session_input_too_large")
    return settings, list(dict.fromkeys(changes))


def safe_directory(value):
    path = Path(os.path.abspath(value))
    for current in (path, *path.parents):
        try:
            info = current.lstat()
        except FileNotFoundError:
            raise SessionError("target_missing") from None
        require(not stat.S_ISLNK(info.st_mode) and not
                getattr(info, "st_file_attributes", 0) & 0x400, "target_unsafe")
    require(path.is_dir(), "target_unsafe")
    return path.resolve(strict=True)


def identity(path):
    info = path.stat()
    # Directory identity detects common removal/replacement, not malicious tampering.
    return [info.st_dev, info.st_ino]


def valid_document(document):
    fields(document, {"format", "schemaVersion", "sessionId", "revision", "updatedAt", "settings"},
           {"format", "schemaVersion", "sessionId", "revision", "updatedAt", "settings"})
    require(document["format"] == "vas-chat-session" and type(document["schemaVersion"]) is int
            and document["schemaVersion"] == 1)
    require(isinstance(document["sessionId"], str) and SESSION_ID.fullmatch(document["sessionId"]))
    require(type(document["revision"]) is int and document["revision"] >= 1)
    require(isinstance(document["updatedAt"], str) and len(document["updatedAt"]) < 40)
    require(datetime.fromisoformat(document["updatedAt"]).tzinfo is not None)
    normalized, changes = normalize_settings(document["settings"])
    require(normalized == document["settings"] and not changes)


class SessionManager:
    def __init__(self, vas_root: Path, state_home: Path | None = None):
        self.store = Store(vas_root, state_home)
        self.root = self.store.root
        require((self.root / "Run-VAS-System.bat").is_file() and
                (self.root / "src/vas-hub.html").is_file(), "vas_root_invalid")

    def _target(self, value):
        target = safe_directory(value)
        require(target != self.root and not self.root.is_relative_to(target), "target_is_vas")
        if target.is_relative_to(self.root):
            require(target.is_relative_to(self.root / "workspace") and
                    target != self.root / "workspace", "target_is_vas")
        return target

    def _records(self, data):
        records = data["sessions"]
        for key, record in records.items():
            fields(record, {"document", "binding"}, {"document", "binding"})
            valid_document(record["document"])
            require(key == record["document"]["sessionId"])
            binding = record["binding"]
            fields(binding, {"path", "identity"}, {"path", "identity"})
            require(isinstance(binding["path"], str) and Path(binding["path"]).is_absolute())
            require(isinstance(binding["identity"], list) and len(binding["identity"]) == 2 and
                    all(type(item) is int and item >= 0 for item in binding["identity"]))
        return records

    def _record(self, records, session_id):
        require(isinstance(session_id, str) and SESSION_ID.fullmatch(session_id), "session_id_invalid")
        require(session_id in records, "session_not_found")
        return records[session_id]

    def _view(self, record):
        binding = record["binding"]
        try:
            target = self._target(binding["path"])
            status = "available" if identity(target) == binding["identity"] else "changed"
            if not binding["identity"][1]:
                status = "unverified"
        except (OSError, SessionError) as error:
            status = "missing" if getattr(error, "code", "") == "target_missing" else "unsafe"
        return {"status": "resumed" if status == "available" else "target_unavailable",
                "session": deepcopy(record["document"]),
                "target": {"path": binding["path"], "status": status}}

    @staticmethod
    def _summary(record):
        doc = record["document"]
        return {"sessionId": doc["sessionId"], "revision": doc["revision"],
                "name": doc["settings"]["project"]["name"],
                "sourceType": doc["settings"]["project"]["sourceType"]}

    @staticmethod
    def _revision(record, expected_revision):
        require(type(expected_revision) is int and expected_revision >= 1, "revision_invalid")
        require(record["document"]["revision"] == expected_revision, "revision_conflict")

    @staticmethod
    def _stamp(document):
        document["updatedAt"] = datetime.now(timezone.utc).isoformat()

    def list(self):
        return [self._summary(record) for record in self._records(self.store.read()).values()]

    def create(self, raw_settings, target):
        settings, changes = normalize_settings(raw_settings)
        target = self._target(target)
        def update(data):
            records = self._records(data)
            require(len(records) < 64, "session_limit")
            require(not any(os.path.normcase(record["binding"]["path"]) == os.path.normcase(str(target))
                            for record in records.values()), "target_already_registered")
            doc = {"format": "vas-chat-session", "schemaVersion": 1, "sessionId": uuid.uuid4().hex,
                   "revision": 1, "settings": settings}
            self._stamp(doc)
            record = {"document": doc, "binding": {"path": str(target), "identity": identity(target)}}
            records[doc["sessionId"]] = record
            return dict(self._view(record), reviewFields=changes)
        return self.store.mutate(update)

    def resume(self, session_id=None, target=None):
        require(not (session_id is not None and target is not None), "selector_conflict")
        records = self._records(self.store.read())
        if session_id is not None:
            return self._view(self._record(records, session_id))
        if target is not None:
            canonical = str(self._target(target))
            matches = [record for record in records.values() if
                       os.path.normcase(record["binding"]["path"]) == os.path.normcase(canonical)]
            require(len(matches) == 1, "session_not_found")
            return self._view(matches[0])
        if not records:
            return {"status": "empty"}
        if len(records) > 1:
            return {"status": "selection_required", "sessions": [self._summary(r) for r in records.values()]}
        return self._view(next(iter(records.values())))

    def save(self, session_id, expected_revision, raw_settings):
        settings, changes = normalize_settings(raw_settings)
        def update(data):
            record = self._record(self._records(data), session_id)
            self._revision(record, expected_revision)
            require(self._view(record)["status"] == "resumed", "target_unavailable")
            record["document"]["settings"] = settings
            record["document"]["revision"] += 1
            self._stamp(record["document"])
            return dict(self._view(record), reviewFields=changes)
        return self.store.mutate(update)

    def rebind(self, session_id, expected_revision, target):
        target = self._target(target)
        def update(data):
            records = self._records(data)
            record = self._record(records, session_id)
            self._revision(record, expected_revision)
            require(not any(key != session_id and os.path.normcase(other["binding"]["path"]) ==
                            os.path.normcase(str(target)) for key, other in records.items()), "target_already_registered")
            record["binding"] = {"path": str(target), "identity": identity(target)}
            record["document"]["revision"] += 1
            self._stamp(record["document"])
            return self._view(record)
        return self.store.mutate(update)

    def forget(self, session_id, expected_revision):
        def update(data):
            records = self._records(data)
            self._revision(self._record(records, session_id), expected_revision)
            del records[session_id]
            return {"status": "forgotten", "sessionId": session_id}
        return self.store.mutate(update)

    def export(self, session_id):
        record = self._record(self._records(self.store.read()), session_id)
        return deepcopy(record["document"])
