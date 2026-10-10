"""Design-studio metadata is optional in existing version-one chat documents."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vas_session import SessionError, SessionManager, normalize_settings, valid_document


@pytest.fixture
def service(tmp_path):
    root = tmp_path / "VAS"
    (root / "src").mkdir(parents=True)
    (root / "Run-VAS-System.bat").write_text("@echo off", encoding="utf-8")
    (root / "src/vas-hub.html").write_text("VAS", encoding="utf-8")
    target = root / "workspace/app"
    target.mkdir(parents=True)
    return SessionManager(root, tmp_path / "private-state"), target


@pytest.fixture
def settings():
    return {
        "project": {"name": "예약 도구", "sourceType": "new"},
        "task": {"request": "예약 CSV 내보내기", "constraints": ["로그인 제외"],
                 "designScope": {"mode": "new", "scope": "예약 화면"},
                 "completionCriteria": [{"description": "한글과 쉼표 보존",
                                         "method": "automatic", "required": True}]},
        "design": {"profileId": "editorial", "direction": "차분한 화면",
                   "tokens": {"radius": 8, "colors": {"primary": "#123456"}}},
        "questions": ["예약 시간 단위를 확인"], "nextStep": "입력 항목 확정",
    }


def test_original_v1_shape_remains_unchanged_without_studio_metadata(service, settings):
    manager, target = service
    first = manager.create(settings, target)["session"]
    valid_document(first)
    assert first["schemaVersion"] == 1
    assert set(first["settings"]["design"]) == {"profileId", "direction", "tokens"}
    assert first["settings"]["design"] == settings["design"]
    saved = manager.save(first["sessionId"], first["revision"], first["settings"])["session"]
    assert saved["settings"] == first["settings"]
    assert manager.export(first["sessionId"]) == saved


@pytest.mark.parametrize("metadata", [
    {"preset": "linear"}, {"basePreset": "awwwards"}, {"tasteProfileMode": "auto"},
    {"preset": "custom", "basePreset": "botanical", "tasteProfileMode": "editorial"},
    {"tasteProfileMode": "bentoStudio"}, {"tasteProfileMode": "premiumFrontend"},
    {"tasteProfileMode": "curatedProduct"},
])
def test_optional_metadata_round_trips_without_changing_other_settings(service, settings, metadata):
    manager, target = service
    original = manager.create(settings, target)["session"]
    changed = deepcopy(original["settings"])
    changed["design"].update(metadata)
    updated = manager.save(original["sessionId"], original["revision"], changed)["session"]
    valid_document(updated)
    assert updated["schemaVersion"] == 1
    assert updated["settings"] == changed
    assert updated["revision"] == original["revision"] + 1
    assert manager.resume(session_id=original["sessionId"])["session"] == updated
    assert normalize_settings(updated["settings"]) == (updated["settings"], [])


@pytest.mark.parametrize("key", ["preset", "basePreset", "tasteProfileMode"])
@pytest.mark.parametrize("value", [None, True, 1, [], {}, "", "../private",
                                 "https://example.invalid", "x" * 49, "preset\nnext"])
def test_invalid_metadata_cannot_mutate_saved_document(service, settings, key, value):
    manager, target = service
    original = manager.create(settings, target)["session"]
    changed = deepcopy(original["settings"])
    changed["design"][key] = value
    with pytest.raises(SessionError):
        manager.save(original["sessionId"], original["revision"], changed)
    assert manager.export(original["sessionId"]) == original


@pytest.mark.parametrize("key", ["preset", "basePreset"])
def test_preset_keys_remain_lowercase_even_when_profile_names_allow_camel_case(service, settings, key):
    manager, target = service
    original = manager.create(settings, target)["session"]
    changed = deepcopy(original["settings"])
    changed["design"][key] = "Awwwards"
    with pytest.raises(SessionError):
        manager.save(original["sessionId"], original["revision"], changed)
    assert manager.export(original["sessionId"]) == original


def test_existing_preserve_discards_all_studio_fields_and_cannot_restore_stale_tokens(service, settings):
    manager, target = service
    settings["design"].update(preset="custom", basePreset="linear", tasteProfileMode="editorial")
    first = manager.create(settings, target)["session"]
    changed = deepcopy(first["settings"])
    changed["project"]["sourceType"] = "existing"
    changed["task"]["designScope"] = {"mode": "preserve", "scope": "stale scope"}
    second = manager.save(first["sessionId"], first["revision"], changed)["session"]
    assert second["settings"]["design"] == {"profileId": "", "direction": "", "tokens": {}}
    assert second["settings"]["task"]["designScope"] == {"mode": "preserve", "scope": ""}
    assert second["settings"]["task"]["completionCriteria"] == first["settings"]["task"]["completionCriteria"]
    assert normalize_settings(second["settings"]) == (second["settings"], [])


def test_optional_metadata_does_not_expand_the_design_allowlist(service, settings):
    manager, target = service
    original = manager.create(settings, target)["session"]
    changed = deepcopy(original["settings"])
    changed["design"]["script"] = "run-untrusted-code"
    with pytest.raises(SessionError):
        manager.save(original["sessionId"], original["revision"], changed)
    assert manager.export(original["sessionId"]) == original
