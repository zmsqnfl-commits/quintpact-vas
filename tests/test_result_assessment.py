"""Shared policy fixtures plus JS/Python parity, with synthetic local observations."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("vas_result_assessment", ROOT / "scripts/vas_result_assessment.py")
ASSESSMENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSESSMENT)
FIXTURE = json.loads((ROOT / "tests/fixtures/result-assessment-cases.json").read_text(encoding="utf-8"))


def cases():
    rows = []
    for case in FIXTURE["cases"]:
        result = {**copy.deepcopy(FIXTURE["result"]), **copy.deepcopy(case.get("result", {}))}
        context = {**copy.deepcopy(FIXTURE["context"]), **copy.deepcopy(case.get("context", {}))}
        if case.get("review"):
            context["observations"] = [{**copy.deepcopy(FIXTURE["observation"]), **case.get("observation", {})}]
        rows.append({"name": case["name"], "result": result, "context": context, "expected": case["expected"]})
    return rows


@pytest.mark.parametrize("case", cases(), ids=lambda case: case["name"])
def test_completion_policy(case):
    before = copy.deepcopy(case)
    assert ASSESSMENT.evaluate_result(case["result"], case["context"])["status"] == case["expected"]
    assert case == before, "Assessment must not mutate the reported result or original conditions"


def test_js_python_policy_parity():
    node = shutil.which("node")
    assert node, "Node is required to check the shared browser/Python contract"
    script = """
require(process.argv[1]);
const rows = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(rows.map(row => VASResultAssessment.evaluate(row.result, row.context))));
"""
    rows = cases()
    run = subprocess.run([node, "-e", script, str(ROOT / "src/result-assessment.js")],
                         input=json.dumps(rows, ensure_ascii=False), text=True, encoding="utf-8",
                         capture_output=True, check=True)
    javascript = json.loads(run.stdout)
    python = [ASSESSMENT.evaluate_result(row["result"], row["context"]) for row in rows]
    assert javascript == python


@pytest.mark.parametrize("key,item", [("tests", {"status": "passed"}), ("remaining", {"severity": "low"}),
                                      ("evidence", {"criterionId": "C1", "method": "manual", "outcome": "passed"})])
def test_overflow_never_hides_last_failure(key, item):
    result = copy.deepcopy(FIXTURE["result"])
    result[key] = [copy.deepcopy(item) for _ in range(51)]
    assert ASSESSMENT.evaluate_result(result, FIXTURE["context"])["status"] == "invalid"
