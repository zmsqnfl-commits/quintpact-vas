"""Browser/Python contract parity using shared, synthetic JSON fixtures."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import subprocess
import pytest
from scripts.vas_ai_contract import validate_result, normalize_handoff, repair_legacy_numbers

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/result-validation-parity.json").read_text(encoding="utf-8"))


def document(case):
    if "root" in case:
        return copy.deepcopy(case["root"])
    raw = copy.deepcopy(FIXTURE["base"])
    for key in case.get("drop", []):
        raw.pop(key)
    for change in case["changes"]:
        keys = change["path"].split(".")
        owner = raw
        for key in keys[:-1]:
            owner = owner[int(key)] if isinstance(owner, list) else owner[key]
        value = copy.deepcopy(change["value"])
        if "repeat" in change:
            value = [copy.deepcopy(value) for _ in range(change["repeat"])]
        owner[int(keys[-1]) if isinstance(owner, list) else keys[-1]] = value
    return raw


def node(operation, documents):
    completed = subprocess.run(["node", str(ROOT / "tests/result-validation-parity.cjs")],
        input=json.dumps({"operation": operation, "documents": documents}, ensure_ascii=False),
        text=True, encoding="utf-8", capture_output=True, check=True, cwd=ROOT)
    return json.loads(completed.stdout)


@pytest.fixture(scope="module")
def browser_results():
    return node("result", [document(case) for case in FIXTURE["cases"]])


@pytest.mark.parametrize("index,case", enumerate(FIXTURE["cases"]), ids=[item["name"] for item in FIXTURE["cases"]])
def test_shared_result_fixture(index, case, browser_results):
    raw = document(case)
    if case["error"]:
        with pytest.raises(ValueError) as raised:
            validate_result(raw, "existing")
        assert str(raised.value) == case["error"]
        assert raised.value.error_codes == [case["error"]]
        expected = {"ok": False, "errorCodes": [case["error"]], "result": None}
    else:
        expected = {"ok": True, "errorCodes": [], "result": validate_result(raw, "existing")}
    assert browser_results[index] == expected


def test_incoming_trust_and_reported_status_cannot_promote_evidence():
    case = next(item for item in FIXTURE["cases"] if item["name"] == "untrusted imported evidence")
    result = validate_result(document(case))
    assert result["reportedStatus"] == "complete"
    assert "assessment" not in result and "userAcceptance" not in result
    assert result["evidence"][0]["source"] == "agent-submitted"
    assert "trusted" not in result["evidence"][0] and "verified" not in result["evidence"][0]


def test_legacy_repair_is_explicit_and_does_not_change_original():
    documents = []
    for value in [True, False, "1", "1.0", " 1 ", [], {}, None, "", "1x", "10000"]:
        raw = copy.deepcopy(FIXTURE["base"])
        raw["schemaVersion"], raw["iteration"] = "1", value
        documents.append(raw)
    originals = copy.deepcopy(documents)
    repaired = [repair_legacy_numbers(raw) for raw in documents]
    assert documents == originals
    assert repaired == node("repair", documents)
    assert repaired[0]["conversions"] == [
        {"field": "schemaVersion", "from": "1", "to": 1}, {"field": "iteration", "from": True, "to": 1}]
    assert repaired[0]["requiresConfirmation"] is True
    assert validate_result(repaired[0]["document"])["iteration"] == 1
    with pytest.raises(ValueError):
        validate_result(documents[0])


def test_handoff_numeric_and_shape_parity():
    documents, expected = [], []
    for value in [2, 2.0, 3, 3.0, True, False, "2", "3", [], {}, None, 2.5, 4]:
        documents.append({"format": "vas-ai-handoff", "schemaVersion": value})
        expected.append(None if type(value) in (int, float) and value in (2, 3) else "unsupported_handoff")
    for value in [1, 1.0, True, "1", [], {}, None, 10000]:
        documents.append({"format": "vas-ai-handoff", "schemaVersion": 3, "workflow": {"iteration": value}})
        expected.append(None if type(value) in (int, float) and value == 1 else "invalid_iteration")
    for field in ("workflow", "context", "task", "project", "assistantGuide", "integrity", "qualityGate", "security"):
        documents.append({"format": "vas-ai-handoff", "schemaVersion": 3, field: []})
        expected.append("invalid_handoff_object")
    observed = node("handoff", documents)
    for raw, code, browser in zip(documents, expected, observed):
        if code:
            with pytest.raises(ValueError, match="^" + code + "$"):
                normalize_handoff(raw, lambda _: "")
        else:
            assert normalize_handoff(raw, lambda _: "")["schemaVersion"] == 3
        assert browser == {"ok": code is None, "errorCodes": [code] if code else []}
