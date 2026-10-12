"""Optional blocking questions preserve old sessions and the design-only boundary."""
from copy import deepcopy
import hashlib
import json

import pytest

from test_chat_session import assert_no_text, layout, manager, settings
from test_session_web import request
from vas_session import SessionError, normalize_settings
from vas_session_web import dispatch


def snapshot(service):
    return {str(path.relative_to(service.store.home)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in service.store.home.rglob("*") if path.is_file()}


def test_absent_optional_question_key_preserves_canonical_reads_and_hash(layout, settings):
    service = manager(layout)
    first = service.create(settings, layout[2])["session"]
    before = snapshot(service)
    original = json.dumps(first["settings"], ensure_ascii=False, sort_keys=True).encode("utf-8")
    normalized, changes = normalize_settings(first["settings"])
    assert normalized == first["settings"] and not changes
    assert "blockingQuestions" not in normalized
    for restored in (manager(layout).resume()["session"], service.export(first["sessionId"]),
                     dispatch(service, "get", {"sessionId": first["sessionId"]})["session"]):
        assert restored == first
        current = json.dumps(restored["settings"], ensure_ascii=False, sort_keys=True).encode("utf-8")
        assert hashlib.sha256(current).digest() == hashlib.sha256(original).digest()
    assert service.list()[0]["revision"] == first["revision"]
    assert snapshot(service) == before


@pytest.mark.parametrize("blockers", [[], ["핵심 질문"], [f"질문 {index}" for index in range(10)]])
def test_optional_question_array_round_trips_without_changing_advisory_questions(layout, settings, blockers):
    settings["blockingQuestions"] = blockers
    settings["questions"] = ["", "참고 질문"]
    service = manager(layout)
    first = service.create(settings, layout[2])["session"]
    restored = manager(layout).resume()["session"]
    assert restored == first
    assert restored["settings"]["blockingQuestions"] == blockers
    assert restored["settings"]["questions"] == settings["questions"]
    assert service.save(first["sessionId"], first["revision"], first["settings"])["session"]["settings"] == first["settings"]


@pytest.mark.parametrize("invalid", [None, True, "", "question", {}, [42], [True], [None],
                                      [""], [" \t\n "], ["\x00"], ["질문"] * 11])
def test_invalid_blocking_questions_never_modify_saved_state(layout, settings, invalid):
    service = manager(layout)
    first = service.create(settings, layout[2])["session"]
    before = snapshot(service)
    changed = deepcopy(first["settings"])
    changed["blockingQuestions"] = invalid
    with pytest.raises(SessionError, match="question_invalid"):
        service.save(first["sessionId"], first["revision"], changed)
    assert service.resume()["session"] == first
    assert snapshot(service) == before


@pytest.mark.parametrize("question", ["가" * 501, "😀" * 251])
def test_question_length_uses_existing_safe_text_limit(layout, settings, question):
    service = manager(layout)
    first = service.create(settings, layout[2])["session"]
    before = snapshot(service)
    settings["blockingQuestions"] = [question]
    with pytest.raises(ValueError, match="blockingQuestions"):
        service.save(first["sessionId"], first["revision"], settings)
    assert snapshot(service) == before


def test_question_trim_and_utf16_boundary_use_existing_text_rules(settings):
    settings["blockingQuestions"] = ["  결정 필요  ", "가" * 500, "😀" * 250]
    settings["questions"] = ["결정 필요", " "]
    normalized, _ = normalize_settings(settings)
    assert normalized["blockingQuestions"] == ["결정 필요", "가" * 500, "😀" * 250]
    assert normalized["questions"] == ["결정 필요", ""]


def test_new_blocking_question_secrets_and_paths_are_redacted_before_persistence(layout, settings):
    private = ["QuestionCredential47", "owner@example.com", "010-1234-5678",
               r"C:\Users\private\questions.txt", "/volume1/private/questions.txt", "/opt/private/questions.txt"]
    settings["blockingQuestions"] = ['password="' + private[0] + '"', *private[1:]]
    settings["questions"] = ["참고 질문"]
    service = manager(layout)
    first = service.create(settings, layout[2])
    assert "blockingQuestions" in first["reviewFields"]
    public = dispatch(service, "get", {"sessionId": first["session"]["sessionId"]})
    assert_no_text([first["session"], service.export(first["session"]["sessionId"]), public], private)
    assert_no_text(service.store.read(), private)
    assert public["session"]["settings"]["questions"] == ["참고 질문"]


@pytest.fixture
def legacy_question(layout, settings):
    settings["blockingQuestions"] = ["저장된 핵심 질문"]
    service = manager(layout)
    first = service.create(settings, layout[2])["session"]
    data = service.store.read()
    data["sessions"][first["sessionId"]]["document"]["settings"]["blockingQuestions"] = [
        "password%3aQuestionLegacyCanary47", "/opt/private/questions.txt"]
    service.store.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return service, first


def test_legacy_question_privacy_views_are_read_only_and_web_save_requires_review(legacy_question):
    service, first = legacy_question
    before = snapshot(service)
    identifier = first["sessionId"]
    for view in (service.resume(session_id=identifier), dispatch(service, "get", {"sessionId": identifier})):
        assert "blockingQuestions" in view["reviewFields"]
        assert view["session"]["revision"] == first["revision"]
        assert view["session"]["settings"]["blockingQuestions"] == ["[redacted]", "[absolute-path]"]
        assert_no_text(view, ["QuestionLegacyCanary47", "/opt/private/questions.txt"])
    assert_no_text(service.export(identifier), ["QuestionLegacyCanary47", "/opt/private/questions.txt"])
    assert service.list()[0]["reviewFields"]
    with pytest.raises(SessionError, match="session_review_required"):
        dispatch(service, "design", request(first))
    assert snapshot(service) == before


@pytest.mark.parametrize("invalid", ["question", [True], [""], [" noncanonical "], ["line\tbreak"]])
def test_privacy_upgrade_does_not_repair_question_structure_or_whitespace(legacy_question, invalid):
    service, first = legacy_question
    data = service.store.read()
    saved = data["sessions"][first["sessionId"]]["document"]["settings"]
    saved["task"]["request"] = "password%3aQuestionLegacyCanary47"
    saved["blockingQuestions"] = invalid
    service.store.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    before = snapshot(service)
    with pytest.raises(SessionError):
        service.resume(session_id=first["sessionId"])
    assert snapshot(service) == before


@pytest.mark.parametrize("blockers", [None, [], ["확정할 핵심 질문"]])
def test_web_design_save_preserves_both_question_arrays_and_next_step(layout, settings, blockers):
    if blockers is not None:
        settings["blockingQuestions"] = blockers
    service = manager(layout)
    first = service.create(settings, layout[2])["session"]
    payload = request(first)
    updated = dispatch(service, "design", payload)["session"]
    expected = deepcopy(first["settings"])
    expected["design"] = payload["design"]
    expected["task"]["designScope"] = payload["designScope"]
    assert updated["settings"] == expected
    assert updated["revision"] == first["revision"] + 1
    assert manager(layout).resume()["session"] == updated
    before = snapshot(service)
    with pytest.raises(SessionError, match="session_invalid"):
        dispatch(service, "design", request(updated, blockingQuestions=[]))
    assert snapshot(service) == before


def test_concurrent_chat_save_protects_new_question_state_from_stale_web_save(layout, settings, monkeypatch):
    settings["blockingQuestions"] = ["이전 핵심 질문"]
    service = manager(layout)
    first = service.create(settings, layout[2])["session"]
    changed = deepcopy(first["settings"])
    changed.update(questions=["새 참고 질문"], blockingQuestions=["새 핵심 질문"], nextStep="새 다음 단계")
    real_save = service.save

    def racing_save(identifier, revision, raw, **kwargs):
        manager(layout).save(identifier, revision, changed)
        return real_save(identifier, revision, raw, **kwargs)

    monkeypatch.setattr(service, "save", racing_save)
    with pytest.raises(SessionError, match="revision_conflict"):
        dispatch(service, "design", request(first))
    restored = manager(layout).resume()["session"]
    assert restored["settings"] == changed
    assert restored["revision"] == first["revision"] + 1


def test_web_save_rechecks_new_legacy_question_review_inside_lock(layout, settings, monkeypatch):
    settings["blockingQuestions"] = ["핵심 질문"]
    service = manager(layout)
    first = service.create(settings, layout[2])["session"]
    real_save = service.save

    def changed_before_save(identifier, revision, raw, **kwargs):
        data = service.store.read()
        data["sessions"][identifier]["document"]["settings"]["blockingQuestions"] = [
            "password%3aQuestionLegacyCanary47"]
        service.store.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return real_save(identifier, revision, raw, **kwargs)

    monkeypatch.setattr(service, "save", changed_before_save)
    with pytest.raises(SessionError, match="session_review_required"):
        dispatch(service, "design", request(first))
    resumed = manager(layout).resume()["session"]
    assert resumed["revision"] == first["revision"]
    assert resumed["settings"]["design"] == first["settings"]["design"]
    assert resumed["settings"]["blockingQuestions"] == ["[redacted]"]
