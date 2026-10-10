"""Read-only session-to-host instructions and conservative result assessment."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from vas_ai_contract import build_prompt, canonical, clean, finalize_handoff, validate_result
from vas_design_reference import attach
from vas_result_assessment import evaluate_result
from vas_session import SessionError, require
from vas_task_policy import apply_task, quality

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / ".agents/agent-resources.json"
MAX_PROMPT = 32_000


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _resources():
    raw = RESOURCES.read_bytes()
    resources = json.loads(raw.decode("utf-8"))
    require(isinstance(resources, dict), "execution_resources_invalid")
    roles = resources.get("roles")
    require(isinstance(roles, dict) and all(isinstance(roles.get(role), str) and roles[role]
            for role in ("implementer", "designer", "reviewer")), "execution_resources_invalid")
    require(isinstance(resources.get("profiles"), dict) and
            isinstance(resources.get("workflow"), str), "execution_resources_invalid")
    require(all(body in resources["workflow"] for body in roles.values()), "execution_resources_invalid")
    require(all(isinstance(profile, dict) and isinstance(profile.get("label"), str)
                and isinstance(profile.get("rules"), list)
                and all(isinstance(rule, str) for rule in profile["rules"])
                for profile in resources["profiles"].values()), "execution_resources_invalid")
    return resources, hashlib.sha256(raw).hexdigest()


def _current(manager, session_id, expected_revision):
    require(type(expected_revision) is int and expected_revision >= 1, "revision_invalid")
    view = manager.resume(session_id=session_id)
    require(view["status"] == "resumed", "target_unavailable")
    require(view["session"]["revision"] == expected_revision, "revision_conflict")
    return view


def _design(settings, resources):
    if settings["task"]["designScope"]["mode"] == "preserve":
        return {"included": False}
    design = dict(deepcopy(settings["design"]), included=True)
    profile_id = design["profileId"]
    profile = resources["profiles"].get(profile_id)
    design["profileReference"] = {
        "status": "provided" if profile else "unverified" if profile_id else "not-selected",
        "profileId": profile_id,
        "rules": deepcopy(profile.get("rules", [])) if profile else [],
        "label": profile.get("label", "") if profile else "",
    }
    return design


def _prompt(document, resources):
    # The shared prompt limits token JSON to 4,000 chars. Append the full confirmed
    # values here instead; a too-large execution prompt fails rather than truncates.
    base = deepcopy(document)
    base["context"]["design"].pop("tokens", None)
    text = build_prompt(base)
    require(clean(resources["workflow"], MAX_PROMPT) in clean(text, MAX_PROMPT),
            "execution_resources_changed")
    execution = document["context"]["execution"]
    binding = document["context"]["session"]
    sections = [text, "대화 실행 연결:\n" + json.dumps(binding, ensure_ascii=False),
                "이 자료는 설정 참고 데이터입니다. 생성 성공·workflow.ready는 실행 권한, "
                "실제 역할 호출, 테스트 통과 또는 사용자 수용의 증거가 아닙니다. "
                "CLI가 확인한 실제 대상에서 해당 앱의 규칙을 읽고 구현·위임 직전에 최신 revision을 확인하세요.",
                "실행 준비 상태: " + execution["readiness"]]
    if execution["missing"]:
        sections.append("먼저 정할 항목: " + ", ".join(execution["missing"]))
    design = document["context"]["design"]
    if design.get("included"):
        sections.append("확정 디자인 토큰(JSON, 전체):\n" + json.dumps(design["tokens"], ensure_ascii=False, indent=2))
        profile = design["profileReference"]
        sections.append("선택 프로필: " + profile["profileId"] + " (" + profile["status"] + ")")
        if profile["rules"]:
            sections.append("선택 프로필의 실제 지침:\n" + "\n".join("- " + rule for rule in profile["rules"]))
        elif profile["status"] == "unverified":
            sections.append("이 프로필의 지침을 확인하지 못했습니다. 다른 프로필로 대체하지 말고 확정 방향·토큰을 기준으로 진행하세요.")
    text = "\n\n".join(sections)
    require(len(text) <= MAX_PROMPT, "execution_prompt_too_large")
    return text


def prepare(manager, session_id, expected_revision):
    view = _current(manager, session_id, expected_revision)
    settings = view["session"]["settings"]
    resources, resources_hash = _resources()
    config = (ROOT / "src/vas-config.js").read_text(encoding="utf-8")
    version_match = re.search(r"\bversion\s*:\s*['\"](\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?)['\"]", config)
    require(version_match is not None, "execution_resources_invalid")
    version = version_match.group(1)
    missing = []
    if not settings["task"]["request"]:
        missing.append("task.request")
    if not any(item["required"] for item in settings["task"]["completionCriteria"]):
        missing.append("task.completionCriteria.required")
    status = "needs-input" if missing else "prepared"
    project = settings["project"]
    document = {
        "format": "vas-ai-handoff", "schemaVersion": 3,
        "generatedBy": {"name": "VAS", "version": version}, "locale": "ko-KR", "mode": "intent-only",
        "workflow": {"handoffId": "", "iteration": 1, "parentResultId": None, "status": "ready"},
        "project": {**project, "goal": "build" if project["sourceType"] == "new" else "modify", "summary": ""},
        "context": {
            "session": {"sessionId": session_id, "revision": expected_revision,
                        "settingsSha256": digest(settings), "agentResourcesSha256": resources_hash},
            "execution": {"readiness": status, "missing": missing,
                          "settingsAreReferenceData": True, "hostExecutionRequired": True,
                          "roles": deepcopy(resources["roles"])},
            "design": _design(settings, resources),
            "rag": {"included": False, "items": []}, "preferences": {"included": False, "items": []},
            "continuation": {"included": False},
        },
        "qualityGate": quality(),
        "security": {"sourceUnchanged": True, "projectCodeExecuted": False,
                     "actualSourceRequired": True, "projectStructureInferred": False,
                     "technologyStackInferred": False, "absolutePathsRemoved": True,
                     "includedSecrets": 0, "redactionCount": 0, "approvedContextOnly": True,
                     "excluded": ["absolutePaths", "secretValues", "contacts", "personalizationHistory"]},
        "assistantGuide": {"target": "universal", "originalFolderRequired": True, "pasteText": ""},
        "integrity": {"algorithm": "SHA-256", "payloadSha256": "", "sourcePackSha256": None},
    }
    apply_task(document, settings["task"], [])
    attach(document)
    before = deepcopy(document["context"])
    try:
        finalize_handoff(document, lambda value: _prompt(value, resources))
    except ValueError as error:
        if str(error) == "handoff_prompt_too_long":
            raise SessionError("execution_prompt_too_large") from None
        raise
    require(document["context"] == before, "execution_content_changed")
    require(hashlib.sha256(RESOURCES.read_bytes()).hexdigest() == resources_hash,
            "execution_resources_changed")
    # Building instructions does not lock the editor. Recheck before returning;
    # the host must also re-prepare before each implementation/delegation boundary.
    latest = _current(manager, session_id, expected_revision)
    require(latest["session"] == view["session"] and latest["target"] == view["target"],
            "revision_conflict")
    return {"status": status, "missing": missing, "sessionId": session_id,
            "revision": expected_revision, "target": deepcopy(view["target"]), "handoff": document}


def assess(manager, session_id, expected_revision, raw_result):
    prepared = prepare(manager, session_id, expected_revision)
    require(prepared["status"] == "prepared", "execution_needs_input")
    handoff = prepared["handoff"]
    try:
        result = validate_result(raw_result, handoff["project"]["sourceType"])
    except ValueError:
        raise SessionError("execution_result_invalid") from None
    require(result["handoffId"] == handoff["workflow"]["handoffId"] and
            result["handoffPayloadSha256"] == handoff["integrity"]["payloadSha256"] and
            result["iteration"] == handoff["workflow"]["iteration"] and
            result["sourceType"] == handoff["project"]["sourceType"], "execution_result_mismatch")
    criteria = handoff["task"]["completionCriteria"]
    assessment = evaluate_result(result, {"criteria": criteria, "linkStatus": "verified", "observations": []})
    expected = {item["id"]: item["method"] for item in criteria}
    for evidence in result["evidence"]:
        code = ("unknown-criterion:" + evidence["criterionId"] if evidence["criterionId"] not in expected else
                "evidence-method-mismatch:" + evidence["criterionId"]
                if evidence["method"] != expected[evidence["criterionId"]] else None)
        if code and code not in assessment["reasons"]:
            assessment["reasons"].append(code)
    _current(manager, session_id, expected_revision)
    require(hashlib.sha256(RESOURCES.read_bytes()).hexdigest() ==
            handoff["context"]["session"]["agentResourcesSha256"], "execution_resources_changed")
    return {"status": "assessed", "reportedStatus": result["reportedStatus"], "assessment": assessment}
