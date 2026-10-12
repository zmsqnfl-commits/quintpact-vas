"""Fresh-process delivery journeys with real host commands and conservative reports."""
from copy import deepcopy
import json
import subprocess
import sys

import pytest

from test_chat_session import layout, settings, manager, run_cli, successful_cli
from test_session_execution import result


class Journey:
    """Every VAS operation launches a new process; only the host changes app files."""

    def __init__(self, layout, settings):
        self.layout, self.app = layout, layout[2]
        self.service = manager(layout)
        self.n = self.w = self.p = 0
        created = self.call("create", "--target", str(self.app), data=settings)
        self.sid = created["session"]["sessionId"]

    def files(self):
        return {str(p.relative_to(self.app)): p.read_bytes()
                for p in self.app.rglob("*") if p.is_file()}

    def call(self, *args, data=None):
        files = self.files()
        value = successful_cli(self.layout, *args, data=data)
        assert self.files() == files, "VAS must never implement or execute the app"
        if "session" in value:
            self.n = value["session"]["revision"]
        if "work" in value:
            self.w = value["work"]["revision"]
        if "progress" in value:
            self.p = value["progress"]["revision"]
        return value

    def session(self, action, data=None, *extra):
        args = [action, "--session", self.sid]
        if action not in {"resume", "export"}:
            args += ["--expected-revision", str(self.n)]
        return self.call(*args, *extra, data=data)

    def work(self, action, data=None, unit=None):
        args = ["work", action, "--session", self.sid, "--expected-revision", str(self.n)]
        if action != "inspect":
            args += ["--expected-work-revision", str(self.w)]
        if unit:
            args += ["--unit", unit]
        return self.call(*args, data=data)

    def rejected(self, code, *args, data=None):
        before, files = self.service.store.path.read_bytes(), self.files()
        response = run_cli(self.layout, *args, data=data)
        assert response.returncode == 1, response.stdout + response.stderr
        assert json.loads(response.stdout)["code"] == code
        assert self.service.store.path.read_bytes() == before
        assert self.files() == files

    def checkpoint(self, phase, summary, next_step):
        return self.session("checkpoint", {
            "phase": phase, "summary": summary, "nextStep": next_step,
            "changedFiles": [], "decisions": [], "checks": [], "remaining": [],
        }, "--expected-progress-revision", str(self.p))

    def execute(self, name):
        run = subprocess.run([sys.executable, "-B", name], cwd=self.app,
                             capture_output=True, text=True, encoding="utf-8", timeout=10)
        return run.returncode

    def finish(self, unit, code=None, criteria=(), changed=()):
        state = "returned" if code in {0, None} else "failed"
        return self.work("finish", {
            "state": state, "hostCallId": "delivery-" + unit,
            "summary": "Host command exit " + str(code) if code is not None else "Host implementation",
            "changedFiles": list(changed), "exitCode": code,
            "criteria": [{"id": cid, "status": status, "summary": "Observed by test host"}
                         for cid, status in criteria],
        }, unit)

    def assessed(self, prepared, outcomes, tests):
        sample = self.work("inspect")
        submitted = result(prepared)
        submitted["artifactVersion"] = sample["artifactVersion"]
        submitted["tests"] = [{"name": name, "command": "python -B " + name,
                               "status": status, "summary": "Actual host command"}
                              for name, status in tests]
        submitted["evidence"] = [
            {"criterionId": cid, "method": "automatic", "outcome": status,
             "artifactVersion": sample["artifactVersion"], "summary": "Actual host command"}
            for cid, status in outcomes]
        before = self.service.store.path.read_bytes()
        assessed = self.session("assess", submitted)
        assert self.service.store.path.read_bytes() == before
        return assessed


def assignment(kind, files, ids=(), command="", writable=(), supersedes=None):
    value = {"kind": kind, "role": "reviewer" if kind == "review" else "main",
             "mode": "direct", "label": "Delivery flow " + kind,
             "observedFiles": list(files), "writableFiles": list(writable),
             "criterionIds": list(ids), "command": command}
    if supersedes:
        value["supersedes"] = supersedes
    return value


def kinds(assessed):
    return [item["kind"] for item in assessed["followUp"]["actions"]]


def write_app(app, source):
    for name, content in source.items():
        (app / name).write_text(content, encoding="utf-8", newline="\n")


@pytest.mark.parametrize("source_type", ["new", "existing"])
def test_question_pause_repair_and_followup_across_fresh_processes(layout, settings, source_type):
    settings["project"]["sourceType"] = source_type
    if source_type == "existing":
        settings["task"]["designScope"] = {"mode": "preserve"}
        write_app(layout[2], {"style.css": ":root { color: #123456; }\n",
                              "calc.py": "def total(values):\n    return 0\n"})
    protected_style = (layout[2] / "style.css").read_bytes() if source_type == "existing" else None
    settings["task"]["request"] = "Sum integer amounts and preserve the independent label"
    settings["task"]["completionCriteria"] = [
        {"description": "Integer amount sum is correct", "method": "automatic", "required": True},
        {"description": "Label preserves Hangul and commas", "method": "automatic", "required": True},
        {"description": "Optional appearance check", "method": "manual", "required": False},
    ]
    settings["blockingQuestions"] = ["Should amounts use integer units?"]
    settings["questions"] = []
    flow = Journey(layout, settings)
    pending = flow.session("prepare")
    assert pending["status"] == "needs-input" and pending["missing"] == ["blockingQuestions"]
    flow.rejected("execution_needs_input", "work", "open", "--session", flow.sid,
                  "--expected-revision", "1", "--expected-work-revision", "0")

    answered = deepcopy(flow.session("resume")["session"]["settings"])
    answered["blockingQuestions"] = []
    answered["task"]["constraints"].append("Use integer units; do not round amounts")
    answered["nextStep"] = "Implement integer sum and label checks"
    flow.session("save", answered)
    prepared = flow.session("prepare")
    assert prepared["status"] == "prepared" and flow.n == 2
    assert "Should amounts" not in prepared["handoff"]["assistantGuide"]["pasteText"]
    assert prepared["handoff"]["task"]["designScope"]["mode"] == ("new" if source_type == "new" else "preserve")
    flow.work("open")
    sources = {"calc.py": "def total(values):\n    return sum(values[1:])\n",
               "label.py": "def label():\n    return '예약, 금액'\n",
               "check_calc.py": "from calc import total\nassert total([100, 200]) == 300\nassert total([]) == 0\n",
               "check_label.py": "from label import label\nassert label() == '예약, 금액'\n"}
    implementation = flow.work("start", assignment("implementation", sources, writable=sources))["unitId"]
    write_app(flow.app, sources)
    flow.finish(implementation, changed=sources)
    previous_context = flow.session("resume")["work"]["record"]["context"]
    flow.checkpoint("paused", "Implemented; no verification command has run", "Read source, then run both checks")
    resumed = flow.session("resume")
    assert resumed["progress"]["record"]["summary"]["phase"] == "paused"
    assert resumed["work"]["status"] == "stale" and flow.n == 3
    assert resumed["work"]["record"]["context"] == previous_context
    assert resumed["session"]["settings"]["blockingQuestions"] == []
    assert resumed["session"]["settings"]["task"] == answered["task"]
    prepared = flow.session("prepare")
    stale = flow.assessed(prepared, [], [])
    assert kinds(stale) == ["reconcile-context"]
    assert stale["followUp"]["reusableCriteria"] == []
    calc = assignment("verification", ["calc.py", "check_calc.py"], ["C1"], "python -B check_calc.py")
    label = assignment("verification", ["label.py", "check_label.py"], ["C2"], "python -B check_label.py")
    flow.rejected("work_context_changed", "work", "start", "--session", flow.sid,
                  "--expected-revision", str(flow.n), "--expected-work-revision", str(flow.w), data=calc)
    # The host compares the resumed task/source before opening a new context.
    assert flow.files() == {name: value.encode("utf-8") for name, value in sources.items()} | (
        {"style.css": protected_style} if protected_style else {})
    flow.work("open")
    label_unit = flow.work("start", label)["unitId"]
    label_exit = flow.execute("check_label.py")
    assert label_exit == 0
    flow.finish(label_unit, label_exit, [("C2", "passed")])
    calc_unit = flow.work("start", calc)["unitId"]
    calc_exit = flow.execute("check_calc.py")
    assert calc_exit != 0
    flow.finish(calc_unit, calc_exit, [("C1", "failed")])
    failed = flow.assessed(prepared, [("C1", "failed"), ("C2", "passed")],
                           [("check_calc.py", "failed"), ("check_label.py", "passed")])
    assert failed["assessment"]["status"] == "incomplete"
    assert "fix-failure" in kinds(failed) and "confirm-user" not in kinds(failed)
    assert failed["followUp"]["reusableCriteria"] == ["C2"]
    fix = next(item for item in failed["followUp"]["actions"] if item["kind"] == "fix-failure")
    assert fix["criterionIds"] == ["C1"] and fix["testIndexes"] == [0]
    flow.rejected("revision_conflict", "save", "--session", flow.sid,
                  "--expected-revision", "2", data=answered)
    flow.rejected("work_revision_conflict", "work", "start", "--session", flow.sid,
                  "--expected-revision", "3", "--expected-work-revision", str(flow.w - 1), data=calc)

    repair = flow.work("start", assignment("implementation", ["calc.py"], writable=["calc.py"]))["unitId"]
    write_app(flow.app, {"calc.py": "def total(values):\n    return sum(values)\n"})
    flow.finish(repair, changed=["calc.py"])
    changed = flow.assessed(prepared, [("C1", "failed"), ("C2", "passed")], [])
    rerun = next(item for item in changed["followUp"]["actions"] if item["kind"] == "rerun-check")
    assert rerun["criterionIds"] == ["C1"] and rerun["unitIds"] == [calc_unit]
    assert changed["followUp"]["reusableCriteria"] == ["C2"]
    retry = flow.work("start", dict(calc, supersedes=calc_unit))["unitId"]
    calc_exit = flow.execute("check_calc.py")
    assert calc_exit == 0
    flow.finish(retry, calc_exit, [("C1", "passed")])
    finished = flow.assessed(prepared, [("C1", "passed"), ("C2", "passed")],
                             [("check_calc.py", "passed"), ("check_label.py", "passed")])
    advice = finished["followUp"]
    assert finished["assessment"]["status"] == "needs-verification"
    assert advice["actions"] == [] and advice["reusableCriteria"] == ["C1", "C2"]
    assert advice["complete"] is advice["executionAuthorized"] is False
    assert advice["userAcceptance"] == "not-recorded"
    record = flow.session("resume")["work"]["record"]
    assert len([unit for unit in record["units"] if unit["command"] == "python -B check_label.py"]) == 1
    assert len([unit for unit in record["units"] if unit["command"] == "python -B check_calc.py"]) == 2
    flow.checkpoint(advice["suggestedPhase"], "Both current samples passed; no user acceptance recorded", advice["nextStep"])
    final = flow.session("resume")
    assert final["progress"]["record"]["summary"]["phase"] == "awaiting-request"
    assert final["session"]["settings"]["nextStep"] == advice["nextStep"]
    assert final["session"]["settings"]["task"] == answered["task"]
    public = flow.session("export")
    assert not {"progress", "work", "followUp"} & public.keys()
    if protected_style:
        assert (flow.app / "style.css").read_bytes() == protected_style


def test_pending_then_failed_review_survives_passing_command_and_restart(layout, settings):
    settings["task"]["completionCriteria"] = [
        {"description": "Integer sum rejects negative inputs", "method": "automatic", "required": True}]
    settings["questions"] = []
    flow = Journey(layout, settings)
    prepared = flow.session("prepare")
    write_app(flow.app, {"calc.py": "def total(values):\n    return sum(values)\n",
                         "check_calc.py": "from calc import total\nassert total([100, 200]) == 300\n",
                         "review_probe.py": "from calc import total\ntry:\n    total([-1])\nexcept ValueError:\n    pass\nelse:\n    raise AssertionError('Negative amount accepted')\n"})
    flow.work("open")
    verification = flow.work("start", assignment("verification", ["calc.py", "check_calc.py"],
                             ["C1"], "python -B check_calc.py"))["unitId"]
    assert flow.execute("check_calc.py") == 0
    flow.finish(verification, 0, [("C1", "passed")])
    reviewer = flow.work("start", assignment("review", ["calc.py", "review_probe.py"],
                                             ["C1"], "python -B review_probe.py"))["unitId"]
    pending = flow.assessed(prepared, [("C1", "passed")], [("check_calc.py", "passed")])
    assert pending["assessment"]["status"] == "incomplete"
    assert "recover-role" in kinds(pending) and pending["followUp"]["suggestedPhase"] == "blocked"
    assert pending["followUp"]["reusableCriteria"] == []
    flow.rejected("work_pending", "work", "open", "--session", flow.sid,
                  "--expected-revision", str(flow.n), "--expected-work-revision", str(flow.w))
    code = flow.execute("review_probe.py")
    assert code != 0
    flow.finish(reviewer, code, [("C1", "failed")])
    assert flow.session("resume")["work"]["record"]["units"][-1]["result"]["state"] == "failed"
    assessed = flow.assessed(prepared, [("C1", "passed")], [("check_calc.py", "passed")])
    assert assessed["assessment"]["status"] == "incomplete"
    assert "fix-failure" in kinds(assessed) and "recover-role" not in kinds(assessed)
    assert assessed["followUp"]["criteria"][0]["state"] == "failed"
    assert assessed["followUp"]["reusableCriteria"] == []
    assert assessed["followUp"]["complete"] is False
