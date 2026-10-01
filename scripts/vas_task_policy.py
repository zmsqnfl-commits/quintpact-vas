"""Scope and condition policy for newly generated, not restored, handoffs."""
from __future__ import annotations

METHODS = {"automatic": "자동 검사", "manual": "수동 확인", "static": "정적 검토"}
MODES = {"preserve": "기존 디자인 유지", "partial": "부분 디자인 수정", "redesign": "전체 리디자인", "new": "새 프로젝트 디자인"}


def safe_text(value, maximum, label, changes):
    try:
        from .vas_ai_contract import clean
    except ImportError:
        from vas_ai_contract import clean
    if not isinstance(value, str) or len(value.encode("utf-16-le")) // 2 > maximum:
        raise ValueError(f"{label}: 텍스트 {maximum}자 한도를 확인하세요. 내용을 줄여 다시 확인하세요.")
    normalized = clean(value, maximum)
    if normalized != value.strip():
        changes.append(label)
    return normalized


def design_direction(document):
    scope = (document.get("task") or {}).get("designScope") or {}
    mode = scope.get("mode")
    common = "디자인 선택은 데이터 삭제나 요청 밖 기능 변경 권한을 포함하지 않습니다."
    if mode == "preserve":
        return "기존 디자인 유지: 기존 컴포넌트·색상·글꼴·배치를 유지하세요. 요청 기능에 필요한 최소 UI 추가와 키보드 조작·레이블 보완만 기존 규칙으로 적용하세요. 관련 없는 화면의 디자인 변경은 허용하지 않습니다. 기존 모습과 필수 접근성 조건이 충돌하면 보고하세요. " + common
    if mode == "partial":
        return "부분 디자인 수정: " + scope.get("scope", "") + "\n지정한 화면·요소·속성에만 디자인 지침을 적용하고 나머지 기존 디자인은 유지하세요. " + common
    if mode in {"redesign", "new"}:
        return MODES[mode] + ": " + (scope.get("scope") or "요청에서 정한 UI 범위") + ". " + common
    return "이전 인계에 디자인 변경 범위가 없습니다. 변경 권한을 추정하지 말고 기존 요청을 확인하세요."


def quality():
    return {"requirementsConfirmed": False, "designConfirmed": False, "sourceHandlingConfirmed": False,
            "privacyChecked": False, "ragReviewed": False, "continuationReviewed": False,
            "automaticRedaction": {"applied": True, "scope": "known-sensitive-patterns", "guaranteesAbsence": False},
            "userConfirmation": {"status": "not-performed", "scope": []},
            "independentSecurityVerification": {"status": "not-performed"}}


def apply_task(document, raw_task, changes):
    if not isinstance(raw_task, dict):
        raise ValueError("작업 입력은 객체여야 합니다.")
    source_type = document["project"]["sourceType"]
    scope = raw_task.get("designScope", {"mode": "new" if source_type == "new" else "preserve", "scope": ""})
    if not isinstance(scope, dict) or not isinstance(scope.get("mode"), str) or scope.get("mode") not in MODES or (source_type == "new") != (scope.get("mode") == "new"):
        raise ValueError("디자인 변경 범위를 다시 선택하세요.")
    scope = {"mode": scope["mode"], "scope": safe_text(scope.get("scope", ""), 1000, "디자인 변경 범위", changes)}
    if scope["mode"] == "partial" and not scope["scope"]:
        raise ValueError("부분 수정할 화면·요소·속성을 입력하세요.")
    if scope["mode"] == "preserve":
        scope["scope"] = ""
    criteria = raw_task.get("completionCriteria", [])
    if not isinstance(criteria, list) or len(criteria) > 20:
        raise ValueError("완료조건은 최대 20개까지 입력하세요.")
    completed = []
    for index, item in enumerate(criteria, 1):
        if not isinstance(item, dict) or not isinstance(item.get("method"), str) or item.get("method") not in METHODS or not isinstance(item.get("required"), bool):
            raise ValueError("완료조건의 확인 방법과 필수 여부를 확인하세요.")
        description = safe_text(item.get("description"), 500, f"완료조건 {index}", changes)
        if not description:
            raise ValueError("빈 완료조건을 삭제하거나 내용을 입력하세요.")
        completed.append({"id": f"C{index}", "description": description, "method": item["method"], "required": item["required"]})
    constraints = raw_task.get("constraints", [])
    legacy = raw_task.get("acceptanceCriteria", [])
    if not isinstance(constraints, list) or len(constraints) > 20 or not isinstance(legacy, list) or len(legacy) > 20:
        raise ValueError("제약사항과 이전 완료조건은 각각 20개 이하여야 합니다.")
    document["task"] = {"request": safe_text(raw_task.get("request", ""), 4000, "요청", changes),
                        "constraints": [safe_text(item, 2000, "제약사항", changes) for item in constraints],
                        "designScope": scope, "completionCriteria": completed}
    task = document["task"]
    task["acceptanceCriteria"] = ([f"[{item['id']} · {'필수' if item['required'] else '선택'} · {METHODS[item['method']]}] {item['description']}" for item in completed]
                                  if "completionCriteria" in raw_task else [safe_text(item, 500, "이전 완료조건", changes) for item in legacy])
    task["validationGuidance"] = ["요청한 기능과 제약사항을 실제 산출물로 확인하고 실행한 검사·미실행 항목과 결과를 보고하세요.",
                                  "UI 변경은 기존 화면과 비교하세요. 요청에 필요한 최소 변경 외에 색상·글꼴·레이아웃을 유지했는지 확인하세요." if scope["mode"] == "preserve" else "허용한 UI 범위에서 선택한 디자인 지침과 참고 화면을 비교하고 모바일·데스크톱 차이를 확인하세요."]
    task["constraints"].append(design_direction(document))
    if scope["mode"] == "preserve":
        document["context"]["design"] = {"included": False}
    document["inputReview"] = {"required": bool(changes), "fields": list(dict.fromkeys(changes)), "acknowledged": False}
    return document
